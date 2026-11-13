import logging
from sqlalchemy import inspect,select,update,text
# Startup upgrade plan for databases created by the initial metadata scheme.
# SQLAlchemy's create_all never changes existing tables, so this runner adds the
# multi-batch columns and backfills legacy runs. Every step inspects first, so it
# is safe to run on every boot and on a fresh database.
def apply_migrations(engine):
 tables=inspect(engine).get_table_names()
 if 'rule_runs' in tables: upgrade_rule_runs(engine)
 if 'receipts' in tables: upgrade_receipts(engine)
def column_names(connection,table):
 return {c['name'] for c in inspect(connection).get_columns(table)}
def add_column(connection,engine,column,postgres_type):
 if engine.dialect.name=='postgresql':
  connection.execute(text(f'ALTER TABLE rule_runs ADD COLUMN IF NOT EXISTS {column} {postgres_type}'))
 else:
  # Only reached on a legacy SQLite database; fresh databases get the column from metadata.
  connection.execute(text(f'ALTER TABLE rule_runs ADD COLUMN {column} JSON'))
def upgrade_rule_runs(engine):
 from src.models import RuleRun
 with engine.begin() as connection:
  columns=column_names(connection,'rule_runs')
  if 'batch_id' in columns and engine.dialect.name=='postgresql':
   # Legacy single-batch column becomes optional; batch_ids is authoritative.
   connection.execute(text('ALTER TABLE rule_runs ALTER COLUMN batch_id DROP NOT NULL'))
  if 'batch_ids' not in columns:
   add_column(connection,engine,'batch_ids',"JSONB NOT NULL DEFAULT '[]'::jsonb")
  if 'sample_report' not in columns:
   add_column(connection,engine,'sample_report',"JSONB NOT NULL DEFAULT '{}'::jsonb")
 # Backfill in Python so JSON handling is identical across dialects. A legacy run
 # keeps its original single batch, so recomputing it stays single-batch.
 with engine.begin() as connection:
  for run_id,batch_id,batch_ids,sample_report in connection.execute(select(RuleRun.id,RuleRun.batch_id,RuleRun.batch_ids,RuleRun.sample_report)).all():
   values={}
   if batch_id is not None and not batch_ids: values['batch_ids']=[batch_id]
   if sample_report is None: values['sample_report']={}
   if values: connection.execute(update(RuleRun).where(RuleRun.id==run_id).values(**values))
 logging.info('migration_applied rule_runs.multi_batch')
def upgrade_receipts(engine):
 with engine.begin() as connection:
  # Reference lookup across batches is the hot path for overlap resolution.
  connection.execute(text('CREATE INDEX IF NOT EXISTS ix_receipts_reference ON receipts(reference)'))
 logging.info('migration_applied receipts.reference_index')
