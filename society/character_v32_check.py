"""Small reproducible v3.1/v3.2 regression comparison, not empirical validation.

Run: python -m society.character_v32_check
Only compact evidence is retained; historical study archives are not overwritten.
"""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from .behavior import load_v32_profile as load_profile, load_v31_profile
from .engine import Config, Simulation


def frozen_replay(root):
    archive=root/'reports/character-study/frozen-source.zip'
    code='''from pathlib import Path
import hashlib
from society.engine import Simulation
try:
 from society.behavior import load_v31_profile as profile
except ImportError:
 from society.behavior import load_profile as profile
s=Simulation(behavior_profile=profile())
s.schedule(1,'price_shock',{'multiplier':1.6})
leader=next(iter(s.authorities))
target=next(e['target'] for e in s.edges if e['source']==leader)
s.schedule(2,'external_action',{'actor':leader,'proposal':{'type':'send','target':target,'text':'forecast','topic':'economic_outlook','claim':0}})
s.run(10*1440)
s.save('replay.json')
print(hashlib.sha256(Path('replay.json').read_bytes()).hexdigest())
'''
    (root/'runs').mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root/'runs') as td:
        td=Path(td);old=td/'frozen';old.mkdir()
        with zipfile.ZipFile(archive) as z:
            z.extractall(old)
            profile_identical=z.read('society/behavior.json')==(root/'society/behavior-v31.json').read_bytes()
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
        def replay(cwd,pythonpath):
            return subprocess.check_output([sys.executable,'-c',code],cwd=cwd,
                env={**env,'PYTHONPATH':str(Path(pythonpath).resolve())},text=True).strip()
        previous=replay(old,old)
        current=td/'current';current.mkdir();now=replay(current,root)
    return {'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
            'profile_bytes_identical':profile_identical,'frozen_snapshot_sha256':previous,
            'current_v31_snapshot_sha256':now,'exact_snapshot_match':previous==now,
            'scope':'100 agents, seed 44, 10 days, price shock + locally delivered forecast, baseline provider'}


def probe(seed,model,case):
    sim=Simulation(Config(seed=seed),load_v31_profile() if model=='v3.1' else load_profile())
    for day in ([90] if case.endswith('sudden') else range(1,91)):
        if case.startswith('price'):
            multiplier=1.3 if case.endswith('sudden') else (1+.3*day/90)/(1+.3*(day-1)/90)
            sim.schedule(day*1440+1,'price_shock',{'multiplier':multiplier})
        else:
            target=next(a.id for a in sim.agents.values() if a.initial_group=='discontented')
            sim.schedule(day*1440+1,'local_disruption',{'target':target,'domain':'supply_access',
                'severity':.3 if case.endswith('sudden') else .3*day/90})
    sim.run(91*1440+1439)
    group=Counter(e['kind'] for e in sim.log)
    target=next(a for a in sim.agents.values() if a.initial_group=='discontented')
    return {'seed':seed,'model':model,'case':case,'population':len(sim.agents),
        'days_with_receipts':92,'losses':sum(a.losses for a in sim.agents.values()),
        'alignment_changes':group['alignment_changed'],'core_changes':group['core_orientation_changed'],
        'support_withdrawals':group['support_withdrawn'],'gatherings_created':group['gathering_created'],
        'attendances':group['gathering_attended'],'institutional_contests':group['institutional_competition'],
        'self_study_actions':group['self_development'],'rejected_actions':group['action_rejected'],
        'decision_reasons':dict(Counter(e['payload']['reason'] for e in sim.log if e['kind']=='decision_appraisal')),
        'target_temporal':target.behavior.get('character',{}).get('domains',{}),
        'total_institutional_position':sum(x['institutional_power'] for x in sim.authorities.values()),
        'observer_development':[a.behavior.get('character',{}).get('development') for a in sim.agents.values() if a.initial_group=='observer']}


def main():
    root=Path(__file__).resolve().parents[1];(root/'runs').mkdir(exist_ok=True)
    data={'schema_version':1,'description':'Mechanism probes; no target rates or real-world validation.',
        'schedule':'Both endpoints day 90: sudden +30% at day 90 vs 90 equal level increments days 1..90. Receipts start day 0; run through day 91. Different cumulative exposure is intentional, not controlled away.',
        'local_nonprice_scope':'Only one directly notified discontented individual per run. No political attribution or monetary loss is invented.',
        'legacy_replay':frozen_replay(root),'runs':[]}
    assert data['legacy_replay']['profile_bytes_identical'] and data['legacy_replay']['exact_snapshot_match'],data['legacy_replay']
    for seed in (0,44,101,777):
        for model in ('v3.1','v3.2'):
            for case in ('price_sudden','price_gradual'):
                data['runs'].append(probe(seed,model,case))
        for case in ('nonprice_sudden','nonprice_gradual'):
            data['runs'].append(probe(seed,'v3.2',case))
    data['run_count']=len(data['runs'])
    data['source_sha256']={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ('society','tests') for p in sorted((root/folder).iterdir()) if p.suffix in ('.py','.json')}
    out=root/'reports/character-v32-check.json';out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(f'{len(data["runs"])} runs; exact frozen v3.1 replay matched; evidence: {out}')


if __name__=='__main__':main()
