import unittest
from society.character_research_v33 import specs,prepared
from society.character_research_v32 import identifier,advance


class CurrentResearchContracts(unittest.TestCase):
    def job(self,name):return next(j for j in specs() if j['case']['name']=='agenda-'+name and j['seed']==0 and j['population']==100)

    def test_fixed_scope_and_unique_jobs(self):
        jobs=list(specs());self.assertEqual(len(jobs),808)
        self.assertEqual(len(set(map(identifier,jobs))),808)
        self.assertEqual(sum(j['section']=='fresh-v32-control' for j in jobs),32)
        self.assertEqual(sum(j['section'].startswith('agenda') for j in jobs),84)

    def test_whole_population_scale_does_not_require_outside_peer(self):
        j=next(j for j in specs() if j['section']=='agenda-scale')
        sim=prepared(j)
        notices=[x for x in sim.protocol['character_study']['plan'] if x['kind']=='agenda_notice']
        self.assertEqual(len({x['payload']['target'] for x in notices}),1000)

    def test_ordinary_arms_share_initial_personality_economy_and_graph(self):
        a=prepared(self.job('no-notice'));b=prepared(self.job('evidence-direct'))
        self.assertEqual(a.protocol['character_study']['initial_world_hash'],b.protocol['character_study']['initial_world_hash'])
        self.assertEqual(a.behavior_profile,b.behavior_profile)

    def test_received_proof_not_equivalent_to_unread_transmission(self):
        a=prepared(self.job('evidence-direct'));b=prepared(self.job('evidence-unread'))
        for sim in (a,b):advance(sim,8*1440-1)
        target=a.protocol['character_study']['targets'][0]
        self.assertEqual(a.agents[target].behavior['agenda']['appointment']['qualification'],1)
        self.assertEqual(b.agents[target].behavior['agenda']['appointment']['qualification'],.5)
        self.assertEqual(a.agenda_runtime['network_requests'],0)
        self.assertEqual(b.agenda_runtime['network_requests'],0)


if __name__=='__main__':unittest.main()
