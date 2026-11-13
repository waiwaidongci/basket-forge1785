import copy
import pytest
from src.services.samples import resolve_samples,SampleConflict,SampleError
from src.services.apriori import mine_rules
from src.models import Product
from conftest import add_batch

PRODUCTS={sku:{'price':price,'cost':cost} for sku,_,price,cost in __import__('conftest').PRODUCTS}

def test_overlap_same_reference_same_items_counted_once(db):
 a=add_batch(db,'批A',[('R-1',['OAT','BREAD']),('R-2',['OAT']),('R-3',['YOG','NUT'])])
 b=add_batch(db,'批B',[('R-3',['NUT','YOG']),('R-4',['TEA'])])
 baskets,report=resolve_samples(db,[a.id,b.id])
 assert baskets==[['BREAD','OAT'],['NUT','YOG'],['OAT'],['TEA']]
 assert report['raw_count']==5 and report['duplicate_count']==1 and report['effective_count']==4
 assert report['overlap_reference_count']==1
 assert [(x['raw_count'],x['duplicate_count'],x['effective_count']) for x in report['batches']]==[(3,0,3),(2,1,1)]

def test_overlap_is_order_independent_and_duplicate_lands_on_first_batch(db):
 a=add_batch(db,'批A',[('R-1',['OAT']),('R-2',['YOG'])])
 b=add_batch(db,'批B',[('R-1',['OAT'])])
 forward=resolve_samples(db,[a.id,b.id]);backward=resolve_samples(db,[b.id,a.id])
 assert forward[0]==backward[0]
 assert forward[1]['effective_count']==2==backward[1]['effective_count']
 # canonical duplicate always assigned to the smaller batch id
 assert forward[1]['batches']==backward[1]['batches']

def test_conflict_rejected_with_all_sources(db):
 a=add_batch(db,'批A',[('R-9',['OAT','BREAD'])])
 b=add_batch(db,'批B',[('R-9',['OAT','YOG'])])
 c=add_batch(db,'批C',[('R-9',['OAT','BREAD'])])
 with pytest.raises(SampleConflict) as error:
  resolve_samples(db,[c.id,a.id,b.id])
 message=str(error.value)
 assert 'BREAD, OAT' in message and 'OAT, YOG' in message
 assert '批A' in message and '批B' in message
 refs={source['batch_id'] for source in error.value.conflicts[0]['sources']}
 assert refs=={a.id,b.id,c.id}

def test_single_batch_is_unchanged(db):
 a=add_batch(db,'批A',[('R-1',['OAT','BREAD']),('R-2',['YOG'])])
 baskets,report=resolve_samples(db,[a.id])
 assert baskets==[['BREAD','OAT'],['YOG']]
 assert report['duplicate_count']==0 and report['effective_count']==2

def test_missing_batch_and_empty_selection(db):
 with pytest.raises(SampleError): resolve_samples(db,[])
 with pytest.raises(SampleError): resolve_samples(db,[99999])

def test_fingerprint_and_metrics_ignore_batch_and_receipt_order(db):
 a=add_batch(db,'批A',[('R-1',['OAT','BREAD']),('R-2',['OAT']),('R-3',['YOG','NUT'])])
 b=add_batch(db,'批B',[('R-3',['NUT','YOG']),('R-4',['TEA','OAT']),('R-5',['BREAD','EGG'])])
 first,_=resolve_samples(db,[a.id,b.id])
 second,_=resolve_samples(db,[b.id,a.id])
 assert first==second
 baseline=mine_rules(first,PRODUCTS,.2,.3,0,3)
 reordered=mine_rules([list(reversed(basket)) for basket in reversed(first)],PRODUCTS,.2,.3,0,3)
 assert baseline['checksum']==reordered['checksum']
 assert baseline['rules']==reordered['rules']
 assert baseline['receipt_count']==reordered['receipt_count']==5

def test_fingerprint_stable_for_repeated_receipt_contents(db):
 baskets=[['OAT','BREAD'],['OAT','BREAD'],['YOG']]
 base=mine_rules(baskets,PRODUCTS,.2,.3,0,2)
 again=mine_rules(copy.deepcopy(baskets),PRODUCTS,.2,.3,0,2)
 assert base['checksum']==again['checksum'] and base['rules']==again['rules']

def test_conflict_never_silently_merges(db):
 a=add_batch(db,'批A',[('R-1',['OAT','BREAD'])])
 b=add_batch(db,'批B',[('R-1',['BREAD','OAT'])])
 baskets,report=resolve_samples(db,[a.id,b.id])
 # Same item set written in another order is not a conflict.
 assert baskets==[['BREAD','OAT']] and report['duplicate_count']==1
