"""/start, /menu и возврат в главное меню."""
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from bot.keyboards.main import BTN_MENU, main_menu
from bot.services.credits import CreditsService
router=Router(name="start")
MENU_TEXT="Выберите, какой результат вам нужен 👇"
@router.message(CommandStart())
async def cmd_start(message:Message,state:FSMContext,credits:CreditsService):
    await state.clear(); user=message.from_user
    if user is None:return
    _,created=await credits.register(user.id,user.username,user.first_name)
    greeting=f"Добро пожаловать! Вам начислено {await credits.get_balance(user.id)} бесплатных кредитов." if created else "С возвращением!"
    await message.answer(f"{greeting}\n\n{MENU_TEXT}",reply_markup=main_menu())
@router.message(Command("menu"))
@router.message(F.text==BTN_MENU)
async def show_menu(message:Message,state:FSMContext):
    await state.clear(); await message.answer(MENU_TEXT,reply_markup=main_menu())
