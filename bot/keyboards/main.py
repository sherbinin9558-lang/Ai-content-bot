"""Основные клавиатуры и выбор конкретной AI-модели."""
from __future__ import annotations
from aiogram.types import InlineKeyboardButton,InlineKeyboardMarkup,KeyboardButton,ReplyKeyboardMarkup
from bot.services.ai_router import Feature
from bot.services.provider_catalog import list_models
BTN_MENU="🏠 Главное меню"; BTN_BALANCE="💳 Баланс"; BTN_HISTORY="📚 История"; BTN_PROFILE="👤 Профиль"; BTN_BUY="💳 Купить кредиты"; BTN_LEGAL="⚖️ Документы"
FEATURE_BUTTONS={Feature.PHOTO:"🖼 Улучшить фото",Feature.PRODUCT_CARD:"🛍 Карточка товара",Feature.AD_CREATIVE:"📢 Рекламный креатив",Feature.VIDEO:"🎬 Создать видео",Feature.SOCIAL:"📱 Контент для соцсетей",Feature.ASSISTANT:"✨ AI-помощник"}
BUTTON_TO_FEATURE={text:feature for feature,text in FEATURE_BUTTONS.items()}
def main_menu():
    texts=list(FEATURE_BUTTONS.values()); rows=[[KeyboardButton(text=a),KeyboardButton(text=b)] for a,b in zip(texts[::2],texts[1::2],strict=True)]
    rows += [[KeyboardButton(text=BTN_BALANCE),KeyboardButton(text=BTN_BUY)],[KeyboardButton(text=BTN_HISTORY),KeyboardButton(text=BTN_PROFILE)],[KeyboardButton(text=BTN_LEGAL)]]
    return ReplyKeyboardMarkup(keyboard=rows,resize_keyboard=True)
def back_to_menu(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_MENU)]],resize_keyboard=True)
def model_picker(operation:str)->InlineKeyboardMarkup:
    models=list_models(operation)
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{m.title} · {m.credits} кр.",callback_data=f"model:{m.provider}:{m.model}")] for m in models]+[[InlineKeyboardButton(text="Отмена",callback_data="model:cancel")]])
