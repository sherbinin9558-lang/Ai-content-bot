import pytest

from bot.config import ConfigError, load_settings
from bot.db.database import Database
from bot.services.credits import CreditsService, InsufficientCredits


def test_load_settings_requires_token():
    with pytest.raises(ConfigError):
        load_settings({})


def test_load_settings_parses_defaults():
    settings = load_settings({"BOT_TOKEN": "123:abc"})
    assert settings.database_path == "/data/bot.db"
    assert settings.free_credits == 10
    assert settings.ai_api_key == ""


@pytest.mark.asyncio
async def test_credits_are_atomic_and_never_negative(tmp_path):
    db = await Database.connect(str(tmp_path / "bot.db"))
    try:
        credits = CreditsService(db, free_credits=3)
        user, created = await credits.register(1001, "test", "Test")
        assert created is True
        assert user.credits == 3

        assert await credits.deduct(1001, 2) == 1
        with pytest.raises(InsufficientCredits):
            await credits.deduct(1001, 2)
        assert await credits.get_balance(1001) == 1

        assert await credits.add(1001, 4) == 5
    finally:
        await db.close()
