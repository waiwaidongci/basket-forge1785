import os,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
# Settings are read at import time; point them at a throwaway SQLite file before
# importing any application module. Redis is stubbed per-test, never contacted.
os.environ.setdefault('JWT_SECRET','test-secret-not-for-deployment')
os.environ.setdefault('DATABASE_URL','sqlite:///'+tempfile.mkstemp(suffix='.db')[1])
os.environ.setdefault('REDIS_URL','redis://localhost:6379/15')
os.environ.setdefault('SEED_DEMO','false')
os.environ.setdefault('ARTIFACT_DIR',tempfile.mkdtemp(prefix='artifacts-'))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from src.config.database import Base,SessionLocal,get_db
from src.models import Product,User,ReceiptBatch,Receipt
from src.utils.security import hash_password,issue_token
from src.routes import research as research_routes
from src.routes import catalog as catalog_routes
from src.routes import auth as auth_routes
import src.worker as worker

FAKE_USER=User(email='analyst@test',name='测试研究员',role='analyst',password_hash=hash_password('secret123'))
ADMIN=User(email='admin@test',name='测试负责人',role='admin',password_hash=hash_password('secret123'))
PRODUCTS=[('OAT','燕麦拿铁',15.,7.),('BREAD','全麦餐包',9.,3.5),('YOG','原味酸奶',8.,4.),('NUT','每日坚果',12.,5.),('TEA','乌龙冷萃',10.,3.),('EGG','溏心鸡蛋',5.,2.)]

@pytest.fixture()
def db():
 engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
 Base.metadata.create_all(engine)
 Session=__import__('sqlalchemy.orm',fromlist=['sessionmaker']).sessionmaker(engine,expire_on_commit=False)
 with Session() as session:
  session.add_all([FAKE_USER,ADMIN])
  session.add_all([Product(sku=sku,name=name,price=price,cost=cost,category='测试') for sku,name,price,cost in PRODUCTS])
  session.commit()
  yield session

def add_batch(db,name,receipts):
 batch=ReceiptBatch(name=name,filename=name+'.jsonl',checksum='0'*64);db.add(batch);db.flush()
 db.add_all([Receipt(batch_id=batch.id,reference=ref,items=list(dict.fromkeys(items))) for ref,items in receipts]);db.commit()
 return batch

@pytest.fixture()
def client(db,monkeypatch):
 def inline_delay(run_id): worker.analyze(db,run_id)
 monkeypatch.setattr(worker.analyze_run,'delay',inline_delay)
 app=FastAPI();app.include_router(research_routes.router);app.include_router(catalog_routes.router);app.include_router(auth_routes.router)
 def override(): yield db
 app.dependency_overrides[get_db]=override
 return TestClient(app)

@pytest.fixture()
def auth(db):
 return {'Authorization':'Bearer '+issue_token(FAKE_USER)}
