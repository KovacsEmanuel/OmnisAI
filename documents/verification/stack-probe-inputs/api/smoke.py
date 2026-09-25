import json, sys, asyncio
from importlib.metadata import version
from fastapi import FastAPI
import httpx
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import psycopg, alembic
class Probe(BaseModel):
    scope_revision: int
app = FastAPI()
@app.post('/probe')
def probe(body: Probe):
    return body
async def check_api():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://probe.local') as c:
        good=await c.post('/probe',json={'scope_revision':1})
        bad=await c.post('/probe',json={'scope_revision':'bad'})
        assert good.json()=={'scope_revision':1}
        assert bad.status_code==422
asyncio.run(check_api())
engine=create_async_engine('postgresql+psycopg://unused:unused@127.0.0.1:1/unused')
assert engine.dialect.is_async
asyncio.run(engine.dispose())
key=AESGCM.generate_key(bit_length=256); aes=AESGCM(key); nonce=b'012345678901'; data=aes.encrypt(nonce,b'synthetic-secret',b'demo-context')
assert aes.decrypt(nonce,data,b'demo-context')==b'synthetic-secret'
assert 'Probe' in app.openapi()['components']['schemas']
print(json.dumps({'status':'PASS','python':sys.version.split()[0],'tests':['Pydantic valid/invalid DTO','FastAPI OpenAPI/HTTPX ASGITransport','SQLAlchemy async psycopg dialect construction, no DB connection','AESGCM roundtrip synthetic data'],'versions':{p:version(p) for p in ['fastapi','pydantic','SQLAlchemy','alembic','psycopg','httpx','cryptography','greenlet']}}))
