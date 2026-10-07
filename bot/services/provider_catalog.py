"""Каталог моделей и конфигурация экономики AI.
Цены — конфигурационные значения для MVP; перед коммерческим запуском сверяются с
официальными тарифами провайдеров. enabled=False означает «каталог есть, адаптер/API
ещё не подключён», поэтому модель не предлагается как доступная пользователю.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class Model:
    provider: str
    model: str
    title: str
    operation: str
    unit: str
    provider_cost_usd: Decimal
    credits: int
    enabled: bool = True

MODELS: tuple[Model, ...] = (
    Model("openai", "gpt-4o-mini", "GPT-4o mini", "text", "1K output tokens", Decimal("0.0006"), 1, True),
    Model("google", "gemini-3.8-flash", "Gemini 3.8 Flash", "text", "1K output tokens", Decimal("0.0045"), 2, False),
    Model("anthropic", "claude-opus-5.5", "Claude Opus 5.5", "text", "1K output tokens", Decimal("0.0300"), 5, False),
    Model("google", "nano-banana-2", "Nano Banana 2", "image", "image", Decimal("0.067"), 10, False),
    Model("google", "nano-banana-pro", "Nano Banana Pro", "image", "image", Decimal("0.150"), 25, False),
    Model("openai", "gpt-image", "GPT Image", "image", "image", Decimal("0.1000"), 18, False),
    Model("xai", "grok-imagine-image", "Grok Imagine Image", "image", "image", Decimal("0.0800"), 15, False),
    Model("bytedance", "seedream", "Seedream", "image", "image", Decimal("0.1000"), 18, False),
    Model("google", "veo-3.1", "Veo 3.1", "video", "second", Decimal("0.4000"), 35, False),
    Model("google", "veo-3.1-fast", "Veo 3.1 Fast", "video", "second", Decimal("0.1000"), 15, False),
    Model("runway", "gen-4.5", "Runway Gen-4.5", "video", "second", Decimal("0.3000"), 30, False),
    Model("kling", "kling-2.5-turbo", "Kling 2.5 Turbo", "video", "second", Decimal("0.2500"), 25, False),
    Model("bytedance", "seedance", "Seedance", "video", "second", Decimal("0.2000"), 25, False),
)

def list_models(operation: str | None = None) -> list[Model]:
    return [m for m in MODELS if m.enabled and (operation is None or m.operation == operation)]

def get_model(provider: str, model: str) -> Model | None:
    return next((m for m in MODELS if m.provider == provider and m.model == model and m.enabled), None)

def list_catalog(operation: str | None = None) -> list[Model]:
    """Полный каталог, включая ещё не подключённые модели, для админки."""
    return [m for m in MODELS if operation is None or m.operation == operation]
