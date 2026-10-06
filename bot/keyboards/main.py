"""Клавиатуры и тексты кнопок."""
from __future__ import annotations
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from bot.services.ai_router import Feature
BTN_MENU="🏠 Главное меню"; BTN_BALANCE="💳 Баланс"; BTN_HISTORY="📚 История"; BTN_PROFILE="👤 Профиль"
FEATURE_BUTTONS={Feature.PHOTO:"🖼 Улучшить фото",Feature.PRODUCT_CARD:"🛍 Карточка товара",Feature.AD_CREATIVE:"📢 Рекламный креатив",Feature.VIDEO:"🎬 Создать видео",Feature.SOCIAL:"📱 Контент для соцсетей",Feature.ASSISTANT:"✨ AI-помощник"}
BUTTON_TO_FEATURE={text:feature for feature,text in FEATURE_BUTTONS.items()}
def main_menu():
    texts=list(FEATURE_BUTTONS.values()); rows=[[KeyboardButton(text=a),KeyboardButton(text=b)] for a,b in zip(texts[::2],texts[1::2],strict=True)]; rows.append([KeyboardButton(text=t) for t in (BTN_BALANCE,BTN_HISTORY,BTN_PROFILE)]); return ReplyKeyboardMarkup(keyboard=rows,resize_keyboard=True)
def back_to_menu(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_MENU)]],resize_keyboard=True)
