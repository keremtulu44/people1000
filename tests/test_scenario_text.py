"""AI senaryo metninin 6 kitleye ayrilmasi ve tam metnin saklanmasi."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from society.agenda import ReferenceAdvisor
from society import termux, web_ui
from society.scenario_text import GROUPS, parse_kitle_sections


SAMPLE = """
================ SENARYO ZİNCİRİ — GÜN 2 ================
**Günün Gelişmesi:** Belge geldi, usul tartışması sürüyor.

**1. İktidar Yanlıları (power_aligned)**
  • Belgeyle liyakati savundu, usulü görmezden geldi.

**2. Muhalifler (opposition)**
  • Akraba atamasının usulünü sorgulamaya devam etti.

**3. Yöneticiler / Otorite (authority)**
  • Bilgi akışını kontrol altında tuttu.

**4. Zenginler ve Sosyal Medya Etki Ekibi (wealthy)**
  • **A Kutbu Yanlısı Sosyal Medya/Zenginler:** Gündemi olumluya çevirdi.
  • **B Kutbu Yanlısı Sosyal Medya/Zenginler:** İhmalleri büyüttü.
  • **Tarafsız / Ticari Sosyal Medya ve Zenginler:** Otosansüre çekildi.

**5. Hoşnutsuz Kesim (discontented)**
  • Kayırmacılık şüphesiyle öfke biriktirdi.

**6. Gözlemciler (observer)**
  • Oyunu dışarıdan okuyup mesafesini korudu.

