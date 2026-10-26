"""Broad v3.2 replication, fixed coefficients. Never overwrites historical research.

python -m society.character_research_v32
Two workers; resumable run-level evidence. Raw agent-days are Git-ignored;
actual daily group distributions and causal event audits persist compactly.
"""
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import statistics as st
import time

from . import character_study as old
from . import character_study_followup as follow
from .engine import BaselineProvider, Simulation
from .behavior import load_profile

OUT=Path('reports/character-research-v32')
RAW=Path('runs/character-research-v32')
EXTRAS=(['nonprice-'+x for x in ('early','late','ramp','pulse','repeated')]+
        ['colocation-'+x for x in ('opposed-support','shared-support','shared-observe','departure')]+
        ['local-support-'+x for x in ('mild','severe','blocked')]+
        ['contest-'+x for x in ('valid','unknown','poor','empty')]+
        ['observer-study','observer-no-study','recovery40','recovery80'])


def sources():
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('society').iterdir())
            if p.suffix in ('.py','.json')}


def specs():
    for c,s,n,m,d in old.jobs():
        yield dict(case=c,seed=s,population=n,model='v3.2' if m=='v3.1' else m,days=d,section='replication')
    for c,s,mode,m in follow.specifications():
        yield dict(case=c,seed=s,population=100,model='v3.2' if m=='v3.1' else m,days=30,section='directional',mode=mode)
    for name in EXTRAS:
        for s in range(4):
            yield dict(case={'name':'x-'+name,'family':'new-mechanism'},seed=s,population=100,model='v3.2',days=30,section='new-mechanism')


def identifier(job):
    return f"{job['section']}-{job.get('mode','')}-{job['case']['name']}-n{job['population']}-s{job['seed']}-{job['model']}-d{job['days']}"


class NoStudy(BaselineProvider):
    def decide(self, obs):
        p=super().decide(obs)
        return {'type':'wait'} if p['type']=='self_study' else p


def prepared(job):
    c=job['case'];s=job['seed'];m=job['model'];d=job['days']
    if job['section']=='directional':
        return follow.prepared(c,s,job['mode'],m)
    if job['section']!='new-mechanism':return old.setup(c,s,job['population'],m,d)
    name=c['name'][2:]
    base=next(x for x in old.catalog() if x['name']==('i'+name[-2:]+'-A-positive' if name.startswith('recovery') else 'none'))
    sim=old.setup(base,s,100,m,d);p=sim.protocol['character_study'];p['case']=deepcopy(c)
    plan=p['plan'] if name.startswith('recovery') else []
    def event(day,kind,payload):plan.append(dict(at=day*1440+60,kind=kind,payload=payload))
    def action(at,actor,prop,bind=None):plan.append(dict(at=at,kind='action',actor=actor,proposal=prop,bind=bind))
    by={g:[a.id for a in sim.agents.values() if a.initial_group==g] for g in old.GROUPS}
    if name.startswith('nonprice-'):
        levels={'early':[(1,.3)],'late':[(20,.3)],'ramp':[(i,.3*i/20) for i in range(1,21)],
                'pulse':[(1,.3),(10,0)],'repeated':[(i,v) for i in (1,11,21) for i,v in ((i,.3),(i+5,0))]}[name[9:]]
        for day,level in levels:
            for target in p['targets']:event(day,'local_disruption',dict(target=target,domain='supply_access',severity=level))
    elif name.startswith('colocation-'):
        # Each opposite-side root creates and attends its own register. No new edges.
        a=next(a.id for a in sim.agents.values() if a.initial_group=='authority' and a.alignment=='A')
        b=next(a.id for a in sim.agents.values() if a.initial_group=='authority' and a.alignment=='B')
        p['case']['mode']='two'  # Same Wait policy as historical forced-presence controls.
        for actor,bind,purpose in ((a,'g','support:A'),(b,'h','support:B')):
            if 'shared' in name or name.endswith('departure'):purpose='shared-cost-demand'
            action(1500,actor,dict(type='create_gathering',place='square',start=2940,end=3100,purpose=purpose),bind)
            action(2940,actor,dict(type='attend_gathering',gathering_id='$'+bind,
                participation='observe' if name.endswith('observe') else 'support'))
        if name.endswith('departure'):action(3000,b,dict(type='leave_gathering',gathering_id='$h'))
    elif name.startswith('local-support-'):
        # Controlled local ring adds reachable communication, never belief, risk or attendance.
        # All initial personality/financial values remain untouched.
        agents=by['discontented'];p['controlled_network']='directed discontented ring, trust .8, latency 10; extra edges disclosed'
        for i,aid in enumerate(agents):
            dst=agents[(i+1)%len(agents)];edge=sim.edge(aid,dst)
            if edge:edge.update(trust=.8,latency=10)
            else:sim.edges.append(dict(source=aid,target=dst,type='probe',trust=.8,latency=10))
            event(1,'local_disruption',dict(target=aid,domain='supply_access',severity=.3 if name.endswith('mild') else .9))
            action(1600,aid,dict(type='send',target=dst,topic='grievance',claim=30 if name.endswith('mild') else 90,text='Personal local experience, not attendance'))
        if name.endswith('blocked'):p['case']['mode']='blocked'
    elif name.startswith('contest-'):
        a=by['authority'][0];rival=by['authority'][1]
        p['case']['mode']='two'  # Isolate validation/effect, no autonomous contest first.
        if name.endswith('unknown'):sim.agents[a].behavior['known'].pop(rival,None)
        else:sim.agents[a].behavior['known'][rival]={'group':'authority','pole':sim.agents[rival].public_alignment,'trust':.5}
        if name.endswith('poor'):sim.agents[a].savings=-10000.
        if name.endswith('empty'):sim.authorities[rival]['institutional_power']=0.
        action(1500,a,dict(type='compete_position',target=rival))
        p['controlled_initialization']='local rival knowledge; poor=-10000 starting savings; empty=zero rival institutional position; each separate named arm'
    elif name.startswith('recovery'):
        event(15,'price_shock',{'multiplier':1/float(base['price'])})
        leader=next(x['actor'] for x in plan if x['kind']=='action')
        for day in (16,20,24):
            for dst in p['anchors']:action(day*1440+60,leader,dict(type='send',target=dst,topic='economic_outlook',claim=0,text='Forecast, not automatic recovered support'))
    elif name=='observer-no-study':p['no_study']=True
    p['plan']=sorted(plan,key=lambda x:x['at']);p['initial_world_hash']=old.digest(old.world(sim))
    p['initial_institutional_position']=sum(x['institutional_power'] for x in sim.authorities.values())
    return sim


