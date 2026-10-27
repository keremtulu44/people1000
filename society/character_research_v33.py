"""v3.3 broad study: 808 fixed jobs, distinct from the paused v3.2 study.

python -m society.character_research_v33
Offline ReferenceAdvisor only; real paid API use is neither required nor claimed.
"""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
import json
from pathlib import Path
import time

from . import character_research_v32 as base
from . import character_study as old
from .behavior import load_v33_profile as load_profile

OUT=Path('reports/character-research-v33');RAW=Path('runs/character-research-v33')
AGENDA_CASES=('notice','claim-aligned','claim-opposed','claim-peer','claim-manager-only',
    'evidence-direct','evidence-transmitted','evidence-unread','false-assertion','contradiction',
    'repeat-claims','repeat-notice','procedure-proof-only','qualification-only','no-notice',
    'low-channel-trust','high-channel-trust','sparse-contact','early-document','late-document')


def specs():
    for j in base.specs():
        j=deepcopy(j)
        if j['model']=='v3.2':j['model']='v3.3'
        yield j
    by={c['name']:c for c in old.catalog()}
    for name in ('none','severe80','i80-A-positive','i80-unknown-positive','source-aligned','source-opposed','crowd-none','contract-repeat'):
        for seed in range(4):
            yield dict(case=by[name],seed=seed,population=100,model='v3.2',days=30,section='fresh-v32-control')
    for name in AGENDA_CASES:
        for seed in range(4):
            yield dict(case={'name':'agenda-'+name,'family':'agenda'},seed=seed,population=100,model='v3.3',days=30,section='agenda')
    for name in ('notice','evidence-direct'):
        for seed in range(2):
            yield dict(case={'name':'agenda-'+name,'family':'agenda'},seed=seed,population=1000,model='v3.3',days=30,section='agenda-scale')


