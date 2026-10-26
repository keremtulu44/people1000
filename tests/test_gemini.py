import io
import json
import os
import unittest
from unittest.mock import patch,MagicMock
from urllib.error import HTTPError
from society.agenda_api import GeminiAdvisor,advisor_from_environment
from society.termux import create_pilot,ask_operator

ENDPOINT='https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent'


def response(data):
    r=MagicMock();r.__enter__.return_value.read.return_value=json.dumps(data).encode();return r


def candidate(text='TAMAM',finish='STOP'):
    return {'candidates':[{'finishReason':finish,'content':{'parts':[{'text':text}]}}],
        'usageMetadata':{'promptTokenCount':10,'candidatesTokenCount':5,'totalTokenCount':15}}


class GeminiTests(unittest.TestCase):
    def adapter(self):return GeminiAdvisor(ENDPOINT,'gemini-3.5-flash-lite')

    def test_native_header_body_and_no_url_secret(self):
        with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'dummy-key'}),patch('society.agenda_api.urlopen',return_value=response(candidate())) as send:
            a=self.adapter();self.assertEqual(a.generate('instruction','hello'),'TAMAM')
            request=send.call_args.args[0];payload=json.loads(request.data)
            self.assertEqual(request.get_header('X-goog-api-key'),'dummy-key')
            self.assertIsNone(request.get_header('Authorization'))
            self.assertNotIn('dummy-key',request.full_url)
            self.assertEqual(payload['contents'][0]['parts'][0]['text'],'hello')
            self.assertNotIn('messages',payload);self.assertEqual(a.last_usage['total_tokens'],15)

    def test_factory_native_infers_model_and_compatibility_converts(self):
        for endpoint in (ENDPOINT,'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'):
            with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'dummy','PEOPLE1000_API_ENDPOINT':endpoint,'PEOPLE1000_API_MODEL':'gemini-3.5-flash-lite'}):
                a=advisor_from_environment();self.assertIsInstance(a,GeminiAdvisor);self.assertEqual(a.endpoint,ENDPOINT)
        with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'dummy','PEOPLE1000_API_ENDPOINT':ENDPOINT,'PEOPLE1000_API_MODEL':''}):
            self.assertEqual(advisor_from_environment().model,'gemini-3.5-flash-lite')

    def test_mismatched_model_and_url_key_rejected(self):
        for endpoint,model in ((ENDPOINT,'different-model'),(ENDPOINT+'?key=secret','gemini-3.5-flash-lite')):
            with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'dummy','PEOPLE1000_API_ENDPOINT':endpoint,'PEOPLE1000_API_MODEL':model}):
                with self.assertRaises(ValueError):advisor_from_environment()

    def test_safe_http_errors_do_not_echo_provider_body(self):
        for status in (400,403,404,429):
            error=HTTPError(ENDPOINT,status,'dummy-key',{},io.BytesIO(b'{"error":{"message":"dummy-key"}}'))
            with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'dummy-key'}),patch('society.agenda_api.urlopen',side_effect=error) as send:
                with self.assertRaises(RuntimeError) as caught:self.adapter().generate('s','u')
                self.assertIn(str(status),str(caught.exception));self.assertNotIn('dummy-key',str(caught.exception))
                self.assertEqual(send.call_count,1)

    def test_timeout_distinguished(self):
        with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'dummy'}),patch('society.agenda_api.urlopen',side_effect=TimeoutError()):
            with self.assertRaisesRegex(RuntimeError,'zaman aşımı'):self.adapter().generate('s','u')

    def test_token_exhaustion_and_empty_answer_not_success(self):
        for data,expected in ((candidate('','MAX_TOKENS'),'token'),(candidate(''),'boş'),({'candidates':[]},'aday')):
            with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'dummy'}),patch('society.agenda_api.urlopen',return_value=response(data)):
                with self.assertRaisesRegex(RuntimeError,expected):self.adapter().generate('s','u')

    def test_native_review_json_mode(self):
        advice={'approach':'reserve','reason':'r','risks':[],'expected_effect':'uncertain'}
        with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'dummy'}),patch('society.agenda_api.urlopen',return_value=response(candidate(json.dumps(advice)))) as send:
            self.assertEqual(self.adapter().review({'allowed_approaches':['reserve']}),advice)
            payload=json.loads(send.call_args.args[0].data)
            self.assertEqual(payload['generationConfig']['responseMimeType'],'application/json')

    def test_operator_connection_uses_native_minimal_prompt_and_counts(self):
        sim=create_pilot()
        with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'dummy'}),patch('society.agenda_api.urlopen',return_value=response(candidate())) as send:
            self.assertEqual(ask_operator(sim,'test',self.adapter(),connection_test=True),'TAMAM')
            payload=json.loads(send.call_args.args[0].data)
            self.assertNotIn('operator_report',payload['contents'][0]['parts'][0]['text'])
        self.assertEqual(sim.protocol['termux_pilot']['question_attempts'],1)
        self.assertEqual(sim.protocol['termux_pilot']['question_log'][0]['usage']['total_tokens'],15)


if __name__=='__main__':unittest.main()