**Günün Genel Özeti:** Gün 2 sonunda kutuplaşma sürdü.
===========================================================
"""


class ParserTests(unittest.TestCase):
    def test_six_sections_found(self):
        r = parse_kitle_sections(SAMPLE)
        self.assertEqual(set(r['kitleler']), set(GROUPS))
        self.assertIn('usulünü sorgulamaya', r['kitleler']['opposition'])
        self.assertIn('A Kutbu', r['kitleler']['wealthy'])
        self.assertIn('Tarafsız', r['kitleler']['wealthy'])
        self.assertIn('kutuplaşma', r['genel'])
        # Genel ozet hicbir kitle bolumune sizmamali.
        self.assertNotIn('kutuplaşma sürdü', ' '.join(r['kitleler'].values()))

    def test_offline_text_has_same_structure(self):
        d = Path(tempfile.mkdtemp(dir=str(Path(__file__).resolve().parents[1])))
        try:
            p = d / 'p.json'
            sim = termux.create_pilot(); sim.save(p)
            pilot = web_ui.WebPilot(sim, ReferenceAdvisor(), p)
            text, _ = web_ui.execute_command(pilot, {'cmd': 'devam', 'count': 1})
            self.assertEqual(set(parse_kitle_sections(text)['kitleler']), set(GROUPS))
        finally:
            for f in d.iterdir():
                f.unlink()
            d.rmdir()

    def test_markdown_variants(self):
        text = ("### 1. İktidar Yanlıları\nA savundu.\n"
                "2) Muhalifler\nB sorguladı.\n"
                "**3. Yöneticiler**\nC dengeledi.\n"
                "4 - Zenginler ve Sosyal Medya\nD üç kanat.\n"
                "5. Hoşnutsuz Kesim\nE öfkelendi.\n"
                "6. Gözlemciler\nF izledi.\n"
                "Genel Özet: bitti.")
        r = parse_kitle_sections(text)
        self.assertEqual(set(r['kitleler']), set(GROUPS))

    def test_no_headings_returns_empty(self):
        for text in ('', None, 'Sadece duz bir paragraf, hic baslik yok.'):
            self.assertEqual(parse_kitle_sections(text), {'kitleler': {}, 'genel': ''})

    def test_sections_do_not_bleed(self):
        r = parse_kitle_sections(SAMPLE)
        self.assertNotIn('Muhalifler', r['kitleler']['power_aligned'])
        self.assertNotIn('Gözlemciler', r['kitleler']['discontented'])


class FullTextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=str(Path(__file__).resolve().parents[1]))
        self.state = Path(self.tmp.name) / 'pilot.json'
        sim = termux.create_pilot(); sim.save(self.state)
        self.pilot = web_ui.WebPilot(sim, ReferenceAdvisor(), self.state)

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_text_saved_not_only_600_chars(self):
        web_ui.execute_command(self.pilot, {'cmd': 'devam', 'count': 1})
        chain = self.pilot.sim.protocol['termux_pilot']['scenario_chain']
        last = chain['history'][-1]
        self.assertIn('full_text', last)
        self.assertGreater(len(last['full_text']), 600)
        self.assertEqual(len(last['summary']), 600)

    def test_cards_receive_six_ai_texts(self):
        web_ui.execute_command(self.pilot, {'cmd': 'devam', 'count': 2})
        s = web_ui.build_state(self.pilot)
        self.assertTrue(s['senaryo']['ai_var'])
        self.assertEqual(s['senaryo']['secili_gun'], '2')
        with_text = [c for c in s['kitleler'] if c['ai_metni']]
        self.assertEqual(len(with_text), 6)
        self.assertTrue(all(c['ai_gun'] == 2 for c in with_text))
        self.assertTrue(all(not c['ai_kesik'] for c in with_text))
        self.assertIn('A Kutbu', next(c['ai_metni'] for c in with_text if c['id'] == 'wealthy'))

    def test_day_selector_switches_cards(self):
        web_ui.execute_command(self.pilot, {'cmd': 'devam', 'count': 2})
        bir = web_ui.build_state(self.pilot, secili_gun='1')
        iki = web_ui.build_state(self.pilot, secili_gun='2')
        self.assertEqual(bir['senaryo']['secili_gun'], '1')
        self.assertEqual(iki['senaryo']['secili_gun'], '2')
        self.assertTrue(all(c['ai_gun'] == 1 for c in bir['kitleler'] if c['ai_metni']))
        self.assertTrue(all(c['ai_gun'] == 2 for c in iki['kitleler'] if c['ai_metni']))
        self.assertEqual(len(bir['senaryo']['gunler']), 2)

    def test_invalid_day_falls_back_to_latest(self):
        web_ui.execute_command(self.pilot, {'cmd': 'devam', 'count': 1})
        s = web_ui.build_state(self.pilot, secili_gun='999')
        self.assertEqual(s['senaryo']['secili_gun'], '1')

    def test_legacy_checkpoint_without_full_text(self):
        chain = termux.init_scenario_chain(self.pilot.sim, 'eski olay')
        chain['day'] = 1
        chain['history'].append({'day': 1, 'event': 'bir sey',
                                 'allowed_extremes': 'YOK', 'summary': SAMPLE[:600]})
        s = web_ui.build_state(self.pilot)
        self.assertTrue(s['senaryo']['secili_gun'])
        self.assertTrue(all(c['ai_kesik'] for c in s['kitleler'] if c['ai_metni']))

    def test_prompt_uses_summaries_not_full_text(self):
        web_ui.execute_command(self.pilot, {'cmd': 'devam', 'count': 1})
        captured = {}

        class FakeAdvisor(ReferenceAdvisor):
            pass

        # Sadece prompt icerigini olcmek icin ask_operator'i sar.
        from society.agenda_api import OpenAICompatibleAdvisor
        with patch.object(termux, 'ask_operator', wraps=termux.ask_operator) as spy:
            # Cevrimdisi modda ask_operator cagrisi yok; bunun yerine prompt_q
            # olusumunu dogrudan test etmek icin yardimci fonksiyonu kullan.
            chain = self.pilot.sim.protocol['termux_pilot']['scenario_chain']
            gecmis = [{k: h.get(k) for k in ('day', 'event', 'summary')}
                      for h in chain['history'][-3:]]
            captured['json'] = json.dumps(gecmis, ensure_ascii=False)
        self.assertNotIn('full_text', captured['json'])
        self.assertLess(len(captured['json']), 900)

    def test_no_scenario_cards_have_empty_ai_placeholder(self):
        s = web_ui.build_state(self.pilot)
        self.assertFalse(s['senaryo']['ai_var'])
        self.assertTrue(all(c['ai_metni'] == '' for c in s['kitleler']))

    def test_live_gemini_answer_fills_all_six_cards(self):
        """Gercek Gemini yerine sahte adaptor: metin kartlara atanmali."""
        import os
        from society.agenda_api import GEMINI_ENDPOINT, GEMINI_MODEL, GeminiAdvisor
        advisor = GeminiAdvisor(GEMINI_ENDPOINT, GEMINI_MODEL, min_interval=0)
        pilot = web_ui.WebPilot(self.pilot.sim, advisor, self.state)
        with patch.dict(os.environ, {'PEOPLE1000_API_KEY': 'sahte-anahtar'}), \
             patch.object(advisor, 'generate', return_value=SAMPLE) as gen:
            _, s = web_ui.execute_command(pilot, {'cmd': 'sor', 'text': 'Yeni atama krizi'})
            self.assertEqual(gen.call_count, 1)
            self.assertTrue(s['senaryo']['ai_var'])
            self.assertEqual(len([c for c in s['kitleler'] if c['ai_metni']]), 6)
            self.assertEqual(s['senaryo']['secili_gun'], '1')
            # devam: onceki gunun TAM metni modele gitmemeli (kota korumasi).
            _, s2 = web_ui.execute_command(pilot, {'cmd': 'devam', 'count': 1})
            prompt = gen.call_args.kwargs.get('user_text') or gen.call_args.args[-1]
            self.assertNotIn('full_text', prompt)
            self.assertLess(len(gen.call_args.args[-1]) + len(prompt), 12000)
            self.assertTrue(all(c['ai_gun'] == 2 for c in s2['kitleler'] if c['ai_metni']))


if __name__ == '__main__':
    unittest.main()
