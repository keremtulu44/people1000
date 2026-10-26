"""Predeclared paired experiments. Offline, deterministic, no AI calls.

python -m society.experiments --seeds 20 --populations 100 1000 --days 30
Artifacts are compressed snapshots under runs/, never committed datasets.
"""
from collections import Counter, defaultdict, deque
from copy import deepcopy
from dataclasses import asdict
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import resource
import statistics
import time

from .behavior import load_legacy_profile as load_profile
from .engine import Config, Simulation

PROTOCOL = {
    "experiment_version": "1.1.0", "arms": {
        "A": "shock only", "B": "shock plus accessible authority forecasts",
        "C": "B with forecasts restricted to a BFS network region",
        "D": "B with cumulative dynamics disabled",
        "erosion_fast": "B; trust_erosion doubled",
        "threshold_low": "B; alignment threshold range [.55,.65] except observers",
        "observer_less_resistant": "B; observer core resistance .95 rather than .999",
        "pressure": "B; one scoped pressure action on day 10",
        "recovery": "B; accurate .8 harm forecast from day 22 onwards"},
    "shock_minute": 60, "shock_multiplier": 1.8,
    "announcement_days": [1, 8, 15, 22], "announcement_offset_minutes": 60,
    "forecast_claim": 0, "forecast_meaning": "expected personal normalized excess cost/income harm",
    "sample_size_primary": 20, "days_primary": 30,
    "success": "causal local updates, bounds, replay; not a political outcome",
    "regions": "BFS connected subgraph seeded with two initial recipients, at most n/4 nodes",
    "randomness": "Only initialization consumes RNG; runtime policies and shocks are deterministic",
    "interpretation": "Uncalibrated model; intervals describe variation over seeds, not real society"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def region(sim, seeds):
    # Undirected traversal only to DEFINE the experiment's region. Deliveries still
    # follow the original directed edges; no extra communication paths are created.
    graph = defaultdict(set)
    for e in sim.edges:
        graph[e['source']].add(e['target']); graph[e['target']].add(e['source'])
    q, seen = deque(seeds), set(seeds)
    while q and len(seen) < len(sim.agents)//4:
        for x in sorted(graph[q.popleft()]):
            if len(seen) >= len(sim.agents)//4: break
            if x not in seen: seen.add(x); q.append(x)
    return sorted(seen)


def make_run(seed, population, arm, days=30, artifact_root=None, profile=None, stop_at=None):
    started = time.perf_counter()
    profile = deepcopy(profile or load_profile())
    if arm == 'erosion_fast': profile['dynamics']['trust_erosion'] *= 2
    if arm == 'threshold_low':
        for name, g in profile['groups'].items():
            if name != 'observer': g['parameters']['alignment_change_threshold'] = [.55,.65]
    if arm == 'observer_less_resistant':
        profile['groups']['observer']['parameters']['core_orientation_resistance'] = [.95,.95]
    sim = Simulation(Config(population=population,seed=seed,cumulative_enabled=arm!='D'),profile)
    sim.experiment_id = f'n{population}-s{seed}-{arm}-d{days}'
    initial_hash = digest({'agents':{k:asdict(a) for k,a in sim.agents.items()}, 'edges':sim.edges})
    sim.protocol['experiment'] = {**PROTOCOL,'id':sim.experiment_id,'arm':arm,'seed':seed,
                                  'days':days,'initial_hash':initial_hash}
    sim.schedule(60,'price_shock',{'multiplier':1.8},'experiment:shock')
    leader = max((x for x in sim.authorities if sim.agents[x].alignment=='A'),
                 key=lambda x:len([e for e in sim.edges if e['source']==x]))
    recipients = [e['target'] for e in sim.edges if e['source']==leader][:2]
    scope = region(sim,recipients) if arm=='C' else None
    interventions=[]
    if arm!='A':
        for day in PROTOCOL['announcement_days']:
            if day < days:
                interventions.append((day*1440+60,'announcement',day))
    if arm=='pressure' and days>10: interventions.append((10*1440+120,'pressure',10))
    for minute,kind,day in sorted(interventions):
        if kind=='announcement':
            for target in recipients:
                sim.schedule(minute, 'external_action', {'actor':leader, 'proposal':dict(type='send',target=target,
                    text='Beklenen kişisel ekonomik zarar açıklaması.',topic='economic_outlook',
                    claim=80 if arm=='recovery' and day>=22 else 0,audience=scope)}, 'experiment:announcement')
        else:
            target=next(a for a in sim.agents.values() if a.authority_dependency)
            sim.schedule(minute, 'external_action', {'actor':target.authority_dependency,
                'proposal':dict(type='pressure',target=target.id)}, 'experiment:pressure')
    sim.run(days*1440-1 if stop_at is None else stop_at, max_events=max(100000, days*population*5))
    elapsed=time.perf_counter()-started
    row, details = measure(sim, initial_hash, elapsed, scope)
    row['arm']=arm;row['days']=days
    if artifact_root:
        directory=Path(artifact_root)/sim.experiment_id
        directory.mkdir(parents=True,exist_ok=True)
        raw=directory/'state.json';sim.save(raw)
        row['snapshot_bytes']=raw.stat().st_size
        # mtime=0 avoids compression timestamps; contents can be compared by hash.
        with raw.open('rb') as src, (directory/'state.json.gz').open('wb') as dest:
            with gzip.GzipFile(filename='',fileobj=dest,mode='wb',mtime=0,compresslevel=1) as compressed:
                for block in iter(lambda:src.read(1024*1024),b''): compressed.write(block)
        raw.unlink()
        row['compressed_bytes']=(directory/'state.json.gz').stat().st_size
        row['artifact']=str(directory/'state.json.gz')
        (directory/'metrics.json').write_text(json.dumps({'row':row,'details':details},indent=2))
    return sim,row,details


def measure(sim, initial_hash, elapsed, scope):
    agents=list(sim.agents.values()); n=len(agents)
    kinds=Counter(e['kind'] for e in sim.log)
    learned=defaultdict(dict)
    for a in agents:
        for m in a.memories:
            if 'message_id' in m: learned[a.id][m['message_id']]=m['learned_at']
    message_recipients={a.id for a in agents if learned[a.id]}
    leak=[]
    for e in sim.log:
        if e['kind'] in ('trust_updated','social_observation'):
            p=e['payload'];mid=p.get('message_id',p.get('evidence'))
            if mid not in learned[p['agent']] or learned[p['agent']][mid]>e['time']:
                leak.append(e['id'])
        elif e['kind']=='belief_updated' and e['payload'].get('message_id'):
            p=e['payload'];mid=p['message_id']
            if learned[p['agent']].get(mid, float('inf'))>e['time']: leak.append(e['id'])
    reach_by_region={}
    for i in range(4):
        times=[t-sim.messages[mid]['created_at'] for aid,mem in learned.items() if int(aid[1:])%4==i for mid,t in mem.items()]
        reach_by_region[str(i)]={'first_minutes':min(times) if times else None,
            'median_minutes':statistics.median(times) if times else None,'read_count':len(times)}
    switches=[e for e in sim.log if e['kind']=='alignment_changed']
    beliefs=[e for e in sim.log if e['kind']=='belief_updated' and e['payload']['old']!=e['payload']['new']]
    trust=[e for e in sim.log if e['kind']=='trust_updated']
    trust_by_pair=defaultdict(list)
    for e in trust: trust_by_pair[(e['payload']['agent'],e['payload']['source'])].append(e)
    recoveries=[]; censored=0
    for events in trust_by_pair.values():
        first=next((e for e in events if e['payload']['new']<e['payload']['old']),None)
        if first:
            restored=next((e for e in events if e['time']>first['time'] and e['payload']['new']>=first['payload']['old']),None)
            if restored: recoveries.append((restored['time']-first['time'])/1440)
            else:censored+=1
    economic_errors=[]
    for a in agents:
        if 'economic_outlook' in a.beliefs:
            real=min(1.,max(0.,sim.price-1)+max(0.,a.behavior['reference_income']-a.income)/max(1.,a.behavior['reference_income']))
            economic_errors.append(abs(a.beliefs['economic_outlook']['estimate']/100-real))
    pressure=[e for e in sim.log if e['kind']=='pressure_experienced']
    actions=Counter(e['payload']['actor'] for e in sim.log if e['kind']=='action_applied' and e['payload']['type']!='wait')
    communications=Counter(e['payload']['actor'] for e in sim.log if e['kind']=='action_applied' and e['payload']['type'] in ('send','relay'))
    row={'experiment_id':sim.experiment_id,'population':n,'seed':sim.config.seed,
         'behavior_version':sim.behavior_profile['behavior_version'],'initial_hash':initial_hash,
         'wall_seconds':elapsed,'events':sum(e['event_id'] is not None for e in sim.log),
         'log_records':len(sim.log),'memory_records':sum(len(a.memories) for a in agents),
         'events_per_agent_day':sum(e['event_id'] is not None for e in sim.log)/(n*len(sim.daily_metrics)),
         'messages':len(sim.messages),'deliveries':kinds['delivery'],'reads':sum(len(x) for x in learned.values()),
         'reached_agents':len(message_recipients),'unreached_agents':n-len(message_recipients),
         'leaks':len(leak),'scope_violations':sum(a not in scope for a in message_recipients) if scope else 0,
         'alignment_changes':len(switches),'alignment_changed_agents':len({e['payload']['agent'] for e in switches}),
         'alignment_change_rate':len({e['payload']['agent'] for e in switches})/n,
         'topic_changes':len(beliefs),'topic_changed_agents':len({e['payload']['agent'] for e in beliefs}),
         'core_changes':kinds['core_orientation_changed'],
         'trust_erosions':sum(e['payload']['new']<e['payload']['old'] for e in trust),
         'trust_recoveries':sum(e['payload']['new']>e['payload']['old'] for e in trust),
         'fully_recovered_pairs':len(recoveries),'recovery_censored_pairs':censored,
         'mean_recovery_days':statistics.mean(recoveries) if recoveries else None,
         'perception_error':statistics.mean(economic_errors) if economic_errors else None,
         'perception_sample_count':len(economic_errors),
         'rejected_actions':kinds['action_rejected'],'budget_blocked_decisions':kinds['decision_budget_blocked'],
         'pressure_actions':len(pressure),'rss_process_peak_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
         'unreached_switches':len({e['payload']['agent'] for e in switches}-message_recipients),
         **sim.behavior_metrics()}
    details={'events_by_kind':dict(kinds),'region_latency':reach_by_region,'leak_event_ids':leak,
             'losses_by_group':{g: [a.losses for a in agents if a.initial_group==g] for g in sim.behavior_profile['groups']},
             'actions_per_agent':{a.id:actions[a.id] for a in agents},
             'communications_per_agent':{a.id:communications[a.id] for a in agents},
             'pressure_events':pressure,'daily':sim.daily_metrics,
             'switch_times':[e['time'] for e in switches],
             'trust_recovery_days':recoveries,'scope':scope,
             'unreached_topic_changes':sum(e['payload']['agent'] not in message_recipients for e in beliefs)}
    return row,details


def aggregate(rows):
    result={}
    numeric=['wall_seconds','events','reads','reached_agents','alignment_changes','core_changes',
             'trust_erosions','trust_recoveries','mean_support_gap','mean_private_loyalty','perception_error',
             'losses','memory_records','snapshot_bytes','compressed_bytes','leaks','unreached_switches']
    for key in sorted({(r['population'],r['arm']) for r in rows}):
        subset=[r for r in rows if (r['population'],r['arm'])==key]
        stats={}
        for name in numeric:
            values=[r[name] for r in subset if r.get(name) is not None]
            if not values: continue
            sd=statistics.stdev(values) if len(values)>1 else 0.
            avg=statistics.mean(values)
            stats[name]={'n':len(values),'mean':avg,'median':statistics.median(values),'min':min(values),'max':max(values),
                         'sd':sd,'normal_approx_95ci':[avg-1.96*sd/len(values)**.5,avg+1.96*sd/len(values)**.5] if len(values)>1 else None}
        result[f'{key[0]}:{key[1]}']=stats
    paired={}
    by={(r['population'],r['seed'],r['arm']):r for r in rows}
    for pop in sorted({r['population'] for r in rows}):
        for arm,control in [('B','A'),('C','B'),('D','B'),('erosion_fast','B'),('threshold_low','B'),('observer_less_resistant','B'),('pressure','B'),('recovery','B')]:
            differences=defaultdict(list)
            for seed in sorted({r['seed'] for r in rows}):
                r=by.get((pop,seed,arm)); c=by.get((pop,seed,control))
                if r and c:
                    for name in ['alignment_changes','reached_agents','mean_private_loyalty','mean_support_gap','trust_erosions','core_changes']:
                        differences[name].append(r[name]-c[name])
            if differences:
                paired[f'{pop}:{arm}-{control}']={k:{'n':len(v),'mean':statistics.mean(v),'median':statistics.median(v),
                     'positive':sum(x>0 for x in v),'zero':sum(x==0 for x in v),'negative':sum(x<0 for x in v),
                     'normal_approx_95ci': [statistics.mean(v)-1.96*statistics.stdev(v)/len(v)**.5,statistics.mean(v)+1.96*statistics.stdev(v)/len(v)**.5] if len(v)>1 else None} for k,v in differences.items()}
    return {'groups':result,'paired':paired}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--seeds',type=int,default=20)
    p.add_argument('--populations',type=int,nargs='+',default=[100,1000])
    p.add_argument('--days',type=int,default=30)
    p.add_argument('--sensitivity',action='store_true',help='Add five supplemental arms for population 100')
    p.add_argument('--output',default='reports')
    p.add_argument('--artifacts',default='runs/behavior')
    args=p.parse_args()
    if args.seeds<1 or args.days<1:p.error('positive seeds and days required')
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    (out/'behavior-protocol.json').write_text(json.dumps({**PROTOCOL,'actual_seeds':list(range(args.seeds)),
        'actual_days':args.days,'populations':args.populations,'profile':load_profile()},indent=2))
    rows=[];started=time.perf_counter()
    for pop in args.populations:
        arms=['A','B','C','D']
        if args.sensitivity and pop==100: arms+=['erosion_fast','threshold_low','observer_less_resistant','pressure','recovery']
        for seed in range(args.seeds):
            for arm in arms:
                sim,row,details=make_run(seed,pop,arm,args.days,args.artifacts)
                rows.append(row)
                del sim,details
                print(f'completed {len(rows)}: {pop} seed={seed} arm={arm} {row["wall_seconds"]:.3f}s',flush=True)
            # Incremental CSV survives interruption; summaries always state actual count.
            fields=list(dict.fromkeys(k for r in rows for k in r))
            with (out/'behavior-experiment-results.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    results={'completed_runs':len(rows),'total_wall_seconds':time.perf_counter()-started,
             'protocol_hash':digest(json.loads((out/'behavior-protocol.json').read_text())),**aggregate(rows)}
    (out/'behavior-metrics.json').write_text(json.dumps(results,indent=2,allow_nan=False))
    print(json.dumps({'completed_runs':len(rows),'wall_seconds':results['total_wall_seconds']}),flush=True)


if __name__=='__main__':main()
