"""Behavioral contracts, separate from queue/serialization mechanical tests."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from society import dynamics
from society.behavior import load_profile, load_legacy_profile
from society.engine import Config, Simulation


class BehavioralContracts(unittest.TestCase):
    def setUp(self):
        self.sim = Simulation(behavior_profile=load_legacy_profile())
        self.a = self.sim.agents['A0001']

    def harsh_world(self, days=60):
        self.sim.schedule(1, 'price_shock', {'multiplier':2.0})
        self.sim.run(days*1440-1)

    def announcement(self, claim=0, topic='economic_outlook', target=None):
        target = target or self.a.id
        leader = next(x for x in self.sim.authorities if self.sim.agents[x].alignment=='A')
        if not self.sim.edge(leader,target):
            self.sim.edges.append(dict(source=leader,target=target,type='authority',trust=.8,latency=10))
        self.sim.apply(self.sim.propose(leader,dict(type='send',target=target,text='forecast',topic=topic,claim=claim)))
        return leader

    def test_single_shock_not_instant_alignment(self):
        old=self.a.alignment
        self.harsh_world(2)
        self.assertEqual(self.a.alignment,old)
        self.assertGreater(self.a.change_evidence,0)
        self.assertIn('experienced_harm',self.a.beliefs)

    def test_repeated_loss_can_change_some_not_all_agents(self):
        initial={a.id:(a.initial_group,deepcopy(a.initial_traits)) for a in self.sim.agents.values()}
        self.harsh_world(90)
        changed=[e for e in self.sim.log if e['kind']=='alignment_changed']
        self.assertTrue(changed)
        self.assertGreater(len({e['time'] for e in changed}),1)
        self.assertLess(len({e['payload']['agent'] for e in changed}),100)
        for a in self.sim.agents.values():
            self.assertEqual(initial[a.id],(a.initial_group,a.initial_traits))

    def test_private_public_and_action_are_distinct(self):
        self.harsh_world(10)
        self.assertNotEqual(self.a.private_loyalty,self.a.public_support)
        self.assertFalse(any(e['kind']=='action_applied' and e['payload']['actor']==self.a.id for e in self.sim.log))
        private=self.a.private_loyalty
        self.sim.apply(self.sim.propose(self.a.id,dict(type='declare_support',value=0)))
        self.assertEqual(self.a.private_loyalty,private)
        self.assertEqual(self.a.public_support,0)

    def test_pressure_changes_public_not_private(self):
        target=next(a for a in self.sim.agents.values() if a.authority_dependency)
        before=(target.private_loyalty,deepcopy(target.beliefs),target.alignment)
        self.assertTrue(self.sim.apply(self.sim.propose(target.authority_dependency,dict(type='pressure',target=target.id))))
        self.assertGreater(target.public_support,.5)
        self.assertEqual(before,(target.private_loyalty,target.beliefs,target.alignment))
        self.assertTrue(target.memories)

    def test_forecast_contradiction_requires_later_local_observation(self):
        leader=self.announcement()
        self.sim.run(10)
        trust=self.a.behavior['trust'][leader]
        self.sim.schedule(11,'price_shock',{'multiplier':1.8})
        self.sim.run(1439)
        self.assertEqual(self.a.behavior['trust'][leader],trust)
        self.sim.run(3*1440)
        self.assertLess(self.a.behavior['trust'][leader],trust)
        updates=[e for e in self.sim.log if e['kind']=='trust_updated' and e['payload']['agent']==self.a.id]
        self.assertTrue(all(e['time']>e['payload']['learned_at'] for e in updates))

    def test_truthful_forecast_can_restore_trust(self):
        leader=self.announcement(claim=0)
        self.sim.run(10)
        self.a.behavior['trust'][leader]=.2
        self.sim.run(3*1440)
        self.assertGreater(self.a.behavior['trust'][leader],.2)

    def test_unreached_agent_has_no_forecast_evidence(self):
        self.announcement()
        self.sim.run(10)
        ignorant=next(a for a in self.sim.agents.values() if not a.behavior['forecasts'])
        self.assertFalse(any(e['kind']=='trust_updated' and e['payload']['agent']==ignorant.id for e in self.sim.log))
        self.assertFalse(ignorant.behavior['forecasts'])

    def test_hysteresis_has_separate_return_threshold_and_cooldown(self):
        self.sim.run(0)
        self.a.behavior['previous_alignment']='B'
        self.a.behavior['known']['fixture']={'pole':'B','group':'authority','trust':.5}
        self.a.behavior['last_switch_day']=0
        self.a.change_evidence=100
        dynamics.daily(self.sim,self.a,8,'test-local-experience')
        self.assertEqual(self.a.alignment,'A')  # cooldown, despite evidence
        threshold_with_return=self.sim.log[-1]['payload']['threshold']
        self.a.behavior['previous_alignment']=None
        dynamics.daily(self.sim,self.a,8,'test-local-experience')
        threshold_without_return=self.sim.log[-1]['payload']['threshold']
        self.assertAlmostEqual(threshold_with_return-threshold_without_return,.30)

    def test_core_orientation_is_slower_but_not_impossible(self):
        self.sim.run(0)
        observer=next(a for a in self.sim.agents.values() if a.initial_group=='observer')
        self.sim.behavior_profile['dynamics']['core_threshold_scale']=.01
        for _ in range(15):
            dynamics.daily(self.sim,self.a,8,'severe-direct-evidence')
            dynamics.daily(self.sim,observer,8,'severe-direct-evidence')
        self.assertGreater(self.a.behavior['core_changes'],0)
        self.assertEqual(observer.behavior['core_changes'],0)
        for _ in range(2000):
            dynamics.daily(self.sim,observer,8,'prolonged-direct-evidence')
        self.assertGreater(observer.behavior['core_changes'],0)
        self.assertEqual(observer.initial_group,'observer')

    def test_disabled_mechanism_keeps_accumulators_and_loyalty(self):
        self.sim=Simulation(Config(cumulative_enabled=False))
        a=self.sim.agents['A0001']
        self.harsh_world(30)
        self.assertEqual(a.private_loyalty,.5)
        self.assertEqual(a.change_evidence,0)
        self.assertEqual(a.behavior['switch_count'],0)
        self.assertGreater(a.losses,0)

    def test_peer_public_signal_uses_resistance_not_private_state(self):
        sender=next(a for a in self.sim.agents.values() if a.initial_group=='opposition')
        self.sim.edges.append(dict(source=sender.id,target=self.a.id,type='close',trust=.9,latency=10))
        self.sim.apply(self.sim.propose(sender.id,dict(type='send',target=self.a.id,text='public',topic='public_support',claim=100)))
        self.sim.run(10)
        self.assertEqual(self.a.behavior['peer_pull']['B'],0)  # resistance exactly one
        self.assertFalse(self.a.beliefs)

    def test_resume_behavior_matches_uninterrupted(self):
        self.announcement()
        self.sim.schedule(60,'price_shock',{'multiplier':1.8})
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'initial.json';self.sim.save(p)
            resumed=Simulation.load(p)
            self.sim.run(30*1440-1)
            for point in (10,1440,10*1440,20*1440):
                resumed.run(point);resumed.save(p);resumed=Simulation.load(p)
            resumed.run(30*1440-1)
            self.sim.save(Path(tmp)/'full.json');resumed.save(p)
            self.assertEqual(json.loads(p.read_text()),json.loads((Path(tmp)/'full.json').read_text()))

    def test_restricted_audience_cannot_relay_outside(self):
        leader=self.announcement()
        # Separate scoped message; recipient is explicitly allowed, neighbor is not.
        self.sim.apply(self.sim.propose(leader,dict(type='send',target=self.a.id,text='scoped',audience=[self.a.id])))
        mid=next(reversed(self.sim.messages));self.sim.run(10)
        neighbor=next(e['target'] for e in self.sim.edges if e['source']==self.a.id)
        self.assertFalse(self.sim.apply(self.sim.propose(self.a.id,dict(type='relay',target=neighbor,message_id=mid))))

    def test_core_floor_does_not_emit_false_changes(self):
        self.sim.run(0)
        self.a.behavior['core_orientation']=0
        self.a.behavior['core_strain']=100000
        self.a.behavior['observed_days']=100
        dynamics.daily(self.sim,self.a,8,'additional-evidence-at-floor')
        self.assertEqual(self.a.behavior['core_changes'],0)
        self.assertFalse(any(e['kind']=='core_orientation_changed' for e in self.sim.log))


if __name__=='__main__':
    unittest.main()
