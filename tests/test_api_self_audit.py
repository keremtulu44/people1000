"""Independent fault/privacy/cost regression audit; never accesses real Google."""
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError,URLError
from urllib.request import Request
from unittest.mock import patch

from society import agenda
from society.agenda_api import (GeminiAdvisor,OpenAICompatibleAdvisor,APIError,
    NoCredentialRedirect,advisor_from_environment,safe_api_error)
from society.termux import create_pilot,ask_operator,metadata_check,settings
from test_gemini import response,candidate,ENDPOINT


class APISelfAudit(unittest.TestCase):
    def adapter(self):return GeminiAdvisor(ENDPOINT,'gemini-3.5-flash-lite')

    def test_metadata_check_uses_get_not_generation(self):
        body={'name':'models/gemini-3.5-flash-lite','supportedGenerationMethods':['generateContent']}
        sim=create_pilot();deep=deepcopy(sim.agents)
        with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'private-key'}),patch('society.agenda_api.urlopen',return_value=response(body)) as send:
            result=metadata_check(sim,self.adapter())
            req=send.call_args.args[0]
            self.assertEqual(req.get_method(),'GET');self.assertIsNone(req.data)
            self.assertFalse(req.full_url.endswith(':generateContent'))
            self.assertEqual(req.get_header('X-goog-api-key'),'private-key')
        self.assertTrue(result['generateContent_supported']);self.assertFalse(result['text_generation_tested'])
        self.assertEqual(sim.protocol['termux_pilot']['question_attempts'],0)
        self.assertEqual(sim.protocol['termux_pilot']['diagnostic_attempts'],1)
        self.assertEqual(sim.agents,deep)

    def test_model_list_no_automatic_selection_or_extra_pages(self):
        body={'models':[{'name':'models/gemini-3.5-flash-lite','supportedGenerationMethods':['generateContent']},
            {'name':'models/no-generation','supportedGenerationMethods':['embedContent']}],'nextPageToken':'sensitive-page-token'}
        with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'key'}),patch('society.agenda_api.urlopen',return_value=response(body)) as send:
            a=self.adapter();result=a.list_models()
            self.assertEqual(result['models'],['gemini-3.5-flash-lite']);self.assertTrue(result['more_pages'])
            self.assertEqual(send.call_count,1);self.assertEqual(a.model,'gemini-3.5-flash-lite')
            self.assertNotIn('sensitive-page-token',json.dumps(result))

    def test_metadata_404_counts_and_does_not_retry_or_change_model(self):
        sim=create_pilot();a=self.adapter()
        error=HTTPError(ENDPOINT,404,'not found',{},io.BytesIO(b'{"error":{"message":"Model key-private not found for API version v1beta"}}'))
        with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'key-private'}),patch('society.agenda_api.urlopen',side_effect=error) as send:
            with self.assertRaises(APIError) as caught:metadata_check(sim,a)
            self.assertIn('API sürümü',str(caught.exception));self.assertNotIn('key-private',str(caught.exception))
            self.assertEqual(send.call_count,1)
        entry=sim.protocol['termux_pilot']['diagnostic_log'][0]
        self.assertEqual(entry['http_status'],404);self.assertEqual(a.model,'gemini-3.5-flash-lite')

    def test_metadata_budget_stops_before_network(self):
        sim=create_pilot();sim.protocol['termux_pilot']['diagnostic_attempts']=10
        with patch('society.agenda_api.urlopen') as send:
            with self.assertRaises(RuntimeError):metadata_check(sim,self.adapter())
            send.assert_not_called()

    def test_tunable_bounded_limits(self):
        env={'PEOPLE1000_API_KEY':'key','PEOPLE1000_API_ENDPOINT':ENDPOINT,'PEOPLE1000_API_MODEL':'models/gemini-3.5-flash-lite',
             'PEOPLE1000_API_TIMEOUT':'75','PEOPLE1000_MAX_OUTPUT_TOKENS':'512'}
        with patch.dict(os.environ,env):
            a=advisor_from_environment();self.assertEqual(a.timeout,75);self.assertEqual(a.max_output_tokens,512)
            self.assertEqual(a.model,'gemini-3.5-flash-lite')
        for key,value in (('PEOPLE1000_API_TIMEOUT','0'),('PEOPLE1000_API_TIMEOUT','999'),('PEOPLE1000_MAX_OUTPUT_TOKENS','-1'),('PEOPLE1000_MAX_OUTPUT_TOKENS','text')):
            with patch.dict(os.environ,{**env,key:value}):
                with self.assertRaises(ValueError):advisor_from_environment()

    def test_reject_html_and_incomplete_google_addresses(self):
        for endpoint in ('https://generativelanguage&gt;','https://generativelanguage','https://generativelanguage.googleapis.com/v1beta/models/model:generateContent>'):
            with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'key','PEOPLE1000_API_ENDPOINT':endpoint,'PEOPLE1000_API_MODEL':'model'}):
                with self.assertRaises(ValueError):advisor_from_environment()

    def test_invalid_header_key_never_printed_or_sent(self):
        with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'private\nkey'}),patch('society.agenda_api.urlopen') as send:
            with self.assertRaises(APIError) as caught:self.adapter().generate('s','u')
            self.assertNotIn('private',str(caught.exception));send.assert_not_called()

    def test_redirect_is_blocked_even_for_same_origin(self):
        req=Request(ENDPOINT,headers={'X-goog-api-key':'secret'})
        handler=NoCredentialRedirect()
        for url in ('https://evil.invalid/collect','https://generativelanguage.googleapis.com/elsewhere'):
            self.assertIsNone(handler.redirect_request(req,None,302,'redirect',{},url))

    def test_error_matrix_does_not_leak_key(self):
        for code in (301,302,400,401,403,404,429,500,503):
            exc=HTTPError('https://secret.invalid/?key=private',code,'private',{},io.BytesIO(b'{"error":{"message":"private"}}'))
            error=safe_api_error(exc);self.assertIsInstance(error,APIError)
            self.assertNotIn('private',str(error));self.assertEqual(error.http_status,code)
        self.assertEqual(safe_api_error(URLError('private')).kind,'network')
        self.assertEqual(safe_api_error(URLError(TimeoutError())).kind,'timeout')

    def test_failed_generation_records_usage_not_zero_cost(self):
        sim=create_pilot();data=candidate('','MAX_TOKENS')
        with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'key'}),patch('society.agenda_api.urlopen',return_value=response(data)):
            with self.assertRaises(APIError):ask_operator(sim,'Rapor?',self.adapter())
        entry=sim.protocol['termux_pilot']['question_log'][0]
        self.assertEqual(entry['usage']['total_tokens'],15);self.assertEqual(entry['failure_kind'],'max_tokens')
        self.assertEqual(entry['status'],'failed')

    def test_failed_agenda_request_records_usage(self):
        sim=create_pilot();root=sim.protocol['termux_pilot']['issuer']
        sim.schedule(0,'agenda_notice',{'issue':'appointment','target':root})
        class Failed:
            network=True
            last_usage=None
            def review(self,p):
                self.last_usage={'total_tokens':20,'unknown':'not copied'}
                raise APIError('incomplete','max_tokens')
        from society.agenda_api import AgendaProvider
        with self.assertRaises(APIError):sim.run(2,AgendaProvider(Failed()))
        record=sim.agenda_runtime['requests'][0]
        self.assertEqual(record['usage'],{'total_tokens':20});self.assertEqual(record['failure_kind'],'max_tokens')

    def test_thought_parts_are_not_operator_answer(self):
        data=candidate();data['candidates'][0]['content']['parts']=[{'thought':True,'text':'hidden reasoning'},{'text':'visible answer'}]
        with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'key'}),patch('society.agenda_api.urlopen',return_value=response(data)):
            self.assertEqual(self.adapter().generate('s','u'),'visible answer')

    def test_settings_local_only_and_no_key(self):
        with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'private-key'}),patch('society.agenda_api.urlopen') as send:
            data=settings(self.adapter());send.assert_not_called()
            self.assertEqual(data['model'],'gemini-3.5-flash-lite');self.assertNotIn('private-key',json.dumps(data))

    def test_openai_truncation_rejected_and_usage_retained(self):
        data={'choices':[{'finish_reason':'length','message':{'content':'{"partial":'}}],'usage':{'total_tokens':30}}
        a=OpenAICompatibleAdvisor('https://example.invalid/v1/chat/completions','model')
        with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'key'}),patch('society.agenda_api.urlopen',return_value=response(data)):
            with self.assertRaises(APIError):a.review({})
        self.assertEqual(a.last_usage,{'total_tokens':30})

    def test_cli_connection_does_not_generate_or_spend_question_quota(self):
        from society.termux import main
        body={'name':'models/gemini-3.5-flash-lite','supportedGenerationMethods':['generateContent']}
        env={'PEOPLE1000_API_KEY':'private-key','PEOPLE1000_API_ENDPOINT':ENDPOINT,'PEOPLE1000_API_MODEL':'gemini-3.5-flash-lite'}
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'pilot.json'
            with patch.dict(os.environ,env),patch('sys.argv',['termux','--state',str(path)]),patch('builtins.input',side_effect=['ayar','baglanti','e','cik']),patch('builtins.print'),patch('society.agenda_api.urlopen',return_value=response(body)) as send:
                main()
            self.assertEqual(send.call_count,1);self.assertEqual(send.call_args.args[0].get_method(),'GET')
            data=json.loads(path.read_text());meta=data['protocol']['termux_pilot']
            self.assertEqual(meta['question_attempts'],0);self.assertEqual(meta['diagnostic_attempts'],1)
            self.assertNotIn('private-key',path.read_text())

    def test_cli_503_does_not_retry_or_report_success(self):
        from society.termux import main
        env={'PEOPLE1000_API_KEY':'private-key','PEOPLE1000_API_ENDPOINT':ENDPOINT,'PEOPLE1000_API_MODEL':'gemini-3.5-flash-lite'}
        error=HTTPError(ENDPOINT,503,'busy',{},io.BytesIO(b'{"error":{"message":"private-key"}}'))
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'pilot.json'
            with patch.dict(os.environ,env),patch('sys.argv',['termux','--state',str(path)]),patch('builtins.input',side_effect=['uretim-test','e','cik']),patch('builtins.print'),patch('society.agenda_api.urlopen',side_effect=error) as send:
                main()
            self.assertEqual(send.call_count,1)
            meta=json.loads(path.read_text())['protocol']['termux_pilot']
            self.assertEqual(meta['question_attempts'],1);self.assertEqual(meta['question_log'][0]['http_status'],503)
            self.assertEqual(meta['question_log'][0]['status'],'failed');self.assertNotIn('private-key',path.read_text())

    def test_oversized_response_is_rejected(self):
        mock=response({});mock.__enter__.return_value.read.return_value=b'x'*2_000_001
        with patch.dict(os.environ,{'PEOPLE1000_API_KEY':'key'}),patch('society.agenda_api.urlopen',return_value=mock):
            with self.assertRaises(APIError) as caught:self.adapter().generate('s','u')
        self.assertEqual(caught.exception.kind,'response_size')

    def test_groq_qwen_model_and_user_agent_header_sent(self):
        env={'PEOPLE1000_API_KEY':'private-key','PEOPLE1000_API_ENDPOINT':'https://api.groq.com/openai/v1/chat/completions',
             'PEOPLE1000_API_MODEL':'qwen/qwen3.8-27b'}
        with patch.dict(os.environ,env),patch('society.agenda_api.time.sleep') as sleep:
            a=advisor_from_environment()
            self.assertIsInstance(a,OpenAICompatibleAdvisor);self.assertEqual(a.model,'qwen/qwen3.8-27b')
            self.assertEqual(a.min_interval,5.0)
            advice={'approach':'reserve','reason':'r','risks':[],'expected_effect':'uncertain'}
            body={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(advice)}}],'usage':{'total_tokens':12}}
            with patch('society.agenda_api.urlopen',return_value=response(body)) as send:
                self.assertEqual(a.review({'allowed_approaches':['reserve']}),advice)
                req=send.call_args.args[0]
                self.assertEqual(req.get_header('User-agent'),'people1000/0.1')
                self.assertEqual(req.get_header('Accept'),'application/json')
            self.assertEqual(sleep.call_count,0)
            sim=create_pilot()
            chat={'choices':[{'finish_reason':'stop','message':{'content':'BAĞLANTI TAMAM'}}],'usage':{'total_tokens':9}}
            with patch('society.termux.urlopen',return_value=response(chat)) as send_op:
                self.assertEqual(ask_operator(sim,'test',a,connection_test=True),'BAĞLANTI TAMAM')
                op_req=send_op.call_args.args[0]
                self.assertEqual(op_req.get_header('User-agent'),'people1000/0.1')
                self.assertNotIn('operator_report',json.loads(op_req.data)['messages'][1]['content'])
            self.assertEqual(sleep.call_count,1)
        cf403=HTTPError('https://api.groq.com/openai/v1/chat/completions',403,'forbidden',{},io.BytesIO(b'error code: 1010 private-key'))
        err=safe_api_error(cf403)
        self.assertIn('1010',str(err));self.assertNotIn('private-key',str(err))
        err429=safe_api_error(HTTPError('https://api.groq.com/openai/v1/chat/completions',429,'rate',{'Retry-After':'7'},io.BytesIO(b'{"error":{"message":"private-key"}}')))
        self.assertIn('7 saniye',str(err429));self.assertNotIn('private-key',str(err429))
        err404=safe_api_error(HTTPError(ENDPOINT,404,'not found',{},io.BytesIO(b'{"error":{"message":"This model models/gemini-2.5-flash-lite is no longer available to new users. private-key"}}')))
        self.assertIn('yeni kullanıcı',str(err404));self.assertNotIn('private-key',str(err404))

    def test_openai_operator_max_tokens_oversize_minimal_test_prompt_and_gemini_null_fields(self):
        sim = create_pilot()
        oa = OpenAICompatibleAdvisor('https://example.invalid/v1/chat/completions', 'model')
        # 1. OpenAI connection_test uses minimal system prompt, not full PHILOSOPHY_SYSTEM_PROMPT
        ok_resp = response({'choices': [{'finish_reason': 'stop', 'message': {'content': 'BAĞLANTI TAMAM'}}], 'usage': {'total_tokens': 8}})
        with patch.dict(os.environ, {'PEOPLE1000_API_KEY': 'key'}), patch('society.termux.urlopen', return_value=ok_resp) as send_op:
            self.assertEqual(ask_operator(sim, 'test', oa, connection_test=True), 'BAĞLANTI TAMAM')
            sys_msg = json.loads(send_op.call_args.args[0].data)['messages'][0]['content']
            self.assertEqual(sys_msg, 'Türkçe, kısa yanıt ver.')

        # 2. OpenAI ask_operator finish_reason=='length' preserves kind=='max_tokens'
        trunc_resp = response({'choices': [{'finish_reason': 'length', 'message': {'content': 'yarım'}}], 'usage': {'total_tokens': 64}})
        with patch.dict(os.environ, {'PEOPLE1000_API_KEY': 'key'}), patch('society.termux.urlopen', return_value=trunc_resp):
            with self.assertRaises(APIError) as ctx:
                ask_operator(sim, 'Rapor?', oa)
            self.assertEqual(ctx.exception.kind, 'max_tokens')
        self.assertEqual(sim.protocol['termux_pilot']['question_log'][-1]['failure_kind'], 'max_tokens')

        # 3. OpenAI ask_operator >2MB response raises response_size APIError
        big_resp = response({})
        big_resp.__enter__.return_value.read.return_value = b'x' * 2_000_001
        with patch.dict(os.environ, {'PEOPLE1000_API_KEY': 'key'}), patch('society.termux.urlopen', return_value=big_resp):
            with self.assertRaises(APIError) as ctx2:
                ask_operator(sim, 'Rapor?', oa)
            self.assertEqual(ctx2.exception.kind, 'response_size')

        # 4. GeminiAdvisor handles explicit JSON nulls & classifies invalid review JSON as invalid_response
        g = GeminiAdvisor(ENDPOINT, 'gemini-3.5-flash-lite', min_interval=3.0)
        null_payload = {'usageMetadata': None, 'candidates': [{'finishReason': 'STOP', 'content': None}]}
        with patch.dict(os.environ, {'PEOPLE1000_API_KEY': 'key'}), patch('society.agenda_api.urlopen', return_value=response(null_payload)):
            with self.assertRaises(APIError) as ctx3:
                g.generate('s', 'u')
            self.assertEqual(ctx3.exception.kind, 'empty_text')

        bad_json_payload = candidate('not-json')
        with patch.dict(os.environ, {'PEOPLE1000_API_KEY': 'key'}), \
             patch('society.agenda_api.time.sleep'), \
             patch('society.agenda_api.urlopen', return_value=response(bad_json_payload)):
            with self.assertRaises(APIError) as ctx4:
                g.review({'allowed_approaches': ['reserve']})
            self.assertEqual(ctx4.exception.kind, 'invalid_response')


if __name__=='__main__':unittest.main()
