import pytest
from bot.db.database import Database
from bot.services.business_model import plan_by_key

@pytest.mark.asyncio
async def test_subscription_activation_and_idempotency():
    db=await Database.connect(":memory:")
    try:
        await db.register_user(123,"u","User",5)
        await db.create_payment("p1",123,"sub_creator",800,990,payment_type="subscription",plan_key="creator")
        assert await db.confirm_payment_and_credit("p1")
        assert not await db.confirm_payment_and_credit("p1")
        user=await db.get_user(123)
        assert user is not None and user.plan=="creator" and user.credits==805
        sub=await db.get_subscription(123)
        assert sub is not None and sub.plan_key=="creator" and sub.status=="active"
    finally:
        await db.close()

@pytest.mark.asyncio
async def test_history_favorites_projects_and_referral():
    db=await Database.connect(":memory:")
    try:
        await db.register_user(1,"one","One",5)
        await db.register_user(2,"two","Two",5)
        gid=await db.add_generation(1,"social","test prompt","completed")
        assert await db.toggle_favorite(1,gid)
        assert len(await db.list_favorites(1))==1
        pid=await db.create_project(1,"Shop")
        assert await db.attach_generation(1,pid,gid)
        code=await db.referral_code(1)
        assert await db.apply_referral(2,code)
        assert await db.referral_stats(1)==(1,0)
    finally:
        await db.close()

def test_plan_lookup():
    plan=plan_by_key("creator")
    assert plan is not None and plan.monthly_rub==990
