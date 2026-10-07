"""Платежи: кредиты и подписки через YooKassa."""
from __future__ import annotations
from decimal import Decimal
import uuid
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.db.database import Database
from bot.keyboards.main import BTN_BUY, BTN_PLANS, main_menu
from bot.services.business_model import paid_plans
from bot.services.payments import YooKassaClient, PaymentError

router = Router(name="payments")
PACKAGES = (
    ("pack_100", "100 кредитов", 199, 100),
    ("pack_300", "300 кредитов", 499, 300),
    ("pack_1000", "1000 кредитов", 1290, 1000),
)

@router.message(F.text == BTN_BUY)
async def buy_menu(message: Message):
    lines=["💳 Пакеты кредитов (стартовые цены):",""]
    for i,(_,title,price,credits) in enumerate(PACKAGES,1): lines.append(f"{i}. {title} — {price} ₽")
    lines.append("\n/buy 1, /buy 2 или /buy 3")
    lines.append("/subscribe creator|starter|business — подписка")
    await message.answer("\n".join(lines),reply_markup=main_menu())

@router.message(F.text == BTN_PLANS)
async def subscription_menu(message: Message):
    lines=["⭐ Подписки",""]
    for plan in paid_plans(): lines.append(f"{plan.key}: {plan.title} — {plan.monthly_rub} ₽/30 дней · {plan.credits} кредитов")
    lines += ["","Для покупки: /subscribe creator","Автопродление пока хранится как настройка подписки; реальное рекуррентное списание подключается отдельным шагом после настройки сохранённого способа оплаты."]
    await message.answer("\n".join(lines),reply_markup=main_menu())

@router.message(Command("buy"))
async def buy(message: Message, db: Database, settings):
    if not await db.has_legal_consent(message.from_user.id,"offer","1.0"):
        await message.answer("Перед покупкой необходимо принять документы: /offer, /privacy, /rules, /refund, затем /accept.",reply_markup=main_menu()); return
    try: index=int((message.text or "").split(maxsplit=1)[1])-1; package_id,title,price,credits=PACKAGES[index]
    except (ValueError,IndexError): await message.answer("Используйте /buy 1, /buy 2 или /buy 3.",reply_markup=main_menu()); return
    await _create_payment(message,db,settings,package_id,title,price,credits,"credits",None)

@router.message(Command("subscribe"))
async def subscribe(message: Message, db: Database, settings):
    if not await db.has_legal_consent(message.from_user.id,"offer","1.0"):
        await message.answer("Перед покупкой необходимо принять документы: /offer, /privacy, /rules, /refund, затем /accept.",reply_markup=main_menu()); return
    parts=(message.text or "").split()
    key=parts[1].lower() if len(parts)>1 else "creator"
    plan=next((p for p in paid_plans() if p.key==key),None)
    if plan is None:
        await message.answer("Доступные тарифы: starter, creator, business. Пример: /subscribe creator",reply_markup=main_menu()); return
    await _create_payment(message,db,settings,f"sub_{plan.key}",plan.title,plan.monthly_rub or 0,plan.credits,"subscription",plan.key)

async def _create_payment(message:Message,db:Database,settings,package_id,title,price,credits,payment_type,plan_key):
    if not settings.yookassa_shop_id or not settings.yookassa_secret_key:
        await message.answer("Оплата ещё не подключена: в Amvera не заданы ключи YooKassa.",reply_markup=main_menu()); return
    payment_id=str(uuid.uuid4())
    await db.create_payment(payment_id,message.from_user.id,package_id,credits,Decimal(str(price)),payment_type=payment_type,plan_key=plan_key)
    client=YooKassaClient(settings.yookassa_shop_id,settings.yookassa_secret_key,settings.payment_return_url)
    try: data=await client.create_payment(payment_id,Decimal(str(price)),f"AI Content Bot: {title}",{"payment_id":payment_id,"telegram_id":str(message.from_user.id),"package_id":package_id,"payment_type":payment_type,"plan_key":plan_key or ""})
    except PaymentError:
        await db.mark_payment_failed(payment_id,"provider_error"); await message.answer("Не удалось создать платёж. Попробуйте позже.",reply_markup=main_menu()); return
    provider_id=data.get("id"); confirmation=(data.get("confirmation") or {}).get("confirmation_url")
    await db.set_provider_payment_id(payment_id,provider_id or "",data.get("status","pending"))
    if not confirmation: await message.answer("Платёж создан, но ссылка не получена. Обратитесь в поддержку.",reply_markup=main_menu()); return
    await message.answer(f"💳 {title} — {price} ₽\n\nОплата: {confirmation}\n\nПосле подтверждения YooKassa баланс/тариф обновится автоматически.",reply_markup=main_menu())
