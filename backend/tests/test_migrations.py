import sqlite3,tempfile
from pathlib import Path
from sqlalchemy import create_engine,inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from src.config.migrations import apply_migrations
from src.models import RuleRun,ReceiptBatch,Receipt,User

# The upgrade runner targets databases created by the initial metadata scheme.
# A SQLite file is used as a portable stand-in: it is built with the old schema
# (rule_runs without batch_ids/sample_report) and then upgraded in place.
def legacy_database(count=1):
 path=tempfile.mkstemp(suffix='.db')[1]
 raw=sqlite3.connect(path)
 raw.executescript("""
 CREATE TABLE receipt_batches (id INTEGER PRIMARY KEY, name VARCHAR(100) UNIQUE, filename VARCHAR(150), checksum VARCHAR(64), created_at DATETIME);
 CREATE TABLE receipts (id INTEGER PRIMARY KEY, batch_id INTEGER REFERENCES receipt_batches(id), reference VARCHAR(70), items JSON);
 CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(120) UNIQUE, name VARCHAR(80), role VARCHAR(20), password_hash VARCHAR(240));
 CREATE TABLE rule_runs (id INTEGER PRIMARY KEY, batch_id INTEGER NOT NULL REFERENCES receipt_batches(id), name VARCHAR(100), status VARCHAR(20),
   min_support FLOAT, min_confidence FLOAT, min_lift FLOAT, max_size INTEGER, result JSON, error VARCHAR(1000), creator_id INTEGER REFERENCES users(id), created_at DATETIME);
 """)
 raw.commit();raw.close()
 return path

def insert_legacy(path,runs):
 raw=sqlite3.connect(path)
 for run_id,batch_id in runs:
  raw.execute("INSERT INTO rule_runs (id,batch_id,name,status,min_support,min_confidence,min_lift,max_size,result) VALUES (?,?,?,?,?,?,?,?,?)",(run_id,batch_id,f'旧研究{run_id}','succeeded',.05,.35,1.,3,'{"receipt_count":2}'))
 raw.commit();raw.close()

def session_for(path):
 engine=create_engine('sqlite:///'+path,poolclass=NullPool)
 return engine,sessionmaker(engine,expire_on_commit=False)

def test_migration_adds_columns_and_backfills_original_batch():
 path=legacy_database();insert_legacy(path,[(1,7),(2,9)])
 engine,Session=session_for(path)
 apply_migrations(engine)
 columns={c['name'] for c in inspect(engine).get_columns('rule_runs')}
 assert {'batch_ids','sample_report'}<=columns
 with Session() as db:
  runs={run.id:run for run in db.query(RuleRun).all()}
  assert runs[1].batch_ids==[7] and runs[2].batch_ids==[9]
  assert runs[1].batch_id==7 and runs[2].batch_id==9
  assert runs[1].sample_report=={}

def test_migration_is_idempotent_and_keeps_multi_batch_runs():
 path=legacy_database();insert_legacy(path,[(1,7)])
 engine,Session=session_for(path)
 apply_migrations(engine)
 with Session() as db:
  db.get(RuleRun,1).batch_ids=[7,8];db.commit()
 apply_migrations(engine)
 with Session() as db:
  assert db.get(RuleRun,1).batch_ids==[7,8]  # user-edited multi-batch choice survives reboot
  assert db.query(RuleRun).count()==1

def test_migration_receipt_reference_index_exists():
 path=legacy_database();engine,Session=session_for(path)
 apply_migrations(engine)
 assert any(index['name']=='ix_receipts_reference' for index in inspect(engine).get_indexes('receipts'))
