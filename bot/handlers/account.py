"""Баланс, история, профиль."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from bot.db.database import Database
from bot.keyboards.main import BTN_BALANCE,BTN_HISTORY,BTN_PROFILE,FEATURE_BUTTONS,main_menu
from bot.services.ai_router import Feature
from bot.services.credits import CreditsService,UserNotFound
router=Router(name="account")
STATUS_TITLES={"pending_provider":"⏳ ждёт подключения AI","completed":"✅ готово","failed":"❌ ошибка"}
def _short(text,limit=70):
    one_line=" ".join(text.split()); return one_line if len(one_line)<=limit else one_line[:limit-1]+"…"
def _feature_title(value):
    try:return FEATURE_BUTTONS[Feature(value)]
    except ValueError:return value
@router.message(F.text==BTN_BALANCE)
async def show_balance(message:Message,state:FSMContext,credits:CreditsService):
    await state.clear(); await message.answer(f"💳 Ваш баланс: {await credits.get_balance(message.from_user.id)} кредитов.",reply_markup=main_menu())
@router.message(F.text==BTN_HISTORY)
async def show_history(message:Message,state:FSMContext,db:Database):
    await state.clear(); items=await db.list_generations(message.from_user.id,10)
    if not items: await message.answer("История пока пуста. Выберите функцию в меню.",reply_markup=main_menu()); return
    lines=[f"{_feature_title(g.feature)} · {STATUS_TITLES.get(g.status,g.status)}\n«{_short(g.prompt)}»\n{g.created_at[:16].replace('T',' ')} UTC" for g in items]
    await message.answer("📚 Последние генерации:\n\n"+"\n\n".join(lines),reply_markup=main_menu())
@router.message(F.text==BTN_PROFILE)
async def show_profile(message:Message,state:FSMContext,db:Database):
    await state.clear(); user=await db.get_user(message.from_user.id)
    if user is None: raise UserNotFound(message.from_user.id)
    await message.answer(f"👤 Профиль\nИмя: {user.first_name or '—'}\nUsername: {('@'+user.username) if user.username else '—'}\nID: {user.telegram_id}\nТариф: {user.plan}\nКредиты: {user.credits}\nРегистрация: {user.created_at[:10]}",reply_markup=main_menu())
