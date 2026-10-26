"""v3.2 causal contracts; assertions are not fitted switching-rate targets."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from society import characters, collective, dynamics
from society.behavior import load_v32_profile as load_profile, load_v31_profile, validate_profile
from society.engine import Simulation, Config, BaselineProvider


class Wait:
    def decide(self, observation):return {'type':'wait'}


class CharacterContracts(unittest.TestCase):
    def setUp(self):
        self.sim=Simulation(behavior_profile=load_profile());self.sim.run(0,Wait())

    def person(self, group):return next(a for a in self.sim.agents.values() if a.initial_group==group)

    def apply(self,a,**p):return self.sim.apply(self.sim.propose(a.id,p))

    def connect(self,a,b):
        if not self.sim.edge(a.id,b.id):
            self.sim.edges.append(dict(source=a.id,target=b.id,type='close',trust=.9,latency=1))

    def test_profile_freeze_and_six_distinct_groups(self):
        old,new=load_v31_profile(),load_profile()
        self.assertEqual(old['behavior_version'],'3.1.0');self.assertEqual(new['behavior_version'],'3.2.0')
        for key in ('groups','dynamics','belief_step'):self.assertEqual(old[key],new[key])
        self.assertFalse(characters.enabled(Simulation(behavior_profile=old)))
        self.assertEqual(sum(a.initial_group=='observer' for a in self.sim.agents.values()),3)

    def test_character_config_requires_dependencies_and_finite_parameters(self):
        for key,value in [('study_step',2),('adaptation_days',0),('competition_transfer',float('nan'))]:
            p=load_profile();p['character_dynamics'][key]=value
            with self.assertRaises(ValueError):validate_profile(p)
        p=load_profile();p.pop('social_model')
        with self.assertRaises(ValueError):validate_profile(p)

    def test_managers_and_observers_quarantine_both_sides(self):
        for group in ('authority','observer'):
            a=self.person(group);before=deepcopy(a.beliefs)
            for pole in ('A','B'):
                source=next(x for x in self.sim.agents.values() if x.initial_group=='authority' and x.alignment==pole and x.id!=a.id)
                self.connect(source,a)
                self.assertTrue(self.apply(source,type='send',target=a.id,text='Untrusted promise',topic='benefit:B:economic_security',claim=100))
            self.sim.run(self.sim.time+(1440 if group=='observer' else 200),Wait())
            self.assertEqual(a.beliefs,before)
            self.assertEqual(len(characters.state(a)['signals']),2)
            self.assertFalse(a.behavior.get('appraisal',{}).get('benefit_sources',{}))

    def test_observer_sparse_contacts_and_read_send_caps(self):
        obs=self.person('observer')
        self.assertLessEqual(sum(e['target']==obs.id for e in self.sim.edges),1)
        self.assertEqual(characters.limit(self.sim,obs,'read',6),1)
        sources=[a for a in self.sim.agents.values() if a.id!=obs.id][:2]
        for a in sources:
            self.connect(a,obs);self.assertTrue(self.apply(a,type='send',target=obs.id,text='claim',claim=100))
        self.sim.run(200,Wait());self.assertEqual(obs.used['read'],1);self.assertEqual(len(obs.inbox),1)
        target=self.sim.agents[self.sim.observation(obs.id)['contacts'][0]]
        self.assertTrue(self.apply(obs,type='send',target=target.id,text='one'))
        self.assertFalse(self.apply(obs,type='send',target=target.id,text='two'))

    def test_development_is_heterogeneous_bounded_once_per_day(self):
        observers=[a for a in self.sim.agents.values() if a.initial_group=='observer']
        self.assertEqual(len({characters.state(a)['development'] for a in observers}),3)
        a=observers[0];old=characters.state(a)['development']
        self.assertTrue(self.apply(a,type='self_study'));self.assertFalse(self.apply(a,type='self_study'))
        self.assertGreater(characters.state(a)['development'],old)
        self.assertLessEqual(characters.state(a)['development'],1)
        other=self.person('power_aligned');self.assertFalse(self.apply(other,type='self_study'))

    def test_study_requires_later_personal_outcome_and_expires(self):
        a=self.person('observer');s=characters.state(a)
        s['signals']['f']={'topic':'economic_outlook','claim':0,'learned_at':1,'source':'test','message_id':'f'}
        self.sim.time=2;characters.apply(self.sim,a,{'type':'self_study'},'study')
        self.assertFalse(s['source_assessments'])
        self.sim.time=1440;a.memories.append({'type':'direct_experience','expense':a.expense*10,'income':a.income,'learned_at':1440})
        characters.apply(self.sim,a,{'type':'self_study'},'study')
        self.assertEqual(s['source_assessments']['test']['confidence'],0)
        first=deepcopy(s['source_assessments']);self.sim.time=2880
        characters.apply(self.sim,a,{'type':'self_study'},'study');self.assertEqual(first,s['source_assessments'])
        s['signals']['expired']={'topic':'economic_outlook','claim':100,'learned_at':0,'source':'expired','message_id':'expired'}
        self.sim.time=9*1440;characters.apply(self.sim,a,{'type':'self_study'},'study')
        self.assertNotIn('expired',s['source_assessments'])

    def test_institutional_contest_conserves_power_costs_and_cooldown(self):
        a=self.person('authority');rival=next(x for x in self.sim.agents.values() if x.initial_group=='authority' and x.id!=a.id)
        a.behavior['known'][rival.id]={'pole':rival.public_alignment,'group':'authority','trust':.5}
        before=sum(x['institutional_power'] for x in self.sim.authorities.values());cash=a.savings;party=a.alignment
        self.assertTrue(self.apply(a,type='compete_position',target=rival.id))
        self.assertAlmostEqual(sum(x['institutional_power'] for x in self.sim.authorities.values()),before)
        self.assertEqual(a.savings,cash-2);self.assertEqual(a.alignment,party)
        self.assertFalse(self.apply(a,type='compete_position',target=rival.id))
        self.assertEqual(characters.state(rival)['rival_actions'][a.id]['role'],'challenged')
        self.assertNotIn('authorities',self.sim.observation(a.id))

    def test_contest_role_knowledge_and_resource_preconditions(self):
        a=self.person('authority');rival=next(x for x in self.sim.authorities if x!=a.id)
        a.behavior['known'].pop(rival,None)
        self.assertFalse(self.apply(a,type='compete_position',target=rival))
        a.behavior['known'][rival]={'group':'authority','pole':'A','trust':.5};a.savings=0
        self.assertFalse(self.apply(a,type='compete_position',target=rival))
        self.assertFalse(self.apply(self.person('wealthy'),type='compete_position',target=rival))

    def test_autonomous_rivalry_and_inward_study(self):
        self.sim.run(8*1440)
        self.assertTrue(any(e['kind']=='institutional_competition' for e in self.sim.log))
        self.assertTrue(any(e['kind']=='self_development' for e in self.sim.log))
        for a in self.sim.agents.values():
            if a.initial_group in ('authority','observer'):self.assertEqual(a.behavior['switch_count'],0)
        self.assertTrue(any(e['kind']=='decision_appraisal' for e in self.sim.log))

    def test_sudden_vs_gradual_nonprice_and_accumulated_wear(self):
        a=self.person('discontented');b=next(x for x in self.sim.agents.values() if x.initial_group=='discontented' and x.id!=a.id)
        for day in range(91):
            self.sim.time=day*1440
            for person,level in ((a,0 if day<90 else .3),(b,.3*day/90)):
                characters.disruption(self.sim,person,'supply',level,'local')
                characters.temporal(self.sim,person,person.expense,0,'receipt')
        x=characters.state(a)['domains']['supply'];y=characters.state(b)['domains']['supply']
        self.assertGreater(x['surprise'],y['surprise']);self.assertGreater(y['fatigue'],x['fatigue'])
        self.assertEqual(a.losses,0);self.assertEqual(b.losses,0)
        fatigue=y['fatigue']
        for day in range(91,121):
            self.sim.time=day*1440;characters.temporal(self.sim,b,b.expense,0,'receipt')
        self.assertGreater(y['fatigue'],fatigue)

    def test_nonprice_disruption_is_local_immediate_not_blame_or_money(self):
        a=self.person('discontented');other=self.person('opposition');cash=a.savings
        self.sim.schedule(1,'local_disruption',{'target':a.id,'domain':'transport','severity':.6})
        self.sim.run(1,Wait())
        self.assertGreater(collective.state(a)['distress'],0);self.assertEqual(a.savings,cash)
        self.assertNotIn('transport',characters.state(other)['domains'])
        self.assertEqual(a.behavior['appraisal']['responsibility_current'],0)
        with self.assertRaises(ValueError):self.sim.schedule(2,'local_disruption',{'target':a.id,'domain':'living_cost','severity':1})

    def meetings(self,purpose1=None,purpose2=None):
        a=self.person('power_aligned');b=self.person('opposition')
        for person,purpose,end in ((a,purpose1,300),(b,purpose2,400)):
            self.assertTrue(self.apply(person,type='create_gathering',place='square',start=100,end=end,purpose=purpose))
        self.sim.run(100,Wait());gids=list(self.sim.gatherings)
        for person,gid in zip((a,b),gids):self.assertTrue(self.apply(person,type='attend_gathering',gathering_id=gid,participation='support'))
        return a,b,gids

    def test_opposing_crowds_see_without_joining_or_coalition(self):
        a,b,gids=self.meetings('support:A','support:B')
        for person in (a,b):
            s=collective.state(person);self.assertEqual(s['visible_participants'],sorted([a.id,b.id]))
            self.assertFalse(s['collective_active']);self.assertEqual(s['collective_strength'],0)
            self.assertEqual(s['supporting_participants'],[person.id])
        self.assertEqual(a.alignment,'A');self.assertEqual(b.alignment,'B')
        self.assertEqual(collective.state(a)['present_at'],gids[0]);self.assertEqual(collective.state(b)['present_at'],gids[1])
        self.assertNotIn(gids[1],collective.state(a)['known_gatherings'])
        self.sim.run(300,Wait());self.assertEqual(collective.state(b)['visible_participants'],[b.id])
        self.assertEqual(collective.state(a)['visible_participants'],[])

    def test_explicit_shared_purpose_strength_not_party_change(self):
        a,b,_=self.meetings('lower_cost','lower_cost')
        self.assertTrue(collective.state(a)['collective_active']);self.assertTrue(collective.state(b)['collective_active'])
        self.assertEqual(a.alignment,'A');self.assertEqual(b.alignment,'B')
        self.sim.run(400,Wait())
        self.assertEqual(collective.state(b)['supporting_participants'],[])

    def test_unspecified_purposes_do_not_merge(self):
        a,b,_=self.meetings()
        self.assertEqual(len(collective.state(a)['visible_participants']),2)
        self.assertFalse(collective.state(a)['collective_active'])

    def test_silence_withdrawal_restoration_do_not_change_core_or_camp(self):
        a=self.person('power_aligned');s=characters.state(a)
        self.assertEqual(characters.policy(self.sim.observation(a.id))[1],'no_current_personal_distress')
        a.private_loyalty=.4;s['verified_failures']=['personally_checked']
        self.assertEqual(characters.policy(self.sim.observation(a.id))[0],{'type':'withdraw_support'})
        self.assertTrue(self.apply(a,type='withdraw_support'));self.assertEqual(a.alignment,'A')
        a.private_loyalty=.8
        self.assertNotEqual(characters.policy(self.sim.observation(a.id))[1],'support_recovery_from_personal_evidence')
        s['verified_recoveries']=['later_checked']
        proposal,reason=characters.policy(self.sim.observation(a.id));self.assertEqual(reason,'support_recovery_from_personal_evidence')
        self.assertTrue(self.sim.apply(self.sim.propose(a.id,proposal)))
        self.assertEqual(a.public_alignment,'A');self.assertEqual(a.behavior['core_orientation'],1)

    def test_endogenous_organizing_requires_read_peer_interest(self):
        a=self.person('discontented');a.traits['risk_tolerance']=1.
        collective.state(a)['distress']=.8
        self.assertNotEqual(characters.policy(self.sim.observation(a.id))[0]['type'],'create_gathering')
        peer=next(x for x in self.sim.agents.values() if x.initial_group=='discontented' and x.id!=a.id)
        self.connect(peer,a)
        self.assertTrue(self.apply(peer,type='send',target=a.id,text='own experience',topic='grievance',claim=80))
        self.sim.run(200,Wait())
        proposal,reason=characters.policy(self.sim.observation(a.id))
        self.assertEqual(proposal['type'],'create_gathering')
        self.assertEqual(reason,'seek_actual_gathering_after_local_grievance')
        self.assertTrue(self.sim.apply(self.sim.propose(a.id,proposal)))
        self.sim.run(201)
        self.assertTrue(any('gathering' in m for m in self.sim.messages.values()))
        self.assertEqual(next(iter(self.sim.gatherings.values()))['participants'],[])
        self.assertLessEqual(a.used['communication'],self.sim.config.communication_budget)
        self.assertLessEqual(a.used['action'],self.sim.config.action_budget)

    def test_physical_attendance_is_not_automatically_endorsement(self):
        a=self.person('power_aligned');b=self.person('opposition')
        self.assertTrue(self.apply(a,type='create_gathering',place='square',start=100,end=300,purpose='policy'))
        gid=next(iter(self.sim.gatherings))
        self.connect(a,b);self.assertTrue(self.apply(a,type='send',target=b.id,text='public invitation',gathering_id=gid))
        self.sim.run(100,Wait())
        self.assertTrue(self.apply(a,type='attend_gathering',gathering_id=gid))
        self.assertTrue(self.apply(b,type='attend_gathering',gathering_id=gid))
        self.assertEqual(collective.state(a)['visible_participants'],sorted([a.id,b.id]))
        self.assertEqual(self.sim.gatherings[gid]['supporters'],[])
        self.assertFalse(collective.state(a)['collective_active'])
        self.assertEqual(a.public_alignment,'A');self.assertEqual(b.public_alignment,'B')

    def test_daily_silence_is_recorded_without_provider_call(self):
        a=self.person('power_aligned')
        records=[e for e in self.sim.log if e['kind']=='daily_response_appraisal' and e['payload']['agent']==a.id]
        self.assertEqual(records[-1]['payload']['reason'],'no_current_personal_distress')
        self.assertEqual(characters.state(a)['decision_reason'],'no_current_personal_distress')

    def test_correct_forecast_is_not_itself_material_recovery(self):
        a=self.person('power_aligned');source=next(iter(a.behavior['trust']))
        a.behavior['known'][source]['pole']=a.alignment
        a.behavior['harm']=.6;characters.state(a)['last_physical_harm']=.6
        change={'source':source,'old':.4,'new':.5,'message_id':'checked'}
        characters.track_trust(a,[change]);self.assertFalse(characters.state(a)['verified_recoveries'])
        a.behavior['harm']=.2;characters.track_trust(a,[change])
        self.assertEqual(characters.state(a)['verified_recoveries'],['checked'])

    def test_save_load_exact_continuation_and_no_network_resampling(self):
        self.sim.schedule(1,'local_disruption',{'target':self.person('discontented').id,'domain':'supply','severity':.3})
        self.sim.run(1440)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'state.json';self.sim.save(path);other=Simulation.load(path)
            self.assertEqual(self.sim.edges,other.edges)
            self.sim.run(4*1440);other.run(4*1440)
            self.sim.save(path);second=Path(td)/'second.json';other.save(second)
            self.assertEqual(path.read_bytes(),second.read_bytes())


if __name__=='__main__':unittest.main()
