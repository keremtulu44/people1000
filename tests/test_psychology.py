import tempfile
import unittest
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from society import behavior, psychology, scenario_text, termux, web_ui
from society.agenda import ReferenceAdvisor
from society.agenda_api import AgendaProvider, advisor_from_environment, safe_api_error
from society.engine import Config, Simulation
from society.session import Session


class PsychologicalDepthTests(unittest.TestCase):
    def test_v35_profile_differentiates_six_groups_and_preserves_v33_v34_freezes(self):
        v35 = behavior.load_profile()
        v34 = behavior.load_v34_profile()
        v33 = behavior.load_v33_profile()
        self.assertEqual(v35['behavior_version'], '3.5.0')
        self.assertEqual(v35['psychology_model'], 'affective-v2')
        self.assertEqual(v34['behavior_version'], '3.4.0')
        self.assertEqual(v34['psychology_model'], 'affective-v1')
        self.assertEqual(v33['behavior_version'], '3.3.0')

        g = v35['groups']
        self.assertGreater(g['power_aligned']['parameters']['authority_sensitivity'][0],
                           g['authority']['parameters']['authority_sensitivity'][1])
        self.assertGreater(g['opposition']['parameters']['authority_sensitivity'][0],
                           g['observer']['parameters']['authority_sensitivity'][1])
        self.assertGreater(g['power_aligned']['psychology']['tolerance_threshold'][0],
                           g['opposition']['psychology']['tolerance_threshold'][1])
        self.assertGreater(g['observer']['psychology']['tolerance_threshold'][0],
                           g['discontented']['psychology']['tolerance_threshold'][1])
        self.assertGreater(g['wealthy']['psychology']['fear_sensitivity'][0],
                           g['observer']['psychology']['fear_sensitivity'][1])
        self.assertGreater(g['authority']['psychology']['comfort_baseline'][0],
                           g['discontented']['psychology']['comfort_baseline'][1])
        self.assertGreater(g['power_aligned']['psychology']['defense_strength'][0],
                           g['discontented']['psychology']['defense_strength'][1])

    def test_wealthy_three_subwings_and_neutral_commercial_fear_censorship(self):
        sim = Simulation(Config(seed=44, population=200))
        wealthy = [a for a in sim.agents.values() if a.initial_group == 'wealthy']
        subwings = {a.behavior.get('subwing') for a in wealthy}
        self.assertEqual(subwings, {'pro_A', 'pro_B', 'neutral_commercial'})

        neutral = [a for a in wealthy if a.behavior.get('subwing') == 'neutral_commercial']
        pro_a = [a for a in wealthy if a.behavior.get('subwing') == 'pro_A']
        pro_b = [a for a in wealthy if a.behavior.get('subwing') == 'pro_B']
        self.assertTrue(all(a.public_alignment == 'none' for a in neutral))
        self.assertTrue(all(a.public_alignment == 'A' for a in pro_a))
        self.assertTrue(all(a.public_alignment == 'B' for a in pro_b))
        avg_def_neutral = sum(a.behavior['psychology']['defense_wall'] for a in neutral) / len(neutral)
        avg_def_pro_a = sum(a.behavior['psychology']['defense_wall'] for a in pro_a) / len(pro_a)
        self.assertLess(avg_def_neutral, avg_def_pro_a - 0.35)

        target = neutral[0]
        loyalty_before = target.private_loyalty
        psychology.apply_stimulus(sim, target, 'contract_loss', magnitude=0.85)
        psychology.daily(sim, target, harm=0.10, income_harm=0.45, disruption_level=0.10,
                         responsibility_own=0.0, max_own_error=0.0, collective_supported=False)
        self.assertEqual(target.behavior['psychology']['expression_mode'], 'self_censored')
        self.assertEqual(target.private_loyalty, loyalty_before)

    def test_fear_and_pressure_keep_private_belief_intact_while_accumulating_repressed_anger(self):
        sim = Simulation(Config(seed=7, population=100))
        opp = next(a for a in sim.agents.values() if a.initial_group == 'opposition')
        private_before = dict(opp.beliefs)
        opp.pressure = 0.85
        opp.public_support = 0.80
        opp.private_loyalty = 0.30
        psychology.daily(sim, opp, harm=0.55, income_harm=0.25, disruption_level=0.35,
                         responsibility_own=0.0, max_own_error=0.0, collective_supported=True)
        psychology.apply_stimulus(sim, opp, 'pressure', magnitude=0.95)
        ps = psychology.daily(sim, opp, harm=0.55, income_harm=0.25, disruption_level=0.35,
                              responsibility_own=0.0, max_own_error=0.0, collective_supported=True)
        self.assertLess(ps['effective_drive'], 0.30)
        self.assertIn(ps['expression_mode'], ('guarded', 'self_censored'))
        self.assertGreater(ps['repressed_anger'], 0.08)
        self.assertEqual(opp.beliefs, private_before)

        expr = psychology.expression_for_agenda(sim, opp, 'question')
        self.assertIn(expr, ('guarded_question', 'self_censored_silence'))

    def test_tolerance_threshold_and_exhaustion_replace_linear_escalation(self):
        sim = Simulation(Config(seed=19, population=100))
        pa = next(a for a in sim.agents.values() if a.initial_group == 'power_aligned')
        di = next(a for a in sim.agents.values() if a.initial_group == 'discontented')

        ps_pa = psychology.daily(sim, pa, harm=0.35, income_harm=0.25, disruption_level=0.20,
                                 responsibility_own=0.2, max_own_error=0.0, collective_supported=True)
        ps_di = psychology.daily(sim, di, harm=0.35, income_harm=0.25, disruption_level=0.20,
                                 responsibility_own=0.2, max_own_error=0.0, collective_supported=True)
        self.assertGreater(ps_di['effective_drive'], ps_pa['effective_drive'] * 2.0)

        peak_drive = 0.0
        later_drive = 0.0
        for step in range(1, 22):
            p = psychology.daily(sim, di, harm=0.70, income_harm=0.45, disruption_level=0.35,
                                 responsibility_own=0.5, max_own_error=0.2, collective_supported=False)
            if step <= 3:
                peak_drive = max(peak_drive, p['effective_drive'])
            later_drive = p['effective_drive']
        self.assertGreater(di.behavior['psychology']['exhaustion'], 0.45)
        self.assertLess(later_drive, peak_drive)

    def test_defense_wall_buffers_trust_erosion_until_sustained_personal_harm(self):
        sim = Simulation(Config(seed=23, population=100))
        pa = next(a for a in sim.agents.values() if a.initial_group == 'power_aligned')
        mult_initial = psychology.trust_erosion_multiplier(sim, pa)
        self.assertLess(mult_initial, 0.65)

        for _ in range(12):
            psychology.daily(sim, pa, harm=0.90, income_harm=0.60, disruption_level=0.50,
                             responsibility_own=0.95, max_own_error=0.90, collective_supported=False)
        mult_breached = psychology.trust_erosion_multiplier(sim, pa)
        self.assertLess(pa.behavior['psychology']['defense_wall'], 0.30)
        self.assertGreater(mult_breached, mult_initial)

    def test_ordinary_appointment_agenda_has_zero_extremes_and_populates_psychology_summary(self):
        sim = termux.create_pilot(seed=44)
        sess = Session(sim, AgendaProvider(ReferenceAdvisor()))
        sess.day()
        rep = termux.report(sim)
        self.assertEqual(rep['world_metrics']['losses'], 0.0)
        self.assertIn('psychology_by_role', rep)
        self.assertEqual(set(rep['psychology_by_role']), set(termux.ROLE_INFO))
        ozet = termux.turkce_ozet(sim)
        self.assertIn('Psikolojik Hal', ozet)


