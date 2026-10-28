"""Behavior v3: local attribution is not harm; awareness is not advantage."""
from copy import deepcopy
import tempfile
from pathlib import Path
import unittest

from society import appraisal, dynamics, psychology
from society.engine import Simulation
from society.behavior import load_profile, load_legacy_profile, load_v3_profile


class AppraisalContracts(unittest.TestCase):
    def setUp(self):
        self.sim=Simulation()
        self.a=self.sim.agents['A0001']
        self.leader=next(x for x in self.sim.authorities if self.sim.agents[x].alignment=='A')
        if not self.sim.edge(self.leader,self.a.id):
            self.sim.edges.append(dict(source=self.leader,target=self.a.id,type='authority',trust=.9,latency=10))

    def read(self,topic,claim=100):
        # Explicitly deliver and read through the ordinary queue, not direct state injection.
        self.sim.run(self.sim.time)
        leader=self.sim.agents[self.leader]
        # Advance to the next budget day if a previous fixture used its two sends.
        if leader.used['communication']>=self.sim.config.communication_budget:
            self.sim.run((self.sim.time//1440+1)*1440)
        did=self.sim.propose(self.leader,dict(type='send',target=self.a.id,text=topic,topic=topic,claim=claim))
        self.assertTrue(self.sim.apply(did))
        self.sim.run(self.sim.time+self.sim.edge(self.leader,self.a.id)['latency'])
        return appraisal.assess(self.sim,self.a,'test-assessment')

    def test_profile_coefficients_preserved_and_old_version_explicit(self):
        old=load_legacy_profile();v3=load_v3_profile();current=load_profile()
        self.assertEqual(old['groups'],v3['groups'])
        self.assertEqual(old['dynamics'],v3['dynamics'])
        self.assertNotEqual(old['groups'],current['groups'])
        self.assertFalse(appraisal.enabled(Simulation(behavior_profile=old)))
        self.assertTrue(appraisal.enabled(self.sim))
        self.assertTrue(psychology.enabled(self.sim))

    def test_unknown_loss_has_no_automatic_political_blame(self):
        self.sim.schedule(1,'price_shock',{'multiplier':1.8});self.sim.run(30*1440-1)
        s=self.a.behavior
        self.assertGreater(s['burden'],0)
        self.assertEqual(s['appraisal']['burden_by_pole'],{'A':0.,'B':0.})
        self.assertEqual(s['appraisal']['responsibility'],{'unknown':1.})
        self.assertIn('experienced_harm',self.a.beliefs)
        self.assertFalse(any(e['kind']=='alignment_changed' for e in self.sim.log))

    def test_known_alternative_alone_has_zero_advantage(self):
        r=self.read('alternative_known:B',None)
        self.assertIn('B',appraisal.state(self.a)['known_alternatives'])
        self.assertEqual(r['attraction'],0)

    def test_benefit_uses_trust_interests_and_private_topic_views(self):
        r=self.read('benefit:B:economic_security')
        self.assertGreater(r['attraction'],0)
        self.assertIn('benefit:B:economic_security',self.a.beliefs)
        high=r['attraction']
        self.a.behavior['trust'][self.leader]=0
        self.assertEqual(appraisal.assess(self.sim,self.a,'local-distrust')['attraction'],0)
        self.assertGreater(high,0)

    def test_equal_expected_improvements_give_no_relative_advantage(self):
        self.read('benefit:B:order');r=self.read('benefit:A:order')
        self.assertAlmostEqual(r['attraction'],0)

    def test_unread_evidence_cannot_change_appraisal(self):
        self.sim.config.read_budget=0
        self.sim.apply(self.sim.propose(self.leader,dict(type='send',target=self.a.id,text='claim',topic='responsibility:A',claim=100)))
        self.sim.run(300)
        self.assertTrue(self.a.inbox)
        self.assertEqual(appraisal.assess(self.sim,self.a,'unread')['responsibility'],{'unknown':1.})

    def test_external_and_unknown_attributions_do_not_blame_own_pole(self):
        for target in ('external','unknown'):
            r=self.read('responsibility:'+target)
            self.assertEqual(r['shares_by_pole']['A'],0)

    def test_current_pole_and_known_leader_are_distinct_hypotheses(self):
        r=self.read('responsibility:leader:'+self.leader)
        self.assertIn('leader:'+self.leader,r['responsibility'])
        self.assertGreater(r['shares_by_pole']['A'],0)
        self.assertNotIn('A',r['responsibility'])

    def test_attributed_burden_does_not_transfer_to_new_pole(self):
        self.read('responsibility:A')
        self.sim.schedule(self.sim.time+1,'price_shock',{'multiplier':1.8})
        self.sim.run(10*1440)
        old=appraisal.state(self.a)['burden_by_pole']['A']
        self.assertGreater(old,0)
        self.a.alignment='B'
        dynamics.daily(self.sim,self.a,7.2,'direct-local-cost')
        self.assertEqual(appraisal.state(self.a)['burden_by_pole']['B'],0)
        update=self.sim.log[-1]['payload']
        self.assertEqual(update['political_burden'],0)
        self.assertEqual(update['appraisal']['shares_by_pole']['B'],0)

    def test_late_claim_does_not_retroactively_assign_past_loss(self):
        self.sim.schedule(1,'price_shock',{'multiplier':1.8});self.sim.run(10*1440)
        self.assertGreater(self.a.behavior['burden'],0)
        self.read('responsibility:A')
        self.assertEqual(appraisal.state(self.a)['burden_by_pole']['A'],0)
        self.sim.run(11*1440)
        self.assertGreater(appraisal.state(self.a)['burden_by_pole']['A'],0)
        self.assertLess(appraisal.state(self.a)['burden_by_pole']['A'],self.a.behavior['burden'])

    def test_direct_contract_notice_is_local_and_income_scoped(self):
        target=next(a for a in self.sim.agents.values() if a.authority_dependency)
        actor=self.sim.agents[target.authority_dependency]
        self.assertTrue(self.sim.apply(self.sim.propose(actor.id,dict(type='revoke_contract',target=target.id))))
        r=appraisal.assess(self.sim,target,'signed-notice',expense_harm=0.,income_harm=.3)
        self.assertEqual(r['responsibility']['leader:'+actor.id],1)
        other=appraisal.assess(self.sim,target,'price-only',expense_harm=.8,income_harm=0.)
        self.assertEqual(other['responsibility'],{'leader:'+actor.id:0.,'unknown':1.})
        self.assertFalse(appraisal.state(self.a)['responsibility_sources'])

    def test_positive_evidence_and_attributed_harm_can_still_produce_change(self):
        # Three local, independent trusted authorities, not magical global knowledge.
        leaders=[x for x in self.sim.authorities if self.sim.agents[x].alignment=='A'][:3]
        for x in leaders:
            if not self.sim.edge(x,self.a.id):
                self.sim.edges.append(dict(source=x,target=self.a.id,type='authority',trust=.95,latency=10))
            for day,topic in enumerate(('responsibility:A','benefit:B:economic_security','benefit:B:status','benefit:B:order'),1):
                self.sim.schedule(day*1440+60,'external_action',{'actor':x,'proposal':dict(type='send',target=self.a.id,text=topic,topic=topic,claim=100)})
        self.sim.schedule(1,'price_shock',{'multiplier':2.0});self.sim.run(90*1440-1)
        changes=[e for e in self.sim.log if e['kind']=='alignment_changed' and e['payload']['agent']==self.a.id]
        self.assertTrue(changes)
        self.assertGreater(changes[0]['payload']['diagnostic']['appraisal']['attraction'],0)
        self.assertEqual(self.a.initial_group,'power_aligned')

    def test_resume_and_replay_preserve_appraisals(self):
        self.read('responsibility:A');self.read('benefit:B:order')
        self.sim.schedule(self.sim.time+1,'price_shock',{'multiplier':1.8})
        full=deepcopy(self.sim);full.run(30*1440-1)
        self.sim.run(15*1440)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'state.json';self.sim.save(p);loaded=Simulation.load(p);loaded.run(30*1440-1)
        self.assertEqual(full.agents,loaded.agents)
        self.assertEqual(full.log,loaded.log)

    def test_hidden_world_power_does_not_influence_assessment(self):
        self.read('benefit:B:order')
        before=appraisal.assess(self.sim,self.a,'before')
        self.sim.pole_power={'A':0.,'B':100.}
        after=appraisal.assess(self.sim,self.a,'after')
        self.assertEqual(before,after)

    def test_topic_change_resistance_blocks_unaccepted_benefit_claim(self):
        self.a.traits['topic_change_threshold']=1.
        r=self.read('benefit:B:order')
        self.assertEqual(r['attraction'],0)
        self.assertEqual(self.a.beliefs['benefit:B:order']['estimate'],50)

    def test_repeated_same_author_is_not_independent_confirmation(self):
        first=self.read('responsibility:A')
        second=self.read('responsibility:A')
        self.assertEqual(first['responsibility'],second['responsibility'])
        self.assertEqual(len(appraisal.state(self.a)['responsibility_sources']),1)

    def test_hidden_source_change_does_not_rewrite_old_attribution(self):
        before=self.read('responsibility:leader:'+self.leader)
        self.sim.agents[self.leader].alignment='B'
        after=appraisal.assess(self.sim,self.a,'no-new-message')
        self.assertEqual(before['responsibility'],after['responsibility'])
        self.assertEqual(before['shares_by_pole'],after['shares_by_pole'])


if __name__=='__main__':unittest.main()
