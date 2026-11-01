import { useState } from 'react';
import type { FormEvent } from 'react';
import { apiRequest } from './lib/api';

type WorkspaceTab = 'experiments' | 'memory' | 'collaboration' | 'writing';
function pretty(value: unknown) { return JSON.stringify(value, null, 2) ?? String(value); }
function ResponsePanel({ title, value }: { title: string; value: unknown }) {
  return <section className="result-card"><div className="card-title"><h2>{title}</h2><button className="text-button" onClick={() => void navigator.clipboard?.writeText(pretty(value))}>Copy JSON</button></div><pre>{pretty(value)}</pre></section>;
}
function useRequest() {
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [result, setResult] = useState<unknown>(null);
  const execute = async (request: () => Promise<unknown>) => {
    setBusy(true); setError('');
    try { const value = await request(); setResult(value); return value; }
    catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); return null; }
    finally { setBusy(false); }
  };
  return { busy, error, result, execute };
}
function Experiments() {
  const request = useRequest();
  const [items, setItems] = useState<unknown>(null);
  const [title, setTitle] = useState(''), [question, setQuestion] = useState(''), [hypothesisId, setHypothesisId] = useState('');
  const [method, setMethod] = useState(''), [success, setSuccess] = useState(''), [failure, setFailure] = useState('');
  const load = async () => { const value = await request.execute(() => apiRequest('/api/v1/records?record_type=experiment_plan&limit=50')); if (value !== null) setItems(value); };
  const create = async (event: FormEvent) => {
    event.preventDefault();
    const value = await request.execute(() => apiRequest('/api/v1/records', { method: 'POST', body: JSON.stringify({
      record_type: 'experiment_plan', title, research_question: question, hypothesis_record_id: hypothesisId, method,
      success_criteria: success.split('\n').map(x => x.trim()).filter(Boolean),
      failure_criteria: failure.split('\n').map(x => x.trim()).filter(Boolean),
      status: 'draft', risk_level: 'low', provenance: { method: 'human_provided', notes: 'Created from the ASDS experiment journal.' }
    }) }));
    if (value !== null) { setTitle(''); setQuestion(''); setHypothesisId(''); setMethod(''); setSuccess(''); setFailure(''); await load(); }
  };
  return <section className="view">
    <div className="section-head"><div><span className="eyebrow">PHASE 6 · EXPERIMENT LIFECYCLE</span><h2>Experiment journal</h2></div><button className="secondary-button" disabled={request.busy} onClick={() => void load()}>{request.busy ? 'Loading…' : 'Refresh records'}</button></div>
    <div className="notice"><b>Append-only research records</b><span>Plans are stored through the backend records API. Production access remains subject to tenant authorization and the record-isolation release gate.</span></div>
    <div className="work-card"><span className="eyebrow">NEW EXPERIMENT PLAN</span><h2>Register a reproducible protocol</h2><form onSubmit={create}>
      <label>Plan title</label><input value={title} onChange={e=>setTitle(e.target.value)} minLength={3} required placeholder="e.g. Ablation study — baseline architecture"/>
      <label>Research question</label><textarea value={question} onChange={e=>setQuestion(e.target.value)} minLength={10} required rows={3}/>
      <label>Existing hypothesis record UUID</label><input value={hypothesisId} onChange={e=>setHypothesisId(e.target.value)} required placeholder="UUID of a previously registered hypothesis"/>
      <label>Method / protocol</label><textarea value={method} onChange={e=>setMethod(e.target.value)} minLength={10} required rows={4}/>
      <label>Success criteria (one per line)</label><textarea value={success} onChange={e=>setSuccess(e.target.value)} required rows={2}/>
      <label>Failure criteria (one per line)</label><textarea value={failure} onChange={e=>setFailure(e.target.value)} required rows={2}/>
      <button className="primary-button" disabled={request.busy}>Save experiment plan ↗</button>
    </form></div>
    {request.error && <div className="notice notice-error"><b>Backend rejected the operation</b><span>{request.error}</span></div>}
    {items !== null && <ResponsePanel title="Stored experiment plans" value={items}/>}
    {request.result !== null && <ResponsePanel title="Latest API response" value={request.result}/>}
  </section>;
}
type MemoryEntry = { key: string; value: string; evidence: string; status: 'active' | 'disputed' };
function Memory() {
  const [entries, setEntries] = useState<MemoryEntry[]>([]), [key, setKey] = useState(''), [value, setValue] = useState(''), [evidence, setEvidence] = useState('');
  const [status, setStatus] = useState<'active' | 'disputed'>('active');
  const add = (event: React.FormEvent) => { event.preventDefault(); setEntries(current => [...current, { key: key.trim(), value: value.trim(), evidence: evidence.trim(), status }]); setKey(''); setValue(''); setEvidence(''); };
  const exportMemory = () => {
    const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), storage: 'browser-session-only', entries }, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob), anchor = document.createElement('a'); anchor.href = url; anchor.download = 'asds-scientific-memory-draft.json'; anchor.click(); URL.revokeObjectURL(url);
  };
  return <section className="view">
    <div className="section-head"><div><span className="eyebrow">PHASE 10 · VERSIONED KNOWLEDGE</span><h2>Scientific memory workspace</h2></div><span className="chip">SESSION DRAFT</span></div>
    <div className="notice"><b>Persistence boundary</b><span>The backend contains a versioned memory engine, but no authenticated memory API is currently exposed. Entries below remain in this browser session only; they are not sent to a server or retained after refresh. Export a draft if you need a copy.</span></div>
    <div className="work-card"><span className="eyebrow">CAPTURE A KNOWLEDGE ITEM</span><h2>Evidence-linked memory draft</h2><form onSubmit={add}>
      <label>Memory key</label><input value={key} onChange={e=>setKey(e.target.value)} required maxLength={200} placeholder="e.g. model-validation/baseline-v2"/>
      <label>Knowledge statement / structured value</label><textarea value={value} onChange={e=>setValue(e.target.value)} required rows={4}/>
      <label>Evidence reference (required)</label><textarea value={evidence} onChange={e=>setEvidence(e.target.value)} required rows={2} placeholder="DOI, record UUID, dataset identifier, or reproducible artifact reference"/>
      <label>Assessment status</label><select value={status} onChange={e=>setStatus(e.target.value as 'active'|'disputed')}><option value="active">Active — provisional</option><option value="disputed">Disputed</option></select><button className="primary-button">Add session draft</button>
    </form></div>
    <div className="section-head"><div><span className="eyebrow">CURRENT SESSION</span><h2>Memory entries ({entries.length})</h2></div><button className="secondary-button" disabled={!entries.length} onClick={exportMemory}>Export JSON</button></div>
    {entries.length === 0 ? <div className="gate-panel"><h2>No memory drafts yet</h2><p>Add an evidence-linked item above. No sample or fabricated scientific findings are preloaded.</p></div> : <div className="workspace-grid">{entries.map((entry,index)=><article className="work-card" key={index}><span className="eyebrow">{entry.status.toUpperCase()} · SESSION ONLY</span><h2>{entry.key}</h2><p>{entry.value}</p><small className="muted">Evidence: {entry.evidence}</small><button className="text-button" onClick={()=>setEntries(current=>current.filter((_,i)=>i!==index))}>Remove draft</button></article>)}</div>}
  </section>;
}
function Collaboration({ authenticatedActor }: { authenticatedActor: string }) {
  const request = useRequest();
  const [workflowId, setWorkflowId] = useState(''), [actor, setActor] = useState(authenticatedActor), [reason, setReason] = useState(''), [approvalToken, setApprovalToken] = useState('');
  const create = async (event: React.FormEvent) => { event.preventDefault(); await request.execute(()=>apiRequest('/api/v1/autonomy/workflows',{method:'POST',body:JSON.stringify({workflow_id:workflowId,consequential:true})})); };
  const inspect = async (event: React.FormEvent) => { event.preventDefault(); await request.execute(()=>apiRequest('/api/v1/autonomy/workflows/'+encodeURIComponent(workflowId))); };
  const transition = (action: 'plan'|'request-approval') => request.execute(()=>apiRequest('/api/v1/autonomy/workflows/'+encodeURIComponent(workflowId)+'/'+action,{method:'POST',body:JSON.stringify({actor,reason})}));
  const approve = () => request.execute(()=>apiRequest('/api/v1/autonomy/workflows/'+encodeURIComponent(workflowId)+'/approve',{method:'POST',body:JSON.stringify({actor,token:approvalToken})}));
  return <section className="view">
    <div className="section-head"><div><span className="eyebrow">PHASE 8 · GOVERNED ORCHESTRATION</span><h2>Collaboration & workflow control</h2></div><span className="chip">API WORKFLOW</span></div>
    <div className="notice"><b>Human approval remains mandatory</b><span>Creating or transitioning a workflow does not authorize consequential execution. Tenant membership and workflow permissions are enforced by the backend.</span></div>
    <div className="two-col">
      <div className="work-card"><span className="eyebrow">CREATE WORKFLOW</span><h2>Start a governed workflow</h2><form onSubmit={create}><label>Unique workflow ID</label><input value={workflowId} onChange={e=>setWorkflowId(e.target.value)} required maxLength={200} placeholder="project-review-2026-001"/><button className="primary-button" disabled={request.busy}>Create workflow ↗</button></form></div>
      <div className="work-card"><span className="eyebrow">INSPECT WORKFLOW</span><h2>Load current state</h2><form onSubmit={inspect}><label>Workflow ID</label><input value={workflowId} onChange={e=>setWorkflowId(e.target.value)} required/><button className="secondary-button" disabled={request.busy}>Retrieve state</button></form></div>
    </div>
    <div className="work-card"><span className="eyebrow">STATE TRANSITIONS</span><h2>Plan or request review</h2><label>Authenticated account label (audit metadata)</label><input value={actor} onChange={e=>setActor(e.target.value)} required placeholder="Authenticated account label"/><label>Reason for transition</label><textarea value={reason} onChange={e=>setReason(e.target.value)} required rows={2}/><div className="search-row"><button className="secondary-button" disabled={request.busy||!workflowId||!actor||!reason} onClick={()=>void transition('plan')}>Move to planned</button><button className="primary-button" disabled={request.busy||!workflowId||!actor||!reason} onClick={()=>void transition('request-approval')}>Request approval</button></div>
      <label>Approval token (only if issued through the trusted approval process)</label><input type="password" value={approvalToken} onChange={e=>setApprovalToken(e.target.value)} autoComplete="off"/><button className="secondary-button" disabled={request.busy||!workflowId||!actor||!approvalToken} onClick={()=>void approve()}>Submit approval token</button>
    </div>
    {request.error && <div className="notice notice-error"><b>Workflow operation failed</b><span>{request.error}</span></div>}
    {request.result !== null && <ResponsePanel title="Workflow state / API response" value={request.result}/>}
  </section>;
}
function Writing() {
  const [title,setTitle]=useState('Research manuscript draft'), [abstract,setAbstract]=useState(''), [introduction,setIntroduction]=useState('');
  const [methods,setMethods]=useState(''), [results,setResults]=useState(''), [limitations,setLimitations]=useState(''), [references,setReferences]=useState(''), [notice,setNotice]=useState('');
  const markdown = ['# '+title,'','## Abstract',abstract,'','## Introduction',introduction,'','## Methods',methods,'','## Results',results,'','## Limitations',limitations,'','## References (author-supplied; not independently verified)',references].join('\n');
  const exportDraft = () => { const blob=new Blob([markdown],{type:'text/markdown;charset=utf-8'}), url=URL.createObjectURL(blob), anchor=document.createElement('a'); anchor.href=url; anchor.download='asds-manuscript-draft.md'; anchor.click(); URL.revokeObjectURL(url); setNotice('Markdown draft exported. References and scientific claims still require independent verification.'); };
  return <section className="view">
    <div className="section-head"><div><span className="eyebrow">PHASE 12 · EVIDENCE-LINKED WRITING</span><h2>Manuscript studio</h2></div><span className="chip">DRAFT MODE</span></div>
    <div className="notice"><b>No automatic scientific validation</b><span>This editor prepares a structured manuscript draft. It does not invent citations, validate results, establish novelty, or authorize submission. The current backend writing module is not exposed as an API.</span></div>
    <div className="work-card"><label>Manuscript title</label><input value={title} onChange={e=>setTitle(e.target.value)} required/><label>Abstract</label><textarea rows={5} value={abstract} onChange={e=>setAbstract(e.target.value)} placeholder="State objective, methods, results and conclusion; distinguish measured from inferred findings."/><label>Introduction</label><textarea rows={6} value={introduction} onChange={e=>setIntroduction(e.target.value)}/><label>Methods</label><textarea rows={6} value={methods} onChange={e=>setMethods(e.target.value)}/><label>Results</label><textarea rows={6} value={results} onChange={e=>setResults(e.target.value)}/><label>Limitations</label><textarea rows={4} value={limitations} onChange={e=>setLimitations(e.target.value)}/><label>References (one per line; include DOI or stable URL)</label><textarea rows={5} value={references} onChange={e=>setReferences(e.target.value)}/><div className="search-row"><button className="primary-button" disabled={!title.trim()||!abstract.trim()||!methods.trim()||!limitations.trim()} onClick={exportDraft}>Export Markdown ↗</button><button className="secondary-button" onClick={()=>setNotice('Draft completeness: '+[title,abstract,introduction,methods,results,limitations,references].filter(x=>x.trim()).length+'/7 sections contain text.')}>Check draft completeness</button></div>{notice&&<div className="notice">{notice}</div>}</div>
    <div className="result-card"><div className="card-title"><h2>Live manuscript preview</h2><span className="chip">LOCAL DRAFT</span></div><pre>{markdown}</pre></div>
  </section>;
}
export default function AdvancedWorkspaces({ tab, authenticatedActor = '' }: { tab: WorkspaceTab; authenticatedActor?: string }) {
  if (tab === 'experiments') return <Experiments/>;
  if (tab === 'memory') return <Memory/>;
  if (tab === 'collaboration') return <Collaboration authenticatedActor={authenticatedActor}/>;
  return <Writing/>;
}
