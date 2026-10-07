"""Баланс, профиль, история, избранное, проекты и реферальная программа."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from bot.db.database import Database
from bot.keyboards.main import BTN_BALANCE,BTN_HISTORY,BTN_PROFILE,FEATURE_BUTTONS,main_menu
from bot.services.ai_router import Feature
from bot.services.business_model import plan_by_key
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
@router.message(Command("history"))
async def show_history(message:Message,state:FSMContext,db:Database):
    await state.clear(); items=await db.list_generations(message.from_user.id,15)
    if not items: await message.answer("История пока пуста. Выберите функцию в меню.",reply_markup=main_menu()); return
    lines=["📚 История генераций",""]
    for g in items: lines.append(f"#{g.id} {_feature_title(g.feature)} · {STATUS_TITLES.get(g.status,g.status)}\n«{_short(g.prompt)}»\n/generation {g.id}")
    lines.append("\nЧтобы повторить задачу: /repeat ID. Избранное: /favorite ID")
    await message.answer("\n\n".join(lines),reply_markup=main_menu())

@router.message(Command("generation"))
async def generation(message:Message,db:Database):
    try: gid=int((message.text or "").split()[1])
    except (ValueError,IndexError): await message.answer("Пример: /generation 12"); return
    item=await db.get_generation(message.from_user.id,gid)
    if not item: await message.answer("Генерация не найдена."); return
    await message.answer(f"🧾 Генерация #{item.id}\nФункция: {_feature_title(item.feature)}\nСтатус: {STATUS_TITLES.get(item.status,item.status)}\n\n{item.prompt}\n\nДля повторения: /repeat {item.id}")

@router.message(Command("favorite"))
async def favorite(message:Message,db:Database):
    try: gid=int((message.text or "").split()[1])
    except (ValueError,IndexError): await message.answer("Пример: /favorite 12"); return
    added=await db.toggle_favorite(message.from_user.id,gid)
    await message.answer("⭐ Добавлено в избранное." if added else "⭐ Убрано из избранного.",reply_markup=main_menu())

@router.message(Command("favorites"))
async def favorites(message:Message,db:Database):
    items=await db.list_favorites(message.from_user.id)
    if not items: await message.answer("Избранное пока пусто.",reply_markup=main_menu()); return
    await message.answer("⭐ Избранное:\n\n" + "\n\n".join(f"#{g.id} {_feature_title(g.feature)}\n{_short(g.prompt)}" for g in items),reply_markup=main_menu())

@router.message(Command("project"))
async def project(message:Message,db:Database):
    parts=(message.text or "").split(maxsplit=2)
    if len(parts)<2:
        items=await db.list_projects(message.from_user.id)
        if not items: await message.answer("Проектов пока нет. Создайте: /project create Название"); return
        await message.answer("📁 Проекты:\n\n"+"\n".join(f"#{p.id} {p.name}" for p in items),reply_markup=main_menu()); return
    if parts[1].lower()=="create" and len(parts)>=3:
        pid=await db.create_project(message.from_user.id,parts[2]); await message.answer(f"📁 Проект создан: #{pid} {parts[2]}",reply_markup=main_menu()); return
    if parts[1].lower()=="list":
        items=await db.list_projects(message.from_user.id); await message.answer("📁 Проекты:\n\n"+("\n".join(f"#{p.id} {p.name}" for p in items) or "Пока пусто."),reply_markup=main_menu()); return
    await message.answer("Команды: /project create Название или /project list")

@router.message(Command("ref"))
async def referral(message:Message,db:Database):
    code=await db.referral_code(message.from_user.id); count,rewarded=await db.referral_stats(message.from_user.id)
    await message.answer(f"🤝 Партнёрская программа\n\nВаш код: {code}\nПриглашено: {count}\nАктивировано: {rewarded}\n\nДля MVP код можно передать другу; автоматическая выдача бонусов подключается отдельным этапом после фиксации антифрода и условий программы.",reply_markup=main_menu())


@router.message(F.text==BTN_PROFILE)
@router.message(Command("profile"))
async def show_profile(message:Message,state:FSMContext,db:Database):
    await state.clear(); user=await db.get_user(message.from_user.id)
    if user is None: raise UserNotFound(message.from_user.id)
    plan=plan_by_key(user.plan); sub=await db.get_subscription(user.telegram_id)
    sub_text=f"до {sub.current_period_end[:10]}" if sub and sub.status=="active" else "нет активной подписки"
    await message.answer(f"👤 Профиль\nИмя: {user.first_name or '—'}\nUsername: {('@'+user.username) if user.username else '—'}\nТариф: {plan.title if plan else user.plan}\nКредиты: {user.credits}\nПодписка: {sub_text}\nРегистрация: {user.created_at[:10]}\n\nИстория: /history\nИзбранное: /favorites\nПроекты: /project\nПартнёрство: /ref",reply_markup=main_menu())
