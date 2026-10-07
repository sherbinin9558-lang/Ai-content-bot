"""Каталог моделей: пользователь выбирает конкретного провайдера/модель.
Цены здесь — конфигурационные значения для MVP и должны сверяться с тарифом API перед запуском продаж.
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
    Model("google", "nano-banana-2", "Nano Banana 2", "image", "image", Decimal("0.067"), 10),
    Model("google", "nano-banana-pro", "Nano Banana Pro", "image", "image", Decimal("0.150"), 25),
    Model("openai", "gpt-4o-mini", "GPT-4o mini", "text", "1K output tokens", Decimal("0.0006"), 1),
)

def list_models(operation: str | None = None) -> list[Model]:
    return [m for m in MODELS if m.enabled and (operation is None or m.operation == operation)]

def get_model(provider: str, model: str) -> Model | None:
    return next((m for m in MODELS if m.provider == provider and m.model == model and m.enabled), None)
