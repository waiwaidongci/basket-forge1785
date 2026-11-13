from src.services import runs,proposals
from src.utils.csv_export import csv_response
from src.models import Product
from sqlalchemy import select
def sample_notes(report):
 """Leading # note lines: explain the merged sample before the rule table."""
 batches=report.get('batches') or []
 batch_ids='+'.join(str(x) for x in report.get('batch_ids',[]))
 notes=[['# 规则导出 / 有效样本口径',f'# 来源批次 {batch_ids or "—"}',f'# 原始总量 {report.get("raw_count",0)}',f'# 重复总量 {report.get("duplicate_count",0)}',f'# 有效样本总数 {report.get("effective_count",0)}',f'# 重叠编号数量 {report.get("overlap_reference_count",0)}']]
 notes.append(['# 批次编号','# 批次名称','# 原始数量','# 重复数量','# 有效数量','#'])
 notes+=[['# '+str(b.get('batch_id','')),'# '+str(b.get('name','')),'# '+str(b.get('raw_count',0)),'# '+str(b.get('duplicate_count',0)),'# '+str(b.get('effective_count',0)),'#'] for b in batches]
 notes.append(['# 说明','# 同编号且商品相同的收据只计一次；编号相同但商品不一致会拒绝计算并列出来源','#','#','#','#'])
 notes.append([])
 return notes
def export_rules(db,id):
 r=runs.get_run(db,id);names={p.sku:p.name for p in db.scalars(select(Product))}
 payload=runs.with_batches(db,r)
 result=payload['result'] or {}
 rules=result.get('rules',[])
 report=result.get('sample_report') or payload['sample_report'] or {}
 rows=[[','.join(names.get(s,s) for s in x['antecedent']),','.join(names.get(s,s) for s in x['consequent']),x['support_count'],x['support'],x['confidence'],x['lift'],x['gross_profit'],x['margin']] for x in rules]
 return csv_response(f'rules-{id}.csv',rows,['前件','后件','支持数','支持度','置信度','提升度','组合毛利','毛利率'],notes=sample_notes(report))
def export_proposals(db):
 return csv_response('bundle-proposals.csv',[[p['id'],p['name'],p['status'],','.join(p['rule']['antecedent']),','.join(p['rule']['consequent']),p['rule']['lift'],p['note']] for p in proposals.list_proposals(db)],['编号','提案','状态','前件SKU','后件SKU','提升度','说明'])