def advance(sim,until):
    """Record interference/rejection instead of assuming scenario input succeeded."""
    p=sim.protocol['character_study'];provider=NoStudy() if p.get('no_study') else old.provider_for(p['case'])
    while p['next_input']<len(p['plan']) and p['plan'][p['next_input']]['at']<=until:
        item=p['plan'][p['next_input']];sim.run(item['at'],provider,max_events=1000000)
        if item['kind']=='action':
            prop=deepcopy(item['proposal'])
            if isinstance(prop.get('gathering_id'),str) and prop['gathering_id'].startswith('$'):
                prop['gathering_id']=p['bindings'].get(prop['gathering_id'][1:])
            before=set(getattr(sim,'gatherings',{}));did=sim.propose(item['actor'],prop);ok=sim.apply(did)
            reason=next((e['payload']['reason'] for e in reversed(sim.log) if e['kind']=='action_rejected' and e['payload']['decision']==did),None) if not ok else None
            p['input_outcomes'].append(dict(time=sim.time,decision=did,actor=item['actor'],type=prop['type'],accepted=ok,reason=reason))
            if item.get('bind'):
                created=set(sim.gatherings)-before;p['bindings'][item['bind']]=created.pop() if ok and len(created)==1 else None
        else:sim.schedule(sim.time,item['kind'],item['payload'])
        p['next_input']+=1
    sim.run(until,provider,max_events=1000000)


def distribution(values):
    values=[v for v in values if v is not None]
    return {'mean':st.mean(values),'min':min(values),'max':max(values),'sd':st.pstdev(values)} if values else None


def samples(sim,day):
    for r in old.observations(sim,day):
        a=sim.agents[r['agent']];c=a.behavior.get('character',{});social=a.behavior.get('social',{})
        r.update(development=c.get('development'),reaction=c.get('reaction'),reason=c.get('decision_reason'),
            surprise=sum(x.get('surprise',0) for x in c.get('domains',{}).values()) if c else None,
            fatigue=sum(x.get('fatigue',0) for x in c.get('domains',{}).values()) if c else None,
            institutional_position=sim.authorities.get(a.id,{}).get('institutional_power'),
            visible=len(social.get('visible_participants',[])),supporting=len(social.get('supporting_participants',[])))
        yield r


