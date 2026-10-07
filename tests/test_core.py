import pytest
from decimal import Decimal
from bot.config import ConfigError,load_settings
from bot.db.database import Database
from bot.services.credits import CreditsService,InsufficientCredits
from bot.services.economics import calculate_cost,EconomicsConfig
from bot.services.provider_catalog import get_model,list_models

def test_load_settings_requires_token():
    with pytest.raises(ConfigError): load_settings({})
def test_load_settings_parses_defaults():
    s=load_settings({"BOT_TOKEN":"123:abc"})
    assert s.database_path=="/data/bot.db"; assert s.free_credits==10; assert s.yookassa_shop_id==""
@pytest.mark.asyncio
async def test_credits_are_atomic_and_never_negative(tmp_path):
    db=await Database.connect(str(tmp_path/"bot.db"))
    try:
        credits=CreditsService(db,3); user,created=await credits.register(1001,"test","Test")
        assert created is True and user.credits==3
        assert await credits.deduct(1001,2,"usage-1")==1
        with pytest.raises(InsufficientCredits): await credits.deduct(1001,2,"usage-2")
        assert await credits.get_balance(1001)==1
        assert await credits.add(1001,4,"payment","pay-1")==5
        assert await credits.add(1001,4,"payment","pay-1")==5
    finally: await db.close()
@pytest.mark.asyncio
async def test_payment_confirmation_is_idempotent(tmp_path):
    db=await Database.connect(str(tmp_path/"bot.db"))
    try:
        credits=CreditsService(db,0); await credits.register(2002)
        await db.create_payment("pay-1",2002,"pack_100",100,Decimal("199"))
        await db.set_provider_payment_id("pay-1","yk-1","pending")
        assert await db.confirm_payment_and_credit("pay-1") is True
        assert await db.confirm_payment_and_credit("pay-1") is False
        assert await credits.get_balance(2002)==100
    finally: await db.close()
def test_provider_catalog_exposes_named_models():
    assert get_model("google","nano-banana-2") is not None
    assert any(m.title=="Nano Banana Pro" for m in list_models("image"))
def test_economics_is_decimal_and_tracks_margin():
    result=calculate_cost(Decimal("0.067"),Decimal("199"),EconomicsConfig(usd_rub=Decimal("90")))
    assert result.provider_rub==Decimal("6.03")
    assert result.margin_rub>Decimal("0")
