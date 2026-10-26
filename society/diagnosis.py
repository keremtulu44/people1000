"""Frozen-parameter diagnosis. No calibration; one mechanism disabled per arm.

python -m society.diagnosis --seeds 20 --population 100
python -m society.diagnosis --seeds 5 --population 1000
python -m society.diagnosis --legacy
python -m society.diagnosis --report
"""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import time

from .behavior import load_legacy_profile as load_profile
from .engine import Config, Simulation
from .experiments import digest

SHOCKS = {'none':1.,'mild':1.1,'moderate':1.4,'severe':1.8}
ABLATIONS = ('none','economic_evidence','peer','trust_erosion')
ROOT = Path('runs/diagnosis')
OUT = Path('reports/diagnosis')


def write_csv(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else []);w.writeheader();w.writerows(rows)


def summary(values):
    if not values:return {'n':0,'mean':None,'median':None,'min':None,'max':None,'sd':None,'ci95':None}
    avg=statistics.mean(values); sd=statistics.stdev(values) if len(values)>1 else 0.
    return {'n':len(values),'mean':avg,'median':statistics.median(values),'min':min(values),'max':max(values),'sd':sd,
            'ci95':[avg-1.96*sd/len(values)**.5,avg+1.96*sd/len(values)**.5] if len(values)>1 else None}


def setup(seed,population,shock,announcements,ablation='none',peer_probe=False):
    sim=Simulation(Config(population=population,seed=seed,ablation=ablation),load_profile())
    initial_hash=digest({'agents':{k:asdict(a) for k,a in sim.agents.items()},'edges':sim.edges})
    if SHOCKS[shock]!=1.:
        sim.schedule(60,'price_shock',{'multiplier':SHOCKS[shock]},'diagnosis:shock')
    leader=max((x for x in sim.authorities if sim.agents[x].alignment=='A'),key=lambda x:sum(e['source']==x for e in sim.edges))
    recipients=[e['target'] for e in sim.edges if e['source']==leader][:2]
    if announcements:
        for day in (1,8,15,22):
            for target in recipients:
                sim.schedule(day*1440+60,'external_action',{'actor':leader,'proposal':dict(type='send',target=target,
                    text='Beklenen ekonomik zarar yok.',topic='economic_outlook',claim=0)},'diagnosis:forecast')
    if peer_probe:
        edge=next(e for e in sim.edges if sim.agents[e['source']].initial_group=='opposition' and
                  sim.agents[e['target']].initial_group in ('authority','wealthy'))
        for day in (2,9,16,23):
            sim.schedule(day*1440+120,'external_action',{'actor':edge['source'],'proposal':dict(type='send',target=edge['target'],
                text='Kamuya açık destek.',topic='public_support',claim=100)},'diagnosis:peer_probe')
    sim.experiment_id=f'n{population}-s{seed}-{shock}-ann{int(announcements)}-{ablation}'+('-probe' if peer_probe else '')
    return sim,initial_hash


def measure(sim,initial_hash,shock,announcements,ablation,peer_probe):
    changes=[e for e in sim.log if e['kind']=='alignment_changed']
    by_agent=defaultdict(list)
    for e in changes:by_agent[e['payload']['agent']].append(e)
    topic_agents={e['payload']['agent'] for e in sim.log if e['kind']=='belief_updated' and e['payload']['old']!=e['payload']['new']}
    group_rows=[]
    for group in sim.behavior_profile['groups']:
        agents=[a for a in sim.agents.values() if a.initial_group==group]
        ids={a.id for a in agents}; changed=ids & set(by_agent)
        times=[by_agent[x][0]['time']/1440 for x in changed]
        returned={x for x in changed if any(e['payload']['diagnostic']['returning'] for e in by_agent[x])}
        balance=Counter(); eligible_local=Counter()
        for x in changed:
            for e in by_agent[x]:
                d=e['payload']['diagnostic']
                for k,v in d['accumulated_components'].items():balance[k]+=v
                eligible_local['without_authority_message']+=not any(m.get('source_group')=='authority' for m in d['messages_learned'])
                eligible_local['without_any_message']+=not d['messages_learned']
        group_rows.append({'run_id':sim.experiment_id,'population':len(sim.agents),'seed':sim.config.seed,
            'shock':shock,'announcement':int(announcements),'ablation':ablation,'peer_probe':int(peer_probe),'initial_hash':initial_hash,
            'group':group,'agents':len(agents),'switches':sum(len(by_agent[x]) for x in ids),
            'changed_agents':len(changed),'change_rate':len(changed)/len(agents),
            'first_change_mean_days':statistics.mean(times) if times else None,
            'first_change_median_days':statistics.median(times) if times else None,
            'unchanged_censored':len(agents)-len(changed),'returned_agents':len(returned),
            'return_rate_among_changed':len(returned)/len(changed) if changed else None,
            'topic_changed_agents':len(topic_agents&ids),'topic_change_rate':len(topic_agents&ids)/len(agents),
            'mean_strength_gap':statistics.mean(abs(a.public_support-a.private_loyalty) for a in agents),
            'mean_alignment_distance':statistics.mean((abs(a.public_support-a.private_loyalty) if a.public_alignment==a.alignment else a.public_support+a.private_loyalty)/2 for a in agents),
            'core_changed_agents':sum(a.behavior['core_changes']>0 for a in agents),
            'core_change_events':sum(a.behavior['core_changes'] for a in agents),
            'loss_mean':statistics.mean(a.losses for a in agents),'loss_min':min(a.losses for a in agents),'loss_max':max(a.losses for a in agents),
            'evidence_economic':balance['economic'],'evidence_distrust':balance['distrust'],'evidence_peer':balance['peer'],
            'evidence_relief':balance['relief'],'evidence_unattributed':balance['unattributed'],
            'switches_without_authority_message':eligible_local['without_authority_message'],
            'switches_without_any_message':eligible_local['without_any_message']})
    return group_rows,changes


