"""YooKassa client. СБП и карты выбираются на стороне YooKassa."""
from __future__ import annotations
import base64
from decimal import Decimal
import aiohttp
class PaymentError(RuntimeError): pass
class YooKassaClient:
    BASE_URL="https://api.yookassa.ru/v3"
    def __init__(self,shop_id:str,secret_key:str,return_url:str,timeout:int=30):
        self.shop_id=shop_id; self.secret_key=secret_key; self.return_url=return_url; self.timeout=aiohttp.ClientTimeout(total=timeout)
    def _auth(self)->str: return "Basic "+base64.b64encode(f"{self.shop_id}:{self.secret_key}".encode()).decode()
    async def create_payment(self,payment_id:str,amount_rub:Decimal,description:str,metadata:dict,payment_method_type:str|None=None):
        payload={"amount":{"value":f"{amount_rub:.2f}","currency":"RUB"},"capture":True,"confirmation":{"type":"redirect","return_url":self.return_url},"description":description,"metadata":metadata}
        if payment_method_type:
            payload["payment_method_data"]={"type":payment_method_type}
        headers={"Authorization":self._auth(),"Content-Type":"application/json","Idempotence-Key":payment_id}
        async with aiohttp.ClientSession(timeout=self.timeout) as s:
            async with s.post(f"{self.BASE_URL}/payments",json=payload,headers=headers) as r:
                data=await r.json(content_type=None)
                if r.status>=400: raise PaymentError(f"YooKassa HTTP {r.status}")
                return data
    async def get_payment(self,provider_payment_id:str):
        async with aiohttp.ClientSession(timeout=self.timeout) as s:
            async with s.get(f"{self.BASE_URL}/payments/{provider_payment_id}",headers={"Authorization":self._auth()}) as r:
                data=await r.json(content_type=None)
                if r.status>=400: raise PaymentError(f"YooKassa HTTP {r.status}")
                return data