def group_day(rows,rid):
    for group in old.GROUPS:
        items=[r for r in rows if r['group']==group]
        yield dict(id=rid,day=items[0]['day'],time=items[0]['time'],group=group,n=len(items),
            distributions={k:distribution([r[k] for r in items]) for k in
                ('harm','burden','distress','loyalty','savings','reaction','surprise','fatigue','development','institutional_position','all_trust')},
            alignment=dict(Counter(r['alignment'] for r in items)),reasons=dict(Counter(r['reason'] for r in items)),
            support_zero=sum(r['public_support']==0 for r in items),negative_savings=sum(r['savings']<0 for r in items))


def one(job,prepare=None):
    started=time.perf_counter();rid=identifier(job);sim=(prepare or prepared)(job);p=sim.protocol['character_study']
    folder=RAW/rid;folder.mkdir(parents=True,exist_ok=True)
    persisted=OUT/'evidence'/rid;persisted.mkdir(parents=True,exist_ok=True)
    initial={a.id:dict(alignment=a.alignment,loyalty=a.private_loyalty,beliefs=deepcopy(a.beliefs),development=a.behavior.get('character',{}).get('development')) for a in sim.agents.values()}
    initial_power=sum(x['institutional_power'] for x in sim.authorities.values())
    history={g:{'harm':[],'burden':[]} for g in old.GROUPS}
    with gzip.open(folder/'agent-days.jsonl.gz','wt',compresslevel=1) as raw, gzip.open(persisted/'group-days.jsonl.gz','wt',compresslevel=6) as compact:
        for day in range(job['days']):
            advance(sim,(day+1)*1440-1);rows=list(samples(sim,day))
            for r in rows:
                raw.write(json.dumps(r,separators=(',',':'))+'\n')
                history[r['group']]['harm'].append(r['harm']);history[r['group']]['burden'].append(r['burden'])
            for r in group_day(rows,rid):compact.write(json.dumps(r,separators=(',',':'))+'\n')
    row,groups=old.extract(sim,rid,history);row.update(section=job['section'],wall_seconds=time.perf_counter()-started,
        initial_institutional_position=initial_power,final_institutional_position=sum(x['institutional_power'] for x in sim.authorities.values()))
    events=Counter(e['kind'] for e in sim.log)
    row.update(institutional_contests=events['institutional_competition'],self_study_actions=events['self_development'],
        restored_support=sum(e['kind']=='action_applied' and e['payload']['type']=='declare_support' for e in sim.log),
        co_presence_without_shared_strength=sum(e['kind']=='collective_observation' and len(e['payload']['visible_participants'])>1 and not e['payload']['collective_active'] for e in sim.log),
        support_membership_errors=sum(e['kind']=='collective_observation' and e['payload']['collective_active'] and 'supporting_participants' in e['payload'] and e['payload']['agent'] not in e['payload']['supporting_participants'] for e in sim.log))
    rt=getattr(sim,'agenda_runtime',{})
    row.update(review_attempts=len(rt.get('requests',[])),network_attempts=rt.get('network_requests',0),
        agenda_responses=events['agenda_response'],agenda_reads=events['agenda_claim_read'],agenda_documents=events['agenda_evidence_learned'])
    for g in groups:
        agents=[a for a in sim.agents.values() if a.initial_group==g['group']];ids={a.id for a in agents}
        g.update(mean_distress=st.mean(a.behavior.get('social',{}).get('distress',0) for a in agents),
            mean_development=st.mean(a.behavior['character']['development'] for a in agents) if job['model'] in ('v3.2','v3.3') and g['group']=='observer' else None,
            institutional_contests=sum(e['kind']=='institutional_competition' and e['payload']['actor'] in ids for e in sim.log),
            self_study_actions=sum(e['kind']=='self_development' and e['payload']['agent'] in ids for e in sim.log),
            final_reasons=dict(Counter(a.behavior.get('character',{}).get('decision_reason') for a in agents)))
    targets=[]
    for aid in p['targets']:
        a=sim.agents[aid];c=a.behavior.get('character',{})
        targets.append(dict(agent=aid,group=a.initial_group,initial=initial[aid],alignment=a.alignment,loyalty=a.private_loyalty,
            beliefs=a.beliefs,signals=c.get('signals'),assessments=c.get('source_assessments'),development=c.get('development'),
            read_messages=[{k:v for k,v in m.items() if k!='text'} for m in a.memories if 'message_id' in m],
            benefit_sources=a.behavior.get('appraisal',{}).get('benefit_sources',{}),
            domains=c.get('domains'),verified_failures=c.get('verified_failures'),verified_recoveries=c.get('verified_recoveries'),reason=c.get('decision_reason'),agenda=deepcopy(a.behavior.get('agenda',{}))))
    keep={'alignment_changed','core_orientation_changed','support_withdrawn','institutional_competition',
          'gathering_created','gathering_attended','gathering_departed','collective_observation',
          'collective_expression_started','collective_expression_ended','action_rejected','responsibility_direct_experience',
          'agenda_learned','agenda_claim_read','agenda_evidence_learned','agenda_response','agenda_advice_rejected'}
    audit=dict(protocol=p,targets=targets,event_counts=dict(events),agenda_runtime=rt,
        final_deep_state={a.id:{'alignment':a.alignment,'public_alignment':a.public_alignment,'public_support':a.public_support,
             'private_loyalty':a.private_loyalty,'core':a.behavior['core_orientation'],'evidence':a.change_evidence} for a in sim.agents.values()},
        daily_reasons=dict(Counter(e['payload']['reason'] for e in sim.log if e['kind']=='daily_response_appraisal')),
        events=[e for e in sim.log if e['kind'] in keep])
    with gzip.open(persisted/'audit.json.gz','wt',compresslevel=6) as f:json.dump(audit,f,separators=(',',':'))
    raw_path=folder/'agent-days.jsonl.gz'
    files={str(path):dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(persisted.iterdir())}
    return dict(run=row,groups=groups,files=files,raw_agent_days=dict(path=str(raw_path),rows=job['population']*job['days'],sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest()))


