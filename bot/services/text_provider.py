"""Опциональный OpenAI-compatible текстовый провайдер."""
from __future__ import annotations
import logging
from typing import Any
import aiohttp
from bot.services.ai_router import AIJob,Feature
log=logging.getLogger(__name__)
TEXT_FEATURES={Feature.PRODUCT_CARD,Feature.AD_CREATIVE,Feature.SOCIAL,Feature.ASSISTANT}
class OpenAICompatibleTextProvider:
    def __init__(self,api_key:str,base_url:str,model:str,timeout_seconds:int=90): self._api_key=api_key; self._url=f"{base_url.rstrip('/')}/chat/completions"; self._model=model; self._timeout=aiohttp.ClientTimeout(total=timeout_seconds)
    def supports(self,feature): return feature in TEXT_FEATURES
    async def run(self,job:AIJob)->str:
        payload:dict[str,Any]={"model":self._model,"messages":[{"role":"system","content":"Ты полезный AI-помощник для создания коммерческого контента. Отвечай на русском языке, структурированно и без лишней воды. Сохраняй факты пользователя и не выдумывай характеристики товара."},{"role":"user","content":job.prompt}],"temperature":0.7}
        headers={"Authorization":f"Bearer {self._api_key}","Content-Type":"application/json"}
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.post(self._url,json=payload,headers=headers) as response:
                if response.status>=400: log.error("AI provider returned HTTP %s",response.status); raise RuntimeError(f"AI provider HTTP {response.status}")
                try:data=await response.json()
                except Exception as exc: raise RuntimeError("AI provider returned invalid JSON") from exc
        choices=data.get("choices")
        if not choices: raise RuntimeError("AI provider returned no choices")
        content=choices[0].get("message",{}).get("content")
        if not isinstance(content,str) or not content.strip(): raise RuntimeError("AI provider returned empty content")
        return content.strip()
