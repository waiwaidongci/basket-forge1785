from pydantic import BaseModel,Field,model_validator
class RunInput(BaseModel):
 name:str=Field(min_length=1,max_length=100)
 batch_ids:list[int]=Field(default_factory=list,max_length=20)
 # legacy single-batch field, still accepted so old clients and old tests work
 batch_id:int|None=Field(default=None,gt=0)
 min_support:float=Field(ge=.01,le=1,allow_inf_nan=False)
 min_confidence:float=Field(ge=.01,le=1,allow_inf_nan=False)
 min_lift:float=Field(ge=0,le=100,allow_inf_nan=False)
 max_size:int=Field(ge=2,le=4)
 @model_validator(mode='after')
 def check_batches(self):
  if any(x<0 for x in self.batch_ids): raise ValueError('批次编号必须为正整数')
  ids=[x for x in self.batch_ids if x>0]
  if self.batch_id is not None: ids.append(self.batch_id)
  if not ids: raise ValueError('请至少选择一个收据批次')
  if len(set(ids))>20: raise ValueError('一次最多合并 20 个批次')
  # Duplicate batch ids are collapsed: the union is order independent.
  self.batch_ids=sorted(set(ids))
  self.batch_id=self.batch_ids[0]
  return self
