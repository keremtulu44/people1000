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

    def test_v35_wealthy_comm_limit_amplify_agenda_gate_and_same_day_bridge_warnings(self):
        import tomllib
        from society import characters, character_study, psychology_research_v34

        # 1. pyproject.toml includes all 7 behavior JSON files
        pyproject = tomllib.loads((Path(__file__).resolve().parents[1] / 'pyproject.toml').read_text(encoding='utf-8'))
        pkg_files = set(pyproject['tool']['setuptools']['package-data']['society'])
        for expected_json in (
            'behavior.json', 'behavior-v2.json', 'behavior-v3.json',
            'behavior-v31.json', 'behavior-v32.json', 'behavior-v33.json', 'behavior-v34.json',
        ):
            self.assertIn(expected_json, pkg_files)

        # 2. Historical study loaders preserve v3.4 vs v3.5 separation
        cs_case = next(c for c in character_study.catalog() if c['name'] == 'none')
        self.assertEqual(character_study.setup(cs_case, model='v3.4').behavior_profile['behavior_version'], '3.4.0')
        self.assertEqual(character_study.setup(cs_case, model='v3.5').behavior_profile['behavior_version'], '3.5.0')
        self.assertTrue(hasattr(psychology_research_v34, 'run_all_studies'))

        # 3. v3.5 wealthy communication limit is 6 (not regressed to 2)
        sim = Simulation(Config(seed=44, population=100))
        w = next(a for a in sim.agents.values() if a.initial_group == 'wealthy')
        self.assertEqual(characters.limit(sim, w, 'communication', sim.config.communication_budget), 6)

        # 4. `amplify` enforces structured agenda gate & rejects inaccessible audience without spending budget
        used_before = dict(w.used)
        self.assertFalse(sim.apply(sim.propose(w.id, {
            'type': 'amplify', 'topic': 'agenda:appointment:qualification',
            'claim': 100, 'text': 'Belgesiz gündem yayını',
        })))
        self.assertEqual(sim.log[-1]['payload']['reason'], 'agenda topics require structured local issue')
        self.assertFalse(sim.apply(sim.propose(w.id, {
            'type': 'amplify', 'topic': 'media:scoped', 'claim': 50,
            'text': 'Erişilmez hedef kitle', 'audience': [w.id],
        })))
        self.assertEqual(w.used, used_before)

        # 5. Crisis bridge: same-day sanction/boycott effects (0-day lag) & live observer_warnings > 0
        pilot_sim = termux.create_pilot(seed=44)
        ch = termux.init_scenario_chain(pilot_sim, 'Büyük maden faciası yaşandı, denetim ihmali iddiası var')
        termux.advance_scenario_days(pilot_sim, ReferenceAdvisor(), count=6)
        by_day = {h['day']: h['engine_effects'] for h in ch['history']}
        self.assertGreater(by_day[2]['employer_cut_workers'], 0)
        self.assertGreater(by_day[2]['self_censored_blocks'], 0)
        self.assertGreater(by_day[3]['observer_warnings'], 0)
        self.assertGreater(by_day[6]['employer_cut_workers'], by_day[4]['employer_cut_workers'])


