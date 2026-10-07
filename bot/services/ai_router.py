"""Сервис выполнения выбранной пользователем модели.
Название файла сохранено для совместимости, но автоматического роутера здесь нет.
"""
from __future__ import annotations
import logging, uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol
from bot.services.credits import CreditsService, InsufficientCredits
from bot.services.provider_catalog import Model, get_model

log=logging.getLogger(__name__)

@dataclass(frozen=True)
class ProviderResult:
    text: str | None = None
    media: bytes | None = None
    mime_type: str | None = None
    filename: str | None = None

class Feature(StrEnum):
    PHOTO="photo"; PRODUCT_CARD="product_card"; AD_CREATIVE="ad_creative"; VIDEO="video"; SOCIAL="social"; ASSISTANT="assistant"
class JobStatus(StrEnum):
    PENDING_PROVIDER="pending_provider"; COMPLETED="completed"; FAILED="failed"
OPERATION_BY_FEATURE={Feature.PHOTO:"image",Feature.PRODUCT_CARD:"text",Feature.AD_CREATIVE:"text",Feature.VIDEO:"video",Feature.SOCIAL:"text",Feature.ASSISTANT:"text"}

@dataclass(frozen=True)
class AIJob:
    feature:Feature; prompt:str; user_id:int; provider:str; model:str; params:Mapping[str,Any]=field(default_factory=dict)

@dataclass(frozen=True)
class JobResult:
    status:JobStatus; text:str|None=None; cost:int=0; usage_id:str|None=None; media:bytes|None=None; mime_type:str|None=None; filename:str|None=None

class AIProvider(Protocol):
    provider_name:str
    model_name:str
    def supports(self,operation:str)->bool: ...
    async def run(self,job:AIJob)->ProviderResult | str: ...

class AIService:
    def __init__(self,credits:CreditsService,db=None)->None:
        self._credits=credits; self._db=db; self._providers:dict[tuple[str,str],AIProvider]={}
    def register(self,provider:AIProvider)->None:
        self._providers[(provider.provider_name,provider.model_name)]=provider
    async def submit(self,job:AIJob)->JobResult:
        operation=OPERATION_BY_FEATURE[job.feature]
        model=get_model(job.provider,job.model)
        if model is None or model.operation!=operation:
            raise ValueError("Выбранная модель не поддерживает эту функцию")
        usage_id=str(uuid.uuid4())
        provider=self._providers.get((model.provider,model.model))
        if provider is None or not provider.supports(operation):
            if not await self._credits.has_credits(job.user_id,model.credits):
                raise InsufficientCredits(await self._credits.get_balance(job.user_id),model.credits)
            if self._db: await self._db.add_ai_usage(job.user_id,model.provider,model.model,operation,model.provider_cost_usd,0,"pending_provider")
            return JobResult(JobStatus.PENDING_PROVIDER,cost=model.credits,usage_id=usage_id)
        await self._credits.deduct(job.user_id,model.credits,usage_id)
        try:
            result=await provider.run(job)
            if isinstance(result,str): result=ProviderResult(text=result)
        except Exception:
            log.exception("provider failed provider=%s model=%s",model.provider,model.model)
            await self._credits.add(job.user_id,model.credits,"refund",usage_id)
            if self._db: await self._db.add_ai_usage(job.user_id,model.provider,model.model,operation,model.provider_cost_usd,model.credits,"failed_refunded")
            return JobResult(JobStatus.FAILED,cost=model.credits,usage_id=usage_id)
        if self._db: await self._db.add_ai_usage(job.user_id,model.provider,model.model,operation,model.provider_cost_usd,model.credits,"completed")
        return JobResult(JobStatus.COMPLETED,text=result.text,cost=model.credits,usage_id=usage_id,media=result.media,mime_type=result.mime_type,filename=result.filename)

AIRouter=AIService
COSTS={f:1 for f in Feature}
