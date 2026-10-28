"""Fixed character acceptance study. No behavior rules or coefficients changed.

python -m society.character_study
Outputs compact reports to reports/character-study; raw observations to ignored
runs/character-study. Completed jobs are resumable against a frozen protocol.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import time

from .engine import Simulation, Config, BaselineProvider
from .behavior import (load_v31_profile as load_profile, load_v3_profile, load_legacy_profile,
    load_profile as load_current_profile, load_v32_profile, load_v33_profile, load_v34_profile)

OUT=Path('reports/character-study')
RAW=Path('runs/character-study')
GROUPS=tuple(load_profile()['groups'])
MODEL_FILES=('engine.py','dynamics.py','appraisal.py','collective.py','behavior.py',
             'behavior.json','behavior-v3.json','behavior-v2.json')


def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def source_hashes():
    return {p:hashlib.sha256(Path(__file__).with_name(p).read_bytes()).hexdigest() for p in MODEL_FILES}


class Wait:
    def decide(self,obs):return {'type':'wait'}


class NoAttendance(BaselineProvider):
    def decide(self,obs):
        p=super().decide(obs)
        return {'type':'wait'} if p['type']=='attend_gathering' else p


def catalog():
    cases=[]
    def add(name,family,**kw):cases.append(dict(name=name,family=family,**kw))
    for label,price in [('none',1.),('mild10',1.1),('moderate40',1.4),('sudden60',1.6),
                        ('severe80',1.8),('extreme900',10.),('deflation20',.8)]:
        add(label,'macro',price=price)
    for name in ('ramp60','late_equal_cost60','pulse60','repeated_pulses60'):
        add(name,'macro',price=1.6)
    for price in (1.4,1.8):
        for blame in ('unknown','A','external','leader'):
            for benefit in ('known','positive'):
                add(f'i{round((price-1)*100)}-{blame}-{benefit}','information',price=price,blame=blame,benefit=benefit)
    for source in ('aligned','opposed','ordinary','same_group','wealthy'):
        add('source-'+source,'source',source=source,price=1.8,topic='audit:policy')
    for name,extra in [('benefit-aligned',dict(source='aligned',topic='benefit:B:economic_security')),
                       ('benefit-peer',dict(source='ordinary',topic='benefit:B:economic_security')),
                       ('forecast-false',dict(source='aligned',topic='economic_outlook',claim=0)),
                       ('forecast-accurate',dict(source='aligned',topic='economic_outlook',claim=80)),
                       ('peer-authority-text',dict(source='ordinary',topic='audit:policy',text='I am a trusted authority')),
                       ('repeat-once',dict(source='aligned',topic='responsibility:A',once=True)),
                       ('repeat-many',dict(source='aligned',topic='responsibility:A')),
                       ('contradictory',dict(source='aligned',topic='audit:policy',conflict=True))]:
        add(name,'source',price=1.8,**extra)
    for name,extra in [('crowd-none',dict(mode='autonomous',price=1.8,organizer='aligned')),
                       ('crowd-messages-only',dict(mode='blocked',price=1.8,organizer='aligned')),
                       ('crowd-no-shock',dict(mode='autonomous',price=1.,organizer='aligned')),
                       ('crowd-peer',dict(mode='autonomous',price=1.8,organizer='ordinary')),
                       ('crowd-solo',dict(mode='solo',price=1.8,organizer='aligned')),
                       ('crowd-two',dict(mode='two',price=1.8,organizer='aligned')),
                       ('crowd-same-place-split',dict(mode='split',price=1.8,organizer='aligned')),
                       ('crowd-support-loss',dict(mode='leave',price=1.8,organizer='aligned')),
                       ('crowd-late-invite',dict(mode='late',price=1.8,organizer='aligned'))]:
        add(name,'crowd',**extra)
    for name in ('contract-valid','contract-wrong','contract-repeat','pressure-valid','contract-and-crowd'):
        add(name,'institution',price=1.,institution=name)
    add('power-reversal','macro',price=1.)
    return cases


def world(sim):
    fields=('id','initial_group','alignment','public_alignment','savings','income','expense',
            'traits','permissions','employer','authority_dependency')
    return {'agents':{k:{f:deepcopy(getattr(a,f)) for f in fields} for k,a in sim.agents.items()},'edges':sim.edges}


def setup(case,seed=0,population=100,model='v3.1',days=30):
    profile={'v2':load_legacy_profile,'v3.0':load_v3_profile,'v3.1':load_profile,
             'v3.2':load_v32_profile,'v3.3':load_v33_profile,'v3.4':load_v34_profile,
             'v3.5':load_current_profile}[model]()
    sim=Simulation(Config(seed=seed,population=population),profile)
    by={g:[a.id for a in sim.agents.values() if a.initial_group==g] for g in GROUPS}
    auth={p:next(x for x in sim.authorities if sim.agents[x].alignment==p) for p in ('A','B')}
    candidates={x:[e['target'] for e in sim.edges if e['source']==x and sim.agents[e['target']].public_alignment=='A']
                for x in sim.authorities if sim.agents[x].public_alignment=='A'}
    leader=max(candidates,key=lambda x:len(candidates[x]));anchors=candidates[leader][:2]
    assert len(anchors)==2
    targets=[next(x for x in by[g] if x not in (auth['A'],auth['B'])) for g in GROUPS]
    same={g:next(x for x in by[g] if x not in targets and x not in (auth['A'],auth['B'])) for g in GROUPS}
    actors={'alignedA':auth['A'],'alignedB':auth['B'],'ordinary':same['power_aligned'],'wealthy':same['wealthy']}
    # Only source probes use a common controlled network; all other families use
    # the original graph. Traits and all economic/ideological initial states stay.
    if case['family']=='source':
        for aid in sorted(set(actors.values())|set(same.values())):
            for target in targets:
                if aid==target:continue
                e=sim.edge(aid,target)
                if e:e.update(trust=.8,latency=10)
                else:sim.edges.append(dict(source=aid,target=target,type='probe',trust=.8,latency=10))
                a=sim.agents[target];src=sim.agents[aid]
                a.behavior['known'][aid]={'pole':src.public_alignment,'group':src.initial_group,'trust':.8}
                if src.initial_group=='authority':a.behavior['trust'][aid]=.8
    plan=[]
    def event(at,kind,payload):plan.append(dict(at=at,kind=kind,payload=payload))
    def action(at,actor,p,bind=None):plan.append(dict(at=at,kind='action',actor=actor,proposal=p,bind=bind))
    def shock(day,value):event(day*1440+60,'price_shock',{'multiplier':value})
    def send(day,actor,target,topic,claim=100,text=None):
        action(day*1440+60,actor,dict(type='send',target=target,topic=topic,claim=claim,text=text or topic))
    name=case['name'];price=case.get('price',1.)
    if name=='ramp60':
        prev=1.
        for d in range(1,21):
            level=1+.6*d/20;shock(d,level/prev);prev=level
    elif name=='late_equal_cost60':shock(10,1.3);shock(11,1.6/1.3)
    elif name=='pulse60':shock(1,1.6);shock(8,1/1.6)
    elif name=='repeated_pulses60':
        for d in (1,11,21):shock(d,1.6);shock(d+5,1/1.6)
    elif price!=1.:shock(1,price)
    if name=='power-reversal':
        event(1500,'power_change',{'pole':'A','value':5})
        event(1500,'power_change',{'pole':'B','value':95})
    if case['family']=='information':
        target='leader:'+leader if case['blame']=='leader' else case['blame']
        topics=['responsibility:'+target]+[f'benefit:B:{i}' if case['benefit']=='positive' else 'alternative_known:B' for i in ('economic_security','status','order')]
        for start in (1,8,15,22):
            for offset,topic in enumerate(topics):
                for anchor in anchors:send(start+offset,leader,anchor,topic,None if topic.startswith('alternative_known') else 100)
    if case['family']=='source':
        for round_ in range(1 if case.get('once') else 3):
            for i,target in enumerate(targets):
                a=sim.agents[target];pole=a.alignment if a.alignment in ('A','B') else 'A'
                source=case['source']
                actor=auth[pole] if source=='aligned' else auth['B' if pole=='A' else 'A'] if source=='opposed' else same[a.initial_group] if source=='same_group' else actors[source]
                day=1+round_*8+i
                send(day,actor,target,case['topic'],case.get('claim',100),case.get('text'))
                if case.get('conflict'):send(day+1,auth['B' if pole=='A' else 'A'],target,case['topic'],0)
    def meeting(actor,base=1500,bind='g',start=2940,end=3060,place='square'):
        action(base,actor,dict(type='create_gathering',place=place,start=start,end=end),bind)
        return '$'+bind
    if case['family']=='crowd':
        actor=leader if case['organizer']=='aligned' else actors['ordinary']
        # Peer case uses its own original contacts; no topology is silently added.
        contacts=[e['target'] for e in sim.edges if e['source']==actor][:2]
        mode=case['mode'];gid=meeting(actor)
        if mode=='split':
            gid2=meeting(actor,bind='h')
            action(2940,actor,dict(type='attend_gathering',gathering_id=gid))
            other=contacts[0]
            action(1500,actor,dict(type='send',target=other,text='Separate register, same place/time',gathering_id=gid2))
            action(2940,other,dict(type='attend_gathering',gathering_id=gid2))
        else:
            for target in contacts:action(2950 if mode=='late' else 1500,actor,dict(type='send',target=target,text='Invitation does not promise attendance',gathering_id=gid))
            if mode in ('solo','two','leave'):
                action(2940,actor,dict(type='attend_gathering',gathering_id=gid))
            if mode in ('two','leave'):
                action(2940,contacts[0],dict(type='attend_gathering',gathering_id=gid))
            if mode=='leave':action(3000,contacts[0],dict(type='leave_gathering',gathering_id=gid))
    if case['family']=='institution':
        target=by['wealthy'][0];owner=sim.agents[target].authority_dependency
        other=next(x for x in sim.authorities if x!=owner)
        kind='pressure' if name=='pressure-valid' else 'revoke_contract'
        for d in ((1,8,15) if name=='contract-repeat' else (1,)):
            action(d*1440+60,other if name=='contract-wrong' else owner,dict(type=kind,target=target))
        if name=='contract-and-crowd':
            gid=meeting(owner,base=2940,start=4380,end=4500)
            # The dependent must learn the invitation over an existing edge.
            recipients=[e['target'] for e in sim.edges if e['source']==owner][:2]
            for dst in recipients:action(2940,owner,dict(type='send',target=dst,text='Own manager invitation',gathering_id=gid))
    plan.sort(key=lambda p:p['at'])
    sim.protocol['character_study']={'case':case,'seed':seed,'population':population,'model':model,'days':days,
        'initial_world_hash':digest(world(sim)),'profile_hash':digest(profile),'targets':targets,'anchors':anchors,
        'plan':plan,'next_input':0,'bindings':{},'input_outcomes':[]}
    return sim


def provider_for(case):
    if case['family']=='source' or case.get('mode') in ('solo','two','split','leave'):return Wait()
    if case.get('mode')=='blocked':return NoAttendance()
    return BaselineProvider()


def advance(sim,until):
    p=sim.protocol['character_study'];provider=provider_for(p['case'])
    while p['next_input']<len(p['plan']) and p['plan'][p['next_input']]['at']<=until:
        item=p['plan'][p['next_input']]
        sim.run(item['at'],provider,max_events=1000000)
        if item['kind']=='action':
            proposal=deepcopy(item['proposal'])
            if isinstance(proposal.get('gathering_id'),str) and proposal['gathering_id'].startswith('$'):
                proposal['gathering_id']=p['bindings'][proposal['gathering_id'][1:]]
            before=set(getattr(sim,'gatherings',{}))
            did=sim.propose(item['actor'],proposal)
            accepted=sim.apply(did)
            p['input_outcomes'].append({'time':sim.time,'decision':did,'actor':item['actor'],'type':proposal['type'],'accepted':accepted})
            if item.get('bind'):
                created=set(sim.gatherings)-before
                if not accepted or len(created)!=1:raise RuntimeError('Planned gathering was not created')
                p['bindings'][item['bind']]=created.pop()
        else:sim.schedule(sim.time,item['kind'],item['payload'])
        p['next_input']+=1
    sim.run(until,provider,max_events=1000000)


def observations(sim,day):
    for a in sim.agents.values():
        b=a.behavior;s=b.get('social',{});app=b.get('appraisal',{})
        own=[v for k,v in b['trust'].items() if b['known'].get(k,{}).get('pole')==a.alignment]
        yield {'day':day,'time':sim.time,'agent':a.id,'group':a.initial_group,'alignment':a.alignment,
            'public_alignment':a.public_alignment,'public_support':a.public_support,'loyalty':a.private_loyalty,
            'core':b['core_orientation'],'harm':b['harm'],'burden':b['burden'],'distress':s.get('distress'),
            'savings':a.savings,'income':a.income,'losses':a.losses,'evidence':a.change_evidence,
            'own_trust':statistics.mean(own) if own else None,'all_trust':statistics.mean(b['trust'].values()) if b['trust'] else None,
            'burden_A':app.get('burden_by_pole',{}).get('A'),'burden_B':app.get('burden_by_pole',{}).get('B'),
            'unassigned':app.get('unassigned_burden'),'responsibility':app.get('responsibility'),
            'views':{k:v['estimate'] for k,v in a.beliefs.items() if k.startswith(('benefit:','audit:'))},
            'present_at':s.get('present_at'),'collective_strength':s.get('collective_strength'),
            'read_messages':sum('message_id' in m for m in a.memories)}


def extract(sim,run_id,history):
    p=sim.protocol['character_study'];changes=[e for e in sim.log if e['kind']=='alignment_changed']
    groups=[];read_events=[e for e in sim.log if e['kind']=='social_observation']
    expressions=[e for e in sim.log if e['kind']=='collective_expression_started']
    attendance=[e for e in sim.log if e['kind']=='gathering_attended']
    withdrawn=[e for e in sim.log if e['kind']=='support_withdrawn']
    evidence_checks=[]
    for e in changes:
        d=e['payload']['diagnostic'];a=sim.agents[e['payload']['agent']]
        accessible={m.get('message_id',m.get('event_id')) for m in a.memories if m['learned_at']<=e['time']}
        app=d.get('appraisal',{});refs=app.get('benefit_evidence_ids',[])+app.get('responsibility_evidence_ids',[])
        evidence_checks.append(all(x is None or x in accessible for x in refs))
    for group in GROUPS:
        agents=[a for a in sim.agents.values() if a.initial_group==group];ids={a.id for a in agents}
        switches=[e for e in changes if e['payload']['agent'] in ids]
        def uniq(events):return len({e['payload']['agent'] for e in events if e['payload']['agent'] in ids})
        trusts=[v for a in agents for v in a.behavior['trust'].values()]
        inc=[sum(e['target']==a.id for e in sim.edges) for a in agents]
        out=[sum(e['source']==a.id for e in sim.edges) for a in agents]
        probe=[a.beliefs.get('audit:policy',{}).get('estimate',50.)-50 for a in agents if a.id in p['targets']]
        groups.append({'id':run_id,'case':p['case']['name'],'family':p['case']['family'],'model':p['model'],
            'seed':p['seed'],'population':p['population'],'days':p['days'],'group':group,'n':len(agents),
            'ever_changed':len({e['payload']['agent'] for e in switches}),'switches':len(switches),
            'returns':sum(e['payload']['diagnostic']['returning'] for e in switches),
            'first_switch_day':min((e['time']/1440 for e in switches),default=None),
            'withdrawn':uniq(withdrawn),'attended':uniq(attendance),'expressed':uniq(expressions),
            'final_A':sum(a.alignment=='A' for a in agents),'final_B':sum(a.alignment=='B' for a in agents),
            'final_none':sum(a.alignment=='none' for a in agents),'mean_loyalty':statistics.mean(a.private_loyalty for a in agents),
            'mean_harm':statistics.mean(a.behavior['harm'] for a in agents),
            'mean_burden':statistics.mean(a.behavior['burden'] for a in agents),
            'mean_savings':statistics.mean(a.savings for a in agents),'negative_savings':sum(a.savings<0 for a in agents),
            'losses':sum(a.losses for a in agents),'mean_core':statistics.mean(a.behavior['core_orientation'] for a in agents),
            'core_changes':sum(a.behavior['core_changes'] for a in agents),
            'mean_trust':statistics.mean(trusts) if trusts else None,
            'read_events':sum(e['payload']['agent'] in ids for e in read_events),
            'mean_in_degree':statistics.mean(inc),'mean_out_degree':statistics.mean(out),
            'probe_view_delta':statistics.mean(probe) if probe else None,
            'mean_history_harm':statistics.mean(history[group]['harm']),
            'mean_history_burden':statistics.mean(history[group]['burden'])})
    rejected=[e for e in sim.log if e['kind']=='action_rejected']
    row={'id':run_id,'case':p['case']['name'],'family':p['case']['family'],'model':p['model'],'seed':p['seed'],
        'population':p['population'],'days':p['days'],'initial_world_hash':p['initial_world_hash'],
        'profile_hash':p['profile_hash'],'ever_changed':len({e['payload']['agent'] for e in changes}),
        'switches':len(changes),'withdrawn':len({e['payload']['agent'] for e in withdrawn}),
        'attended':len({e['payload']['agent'] for e in attendance}),
        'expressed':len({e['payload']['agent'] for e in expressions}),
        'core_changes':sum(g['core_changes'] for g in groups),'losses':sum(g['losses'] for g in groups),
        'rejected':len(rejected),'imposed_rejected':sum(not v['accepted'] for v in p['input_outcomes']),
        'negative_savings':sum(g['negative_savings'] for g in groups),
        'read_events':len(read_events),'transitions_accessible':all(evidence_checks),
        'closed_gatherings_clear':all(not g['participants'] for g in getattr(sim,'gatherings',{}).values() if g['end']<=sim.time),
        'solo_expression_errors':sum(e['payload']['collective_active'] and len(e['payload']['visible_participants'])<2 for e in sim.log if e['kind']=='collective_observation'),
        'frozen_traits':all(a.traits==a.initial_traits for a in sim.agents.values()),
        'final_A':sum(g['final_A'] for g in groups),'final_B':sum(g['final_B'] for g in groups),
        'final_none':sum(g['final_none'] for g in groups)}
    return row,groups


def run_case(case,seed=0,population=100,model='v3.1',days=30,raw_root=RAW):
    sim=setup(case,seed,population,model,days)
    rid=f"{case['name']}-n{population}-s{seed}-{model}-d{days}"
    folder=raw_root/rid;folder.mkdir(parents=True,exist_ok=True)
    history={g:{'harm':[],'burden':[]} for g in GROUPS}
    started=time.perf_counter()
    with gzip.open(folder/'daily.jsonl.gz','wt') as f:
        for day in range(days):
            advance(sim,(day+1)*1440-1)
            rows=list(observations(sim,day))
            for r in rows:
                f.write(json.dumps(r,separators=(',',':'))+'\n')
                history[r['group']]['harm'].append(r['harm']);history[r['group']]['burden'].append(r['burden'])
    row,groups=extract(sim,rid,history)
    trace={'protocol':sim.protocol['character_study'],'final_agents':{k:asdict(a) for k,a in sim.agents.items()},
           'messages':sim.messages,'decisions':sim.decisions,'gatherings':getattr(sim,'gatherings',{}),
           'log':[e for e in sim.log if e['kind'] not in ('behavior_updated','behavior')],
           'end_time':sim.time}
    with gzip.open(folder/'trace.json.gz','wt') as f:json.dump(trace,f,separators=(',',':'))
    if seed==0:
        path=folder/'state.json';sim.save(path)
        with gzip.open(folder/'state.json.gz','wb',compresslevel=1) as gz:gz.write(path.read_bytes())
        path.unlink()
    row['wall_seconds']=time.perf_counter()-started
    files={str(p):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(folder.iterdir())}
    return {'run':row,'groups':groups,'files':files}


def jobs():
    cases=catalog();by={c['name']:c for c in cases}
    for case in cases:
        for seed in range(8):yield case,seed,100,'v3.1',30
    for name in ('none','sudden60','severe80','ramp60','i80-A-positive','i80-unknown-known'):
        for model in ('v2','v3.0'):
            for seed in range(4):yield by[name],seed,100,model,30
    for name in ('sudden60','ramp60','i80-A-positive','crowd-none'):
        for seed in range(2):yield by[name],seed,1000,'v3.1',30
    for name in ('severe80','i80-A-positive','i80-unknown-positive','contract-repeat'):
        for seed in range(3):yield by[name],seed,100,'v3.1',180


def csv_write(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    OUT.mkdir(parents=True,exist_ok=True);RAW.mkdir(parents=True,exist_ok=True)
    specs=list(jobs())
    protocol={'date':'2026-10-25','purpose':'fixed character acceptance study, not calibrated social prediction',
        'model_sources':source_hashes(),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'cases':catalog(),'jobs':[dict(case=c['name'],seed=s,population=n,model=m,days=d) for c,s,n,m,d in specs],
        'notes':['Only source probes add a controlled common network; other families retain original topology.',
        'Source probes use Wait to isolate read-time rules; forced crowd cases use Wait. Other runs use reference autonomous policy.',
        'Same-endpoint early/ramp shocks have different cumulative costs. late_equal_cost60 matches ramp cumulative daily price excess at day 30.',
        'Positive benefit and responsibility messages are testimony, not objective truth.',
        'Daily observations are sampled at actual day-end; subdaily gatherings are measured from their event logs.',
        'Historical profiles differ in state schema; world hashes cover common physical/personality initialization only.',
        'Macro power-reversal is intentionally unannounced; agents must not react to hidden world power.',
        'No behavior coefficients changed; zero core change in v3.1 is deliberately frozen, not validated ideological realism.']}
    pp=OUT/'protocol.json'
    if pp.exists():assert json.loads(pp.read_text())==protocol,'Protocol changed; do not mix studies'
    else:pp.write_text(json.dumps(protocol,indent=2))
    completed=OUT/'completed.jsonl'
    done=[json.loads(x) for x in completed.read_text().splitlines()] if completed.exists() else []
    ids={r['run']['id'] for r in done}
    started=time.perf_counter()
    for case,seed,n,model,days in specs:
        rid=f"{case['name']}-n{n}-s{seed}-{model}-d{days}"
        if rid in ids:continue
        print(f"START {len(done)+1}/{len(specs)} {rid}",flush=True)
        try:result=run_case(case,seed,n,model,days)
        except Exception as exc:
            with (OUT/'failures.jsonl').open('a') as f:f.write(json.dumps({'id':rid,'error':repr(exc)})+'\n')
            raise
        with completed.open('a') as f:f.write(json.dumps(result,separators=(',',':'))+'\n')
        done.append(result);ids.add(rid)
        print(f"DONE {rid} switched={result['run']['ever_changed']} withdrawn={result['run']['withdrawn']} attended={result['run']['attended']}",flush=True)
    assert source_hashes()==protocol['model_sources']
    assert len(done)==len(specs)
    csv_write(OUT/'runs.csv',[r['run'] for r in done]);csv_write(OUT/'groups.csv',[g for r in done for g in r['groups']])
    (OUT/'execution.json').write_text(json.dumps({'completed':len(done),'expected':len(specs),'model_sources_unchanged':True,'last_invocation_seconds':time.perf_counter()-started,'raw_files':sum(len(r['files']) for r in done),'status':'complete'},indent=2))
    print(f"ALL COMPLETE: {len(done)} runs",flush=True)


if __name__=='__main__':main()
