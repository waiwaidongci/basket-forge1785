from sqlalchemy import select,func
from fastapi import HTTPException
from src.models import RuleRun,ReceiptBatch,Receipt,Product
from src.utils.serialize import row
from .audit import record
from .samples import resolve_samples,SampleError,SampleConflict
from src.constants.enums import RunStatus

def legacy_report(db,run,batch_names):
 ids=list(run.batch_ids or ([run.batch_id] if run.batch_id else []))
 counts=dict(db.execute(select(Receipt.batch_id,func.count()).where(Receipt.batch_id.in_(ids)).group_by(Receipt.batch_id)).all())
 batches=[{'batch_id':x,'name':batch_names.get(x,''),'raw_count':counts.get(x,0),'duplicate_count':0,'effective_count':counts.get(x,0)} for x in ids]
 return {'batch_ids':ids,'batches':batches,'raw_count':sum(x['raw_count'] for x in batches),'duplicate_count':0,'effective_count':sum(x['effective_count'] for x in batches),'overlap_reference_count':0,'legacy':True}

def serialize_many(db,items):
 names={b.id:b.name for b in db.scalars(select(ReceiptBatch))}
 output=[]
 for item in items:
  data=row(item)
  if not data.get('batch_ids'): data['batch_ids']=[data['batch_id']] if data.get('batch_id') else []
  if not data.get('sample_report'): data['sample_report']=legacy_report(db,item,names)
  output.append(data)
 return output

def with_batches(db,item):
 return serialize_many(db,[item])[0]

def list_runs(db): return serialize_many(db,db.scalars(select(RuleRun).order_by(RuleRun.id.desc())))

def get_run(db,id):
 run=db.get(RuleRun,id)
 if not run: raise HTTPException(404,'规则实验不存在')
 return run

def create_run(db,data,user):
 try:
  _,sample_report=resolve_samples(db,data.batch_ids,db.scalars(select(Product.sku)))
 except SampleConflict as error: raise HTTPException(422,{'message':str(error),'conflicts':error.conflicts}) from error
 except SampleError as error: raise HTTPException(422,str(error)) from error
 run=RuleRun(batch_id=data.batch_ids[0],batch_ids=data.batch_ids,sample_report=sample_report,creator_id=user.id,**data.model_dump(exclude={'batch_ids','batch_id'}));db.add(run);db.commit()
 from src.worker import analyze_run
 try: analyze_run.delay(run.id)
 except Exception:
  run.status=RunStatus.FAILED;run.error='队列不可用，请重新提交';db.commit();raise HTTPException(503,run.error)
 record(db,user.email,'run.queue',{'run_id':run.id,'batch_ids':data.batch_ids});return with_batches(db,run)
