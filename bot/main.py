"""Точка запуска бота и HTTP webhook для YooKassa."""
from __future__ import annotations
import asyncio,logging,sys
from aiohttp import web
from aiogram import Bot,Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiogram.utils.token import TokenValidationError
from bot.config import ConfigError,RedactingFormatter,Settings,load_settings
from bot.db.database import Database
from bot.handlers import account,features,start,legal,payments
from bot.services.ai_router import AIService
from bot.services.credits import CreditsService,UserNotFound
from bot.services.payments import YooKassaClient,PaymentError
from bot.services.text_provider import OpenAICompatibleTextProvider

log=logging.getLogger("bot"); LOG_FORMAT="%(asctime)s %(levelname)s %(name)s: %(message)s"

def setup_logging(secret=""):
    handler=logging.StreamHandler(); handler.setFormatter(RedactingFormatter(secret,LOG_FORMAT)); logging.basicConfig(level=logging.INFO,handlers=[handler],force=True)

def build_dispatcher(db,credits,settings:Settings|None=None):
    dp=Dispatcher(storage=MemoryStorage()); dp.include_routers(start.router,account.router,features.router,payments.router,legal.router)
    ai_service=AIService(credits,db)
    if settings and settings.ai_api_key:
        ai_service.register(OpenAICompatibleTextProvider(settings.ai_api_key,settings.ai_api_base_url,settings.ai_model))
        log.info("Текстовый провайдер включён: openai/%s",settings.ai_model)
    else: log.info("AI_API_KEY не задан: реальные текстовые вызовы отключены")
    dp.workflow_data.update(db=db,credits=credits,ai_router=ai_service,ai_service=ai_service,settings=settings)
    return dp

async def yookassa_webhook(request:web.Request):
    db:Database=request.app["db"]; settings:Settings=request.app["settings"]
    try: payload=await request.json()
    except Exception: return web.json_response({"ok":False,"error":"invalid_json"},status=400)
    obj=payload.get("object") or {}; provider_payment_id=obj.get("id")
    if not provider_payment_id: return web.json_response({"ok":True})
    payment=await db.get_payment_by_provider_id(provider_payment_id)
    if not payment: return web.json_response({"ok":True})
    if not await db.record_payment_event(f"{provider_payment_id}:{payload.get('event','unknown')}", "yookassa", payment[0], payload.get("event","unknown"), payload): return web.json_response({"ok":True})
    client=YooKassaClient(settings.yookassa_shop_id,settings.yookassa_secret_key,settings.payment_return_url)
    try: verified=await client.get_payment(provider_payment_id)
    except PaymentError:
        log.exception("YooKassa verification failed")
        return web.json_response({"ok":False},status=500)
    if verified.get("status")=="succeeded" and verified.get("paid") is True:
        if await db.confirm_payment_and_credit(payment[0]):
            log.info("Payment confirmed and credits granted: %s",payment[0])
    elif verified.get("status") in {"canceled"}:
        await db.mark_payment_failed(payment[0],"canceled")
    return web.json_response({"ok":True})

async def health(request:web.Request): return web.json_response({"ok":True,"service":"ai-content-bot"})

async def run(settings:Settings):
    bot=Bot(settings.bot_token); db=None; runner=None
    try:
        db=await Database.connect(settings.database_path); credits=CreditsService(db,settings.free_credits); dp=build_dispatcher(db,credits,settings)
        try: await bot.set_my_commands([BotCommand(command="start",description="Начать"),BotCommand(command="menu",description="Главное меню"),BotCommand(command="legal",description="Документы")])
        except TelegramAPIError: log.warning("Не удалось установить команды бота")
        app=web.Application(); app["db"]=db; app["settings"]=settings
        app.router.add_get("/health",health); app.router.add_post(settings.webhook_path,yookassa_webhook)
        runner=web.AppRunner(app); await runner.setup(); await web.TCPSite(runner,settings.webhook_host,settings.webhook_port).start()
        log.info("Бот запущен, база: %s, HTTP :%s",settings.database_path,settings.webhook_port)
        await dp.start_polling(bot,allowed_updates=dp.resolve_used_update_types())
    finally:
        if runner is not None: await runner.cleanup()
        await bot.session.close()
        if db is not None: await db.close()

def main():
    setup_logging()
    try: settings=load_settings()
    except ConfigError as exc: log.error("Ошибка конфигурации: %s",exc); sys.exit(1)
    setup_logging(settings.bot_token)
    try: asyncio.run(run(settings))
    except TokenValidationError: log.error("BOT_TOKEN имеет неверный формат."); sys.exit(1)
    except TelegramAPIError as exc: log.error("Не удалось работать с Telegram API: %s",type(exc).__name__); sys.exit(1)
    except KeyboardInterrupt: log.info("Остановлено")
if __name__=="__main__": main()
