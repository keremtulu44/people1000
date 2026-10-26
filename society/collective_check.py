"""Five-seed presence sanity check, not calibration or a social forecast."""
from collections import Counter
import json
from pathlib import Path
from .engine import Simulation, Config, BaselineProvider
from .behavior import load_v31_profile
from . import collective


class NoAttendance(BaselineProvider):
    def decide(self, obs):
        p=super().decide(obs)
        return {'type':'wait'} if p['type']=='attend_gathering' else p


def main():
    rows=[]
    for seed in range(5):
        for attend in (False,True):
            sim=Simulation(Config(seed=seed),behavior_profile=load_v31_profile());provider=BaselineProvider() if attend else NoAttendance()
            sim.schedule(1,'price_shock',{'multiplier':1.8})
            sim.run(1500,provider)
            candidates={x:[e['target'] for e in sim.edges if e['source']==x and sim.agents[e['target']].public_alignment=='A']
                        for x in sim.authorities if sim.agents[x].public_alignment=='A'}
            leader=max(candidates,key=lambda x:len(candidates[x]));targets=candidates[leader][:2]
            assert len(targets)==2
            def apply(proposal):
                assert sim.apply(sim.propose(leader,proposal))
            apply({'type':'create_gathering','place':'local-square','start':2940,'end':3060})
            gid=next(iter(sim.gatherings))
            for target in targets:
                apply({'type':'send','target':target,'text':'Calendar invitation, no promised crowd','gathering_id':gid})
            sim.run(3060,provider)
            joined={e['payload']['agent'] for e in sim.log if e['kind']=='gathering_attended'}
            peaks=[e['payload']['collective_strength'] for e in sim.log if e['kind']=='collective_observation']
            row={'seed':seed,'autonomous_attendance_allowed':attend,'read_invitation_agents':sum(bool(collective.state(a)['known_gatherings']) for a in sim.agents.values()),
                 'actual_attendees':len(joined),'attendee_groups':dict(sorted(Counter(sim.agents[x].initial_group for x in joined).items())),
                 'peak_strength':max(peaks,default=0.),'active_after_end':sum(collective.state(a)['collective_active'] for a in sim.agents.values()),
                 'remaining_distress_agents':sum(collective.state(a)['distress']>0 for a in sim.agents.values()),
                 'core_changes':sum(a.behavior['core_changes'] for a in sim.agents.values()),
                 'party_switches':sum(e['kind']=='alignment_changed' for e in sim.log),'material_losses':sum(a.losses for a in sim.agents.values())}
            assert row['active_after_end']==0 and row['core_changes']==0
            if not attend:assert row['actual_attendees']==0 and row['peak_strength']==0
            rows.append(row)
            sim.protocol['collective_check']={'seed':seed,'autonomous_attendance_allowed':attend,'scope':'short sanity check, not calibrated'}
            sim.save(Path('runs/collective')/f's{seed}-attendance{int(attend)}.json')
    for seed in range(5):
        pair=[r for r in rows if r['seed']==seed]
        assert pair[0]['material_losses']==pair[1]['material_losses']
    Path('reports/collective-check.json').write_text(json.dumps({'runs':10,'rows':rows},indent=2))
    print(json.dumps(rows,indent=2))


if __name__=='__main__':main()
