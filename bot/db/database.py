"""SQLite: пользователи, кредиты, платежи, AI-экономика и история."""
from __future__ import annotations
import json, os
from dataclasses import dataclass
from datetime import UTC, datetime
import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL UNIQUE,
 username TEXT, first_name TEXT, plan TEXT NOT NULL DEFAULT 'free',
 credits INTEGER NOT NULL DEFAULT 0 CHECK (credits >= 0),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS generations (
 id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL REFERENCES users(telegram_id),
 feature TEXT NOT NULL, prompt TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_generations_user ON generations (telegram_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_generations_status ON generations (status);

CREATE TABLE IF NOT EXISTS credit_transactions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL REFERENCES users(telegram_id),
 delta INTEGER NOT NULL, balance_after INTEGER NOT NULL, kind TEXT NOT NULL,
 reference_id TEXT, created_at TEXT NOT NULL, UNIQUE(kind, reference_id)
);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_user ON credit_transactions (telegram_id, id DESC);

CREATE TABLE IF NOT EXISTS payments (
 payment_id TEXT PRIMARY KEY, telegram_id INTEGER NOT NULL REFERENCES users(telegram_id),
 package_id TEXT NOT NULL, credits INTEGER NOT NULL CHECK (credits > 0),
 amount_rub TEXT NOT NULL, currency TEXT NOT NULL DEFAULT 'RUB',
 provider TEXT NOT NULL DEFAULT 'yookassa', provider_payment_id TEXT UNIQUE,
 status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_payments_user ON payments (telegram_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payments_provider_id ON payments (provider_payment_id);

CREATE TABLE IF NOT EXISTS payment_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, provider_event_id TEXT UNIQUE,
 provider TEXT NOT NULL, payment_id TEXT, event_type TEXT NOT NULL,
 payload TEXT NOT NULL, created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS refunds (
 id INTEGER PRIMARY KEY AUTOINCREMENT, payment_id TEXT NOT NULL, amount_rub TEXT NOT NULL,
 reason TEXT, status TEXT NOT NULL DEFAULT 'requested', created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_usage (
 id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER REFERENCES users(telegram_id),
 provider TEXT NOT NULL, model TEXT NOT NULL, operation TEXT NOT NULL,
 provider_cost_usd TEXT NOT NULL, credits_charged INTEGER NOT NULL DEFAULT 0,
 status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_usage_created ON ai_usage (created_at DESC);

CREATE TABLE IF NOT EXISTS legal_consents (
 id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL REFERENCES users(telegram_id),
 document TEXT NOT NULL, version TEXT NOT NULL, accepted_at TEXT NOT NULL,
 UNIQUE(telegram_id, document, version)
);
"""

@dataclass(frozen=True)
class User:
    id:int; telegram_id:int; username:str|None; first_name:str|None; plan:str; credits:int; created_at:str; updated_at:str
@dataclass(frozen=True)
class Generation:
    id:int; telegram_id:int; feature:str; prompt:str; status:str; created_at:str

def now_iso() -> str: return datetime.now(UTC).isoformat(timespec="seconds")
def validate_telegram_id(telegram_id:int)->int:
    if isinstance(telegram_id,bool) or not isinstance(telegram_id,int) or telegram_id<=0: raise ValueError("telegram_id должен быть положительным целым числом")
    return telegram_id

class Database:
    def __init__(self,conn:aiosqlite.Connection)->None:self._conn=conn
    @classmethod
    async def connect(cls,path:str)->"Database":
        if path!=":memory:": os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
        conn=await aiosqlite.connect(path)
        try:
            await conn.execute("PRAGMA foreign_keys=ON"); await conn.execute("PRAGMA journal_mode=WAL")
            await conn.executescript(SCHEMA); await conn.commit()
        except Exception: await conn.close(); raise
        return cls(conn)
    async def close(self)->None: await self._conn.close()

    async def register_user(self,telegram_id:int,username:str|None,first_name:str|None,free_credits:int)->tuple[User,bool]:
        validate_telegram_id(telegram_id); ts=now_iso()
        cur=await self._conn.execute("INSERT OR IGNORE INTO users (telegram_id,username,first_name,plan,credits,created_at,updated_at) VALUES (?,?,?,'free',?,?,?)",(telegram_id,username,first_name,free_credits,ts,ts))
        created=cur.rowcount==1
        if not created: await self._conn.execute("UPDATE users SET username=?,first_name=?,updated_at=? WHERE telegram_id=?",(username,first_name,ts,telegram_id))
        elif free_credits>0: await self._conn.execute("INSERT OR IGNORE INTO credit_transactions (telegram_id,delta,balance_after,kind,reference_id,created_at) VALUES (?,?,?,?,?,?)",(telegram_id,free_credits,free_credits,"welcome",f"welcome:{telegram_id}",ts))
        await self._conn.commit(); user=await self.get_user(telegram_id); assert user is not None; return user,created

    async def get_user(self,telegram_id:int)->User|None:
        validate_telegram_id(telegram_id)
        async with self._conn.execute("SELECT id,telegram_id,username,first_name,plan,credits,created_at,updated_at FROM users WHERE telegram_id=?",(telegram_id,)) as cur: row=await cur.fetchone()
        return User(*row) if row else None

    async def change_credits(self,telegram_id:int,delta:int,kind:str="adjustment",reference_id:str|None=None)->bool:
        validate_telegram_id(telegram_id)
        await self._conn.execute("BEGIN IMMEDIATE")
        try:
            if kind and reference_id is not None:
                async with self._conn.execute("SELECT 1 FROM credit_transactions WHERE kind=? AND reference_id=? LIMIT 1",(kind,reference_id)) as existing:
                    if await existing.fetchone():
                        await self._conn.rollback()
                        return True
            cur=await self._conn.execute("UPDATE users SET credits=credits+?,updated_at=? WHERE telegram_id=? AND credits+? >= 0",(delta,now_iso(),telegram_id,delta))
            if cur.rowcount!=1: await self._conn.rollback(); return False
            user=await self.get_user(telegram_id); assert user is not None
            await self._conn.execute("INSERT OR IGNORE INTO credit_transactions (telegram_id,delta,balance_after,kind,reference_id,created_at) VALUES (?,?,?,?,?,?)",(telegram_id,delta,user.credits,kind,reference_id,now_iso()))
            await self._conn.commit(); return True
        except Exception:
            await self._conn.rollback(); raise

    async def add_generation(self,telegram_id:int,feature:str,prompt:str,status:str)->int:
        validate_telegram_id(telegram_id)
        cur=await self._conn.execute("INSERT INTO generations (telegram_id,feature,prompt,status,created_at) VALUES (?,?,?,?,?)",(telegram_id,feature,prompt,status,now_iso()))
        await self._conn.commit(); return int(cur.lastrowid)

    async def list_generations(self,telegram_id:int,limit:int=10)->list[Generation]:
        validate_telegram_id(telegram_id)
        async with self._conn.execute("SELECT id,telegram_id,feature,prompt,status,created_at FROM generations WHERE telegram_id=? ORDER BY id DESC LIMIT ?",(telegram_id,max(1,min(limit,50)))) as cur: rows=await cur.fetchall()
        return [Generation(*r) for r in rows]

    async def create_payment(self,payment_id:str,telegram_id:int,package_id:str,credits:int,amount_rub,provider:str="yookassa")->None:
        await self._conn.execute("INSERT INTO payments (payment_id,telegram_id,package_id,credits,amount_rub,provider,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",(payment_id,telegram_id,package_id,credits,str(amount_rub),provider,now_iso(),now_iso())); await self._conn.commit()
    async def set_provider_payment_id(self,payment_id:str,provider_payment_id:str,status:str)->None:
        await self._conn.execute("UPDATE payments SET provider_payment_id=?,status=?,updated_at=? WHERE payment_id=?",(provider_payment_id,status,now_iso(),payment_id)); await self._conn.commit()
    async def mark_payment_failed(self,payment_id:str,status:str="failed")->None:
        await self._conn.execute("UPDATE payments SET status=?,updated_at=? WHERE payment_id=?",(status,now_iso(),payment_id)); await self._conn.commit()
    async def get_payment(self,payment_id:str):
        async with self._conn.execute("SELECT payment_id,telegram_id,package_id,credits,amount_rub,currency,provider,provider_payment_id,status,created_at,updated_at FROM payments WHERE payment_id=?",(payment_id,)) as cur:return await cur.fetchone()
    async def get_payment_by_provider_id(self,provider_payment_id:str):
        async with self._conn.execute("SELECT payment_id,telegram_id,package_id,credits,amount_rub,currency,provider,provider_payment_id,status,created_at,updated_at FROM payments WHERE provider_payment_id=?",(provider_payment_id,)) as cur:return await cur.fetchone()
    async def record_payment_event(self,event_id:str|None,provider:str,payment_id:str|None,event_type:str,payload:dict)->bool:
        cur=await self._conn.execute("INSERT OR IGNORE INTO payment_events (provider_event_id,provider,payment_id,event_type,payload,created_at) VALUES (?,?,?,?,?,?)",(event_id,provider,payment_id,event_type,json.dumps(payload,ensure_ascii=False),now_iso()))
        await self._conn.commit(); return cur.rowcount==1
    async def confirm_payment_and_credit(self,payment_id:str)->bool:
        await self._conn.execute("BEGIN IMMEDIATE")
        try:
            row=await self.get_payment(payment_id)
            if not row: await self._conn.rollback(); return False
            _,telegram_id,_,credits,_,_,_,_,status,_,_=row
            if status=="succeeded": await self._conn.rollback(); return False
            await self._conn.execute("UPDATE payments SET status='succeeded',updated_at=? WHERE payment_id=?",(now_iso(),payment_id))
            cur=await self._conn.execute("UPDATE users SET credits=credits+?,updated_at=? WHERE telegram_id=?",(credits,now_iso(),telegram_id))
            if cur.rowcount!=1: await self._conn.rollback(); return False
            user=await self.get_user(telegram_id); assert user is not None
            await self._conn.execute("INSERT OR IGNORE INTO credit_transactions (telegram_id,delta,balance_after,kind,reference_id,created_at) VALUES (?,?,?,?,?,?)",(telegram_id,credits,user.credits,"payment",payment_id,now_iso()))
            await self._conn.commit(); return True
        except Exception:
            await self._conn.rollback(); raise

    async def add_ai_usage(self,telegram_id:int,provider:str,model:str,operation:str,provider_cost_usd,credits_charged:int,status:str)->None:
        await self._conn.execute("INSERT INTO ai_usage (telegram_id,provider,model,operation,provider_cost_usd,credits_charged,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(telegram_id,provider,model,operation,str(provider_cost_usd),credits_charged,status,now_iso())); await self._conn.commit()

    async def accept_legal(self,telegram_id:int,document:str,version:str)->None:
        await self._conn.execute("INSERT OR IGNORE INTO legal_consents (telegram_id,document,version,accepted_at) VALUES (?,?,?,?)",(telegram_id,document,version,now_iso())); await self._conn.commit()
