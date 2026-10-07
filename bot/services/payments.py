"""YooKassa: создание платежа и подтверждение статуса. Секреты только в окружении."""
from __future__ import annotations
import base64
from decimal import Decimal
import aiohttp
from bot.db.database import Database
class PaymentError(RuntimeError): pass
class YooKassaClient:
    def __init__(self,shop_id,secret_key,return_url,timeout=30):
        self.shop_id=shop_id; self.secret_key=secret_key; self.return_url=return_url; self.timeout=aiohttp.ClientTimeout(total=timeout)
    def _auth(self):
        return "Basic "+base64.b64encode(f"{self.shop_id}:{self.secret_key}".encode()).decode()
    async def create_payment(self,payment_id,amount_rub:Decimal,description,metadata):
        payload={"amount":{"value":f"{amount_rub:.2f}","currency":"RUB"},"capture":True,"confirmation":{"type":"redirect","return_url":self.return_url},"description":description,"metadata":metadata}
        headers={"Authorization":self._auth(),"Content-Type":"application/json","Idempotence-Key":payment_id}
        async with aiohttp.ClientSession(timeout=self.timeout) as s:
            async with s.post("https://api.yookassa.ru/v3/payments",json=payload,headers=headers) as r:
                data=await r.json(content_type=None)
                if r.status>=400: raise PaymentError(f"YooKassa HTTP {r.status}")
                return data
    async def get_payment(self,provider_payment_id):
        async with aiohttp.ClientSession(timeout=self.timeout) as s:
            async with s.get(f"https://api.yookassa.ru/v3/payments/{provider_payment_id}",headers={"Authorization":self._auth()}) as r:
                data=await r.json(content_type=None)
                if r.status>=400: raise PaymentError(f"YooKassa HTTP {r.status}")
                return data