def run(seeds,population,peer_probe=False):
    ROOT.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    profile=load_profile();profile_hash=digest(profile)
    protocol={'version':'diagnosis-1.0','profile':profile,'profile_hash':profile_hash,'days':30,
        'seeds':list(range(seeds)),'population':population,'shocks':SHOCKS,'announcements':[False,True],
        'ablations':list(ABLATIONS),'peer_probe':peer_probe,
        'ablation_semantics':{'economic_evidence':'Remove only economic term in change_evidence. Burden, personal views, private loyalty, core strain remain.',
            'peer':'Disable peer pull accumulation, peer attraction, peer evidence, and peer topic persuasion. Receipt and authority forecasts remain.',
            'trust_erosion':'Clamp only negative trust update delta to zero. Initial distrust and recovery remain.'},
        'primary':'100 agents, 20 paired seeds, all 32 conditions; 1000 agents 5 seeds exploratory scaling validation',
        'limitations':'Ablations measure total counterfactual effect, not additive causal shares. Interactions and endogenous alignment affect later own-trust selection.',
        'no_parameter_calibration':True}
    label=f'n{population}'+('-probe' if peer_probe else '')
    (OUT/f'protocol-{label}.json').write_text(json.dumps(protocol,indent=2))
    rows=[];runs=[];start=time.perf_counter()
    conditions=[('severe',True,a) for a in ('none','peer')] if peer_probe else [(s,ann,a) for s in SHOCKS for ann in (False,True) for a in ABLATIONS]
    for seed in range(seeds):
        expected_hash=None
        for shock,ann,ablation in conditions:
            sim,initial_hash=setup(seed,population,shock,ann,ablation,peer_probe)
            if expected_hash is None:expected_hash=initial_hash
            assert initial_hash==expected_hash,'Ablation changed initial world'
            sim.protocol['diagnosis']=protocol
            started=time.perf_counter();sim.run(30*1440-1,max_events=population*30*6)
            group_rows,changes=measure(sim,initial_hash,shock,ann,ablation,peer_probe)
            directory=ROOT/sim.experiment_id;directory.mkdir(exist_ok=True)
            with gzip.open(directory/'transitions.jsonl.gz','wt') as f:
                for e in changes:f.write(json.dumps(e,ensure_ascii=False)+'\n')
            # Retain full snapshots for seed 0, all conditions; every other run has
            # complete switch diagnostics and final agent summaries + reproducible protocol.
            if seed==0:
                sim.save(directory/'state.json')
                with (directory/'state.json').open('rb') as src,gzip.open(directory/'state.json.gz','wb',compresslevel=1) as dest:
                    for block in iter(lambda:src.read(1024*1024),b''):dest.write(block)
                (directory/'state.json').unlink()
            with gzip.open(directory/'agents.json.gz','wt') as f:
                json.dump([asdict(a) for a in sim.agents.values()],f)
            rows.extend(group_rows)
            runs.append({'run_id':sim.experiment_id,'population':population,'seed':seed,'shock':shock,'announcement':int(ann),
                'ablation':ablation,'peer_probe':int(peer_probe),'initial_hash':initial_hash,'switches':len(changes),
                'changed_agents':sum(r['changed_agents'] for r in group_rows),
                'wall_seconds':time.perf_counter()-started,'transition_file':str(directory/'transitions.jsonl.gz'),
                'evidence_arithmetic_max_error':max((abs(sum(e['payload']['diagnostic']['accumulated_components'].values())-e['payload']['accumulated_evidence']) for e in changes),default=0.)})
            print(f'{len(runs)} completed {sim.experiment_id}: {len(changes)} switches',flush=True)
            del sim
        write_csv(OUT/f'groups-{label}.csv',rows);write_csv(OUT/f'runs-{label}.csv',runs)
    assert digest(load_profile())==profile_hash
    (OUT/f'execution-{label}.json').write_text(json.dumps({'completed_runs':len(runs),'wall_seconds':time.perf_counter()-start,
        'profile_hash_before':profile_hash,'profile_hash_after':digest(load_profile()),'exit_status':'complete'},indent=2))