class FiveResearchSynthesisTests(unittest.TestCase):
    def test_1_preference_falsification_internalization_and_jsd_index(self):
        sim = Simulation(Config(seed=44, population=100))
        sim.run(0)
        jsd_calm = psychology.preference_divergence_jsd(sim)

        opp = next(a for a in sim.agents.values() if a.initial_group == 'opposition')
        opp.pressure = 0.55
        opp.public_alignment = 'A'
        opp.public_support = 0.85
        opp.private_loyalty = 0.25
        loyalty_day2 = None
        for day in range(1, 8):
            sim.protocol['active_crisis_signals'] = {
                'tier': 'institutional_crisis', 'domain': 'corruption_institutional',
                'conditions': {'prosecution_fear': 'elevated', 'coverup_level': 'moderate',
                               'leak_occurred': False, 'scapegoat_isolated': False, 'unaddressed_neglect': True},
                'day': day,
            }
            psychology.daily(sim, opp, harm=0.12, income_harm=0.04, disruption_level=0.10,
                             responsibility_own=0.0, max_own_error=0.0, collective_supported=False)
            if day == 2:
                loyalty_day2 = opp.private_loyalty
        # Days 1-2 keep private loyalty untouched; chronic forced conformity (5+ days) partially internalizes
        self.assertEqual(loyalty_day2, 0.25)
        self.assertGreaterEqual(opp.behavior['psychology']['conformist_days'], 5)
        self.assertGreater(opp.behavior['psychology']['conformist_internalization'], 0.08)
        self.assertGreater(opp.private_loyalty, 0.25)

        # Widespread self-censorship elevates macro JSD divergence
        for a in sim.agents.values():
            if a.initial_group in ('opposition', 'discontented'):
                psychology.state(a)['expression_mode'] = 'self_censored'
        jsd_silenced = psychology.preference_divergence_jsd(sim)
        self.assertGreater(jsd_silenced, jsd_calm + 0.05)

        # Leak breaks cognitive spell
        sim.protocol['active_crisis_signals']['conditions']['leak_occurred'] = True
        psychology.daily(sim, opp, harm=0.12, income_harm=0.04, disruption_level=0.10,
                         responsibility_own=0.0, max_own_error=0.0, collective_supported=False)
        self.assertEqual(opp.behavior['psychology']['conformist_days'], 0)

    def test_2_elite_counter_rationalization_repairs_wall_until_personal_harm(self):
        sim_framed = Simulation(Config(seed=44, population=100))
        sim_isolated = Simulation(Config(seed=44, population=100))
        sim_framed.run(0)
        sim_isolated.run(0)

        pa_f = next(a for a in sim_framed.agents.values() if a.initial_group == 'power_aligned' and a.alignment == 'A')
        pa_i = sim_isolated.agents[pa_f.id]
        # Connect pa_f to an active pro_A wealthy elite; sever elite ties for pa_i
        elite_a = next(a for a in sim_framed.agents.values()
                       if a.initial_group == 'wealthy' and a.behavior.get('subwing') == 'pro_A')
        psychology.state(elite_a)['motivated_framing'] = 0.75
        if not sim_framed.edge(elite_a.id, pa_f.id):
            sim_framed.edges.append({'source': elite_a.id, 'target': pa_f.id, 'type': 'media', 'trust': 0.8, 'latency': 5})
        sim_isolated.edges = [
            e for e in sim_isolated.edges
            if not (e['target'] == pa_i.id and sim_isolated.agents[e['source']].initial_group in ('wealthy', 'authority'))
            and not (e['source'] == pa_i.id and sim_isolated.agents[e['target']].initial_group in ('wealthy', 'authority'))
        ]

        for _ in range(5):
            psychology.daily(sim_framed, pa_f, harm=0.22, income_harm=0.02, disruption_level=0.15,
                             responsibility_own=0.65, max_own_error=0.15, collective_supported=False)
            psychology.daily(sim_isolated, pa_i, harm=0.22, income_harm=0.02, disruption_level=0.15,
                             responsibility_own=0.65, max_own_error=0.15, collective_supported=False)
        pf = psychology.state(pa_f)
        pi = psychology.state(pa_i)
        self.assertGreater(pf['intermediary_trust'], pi['intermediary_trust'])
        self.assertGreater(pf['defense_wall'], pi['defense_wall'])

    def test_3_hirschman_functional_exit_capital_flight_and_voice_repair(self):
        sim = Simulation(Config(seed=44, population=100))
        sim.run(0)
        w = next(a for a in sim.agents.values()
                 if a.initial_group == 'wealthy' and a.behavior.get('subwing') == 'neutral_commercial')
        workers = [a for a in sim.agents.values() if a.employer == w.id]
        self.assertTrue(workers)
        for _ in range(6):
            psychology.apply_stimulus(sim, w, 'pressure', magnitude=0.80)
            psychology.daily(sim, w, harm=0.35, income_harm=0.30, disruption_level=0.20,
                             responsibility_own=0.0, max_own_error=0.0, collective_supported=False)
        self.assertTrue(psychology.state(w)['functional_exit'])
        sim.run(1440)
        # Capital flight contracts dependent workers' effective income in closed economy
        self.assertTrue(any(wk.behavior.get('economic_chain', {}).get('employer_cut', 0.0) > 0 for wk in workers))

        # Credible institutional response to Voice repairs trust and lowers exit pressure
        pa = next(a for a in sim.agents.values() if a.initial_group == 'power_aligned')
        psychology.state(pa)['disengaged'] = True
        psychology.state(pa)['intermediary_trust'] = 0.35
        exit_before = psychology.state(w)['exit_pressure']
        sim.protocol['active_crisis_signals'] = {
            'tier': 'institutional_crisis', 'domain': 'corruption_institutional',
            'conditions': {'prosecution_fear': 'low', 'coverup_level': 'none',
                           'leak_occurred': False, 'scapegoat_isolated': False, 'unaddressed_neglect': False},
            'day': 4, 'voice_response': 0.70,
        }
        psychology.daily(sim, w, harm=0.05, income_harm=0.02, disruption_level=0.05,
                         responsibility_own=0.0, max_own_error=0.0, collective_supported=False)
        psychology.daily(sim, pa, harm=0.05, income_harm=0.0, disruption_level=0.05,
                         responsibility_own=0.2, max_own_error=0.0, collective_supported=False)
        self.assertLess(psychology.state(w)['exit_pressure'], exit_before)
        self.assertFalse(psychology.state(pa)['disengaged'])
        self.assertGreater(psychology.state(pa)['intermediary_trust'], 0.40)

    def test_4_whistleblower_ostracism_darvo_and_anticipatory_resilience(self):
        sim = Simulation(Config(seed=44, population=100))
        sim.run(0)
        obs = next(a for a in sim.agents.values() if a.initial_group == 'observer')
        insider = next(a for a in sim.agents.values()
                       if a.initial_group == 'authority' and psychology.state(a).get('conscience_insider'))
        psychology.state(obs)['epistemic_alarm'] = 0.72
        psychology.state(obs)['whistleblower_ready'] = True
        sim.protocol['active_crisis_signals'] = {
            'tier': 'severe_security_crisis', 'domain': 'disaster_neglect',
            'conditions': {'prosecution_fear': 'high', 'coverup_level': 'high',
                           'leak_occurred': True, 'scapegoat_isolated': False, 'unaddressed_neglect': True},
            'day': 3, 'darvo_signal': 0.72,
        }
        for _ in range(3):
            psychology.daily(sim, obs, harm=0.25, income_harm=0.0, disruption_level=0.65,
                             responsibility_own=0.0, max_own_error=0.45, collective_supported=False)
            psychology.daily(sim, insider, harm=0.25, income_harm=0.0, disruption_level=0.30,
                             responsibility_own=0.6, max_own_error=0.45, collective_supported=False)
        po = psychology.state(obs)
        pi = psychology.state(insider)
        self.assertGreater(po['ostracism'], 0.30)
        self.assertGreater(pi['ostracism'], 0.30)
        # SIT prediction: unprepared insider suffers deeper identity dislocation than prepared observer
        self.assertGreater(pi['identity_dislocation'], po['identity_dislocation'])

    def test_5_hybrid_constitutional_llm_to_abm_feedback_and_guardrail_filtering(self):
        from society import crisis_bridge
        # A) Constitutional filter blocks mass-suicide & ordinary-tier arrest hallucinations and strips tag from cards
        ord_dir = {'day': 1, 'tier': 'ordinary', 'branch': 'rutin',
                   'conditions': {'prosecution_fear': 'low', 'coverup_level': 'none'}}
        bad_llm_text = (
            "**1. İktidar Yanlıları (power_aligned)**\nSavundu.\n"
            "**2. Muhalifler (opposition)**\nSorguladı.\n"
            "**3. Yöneticiler / Otorite (authority)**\nEleştirenler tutuklandı ve hain ilan edildi.\n"
            "**4. Zenginler ve Sosyal Medya Etki Ekibi (wealthy)**\nÜç kanat izledi.\n"
            "**5. Hoşnutsuz Kesim (discontented)**\nKitlenin %15'i intihar etti.\n"
            "**6. Gözlemciler (observer)**\nOyunu izledi.\n"
            "**Günün Genel Özeti:** Tartışma sürdü.\n"
            '[ANAYASAL_GERIBESLEME: {"institutional_posture":"darvo_attack","voice_response":"suppressed","whistleblower_climate":"ostracized"}]'
        )
        parsed_cards = scenario_text.analyze_scenario(bad_llm_text)
        self.assertEqual(parsed_cards['bagli'], 6)
        self.assertNotIn('ANAYASAL_GERIBESLEME', parsed_cards['genel'])
        self.assertNotIn('ANAYASAL_GERIBESLEME', parsed_cards['kitleler']['observer'])

        fb_bad = crisis_bridge.extract_constitutional_feedback(bad_llm_text, ord_dir)
        self.assertFalse(fb_bad['constitutional_valid'])
        self.assertIn('mass_suicide_hallucination', fb_bad['rejected_extremes'])
        self.assertEqual(fb_bad['institutional_posture'], 'procedural_calm')
        self.assertEqual(fb_bad['whistleblower_climate'], 'neutral')

        # B) Valid constructive LLM feedback causally steers crisis chain into `seffaf_onarim` over 2 days
        pilot_sim = termux.create_pilot(seed=44)
        chain = termux.init_scenario_chain(pilot_sim, 'Büyük maden faciası yaşandı, denetim ihmali iddiası var')
        for _ in range(2):
            d_no = chain['day'] + 1
            direc = termux.causal_day_directive(chain, d_no, sim=pilot_sim)
            crisis_bridge.sync_day_to_engine(pilot_sim, chain, direc)
            chain['day'] = d_no
            good_fb = crisis_bridge.extract_constitutional_feedback(
                '**3. Yöneticiler (authority)**\nUzman uyarısı dikkate alındı, bağımsız denetim ve şeffaf soruşturma başlatıldı.\n'
                '[ANAYASAL_GERIBESLEME: {"institutional_posture":"transparent_repair","elite_framing":"deescalation","voice_response":"acknowledged","whistleblower_climate":"protected"}]',
                direc,
            )
            self.assertTrue(good_fb['constitutional_valid'])
            crisis_bridge.apply_constitutional_feedback(chain, good_fb)
        direc_day3 = termux.causal_day_directive(chain, 3, sim=pilot_sim)
        self.assertEqual(direc_day3['branch'], 'seffaf_onarim')


if __name__ == '__main__':
    unittest.main()