class NetworkHomophilyAmplifyAndEconomyTests(unittest.TestCase):
    def test_echo_chamber_homophily_observer_monitors_and_media_amplify(self):
        sim = Simulation(Config(seed=44, population=100))
        sim.run(0)
        # 1. Yankı odası kümelemesi: İktidar yanlısı ve muhaliflerin yakın bağlarının çoğunluğu kendi kutbundandır
        same_count = total_count = 0
        for e in sim.edges:
            src = sim.agents[e['source']]
            tgt = sim.agents[e['target']]
            if e['type'] == 'close' and src.initial_group in ('power_aligned', 'opposition'):
                total_count += 1
                if tgt.alignment == src.alignment:
                    same_count += 1
        self.assertGreater(same_count / total_count, 0.72)

        # 2. Gözlemci dışarıya 1 yakın bağ kurar ama iki kutbu da izleyen gelen monitor bağlarına sahiptir
        obs = next(a for a in sim.agents.values() if a.initial_group == 'observer')
        incoming = [e for e in sim.edges if e['target'] == obs.id]
        self.assertGreaterEqual(len(incoming), 4)
        self.assertLessEqual(len(incoming), 6)

        # 3. Sosyal medya `amplify` eylemi tek hamlede çoklu takipçiye ulaşır; korku otosansüründe reddedilir
        w_n = next(a for a in sim.agents.values()
                   if a.initial_group == 'wealthy' and a.behavior.get('subwing') == 'neutral_commercial')
        ok = sim.apply(sim.propose(w_n.id, {'type': 'amplify', 'topic': 'media:test', 'claim': 60, 'text': 'Yayın'}))
        self.assertTrue(ok)
        amp_ev = next(e for e in reversed(sim.log) if e['kind'] == 'media_amplified')
        self.assertGreaterEqual(amp_ev['payload']['reach_count'], 8)

        # Korkuyla otosansüre giren tarafsız medya artık amplify yapamaz
        psychology.apply_stimulus(sim, w_n, 'contract_loss', magnitude=0.95)
        self.assertEqual(w_n.behavior['psychology']['expression_mode'], 'self_censored')
        blocked = sim.apply(sim.propose(w_n.id, {'type': 'amplify', 'topic': 'media:test2', 'claim': 60, 'text': 'Riskli yayın'}))
        self.assertFalse(blocked)

    def test_employer_to_employee_economic_cascade_on_contract_revocation_and_boycott(self):
        sim = Simulation(Config(seed=44, population=100))
        sim.run(0)
        w = next(a for a in sim.agents.values()
                 if a.initial_group == 'wealthy' and a.authority_dependency)
        workers = [a for a in sim.agents.values() if a.employer == w.id]
        self.assertTrue(workers)
        boss_auth = w.authority_dependency
        self.assertTrue(sim.apply(sim.propose(boss_auth, {'type': 'revoke_contract', 'target': w.id})))
        sim.run(1440)
        # İşverene kesilen ceza çalışanlara gerçek gelir kesintisi (`employer_cut`) ve ekonomik zarar olarak yansır
        for worker in workers:
            cut = worker.behavior.get('economic_chain', {}).get('employer_cut', 0.0)
            self.assertGreater(cut, 0.05)
            self.assertGreater(worker.losses, 0.0)


