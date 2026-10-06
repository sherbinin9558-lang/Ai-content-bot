"""Настройки из переменных окружения. Секреты в коде и в Git не хранятся."""
from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """Некорректная или неполная конфигурация."""


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_path: str
    free_credits: int
    ai_api_key: str
    ai_api_base_url: str
    ai_model: str

    def __repr__(self) -> str:
        return (
            f"Settings(database_path={self.database_path!r}, "
            f"free_credits={self.free_credits}, "
            f"ai_enabled={bool(self.ai_api_key)})"
        )


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    if env is None:
        load_dotenv()
        env = os.environ
    token = env.get("BOT_TOKEN", "").strip()
    if not token:
        raise ConfigError("Не задана переменная окружения BOT_TOKEN.")
    raw_credits = env.get("FREE_CREDITS", "10").strip() or "10"
    try:
        free_credits = int(raw_credits)
    except ValueError as exc:
        raise ConfigError("FREE_CREDITS должна быть целым числом.") from exc
    if free_credits < 0:
        raise ConfigError("FREE_CREDITS не может быть отрицательной.")
    path = env.get("DATABASE_PATH", "").strip() or "/data/bot.db"
    ai_api_key = env.get("AI_API_KEY", "").strip()
    ai_api_base_url = (env.get("AI_API_BASE_URL", "").strip() or "https://api.openai.com/v1").rstrip("/")
    ai_model = env.get("AI_MODEL", "").strip() or "gpt-4o-mini"
    return Settings(token, path, free_credits, ai_api_key, ai_api_base_url, ai_model)


class RedactingFormatter(logging.Formatter):
    """Вырезает секрет из строк лога."""

    def __init__(self, secret: str, fmt: str) -> None:
        super().__init__(fmt)
        self._secret = secret

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        return text.replace(self._secret, "***") if self._secret else text
