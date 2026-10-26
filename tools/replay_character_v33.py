"""Exact continuation checks; does not overwrite main study evidence."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from society.character_research_v33 import specs,prepared
from society.character_research_v32 import advance,identifier
from society.character_v32_check import frozen_replay
from society.engine import Simulation


def main():
    out=ROOT/'reports/character-research-v33';rows=[]
    selected=('i80-A-positive','source-aligned','x-colocation-shared-support','agenda-qualification-only')
    for case in selected:
        j=next(j for j in specs() if j['case']['name']==case and j['seed']==0 and j['population']==100 and j['model']=='v3.3' and j['days']==30)
        sim=prepared(j)
        for day in range(6):advance(sim,(day+1)*1440-1)
        with tempfile.TemporaryDirectory(dir=ROOT/'runs') as td:
            path=Path(td)/'original.json';sim.save(path);other=Simulation.load(path)
            for day in range(6,30):
                advance(sim,(day+1)*1440-1);advance(other,(day+1)*1440-1)
            sim.save(path);second=Path(td)/'restored.json';other.save(second)
            h=hashlib.sha256(path.read_bytes()).hexdigest();h2=hashlib.sha256(second.read_bytes()).hexdigest()
            assert h==h2
        rid=identifier(j)
        with gzip.open(out/'evidence'/rid/'audit.json.gz','rt') as f:audit=json.load(f)
        result={a.id:{'alignment':a.alignment,'public_alignment':a.public_alignment,'public_support':a.public_support,
             'private_loyalty':a.private_loyalty,'core':a.behavior['core_orientation'],'evidence':a.change_evidence} for a in sim.agents.values()}
        assert result==audit['final_deep_state']
        rows.append({'id':rid,'checkpoint_day':5,'end_day':29,'original_sha256':h,'restored_sha256':h2,'exact_snapshot_match':True,'matches_study_deep_state':True})
    old=frozen_replay(ROOT);assert old['exact_snapshot_match'] and old['profile_bytes_identical']
    (out/'replays.json').write_text(json.dumps({'v33_replays':rows,'frozen_v31_control':old},ensure_ascii=False,indent=2)+'\n')
    print('4 exact v3.3 continuations + frozen v3.1 full snapshot comparison matched')


if __name__=='__main__':main()
