"""Diagnosis changes observability, not default behavioral coefficients."""
from copy import deepcopy
from dataclasses import asdict
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from society.behavior import load_legacy_profile as load_profile
from society.diagnosis import setup, measure
from society.engine import Config, Simulation
from society.experiments import make_run


class DiagnosisContracts(unittest.TestCase):
    def test_ablation_validation(self):
        with self.assertRaises(ValueError):Config(ablation='unknown')

    def test_all_arms_have_identical_initial_agents_and_topology(self):
        hashes=[]
        for shock in ('none','mild','moderate','severe'):
            for ablation in ('none','economic_evidence','peer','trust_erosion'):
                sim,h=setup(3,100,shock,True,ablation)
                hashes.append(h)
        self.assertEqual(len(set(hashes)),1)

    def test_instrumentation_matches_archived_behavior_when_available(self):
        path=Path('runs/behavior/n100-s0-B-d30/state.json.gz')
        if not path.exists():self.skipTest('Historical raw artifact absent; regenerate previous experiment suite')
        with gzip.open(path,'rt') as f:old=json.load(f)
        current,_,_=make_run(0,100,'B',30)
        def projection(agent):
            a=deepcopy(agent)
            a['behavior']={k:v for k,v in a['behavior'].items() if not k.startswith('diagnostic_')}
            return a
        for aid,a in current.agents.items():
            self.assertEqual(projection(asdict(a)),projection(old['agents'][aid]))
        old_switches=[(e['time'],e['payload']['agent'],e['payload']['old'],e['payload']['new']) for e in old['log'] if e['kind']=='alignment_changed']
        new_switches=[(e['time'],e['payload']['agent'],e['payload']['old'],e['payload']['new']) for e in current.log if e['kind']=='alignment_changed']
        self.assertEqual(old_switches,new_switches)

    def test_transition_explanation_is_contemporaneous_and_balanced(self):
        sim,_=setup(2,100,'severe',True)
        sim.run(43199)
        events=[e for e in sim.log if e['kind']=='alignment_changed']
        self.assertTrue(events)
        for e in events:
            p=e['payload'];d=p['diagnostic']
            self.assertAlmostEqual(sum(d['accumulated_components'].values()),p['accumulated_evidence'])
            self.assertAlmostEqual(d['decision_score'],p['accumulated_evidence']*p['attraction'])
            self.assertGreater(d['decision_score'],p['threshold'])
            self.assertGreaterEqual(d['elapsed_days'],d['cooldown_days'])
            self.assertTrue(all(m['learned_at']<=e['time'] for m in d['messages_learned']))
            self.assertEqual(d['before']['alignment'],p['old'])
            self.assertEqual(d['cause_event_id'],e['caused_by'])
            self.assertLessEqual(d['economic']['first_harm_at'],e['time'])
            self.assertEqual(d['initial_group'],sim.agents[p['agent']].initial_group)

    def test_economic_ablation_retains_personal_experience(self):
        sim,h=setup(1,100,'severe',True,'economic_evidence')
        sim.run(43199)
        self.assertTrue(all(a.behavior['burden']>0 for a in sim.agents.values()))
        self.assertTrue(any(a.private_loyalty!=.5 for a in sim.agents.values()))
        self.assertTrue(all(a.behavior['diagnostic_evidence_components']['economic']==0 for a in sim.agents.values()))
        self.assertTrue(all(a.losses>0 for a in sim.agents.values()))

    def test_trust_ablation_disables_only_erosion_and_keeps_messages(self):
        sim,_=setup(4,100,'severe',True,'trust_erosion');sim.run(43199)
        updates=[e for e in sim.log if e['kind']=='trust_updated']
        self.assertTrue(updates)
        self.assertTrue(all(e['payload']['new']>=e['payload']['old'] for e in updates))
        self.assertTrue(sim.messages)
        self.assertTrue(any(a.behavior['forecasts'] for a in sim.agents.values()))

    def test_peer_ablation_has_positive_control(self):
        enabled,_=setup(3,100,'severe',True,'none',True)
        disabled,_=setup(3,100,'severe',True,'peer',True)
        enabled.run(43199);disabled.run(43199)
        self.assertTrue(any(sum(a.behavior['peer_pull'].values())>0 for a in enabled.agents.values()))
        self.assertTrue(all(sum(a.behavior['peer_pull'].values())==0 for a in disabled.agents.values()))
        self.assertEqual(len(enabled.messages),len(disabled.messages))

    def test_explanations_survive_resume_and_repeat(self):
        sim,_=setup(5,100,'severe',True)
        full=deepcopy(sim)
        full.run(43199);sim.run(20000)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json';sim.save(path);sim=Simulation.load(path);sim.run(43199)
        self.assertEqual(full.log,sim.log)
        self.assertEqual(full.agents,sim.agents)

    def test_no_shock_is_not_silently_treated_as_a_shock(self):
        sim,_=setup(0,100,'none',False);sim.run(43199)
        self.assertEqual(sim.price,1.)
        self.assertFalse(any(e['kind']=='alignment_changed' for e in sim.log))
        self.assertTrue(all(a.losses==0 for a in sim.agents.values()))

    def test_profile_not_modified_by_setup_or_execution(self):
        before=load_profile()
        sim,_=setup(6,100,'moderate',True,'economic_evidence');sim.run(43199)
        self.assertEqual(before,load_profile())
        self.assertEqual(before,sim.behavior_profile)

    def test_audit_exposes_existing_float_boundary_without_calibrating_it(self):
        # Evidence test for an explicitly documented current numerical limitation,
        # not a claim that strict binary-float comparison is the desired policy.
        sim,_=setup(0,100,'mild',True);sim.run(3*1440-1)
        updates=[e for e in sim.log if e['kind']=='trust_updated']
        self.assertTrue(updates)
        self.assertTrue(all(.1 < e['payload']['error'] < .1+1e-12 for e in updates))
        self.assertTrue(any(e['payload']['new']<e['payload']['old'] for e in updates))
        self.assertFalse(any(e['kind']=='alignment_changed' for e in sim.log))


if __name__=='__main__':unittest.main()