class DynamicBranchingBridgeAndMemoryTests(unittest.TestCase):
    def test_early_transparent_reform_branches_away_from_aftershock_and_scapegoat(self):
        sim = termux.create_pilot(seed=44)
        chain = termux.init_scenario_chain(sim, 'Büyük maden faciası yaşandı, ihmal iddiası var')
        termux.advance_scenario_day(sim, ReferenceAdvisor())  # Gün 1
        # Gün 2'de erken şeffaf soruşturma ve somut önlem müdahalesi
        termux.advance_scenario_day(
            sim, ReferenceAdvisor(),
            custom_event='Bağımsız denetim başlatıldı, sorumlu üst yönetici istifa etti ve güvenlik önlem alındı',
        )
        termux.advance_scenario_days(sim, ReferenceAdvisor(), count=6)
        self.assertEqual(chain['branch_state']['branch_path'], 'seffaf_onarim')
        self.assertEqual(chain['conditions']['detained_individuals'], 0)
        self.assertFalse(chain['conditions']['scapegoat_isolated'])
        self.assertFalse(chain['conditions']['singular_tragedy_occurred'])
        self.assertNotEqual(chain['conditions']['aftershock_stage'], 'aftershock_occurred')

    def test_disaster_chain_never_hallucinates_school_shooting_and_syncs_engine(self):
        sim = termux.create_pilot(seed=44)
        t0 = sim.time
        chain = termux.init_scenario_chain(sim, 'Büyük bir deprem oldu, 30 bina yıkıldı')
        self.assertEqual(chain['tier'], 'severe_security_crisis')
        self.assertEqual(chain['domain'], 'disaster_neglect')
        outputs = termux.advance_scenario_days(sim, ReferenceAdvisor(), count=8)
        joined = '\n'.join(outputs).lower()
        self.assertNotIn('silah sokma', joined)
        self.assertNotIn('okulda artçı saldırı', joined)
        self.assertIn('denetim', joined)
        # Senaryo motorla birleşti: simülasyon zamanı 8 gün ilerledi ve motor etkileri kaydedildi
        self.assertGreater(sim.time, t0 + 7 * 1440)
        self.assertIn('engine_effects', chain['history'][-1])
        for k, v in chain['conditions'].items():
            if k != 'detained_individuals':
                self.assertNotIsInstance(v, (int, float) if not isinstance(v, bool) else ())

    def test_cross_crisis_institutional_memory_lowers_patience_and_compresses_third_crisis(self):
        sim = termux.create_pilot(seed=44)
        opp = next(a for a in sim.agents.values() if a.initial_group == 'opposition')
        pa = next(a for a in sim.agents.values() if a.initial_group == 'power_aligned')
        tol_before = opp.behavior['psychology']['tolerance_threshold']
        def_before = pa.behavior['psychology']['defense_wall']

        # 1. Kriz: örtbas ve günah keçisiyle kapanır
        termux.init_scenario_chain(sim, 'Büyük ihale yolsuzluğu ve yayın yasağı')
        termux.advance_scenario_days(sim, ReferenceAdvisor(), count=7)

        # 2. Kriz başladığında 1. krizin kurumsal hafıza izi ajanlara kazınır
        termux.init_scenario_chain(sim, 'Maden ocağında göçük ve denetim ihmali')
        mem1 = psychology.institutional_memory_state(sim)
        self.assertEqual(mem1['past_crises'], 1)
        self.assertGreater(mem1['coverup_scar'], 0.10)
        self.assertGreater(mem1['scapegoat_scar'], 0.15)
        self.assertLess(opp.behavior['psychology']['tolerance_threshold'], tol_before)
        self.assertLess(pa.behavior['psychology']['defense_wall'], def_before)
        termux.advance_scenario_days(sim, ReferenceAdvisor(), count=7)

        # 3. Kriz: 2 geçmiş örtbas krizinden sonra içerideki sızıntı artık 3. günü bile beklemeden 2. günde patlar!
        ch3 = termux.init_scenario_chain(sim, 'Fabrikada büyük yangın faciası yaşandı')
        self.assertEqual(psychology.institutional_memory_state(sim)['past_crises'], 2)
        termux.advance_scenario_days(sim, ReferenceAdvisor(), count=2)
        self.assertTrue(ch3['conditions']['leak_occurred'])

    def test_parser_disambiguates_cross_keyword_wealthy_heading(self):
        sample = (
            "**Günün Gelişmesi:** Kriz derinleşti.\n\n"
            "**1. İktidar Yanlıları**\nDüzeni savundu.\n\n"
            "**2. Muhalifler**\nUsulü sorguladı.\n\n"
            "**3. Yöneticiler ve Otorite**\nBilgi akışını daralttı.\n\n"
            "**4. Yöneticilere Bağımlı Zenginler ve Sosyal Medya Etki Ekibi**\n"
            "A yanlısı, B yanlısı ve tarafsız medya ayrıştı.\n\n"
            "**5. Hoşnutsuz Kesim**\nGeçim ve güvenlik tepkisi büyüdü.\n\n"
            "**6. Gözlemciler**\nAynı tiyatroyu okudu.\n\n"
            "**Günün Genel Özeti:** Altı kitle ayrıştı."
        )
        parsed = scenario_text.analyze_scenario(sample)
        self.assertEqual(parsed['bagli'], 6)
        self.assertIn('tarafsız medya', parsed['kitleler']['wealthy'])
        self.assertIn('Bilgi akışını', parsed['kitleler']['authority'])


class WebUIPsychologyAndResilienceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmp.name) / 'pilot.json'
        self.sim = termux.create_pilot(seed=44)
        self.pilot = web_ui.WebPilot(self.sim, ReferenceAdvisor(), self.state_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_state_exposes_unified_engine_psychology_and_wealthy_subwings_across_days(self):
        web_ui.execute_command(self.pilot, {'cmd': 'olay', 'text': 'Büyük maden faciası yaşandı, ihmal iddiası var'})
        web_ui.execute_command(self.pilot, {'cmd': 'devam', 'count': 4})

        st_day1 = web_ui.build_state(self.pilot, secili_gun='1')
        st_day4 = web_ui.build_state(self.pilot, secili_gun='4')
        self.assertGreaterEqual(st_day4['day'], 4)
        self.assertTrue(st_day4['senaryo']['gunler']['4']['motor_etkisi']['sim_day'] >= 4)
        w1 = next(c for c in st_day1['kitleler'] if c['id'] == 'wealthy')['psikoloji']
        w4 = next(c for c in st_day4['kitleler'] if c['id'] == 'wealthy')['psikoloji']
        self.assertGreater(w4['korku'], w1['korku'])
        self.assertIn('alt_kanatlar', w4)
        self.assertGreater(w4['alt_kanatlar']['neutral_commercial']['korku'],
                           w4['alt_kanatlar']['pro_A']['korku'])
        self.assertEqual(w4['alt_kanatlar']['neutral_commercial']['ifade_etiketi'],
                         'Tam otosansür / sessizlik')

    def test_get_state_does_not_touch_disk_and_question_limit_is_honored(self):
        mtime_before = self.pilot.history_path.stat().st_mtime_ns
        _ = web_ui.build_state(self.pilot)
        mtime_after = self.pilot.history_path.stat().st_mtime_ns
        self.assertEqual(mtime_before, mtime_after)

        env = {
            'PEOPLE1000_API_PROVIDER': 'gemini',
            'PEOPLE1000_API_KEY': 'fake-secret-key',
            'PEOPLE1000_API_MIN_INTERVAL': '0',
        }
        with patch.dict('os.environ', env):
            live_adv = advisor_from_environment()
            live_pilot = web_ui.WebPilot(
                termux.create_pilot(seed=44),
                live_adv,
                Path(self.tmp.name) / 'live.json',
            )
            web_ui.execute_command(live_pilot, {'cmd': 'sor-limit', 'count': 1})
            live_pilot.sim.protocol['termux_pilot']['question_attempts'] = 1
            with self.assertRaises(RuntimeError) as ctx:
                web_ui.execute_command(live_pilot, {'cmd': 'sor', 'text': 'Yeni olay'})
            self.assertIn('sor-limit', str(ctx.exception))

            msg, st = web_ui.execute_command(
                live_pilot, {'cmd': 'token-limit', 'tokens': 3072, 'timeout': 45})
            self.assertIn('3072', msg)
            self.assertEqual(st['settings']['max_output_tokens'], 3072)
            self.assertEqual(st['settings']['timeout_seconds'], 45)

    def test_http_429_extracts_retry_after_without_leaking_key(self):
        headers = {'Retry-After': '17'}
        err = HTTPError(
            url='https://generativelanguage.googleapis.com/v1beta/models/x?key=TOPSECRET99',
            code=429, msg='Too Many Requests', hdrs=headers,
            fp=BytesIO(b'{"error":{"message":"Quota exceeded"}}'),
        )
        safe = safe_api_error(err)
        self.assertEqual(safe.http_status, 429)
        self.assertEqual(safe.retry_after, 17)
        self.assertNotIn('TOPSECRET99', str(safe))


class DeepSocialMindV35Tests(unittest.TestCase):
    def test_asymptotic_anger_and_resource_bounded_solidarity_fatigue(self):
        sim = Simulation(Config(seed=44, population=100))
        di = [a for a in sim.agents.values() if a.initial_group == 'discontented']
        for _ in range(40):
            for a in di:
                psychology.daily(sim, a, harm=0.68, income_harm=0.35, disruption_level=0.40,
                                 responsibility_own=0.5, max_own_error=0.25, collective_supported=True)
        avg_anger = sum(a.behavior['psychology']['anger'] for a in di) / len(di)
        avg_exh_solidarity = sum(a.behavior['psychology']['exhaustion'] for a in di) / len(di)
        # 1.000 tavan doygunluğu çözüldü: öfke nüanslı aralıkta kalır (< 0.97)
        self.assertLess(avg_anger, 0.97)
        # Sınırsız dayanışma ölümsüzlüğü çözüldü: 40 günlük kronik krizde dayanışmalı grup da yorulur (> 0.20)
        self.assertGreater(avg_exh_solidarity, 0.20)

    def test_blame_shifting_amplify_contradiction_and_disengaged_loyalist(self):
        sim = Simulation(Config(seed=44, population=100))
        sim.run(0)
        w_a = next(a for a in sim.agents.values()
                   if a.initial_group == 'wealthy' and a.behavior.get('subwing') == 'pro_A')
        # A yanlısı medya iyimser ekonomik tahmin yayar ('enflasyon sıfır'), ardından ağır fiyat şoku gelir
        sim.schedule(10, 'external_action', {
            'actor': w_a.id,
            'proposal': {'type': 'amplify', 'topic': 'economic_outlook', 'claim': 0, 'text': 'Enflasyon sıfır.'},
        })
        sim.schedule(30, 'price_shock', {'multiplier': 2.20})
        sim.protocol['active_boycott'] = 0.32
        for d in range(22):
            if d in (5, 10, 15):
                sim.schedule(d * 1440 + 20, 'external_action', {
                    'actor': w_a.id,
                    'proposal': {'type': 'amplify', 'topic': 'economic_outlook', 'claim': 0, 'text': 'Refah tam.'},
                })
            sim.protocol['active_boycott'] = 0.32
            sim.run((d + 1) * 1440 - 1)
        pa = [a for a in sim.agents.values() if a.initial_group == 'power_aligned']
        avg_inter = sum(a.behavior['psychology']['intermediary_trust'] for a in pa) / len(pa)
        avg_wall = sum(a.behavior['psychology']['defense_wall'] for a in pa) / len(pa)
        disengaged = sum(1 for a in pa if a.behavior['psychology']['disengaged'])
        switches = sum(a.behavior.get('switch_count', 0) for a in pa)
        self.assertLess(avg_inter, 0.35)
        self.assertLess(avg_wall, 0.55)
        self.assertGreater(disengaged, 0)
        # Karşı partiye ucuz geçiş yerine 'küskün seçmen / sessiz kopuş' oluşur!
        self.assertEqual(switches, 0)

    def test_pluralistic_ignorance_breaks_on_leak_and_observer_whistleblowing(self):
        sim = Simulation(Config(seed=44, population=100))
        sim.run(0)
        opp = next(a for a in sim.agents.values() if a.initial_group == 'opposition')
        cfg = sim.behavior_profile['psychology_dynamics']
        p = psychology.state(opp)
        for _ in range(5):
            psychology._step_agent_psychology(
                p, opp.traits, 'opposition', 'B', 0.65, 0.45, 0.2, cfg,
                harm=0.45, income_harm=0.15, disruption_level=0.35,
                responsibility_own=0.0, max_own_error=0.0, collective_supported=False,
                threat_signal=0.35, coverup_signal=0.60, leak_signal=False,
                use_v2=True, social_ctx={'silent_ratio': 0.80, 'solidarity_capacity': 0.8},
            )
        pi_before = p['pluralistic_ignorance']
        drive_before = p['effective_drive']
        self.assertGreater(pi_before, 0.45)

        # Kamusal sızıntı çoğulcu cehaleti tek günde kırar ve eylem itkisini sıçratır!
        psychology._step_agent_psychology(
            p, opp.traits, 'opposition', 'B', 0.50, 0.45, 0.0, cfg,
            harm=0.45, income_harm=0.15, disruption_level=0.35,
            responsibility_own=0.0, max_own_error=0.0, collective_supported=False,
            threat_signal=0.10, coverup_signal=0.60, leak_signal=True,
            use_v2=True, social_ctx={'silent_ratio': 0.20, 'solidarity_capacity': 0.8},
        )
        self.assertLess(p['pluralistic_ignorance'], 0.12)
        self.assertGreater(p['effective_drive'], drive_before)

        # Gözlemci epistemik alarm eşiği ve web_ui sosyal_zihin radarı
        obs = next(a for a in sim.agents.values() if a.initial_group == 'observer')
        po = psychology.state(obs)
        for _ in range(5):
            psychology._step_agent_psychology(
                po, obs.traits, 'observer', 'none', 0.5, 0.5, 0.0, cfg,
                harm=0.40, income_harm=0.0, disruption_level=0.70,
                responsibility_own=0.0, max_own_error=0.50, collective_supported=False,
                threat_signal=0.10, coverup_signal=0.80, leak_signal=True,
                use_v2=True, social_ctx={'contradiction_spread': 0.35},
            )
        self.assertTrue(po['whistleblower_ready'])
        self.assertEqual(psychology.expression_for_agenda(sim, obs, 'observe'), 'epistemic_technical_warning')


if __name__ == '__main__':
    unittest.main()
