"""Шесть функций: универсальный мастер вопросов."""
from __future__ import annotations
from dataclasses import dataclass
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from bot.db.database import Database
from bot.keyboards.main import BUTTON_TO_FEATURE,FEATURE_BUTTONS,back_to_menu,main_menu
from bot.services.ai_router import COSTS,AIJob,AIRouter,Feature,JobStatus
from bot.services.credits import InsufficientCredits
log=logging.getLogger(__name__); router=Router(name="features"); MAX_ANSWER=1000; PHOTO_KEY="photo"
class FeatureForm(StatesGroup): answering=State()
@dataclass(frozen=True)
class Step: key:str; question:str
@dataclass(frozen=True)
class FormSpec: intro:str; steps:tuple[Step,...]
FORMS={
Feature.PHOTO:FormSpec("Улучшение фото.",(Step(PHOTO_KEY,"Отправьте фотографию (как фото, не файлом)."),)),
Feature.PRODUCT_CARD:FormSpec("Карточка товара.",(Step("Название товара","Как называется товар?"),Step("Описание","Опишите товар."),Step("Характеристики","Перечислите характеристики (размер, материал, цвет…)."),Step("Целевая аудитория","Кто ваш покупатель?"),Step("Пожелания","Дополнительные пожелания? Если нет, напишите «нет»."))),
Feature.AD_CREATIVE:FormSpec("Рекламный креатив.",(Step("Продукт","Что рекламируем?"),Step("Аудитория","Для какой аудитории?"),Step("Площадка","Где будет реклама (Instagram, VK, Telegram, маркетплейс…)?"),Step("Стиль","В каком стиле?"),Step("Цель рекламы","Какая цель: продажи, охват, подписчики…?"))),
Feature.VIDEO:FormSpec("Создание видео.",(Step("Тема","О чём видео?"),Step("Формат","Формат: вертикальное, горизонтальное, квадрат?"),Step("Длительность","Длительность в секундах?"),Step("Стиль","В каком стиле?"),Step("Площадка","Где будет публиковаться (Reels, Shorts, VK Клипы…)?"))),
Feature.SOCIAL:FormSpec("Контент для соцсетей.",(Step("Площадка","Для какой соцсети?"),Step("Тема","Какая тема?"),Step("Аудитория","Для какой аудитории?"),Step("Стиль","В каком стиле?"),Step("Количество вариантов","Сколько публикаций/вариантов нужно?"))),
Feature.ASSISTANT:FormSpec("AI-помощник.",(Step("Запрос","Напишите ваш запрос обычными словами."),))}
OUTCOME_TEXT={JobStatus.PENDING_PROVIDER:"✅ Задача #{n} сохранена в истории.\nAI-провайдер для этой функции ещё не подключён, поэтому задача ждёт запуска. Кредиты не списаны.",JobStatus.FAILED:"❌ Не удалось выполнить задачу #{n}. Кредиты возвращены, попробуйте позже."}

def build_prompt(feature,answers):
    return "\n".join([f"Задача: {FEATURE_BUTTONS[feature]}"]+[f"{k}: {v}" for k,v in answers.items() if k!=PHOTO_KEY])
async def _ask(message,feature,index): await message.answer(FORMS[feature].steps[index].question,reply_markup=back_to_menu())
@router.message(F.text.in_(BUTTON_TO_FEATURE))
async def start_form(message:Message,state:FSMContext):
    feature=BUTTON_TO_FEATURE[message.text]; await state.set_state(FeatureForm.answering); await state.set_data({"feature":feature.value,"index":0,"answers":{}}); await message.answer(f"{FORMS[feature].intro} Стоимость: {COSTS[feature]} кр. Отвечайте по шагам.",reply_markup=back_to_menu()); await _ask(message,feature,0)
@router.message(FeatureForm.answering,F.photo|F.text)
async def process_answer(message:Message,state:FSMContext,db:Database,ai_router:AIRouter):
    data=await state.get_data(); feature=Feature(data["feature"]); index=data["index"]; step=FORMS[feature].steps[index]; answers=dict(data["answers"])
    if step.key==PHOTO_KEY:
        if not message.photo: await message.answer("Нужна именно фотография. Отправьте её как фото."); return
        answers[PHOTO_KEY]=message.photo[-1].file_id
    else:
        text=" ".join((message.text or "").split())
        if not text: await message.answer("Ответ не может быть пустым. Напишите текстом."); return
        if len(text)>MAX_ANSWER: await message.answer(f"Слишком длинно (максимум {MAX_ANSWER} знаков). Сократите, пожалуйста."); return
        answers[step.key]=text
    index+=1
    if index<len(FORMS[feature].steps): await state.update_data(index=index,answers=answers); await _ask(message,feature,index); return
    await state.clear(); await _finish(message,db,ai_router,feature,answers)
async def _finish(message,db,ai_router,feature,answers):
    user_id=message.from_user.id; prompt=build_prompt(feature,answers); params={"file_id":answers[PHOTO_KEY]} if PHOTO_KEY in answers else {}; history=prompt if feature!=Feature.PHOTO else "Задача: Улучшить фото (фото приложено)"
    try: result=await ai_router.submit(AIJob(feature,prompt,user_id,params))
    except InsufficientCredits as exc: await message.answer(f"Недостаточно кредитов: на балансе {exc.balance}, нужно {exc.needed}.",reply_markup=main_menu()); return
    number=await db.add_generation(user_id,feature.value,history,result.status.value)
    if result.status is JobStatus.COMPLETED and result.text: await message.answer(f"{result.text}\n\nСписано кредитов: {result.cost}.",reply_markup=main_menu())
    else: await message.answer(OUTCOME_TEXT[result.status].format(n=number),reply_markup=main_menu())
