"""Declared exploratory follow-up: directional coverage, not outcome tuning.

Main study remains immutable. Reuses its observation/extraction definitions;
adds mirrored B, simultaneous campaigns and historical dose-matched controls.
"""
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import time

from .character_study import (catalog,setup,advance,observations,extract,source_hashes,digest,GROUPS,OUT,RAW,csv_write)

FOLLOW=OUT/'followup'


def specifications():
    by={c['name']:c for c in catalog()}
    specs=[]
    for price in (40,80):
        for blame in ('A','unknown'):
            for benefit in ('known','positive'):
                for seed in range(8):specs.append((by[f'i{price}-{blame}-{benefit}'],seed,'mirror','v3.1'))
        for blame in ('A','unknown'):
            for seed in range(8):specs.append((by[f'i{price}-{blame}-positive'],seed,'dual','v3.1'))
    for model in ('v2','v3.0'):
        for seed in range(4):specs.append((by['late_equal_cost60'],seed,'dose','v2' if model=='v2' else 'v3.0'))
    return specs


def prepared(case,seed,mode,model):
    sim=setup(case,seed,100,model,30);p=sim.protocol['character_study']
    if mode in ('mirror','dual'):
        old=p['anchors'];original=deepcopy(p['plan'])
        candidates={x:[e['target'] for e in sim.edges if e['source']==x and sim.agents[e['target']].public_alignment=='B']
                    for x in sim.authorities if sim.agents[x].public_alignment=='B'}
        leader=max(candidates,key=lambda x:len(candidates[x]));anchors=candidates[leader][:2];assert len(anchors)==2
        mapped=[]
        for item in original:
            if item['kind']!='action':continue
            item=deepcopy(item);item['actor']=leader
            prop=item['proposal'];prop['target']=anchors[old.index(prop['target'])]
            for field in ('topic','text'):
                value=prop[field]
                if value=='responsibility:A':value='responsibility:B'
                elif value.startswith('benefit:B:'):value=value.replace('benefit:B:','benefit:A:',1)
                elif value=='alternative_known:B':value='alternative_known:A'
                prop[field]=value
            mapped.append(item)
        p['plan']=([x for x in original if x['kind']!='action']+mapped) if mode=='mirror' else original+mapped
        p['plan'].sort(key=lambda x:x['at'])
        p['original_A_anchors']=old;p['B_anchors']=anchors
    p['case']={**case,'name':mode+'-'+case['name'],'followup_mode':mode}
    p['exploratory_followup']='Directional and dose coverage after main descriptive results; not an independent confirmation.'
    return sim


def run(sim):
    p=sim.protocol['character_study'];rid=f"{p['case']['name']}-n100-s{p['seed']}-{p['model']}-d30"
    folder=RAW/rid;folder.mkdir(parents=True,exist_ok=True);started=time.perf_counter()
    history={g:{'harm':[],'burden':[]} for g in GROUPS}
    with gzip.open(folder/'daily.jsonl.gz','wt') as f:
        for day in range(30):
            advance(sim,(day+1)*1440-1)
            for row in observations(sim,day):
                f.write(json.dumps(row,separators=(',',':'))+'\n')
                history[row['group']]['harm'].append(row['harm']);history[row['group']]['burden'].append(row['burden'])
    row,groups=extract(sim,rid,history);row['wall_seconds']=time.perf_counter()-started
    trace={'protocol':p,'final_agents':{k:asdict(a) for k,a in sim.agents.items()},'messages':sim.messages,
           'decisions':sim.decisions,'gatherings':getattr(sim,'gatherings',{}),
           'log':[e for e in sim.log if e['kind'] not in ('behavior_updated','behavior')],'end_time':sim.time}
    with gzip.open(folder/'trace.json.gz','wt') as f:json.dump(trace,f,separators=(',',':'))
    if p['seed']==0:
        path=folder/'state.json';sim.save(path)
        with gzip.open(folder/'state.json.gz','wb',compresslevel=1) as f:f.write(path.read_bytes())
        path.unlink()
    return {'run':row,'groups':groups,'files':{str(x):{'bytes':x.stat().st_size,'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in sorted(folder.iterdir())}}


def main():
    FOLLOW.mkdir(parents=True,exist_ok=True)
    specs=specifications();protocol={'sources':source_hashes(),'followup_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'reason':'Main political exposure was A-directed. Add B-mirrors and simultaneous campaigns; complete legacy equal-cost comparison.',
        'notes':['Exploratory, specified after main results, not a blind preregistration.',
                 'Original graph retained. A/B roots have different reach, so mirror differences are not pure group-parameter effects.',
                 'Dual treatment doubles campaign inputs (two distinct authorities), not fixed per-population messaging dose.'],
        'jobs':[{'base':c['name'],'seed':s,'mode':m,'model':v} for c,s,m,v in specs]}
    path=FOLLOW/'protocol.json'
    if path.exists():assert json.loads(path.read_text())==protocol
    else:path.write_text(json.dumps(protocol,indent=2))
    file=FOLLOW/'completed.jsonl';done=[json.loads(x) for x in file.read_text().splitlines()] if file.exists() else []
    ids={r['run']['id'] for r in done}
    for c,seed,mode,model in specs:
        rid=f"{mode}-{c['name']}-n100-s{seed}-{model}-d30"
        if rid in ids:continue
        result=run(prepared(c,seed,mode,model))
        with file.open('a') as f:f.write(json.dumps(result,separators=(',',':'))+'\n')
        done.append(result);ids.add(rid)
        print(f"{len(done)}/{len(specs)} {rid}: {result['run']['ever_changed']} changed",flush=True)
    assert len(done)==len(specs) and protocol['sources']==source_hashes()
    csv_write(FOLLOW/'runs.csv',[x['run'] for x in done]);csv_write(FOLLOW/'groups.csv',[g for x in done for g in x['groups']])
    (FOLLOW/'execution.json').write_text(json.dumps({'runs':len(done),'sources_unchanged':True,'status':'complete'},indent=2))


if __name__=='__main__':main()
