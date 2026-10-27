"""Kart <-> AI metni bağlantı teshisleri: kopuk/yanlış bağlanan kartlar,
karakter sınırıyla yarım kalan metinler ve premium arayüz veri sözleşmesi.

Bu testler gerçek bir AI çıktısı yerine biçim varyantları kullanır; ağ isteği
yoktur. Altı kitle kimliği/tanımı (ROLE_INFO) ve davranış profilleri değişmeden
kalır; yalnızca ayrıştırma + arayüz veri akışı doğrulanır.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from society import termux, web_ui
from society.agenda_api import GEMINI_ENDPOINT, GEMINI_MODEL, GeminiAdvisor
from society.agenda import ReferenceAdvisor
from society.scenario_text import GROUPS, analyze_scenario, parse_kitle_sections


UNNUMBERED = """**Günün Gelişmesi:** Belge geldi.

**İktidar Yanlıları**
Savundu. Usulü görmezden geldi.

**Muhalifler**
Sorguladı. Belge istedi.

**Yöneticiler**
Bilgi akışını kontrol etti.

**Zenginler ve Sosyal Medya**
Kanatlar ayrıştı.

**Hoşnutsuz Kesim**
Öfke biriktirdi.

**Gözlemciler**
Mesafesini korudu.

**Genel Özet:** Kutuplaşma sürdü.
"""

INLINE_BOLD = """**1. İktidar Yanlıları** birinci cümle.
**2. Muhalifler** ikinci.
**3. Yöneticiler** üçüncü.
**4. Zenginler ve Sosyal Medya Etki Ekibi**
  • **A Kutbu Yanlısı Sosyal Medya/Zenginler:** olumluya çevirdi.
  • **B Kutbu Yanlısı Sosyal Medya/Zenginler:** büyüttü.
  • **Tarafsız / Ticari Sosyal Medya ve Zenginler:** otosansür.
