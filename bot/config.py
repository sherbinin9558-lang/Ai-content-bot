"""Настройки из переменных окружения. Секреты не хранятся в Git."""
from __future__ import annotations
import logging, os
from collections.abc import Mapping
from dataclasses import dataclass
from dotenv import load_dotenv

class ConfigError(RuntimeError): pass

@dataclass(frozen=True)
class Settings:
    bot_token:str; database_path:str; free_credits:int
    ai_api_key:str; ai_api_base_url:str; ai_model:str
    yookassa_shop_id:str; yookassa_secret_key:str; payment_return_url:str
    webhook_host:str; webhook_port:int; webhook_path:str
    npd_rate:float; usd_rub:float

    def __repr__(self)->str:
        return f"Settings(database_path={self.database_path!r}, free_credits={self.free_credits}, ai_enabled={bool(self.ai_api_key)}, payments_enabled={bool(self.yookassa_shop_id and self.yookassa_secret_key)})"

def load_settings(env:Mapping[str,str]|None=None)->Settings:
    if env is None: load_dotenv(); env=os.environ
    token=env.get("BOT_TOKEN","").strip()
    if not token: raise ConfigError("Не задана переменная окружения BOT_TOKEN.")
    try: free=int(env.get("FREE_CREDITS","10") or "10")
    except ValueError as exc: raise ConfigError("FREE_CREDITS должна быть целым числом.") from exc
    if free<0: raise ConfigError("FREE_CREDITS не может быть отрицательной.")
    try: port=int(env.get("WEBHOOK_PORT","8080") or "8080")
    except ValueError as exc: raise ConfigError("WEBHOOK_PORT должна быть числом.") from exc
    return Settings(
        token, env.get("DATABASE_PATH","/data/bot.db").strip() or "/data/bot.db", free,
        env.get("AI_API_KEY","").strip(),
        (env.get("AI_API_BASE_URL","https://api.openai.com/v1").strip() or "https://api.openai.com/v1").rstrip("/"),
        env.get("AI_MODEL","gpt-4o-mini").strip() or "gpt-4o-mini",
        env.get("YOOKASSA_SHOP_ID","").strip(), env.get("YOOKASSA_SECRET_KEY","").strip(),
        env.get("PAYMENT_RETURN_URL","https://t.me/").strip() or "https://t.me/",
        env.get("WEBHOOK_HOST","0.0.0.0").strip() or "0.0.0.0", port,
        env.get("WEBHOOK_PATH","/webhooks/yookassa").strip() or "/webhooks/yookassa",
        float(env.get("NPD_RATE","0.04") or "0.04"), float(env.get("USD_RUB","90") or "90"),
    )

class RedactingFormatter(logging.Formatter):
    def __init__(self,secret:str,fmt:str): super().__init__(fmt); self._secret=secret
    def format(self,record:logging.LogRecord)->str:
        text=super().format(record); return text.replace(self._secret,"***") if self._secret else text
