import unittest
from society.appraisal_trial import trial


class SmallPairedTrial(unittest.TestCase):
    def test_same_world_losses_and_reach_across_versions(self):
        old,a=trial(0,'v2',1.8,True,True,days=5)
        new,b=trial(0,'v3',1.8,True,True,days=5)
        self.assertEqual(a['initial_hash'],b['initial_hash'])
        self.assertEqual(a['loss_total'],b['loss_total'])
        self.assertEqual(a['evidence_reached'],b['evidence_reached'])
        self.assertGreater(b['max_assessed_attraction'],0)
        self.assertEqual(old.behavior_profile['behavior_version'],'2.0.0')
        self.assertEqual(new.behavior_profile['behavior_version'],'3.0.0')

    def test_awareness_control_has_no_assessed_advantage(self):
        sim,row=trial(1,'v3',1.8,True,False,days=5)
        self.assertGreater(row['evidence_reached'],0)
        self.assertEqual(row['max_assessed_attraction'],0)
        self.assertEqual(row['changed_agents'],0)


if __name__=='__main__':unittest.main()
