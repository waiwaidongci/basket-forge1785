import {useState} from 'react';
import type {Batch,Run,User} from '../types/domain';
import {researchApi} from '../api/research';
import {PageTitle} from '../components/common/PageTitle';
import {RunList} from '../components/RunList';
import {Notice} from '../components/common/Notice';
import {useAsync} from '../hooks/useAsync';

type Conflict={reference:string;sources:{batch_id:number;batch_name:string;items:string[]}[]};
type ConflictDetail={message?:string;conflicts:Conflict[]};

function conflictDetail(error:Error):ConflictDetail|null{
 try{const detail=JSON.parse(error.message);if(Array.isArray(detail?.conflicts)&&detail.conflicts.length)return detail}catch{}
 return null;
}

export function Lab({batches,runs,user,reload,onSelect}:{batches:Batch[];runs:Run[];user:User;reload:()=>Promise<any>;onSelect:(r:Run)=>void}){
 const {busy,error,message,act}=useAsync();
 const [name,setName]=useState('秋季早餐组合研究'),[batchIds,setBatchIds]=useState<number[]>([]),[support,setSupport]=useState(.05),[confidence,setConfidence]=useState(.35),[lift,setLift]=useState(1),[size,setSize]=useState(3),[conflict,setConflict]=useState<ConflictDetail|null>(null);
 const selected=batchIds.length?batchIds:(batches[0]?[batches[0].id]:[]);
 const raw=batches.filter(b=>selected.includes(b.id)).reduce((n,b)=>n+b.receipt_count,0);
 function toggle(id:number){setBatchIds(current=>{const base=current.length?current:[batches[0]?.id].filter((x):x is number=>!!x);if(!base.includes(id))return [...base,id];if(base.length===1)return base;return base.filter(x=>x!==id)})}
 async function submit(e:React.FormEvent){e.preventDefault();setConflict(null);await act(async()=>{try{const r=await researchApi.queue({name,batch_ids:selected,min_support:support,min_confidence:confidence,min_lift:lift,max_size:size});await reload();onSelect(r);return r}catch(error){const detail=conflictDetail(error as Error);if(detail)setConflict(detail);throw error}},'规则任务已入队')}
 return <><PageTitle eyebrow="03 / RULE EXPERIMENT" title="先定标尺，再发现关系。" description="Apriori 逐层生成候选项集；低于支持度的分支会被剪枝，计算保留在独立 worker。"/>
 <div className="lab-grid"><form className="editor" onSubmit={submit}><h2>建立一份可复算的研究</h2><fieldset disabled={user.role==='viewer'||busy}>
 <label>研究名称<input value={name} onChange={e=>setName(e.target.value)} required maxLength={100}/></label>
 <div className="batch-picker"><span>输入收据批次（可多选联合研究）</span>{batches.map(b=><label key={b.id} className="check"><input type="checkbox" checked={selected.includes(b.id)} onChange={()=>toggle(b.id)}/><span>{b.name}<small>{b.receipt_count} 篮 / {b.filename}</small></span></label>)}
 <p>同编号且商品相同的收据只计一次；编号相同但商品不一致会拒绝计算并列出批次来源。</p><p className="fine">当前选择 {selected.length} 批、原始 {raw} 张；有效样本以提交后返回口径为准。调换批次或收据顺序不影响样本指纹。</p></div>
 <div className="form-grid"><label>最小支持度<input type="number" step=".01" min=".01" max="1" value={support} onChange={e=>setSupport(+e.target.value)}/></label><label>最小置信度<input type="number" step=".01" min=".01" max="1" value={confidence} onChange={e=>setConfidence(+e.target.value)}/></label><label>最小提升度<input type="number" step=".1" min="0" max="100" value={lift} onChange={e=>setLift(+e.target.value)}/></label><label>最大组合商品数<select value={size} onChange={e=>setSize(+e.target.value)}>{[2,3,4].map(n=><option key={n}>{n}</option>)}</select></label></div>
 <button className="primary" disabled={!batches.length}>{busy?'正在提交…':'提交规则研究 →'}</button></fieldset>
 {user.role==='viewer'&&<p>门店督导可阅读结果；提交研究需要分析师权限。</p>}
 {conflict&&<div className="notice error" role="alert"><b>收据编号相同但商品冲突，已拒绝计算</b><ul>{conflict.conflicts.map(c=><li key={c.reference}><code>{c.reference}</code>{c.sources.map(s=><span key={s.batch_id}> · {s.batch_name} #{s.batch_id} {s.items.join(' + ')}</span>)}</li>)}</ul></div>}
 <Notice error={conflict?undefined:error} message={message}/></form>
 <aside className="method-sheet"><small>METHOD CARD / 01</small><h2>三个读数，<br/>缺一不可。</h2><ol><li><b>支持度</b><p>组合出现次数 ÷ 有效样本总数。先避免稀有组合造成误读。</p></li><li><b>置信度</b><p>前后件一起出现 ÷ 前件出现。回答条件出现比例。</p></li><li><b>提升度</b><p>置信度 ÷ 后件支持度。大于 1 表示高于自然基率。</p></li></ol><p className="fine">联合批次先去重再计算；指纹取自排序后的有效篮子集合，批次与收据顺序变化不影响结果。候选最多 4 项，避免高阶规则泛滥。</p></aside></div>
 <div className="section-heading"><h2>所有规则实验</h2><span>队列状态每 3 秒更新</span></div><RunList runs={runs} onSelect={onSelect}/></>
}
