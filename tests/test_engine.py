import json
from pathlib import Path
import tempfile
import unittest
from collections import Counter

from society.engine import Config, GROUPS, Simulation


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.sim = Simulation()
        self.a = next(iter(self.sim.agents))
        self.target = next(e['target'] for e in self.sim.edges if e['source'] == self.a)

    def send(self, text='hello', **extra):
        did = self.sim.propose(self.a, {'type': 'send', 'target': self.target, 'text': text, **extra})
        self.assertTrue(self.sim.apply(did))
        return next(reversed(self.sim.messages))

    def test_population_and_seed(self):
        self.assertEqual(Counter(a.initial_group for a in self.sim.agents.values()), GROUPS)
        self.assertEqual(self.sim.edges, Simulation().edges)
        self.assertEqual(len(Simulation(Config(population=1000)).agents), 1000)

    def test_identity_and_traits_survive_support_change(self):
        a = self.sim.agents[self.a]
        old = (a.initial_group, dict(a.traits), a.alignment)
        self.sim.apply(self.sim.propose(self.a, {'type': 'declare_support', 'value': .1}))
        self.assertEqual(old, (a.initial_group, a.traits, a.alignment))
        self.assertEqual(a.private_loyalty, .5)

    def test_observation_excludes_world_and_is_detached(self):
        self.sim.pole_power['A'] = 60
        obs = self.sim.observation(self.a)
        self.assertNotIn('pole_power', obs)
        self.assertNotIn('price', obs)
        obs['traits']['resistance'] = 0
        self.assertNotEqual(self.sim.agents[self.a].traits['resistance'], 0)

    def test_delivery_does_not_mean_reading(self):
        self.sim.config.read_budget = 0
        mid = self.send()
        self.sim.run(300)
        self.assertTrue(self.sim.agents[self.target].inbox)
        self.assertFalse(any(m.get('message_id') == mid for m in self.sim.agents[self.target].memories))

    def test_delayed_message_and_provenance(self):
        mid = self.send()
        latency = self.sim.edge(self.a, self.target)['latency']
        self.sim.run(latency - 1)
        self.assertFalse(any(m.get('message_id') == mid for m in self.sim.agents[self.target].memories))
        self.sim.run(latency)
        memory = next(m for m in self.sim.agents[self.target].memories if m.get('message_id') == mid)
        self.assertEqual(memory['original_source'], self.a)
        self.assertEqual(memory['learned_at'], latency)
        self.assertEqual(memory['sender'], self.a)

    def test_no_path_and_unlearned_relay_rejected(self):
        unreachable = next(x for x in self.sim.agents if x != self.a and not self.sim.edge(self.a, x))
        self.assertFalse(self.sim.apply(self.sim.propose(self.a, {'type': 'send', 'target': unreachable, 'text': 'x'})))
        self.assertFalse(self.sim.apply(self.sim.propose(self.a, {'type': 'relay', 'target': self.target, 'message_id': 'fake'})))

    def test_daily_accounting(self):
        a = self.sim.agents[self.a]
        before = a.savings
        self.sim.run(0)
        self.assertAlmostEqual(a.savings, before + a.income - a.expense)
        self.sim.schedule(1, 'price_shock', {'multiplier': 1.4})
        self.sim.run(1440)
        self.assertAlmostEqual(a.savings, before + 2 * a.income - a.expense * 2.4)
        self.assertAlmostEqual(a.losses, a.expense * .4)

    def test_permissions_not_supplied_by_proposal(self):
        before = self.sim.agents[self.target].income
        self.assertFalse(self.sim.apply(self.sim.propose(self.a, {'type': 'revoke_contract',
            'target': self.target, 'required_permissions': []})))
        self.assertEqual(before, self.sim.agents[self.target].income)

    def test_authority_scope_and_idempotency(self):
        target = next(a for a in self.sim.agents.values() if a.initial_group == 'wealthy')
        actor = target.authority_dependency
        did = self.sim.propose(actor, {'type': 'revoke_contract', 'target': target.id})
        before = target.income
        self.assertEqual(target.income, before)  # proposal has no effect
        self.assertTrue(self.sim.apply(did))
        self.assertAlmostEqual(target.income, before * .7)
        self.assertFalse(self.sim.apply(did))
        self.assertAlmostEqual(target.income, before * .7)
        wrong = next(x for x in self.sim.authorities if x != actor)
        self.assertFalse(self.sim.apply(self.sim.propose(wrong, {'type': 'revoke_contract', 'target': target.id})))

    def test_attention_and_action_limits(self):
        self.sim.config.communication_budget = 1
        self.send()
        self.assertFalse(self.sim.apply(self.sim.propose(self.a, {'type': 'send', 'target': self.target, 'text': 'second'})))
        self.sim.config.action_budget = 1
        self.assertFalse(self.sim.apply(self.sim.propose(self.a, {'type': 'declare_support', 'value': .3})))

    def test_observer_traits_unchanged(self):
        observer = next(a for a in self.sim.agents.values() if a.initial_group == 'observer')
        before = dict(observer.traits)
        self.sim.schedule(1, 'price_shock', {'multiplier': 1.4})
        self.sim.run(2880)
        self.assertEqual(before, observer.traits)

    def test_invalid_output_is_rejected(self):
        for p in [None, {}, {'type': 'invent_money'}, {'type': 'declare_support', 'value': float('nan')},
                  {'type': 'send', 'target': self.target, 'text': 'x', 'claim': float('inf')}]:
            self.assertFalse(self.sim.apply(self.sim.propose(self.a, p)))

    def test_topic_isolation_and_peer_gate(self):
        self.sim.agents[self.target].initial_group = 'power_aligned'
        self.sim.agents[self.a].initial_group = 'power_aligned'
        self.send(topic='power:A', claim=90)
        self.sim.run(300)
        self.assertNotIn('power:A', self.sim.agents[self.target].beliefs)
        self.assertNotIn('power:B', self.sim.agents[self.target].beliefs)

    def test_snapshot_resume_and_branch(self):
        self.send()
        self.sim.run(20)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'state.json'
            branch = self.sim.fork(path)
            self.sim.run(2880)
            branch.run(2880)
            self.assertEqual(self.sim.metrics(), branch.metrics())
            self.assertEqual(self.sim.log, branch.log)
            self.sim.save(Path(tmp) / 'a.json')
            branch.save(Path(tmp) / 'b.json')
            self.assertEqual(json.loads((Path(tmp) / 'a.json').read_text()), json.loads((Path(tmp) / 'b.json').read_text()))
            branch.agents[self.a].savings = -500
            self.assertNotEqual(branch.agents[self.a].savings, self.sim.agents[self.a].savings)

    def test_provider_failure_retains_event(self):
        class Broken:
            def decide(self, obs):
                raise ConnectionError('offline')
        self.send()
        with self.assertRaises(ConnectionError):
            self.sim.run(300, Broken())
        self.assertEqual(self.sim.queue[0][3], 'decide')
        self.sim.run(300)
        self.assertTrue(self.sim.calls)

    def test_protocol_and_unknown_perception(self):
        self.assertIsNone(self.sim.metrics()['perception_error'])
        protocol = json.dumps(self.sim.protocol, sort_keys=True)
        self.sim.run(1440)
        self.assertEqual(protocol, json.dumps(self.sim.protocol, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
