"""SQLite через aiosqlite: схема, пользователи, история генераций."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL UNIQUE, username TEXT, first_name TEXT, plan TEXT NOT NULL DEFAULT 'free', credits INTEGER NOT NULL DEFAULT 0 CHECK (credits >= 0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS generations (id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL REFERENCES users(telegram_id), feature TEXT NOT NULL, prompt TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_generations_user ON generations (telegram_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_generations_status ON generations (status);
"""

@dataclass(frozen=True)
class User:
    id: int; telegram_id: int; username: str | None; first_name: str | None; plan: str; credits: int; created_at: str; updated_at: str

@dataclass(frozen=True)
class Generation:
    id: int; telegram_id: int; feature: str; prompt: str; status: str; created_at: str

def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")

def validate_telegram_id(telegram_id: int) -> int:
    if isinstance(telegram_id, bool) or not isinstance(telegram_id, int) or telegram_id <= 0: raise ValueError("telegram_id должен быть положительным целым числом")
    return telegram_id

class Database:
    def __init__(self, conn: aiosqlite.Connection) -> None: self._conn = conn
    @classmethod
    async def connect(cls, path: str) -> "Database":
        if path != ":memory:": os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        conn = await aiosqlite.connect(path)
        try:
            await conn.execute("PRAGMA foreign_keys = ON"); await conn.execute("PRAGMA journal_mode = WAL"); await conn.executescript(SCHEMA); await conn.commit()
        except Exception: await conn.close(); raise
        return cls(conn)
    async def close(self) -> None: await self._conn.close()
    async def register_user(self, telegram_id: int, username: str | None, first_name: str | None, free_credits: int) -> tuple[User, bool]:
        validate_telegram_id(telegram_id); ts=now_iso()
        cur=await self._conn.execute("INSERT OR IGNORE INTO users (telegram_id, username, first_name, plan, credits, created_at, updated_at) VALUES (?, ?, ?, 'free', ?, ?, ?)",(telegram_id,username,first_name,free_credits,ts,ts)); created=cur.rowcount==1
        if not created: await self._conn.execute("UPDATE users SET username=?, first_name=?, updated_at=? WHERE telegram_id=?",(username,first_name,ts,telegram_id))
        await self._conn.commit(); user=await self.get_user(telegram_id); assert user is not None; return user,created
    async def get_user(self, telegram_id: int) -> User | None:
        validate_telegram_id(telegram_id)
        async with self._conn.execute("SELECT id, telegram_id, username, first_name, plan, credits, created_at, updated_at FROM users WHERE telegram_id=?",(telegram_id,)) as cur: row=await cur.fetchone()
        return User(*row) if row else None
    async def change_credits(self, telegram_id: int, delta: int) -> bool:
        validate_telegram_id(telegram_id)
        cur=await self._conn.execute("UPDATE users SET credits=credits+?, updated_at=? WHERE telegram_id=? AND credits+? >= 0",(delta,now_iso(),telegram_id,delta)); await self._conn.commit(); return cur.rowcount==1
    async def add_generation(self, telegram_id: int, feature: str, prompt: str, status: str) -> int:
        validate_telegram_id(telegram_id); cur=await self._conn.execute("INSERT INTO generations (telegram_id, feature, prompt, status, created_at) VALUES (?, ?, ?, ?, ?)",(telegram_id,feature,prompt,status,now_iso())); await self._conn.commit(); return int(cur.lastrowid)
    async def list_generations(self, telegram_id: int, limit: int=10) -> list[Generation]:
        validate_telegram_id(telegram_id)
        async with self._conn.execute("SELECT id, telegram_id, feature, prompt, status, created_at FROM generations WHERE telegram_id=? ORDER BY id DESC LIMIT ?",(telegram_id,max(1,min(limit,50)))) as cur: rows=await cur.fetchall()
        return [Generation(*r) for r in rows]
