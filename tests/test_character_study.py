"""Measurement/reproducibility tests, not claims of social realism."""
from copy import deepcopy
import math
from pathlib import Path
import tempfile
import unittest

from society.character_study import catalog, jobs, setup, advance, observations, world, digest, run_case
from society.engine import Simulation
from society.behavior import load_profile


class CharacterStudyTests(unittest.TestCase):
    def case(self,name):return next(c for c in catalog() if c['name']==name)

    def test_catalog_jobs_unique_and_all_six_groups_retained(self):
        all_=list(jobs())
        keys=[(c['name'],s,n,m,d) for c,s,n,m,d in all_]
        self.assertEqual(len(keys),len(set(keys)))
        self.assertEqual(len(catalog()),55);self.assertEqual(len(keys),508)
        sim=setup(self.case('none'))
        self.assertEqual({g:sum(a.initial_group==g for a in sim.agents.values()) for g in load_profile()['groups']},
                         {g:v['population_percent'] for g,v in load_profile()['groups'].items()})

    def test_common_world_equal_across_models_and_source_arms(self):
        before=load_profile()
        base=[digest(world(setup(self.case('sudden60'),model=m))) for m in ('v2','v3.0','v3.1')]
        self.assertEqual(len(set(base)),1)
        probes=[digest(world(setup(c))) for c in catalog() if c['family']=='source']
        self.assertEqual(len(set(probes)),1)
        self.assertEqual(before,load_profile())

    def test_equal_cost_pair_really_matches_but_history_differs(self):
        a=setup(self.case('ramp60'));b=setup(self.case('late_equal_cost60'))
        advance(a,10*1440-1);advance(b,10*1440-1)
        self.assertGreater(a.agents['A0001'].losses,b.agents['A0001'].losses)
        advance(a,30*1440-1);advance(b,30*1440-1)
        self.assertTrue(math.isclose(a.price,b.price,abs_tol=1e-12))
        self.assertTrue(math.isclose(sum(x.losses for x in a.agents.values()),sum(x.losses for x in b.agents.values()),abs_tol=1e-8))

    def test_plan_inputs_and_bindings_survive_resume(self):
        sim=setup(self.case('crowd-support-loss'));advance(sim,2000);full=deepcopy(sim)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json';sim.save(path);loaded=Simulation.load(path)
            advance(full,30*1440-1);advance(loaded,30*1440-1)
        self.assertEqual(full.agents,loaded.agents);self.assertEqual(full.log,loaded.log)
        self.assertEqual(full.protocol,loaded.protocol)

    def test_actual_samples_not_final_state_backfill_and_legacy_missing_is_null(self):
        sim=setup(self.case('sudden60'));advance(sim,1439)
        early=list(observations(sim,0));self.assertTrue(all(x['losses']==0 for x in early))
        advance(sim,30*1440-1)
        self.assertTrue(all(x['losses']==0 for x in early))
        self.assertGreater(sum(x.losses for x in sim.agents.values()),0)
        old=setup(self.case('none'),model='v2');advance(old,1439)
        self.assertTrue(all(x['distress'] is None for x in observations(old,0)))

    def test_raw_export_schema_and_causal_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=run_case(self.case('crowd-two'),days=3,raw_root=Path(tmp))
        r=result['run']
        self.assertEqual(len(result['groups']),6)
        self.assertTrue(r['transitions_accessible']);self.assertTrue(r['frozen_traits'])
        self.assertEqual(r['attended'],2);self.assertEqual(r['solo_expression_errors'],0)
        self.assertTrue(r['closed_gatherings_clear'])
        self.assertTrue(all(v['sha256'] for v in result['files'].values()))


class CharacterFollowupTests(unittest.TestCase):
    def test_mirror_changes_direction_not_personality_or_world(self):
        from society.character_study_followup import prepared, specifications
        c,s,mode,model=specifications()[0]
        main=setup(c,s);mirror=prepared(c,s,'mirror',model)
        self.assertEqual(digest(world(main)),digest(world(mirror)))
        p=mirror.protocol['character_study']
        self.assertTrue(all(mirror.agents[a].public_alignment=='B' for a in p['B_anchors']))
        self.assertTrue(any(x.get('proposal',{}).get('topic')=='responsibility:B' for x in p['plan']))
        self.assertFalse(any(x.get('proposal',{}).get('topic')=='responsibility:A' for x in p['plan']))

    def test_dual_keeps_one_shock_but_doubles_campaign_inputs(self):
        from society.character_study_followup import prepared, specifications
        self.assertEqual(len(specifications()),104)
        c=next(c for c in catalog() if c['name']=='i80-A-positive')
        a=setup(c);b=prepared(c,0,'dual','v3.1')
        pp=a.protocol['character_study']['plan'];qq=b.protocol['character_study']['plan']
        self.assertEqual(sum(x['kind']=='price_shock' for x in qq),1)
        self.assertEqual(sum(x['kind']=='action' for x in qq),2*sum(x['kind']=='action' for x in pp))


if __name__=='__main__':unittest.main()