def legacy():
    ROOT.mkdir(exist_ok=True,parents=True);OUT.mkdir(exist_ok=True,parents=True)
    rows=list(csv.DictReader(open('reports/behavior-experiment-results.csv')))
    counts=Counter();run_rows=[];sample=[]
    with gzip.open(ROOT/'legacy-transitions.jsonl.gz','wt') as dest:
        for row in rows:
            with gzip.open(row['artifact'],'rt') as f:data=json.load(f)
            # behavior_updated is emitted AFTER a switch in the SAME handler, but
            # its loyalty_before field explicitly records a prior value, not future evidence.
            daily={(e['caused_by'],e['payload'].get('agent')):e['payload'] for e in data['log'] if e['kind']=='behavior_updated'}
            last_core={};trust_history=defaultdict(list);read=defaultdict(set);previous={}; local=0
            for e in data['log']:
                p=e['payload'];aid=p.get('agent')
                if e['kind']=='core_orientation_changed':last_core[aid]=p['new']
                if e['kind']=='social_observation':read[aid].add(p['message_id'])
                if e['kind']=='trust_updated':trust_history[aid].append({'time':e['time'],'event_id':e['id'],**p})
                if e['kind']!='alignment_changed':continue
                a=data['agents'][aid];recorded=daily.get((e['caused_by'],aid),{})
                memories=[m for m in a['memories'] if m.get('message_id') in read[aid]]
                entry={'run_id':data['experiment_id'],'agent':aid,'time':e['time'],'log_id':e['id'],'cause_event_id':e['caused_by'],
                    'initial_group':a['initial_group'],'recorded_transition':p,'recorded_private_loyalty_before':recorded.get('loyalty_before'),
                    'recorded_harm':recorded.get('harm'),'learned_authority_messages':[{k:v for k,v in m.items() if k!='text'} for m in memories if m.get('source_group')=='authority'],
                    'recorded_trust_updates_before':list(trust_history[aid]),'last_recorded_core_orientation':last_core.get(aid),
                    'elapsed_since_previous_switch_days':(e['time']-previous[aid]['time'])/1440 if aid in previous else None,
                    'returning_derived_from_transition_sequence':aid in previous and p['new']==previous[aid]['payload']['old'],
                    'missing':['pre-switch public support/alignment snapshot','complete pre-switch private topic state','full initial trust map',
                               'economic exposure summary','accumulated component decomposition','explicit peer and pressure snapshot'],
                    'availability':'Recorded fields only; absent past states are null/missing, not replaced by final state.'}
                previous[aid]=e
                dest.write(json.dumps(entry)+'\n');local+=1
                counts['transitions']+=1;counts['without_authority_message']+=not entry['learned_authority_messages']
                counts['loyalty_before_available']+=entry['recorded_private_loyalty_before'] is not None
                if len(sample)<12:sample.append(entry)
            run_rows.append({'run_id':data['experiment_id'],'population':len(data['agents']),'transitions':local})
    write_csv(OUT/'legacy-runs.csv',run_rows)
    (OUT/'legacy-audit.json').write_text(json.dumps({'runs_inspected':len(rows),'counts':dict(counts),'sample':sample,
        'all_transition_records':str(ROOT/'legacy-transitions.jsonl.gz')},indent=2))
    print(json.dumps({'runs':len(rows),'counts':dict(counts)}))


def report():
    from .diagnosis_report import build
    build()


def main():
    p=argparse.ArgumentParser();p.add_argument('--legacy',action='store_true');p.add_argument('--report',action='store_true')
    p.add_argument('--seeds',type=int,default=20);p.add_argument('--population',type=int,default=100);p.add_argument('--peer-probe',action='store_true')
    args=p.parse_args()
    if args.seeds < 1:
        p.error("--seeds must be positive")
    if args.legacy:legacy()
    elif args.report:report()
    else:run(args.seeds,args.population,args.peer_probe)


if __name__=='__main__':main()
