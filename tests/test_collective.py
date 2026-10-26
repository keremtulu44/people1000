"""No fitted rates: causal separation, actual presence, budgets and local knowledge."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from society import collective, dynamics
from society.behavior import load_v31_profile as load_profile, load_v3_profile, load_legacy_profile
from society.engine import Config, Simulation, BaselineProvider


class Wait:
    def decide(self, observation):
        return {'type':'wait'}


class CollectiveContracts(unittest.TestCase):
    def setUp(self):
        self.sim=Simulation(behavior_profile=load_profile());self.sim.run(0,Wait())
        self.a=self.sim.agents['A0001']
        self.b=self.sim.agents['A0002']
        if not self.sim.edge(self.a.id,self.b.id):
            self.sim.edges.append(dict(source=self.a.id,target=self.b.id,type='close',trust=.9,latency=10))

    def apply(self,aid,**proposal):
        return self.sim.apply(self.sim.propose(aid,proposal))

    def meeting(self):
        self.assertTrue(self.apply(self.a.id,type='create_gathering',place='square',start=100,end=300))
        return next(iter(self.sim.gatherings))

    def invite(self,gid):
        self.assertTrue(self.apply(self.a.id,type='send',target=self.b.id,text='Invitation, not attendance',gathering_id=gid))
        self.sim.run(99,Wait())

    def test_versions_frozen_and_numeric_coefficients_unchanged(self):
        old=load_v3_profile();new=load_profile()
        self.assertEqual(old['behavior_version'],'3.0.0')
        self.assertEqual(new['behavior_version'],'3.1.0')
        for k in ('groups','dynamics','belief_step'):self.assertEqual(old[k],new[k])
        for profile in (old,load_legacy_profile()):
            sim=Simulation(behavior_profile=profile)
            self.assertFalse(collective.enabled(sim))
            self.assertFalse(sim.apply(sim.propose('A0001',{'type':'withdraw_support'})))

    def test_economic_distress_alone_cannot_change_core(self):
        old=Simulation(behavior_profile=load_v3_profile())
        target=old.agents[self.a.id]
        for day in range(1200):
            self.sim.time=old.time=day*1440
            dynamics.daily(self.sim,self.a,8,'local-personal-expense')
            dynamics.daily(old,target,8,'local-personal-expense')
        self.assertGreater(collective.state(self.a)['distress'],0)
        self.assertEqual(self.a.behavior['core_orientation'],1.)
        self.assertEqual(self.a.behavior['core_changes'],0)
        self.assertGreater(target.behavior['core_changes'],0)
        self.assertEqual(self.a.alignment,'A')
        self.assertFalse(collective.state(self.a)['collective_active'])

    def test_support_withdrawal_is_not_party_or_core_conversion(self):
        before=(self.a.alignment,self.a.private_loyalty,self.a.behavior['core_orientation'],deepcopy(self.a.traits))
        self.assertTrue(self.apply(self.a.id,type='withdraw_support'))
        self.assertEqual(self.a.public_alignment,'none');self.assertEqual(self.a.public_support,0.)
        self.assertEqual(before,(self.a.alignment,self.a.private_loyalty,self.a.behavior['core_orientation'],self.a.traits))
        self.assertEqual(self.a.used['action'],1)

    def test_real_blame_can_cause_autonomous_support_withdrawal_without_conversion(self):
        leader=next(x for x in self.sim.authorities if self.sim.agents[x].alignment=='A')
        if not self.sim.edge(leader,self.a.id):
            self.sim.edges.append(dict(source=leader,target=self.a.id,type='authority',trust=.9,latency=10))
        self.assertTrue(self.apply(leader,type='send',target=self.a.id,text='responsibility',topic='responsibility:A',claim=100))
        self.sim.schedule(1,'price_shock',{'multiplier':1.8});self.sim.run(10*1440)
        self.assertTrue(any(e['kind']=='support_withdrawn' and e['payload']['agent']==self.a.id for e in self.sim.log))
        self.assertEqual(self.a.public_alignment,'none');self.assertEqual(self.a.alignment,'A')
        self.assertEqual(self.a.behavior['core_orientation'],1.)

    def test_invitation_and_registration_are_not_attendance(self):
        gid=self.meeting();self.invite(gid)
        self.assertIn(gid,collective.state(self.b)['known_gatherings'])
        self.assertEqual(self.sim.gatherings[gid]['participants'],[])
        for a in (self.a,self.b):
            self.assertFalse(collective.state(a)['collective_active'])
            self.assertEqual(collective.state(a)['collective_strength'],0)

    def test_solo_has_no_collective_strength_then_actual_join_creates_it(self):
        gid=self.meeting();self.invite(gid);self.sim.run(100,Wait())
        self.assertTrue(self.apply(self.a.id,type='attend_gathering',gathering_id=gid))
        self.assertEqual(collective.state(self.a)['collective_strength'],0)
        self.assertTrue(self.apply(self.b.id,type='attend_gathering',gathering_id=gid))
        for a in (self.a,self.b):
            self.assertTrue(collective.state(a)['collective_active'])
            self.assertEqual(collective.state(a)['visible_participants'],[self.a.id,self.b.id])
            self.assertEqual(a.alignment,'A');self.assertEqual(a.behavior['core_orientation'],1.)

    def test_departure_and_end_remove_strength_but_not_distress(self):
        gid=self.meeting();self.invite(gid);self.sim.run(100,Wait())
        # The first actor used create+send. It can still attend (third action).
        for a in (self.a,self.b):
            self.assertTrue(self.apply(a.id,type='attend_gathering',gathering_id=gid))
            collective.state(a)['distress']=.8
        self.assertTrue(self.apply(self.b.id,type='leave_gathering',gathering_id=gid))
        self.assertFalse(collective.state(self.a)['collective_active'])
        self.assertEqual(collective.state(self.a)['distress'],.8)
        self.sim.run(300,Wait())
        self.assertIsNone(collective.state(self.a)['present_at'])
        self.assertEqual(collective.state(self.a)['distress'],.8)
        self.assertEqual(self.sim.gatherings[gid]['participants'],[])
        self.assertTrue(any(e['kind']=='collective_expression_started' for e in self.sim.log))
        self.assertTrue(any(e['kind']=='collective_expression_ended' for e in self.sim.log))

    def test_non_attendee_cannot_see_headcount_or_unknown_gathering(self):
        gid=self.meeting();self.invite(gid);self.sim.run(100,Wait())
        self.assertTrue(self.apply(self.a.id,type='attend_gathering',gathering_id=gid))
        view=self.sim.observation(self.b.id)
        self.assertNotIn('participants',view['social']['known_gatherings'][gid])
        self.assertEqual(view['social']['visible_participants'],[])
        stranger=next(a for a in self.sim.agents.values() if a.id not in (self.a.id,self.b.id))
        self.assertNotIn(gid,self.sim.observation(stranger.id)['social']['known_gatherings'])
        self.assertFalse(self.apply(stranger.id,type='attend_gathering',gathering_id=gid))

    def test_presence_actions_respect_time_budgets_and_duplicate_guards(self):
        gid=self.meeting()
        with self.assertRaises(ValueError):
            self.sim.schedule(200,'gathering_close',{'gathering_id':gid})
        self.assertFalse(self.apply(self.a.id,type='attend_gathering',gathering_id=gid))
        self.sim.run(100,Wait())
        did=self.sim.propose(self.a.id,{'type':'attend_gathering','gathering_id':gid})
        self.assertTrue(self.sim.apply(did));self.assertFalse(self.sim.apply(did))
        self.assertFalse(self.apply(self.a.id,type='attend_gathering',gathering_id=gid))
        self.sim.config.action_budget=self.a.used['action']
        self.assertFalse(self.apply(self.a.id,type='leave_gathering',gathering_id=gid))
        self.sim.run(300,Wait())
        self.assertIsNone(collective.state(self.a)['present_at'])
        self.assertFalse(self.apply(self.b.id,type='attend_gathering',gathering_id=gid))

    def test_unread_invitation_is_not_knowledge(self):
        gid=self.meeting();self.sim.config.read_budget=0
        self.assertTrue(self.apply(self.a.id,type='send',target=self.b.id,text='invite',gathering_id=gid))
        self.sim.run(100,Wait())
        self.assertNotIn(gid,collective.state(self.b)['known_gatherings'])
        self.assertFalse(self.apply(self.b.id,type='attend_gathering',gathering_id=gid))

    def test_public_metadata_does_not_publish_private_switch(self):
        self.a.alignment='B'
        self.assertEqual(self.a.public_alignment,'A')
        self.assertTrue(self.apply(self.a.id,type='send',target=self.b.id,text='no declaration'))
        message=next(iter(self.sim.messages.values()))
        self.assertEqual(message['source_alignment'],'A')

    def test_character_gates_autonomous_attendance(self):
        gid=self.meeting();self.invite(gid);self.sim.run(100,Wait())
        # A peer invitation is known but cannot manipulate either first-30% group.
        for group in ('power_aligned','opposition'):
            obs=self.sim.observation(self.b.id);obs['group']=group;obs['social']['distress']=1
            obs['traits']['risk_tolerance']=1
            self.assertIsNone(collective.policy(obs))
        obs=self.sim.observation(self.b.id);obs['group']='observer';obs['social']['distress']=1
        self.assertIsNone(collective.policy(obs))
        # Distressed discontented can decide to attend without hidden headcount.
        obs=self.sim.observation(self.b.id);obs['group']='discontented'
        obs['social']['distress']=1;obs['traits']['risk_tolerance']=.6
        self.assertEqual(collective.policy(obs),{'type':'attend_gathering','gathering_id':gid})
        # Quiet managers/wealthy do not follow a peer crowd just because it exists.
        for group in ('authority','wealthy'):
            obs['group']=group;obs['behavior']['dependency_loss']=0
            self.assertIsNone(collective.policy(obs))

    def test_later_trusted_endorsement_is_not_erased_by_peer_invitation(self):
        gid=self.meeting();self.invite(gid);self.sim.run(100,Wait())
        obs=self.sim.observation(self.b.id)
        obs['social']['distress']=1.;obs['traits']['risk_tolerance']=.6
        self.assertIsNone(collective.policy(obs))
        leader=next(x for x in self.sim.authorities if self.sim.agents[x].public_alignment=='A')
        # Unit-level received endorsement; separate tests exercise actual delivery.
        value=collective.invitation(self.sim,self.sim.agents[leader],gid)
        collective.learn(self.sim,self.b,value,'read:trusted-endorsement')
        collective.learn(self.sim,self.b,collective.invitation(self.sim,self.a,gid),'read:peer-repeat')
        obs=self.sim.observation(self.b.id)
        obs['social']['distress']=1.;obs['traits']['risk_tolerance']=.6
        self.assertEqual(collective.policy(obs),{'type':'attend_gathering','gathering_id':gid})
        self.assertEqual(len(obs['social']['known_gatherings'][gid]['endorsements']),2)
        self.assertEqual(self.sim.gatherings[gid]['participants'],[])

    def test_resume_and_replay_actual_presence(self):
        gid=self.meeting();self.invite(gid);self.sim.run(100,Wait())
        self.assertTrue(self.apply(self.a.id,type='attend_gathering',gathering_id=gid))
        # Persist a future action as well as the current solitary state.
        self.sim.schedule(120,'external_action',{'actor':self.b.id,'proposal':{'type':'attend_gathering','gathering_id':gid}})
        full=deepcopy(self.sim)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json';self.sim.save(path);loaded=Simulation.load(path)
            full.run(300,Wait());loaded.run(300,Wait())
        self.assertEqual(full.agents,loaded.agents)
        self.assertEqual(full.gatherings,loaded.gatherings)
        self.assertEqual(full.log,loaded.log)

    def test_invalid_gathering_proposals_rejected_without_state_effects(self):
        before=deepcopy(self.sim.gatherings)
        for p in ({'type':'create_gathering','place':'square','start':True,'end':300},
                  {'type':'create_gathering','place':'square','start':100,'end':100},
                  {'type':'create_gathering','place':'square','start':100,'end':1600},
                  {'type':'attend_gathering','gathering_id':[]},
                  {'type':'send','target':self.b.id,'text':'fake','gathering_id':[]}):
            self.assertFalse(self.sim.apply(self.sim.propose(self.a.id,p)))
        self.assertEqual(before,self.sim.gatherings)
        self.assertEqual(self.a.used['action'],0)


if __name__=='__main__':unittest.main()
