"""SQLite: пользователи, кредиты, платежи, AI-экономика, подписки, проекты и история."""
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
CREATE TABLE IF NOT EXISTS providers (
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
 currency TEXT NOT NULL DEFAULT 'USD', api_base TEXT, active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS models (
 id INTEGER PRIMARY KEY AUTOINCREMENT, provider_id INTEGER NOT NULL REFERENCES providers(id),
 name TEXT NOT NULL, title TEXT NOT NULL, operation TEXT NOT NULL, pricing_unit TEXT NOT NULL,
 provider_cost_usd TEXT NOT NULL, credits INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 0,
 UNIQUE(provider_id,name)
);
CREATE TABLE IF NOT EXISTS ai_operations (
 id TEXT PRIMARY KEY, telegram_id INTEGER NOT NULL REFERENCES users(telegram_id),
 model_id INTEGER, operation TEXT NOT NULL, input_units TEXT, output_units TEXT,
 provider_cost_usd TEXT NOT NULL, credits_charged INTEGER NOT NULL DEFAULT 0,
 status TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(model_id) REFERENCES models(id)
);
CREATE INDEX IF NOT EXISTS idx_ai_operations_user ON ai_operations (telegram_id, created_at DESC);
CREATE TABLE IF NOT EXISTS legal_consents (
 id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL REFERENCES users(telegram_id),
 document TEXT NOT NULL, version TEXT NOT NULL, accepted_at TEXT NOT NULL,
 UNIQUE(telegram_id, document, version)
);
CREATE TABLE IF NOT EXISTS subscriptions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL REFERENCES users(telegram_id),
 plan_key TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
 started_at TEXT NOT NULL, current_period_end TEXT NOT NULL,
 auto_renew INTEGER NOT NULL DEFAULT 0, provider_payment_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions (telegram_id, status, current_period_end);
CREATE TABLE IF NOT EXISTS projects (
 id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL REFERENCES users(telegram_id),
 name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_user ON projects (telegram_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS project_generations (
 project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 generation_id INTEGER NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
 PRIMARY KEY(project_id,generation_id)
);
CREATE TABLE IF NOT EXISTS favorites (
 telegram_id INTEGER NOT NULL REFERENCES users(telegram_id), generation_id INTEGER NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL, PRIMARY KEY(telegram_id,generation_id)
);
CREATE TABLE IF NOT EXISTS referral_codes (
 telegram_id INTEGER PRIMARY KEY REFERENCES users(telegram_id), code TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS referrals (
 id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER NOT NULL REFERENCES users(telegram_id),
 referred_id INTEGER NOT NULL UNIQUE REFERENCES users(telegram_id), status TEXT NOT NULL DEFAULT 'registered',
 rewarded INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id,created_at DESC);
"""

@dataclass(frozen=True)
class User:
    id:int; telegram_id:int; username:str|None; first_name:str|None; plan:str; credits:int; created_at:str; updated_at:str
@dataclass(frozen=True)
class Generation:
    id:int; telegram_id:int; feature:str; prompt:str; status:str; created_at:str
@dataclass(frozen=True)
class Project:
    id:int; telegram_id:int; name:str; description:str; created_at:str; updated_at:str
@dataclass(frozen=True)
class Subscription:
    id:int; telegram_id:int; plan_key:str; status:str; started_at:str; current_period_end:str; auto_renew:bool; provider_payment_id:str|None

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
            await conn.executescript(SCHEMA)
            await cls._migrate(conn)
            await conn.commit()
        except Exception: await conn.close(); raise
        return cls(conn)
    @staticmethod
    async def _migrate(conn):
        cols={row[1] async for row in (await conn.execute("PRAGMA table_info(payments)"))}
        if "payment_type" not in cols: await conn.execute("ALTER TABLE payments ADD COLUMN payment_type TEXT NOT NULL DEFAULT 'credits'")
        if "plan_key" not in cols: await conn.execute("ALTER TABLE payments ADD COLUMN plan_key TEXT")
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
        validate_telegram_id(telegram_id); await self._conn.execute("BEGIN IMMEDIATE")
        try:
            if kind and reference_id is not None:
                async with self._conn.execute("SELECT 1 FROM credit_transactions WHERE kind=? AND reference_id=? LIMIT 1",(kind,reference_id)) as cur:
                    if await cur.fetchone(): await self._conn.rollback(); return True
            cur=await self._conn.execute("UPDATE users SET credits=credits+?,updated_at=? WHERE telegram_id=? AND credits+? >= 0",(delta,now_iso(),telegram_id,delta))
            if cur.rowcount!=1: await self._conn.rollback(); return False
            user=await self.get_user(telegram_id); assert user is not None
            await self._conn.execute("INSERT OR IGNORE INTO credit_transactions (telegram_id,delta,balance_after,kind,reference_id,created_at) VALUES (?,?,?,?,?,?)",(telegram_id,delta,user.credits,kind,reference_id,now_iso()))
            await self._conn.commit(); return True
        except Exception: await self._conn.rollback(); raise

    async def add_generation(self,telegram_id:int,feature:str,prompt:str,status:str)->int:
        validate_telegram_id(telegram_id)
        cur=await self._conn.execute("INSERT INTO generations (telegram_id,feature,prompt,status,created_at) VALUES (?,?,?,?,?)",(telegram_id,feature,prompt,status,now_iso()))
        await self._conn.commit(); return int(cur.lastrowid)

    async def list_generations(self,telegram_id:int,limit:int=10)->list[Generation]:
        validate_telegram_id(telegram_id)
        async with self._conn.execute("SELECT id,telegram_id,feature,prompt,status,created_at FROM generations WHERE telegram_id=? ORDER BY id DESC LIMIT ?",(telegram_id,max(1,min(limit,50)))) as cur: rows=await cur.fetchall()
        return [Generation(*r) for r in rows]

    async def get_generation(self,telegram_id:int,generation_id:int)->Generation|None:
        async with self._conn.execute("SELECT id,telegram_id,feature,prompt,status,created_at FROM generations WHERE telegram_id=? AND id=?",(telegram_id,generation_id)) as cur:
            row=await cur.fetchone()
        return Generation(*row) if row else None

    async def toggle_favorite(self,telegram_id:int,generation_id:int)->bool:
        if not await self.get_generation(telegram_id,generation_id): return False
        async with self._conn.execute("SELECT 1 FROM favorites WHERE telegram_id=? AND generation_id=?",(telegram_id,generation_id)) as cur: exists=await cur.fetchone()
        if exists: await self._conn.execute("DELETE FROM favorites WHERE telegram_id=? AND generation_id=?",(telegram_id,generation_id)); result=False
        else: await self._conn.execute("INSERT INTO favorites VALUES (?,?,?)",(telegram_id,generation_id,now_iso())); result=True
        await self._conn.commit(); return result

    async def list_favorites(self,telegram_id:int,limit:int=20)->list[Generation]:
        async with self._conn.execute("SELECT g.id,g.telegram_id,g.feature,g.prompt,g.status,g.created_at FROM generations g JOIN favorites f ON f.generation_id=g.id WHERE f.telegram_id=? ORDER BY f.created_at DESC LIMIT ?",(telegram_id,max(1,min(limit,50)))) as cur: rows=await cur.fetchall()
        return [Generation(*r) for r in rows]

    async def create_payment(self,payment_id:str,telegram_id:int,package_id:str,credits:int,amount_rub,provider:str="yookassa",payment_type:str="credits",plan_key:str|None=None)->None:
        await self._conn.execute("INSERT INTO payments (payment_id,telegram_id,package_id,credits,amount_rub,provider,payment_type,plan_key,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(payment_id,telegram_id,package_id,credits,str(amount_rub),provider,payment_type,plan_key,now_iso(),now_iso())); await self._conn.commit()

    async def set_provider_payment_id(self,payment_id:str,provider_payment_id:str,status:str)->None:
        await self._conn.execute("UPDATE payments SET provider_payment_id=?,status=?,updated_at=? WHERE payment_id=?",(provider_payment_id,status,now_iso(),payment_id)); await self._conn.commit()
    async def mark_payment_failed(self,payment_id:str,status:str="failed")->None:
        await self._conn.execute("UPDATE payments SET status=?,updated_at=? WHERE payment_id=?",(status,now_iso(),payment_id)); await self._conn.commit()
    async def get_payment(self,payment_id:str):
        async with self._conn.execute("SELECT payment_id,telegram_id,package_id,credits,amount_rub,currency,provider,provider_payment_id,status,created_at,updated_at,payment_type,plan_key FROM payments WHERE payment_id=?",(payment_id,)) as cur:return await cur.fetchone()
    async def get_payment_by_provider_id(self,provider_payment_id:str):
        async with self._conn.execute("SELECT payment_id,telegram_id,package_id,credits,amount_rub,currency,provider,provider_payment_id,status,created_at,updated_at,payment_type,plan_key FROM payments WHERE provider_payment_id=?",(provider_payment_id,)) as cur:return await cur.fetchone()
    async def record_payment_event(self,event_id:str|None,provider:str,payment_id:str|None,event_type:str,payload:dict)->bool:
        cur=await self._conn.execute("INSERT OR IGNORE INTO payment_events (provider_event_id,provider,payment_id,event_type,payload,created_at) VALUES (?,?,?,?,?,?)",(event_id,provider,payment_id,event_type,json.dumps(payload,ensure_ascii=False),now_iso())); await self._conn.commit(); return cur.rowcount==1

    async def confirm_payment_and_credit(self,payment_id:str)->bool:
        await self._conn.execute("BEGIN IMMEDIATE")
        try:
            row=await self.get_payment(payment_id)
            if not row: await self._conn.rollback(); return False
            _,telegram_id,_,credits,_,_,_,_,status,_,_,payment_type,plan_key=row
            if status=="succeeded": await self._conn.rollback(); return False
            await self._conn.execute("UPDATE payments SET status='succeeded',updated_at=? WHERE payment_id=?",(now_iso(),payment_id))
            user=await self.get_user(telegram_id); assert user is not None
            if payment_type=="subscription" and plan_key:
                from bot.services.business_model import plan_by_key
                plan=plan_by_key(plan_key)
                if plan is None: await self._conn.rollback(); return False
                from datetime import timedelta
                now=datetime.now(UTC); end=now+timedelta(days=30)
                await self._conn.execute("UPDATE users SET plan=?,credits=credits+?,updated_at=? WHERE telegram_id=?",(plan.key,plan.credits,now_iso(),telegram_id))
                await self._conn.execute("INSERT INTO subscriptions (telegram_id,plan_key,status,started_at,current_period_end,auto_renew,provider_payment_id,created_at,updated_at) VALUES (?,?,?,?,?,0,?,?,?)",(telegram_id,plan.key,"active",now.isoformat(timespec="seconds"),end.isoformat(timespec="seconds"),row[7],now_iso(),now_iso()))
                delta=plan.credits
            else:
                cur=await self._conn.execute("UPDATE users SET credits=credits+?,updated_at=? WHERE telegram_id=?",(credits,now_iso(),telegram_id))
                if cur.rowcount!=1: await self._conn.rollback(); return False
                delta=credits
            user=await self.get_user(telegram_id); assert user is not None
            await self._conn.execute("INSERT OR IGNORE INTO credit_transactions (telegram_id,delta,balance_after,kind,reference_id,created_at) VALUES (?,?,?,?,?,?)",(telegram_id,delta,""+str(user.credits),"payment",payment_id,now_iso()))
            await self._conn.commit(); return True
        except Exception: await self._conn.rollback(); raise

    async def get_subscription(self,telegram_id:int)->Subscription|None:
        async with self._conn.execute("SELECT id,telegram_id,plan_key,status,started_at,current_period_end,auto_renew,provider_payment_id FROM subscriptions WHERE telegram_id=? ORDER BY id DESC LIMIT 1",(telegram_id,)) as cur: row=await cur.fetchone()
        return Subscription(*row) if row else None
    async def set_auto_renew(self,telegram_id:int,enabled:bool)->bool:
        cur=await self._conn.execute("UPDATE subscriptions SET auto_renew=?,updated_at=? WHERE telegram_id=? AND status='active'",(int(enabled),now_iso(),telegram_id)); await self._conn.commit(); return cur.rowcount>0

    async def create_project(self,telegram_id:int,name:str,description:str="")->int:
        cur=await self._conn.execute("INSERT INTO projects (telegram_id,name,description,created_at,updated_at) VALUES (?,?,?,?,?)",(telegram_id,name.strip(),description.strip(),now_iso(),now_iso())); await self._conn.commit(); return int(cur.lastrowid)
    async def list_projects(self,telegram_id:int,limit:int=20)->list[Project]:
        async with self._conn.execute("SELECT id,telegram_id,name,description,created_at,updated_at FROM projects WHERE telegram_id=? ORDER BY updated_at DESC LIMIT ?",(telegram_id,max(1,min(limit,50)))) as cur: rows=await cur.fetchall()
        return [Project(*r) for r in rows]
    async def attach_generation(self,telegram_id:int,project_id:int,generation_id:int)->bool:
        async with self._conn.execute("SELECT 1 FROM projects WHERE id=? AND telegram_id=?",(project_id,telegram_id)) as cur:
            if not await cur.fetchone(): return False
        if not await self.get_generation(telegram_id,generation_id): return False
        await self._conn.execute("INSERT OR IGNORE INTO project_generations VALUES (?,?)",(project_id,generation_id)); await self._conn.commit(); return True

    async def referral_code(self,telegram_id:int)->str:
        import secrets
        async with self._conn.execute("SELECT code FROM referral_codes WHERE telegram_id=?",(telegram_id,)) as cur: row=await cur.fetchone()
        if row: return row[0]
        code=secrets.token_urlsafe(6).replace("-","_")
        await self._conn.execute("INSERT INTO referral_codes VALUES (?,?,?)",(telegram_id,code,now_iso())); await self._conn.commit(); return code
    async def apply_referral(self,referred_id:int,code:str)->bool:
        async with self._conn.execute("SELECT telegram_id FROM referral_codes WHERE code=?",(code,)) as cur: row=await cur.fetchone()
        if not row or row[0]==referred_id: return False
        try:
            await self._conn.execute("INSERT INTO referrals (referrer_id,referred_id) VALUES (?,?)",(row[0],referred_id)); await self._conn.commit(); return True
        except aiosqlite.IntegrityError: await self._conn.rollback(); return False
    async def referral_stats(self,telegram_id:int)->tuple[int,int]:
        async with self._conn.execute("SELECT COUNT(*),COALESCE(SUM(rewarded),0) FROM referrals WHERE referrer_id=?",(telegram_id,)) as cur: row=await cur.fetchone()
        return int(row[0]),int(row[1])

    async def sync_provider_catalog(self)->None:
        from bot.services.provider_catalog import MODELS
        ts=now_iso()
        for item in MODELS:
            await self._conn.execute("INSERT INTO providers (name,currency,active,created_at) VALUES (?,'USD',1,?) ON CONFLICT(name) DO UPDATE SET active=1",(item.provider,ts))
            async with self._conn.execute("SELECT id FROM providers WHERE name=?",(item.provider,)) as cur: row=await cur.fetchone()
            assert row is not None
            await self._conn.execute("INSERT INTO models (provider_id,name,title,operation,pricing_unit,provider_cost_usd,credits,active) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(provider_id,name) DO UPDATE SET title=excluded.title,operation=excluded.operation,pricing_unit=excluded.pricing_unit,provider_cost_usd=excluded.provider_cost_usd,credits=excluded.credits,active=excluded.active",(row[0],item.model,item.title,item.operation,item.unit,str(item.provider_cost_usd),item.credits,int(item.enabled)))
        await self._conn.commit()

    async def add_ai_usage(self,telegram_id:int,provider:str,model:str,operation:str,provider_cost_usd,credits_charged:int,status:str)->None:
        created=now_iso()
        await self._conn.execute("INSERT INTO ai_usage (telegram_id,provider,model,operation,provider_cost_usd,credits_charged,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(telegram_id,provider,model,operation,str(provider_cost_usd),credits_charged,status,created))
        async with self._conn.execute("SELECT m.id FROM models m JOIN providers p ON p.id=m.provider_id WHERE p.name=? AND m.name=?",(provider,model)) as cur: row=await cur.fetchone()
        await self._conn.execute("INSERT INTO ai_operations (id,telegram_id,model_id,operation,provider_cost_usd,credits_charged,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(f"usage:{telegram_id}:{provider}:{model}:{created}",telegram_id,row[0] if row else None,operation,str(provider_cost_usd),credits_charged,status,created)); await self._conn.commit()

    async def has_legal_consent(self,telegram_id:int,document:str,version:str)->bool:
        async with self._conn.execute("SELECT 1 FROM legal_consents WHERE telegram_id=? AND document=? AND version=? LIMIT 1",(telegram_id,document,version)) as cur:return await cur.fetchone() is not None
    async def accept_legal(self,telegram_id:int,document:str,version:str)->None:
        await self._conn.execute("INSERT OR IGNORE INTO legal_consents (telegram_id,document,version,accepted_at) VALUES (?,?,?,?)",(telegram_id,document,version,now_iso())); await self._conn.commit()
