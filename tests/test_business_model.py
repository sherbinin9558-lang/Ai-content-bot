from bot.services.business_model import PLANS, TEMPLATES, plans_text, templates_text


def test_business_model_has_free_and_paid_plans():
    assert PLANS[0].key == "free"
    assert PLANS[0].credits == 5
    assert any(p.monthly_rub is not None for p in PLANS[1:])


def test_business_model_has_reusable_templates():
    assert {t.key for t in TEMPLATES} >= {
        "product_card", "ad_creative", "social_pack", "video_script"
    }
    assert "подписка" in plans_text()
    assert "Готовые сценарии" in templates_text()
