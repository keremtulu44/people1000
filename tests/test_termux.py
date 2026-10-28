from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,MagicMock

from society.termux import (create_pilot,report,turkce_ozet,ask_operator,main,
    init_scenario_chain,start_scenario,advance_scenario_day,advance_scenario_days)
from society.agenda import ReferenceAdvisor
from society.agenda_api import AgendaProvider,OpenAICompatibleAdvisor
from society.session import Session


class TermuxPilotTests(unittest.TestCase):
    def test_offline_pilot_advances_without_key_and_preserves_agenda_scope(self):
        sim=create_pilot();session=Session(sim,AgendaProvider(ReferenceAdvisor()))
        session.days(7)
        self.assertEqual(sim.agenda_runtime['network_requests'],0)
        self.assertLessEqual(len(sim.agenda_runtime['requests']),30)
        for aid in sim.protocol['termux_pilot']['targets']:
            self.assertEqual(sim.agents[aid].behavior['agenda']['appointment']['qualification'],1)
        self.assertEqual(sum(a.behavior['switch_count'] for a in sim.agents.values()),0)
        summary=turkce_ozet(sim)
        for label in ('İktidar Yanlıları','Muhalifler','Yöneticiler','Zenginler','Hoşnutsuz Kesim','Gözlemciler','GENEL ÖZETİ'):
            self.assertIn(label,summary)

    def test_offline_question_is_not_a_paid_request(self):
        sim=create_pilot();msg=ask_operator(sim,'Ne oldu?',ReferenceAdvisor())
        self.assertIn('Çevrimdışı',msg)
        self.assertEqual(sim.protocol['termux_pilot']['question_attempts'],0)

    def test_mocked_question_reads_report_only_and_does_not_save_key(self):
        sim=create_pilot();before=deepcopy(sim.agents)
        adapter=OpenAICompatibleAdvisor('https://example.invalid/v1/chat/completions','model')
        response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps({'choices':[{'message':{'content':'Henüz gündem öğrenilmedi.'}}],
            'usage':{'total_tokens':50}}).encode()
        with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'dummy-private-key'}),patch('society.termux.urlopen',return_value=response) as request:
            self.assertIn('Henüz',ask_operator(sim,'Ne oldu?',adapter));self.assertEqual(request.call_count,1)
        self.assertEqual(before,sim.agents)
        self.assertEqual(sim.protocol['termux_pilot']['question_attempts'],1)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'s.json';sim.save(path);self.assertNotIn('dummy-private-key',path.read_text())

    def test_failed_question_counts_once_and_limit_prevents_next_request(self):
        sim=create_pilot();sim.protocol['termux_pilot']['question_limit']=1
        adapter=OpenAICompatibleAdvisor('https://example.invalid/v1/chat/completions','model')
        with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'dummy'}),patch('society.termux.urlopen',side_effect=OSError('error')) as request:
            with self.assertRaises(RuntimeError):ask_operator(sim,'Rapor?',adapter)
            with self.assertRaises(RuntimeError):ask_operator(sim,'Yeniden?',adapter)
            self.assertEqual(request.call_count,1)
        self.assertEqual(sim.protocol['termux_pilot']['question_log'][0]['status'],'failed')

    def test_interactive_offline_checkpoint_resume(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'s.json'
            with patch('sys.argv',['termux','--offline','--state',str(path)]),patch('builtins.input',side_effect=['gun','cik']),patch('builtins.print'):
                main()
            first=json.loads(path.read_text());self.assertEqual(first['time'],1439)
            with patch('sys.argv',['termux','--offline','--state',str(path)]),patch('builtins.input',side_effect=['gun','cik']),patch('builtins.print'):
                main()
            second=json.loads(path.read_text());self.assertEqual(second['time'],2879)

    def test_philosophy_scenario_chains_and_guardrails(self):
        sim=create_pilot();adv=ReferenceAdvisor()
        # 1. Ordinary issue: never produces detentions, attacks, deaths or suicides across 10 days.
        ch1=init_scenario_chain(sim,'Belediye park düzenlemesi ve müdür ataması tartışması')
        self.assertEqual(ch1['tier'],'ordinary')
        outs1=advance_scenario_days(sim,adv,10)
        self.assertEqual(len(outs1),10);self.assertEqual(ch1['day'],10)
        self.assertEqual(ch1['conditions']['detained_individuals'],0)
        self.assertFalse(ch1['conditions']['singular_tragedy_occurred'])
        self.assertEqual(ch1['conditions']['aftershock_stage'],'none')
        # 2. Institutional crisis: no arrests on day 1-2, targeted investigation on day 3-4, scapegoat on day 5+, never attacks/suicides.
        ch2=init_scenario_chain(sim,'Büyük ihale yolsuzluğu iddiası ve yayın yasağı')
        self.assertEqual(ch2['tier'],'institutional_crisis')
        advance_scenario_days(sim,adv,2)
        self.assertEqual(ch2['conditions']['detained_individuals'],0)
        advance_scenario_days(sim,adv,2)
        self.assertEqual(ch2['conditions']['detained_individuals'],1)
        self.assertEqual(ch2['conditions']['prosecution_fear'],'high')
        advance_scenario_days(sim,adv,6)
        self.assertTrue(ch2['conditions']['scapegoat_isolated'])
        self.assertFalse(ch2['conditions']['singular_tragedy_occurred'])
        self.assertEqual(ch2['conditions']['aftershock_stage'],'none')
        # 3. Severe security crisis: 10-day progression with causal phases, 3 wealthy sub-factions, awake observer, and no 0-100 score.
        ch3=init_scenario_chain(sim,'Bir okula silahlı saldırı yapıldı, 25 ölü var')
        self.assertEqual(ch3['tier'],'severe_security_crisis')
        for k,v in ch3['conditions'].items():
            if k!='detained_individuals':self.assertNotIsInstance(v,(int,float) if not isinstance(v,bool) else ())
        d1=advance_scenario_day(sim,adv)
        self.assertEqual(ch3['conditions']['detained_individuals'],0)
        self.assertFalse(ch3['conditions']['singular_tragedy_occurred'])
        for label in ('A Kutbu Yanlısı','B Kutbu Yanlısı','Tarafsız / Ticari','aynı tiyatroyu oynuyor'):
            self.assertIn(label,d1)
        advance_scenario_days(sim,adv,2)  # Days 2-3: leak + foiled attempt
        self.assertTrue(ch3['conditions']['leak_occurred'])
        self.assertEqual(ch3['conditions']['aftershock_stage'],'foiled_attempt')
        advance_scenario_day(sim,adv)     # Day 4: 2 media/wealthy actors detained, high fear
        self.assertEqual(ch3['conditions']['detained_individuals'],2)
        self.assertEqual(ch3['conditions']['prosecution_fear'],'high')
        advance_scenario_day(sim,adv)     # Day 5: aftershock occurs due to unaddressed security gap
        self.assertEqual(ch3['conditions']['aftershock_stage'],'aftershock_occurred')
        advance_scenario_days(sim,adv,2)  # Days 6-7: scapegoat isolated
        self.assertTrue(ch3['conditions']['scapegoat_isolated'])
        self.assertTrue(ch3['conditions']['singular_tragedy_occurred'])
        advance_scenario_days(sim,adv,3)  # Days 8-10: security measures contain further attacks
        self.assertEqual(ch3['conditions']['aftershock_stage'],'contained')
        self.assertFalse(ch3['conditions']['unaddressed_neglect'])
        self.assertEqual(ch3['day'],10)

    def test_live_scenario_failure_is_atomic_and_live_prompt_matches_offline_engine(self):
        sim_live = create_pilot(seed=44)
        # Seed a completed 3-day crisis so institutional memory imprinting would trigger if non-atomic
        init_scenario_chain(sim_live, 'Büyük ihale yolsuzluğu ve yayın yasağı')
        advance_scenario_days(sim_live, ReferenceAdvisor(), 3)
        snap_before = deepcopy({
            'time': sim_live.time,
            'agents': sim_live.agents,
            'chain': sim_live.protocol['termux_pilot']['scenario_chain'],
            'mem': deepcopy(sim_live.protocol.get('institutional_memory')),
        })

        adapter = OpenAICompatibleAdvisor('https://example.invalid/v1/chat/completions', 'model')
        with patch.dict(os.environ, {'PEOPLE1000_API_KEY': 'dummy'}), \
             patch('society.termux.urlopen', side_effect=TimeoutError('timeout')):
            # 1) Failed live `start_scenario` must NOT wipe previous chain or imprint memory
            with self.assertRaises(RuntimeError):
                start_scenario(sim_live, 'Maden ocağında göçük ve denetim ihmali', adapter)
            self.assertEqual(sim_live.time, snap_before['time'])
            self.assertEqual(sim_live.agents, snap_before['agents'])
            self.assertEqual(sim_live.protocol['termux_pilot']['scenario_chain'], snap_before['chain'])
            self.assertEqual(sim_live.protocol.get('institutional_memory'), snap_before['mem'])
            self.assertEqual(sim_live.protocol['termux_pilot']['question_attempts'], 1)
            self.assertEqual(sim_live.protocol['termux_pilot']['question_log'][-1]['status'], 'failed')

            # 2) Failed live `advance_scenario_day` must NOT consume Day 4 milestone
            with self.assertRaises(RuntimeError):
                advance_scenario_day(sim_live, adapter)
            self.assertEqual(sim_live.time, snap_before['time'])
            self.assertEqual(sim_live.protocol['termux_pilot']['scenario_chain'], snap_before['chain'])

        # 3) Live vs Offline causal parity: LLM receives Day-k synced engine state, matching offline
        sim_a = create_pilot(seed=44)
        sim_b = create_pilot(seed=44)
        init_scenario_chain(sim_b, 'Büyük maden faciası yaşandı, denetim ihmali iddiası var')
        advance_scenario_day(sim_b, ReferenceAdvisor())

        captured_payloads = []
        def fake_urlopen(req, timeout=60):
            captured_payloads.append(json.loads(req.data.decode('utf-8')))
            r = MagicMock()
            r.__enter__.return_value.read.return_value = json.dumps({
                'choices': [{'finish_reason': 'stop', 'message': {'content': 'Gün tamamlandı.'}}],
                'usage': {'total_tokens': 25},
            }).encode('utf-8')
            return r

        with patch.dict(os.environ, {'PEOPLE1000_API_KEY': 'dummy'}), \
             patch('society.termux.urlopen', side_effect=fake_urlopen):
            start_scenario(sim_a, 'Büyük maden faciası yaşandı, denetim ihmali iddiası var', adapter)

        sent_user = json.loads(captured_payloads[0]['messages'][1]['content'])
        self.assertEqual(sent_user['operator_report']['time'], sim_b.time)
        self.assertEqual(
            sim_a.protocol['termux_pilot']['scenario_chain']['history'][-1]['engine_effects'],
            sim_b.protocol['termux_pilot']['scenario_chain']['history'][-1]['engine_effects'],
        )
        self.assertEqual(
            sim_a.protocol['termux_pilot']['scenario_chain']['history'][-1]['psychology_snapshot'],
            sim_b.protocol['termux_pilot']['scenario_chain']['history'][-1]['psychology_snapshot'],
        )


if __name__=='__main__':unittest.main()
