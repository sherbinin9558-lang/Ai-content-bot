"""Кредиты: баланс, проверка, атомарное списание и пополнение."""
from __future__ import annotations

from bot.db.database import Database, User


class CreditsError(Exception):
    pass


class UserNotFound(CreditsError):
    def __init__(self, telegram_id: int) -> None:
        super().__init__(f"user {telegram_id} not registered")
        self.telegram_id = telegram_id


class InsufficientCredits(CreditsError):
    def __init__(self, balance: int, needed: int) -> None:
        super().__init__(f"balance {balance}, needed {needed}")
        self.balance = balance
        self.needed = needed


def _positive(amount: int) -> int:
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise ValueError("amount должен быть положительным целым числом")
    return amount


class CreditsService:
    def __init__(self, db: Database, free_credits: int) -> None:
        self._db = db
        self._free_credits = free_credits

    async def register(self, telegram_id: int, username: str | None = None, first_name: str | None = None) -> tuple[User, bool]:
        return await self._db.register_user(telegram_id, username, first_name, self._free_credits)

    async def get_balance(self, telegram_id: int) -> int:
        user = await self._db.get_user(telegram_id)
        if user is None:
            raise UserNotFound(telegram_id)
        return user.credits

    async def has_credits(self, telegram_id: int, amount: int = 1) -> bool:
        return await self.get_balance(telegram_id) >= _positive(amount)

    async def deduct(self, telegram_id: int, amount: int = 1) -> int:
        _positive(amount)
        if await self._db.change_credits(telegram_id, -amount):
            return await self.get_balance(telegram_id)
        raise InsufficientCredits(await self.get_balance(telegram_id), amount)

    async def add(self, telegram_id: int, amount: int) -> int:
        _positive(amount)
        if not await self._db.change_credits(telegram_id, amount):
            raise UserNotFound(telegram_id)
        return await self.get_balance(telegram_id)
