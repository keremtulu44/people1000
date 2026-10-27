from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,MagicMock

from society import agenda, psychology
from society.engine import Simulation,BaselineProvider,Config
from society.behavior import load_profile,load_v32_profile,load_v33_profile
from society.agenda_api import AgendaProvider,OpenAICompatibleAdvisor
from society.session import Session


class Wait:
    def decide(self,obs):return {'type':'wait'}


def deep(sim):
    return {a.id:(a.alignment,a.public_alignment,a.public_support,a.private_loyalty,
        a.behavior['core_orientation'],a.change_evidence,deepcopy(a.behavior['trust']),
        deepcopy(a.behavior.get('appraisal'))) for a in sim.agents.values()}


class AgendaContracts(unittest.TestCase):
    def setUp(self):
        self.sim=Simulation();self.sim.run(0,Wait())
        self.root=next(a for a in self.sim.agents.values() if a.initial_group=='authority' and a.alignment=='A')
        self.register()

    def register(self):
        self.sim.schedule(1,'agenda_create',dict(issue='appointment',kind='appointment',issuer=self.root.id,title='Public appointment',
            facts={'diploma':{'aspect':'qualification','value':100}}));self.sim.run(1,Wait())

    def notice(self,a):
        self.sim.schedule(self.sim.time,'agenda_notice',{'issue':'appointment','target':a.id});self.sim.run(self.sim.time,Wait())

    def person(self,group):return next(a for a in self.sim.agents.values() if a.initial_group==group)

    def send(self,a,target,**extra):
        if not self.sim.edge(a.id,target.id):self.sim.edges.append(dict(source=a.id,target=target.id,trust=.8,type='probe',latency=1))
        p=dict(type='send',target=target.id,text='Qualifications asserted',topic='agenda:appointment:qualification',agenda_id='appointment',aspect='qualification',claim=100)
        p.update(extra);return self.sim.apply(self.sim.propose(a.id,p))

    def test_frozen_v32_and_same_coefficients(self):
        from society.behavior import load_v34_profile
        old,v33,v34,current=load_v32_profile(),load_v33_profile(),load_v34_profile(),load_profile()
        self.assertEqual(old['behavior_version'],'3.2.0')
        self.assertEqual(v33['behavior_version'],'3.3.0')
        self.assertEqual(v34['behavior_version'],'3.4.0')
        self.assertEqual(current['behavior_version'],'3.5.0')
        for k in ('groups','dynamics','belief_step','character_dynamics'):self.assertEqual(old[k],v33[k])
        self.assertFalse(agenda.enabled(Simulation(behavior_profile=old)))
        self.assertFalse(psychology.enabled(Simulation(behavior_profile=v33)))
        self.assertTrue(psychology.enabled(Simulation(behavior_profile=v34)))
        self.assertTrue(psychology.v2_enabled(Simulation(behavior_profile=current)))

    def test_world_registration_not_agent_knowledge(self):
        a=self.person('observer');self.assertEqual(agenda.state(a),{})
        obs=self.sim.observation(a.id);self.assertNotIn('agendas',obs);self.assertNotIn('diploma',json.dumps(obs))
        self.notice(a);self.assertEqual(agenda.state(a)['appointment']['evidence'],{})

    def test_notice_preserves_role_prior_not_qualification_truth(self):
        a=self.person('power_aligned');b=self.person('opposition')
        for x in (a,b):self.notice(x)
        self.assertGreater(agenda.state(a)['appointment']['procedure'],.5)
        self.assertLess(agenda.state(b)['appointment']['procedure'],.5)
        self.assertEqual(agenda.state(a)['appointment']['qualification'],.5)

    def test_claim_and_document_are_distinct_and_procedure_survives(self):
        a=self.person('power_aligned');b=self.person('opposition');self.notice(self.root)
        for x in (a,b):self.assertTrue(self.send(self.root,x))
        self.sim.run(20,Wait())
        self.assertGreater(agenda.state(a)['appointment']['qualification'],.5)
        self.assertEqual(agenda.state(b)['appointment']['qualification'],.5)
        prior=agenda.state(b)['appointment']['procedure']
        self.sim.schedule(21,'agenda_evidence',dict(issue='appointment',target=b.id,evidence_id='diploma'))
        self.sim.run(22)
        self.assertEqual(agenda.state(b)['appointment']['qualification'],1)
        self.assertEqual(agenda.state(b)['appointment']['procedure'],prior)
        self.assertEqual(b.alignment,'B');self.assertEqual(agenda.state(b)['appointment']['response']['approach'],'question')

    def test_observer_and_manager_do_not_adopt_speech_as_truth(self):
        self.notice(self.root)
        for group in ('observer','authority'):
            a=self.person(group)
            if a.id==self.root.id:a=next(a for a in self.sim.agents.values() if a.initial_group==group and a.id!=self.root.id)
            self.assertTrue(self.send(self.root,a))
        self.sim.run(200,Wait())
        for a in self.sim.agents.values():
            if a.initial_group in ('observer','authority') and 'appointment' in agenda.state(a):
                self.assertEqual(agenda.state(a)['appointment']['qualification'],.5)

    def test_unread_claim_not_knowledge(self):
        self.notice(self.root);a=self.person('opposition');self.sim.config.read_budget=0
        self.assertTrue(self.send(self.root,a));self.sim.run(200,Wait())
        self.assertNotIn('appointment',agenda.state(a))

    def test_cannot_forge_proof_or_smuggle_political_topic(self):
        self.notice(self.root);a=self.person('opposition')
        self.assertFalse(self.send(self.root,a,evidence_id='diploma'))
        self.assertFalse(self.send(self.root,a,topic='economic_outlook'))
        self.sim.schedule(2,'agenda_evidence',dict(issue='appointment',target=self.root.id,evidence_id='diploma'));self.sim.run(2,Wait())
        self.assertTrue(self.send(self.root,a,evidence_id='diploma'));self.sim.run(200,Wait())
        self.assertEqual(agenda.state(a)['appointment']['qualification'],1)

    def test_event_path_does_not_modify_deep_state(self):
        before=deep(self.sim)
        for a in self.sim.agents.values():self.notice(a)
        self.sim.run(3,Wait())
        self.assertEqual(before,deep(self.sim))
        for a in self.sim.agents.values():
            self.sim.schedule(4,'agenda_evidence',dict(issue='appointment',target=a.id,evidence_id='diploma'))
        self.sim.run(5,Wait());self.assertEqual(before,deep(self.sim))

    def test_30_days_repeated_normal_agenda_vs_untreated_deep_state(self):
        # Same Wait policy and untouched original graph: ordinary messages cannot leak into political dynamics.
        untreated=Simulation();untreated.run(0,Wait())
        self.notice(self.root)
        a=self.sim.agents[next(e['target'] for e in self.sim.edges if e['source']==self.root.id)]
        for day in range(30):
            self.sim.run(day*1440+10,Wait());untreated.run(day*1440+10,Wait())
            self.assertTrue(self.send(self.root,a,text='Repeated normal claim '+str(day)))
            self.sim.run((day+1)*1440-1,Wait());untreated.run((day+1)*1440-1,Wait())
        self.assertEqual(deep(self.sim),deep(untreated))

    def test_review_pools_shared_public_context_not_every_person(self):
        for a in self.sim.agents.values():self.notice(a)
        self.sim.run(2,Wait());rt=self.sim.agenda_runtime
        self.assertLess(len(rt['requests']),20);self.assertEqual(rt['network_requests'],0)
        for r in rt['requests']:
            p=r['packet'];self.assertNotIn('agents',p);self.assertNotIn('savings',p)
            self.assertNotIn('private_loyalty',json.dumps(p))
        count=len(rt['requests']);self.sim.run(20,Wait());self.assertEqual(count,len(rt['requests']))

    def test_invalid_api_deep_updates_rejected(self):
        class Bad:
            network=False
            def review(self,p):return {'approach':'defend','alignment':'A','reason':'override'}
        a=self.person('opposition');self.notice(a);before=deep(self.sim)
        self.sim.run(2,AgendaProvider(Bad()));self.assertEqual(before,deep(self.sim))
        self.assertEqual(self.sim.agenda_runtime['requests'][0]['status'],'rejected')
        self.assertFalse(self.sim.apply(self.sim.propose(a.id,dict(type='agenda_response',issue='appointment',approach='question',alignment='A'))))

    def test_review_budget_pauses_no_silent_fallback(self):
        self.sim.behavior_profile['agenda_dynamics']['total_review_limit']=0
        self.notice(self.person('opposition'))
        with self.assertRaises(agenda.ReviewBudgetExceeded):self.sim.run(2)
        self.assertEqual(len(self.sim.agenda_runtime['requests']),0)
        self.sim.behavior_profile['agenda_dynamics']['total_review_limit']=10;self.sim.run(2)
        self.assertEqual(len(self.sim.agenda_runtime['requests']),1)

    def test_snapshot_restores_pending_review_and_cache(self):
        self.notice(self.person('opposition'))
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'s.json';self.sim.save(p);other=Simulation.load(p)
            self.sim.run(200);other.run(200)
            q=Path(td)/'q.json';self.sim.save(p);other.save(q)
            self.assertEqual(p.read_bytes(),q.read_bytes())

    def test_http_adapter_mocked_no_real_network_or_saved_key(self):
        a=self.person('opposition');self.notice(a)
        reply=agenda.ReferenceAdvisor().review(agenda.packet(a,agenda.state(a)['appointment']))
        response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps({'choices':[{'message':{'content':json.dumps(reply)}}],
            'usage':{'prompt_tokens':120,'completion_tokens':30,'total_tokens':150}}).encode()
        adapter=OpenAICompatibleAdvisor('https://example.invalid/v1/chat/completions','test-model')
        with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'not-a-real-key'}),patch('society.agenda_api.urlopen',return_value=response) as transport:
            self.sim.run(2,AgendaProvider(adapter));self.assertEqual(transport.call_count,1)
        self.assertEqual(self.sim.agenda_runtime['requests'][0]['usage']['total_tokens'],150)
        self.assertNotIn('not-a-real-key',json.dumps(self.sim.agenda_runtime))

    def test_no_daily_requests_without_important_agenda(self):
        sim=Simulation();session=Session(sim);reports=session.days(3)
        self.assertEqual(reports[-1]['time'],4319)
        self.assertEqual(reports[-1]['reviews']['attempts'],0)
        self.assertEqual(sim.agenda_runtime['requests'],[])


if __name__=='__main__':unittest.main()
