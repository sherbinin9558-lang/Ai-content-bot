"""OpenAI-compatible текстовый провайдер. Пользователь выбирает модель до запуска."""
from __future__ import annotations
import logging
from typing import Any
import aiohttp
from bot.services.ai_router import AIJob,Feature
log=logging.getLogger(__name__)
TEXT_FEATURES={Feature.PRODUCT_CARD,Feature.AD_CREATIVE,Feature.SOCIAL,Feature.ASSISTANT}
class OpenAICompatibleTextProvider:
    provider_name="openai"
    def __init__(self,api_key:str,base_url:str,model:str,timeout_seconds:int=90):
        self._api_key=api_key; self.model_name=model; self._url=f"{base_url.rstrip('/')}/chat/completions"; self._timeout=aiohttp.ClientTimeout(total=timeout_seconds)
    def supports(self,operation:str)->bool:return operation=="text"
    async def run(self,job:AIJob)->str:
        if job.feature not in TEXT_FEATURES: raise RuntimeError("Эта модель не поддерживает выбранную функцию")
        payload:dict[str,Any]={"model":self.model_name,"messages":[{"role":"system","content":"Ты полезный AI-помощник для коммерческого контента. Отвечай по-русски, структурированно и без выдуманных характеристик."},{"role":"user","content":job.prompt}],"temperature":0.7}
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.post(self._url,json=payload,headers={"Authorization":f"Bearer {self._api_key}","Content-Type":"application/json"}) as response:
                if response.status>=400: log.error("AI provider returned HTTP %s",response.status); raise RuntimeError(f"AI provider HTTP {response.status}")
                data=await response.json(content_type=None)
        content=((data.get("choices") or [{}])[0].get("message") or {}).get("content")
        if not isinstance(content,str) or not content.strip(): raise RuntimeError("AI provider returned empty content")
        return content.strip()
