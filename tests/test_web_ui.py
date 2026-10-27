"""Yerel web arayuzunun veri semasi, komutlari ve HTTP katmani."""
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from society.agenda import ReferenceAdvisor
from society.agenda_api import GEMINI_ENDPOINT, GEMINI_MODEL, GeminiAdvisor
from society import termux, web_ui


class WebUIFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=str(Path(__file__).resolve().parents[1]))
        self.state = Path(self.tmp.name) / 'pilot.json'
        self.sim = termux.create_pilot()
        self.sim.save(self.state)
        self.pilot = web_ui.WebPilot(self.sim, ReferenceAdvisor(), self.state)

    def tearDown(self):
        self.tmp.cleanup()

    def days(self, n):
        for _ in range(n):
            web_ui.execute_command(self.pilot, {'cmd': 'gun'})


class StateTests(WebUIFixture):
    def test_six_cards_always_present(self):
        s = web_ui.build_state(self.pilot)
        self.assertEqual(len(s['kitleler']), 6)
        self.assertEqual([c['sira'] for c in s['kitleler']], [1, 2, 3, 4, 5, 6])
        self.assertEqual(s['mode'], 'offline')
        self.assertIn('kitle', s['ozet_metni'].lower())
        self.assertTrue(all(c['ad'] and c['tanim'] for c in s['kitleler']))

    def test_cards_gain_data_and_delta_after_days(self):
        self.days(4)
        s = web_ui.build_state(self.pilot)
        self.assertTrue(any(c['var'] for c in s['kitleler']))
        self.assertEqual(s['gecmis_gunler'], [0, 1, 2, 3, 4])
        # Ayni gun tekrar okununca gecmis buyumemeli.
        web_ui.build_state(self.pilot)
        self.assertEqual(len(self.pilot.history), 5)

    def test_history_survives_restart(self):
        self.days(2)
        again = web_ui.WebPilot(self.sim, ReferenceAdvisor(), self.state)
        self.assertEqual(len(again.history), 3)

    def test_key_never_in_state(self):
        advisor = GeminiAdvisor(GEMINI_ENDPOINT, GEMINI_MODEL)
        with patch.dict(os.environ, {'PEOPLE1000_API_KEY': 'private-key-xyz'}):
            pilot = web_ui.WebPilot(self.sim, advisor, self.state)
            s = web_ui.build_state(pilot)
            self.assertNotIn('private-key-xyz', json.dumps(s, ensure_ascii=False))
            self.assertEqual(pilot.redact('key=private-key-xyz'), 'key=[REDACTED]')


class CommandTests(WebUIFixture):
    def test_safe_commands(self):
        for cmd in ('ozet', 'rapor', 'ayar', 'yardim', 'kaydet'):
            message, state = web_ui.execute_command(self.pilot, {'cmd': cmd})
            self.assertTrue(message)
            self.assertEqual(len(state['kitleler']), 6)

    def test_gun_advances_and_checkpoints(self):
        message, state = web_ui.execute_command(self.pilot, {'cmd': 'gun'})
        self.assertIn('1 gun', message)
        self.assertEqual(state['day'], 1)
        self.assertTrue(self.state.exists())

    def test_ilerle_validation(self):
        for count in (0, 31, 2.5, '3', True):
            with self.assertRaises(ValueError):
                web_ui.execute_command(self.pilot, {'cmd': 'ilerle', 'count': count})

    def test_text_validation(self):
        with self.assertRaises(ValueError):
            web_ui.execute_command(self.pilot, {'cmd': 'sor', 'text': ''})
        with self.assertRaises(ValueError):
            web_ui.execute_command(self.pilot, {'cmd': 'sor', 'text': 'x' * 2001})

    def test_dangerous_commands_need_confirmation(self):
        with self.assertRaises(ValueError):
            web_ui.execute_command(self.pilot, {'cmd': 'uretim-test'})
        with self.assertRaises(ValueError):
            web_ui.execute_command(self.pilot, {'cmd': 'baglanti'})

    def test_unknown_and_bad_payload(self):
        for payload in ({'cmd': 'rm -rf'}, {'cmd': None}, None, 'gun'):
            with self.assertRaises(ValueError):
                web_ui.execute_command(self.pilot, payload)

    def test_limits_and_scenario(self):
        web_ui.execute_command(self.pilot, {'cmd': 'limit', 'total': 40, 'daily': 15})
        s = web_ui.build_state(self.pilot)
        self.assertEqual(s['limitler'], {'toplam': 40, 'gunluk': 15})
        web_ui.execute_command(self.pilot, {'cmd': 'sor-limit', 'count': 9})
        self.assertEqual(self.sim.protocol['termux_pilot']['question_limit'], 9)
        _, s2 = web_ui.execute_command(self.pilot, {'cmd': 'devam', 'count': 2})
        self.assertEqual(s2['senaryo']['gun'], 2)
        self.assertEqual(len(s2['senaryo']['gecmis']), 2)

    def test_offline_rejects_pacing_change(self):
        with self.assertRaises(ValueError):
            web_ui.execute_command(self.pilot, {'cmd': 'bekleme', 'seconds': 5})


class HttpTests(WebUIFixture):
    def setUp(self):
        super().setUp()
        self.server = web_ui.create_server('127.0.0.1', 0, self.pilot)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        super().tearDown()

    def get(self, path):
        with urlopen(f'http://127.0.0.1:{self.port}{path}', timeout=5) as response:
            return response.status, response.read().decode('utf-8')

    def post(self, payload):
        request = Request(f'http://127.0.0.1:{self.port}/api/command',
                          data=json.dumps(payload).encode('utf-8'),
                          headers={'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode('utf-8'))

    def test_page_and_state(self):
        status, page = self.get('/')
        self.assertEqual(status, 200)
        self.assertIn('PEOPLE', page)
        self.assertIn('data-cmd="gun"', page)
        self.assertNotIn('PEOPLE1000_API_KEY', page)
        status, body = self.get('/api/state')
        self.assertEqual(status, 200)
        state = json.loads(body)['state']
        self.assertEqual(len(state['kitleler']), 6)

    def test_post_command_and_validation_error(self):
        status, result = self.post({'cmd': 'gun'})
        self.assertEqual(status, 200)
        self.assertTrue(result['ok'])
        self.assertEqual(result['state']['day'], 1)
        status, result = self.post({'cmd': 'bilinmeyen'})
        self.assertEqual(status, 400)
        self.assertFalse(result['ok'])
        self.assertIn('Bilinmeyen', result['error'])

    def test_export_and_404(self):
        status, body = self.get('/api/export')
        self.assertEqual(status, 200)
        self.assertIn('world_metrics', body)
        with self.assertRaises(HTTPError) as caught:
            self.get('/api/yok')
        self.assertEqual(caught.exception.code, 404)


if __name__ == '__main__':
    unittest.main()
