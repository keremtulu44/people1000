from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,MagicMock

from society.termux import create_pilot,report,ask_operator,main
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


if __name__=='__main__':unittest.main()
