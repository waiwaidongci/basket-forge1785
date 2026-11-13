import json
from src.models import RuleRun,ReceiptBatch,Receipt
from conftest import add_batch

FORM={'name':'联合研究','min_support':.2,'min_confidence':.3,'min_lift':0,'max_size':3}

def test_api_multi_batch_run_reports_sample_counts(client,auth,db):
 a=add_batch(db,'批A',[('R-1',['OAT','BREAD']),('R-2',['OAT']),('R-3',['YOG','NUT'])])
 b=add_batch(db,'批B',[('R-3',['NUT','YOG']),('R-4',['TEA','OAT'])])
 response=client.post('/runs',json={**FORM,'batch_ids':[b.id,a.id]},headers=auth)
 assert response.status_code==201,response.text
 body=response.json()
 assert body['batch_ids']==sorted([a.id,b.id])
 report=body['sample_report']
 assert report['raw_count']==5 and report['duplicate_count']==1 and report['effective_count']==4
 run=db.get(RuleRun,body['id'])
 assert run.status=='succeeded'
 assert run.result['receipt_count']==4
 assert run.result['sample_report']==report

def test_api_batch_order_yields_same_fingerprint_and_rules(client,auth,db):
 a=add_batch(db,'批A',[('R-1',['OAT','BREAD']),('R-2',['OAT'])])
 b=add_batch(db,'批B',[('R-3',['BREAD','EGG']),('R-4',['YOG','NUT'])])
 first=client.post('/runs',json={**FORM,'batch_ids':[a.id,b.id]},headers=auth).json()
 second=client.post('/runs',json={**FORM,'batch_ids':[b.id,a.id]},headers=auth).json()
 assert first['result']['checksum']==second['result']['checksum']
 assert first['result']['rules']==second['result']['rules']
 assert first['result']['receipt_count']==second['result']['receipt_count']==4

def test_api_conflict_is_422_with_sources(client,auth,db):
 a=add_batch(db,'批A',[('R-7',['OAT','BREAD'])])
 b=add_batch(db,'批B',[('R-7',['OAT','YOG'])])
 response=client.post('/runs',json={**FORM,'batch_ids':[a.id,b.id]},headers=auth)
 assert response.status_code==422
 detail=response.json()['detail']
 assert detail['conflicts'][0]['reference']=='R-7'
 assert {source['batch_id'] for source in detail['conflicts'][0]['sources']}=={a.id,b.id}
 assert 'BREAD, OAT' in detail['message'] and 'OAT, YOG' in detail['message']
 assert db.query(RuleRun).count()==0

def test_api_legacy_single_batch_field_still_works(client,auth,db):
 a=add_batch(db,'批A',[('R-1',['OAT','BREAD']),('R-2',['OAT'])])
 response=client.post('/runs',json={**FORM,'batch_id':a.id},headers=auth)
 assert response.status_code==201
 body=response.json()
 assert body['batch_ids']==[a.id] and body['sample_report']['effective_count']==2
 assert body['result']['receipt_count']==2

def test_api_rejects_empty_or_unknown_batch(client,auth,db):
 assert client.post('/runs',json={**FORM,'batch_ids':[]},headers=auth).status_code==422
 assert client.post('/runs',json={**FORM,'batch_ids':[12345]},headers=auth).status_code==422

def test_api_dedupes_repeated_batch_ids(client,auth,db):
 a=add_batch(db,'批A',[('R-1',['OAT','BREAD']),('R-2',['OAT'])])
 response=client.post('/runs',json={**FORM,'batch_ids':[a.id,a.id]},headers=auth)
 assert response.status_code==201
 assert response.json()['result']['receipt_count']==2

def test_api_export_includes_sample_report_rows(client,auth,db):
 a=add_batch(db,'批A',[('R-1',['OAT','BREAD']),('R-2',['OAT'])])
 b=add_batch(db,'批B',[('R-2',['OAT']),('R-3',['YOG','NUT'])])
 run=client.post('/runs',json={**FORM,'batch_ids':[a.id,b.id]},headers=auth).json()
 response=client.get(f"/runs/{run['id']}/export",headers=auth)
 assert response.status_code==200
 text=response.content.decode('utf-8-sig')
 assert '# 有效样本总数 3' in text and '# 原始总量 4' in text and '# 重复总量 1' in text
 assert '# 批A' in text and '# 批B' in text
 assert '# 2,# 1,# 1,#' in text  # per-batch: raw 2, duplicate 1, effective 1
 assert text.index('# 有效样本总数 3')<text.index('前件,后件')  # notes precede the table
 assert '前件,后件' in text

def test_list_and_detail_expose_batch_ids_for_legacy_runs(client,auth,db):
 a=add_batch(db,'批A',[('R-1',['OAT','BREAD']),('R-2',['OAT'])])
 legacy=RuleRun(name='旧研究',batch_id=a.id,min_support=.2,min_confidence=.3,min_lift=0,max_size=3,status='succeeded',result={'receipt_count':2,'rules':[],'checksum':'abc'},creator_id=1)
 db.add(legacy);db.commit()
 for payload in (client.get('/runs',headers=auth).json()[0],client.get(f'/runs/{legacy.id}',headers=auth).json()):
  assert payload['batch_ids']==[a.id]
  assert payload['sample_report']['effective_count']==2
  assert payload['sample_report']['legacy'] is True

def test_worker_recomputes_legacy_run_from_its_original_batch(db):
 from src.worker import analyze,run_batch_ids
 a=add_batch(db,'批A',[('R-1',['OAT','BREAD']),('R-2',['OAT']),('R-3',['BREAD','EGG'])])
 b=add_batch(db,'批B',[('R-4',['YOG','NUT'])])
 legacy=RuleRun(name='旧研究',batch_id=a.id,batch_ids=[],min_support=.2,min_confidence=.3,min_lift=0,max_size=3,status='queued',creator_id=1)
 db.add(legacy);db.commit()
 assert run_batch_ids(legacy)==[a.id]
 analyze(db,legacy.id)
 db.refresh(legacy)
 assert legacy.status=='succeeded'
 assert db.get(type(legacy),legacy.id).result['receipt_count']==3
 assert legacy.sample_report['effective_count']==3
 assert legacy.sample_report['batch_ids']==[a.id]
