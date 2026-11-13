from collections import defaultdict
from sqlalchemy import select
from src.models import Receipt,ReceiptBatch

class SampleError(ValueError):
 pass

class SampleConflict(SampleError):
 def __init__(self,conflicts):
  self.conflicts=conflicts
  super().__init__(conflict_message(conflicts))

def _items_text(items): return '['+', '.join(items)+']'

def conflict_message(conflicts,limit=20):
 lines=[]
 for conflict in conflicts[:limit]:
  sources='；'.join(f"批次「{s['batch_name']}」#{s['batch_id']} {_items_text(s['items'])}" for s in conflict['sources'])
  lines.append(f"收据编号 {conflict['reference']}：{sources}")
 more=f"；另有 {len(conflicts)-limit} 个编号冲突" if len(conflicts)>limit else ''
 return f"收据编号相同但商品不一致，拒绝计算：{' / '.join(lines)}{more}"

def resolve_samples(db,batch_ids,valid_skus=None):
 """Merge receipts from several batches into one order-independent sample.

 Same reference + same item set is counted once. Same reference with different
 item sets raises SampleConflict listing every source. The canonical copy of an
 overlapping receipt belongs to the smallest batch id, so per-batch duplicate
 counts and the basket set do not depend on the order batches are supplied.
 """
 ids=sorted({int(batch_id) for batch_id in batch_ids})
 if not ids: raise SampleError('请至少选择一个收据批次')
 batches={b.id:b for b in db.scalars(select(ReceiptBatch).where(ReceiptBatch.id.in_(ids)))}
 missing=[batch_id for batch_id in ids if batch_id not in batches]
 if missing: raise SampleError('批次不存在：'+', '.join(str(x) for x in missing))
 rows=list(db.execute(select(Receipt.batch_id,Receipt.id,Receipt.reference,Receipt.items).where(Receipt.batch_id.in_(ids)).order_by(Receipt.batch_id,Receipt.id)))
 raw=defaultdict(int);groups=defaultdict(list)
 for batch_id,receipt_id,reference,items in rows:
  raw[batch_id]+=1
  groups[reference].append((batch_id,receipt_id,tuple(sorted(set(items or [])))))
 conflicts=[]
 for reference in sorted(groups):
  group=groups[reference]
  if len({entry[2] for entry in group})>1:
   sources=sorted(({'batch_id':batch_id,'batch_name':batches[batch_id].name,'items':list(items)} for batch_id,_,items in group),key=lambda source:(source['batch_id'],source['items']))
   conflicts.append({'reference':reference,'sources':sources})
 if conflicts: raise SampleConflict(conflicts)
 if valid_skus is not None:
  allowed=set(valid_skus);unknown=set()
  for group in groups.values(): unknown.update(set(group[0][2])-allowed)
  if unknown: raise SampleError('存在未知商品：'+', '.join(sorted(unknown)))
 samples=[];duplicates=defaultdict(int);overlap_references=0
 for reference,group in groups.items():
  canonical=min(group,key=lambda entry:(entry[0],entry[1]))
  samples.append(list(canonical[2]))
  for entry in group:
   if (entry[0],entry[1])!=(canonical[0],canonical[1]): duplicates[entry[0]]+=1
  if len({entry[0] for entry in group})>1: overlap_references+=1
 samples.sort()
 report_batches=[]
 for batch_id in ids:
  raw_count=raw.get(batch_id,0);duplicate_count=duplicates.get(batch_id,0)
  report_batches.append({'batch_id':batch_id,'name':batches[batch_id].name,'raw_count':raw_count,'duplicate_count':duplicate_count,'effective_count':raw_count-duplicate_count})
 report={'batch_ids':ids,'batches':report_batches,'raw_count':sum(x['raw_count'] for x in report_batches),'duplicate_count':sum(x['duplicate_count'] for x in report_batches),'effective_count':sum(x['effective_count'] for x in report_batches),'overlap_reference_count':overlap_references}
 return samples,report
