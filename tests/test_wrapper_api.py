"""ApiWrapper entegrasyonu: durumsuz istek, hata biçimi, sır sızdırmama, arayüz."""
import io
import json
import os
import re
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from society.agenda import ReferenceAdvisor
from society.agenda_api import OpenAICompatibleAdvisor, advisor_from_environment
from society.wrapper_api import (MAX_TEXT, WRAPPER_MODEL, WRAPPER_TIMEOUT, WrapperAdvisor,
                                 WrapperClient, WrapperError, normalize_base_url,
                                 wrapper_api_key, wrapper_configured, main as wrapper_main)
from society import termux, web_ui

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://wrapper.example.invalid'
KEY = 'wrapper-secret-key'
ENV = {'WRAPPER_URL': URL, 'WRAPPER_API_KEY': KEY}


def response(data):
    mock = MagicMock()
    mock.__enter__.return_value.read.return_value = json.dumps(data).encode('utf-8')
    return mock


def chat(content='MERHABA', finish='stop', usage=None):
    return {'choices': [{'finish_reason': finish, 'message': {'role': 'assistant',
                                                             'content': content}}],
            'usage': usage if usage is not None else {'prompt_tokens': 7,
                                                       'completion_tokens': 3,
                                                       'total_tokens': 10}}


class UrlNormalizationTests(unittest.TestCase):
    def test_trailing_slash_removed_and_v1_appended(self):
        self.assertEqual(normalize_base_url('https://api.wrap/'), 'https://api.wrap/v1')
        self.assertEqual(normalize_base_url('https://api.wrap'), 'https://api.wrap/v1')
        self.assertEqual(normalize_base_url('  https://api.wrap//  '), 'https://api.wrap/v1')

    def test_existing_v1_is_not_doubled(self):
        self.assertEqual(normalize_base_url('https://api.wrap/v1'), 'https://api.wrap/v1')
        self.assertEqual(normalize_base_url('https://api.wrap/v1/'), 'https://api.wrap/v1')

    def test_pasted_full_endpoint_is_reduced_to_base(self):
        self.assertEqual(normalize_base_url('https://api.wrap/v1/chat/completions'),
                         'https://api.wrap/v1')
        self.assertEqual(normalize_base_url('https://api.wrap/chat/completions'),
                         'https://api.wrap/v1')

    def test_path_and_port_preserved(self):
        self.assertEqual(normalize_base_url('https://api.wrap:8443/proxy/'),
                         'https://api.wrap:8443/proxy/v1')
        self.assertEqual(normalize_base_url('http://127.0.0.1:8080'),
                         'http://127.0.0.1:8080/v1')
        self.assertEqual(normalize_base_url('http://localhost:3000/v1/'),
                         'http://localhost:3000/v1')

    def test_invalid_urls_rejected(self):
        for value in ('', '   ', 'api.wrap', 'ftp://api.wrap', 'https://',
                      'https://user:pass@api.wrap', 'https://api.wrap?x=1',
                      'https://api.wrap#frag', 'https://api.wrap/a b',
                      'https://api.wrap/<script>', 'https://api.wrap:99999',
                      'http://api.wrap'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_base_url(value)

    def test_non_string_and_missing_env(self):
        with self.assertRaises(ValueError):
            normalize_base_url(123)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(WrapperError) as caught:
                WrapperClient()
        self.assertEqual(caught.exception.kind, 'missing_url')


class CredentialTests(unittest.TestCase):
    def test_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(WrapperError) as caught:
                wrapper_api_key()
        self.assertEqual(caught.exception.kind, 'missing_key')

    def test_invalid_key_is_not_echoed(self):
        for value in ('secret key', 'line\nbreak', 'tab\tkey', 'é' * 3, 'x' * 513):
            with patch.dict(os.environ, {'WRAPPER_API_KEY': value}, clear=True):
                with self.assertRaises(WrapperError) as caught:
                    wrapper_api_key()
                self.assertEqual(caught.exception.kind, 'key_format')
                self.assertNotIn(value.strip()[:4], str(caught.exception))

    def test_key_comes_from_configured_env_name(self):
        with patch.dict(os.environ, {'OTHER_KEY': 'abc'}, clear=True):
            self.assertEqual(wrapper_api_key('OTHER_KEY'), 'abc')


class RequestShapeTests(unittest.TestCase):
    def client(self, **kwargs):
        return WrapperClient(URL, **kwargs)

    def test_single_user_message_model_max_stream_false_timeout_180(self):
        with patch.dict(os.environ, ENV), patch('society.wrapper_api.urlopen',
                                                return_value=response(chat())) as send:
            client = self.client()
            self.assertEqual(client.endpoint, URL + '/v1/chat/completions')
            self.assertEqual(client.ask('  İlk metin  '), 'MERHABA')
            request = send.call_args.args[0]
            payload = json.loads(request.data)
            self.assertEqual(request.full_url, URL + '/v1/chat/completions')
            self.assertEqual(request.get_method(), 'POST')
            self.assertEqual(payload['model'], 'max')
            self.assertIs(payload['stream'], False)
            self.assertEqual(payload['messages'], [{'role': 'user', 'content': 'İlk metin'}])
            self.assertEqual(request.get_header('Authorization'), 'Bearer ' + KEY)
            self.assertEqual(request.get_header('Content-type'), 'application/json')
            self.assertNotIn(KEY, request.full_url)
            self.assertEqual(send.call_args.kwargs['timeout'], WRAPPER_TIMEOUT)
            self.assertEqual(client.last_usage, {'prompt_tokens': 7, 'completion_tokens': 3,
                                                 'total_tokens': 10})

    def test_no_system_developer_history_or_session_fields(self):
        with patch.dict(os.environ, ENV), patch('society.wrapper_api.urlopen',
                                                return_value=response(chat())) as send:
            WrapperClient.from_environment().ask('tek istek')
            payload = json.loads(send.call_args.args[0].data)
            roles = [m['role'] for m in payload['messages']]
            self.assertEqual(roles, ['user'])
            self.assertEqual(len(payload['messages']), 1)
            for forbidden in ('conversation', 'history', 'session', 'previous_response_id',
                              'developer'):
                self.assertNotIn(forbidden, payload)

    def test_each_request_is_independent(self):
        with patch.dict(os.environ, ENV), \
                patch('society.wrapper_api.urlopen', return_value=response(chat())) as send:
            first = WrapperClient.from_environment()
            first.ask('birinci')
            first.ask('ikinci')
            self.assertEqual(send.call_count, 2)
            for call, text in zip(send.call_args_list, ('birinci', 'ikinci')):
                payload = json.loads(call.args[0].data)
                self.assertEqual(payload['messages'], [{'role': 'user', 'content': text}])

    def test_text_validation(self):
        client = WrapperClient(URL)
        for value in ('', '   ', 'x' * (MAX_TEXT + 1), None, 5):
            with patch.dict(os.environ, ENV), patch('society.wrapper_api.urlopen') as send:
                with self.assertRaises(WrapperError):
                    client.ask(value)
                send.assert_not_called()

    def test_model_and_timeout_validation(self):
        for kwargs in ({'model': ''}, {'model': 'bad model'}, {'timeout': 0},
                       {'timeout': 601}, {'timeout': True}, {'timeout': '180'}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    WrapperClient(URL, **kwargs)


class ResponseParsingTests(unittest.TestCase):
    def ask(self, data):
        with patch.dict(os.environ, ENV), \
                patch('society.wrapper_api.urlopen', return_value=response(data)):
            return WrapperClient(URL).ask('metin')

    def test_content_read_from_choices_message(self):
        self.assertEqual(self.ask(chat('  yanıt metni  ')), 'yanıt metni')

    def test_error_body_with_http_200_keeps_wrapper_code(self):
        data = {'error': {'code': 'quota_exceeded', 'message': 'secret ' + KEY}}
        with patch.dict(os.environ, ENV), \
                patch('society.wrapper_api.urlopen', return_value=response(data)):
            with self.assertRaises(WrapperError) as caught:
                WrapperClient(URL).ask('metin')
        self.assertEqual(caught.exception.kind, 'error_body')
        self.assertEqual(caught.exception.code, 'quota_exceeded')
        self.assertIn('quota_exceeded', str(caught.exception))
        self.assertNotIn(KEY, str(caught.exception))

    def test_broken_shapes_raise(self):
        cases = [
            {'choices': []},
            {'choices': None},
            {'choices': [{'message': {'content': None}}]},
            {'choices': [{'message': 'metin'}]},
            {'choices': [{'message': {'content': '   '}}]},
            {'choices': [{'finish_reason': 'length', 'message': {'content': 'yarım'}}]},
            {'error': 'x'},
        ]
        for data in cases:
            with self.subTest(data=data):
                with self.assertRaises(WrapperError):
                    self.ask(data)

    def test_oversized_response_rejected(self):
        mock = response({})
        mock.__enter__.return_value.read.return_value = b'x' * 2_000_001
        with patch.dict(os.environ, ENV), patch('society.wrapper_api.urlopen', return_value=mock):
            with self.assertRaises(WrapperError) as caught:
                WrapperClient(URL).ask('metin')
        self.assertEqual(caught.exception.kind, 'response_size')


class ErrorSurfaceTests(unittest.TestCase):
    def run_error(self, exc):
        with patch.dict(os.environ, ENV), patch('society.wrapper_api.urlopen', side_effect=exc):
            with self.assertRaises(WrapperError) as caught:
                WrapperClient(URL).ask('metin')
        return caught.exception

    def test_http_status_and_wrapper_code_preserved_without_secret(self):
        body = json.dumps({'error': {'message': 'secret ' + KEY, 'code': 'invalid_api_key',
                                     'type': 'invalid_request_error'}}).encode()
        error = HTTPError(URL + '/v1/chat/completions', 401, 'unauthorized',
                          {}, io.BytesIO(body))
        caught = self.run_error(error)
        self.assertEqual(caught.kind, 'http_error')
        self.assertEqual(caught.http_status, 401)
        self.assertEqual(caught.code, 'invalid_api_key')
        self.assertIn('401', str(caught))
        self.assertIn('invalid_api_key', str(caught))
        self.assertNotIn(KEY, str(caught))

    def test_non_json_error_body_still_reports_status(self):
        error = HTTPError(URL, 503, 'busy', {}, io.BytesIO(b'<html>gateway</html>'))
        caught = self.run_error(error)
        self.assertEqual(caught.http_status, 503)
        self.assertIsNone(caught.code)
        self.assertIn('503', str(caught))

    def test_unsafe_code_is_dropped(self):
        body = json.dumps({'error': {'code': 'bad code with spaces ' + KEY}}).encode()
        caught = self.run_error(HTTPError(URL, 400, 'bad', {}, io.BytesIO(body)))
        self.assertIsNone(caught.code)
        self.assertNotIn(KEY, str(caught))

    def test_timeout_and_network_kinds(self):
        self.assertEqual(self.run_error(TimeoutError()).kind, 'timeout')
        self.assertEqual(self.run_error(URLError(TimeoutError())).kind, 'timeout')
        self.assertEqual(self.run_error(URLError('dns')).kind, 'network')

    def test_settings_never_include_key(self):
        with patch.dict(os.environ, ENV):
            data = WrapperClient(URL).settings()
        text = json.dumps(data)
        self.assertNotIn(KEY, text)
        self.assertTrue(data['has_key'])
        self.assertIs(data['stream'], False)
        self.assertEqual(data['timeout_seconds'], 180.0)
        self.assertTrue(data['stateless'])


class AdvisorIntegrationTests(unittest.TestCase):
    def test_factory_prefers_wrapper(self):
        with patch.dict(os.environ, ENV, clear=True):
            advisor = advisor_from_environment()
        self.assertIsInstance(advisor, WrapperAdvisor)
        self.assertIsInstance(advisor, OpenAICompatibleAdvisor)
        self.assertEqual(advisor.endpoint, URL + '/v1/chat/completions')
        self.assertEqual(advisor.model, WRAPPER_MODEL)
        self.assertEqual(advisor.timeout, WRAPPER_TIMEOUT)
        self.assertEqual(advisor.key_env, 'WRAPPER_API_KEY')

    def test_factory_requires_url_and_key(self):
        with patch.dict(os.environ, {'WRAPPER_URL': URL}, clear=True):
            with self.assertRaisesRegex(ValueError, 'WRAPPER_API_KEY'):
                advisor_from_environment()
        with patch.dict(os.environ, {'WRAPPER_URL': 'not a url',
                                     'WRAPPER_API_KEY': KEY}, clear=True):
            with self.assertRaises(ValueError):
                advisor_from_environment()

    def test_review_uses_wrapper_endpoint_and_parses_json(self):
        advice = {'approach': 'reserve', 'reason': 'r', 'risks': [],
                  'expected_effect': 'belirsiz'}
        with patch.dict(os.environ, ENV), \
                patch('society.wrapper_api.urlopen',
                      return_value=response(chat(json.dumps(advice)))) as send:
            result = WrapperAdvisor(URL).review({'allowed_approaches': ['reserve']})
        self.assertEqual(result, advice)
        payload = json.loads(send.call_args.args[0].data)
        self.assertEqual(payload['model'], 'max')
        self.assertIs(payload['stream'], False)
        self.assertEqual([m['role'] for m in payload['messages']], ['system', 'user'])
        self.assertIn('allowed_approaches', payload['messages'][1]['content'])

    def test_review_rejects_non_json_without_leaking(self):
        with patch.dict(os.environ, ENV), \
                patch('society.wrapper_api.urlopen', return_value=response(chat('düz metin'))):
            with self.assertRaises(WrapperError) as caught:
                WrapperAdvisor(URL).review({})
        self.assertEqual(caught.exception.kind, 'invalid_response')
        self.assertNotIn(KEY, str(caught.exception))

    def test_missing_wrapper_keeps_legacy_factory(self):
        env = {'PEOPLE1000_API_KEY': 'dummy-key'}
        with patch.dict(os.environ, env, clear=True):
            advisor = advisor_from_environment()
        self.assertNotIsInstance(advisor, WrapperAdvisor)

    def test_configured_summary_has_no_secret_or_url(self):
        with patch.dict(os.environ, ENV, clear=True):
            data = wrapper_configured()
        self.assertTrue(data['configured'])
        self.assertTrue(data['has_key'])
        self.assertNotIn(KEY, json.dumps(data))
        self.assertNotIn(URL, json.dumps(data))
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(wrapper_configured()['configured'])


class CliTests(unittest.TestCase):
    def test_check_prints_settings_without_network_or_key(self):
        with patch.dict(os.environ, ENV), patch('society.wrapper_api.urlopen') as send, \
                patch('builtins.print') as printed:
            self.assertEqual(wrapper_main(['--check']), 0)
            send.assert_not_called()
        text = ' '.join(str(c.args[0]) for c in printed.call_args_list)
        self.assertIn('chat/completions', text)
        self.assertNotIn(KEY, text)

    def test_missing_config_exits_without_network(self):
        with patch.dict(os.environ, {}, clear=True), patch('society.wrapper_api.urlopen') as send, \
                patch('builtins.print'):
            self.assertEqual(wrapper_main(['merhaba']), 2)
            send.assert_not_called()


class WebEndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=str(ROOT))
        self.state = Path(self.tmp.name) / 'pilot.json'
        self.sim = termux.create_pilot()
        self.sim.save(self.state)
        self.pilot = web_ui.WebPilot(self.sim, ReferenceAdvisor(), self.state)
        self.server = web_ui.create_server('127.0.0.1', 0, self.pilot)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def post(self, payload, path='/api/wrapper'):
        request = Request(f'http://127.0.0.1:{self.port}{path}',
                          data=json.dumps(payload).encode('utf-8'),
                          headers={'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode('utf-8'))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode('utf-8'))

    def test_success_returns_answer(self):
        with patch.dict(os.environ, ENV), \
                patch('society.wrapper_api.urlopen', return_value=response(chat('APIWRAPPER OK'))):
            status, body = self.post({'text': 'merhaba'})
        self.assertEqual(status, 200)
        self.assertTrue(body['ok'])
        self.assertEqual(body['answer'], 'APIWRAPPER OK')
        self.assertEqual(body['model'], 'max')
        self.assertIs(body['stream'], False)
        self.assertNotIn(KEY, json.dumps(body))

    def test_wrapper_http_error_exposes_status_and_code(self):
        raw = json.dumps({'error': {'code': 'rate_limit_exceeded',
                                    'message': 'secret ' + KEY}}).encode()
        error = HTTPError(URL, 429, 'rate', {}, io.BytesIO(raw))
        with patch.dict(os.environ, ENV), \
                patch('society.wrapper_api.urlopen', side_effect=error):
            status, body = self.post({'text': 'merhaba'})
        self.assertEqual(status, 429)
        self.assertFalse(body['ok'])
        self.assertEqual(body['http_status'], 429)
        self.assertEqual(body['error_code'], 'rate_limit_exceeded')
        self.assertNotIn(KEY, json.dumps(body))

    def test_unconfigured_wrapper_returns_503(self):
        with patch.dict(os.environ, {}, clear=True):
            status, body = self.post({'text': 'merhaba'})
        self.assertEqual(status, 503)
        self.assertFalse(body['ok'])
        self.assertIn('WRAPPER_URL', body['error'])

    def test_text_validation_and_bad_payload(self):
        with patch.dict(os.environ, ENV):
            status, body = self.post({'text': ''})
            self.assertEqual(status, 400)
            self.assertFalse(body['ok'])
            status, body = self.post({'text': 'x' * (MAX_TEXT + 1)})
            self.assertEqual(status, 400)
        request = Request(f'http://127.0.0.1:{self.port}/api/wrapper',
                          data=b'not-json', headers={'Content-Type': 'application/json'})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 400)

    def test_state_reports_wrapper_without_secret(self):
        with patch.dict(os.environ, ENV):
            state = web_ui.build_state(self.pilot)
        self.assertTrue(state['wrapper']['configured'])
        self.assertEqual(state['wrapper']['model'], 'max')
        self.assertNotIn(KEY, json.dumps(state, ensure_ascii=False))

    def test_page_has_wrapper_panel_and_no_key(self):
        with urlopen(f'http://127.0.0.1:{self.port}/', timeout=5) as resp:
            page = resp.read().decode('utf-8')
        self.assertIn('/api/wrapper', page)
        self.assertIn('wrapperText', page)
        self.assertNotIn('WRAPPER_API_KEY', page)


class RepositoryHygieneTests(unittest.TestCase):
    def test_env_example_has_only_placeholders(self):
        text = (ROOT / '.env.example').read_text(encoding='utf-8')
        for name in ('WRAPPER_URL', 'WRAPPER_API_KEY'):
            lines = [line for line in text.splitlines() if name in line]
            self.assertTrue(lines, f'{name} şablonda olmalı')
            for line in lines:
                self.assertTrue(line.lstrip().startswith('#'),
                                f'{name} gerçek değer olarak commit edilemez')
        self.assertNotIn(KEY, text)
        self.assertNotRegex(text, r'sk-[A-Za-z0-9]{12,}')

    def test_module_has_no_hardcoded_key(self):
        source = (ROOT / 'society' / 'wrapper_api.py').read_text(encoding='utf-8')
        self.assertNotRegex(source, r'sk-[A-Za-z0-9]{12,}')
        self.assertNotIn('Bearer ' + 'hardcoded', source)


if __name__ == '__main__':
    unittest.main()
