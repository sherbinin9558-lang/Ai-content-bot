"""Покупка кредитов через YooKassa. СБП/карты выбираются на стороне YooKassa."""
from __future__ import annotations
from decimal import Decimal
import uuid
from aiogram import F, Router
from aiogram.types import Message
from bot.db.database import Database
from bot.keyboards.main import BTN_BUY, main_menu
from bot.services.payments import YooKassaClient, PaymentError

router = Router(name="payments")

PACKAGES = (
    ("pack_100", "100 кредитов", 199, 100),
    ("pack_300", "300 кредитов", 499, 300),
    ("pack_1000", "1000 кредитов", 1290, 1000),
)

@router.message(F.text == BTN_BUY)
async def buy_menu(message: Message):
    lines = ["💳 Пакеты кредитов (стартовые цены — можно изменить):", ""]
    for i, (_, title, price, credits) in enumerate(PACKAGES, 1):
        lines.append(f"{i}. {title} — {price} ₽")
    lines.append("\nДля покупки отправьте: /buy 1, /buy 2 или /buy 3")
    await message.answer("\n".join(lines), reply_markup=main_menu())

@router.message(F.text.startswith("/buy"))
async def buy(message: Message, db: Database, settings):
    try:
        index = int((message.text or "").split(maxsplit=1)[1]) - 1
        package_id, title, price, credits = PACKAGES[index]
    except (ValueError, IndexError):
        await message.answer("Используйте /buy 1, /buy 2 или /buy 3.", reply_markup=main_menu())
        return
    if not settings.yookassa_shop_id or not settings.yookassa_secret_key:
        await message.answer("Оплата ещё не подключена: в Amvera не заданы ключи YooKassa.", reply_markup=main_menu())
        return
    payment_id = str(uuid.uuid4())
    await db.create_payment(payment_id, message.from_user.id, package_id, credits, Decimal(str(price)))
    client = YooKassaClient(settings.yookassa_shop_id, settings.yookassa_secret_key, settings.payment_return_url)
    try:
        data = await client.create_payment(payment_id, Decimal(str(price)), f"AI Content Bot: {title}", {"payment_id": payment_id, "telegram_id": str(message.from_user.id), "package_id": package_id})
    except PaymentError:
        await db.mark_payment_failed(payment_id, "provider_error")
        await message.answer("Не удалось создать платёж. Попробуйте позже.", reply_markup=main_menu())
        return
    provider_id = data.get("id")
    confirmation = (data.get("confirmation") or {}).get("confirmation_url")
    await db.set_provider_payment_id(payment_id, provider_id or "", data.get("status", "pending"))
    if not confirmation:
        await message.answer("Платёж создан, но ссылка не получена. Обратитесь в поддержку.", reply_markup=main_menu())
        return
    await message.answer(f"💳 {title} — {price} ₽\n\nОплата: {confirmation}\n\nКредиты начисляются только после подтверждения успешного платежа.", reply_markup=main_menu())
