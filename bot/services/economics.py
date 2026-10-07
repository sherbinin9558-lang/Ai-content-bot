"""Расчёт AI-себестоимости и маржи."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal,ROUND_HALF_UP
@dataclass(frozen=True)
class EconomicsConfig:
    usd_rub:Decimal=Decimal("90"); payment_fee_rate:Decimal=Decimal("0.03"); npd_rate:Decimal=Decimal("0.04"); safety_margin:Decimal=Decimal("0.15")
@dataclass(frozen=True)
class CostBreakdown:
    provider_usd:Decimal; provider_rub:Decimal; payment_fee_rub:Decimal; npd_rub:Decimal; reserve_rub:Decimal; revenue_rub:Decimal; margin_rub:Decimal
def calculate_cost(provider_usd,revenue_rub,cfg=EconomicsConfig()):
    provider_rub=(Decimal(provider_usd)*cfg.usd_rub).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
    fee=(revenue_rub*cfg.payment_fee_rate).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
    tax=(revenue_rub*cfg.npd_rate).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
    reserve=(provider_rub*cfg.safety_margin).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
    margin=(revenue_rub-provider_rub-fee-tax-reserve).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
    return CostBreakdown(Decimal(provider_usd),provider_rub,fee,tax,reserve,revenue_rub,margin)
