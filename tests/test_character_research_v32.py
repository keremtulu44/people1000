from collections import Counter
import unittest
from society.character_research_v32 import specs,prepared,advance,identifier


class BroadStudyContracts(unittest.TestCase):
    def jobs(self,name):return next(j for j in specs() if j['case']['name']=='x-'+name and j['seed']==0)

    def test_fixed_scope_unique_and_profiles(self):
        jobs=list(specs());self.assertEqual(len(jobs),692)
        self.assertEqual(len(set(map(identifier,jobs))),692)
        self.assertEqual(Counter(j['section'] for j in jobs),{'replication':508,'directional':104,'new-mechanism':80})
        self.assertEqual(sum(j['model']=='v3.2' for j in jobs),636)
        sim=prepared(next(j for j in jobs if j['model']=='v3.2'))
        self.assertEqual(sim.behavior_profile['behavior_version'],'3.2.0')

    def test_no_attendance_and_no_study_change_policy_not_initial_world(self):
        for a,b in [('local-support-severe','local-support-blocked'),('observer-study','observer-no-study')]:
            x,y=prepared(self.jobs(a)),prepared(self.jobs(b))
            self.assertEqual(x.protocol['character_study']['initial_world_hash'],y.protocol['character_study']['initial_world_hash'])
            self.assertEqual(x.behavior_profile,y.behavior_profile)
            self.assertEqual(x.edges,y.edges)

    def test_explicit_support_fixture_differs_from_observe_without_party_change(self):
        for name,active in [('colocation-opposed-support',0),('colocation-shared-support',2),('colocation-shared-observe',0)]:
            sim=prepared(self.jobs(name));advance(sim,2950)
            views=[a.behavior['social'] for a in sim.agents.values() if a.behavior['social']['present_at']]
            self.assertEqual(len(views),2);self.assertEqual(sum(v['collective_active'] for v in views),active)
            self.assertTrue(all(len(v['visible_participants'])==2 for v in views))
            self.assertFalse(any(e['kind']=='alignment_changed' for e in sim.log))
            self.assertTrue(all(x['accepted'] for x in sim.protocol['character_study']['input_outcomes']))

    def test_precondition_refusal_is_recorded(self):
        for name,accepted in [('contest-valid',True),('contest-unknown',False),('contest-poor',False),('contest-empty',False)]:
            sim=prepared(self.jobs(name));advance(sim,1600)
            outcome=sim.protocol['character_study']['input_outcomes'][0]
            self.assertEqual(outcome['accepted'],accepted)
            if not accepted:self.assertTrue(outcome['reason'])


if __name__=='__main__':unittest.main()