def prepared(job):
    if job['section'] not in ('agenda','agenda-scale'):return base.prepared(job)
    case=job['case'];name=case['name'][7:]
    sim=old.setup(next(c for c in old.catalog() if c['name']=='none'),job['seed'],job['population'],'v3.3',job['days'])
    p=sim.protocol['character_study'];p['case']=deepcopy(case);p['plan']=[]
    # Wait isolates ordinary opinion from unrelated autonomous political/collective choices.
    # Both all-agent no-agenda controls and all agenda jobs use this identical policy.
    p['case']['mode']='two'
    targets=p['targets'] if job['population']==100 else list(sim.agents)
    roots={pole:next(a.id for a in sim.agents.values() if a.initial_group=='authority' and a.alignment==pole) for pole in ('A','B')}
    peers=[a.id for a in sim.agents.values() if a.initial_group=='power_aligned']
    peer=next((aid for aid in peers if aid not in targets),peers[0])
    p['deep_initial']={a.id:{'alignment':a.alignment,'public_alignment':a.public_alignment,'public_support':a.public_support,
        'private_loyalty':a.private_loyalty,'core':a.behavior['core_orientation'],'evidence':a.change_evidence} for a in sim.agents.values()}
    def event(at,event_kind,**payload):p['plan'].append(dict(at=at,kind=event_kind,payload=payload))
    def action(at,source,target,claim=100,proof=False,aspect='qualification'):
        prop=dict(type='send',target=target,agenda_id='appointment',topic='agenda:appointment:'+aspect,
            aspect=aspect,claim=claim,text='Appointment statement, not political allegiance')
        if proof:prop['evidence_id']='qualification-document'
        p['plan'].append(dict(at=at,kind='action',actor=source,proposal=prop,bind=None))
    truth=0 if name=='false-assertion' else 100
    event(60,'agenda_create',issue='appointment',kind='appointment',issuer=roots['A'],title='Ordinary appointment dispute',
        facts={'qualification-document':{'aspect':'qualification','value':truth},'procedure-document':{'aspect':'procedure','value':100}})
    if name!='no-notice':
        for dst in targets:event(1500,'agenda_notice',issue='appointment',target=dst)
        for src in (*roots.values(),peer):event(1500,'agenda_notice',issue='appointment',target=src)
    # Identical controlled communication graph across agenda arms except explicitly sparse/trust arms.
    if name!='sparse-contact':
        trust=.2 if name=='low-channel-trust' else .95 if name=='high-channel-trust' else .8
        for src in (*roots.values(),peer):
            for dst in targets:
                if src==dst:continue
                e=sim.edge(src,dst)
                if e:e.update(trust=trust,latency=10)
                else:sim.edges.append(dict(source=src,target=dst,trust=trust,latency=10,type='agenda-probe'))
        p['controlled_network']='three public sources -> targets; trust .8 except named .2/.95 arms; no private-state edits'
    if name=='evidence-unread':sim.config.read_budget=0;p['read_budget_override']=0
    proof_names=('evidence-transmitted','evidence-unread')
    if name in proof_names:event(2940,'agenda_evidence',issue='appointment',target=roots['A'],evidence_id='qualification-document')
    direct_day=2 if name in ('evidence-direct','procedure-proof-only','early-document') else 15 if name in ('false-assertion','qualification-only') else 20 if name=='late-document' else None
    if direct_day is not None:
        for dst in targets:event(direct_day*1440+60,'agenda_evidence',issue='appointment',target=dst,
            evidence_id='procedure-document' if name=='procedure-proof-only' else 'qualification-document')
    speech=name not in ('notice','evidence-direct','repeat-notice','procedure-proof-only','no-notice')
    if speech:
        source=roots['B'] if name=='claim-opposed' else peer if name=='claim-peer' else roots['A']
        audience=[x for x in targets if x!=source and (name!='claim-manager-only' or sim.agents[x].initial_group=='authority')]
        starts=(3,10,17) if name=='repeat-claims' else (3,)
        for start in starts:
            for i,dst in enumerate(audience):action((start+i//2)*1440+60,source,dst,proof=name in proof_names)
        if name=='contradiction':
            for i,dst in enumerate(targets):
                if dst!=roots['B']:action((10+i//2)*1440+60,roots['B'],dst,claim=0)
    if name=='repeat-notice':
        for day in range(2,12):
            for dst in targets:event(day*1440+60,'agenda_notice',issue='appointment',target=dst)
    p['plan'].sort(key=lambda x:x['at']);p['initial_world_hash']=old.digest(old.world(sim))
    p['profile_hash']=old.digest(sim.behavior_profile)
    return sim


def one(job):
    base.OUT=OUT;base.RAW=RAW
    return base.one(job,prepare=prepared)


def main():
    OUT.mkdir(parents=True,exist_ok=True);RAW.mkdir(parents=True,exist_ok=True)
    jobs=list(specs());protocol={'date':'2026-10-25','purpose':'Fixed v3.3 ordinary-agenda implementation and broad character research; no empirical validation',
        'sources':base.sources(),'profile':load_profile(),'jobs':jobs,
        'notes':['692 historical/new-character specifications repeated under v3.3 (historical v2/v3.0 controls remain explicit). 32 fresh v3.2 controls; 80 ordinary-agenda runs; 4 population-1000 agenda scale runs.',
        'Paused v3.2 98-run ledger is untouched and not pooled. Exact-input legacy forced attendance remains observe by default; explicit-support cases separate.',
        'All agenda arms use Wait to isolate ordinary issue updates. Actual API packets are reviewed by ReferenceAdvisor offline; network calls zero. No claim of LLM persuasion validation.',
        'Ordinary agenda may change issue qualification/procedure opinions, not allegiance/ideology/general support. Natural daily drift is compared to a matched Wait untreated world, not frozen as a fake history.',
        'Claims, authentic documents, unread messages, repetition and channel trust have separate arms. Controlled edges and read-budget overrides explicitly declared.',
        'Identical public-role knowledge pooled; no agent balances/private memories in API packets. Group daily data sampled at actual day-end; subdaily crowds checked from logs.',
        'No behavior coefficient tuning during research. Two workers; compact evidence persists, raw agent-days ignored.']}
    path=OUT/'protocol.json'
    if path.exists():
        recorded=json.loads(path.read_text());recorded.pop('source_amendments',None)
        assert recorded==protocol,'Refuse mixed source/protocol'
    else:path.write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n')
    ledger=OUT/'completed.jsonl';done=[json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
    ids={r['run']['id'] for r in done};pending=[j for j in jobs if base.identifier(j) not in ids];started=time.perf_counter()
    with ProcessPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(one,j):j for j in pending}
        for future in as_completed(futures):
            j=futures[future]
            try:r=future.result()
            except Exception as exc:
                with (OUT/'failures.jsonl').open('a') as f:f.write(json.dumps({'id':base.identifier(j),'error':repr(exc)})+'\n')
                print('FAILED',base.identifier(j),repr(exc),flush=True);raise
            with ledger.open('a') as f:f.write(json.dumps(r,separators=(',',':'))+'\n')
            done.append(r)
            (OUT/'execution.json').write_text(json.dumps({'status':'running','completed':len(done),'expected':len(jobs)}))
            print(f"{len(done)}/{len(jobs)} {r['run']['id']} changed={r['run']['ever_changed']} withdrawn={r['run']['withdrawn']} attended={r['run']['attended']} reviews={r['run']['review_attempts']}",flush=True)
    assert protocol['sources']==base.sources(),'Sources changed during research'
    assert len(done)==len(jobs) and len({r['run']['id'] for r in done})==len(jobs)
    done.sort(key=lambda r:r['run']['id']);old.csv_write(OUT/'runs.csv',[r['run'] for r in done]);old.csv_write(OUT/'groups.csv',[g for r in done for g in r['groups']])
    (OUT/'execution.json').write_text(json.dumps({'status':'complete','completed':len(done),'expected':len(jobs),'sources_unchanged':True,
        'agent_days':sum(r['raw_agent_days']['rows'] for r in done),'persisted_files':sum(len(r['files']) for r in done),
        'last_invocation_seconds':time.perf_counter()-started},indent=2)+'\n')
    print('ALL COMPLETE',len(done),flush=True)


if __name__=='__main__':main()
