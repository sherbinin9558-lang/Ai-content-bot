"""Реестр провайдеров. Пользователь выбирает модель; автоматического AI Router нет."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
@dataclass(frozen=True)
class ModelPricing:
    provider:str; model:str; operation:str; unit:str; provider_cost_usd:Decimal; credits:int; active:bool=True
class ProviderRegistry:
    def __init__(self): self._items={}
    def register(self,item:ModelPricing):
        if item.credits<=0 or item.provider_cost_usd<0: raise ValueError("Некорректная цена модели")
        self._items[(item.provider,item.model,item.operation)]=item
    def get(self,provider,model,operation): return self._items.get((provider,model,operation))
    def list_active(self,operation=None): return sorted([x for x in self._items.values() if x.active and (operation is None or x.operation==operation)],key=lambda x:(x.operation,x.provider,x.model))
def default_registry():
    from bot.services.provider_catalog import MODELS
    r=ProviderRegistry()
    for m in MODELS:r.register(ModelPricing(m.provider,m.model,m.operation,m.unit,m.provider_cost_usd,m.credits,m.enabled))
    return r
