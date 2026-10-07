"""Публичная витрина бизнес-модели: тарифы и готовые сценарии."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.keyboards.main import BTN_PLANS, BTN_TEMPLATES, main_menu
from bot.services.business_model import plans_text, templates_text

router = Router(name="business")


@router.message(Command("plans"))
@router.message(F.text == BTN_PLANS)
async def show_plans(message: Message):
    await message.answer(plans_text(), reply_markup=main_menu())


@router.message(Command("templates"))
@router.message(F.text == BTN_TEMPLATES)
async def show_templates(message: Message):
    await message.answer(templates_text(), reply_markup=main_menu())


from aiogram.filters import Command
from bot.services.content_library import trends_text, prompts_text

@router.message(Command("trends"))
async def show_trends(message: Message):
    await message.answer(trends_text(), reply_markup=main_menu())

@router.message(Command("prompts"))
async def show_prompts(message: Message):
    await message.answer(prompts_text(), reply_markup=main_menu())

