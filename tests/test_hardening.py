"""Audit regressions: boundary ordering, serialization, local knowledge and profiles."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from society.behavior import PARAMETERS, load_profile, validate_profile
from society.engine import BaselineProvider, Config, GROUPS, Simulation


class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.sim = Simulation()
        self.actor = next(iter(self.sim.agents))
        self.target = next(e['target'] for e in self.sim.edges if e['source'] == self.actor)

    def send(self, **kw):
        p = dict(type='send', target=self.target, text='statement', topic='power:A', claim=75)
        p.update(kw)
        self.assertTrue(self.sim.apply(self.sim.propose(self.actor, p)))
        return next(reversed(self.sim.messages))

    def state(self, sim):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 's.json'
            sim.save(p)
            return json.loads(p.read_text())

    def test_profiles_population_and_personal_bounds(self):
        for population in (100, 1000):
            sim = Simulation(Config(population=population))
            self.assertEqual(Counter(a.initial_group for a in sim.agents.values()),
                             {g: v * population // 100 for g, v in GROUPS.items()})
            for a in sim.agents.values():
                profile = sim.behavior_profile['groups'][a.initial_group]
                self.assertEqual(a.traits, a.initial_traits)
                self.assertIsNot(a.traits, a.initial_traits)
                for key in PARAMETERS:
                    lo, hi = profile['parameters'][key]
                    self.assertLessEqual(lo, a.traits[key])
                    self.assertLessEqual(a.traits[key], hi)
                self.assertEqual(a.traits['resistance'], a.traits['core_orientation_resistance'])
            values = [a.traits['authority_sensitivity'] for a in sim.agents.values() if a.initial_group == 'power_aligned']
            self.assertGreater(len(set(values)), 1)

    def test_seed_reproduces_complete_run(self):
        other = Simulation()
        for sim in (self.sim, other):
            sim.run(0)
            sim.schedule(60, 'price_shock', {'multiplier': 1.4})
            sim.apply(sim.propose(self.actor, dict(type='send', target=self.target, text='x')))
            sim.run(3000)
        self.assertEqual(self.state(self.sim), self.state(other))
        self.assertNotEqual(asdict(Simulation(Config(seed=45)).agents[self.actor]), asdict(self.sim.agents[self.actor]))

    def test_config_rejects_invalid_types(self):
        for kw in ({'population':100.0}, {'read_budget':1.5}, {'action_budget':True}, {'communication_budget':-1}):
            with self.assertRaises(ValueError):
                Config(**kw)
        for mutation in ('range', 'missing', 'fraction', 'nan'):
            p = load_profile()
            if mutation == 'range': p['groups']['observer']['parameters']['pressure_response'] = [1, 0]
            if mutation == 'missing': del p['groups']['wealthy']['parameters']['economic_harm_response']
            if mutation == 'fraction': p['groups']['authority']['population_percent'] = 14
            if mutation == 'nan': p['belief_step'] = float('nan')
            with self.assertRaises(ValueError): validate_profile(p)

    def test_initial_daily_does_not_refill_spent_budget(self):
        self.sim.config.action_budget = 1
        self.sim.apply(self.sim.propose(self.actor, {'type':'declare_support', 'value':.2}))
        self.sim.run(0)
        self.assertFalse(self.sim.apply(self.sim.propose(self.actor, {'type':'declare_support', 'value':.3})))
        self.assertEqual(self.sim.agents[self.actor].used['action'], 1)
        self.sim.run(1439)
        self.assertEqual(self.sim.agents[self.actor].used['action'], 1)
        self.sim.run(1440)
        self.assertEqual(self.sim.agents[self.actor].used['action'], 0)

    def test_duplicate_daily_does_not_repeat_economy(self):
        before = self.sim.agents[self.actor].savings
        self.sim.schedule(0, 'daily', {})
        self.sim.schedule(1440, 'daily', {})
        self.sim.run(1440)
        a = self.sim.agents[self.actor]
        self.assertAlmostEqual(a.savings, before + 2*(a.income-a.expense))
        self.assertEqual(len([m for m in a.memories if m['type']=='direct_experience']), 2)

    def test_boundary_daily_precedes_prequeued_decision(self):
        self.sim.config.action_budget = 1
        self.sim.schedule(1440, 'decide', {'target':self.actor})
        self.sim.run(0)
        self.sim.apply(self.sim.propose(self.actor, {'type':'declare_support','value':.1}))
        class Supports:
            def decide(self, obs): return {'type':'declare_support','value':.7}
        self.sim.run(1440, Supports())
        a = self.sim.agents[self.actor]
        self.assertEqual(a.public_support, .7)
        self.assertEqual(a.used['action'], 1)
        logs = [e['kind'] for e in self.sim.log if e['time']==1440]
        self.assertLess(logs.index('daily'), logs.index('decide'))

    def test_same_time_fifo_and_causal_ids(self):
        first = self.sim.schedule(5, 'power_change', {'pole':'A','value':60})
        second = self.sim.schedule(5, 'power_change', {'pole':'A','value':40}, first)
        self.sim.run(5)
        self.assertEqual(self.sim.pole_power['A'], 40)
        events = [e for e in self.sim.log if e['kind']=='power_change']
        self.assertEqual([e['event_id'] for e in events], [first, second])
        self.assertEqual(events[-1]['caused_by'], first)
        self.assertFalse(self.sim.agents[self.actor].beliefs)

    def test_pause_reload_at_multiple_boundaries(self):
        self.send()
        self.sim.schedule(1440, 'power_change', {'pole':'A','value':30})
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'base.json'
            self.sim.save(p)
            continuous = Simulation.load(p)
            continuous.run(4000)
            for stops in ([0,1,1439,1440,1441,2880], [20,150,1200,3000]):
                resumed = Simulation.load(p)
                for stop in stops:
                    resumed.run(stop)
                    resumed.save(Path(tmp)/'resume.json')
                    resumed = Simulation.load(Path(tmp)/'resume.json')
                resumed.run(4000)
                self.assertEqual(self.state(continuous), self.state(resumed))

    def test_delivered_read_and_memory_times_are_separate(self):
        self.sim.config.read_budget = 0
        mid = self.send()
        self.sim.run(1439)
        a = self.sim.agents[self.target]
        delivered = a.inbox[0]['delivered_at']
        self.assertLess(delivered, 1440)
        self.assertFalse(any(m.get('message_id')==mid for m in self.sim.observation(a.id)['messages']))
        self.sim.config.read_budget = 1
        self.sim.run(1440)
        m = next(m for m in a.memories if m.get('message_id')==mid)
        self.assertEqual(m['delivered_at'], delivered)
        self.assertEqual(m['learned_at'], 1440)
        self.assertEqual(m['topic'], 'power:A')
        self.assertEqual(a.used['read'], 1)

    def test_provider_ignores_nonmessage_experiences(self):
        self.assertEqual(BaselineProvider().decide({'messages':[{'type':'direct_experience'}], 'contacts':['x']}), {'type':'wait'})
        self.sim.run(0)
        self.assertEqual(self.sim.observation(self.actor)['messages'], [])
        self.assertTrue(self.sim.observation(self.actor)['experiences'])

    def test_historical_source_metadata_not_live_private_state(self):
        leader = next(x for x in self.sim.authorities if self.sim.agents[x].alignment=='A')
        self.sim.edges.append(dict(source=leader,target=self.actor,type='authority',trust=.9,latency=10))
        self.sim.apply(self.sim.propose(leader, dict(type='send',target=self.actor,text='x',topic='power:A',claim=90)))
        self.sim.agents[leader].alignment = 'B'  # unobserved later change must not rewrite old statement
        self.sim.run(10)
        self.assertIn('power:A', self.sim.agents[self.actor].beliefs)
        self.assertNotIn('power:B', self.sim.agents[self.actor].beliefs)

    def test_malformed_actions_no_mutation_and_snapshot_safe(self):
        self.sim.run(0)
        before = {k:asdict(a) for k,a in self.sim.agents.items()}
        for p in ({'type':[]}, {'type':'send','target':self.target,'text':'x','topic':[]},
                  {'type':'pressure','target':[]}, {'type':'send','target':self.target,'text':'x','claim':float('nan')},
                  {'type':'send','target':self.target,'text':set()}):
            self.assertFalse(self.sim.apply(self.sim.propose(self.actor,p)))
        self.assertEqual(before, {k:asdict(a) for k,a in self.sim.agents.items()})
        self.state(self.sim)  # rejected output must not make JSON unsaveable

    def test_rejected_events_do_not_enter_queue(self):
        before = deepcopy(self.sim.queue)
        for kind,p in [('unknown',{}),('price_shock',{'multiplier':float('nan')}),
                       ('read',{'target':[]}),('power_change',{'pole':[],'value':5})]:
            with self.assertRaises(ValueError): self.sim.schedule(5,kind,p)
        self.assertEqual(before,self.sim.queue)

    def test_failed_provider_resume(self):
        self.send()
        class Fails:
            def decide(self,obs): raise ConnectionError('test outage')
        with self.assertRaises(ConnectionError): self.sim.run(300,Fails())
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'state.json'
            resumed=self.sim.fork(p)
            self.sim.run(300)
            resumed.run(300)
            self.assertEqual(self.state(self.sim),self.state(resumed))

    def test_profile_frozen_in_snapshot(self):
        self.sim.run(0)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'s.json'
            self.sim.save(p)
            loaded=Simulation.load(p)
            self.assertEqual(loaded.behavior_profile, self.sim.behavior_profile)
            self.assertEqual(loaded.protocol['behavior_profile'],self.sim.behavior_profile)
            loaded.behavior_profile['belief_step']=.1
            self.assertEqual(self.sim.behavior_profile['belief_step'],.3)

    def test_alignment_does_not_rewrite_identity_or_other_state(self):
        a=self.sim.agents[self.actor]
        initial, traits, beliefs=a.initial_group,deepcopy(a.traits),deepcopy(a.beliefs)
        a.alignment='B'
        self.assertEqual((a.initial_group,a.traits,a.beliefs),(initial,traits,beliefs))
        self.assertEqual(a.initial_traits,traits)

    def test_insufficient_resources_no_partial_pressure(self):
        target = next(a for a in self.sim.agents.values() if a.initial_group == 'wealthy')
        actor = self.sim.agents[target.authority_dependency]
        actor.savings = 1
        before = {k: asdict(a) for k, a in self.sim.agents.items()}
        self.assertFalse(self.sim.apply(self.sim.propose(actor.id, {'type':'pressure', 'target':target.id})))
        self.assertEqual(before, {k: asdict(a) for k, a in self.sim.agents.items()})

    def test_inbox_exhaustion_and_next_day_refill(self):
        self.sim.config.read_budget = 1
        self.send(text='first')
        self.send(text='second')
        self.sim.run(1439)
        target = self.sim.agents[self.target]
        self.assertEqual(target.used['read'], 1)
        self.assertEqual(len(target.inbox), 1)
        self.sim.run(1440)
        self.assertEqual(target.used['read'], 1)
        self.assertFalse(target.inbox)
        learned = [m for m in target.memories if 'message_id' in m]
        self.assertEqual(len(learned), 2)
        self.assertEqual(len(set(m['message_id'] for m in learned)), 2)

    def test_configurable_topic_threshold(self):
        profile = load_profile()
        profile['groups']['power_aligned']['parameters']['topic_change_threshold'] = [.9,.9]
        sim = Simulation(behavior_profile=profile)
        leader = next(x for x in sim.authorities if sim.agents[x].alignment == 'A')
        sim.edges.append(dict(source=leader, target=self.actor, type='authority', trust=.9, latency=5))
        sim.apply(sim.propose(leader, dict(type='send',target=self.actor,text='small evidence',topic='power:A',claim=51)))
        sim.run(10)
        self.assertFalse(sim.agents[self.actor].beliefs)
        self.assertTrue(sim.observation(self.actor)['messages'])  # hearing is not accepting

    def test_legacy_snapshot_migration_without_rng_draws(self):
        self.sim.run(20)
        data = self.state(self.sim)
        data['version'] = 1
        del data['behavior_profile']
        del data['last_daily_day']
        for agent in data['agents'].values():
            del agent['budget_day']
            for key in ('traits','initial_traits'):
                agent[key] = {k:v for k,v in agent[key].items() if k in ('resistance','risk_tolerance','authority_sensitivity')}
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'legacy.json'
            p.write_text(json.dumps(data))
            loaded = Simulation.load(p)
            self.assertEqual(loaded.rng.getstate(), self.sim.rng.getstate())
            self.assertEqual(loaded.agents[self.actor].savings, self.sim.agents[self.actor].savings)
            self.assertEqual(loaded.agents[self.actor].traits['resistance'],self.sim.agents[self.actor].traits['resistance'])
            loaded.run(2880)
            loaded.save(Path(tmp)/'v2.json')
            self.assertEqual(json.loads((Path(tmp)/'v2.json').read_text())['version'], 2)


if __name__ == '__main__':
    unittest.main()
