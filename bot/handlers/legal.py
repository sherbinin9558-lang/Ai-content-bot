"""Юридическая информация и согласия. Тексты — рабочие шаблоны, требуют проверки перед коммерческим запуском."""
from pathlib import Path
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.keyboards.main import BTN_LEGAL, main_menu

router = Router(name="legal")
ROOT = Path(__file__).resolve().parents[1] / "legal"

def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")

@router.message(Command("legal"))
@router.message(F.text == BTN_LEGAL)
async def legal_menu(message: Message):
    await message.answer(
        "⚖️ Юридическая информация\n\n"
        "/offer — публичная оферта\n"
        "/privacy — политика обработки данных\n"
        "/rules — правила сервиса\n"
        "/refund — возвраты\n\n"
        "Перед коммерческим запуском документы необходимо проверить под фактический статус продавца, реквизиты и схему оплаты.",
        reply_markup=main_menu(),
    )

@router.message(Command("offer"))
async def offer(message: Message):
    await message.answer(_read("offer.md"), reply_markup=main_menu())

@router.message(Command("privacy"))
async def privacy(message: Message):
    await message.answer(_read("privacy.md"), reply_markup=main_menu())

@router.message(Command("rules"))
async def rules(message: Message):
    await message.answer(_read("rules.md"), reply_markup=main_menu())

@router.message(Command("refund"))
async def refund(message: Message):
    await message.answer(_read("refunds.md"), reply_markup=main_menu())
