"""Long horizon replay/resume checks; hashes cover complete saved state."""
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import time

from .engine import Simulation
from .experiments import make_run


def main():
    results=[]
    for pop in (100,1000):
        start=time.perf_counter()
        full,row,_=make_run(19,pop,'B',60,'runs/behavior-verification')
        replay,_,_=make_run(19,pop,'B',60)
        partial,_,_=make_run(19,pop,'B',60,stop_at=15*1440)
        with tempfile.TemporaryDirectory(dir='runs') as tmp:
            p=Path(tmp)/'resume.json';partial.save(p)
            resumed=Simulation.load(p);resumed.run(60*1440-1, max_events=1000000)
            checks={}
            for name,sim in [('full',full),('replay',replay),('resumed',resumed)]:
                dest=Path(tmp)/(name+'.json');sim.save(dest)
                checks[name]=hashlib.sha256(dest.read_bytes()).hexdigest()
            equal=len(set(checks.values()))==1
        result={'population':pop,'days':60,'seed':19,'completed_trajectories':3,
                'hashes':checks,'full_replay_resume_equal':equal,
                'total_wall_seconds':time.perf_counter()-start,'full_metrics':row}
        results.append(result)
        print(json.dumps(result),flush=True)
        del full,replay,partial,resumed
        if not equal: raise RuntimeError('Long horizon replay/resume mismatch')
    Path('reports/behavior-verification.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':main()
