"""Точка входа: python -m bot.main"""
from __future__ import annotations
import asyncio,logging,sys
from aiogram import Bot,Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand,ErrorEvent
from aiogram.utils.token import TokenValidationError
from bot.config import ConfigError,RedactingFormatter,Settings,load_settings
from bot.db.database import Database
from bot.handlers import account,features,start
from bot.services.ai_router import AIRouter
from bot.services.text_provider import OpenAICompatibleTextProvider
from bot.services.credits import CreditsService,UserNotFound
log=logging.getLogger("bot"); LOG_FORMAT="%(asctime)s %(levelname)s %(name)s: %(message)s"
def setup_logging(secret=""):
    handler=logging.StreamHandler(); handler.setFormatter(RedactingFormatter(secret,LOG_FORMAT)); logging.basicConfig(level=logging.INFO,handlers=[handler],force=True)
async def on_error(event:ErrorEvent)->bool:
    exc=event.exception; text="Сначала нажмите /start, чтобы зарегистрироваться." if isinstance(exc,UserNotFound) else "Произошла ошибка. Попробуйте ещё раз или вернитесь в меню: /menu."
    if not isinstance(exc,UserNotFound): log.error("Необработанная ошибка",exc_info=exc)
    message=event.update.message or (event.update.callback_query.message if event.update.callback_query else None)
    if message is not None:
        try: await message.answer(text)
        except TelegramAPIError: log.warning("Не удалось отправить сообщение об ошибке")
    return True
def build_dispatcher(db,credits,settings:Settings|None=None):
    dp=Dispatcher(storage=MemoryStorage()); dp.include_routers(start.router,account.router,features.router); dp.errors.register(on_error); ai_router=AIRouter(credits)
    if settings is not None and settings.ai_api_key:
        ai_router.register(OpenAICompatibleTextProvider(settings.ai_api_key,settings.ai_api_base_url,settings.ai_model)); log.info("Текстовый AI-провайдер включён")
    else: log.info("AI_API_KEY не задан: текстовые задачи ждут подключения провайдера")
    dp.workflow_data.update(db=db,credits=credits,ai_router=ai_router); return dp
async def run(settings):
    bot=Bot(settings.bot_token); db=None
    try:
        db=await Database.connect(settings.database_path); dp=build_dispatcher(db,CreditsService(db,settings.free_credits),settings)
        try: await bot.set_my_commands([BotCommand(command="start",description="Начать"),BotCommand(command="menu",description="Главное меню")])
        except TelegramAPIError: log.warning("Не удалось установить команды бота")
        log.info("Бот запущен, база: %s",settings.database_path); await dp.start_polling(bot,allowed_updates=dp.resolve_used_update_types())
    finally:
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