**5. Hoşnutsuz Kesim** beşinci.
**6. Gözlemciler** altıncı.
**Günün Genel Özeti:** Tamam.
"""

SUMMARY_VARIANT = """### 1. İktidar Yanlıları
Savundu.
### 2. Muhalifler
Sorguladı.
### 3. Yöneticiler
Dengeledi.
### 4. Zenginler / Sosyal Medya
Üç kanat ayrıştı.
### 5. Hoşnutsuzlar
Öfkelendi.
### 6. Gözlemciler
İzledi.
**Sonuç ve Genel Değerlendirme:** Herkes yerinde kaldı. BU SON KARTA SIZMAMALI.
"""

PREAMBLE_MENTION = """Aşağıda günün genel özeti ve 6 kitlenin tepkisi var.
**1. İktidar Yanlıları (power_aligned)**
Savundu.
**2. Muhalifler (opposition)**
Sorguladı.
**3. Yöneticiler (authority)**
Korudu.
**4. Zenginler ve Sosyal Medya (wealthy)**
Kanatlar ayrıştı.
**5. Hoşnutsuz Kesim (discontented)**
Tepkili.
**6. Gözlemciler (observer)**
Mesafeli.
**Günün Genel Özeti:** Bitti.
"""

OUT_OF_ORDER = """**Günün Gelişmesi:** yeni belge.
**6. Gözlemciler** oyunu okudu.
**1. İktidar Yanlıları** savundu.
**3. Yöneticiler (authority)** dengeledi.
**2. Muhalifler** sorguladı.
**5. Hoşnutsuz Kesim** tepkili.
**4. Zenginler** kanatlar ayrıştı.
Genel Özet: tamamlandı.
"""

NO_HEADINGS = ("Bugün herkes kendi işine baktı. Ne bir kriz ne bir gelişme oldu, "
               "usul tartışması sürdü. Yöneticiler belgeyi inceledi.")


class ParserRobustnessTests(unittest.TestCase):
    def test_all_six_cards_connected_for_every_format(self):
        for name, text in (('numarasiz', UNNUMBERED), ('satir_ici', INLINE_BOLD),
                           ('ozet_cesidi', SUMMARY_VARIANT),
                           ('giriste_ozet', PREAMBLE_MENTION),
                           ('karisik_sira', OUT_OF_ORDER)):
            with self.subTest(bicim=name):
                result = analyze_scenario(text)
                self.assertEqual(result['bagli'], 6, name)
                self.assertEqual(result['eksik'], [], name)
                self.assertEqual(set(parse_kitle_sections(text)['kitleler']), set(GROUPS))

    def test_general_summary_never_bleeds_into_last_card(self):
        r = analyze_scenario(SUMMARY_VARIANT)
        self.assertIn('BU SON KARTA SIZMAMALI', r['genel'])
        for gid, metin in r['kitleler'].items():
            self.assertNotIn('BU SON KARTA SIZMAMALI', metin, gid)
        self.assertEqual(r['kitleler']['observer'], 'İzledi.')

    def test_preamble_summary_word_does_not_cut_sections(self):
        r = analyze_scenario(PREAMBLE_MENTION)
        self.assertEqual(r['bagli'], 6)
        self.assertIn('Aşağıda günün genel özeti', r['ortak'])
        self.assertEqual(r['genel'], 'Bitti.')
        self.assertEqual(r['kitleler']['observer'], 'Mesafeli.')

    def test_wealthy_subwings_stay_in_their_own_card(self):
        r = analyze_scenario(INLINE_BOLD)
        self.assertIn('A Kutbu', r['kitleler']['wealthy'])
        self.assertIn('B Kutbu', r['kitleler']['wealthy'])
        self.assertIn('Tarafsız', r['kitleler']['wealthy'])
        self.assertNotIn('A Kutbu', r['kitleler']['observer'])

    def test_out_of_order_headings_map_by_identity_not_position(self):
        r = analyze_scenario(OUT_OF_ORDER)
        self.assertEqual(r['kitleler']['observer'], 'oyunu okudu.')
        self.assertEqual(r['kitleler']['power_aligned'], 'savundu.')
        self.assertEqual(r['kitleler']['wealthy'], 'kanatlar ayrıştı.')

    def test_no_character_limit_truncates_section_text(self):
        # Eski `_tidy` 6000. karakterde kesiyordu. Simdi bolumun TAMAMI kartta.
        uzun = ('Cumle sonu. ' * 900).strip()
        text = ('**1. İktidar Yanlıları (power_aligned)**\n' + uzun + '\n'
                '**2. Muhalifler (opposition)**\nkisa.\n'
                '**Günün Genel Özeti:** bitti.')
        r = analyze_scenario(text)
        self.assertEqual(r['kitleler']['power_aligned'], uzun)
        self.assertGreater(len(r['kitleler']['power_aligned']), 6000)
        self.assertTrue(r['kitleler']['power_aligned'].endswith('Cumle sonu.'))

    def test_no_headings_is_reported_not_faked(self):
        r = analyze_scenario(NO_HEADINGS)
        self.assertEqual(r['bagli'], 0)
        self.assertEqual(r['eksik'], list(GROUPS))
        self.assertTrue(r['ortak'])
        self.assertEqual(parse_kitle_sections(NO_HEADINGS)['kitleler'], {})

    def test_explicit_ids_win_over_numbering(self):
        text = ('**6. İktidar Yanlıları (power_aligned)** savundu.\n'
                '**2. Gözlemciler (observer)** izledi.\n'
                '**Günün Genel Özeti:** bitti.')
        r = analyze_scenario(text)
        self.assertEqual(r['kitleler']['power_aligned'], 'savundu.')
        self.assertEqual(r['kitleler']['observer'], 'izledi.')

    def test_group_heading_with_summary_word_stays_a_group(self):
        text = ('**1. İktidar Yanlıları** savundu.\n'
                '**6. Gözlemciler ve Sonuç** oyunu okudu.\n'
                '**Genel Özet:** herkes yerinde kaldı.')
        r = analyze_scenario(text)
        self.assertEqual(r['kitleler']['observer'], 'oyunu okudu.')
        self.assertEqual(r['genel'], 'herkes yerinde kaldı.')

    def test_body_sentences_are_not_mistaken_for_headings(self):
        text = ('**1. İktidar Yanlıları (power_aligned)**\n'
                '• Yöneticilerin açıklamasını savundu; usulü görmezden geldi.\n'
                '**2. Muhalifler (opposition)**\n'
                '• Gözlemciler gibi davranmadı, belge istedi.\n'
                '**Günün Genel Özeti:** bitti.')
        r = analyze_scenario(text)
        self.assertEqual(r['bagli'], 2)
        self.assertIn('açıklamasını savundu', r['kitleler']['power_aligned'])
        self.assertIn('belge istedi', r['kitleler']['opposition'])


class KisaOzetTests(unittest.TestCase):
    def test_summary_never_cuts_mid_word(self):
        text = ('İlk cümle burada biter. ' * 60)
        s = termux.kisa_ozet(text, 600)
        self.assertLessEqual(len(s), 601)
        self.assertTrue(s.endswith(('…', '.', '!', '?')))
        self.assertNotIn('  ', s)
        self.assertFalse(s.rstrip('…').endswith('bit'))

    def test_short_text_unchanged(self):
        self.assertEqual(termux.kisa_ozet('Kısa metin.', 600), 'Kısa metin.')

    def test_output_format_instruction_does_not_touch_character_definitions(self):
        self.assertIn('power_aligned', termux.CIKTI_BICIMI)
        self.assertIn('Günün Genel Özeti', termux.CIKTI_BICIMI)
        # Karakter felsefesi sistem prompt'unda oldugu gibi kalir.
        self.assertIn('ALTI KİTLENİN KARAKTER FELSEFESİ', termux.PHILOSOPHY_SYSTEM_PROMPT)
        self.assertEqual(tuple(termux.ROLE_INFO), GROUPS)


class StateConnectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=str(Path(__file__).resolve().parents[1]))
        self.state = Path(self.tmp.name) / 'pilot.json'
        sim = termux.create_pilot()
        sim.save(self.state)
        self.pilot = web_ui.WebPilot(sim, ReferenceAdvisor(), self.state)

    def tearDown(self):
        self.tmp.cleanup()

    def _inject(self, full_text, legacy=False, day=1):
        chain = termux.init_scenario_chain(self.pilot.sim, 'test olayı')
        chain['day'] = day
        entry = {'day': day, 'event': 'test gelişmesi',
                 'allowed_extremes': 'YOK', 'summary': full_text[:600]}
        if not legacy:
            entry['full_text'] = full_text
        chain['history'].append(entry)

    def test_every_card_has_connection_state(self):
        self._inject(UNNUMBERED)
        s = web_ui.build_state(self.pilot)
        self.assertEqual(s['baglanti']['bagli'], 6)
        self.assertEqual(s['baglanti']['durum'], 'tam')
        self.assertEqual(s['baglanti']['kaynak'], 'tam-metin')
        self.assertFalse(s['baglanti']['kesik'])
        self.assertEqual(len(s['kitleler']), 6)
        for c in s['kitleler']:
            self.assertEqual(c['ai_durum'], 'tam', c['id'])
            self.assertTrue(c['ai_metni'], c['id'])
            self.assertEqual(c['ai_karakter'], len(c['ai_metni']))
            self.assertEqual(c['ai_gun'], 1)
            self.assertFalse(c['ai_kesik'])
            self.assertEqual(c['ai_kaynak'], 'tam-metin')

    def test_full_text_is_stored_for_timeline_and_cards(self):
        self._inject(SUMMARY_VARIANT)
        s = web_ui.build_state(self.pilot)
        gun = s['senaryo']['gunler']['1']
        self.assertEqual(gun['metin'], SUMMARY_VARIANT)
        self.assertEqual(gun['karakter'], len(SUMMARY_VARIANT))
        self.assertTrue(gun['metin'].endswith('BU SON KARTA SIZMAMALI.\n'))
        self.assertEqual(gun['bagli'], 6)
        self.assertNotIn('BU SON KARTA SIZMAMALI', s['kitleler'][-1]['ai_metni'])

    def test_legacy_600_char_record_is_labelled_not_presented_as_full(self):
        self._inject(UNNUMBERED, legacy=True)
        s = web_ui.build_state(self.pilot)
        self.assertEqual(s['baglanti']['durum'], 'eski')
        self.assertEqual(s['baglanti']['kaynak'], 'eski-ozet')
        self.assertTrue(s['baglanti']['kesik'])
        self.assertIn('600 karakterlik özet', s['baglanti']['aciklama'])
        for c in s['kitleler']:
            if c['ai_metni']:
                self.assertEqual(c['ai_durum'], 'eski')
                self.assertTrue(c['ai_kesik'])
        self.assertEqual(s['senaryo']['gunler']['1']['kaynak'], 'eski-ozet')

    def test_partial_or_missing_sections_fall_back_to_shared_text(self):
        self._inject(NO_HEADINGS)
        s = web_ui.build_state(self.pilot)
        self.assertEqual(s['baglanti']['bagli'], 0)
        self.assertEqual(s['baglanti']['durum'], 'kismi')
        self.assertEqual(s['baglanti']['eksik'], list(GROUPS))
        for c in s['kitleler']:
            self.assertEqual(c['ai_durum'], 'ortak')
            self.assertIn('usul tartışması sürdü', c['ai_ortak'])
            self.assertEqual(c['ai_metni'], '')
        self.assertTrue(s['senaryo']['gunler']['1']['ortak'])

    def test_no_scenario_means_waiting_cards_not_broken_cards(self):
        s = web_ui.build_state(self.pilot)
        self.assertEqual(s['baglanti']['durum'], 'yok')
        for c in s['kitleler']:
            self.assertEqual(c['ai_durum'], 'yok')
            self.assertEqual(c['ai_metni'], '')
            self.assertEqual(c['ai_ortak'], '')

    def test_day_selector_keeps_each_days_own_connections(self):
        chain = termux.init_scenario_chain(self.pilot.sim, 'test olayı')
        chain['day'] = 2
        chain['history'] = [
            {'day': 1, 'event': 'bir', 'allowed_extremes': '', 'summary': NO_HEADINGS[:600],
             'full_text': NO_HEADINGS},
            {'day': 2, 'event': 'iki', 'allowed_extremes': '', 'summary': UNNUMBERED[:600],
             'full_text': UNNUMBERED},
        ]
        bir = web_ui.build_state(self.pilot, secili_gun='1')
        iki = web_ui.build_state(self.pilot, secili_gun='2')
        self.assertEqual(bir['baglanti']['bagli'], 0)
        self.assertEqual(iki['baglanti']['bagli'], 6)
        self.assertTrue(all(c['ai_gun'] == 2 for c in iki['kitleler']))

    def test_state_is_json_safe_and_key_free(self):
        self._inject(UNNUMBERED)
        s = web_ui.build_state(self.pilot)
        json.dumps(s, ensure_ascii=False, allow_nan=False)
        self.assertNotIn('PEOPLE1000_API_KEY', json.dumps(s, ensure_ascii=False))

    def test_last_output_survives_server_restart(self):
        web_ui.execute_command(self.pilot, {'cmd': 'ozet'})
        again = web_ui.WebPilot(self.pilot.sim, ReferenceAdvisor(), self.state)
        self.assertIn('KİTLE', again.last_output)
        self.assertEqual(again.last_command, 'ozet')
        self.assertEqual(web_ui.build_state(again)['son_komut'], 'ozet')


class PilotGecisTests(unittest.TestCase):
    """Termux kurulum scripti + dolu soru kotasi ile uretim testi."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=str(Path(__file__).resolve().parents[1]))
        self.state = Path(self.tmp.name) / 'pilot.json'
        sim = termux.create_pilot()
        sim.save(self.state)
        self.pilot = web_ui.WebPilot(sim, ReferenceAdvisor(), self.state)

    def tearDown(self):
        self.tmp.cleanup()

    def test_setup_script_offers_web_ui_and_keeps_terminal_option(self):
        from subprocess import run
        script = Path(__file__).resolve().parents[1] / 'tools' / 'termux_setup.sh'
        text = script.read_text(encoding='utf-8')
        self.assertIn('python -m society.web_ui --state runs/gemini-pilot.json --open', text)
        self.assertIn('w=web arayuzu', text)
        self.assertIn('python -m society.termux --state runs/gemini-pilot.json', text)
        checked = run(['bash', '-n', str(script)], capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_production_test_is_not_blocked_by_full_question_quota(self):
        advisor = GeminiAdvisor(GEMINI_ENDPOINT, GEMINI_MODEL, min_interval=0)
        pilot = web_ui.WebPilot(self.pilot.sim, advisor, self.state)
        meta = self.pilot.sim.protocol['termux_pilot']
        meta['question_attempts'] = meta['question_limit'] = 5
        with patch.object(termux, 'ask_operator', return_value='BAGLANTI TAMAM') as spy:
            message, _ = web_ui.execute_command(
                pilot, {'cmd': 'uretim-test', 'confirm': True})
        self.assertEqual(message, 'BAGLANTI TAMAM')
        self.assertEqual(meta['question_limit'], 6)
        self.assertTrue(spy.called)

    def test_production_test_still_requires_confirmation(self):
        with self.assertRaises(ValueError):
            web_ui.execute_command(self.pilot, {'cmd': 'uretim-test'})


class HealthAndPageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=str(Path(__file__).resolve().parents[1]))
        self.state = Path(self.tmp.name) / 'pilot.json'
        sim = termux.create_pilot()
        sim.save(self.state)
        self.pilot = web_ui.WebPilot(sim, ReferenceAdvisor(), self.state)

    def tearDown(self):
        self.tmp.cleanup()

    def test_page_has_connection_map_and_no_key(self):
        page = web_ui.PAGE
        for needle in ('id="rail"', 'id="linkBanner"', 'data-copy="output"',
                       '/api/health', 'ai_durum', 'GÜNÜN ORTAK ANLATIMI',
                       'People1000 — Anlatım Konsolu', 'PEOPLE'):
            self.assertIn(needle, page)
        self.assertNotIn('PEOPLE1000_API_KEY', page)
        self.assertNotIn('API_KEY=', page)
        for cmd in ('gun', 'ilerle', 'ozet', 'rapor', 'sor', 'devam', 'olay',
                    'ayar', 'kaydet', 'yardim', 'baglanti', 'modeller',
                    'uretim-test', 'bekleme', 'limit', 'sor-limit'):
            self.assertIn('data-cmd="' + cmd + '"', page)

    def test_health_endpoint_reports_card_count(self):
        import threading
        from urllib.request import urlopen
        server = web_ui.create_server('127.0.0.1', 0, self.pilot)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f'http://127.0.0.1:{server.server_address[1]}/api/health',
                         timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
            self.assertTrue(data['ok'])
            self.assertEqual(data['kart'], 6)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