def main():
    OUT.mkdir(parents=True,exist_ok=True);RAW.mkdir(parents=True,exist_ok=True)
    jobs=list(specs());protocol=dict(date='2026-10-25',purpose='Broad v3.2 replication + separately declared new-mechanism probes; not social validation',
        sources=sources(),profile=load_profile(),jobs=jobs,
        notes=['612 historical specifications repeated: 556 v3.2 jobs and 56 explicitly historical v2/v3.0 controls; plus 80 new mechanism runs. No coefficients changed.',
        'Historical source probes and forced presence use Wait; autonomous arms use baseline policy. NoAttendance suppresses attendance only; NoStudy suppresses self-study only.',
        'Exact-input historical forced attendance is now observe by default in v3.2. New explicit-support arms are labeled separately; do not conflate those differences with persuasion.',
        'Observer pruning changes initial topology vs v3.1. Reused seeds do not make old/new worlds identical. Source fixtures explicitly add controlled edges.',
        'Daily group distributions are actual day-end samples; gathering peaks come from event-time observations. Raw agent-days are ignored/external, compact evidence persists.',
        'Input refusals and dependent unavailable bindings are recorded, not assumed applied. No failed run is silently dropped.'])
    path=OUT/'protocol.json'
    if path.exists():assert json.loads(path.read_text())==protocol,'Protocol changed; refuse to mix runs'
    else:path.write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n')
    ledger=OUT/'completed.jsonl';done=[json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
    ids={x['run']['id'] for x in done};pending=[j for j in jobs if identifier(j) not in ids];started=time.perf_counter()
    (OUT/'execution.json').write_text(json.dumps(dict(status='running',expected=len(jobs),completed=len(done))))
    with ProcessPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(one,j):j for j in pending}
        for future in as_completed(futures):
            j=futures[future]
            try:r=future.result()
            except Exception as exc:
                with (OUT/'failures.jsonl').open('a') as f:f.write(json.dumps(dict(id=identifier(j),error=repr(exc)))+'\n')
                print('FAILED',identifier(j),repr(exc),flush=True)
                raise
            with ledger.open('a') as f:f.write(json.dumps(r,separators=(',',':'))+'\n')
            done.append(r)
            (OUT/'execution.json').write_text(json.dumps(dict(status='running',expected=len(jobs),completed=len(done))))
            print(f"{len(done)}/{len(jobs)} {r['run']['id']} changed={r['run']['ever_changed']} withdrawn={r['run']['withdrawn']} attended={r['run']['attended']}",flush=True)
    assert sources()==protocol['sources'],'Model or runner changed during study'
    assert len(done)==len(jobs) and len({x['run']['id'] for x in done})==len(jobs)
    done.sort(key=lambda x:x['run']['id']);old.csv_write(OUT/'runs.csv',[x['run'] for x in done]);old.csv_write(OUT/'groups.csv',[g for x in done for g in x['groups']])
    (OUT/'execution.json').write_text(json.dumps(dict(status='complete',expected=len(jobs),completed=len(done),source_hashes_unchanged=True,last_invocation_seconds=time.perf_counter()-started,
        agent_days=sum(x['raw_agent_days']['rows'] for x in done),persisted_files=sum(len(x['files']) for x in done)),indent=2)+'\n')
    print('ALL COMPLETE',len(done),flush=True)


if __name__=='__main__':main()
