"""Шесть функций и явный выбор пользователем провайдера/модели."""
from __future__ import annotations
from dataclasses import dataclass
import logging
from aiogram import F,Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State,StatesGroup
from aiogram.types import CallbackQuery,Message,BufferedInputFile
from bot.db.database import Database
from bot.keyboards.main import BUTTON_TO_FEATURE,FEATURE_BUTTONS,back_to_menu,main_menu,model_picker
from bot.services.ai_router import AIJob,AIService,Feature,JobStatus,OPERATION_BY_FEATURE
from bot.services.credits import InsufficientCredits
from bot.services.provider_catalog import get_model

log=logging.getLogger(__name__); router=Router(name="features"); MAX_ANSWER=1000; PHOTO_KEY="photo"
class FeatureForm(StatesGroup): answering=State()
@dataclass(frozen=True)
class Step:key:str;question:str
@dataclass(frozen=True)
class FormSpec:intro:str;steps:tuple[Step,...]
FORMS={
 Feature.PHOTO:FormSpec("Улучшение фото.",(Step(PHOTO_KEY,"Отправьте фотографию (как фото, не файлом)."),)),
 Feature.PRODUCT_CARD:FormSpec("Карточка товара.",(Step("Название товара","Как называется товар?"),Step("Описание","Опишите товар."),Step("Характеристики","Перечислите характеристики."),Step("Целевая аудитория","Кто ваш покупатель?"),Step("Пожелания","Дополнительные пожелания? Если нет — напишите «нет»."))),
 Feature.AD_CREATIVE:FormSpec("Рекламный креатив.",(Step("Продукт","Что рекламируем?"),Step("Аудитория","Для какой аудитории?"),Step("Площадка","Где будет реклама?"),Step("Стиль","В каком стиле?"),Step("Цель рекламы","Какая цель?"))),
 Feature.VIDEO:FormSpec("Создание видео.",(Step("Тема","О чём видео?"),Step("Формат","Вертикальное, горизонтальное или квадрат?"),Step("Длительность","Длительность в секундах?"),Step("Стиль","В каком стиле?"),Step("Площадка","Где публиковать?"))),
 Feature.SOCIAL:FormSpec("Контент для соцсетей.",(Step("Площадка","Для какой соцсети?"),Step("Тема","Какая тема?"),Step("Аудитория","Для какой аудитории?"),Step("Стиль","В каком стиле?"),Step("Количество вариантов","Сколько вариантов нужно?"))),
 Feature.ASSISTANT:FormSpec("AI-помощник.",(Step("Запрос","Напишите ваш запрос обычными словами."),)),
}
async def _ask(message,feature,index): await message.answer(FORMS[feature].steps[index].question,reply_markup=back_to_menu())
def build_prompt(feature,answers): return "\n".join([f"Задача: {FEATURE_BUTTONS[feature]}"]+[f"{k}: {v}" for k,v in answers.items() if k!=PHOTO_KEY])
@router.message(F.text.in_(BUTTON_TO_FEATURE))
async def start_form(message:Message,state:FSMContext):
    feature=BUTTON_TO_FEATURE[message.text]; operation=OPERATION_BY_FEATURE[feature]
    await state.set_state(FeatureForm.answering); await state.set_data({"feature":feature.value,"index":0,"answers":{}})
    await message.answer(f"{FORMS[feature].intro}\n\nСначала выберите AI-модель:",reply_markup=model_picker(operation))
@router.callback_query(F.data.startswith("model:"))
async def choose_model(call:CallbackQuery,state:FSMContext):
    value=call.data.split(":",2)
    if value[-1]=="cancel": await state.clear(); await call.message.edit_text("Выбор отменён."); await call.answer(); return
    _,provider,model=value
    item=get_model(provider,model)
    if item is None: await call.answer("Модель недоступна",show_alert=True); return
    data=await state.get_data()
    if not data.get("feature"): await call.answer("Сначала выберите функцию.",show_alert=True); return
    feature=Feature(data["feature"])
    await state.update_data(provider=provider,model=model)
    await call.message.edit_text(f"Выбрано: {item.title}\nСтоимость: {item.credits} кредитов за операцию.")
    await call.answer(); await _ask(call.message,feature,0)
@router.message(FeatureForm.answering,F.photo|F.text)
async def process_answer(message:Message,state:FSMContext,db:Database,ai_router:AIService):
    data=await state.get_data(); feature=Feature(data["feature"]); index=data["index"]; step=FORMS[feature].steps[index]; answers=dict(data["answers"])
    if not data.get("provider") or not data.get("model"): await message.answer("Сначала выберите AI-модель."); return
    if step.key==PHOTO_KEY:
        if not message.photo: await message.answer("Нужна именно фотография. Отправьте её как фото."); return
        answers[PHOTO_KEY]=message.photo[-1].file_id
    else:
        text=" ".join((message.text or "").split())
        if not text: await message.answer("Ответ не может быть пустым."); return
        if len(text)>MAX_ANSWER: await message.answer(f"Максимум {MAX_ANSWER} знаков."); return
        answers[step.key]=text
    index+=1
    if index<len(FORMS[feature].steps): await state.update_data(index=index,answers=answers); await _ask(message,feature,index); return
    await state.clear(); await _finish(message,db,ai_router,feature,answers,data["provider"],data["model"])
async def _finish(message,db,ai_service,feature,answers,provider,model):
    prompt=build_prompt(feature,answers); params={"file_id":answers[PHOTO_KEY]} if PHOTO_KEY in answers else {}
    try: result=await ai_service.submit(AIJob(feature,prompt,message.from_user.id,provider,model,params))
    except InsufficientCredits as exc: await message.answer(f"Недостаточно кредитов: {exc.balance}, нужно {exc.needed}.",reply_markup=main_menu()); return
    number=await db.add_generation(message.from_user.id,feature.value,prompt if feature!=Feature.PHOTO else "Задача: улучшить фото (фото приложено)",result.status.value)
    if result.status is JobStatus.COMPLETED:
        if result.media and (result.mime_type or "").startswith("image/"):
            await message.answer_photo(BufferedInputFile(result.media,filename=result.filename or "result.png"),caption=f"Готово. Списано: {result.cost} кредитов.",reply_markup=main_menu())
        elif result.media and (result.mime_type or "").startswith("video/"):
            await message.answer_video(BufferedInputFile(result.media,filename=result.filename or "result.mp4"),caption=f"Готово. Списано: {result.cost} кредитов.",reply_markup=main_menu())
        elif result.text:
            await message.answer(f"{result.text}\n\nСписано: {result.cost} кредитов.",reply_markup=main_menu())
        else:
            await message.answer("Генерация завершена, но провайдер не вернул результат.",reply_markup=main_menu())
    elif result.status is JobStatus.PENDING_PROVIDER: await message.answer(f"⏳ {number}: модель выбрана, но её API ещё не подключён. Кредиты не списаны.",reply_markup=main_menu())
    else: await message.answer(f"❌ Задача #{number} не выполнена. Кредиты возвращены.",reply_markup=main_menu())
