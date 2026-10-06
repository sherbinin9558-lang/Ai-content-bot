"""AI Router: пользователь выбирает результат, роутер выбирает провайдера."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from bot.services.credits import CreditsService, InsufficientCredits

log = logging.getLogger(__name__)


class Feature(StrEnum):
    PHOTO = "photo"
    PRODUCT_CARD = "product_card"
    AD_CREATIVE = "ad_creative"
    VIDEO = "video"
    SOCIAL = "social"
    ASSISTANT = "assistant"


class JobStatus(StrEnum):
    PENDING_PROVIDER = "pending_provider"
    COMPLETED = "completed"
    FAILED = "failed"


COSTS: dict[Feature, int] = {f: 1 for f in Feature} | {Feature.VIDEO: 3}


@dataclass(frozen=True)
class AIJob:
    feature: Feature
    prompt: str
    user_id: int
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JobResult:
    status: JobStatus
    text: str | None = None
    cost: int = 0


class AIProvider(Protocol):
    def supports(self, feature: Feature) -> bool: ...
    async def run(self, job: AIJob) -> str: ...


class AIRouter:
    def __init__(self, credits: CreditsService) -> None:
        self._credits = credits
        self._providers: list[AIProvider] = []

    def register(self, provider: AIProvider) -> None:
        self._providers.append(provider)

    def provider_for(self, feature: Feature) -> AIProvider | None:
        return next((p for p in self._providers if p.supports(feature)), None)

    async def submit(self, job: AIJob) -> JobResult:
        cost = COSTS[job.feature]
        provider = self.provider_for(job.feature)
        if provider is None:
            if not await self._credits.has_credits(job.user_id, cost):
                raise InsufficientCredits(await self._credits.get_balance(job.user_id), cost)
            return JobResult(JobStatus.PENDING_PROVIDER)
        await self._credits.deduct(job.user_id, cost)
        try:
            result = await provider.run(job)
        except Exception:
            log.exception("provider failed for feature=%s", job.feature)
            await self._credits.add(job.user_id, cost)
            return JobResult(JobStatus.FAILED)
        return JobResult(JobStatus.COMPLETED, text=result, cost=cost)
