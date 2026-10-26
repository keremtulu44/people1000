"""Paired experiment and analysis integration contracts."""
from pathlib import Path
import tempfile
import unittest

from society.experiments import aggregate, digest, make_run
from society.engine import Simulation


class ExperimentContracts(unittest.TestCase):
    def test_primary_arms_share_initial_world_and_economic_losses(self):
        rows=[]
        for arm in ('A','B','C','D'):
            sim,row,details=make_run(4,100,arm,5)
            rows.append(row)
            self.assertEqual(row['leaks'],0)
            self.assertEqual(len(sim.daily_metrics),5)
            if arm=='A': self.assertEqual(row['messages'],0)
            if arm=='D': self.assertEqual(row['alignment_changes'],0)
            if arm=='C': self.assertEqual(row['scope_violations'],0)
        self.assertEqual(len({r['initial_hash'] for r in rows}),1)
        self.assertEqual(len({r['losses'] for r in rows}),1)
        self.assertEqual(rows[0]['population'],100)
        self.assertLessEqual(rows[2]['reached_agents'],rows[1]['reached_agents'])
        result=aggregate(rows)
        self.assertEqual(result['paired']['100:B-A']['alignment_changes']['n'],1)

    def test_experiment_repeats_and_continues_exactly(self):
        a,ra,_=make_run(5,100,'B',30)
        b,rb,_=make_run(5,100,'B',30)
        self.assertEqual(a.log,b.log)
        self.assertEqual(a.daily_metrics,b.daily_metrics)
        for key in ('alignment_changes','core_changes','reads','leaks','mean_trust'):
            self.assertEqual(ra[key],rb[key])
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'state.json';a.save(p)
            resumed=Simulation.load(p)
            a.run(45*1440-1);resumed.run(45*1440-1)
            self.assertEqual(a.log,resumed.log)
            self.assertEqual(a.daily_metrics,resumed.daily_metrics)

    def test_scope_is_delivery_restriction_not_topology_change(self):
        b,rb,_=make_run(7,100,'B',10)
        c,rc,dc=make_run(7,100,'C',10)
        self.assertEqual(digest(b.edges),digest(c.edges))
        self.assertEqual(rb['initial_hash'],rc['initial_hash'])
        scope=set(dc['scope'])
        for a in c.agents.values():
            if a.id not in scope:
                self.assertFalse(any('message_id' in m for m in a.memories))

    def test_future_interventions_survive_midexperiment_reload(self):
        full,_,_=make_run(3,100,'B',30)
        partial,_,_=make_run(3,100,'B',30,stop_at=10*1440)
        self.assertTrue(any(e[3]=='external_action' for e in partial.queue))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'state.json'
            partial.save(p);partial=Simulation.load(p)
            partial.run(30*1440-1)
            full.save(Path(tmp)/'full.json');partial.save(p)
            self.assertEqual(p.read_text(),(Path(tmp)/'full.json').read_text())


if __name__=='__main__':unittest.main()
