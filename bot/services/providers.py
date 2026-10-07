"""Каталог провайдеров и моделей. Модель выбирает пользователь, автоматического роутера нет."""
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
    r=ProviderRegistry()
    r.register(ModelPricing("openai","gpt-4o-mini","text","1K output tokens",Decimal("0.0006"),1))
    r.register(ModelPricing("google","nano-banana-2","image","image",Decimal("0.067"),10))
    r.register(ModelPricing("google","nano-banana-pro","image","image",Decimal("0.15"),25))
    return r
