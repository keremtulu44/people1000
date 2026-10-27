"""People1000 — Termux icin yerel web arayuzu (yalnizca standart kutuphane).

Motor Termux'ta arkada calisir; tarayici bu sunucuya baglanir. API anahtari
yalnizca sunucu surecinde kalir, HTML/JS icine hicbir zaman yazilmaz.

    python -m society.web_ui --state runs/gemini-pilot.json
    # telefon tarayicisi: http://127.0.0.1:8501

Bu modul termux.py'nin komutlarini yeniden kullanir; yeni secenek eklemez.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .agenda import ReferenceAdvisor
from .agenda_api import (AgendaProvider, GeminiAdvisor, OpenAICompatibleAdvisor,
                         advisor_from_environment)
from .engine import Simulation
from .session import Session
from . import psychology, termux
from .scenario_text import GROUPS, analyze_scenario, parse_kitle_sections  # noqa: F401

MAX_TEXT = 2000
MAX_DAYS = 30
HISTORY_LIMIT = 400
OUTPUT_LIMIT = 60000  # yalnızca terminal çıktısı paneli; AI kart metni kesilmez
COMMANDS = frozenset({
    'gun', 'ilerle', 'ozet', 'rapor', 'sor', 'devam', 'olay', 'ayar', 'kaydet',
    'yardim', 'baglanti', 'modeller', 'uretim-test', 'bekleme', 'limit',
    'sor-limit', 'token-limit'})


def _short_name(title):
    """'1. Iktidar Yanlilari (power_aligned)' -> 'Iktidar Yanlilari'."""
    return re.sub(r'\s*\([^)]*\)\s*$', '', re.sub(r'^\d+\.\s*', '', title)).strip()


def _json_safe(value):
    """JSON.parse'i bozan NaN/Infinity degerlerini None'a cevir."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _metrics_snapshot(r):
    by = r.get('issue_by_role', {})
    return {g: {'yeterlilik': round(info.get('qualification', .5) * 100),
                'usul': round(info.get('procedure', .5) * 100)} for g, info in by.items()}


def _day(sim):
    return sim.time // 1440 + 1 if sim.time > 0 else 0


def kitle_cards(r, previous=None):
    """Raporu, her zaman 6 kartlik sabit bir gorunum semasina cevir."""
    by = r.get('issue_by_role', {})
    previous = previous or {}
    cards = []
    for i, (gid, (title, desc)) in enumerate(termux.ROLE_INFO.items(), 1):
        info = by.get(gid)
        lr = (info or {}).get('last_response') or {}
        app = lr.get('approach', 'reserve')
        expr = lr.get('expression', app)
        qual = (info or {}).get('qualification', .5)
        proc = (info or {}).get('procedure', .5)
        q = round(qual * 100) if info else None
        p = round(proc * 100) if info else None
        prev = previous.get(gid, {})
        cards.append({
            'id': gid, 'sira': i, 'ad': _short_name(title), 'tanim': desc,
            'var': bool(info),
            'eylem': termux.APPROACH_TR.get(app, app) if info else 'Henuz gundem ulasmadi',
            'ifade': termux.EXPR_TR.get(expr, expr) if info else '',
            'yeterlilik': q, 'usul': p,
            'fark_yeterlilik': None if q is None or prev.get('yeterlilik') is None else q - prev['yeterlilik'],
            'fark_usul': None if p is None or prev.get('usul') is None else p - prev['usul'],
            'ozet': (termux._role_summary_tr(gid, app, qual, proc) if info else
                     'Gundem bu kitleye ulasmadi; "Gun ilerlet" ile devam et.'),
            'model_notu': lr.get('reason') or '',
        })
    return cards


class WebPilot:
    """Paylasilan simülasyon durumu; tum erisim tek kilit altinda."""

    def __init__(self, sim, advisor, state_path):
        self.sim = sim
        self.advisor = advisor
        self.state_path = Path(state_path)
        self.session = Session(sim, AgendaProvider(advisor))
        self.lock = threading.RLock()
        self.cached_day = _day(sim)
        self.history_path = self.state_path.with_suffix('.history.json')
        self.last_path = self.state_path.parent / (self.state_path.stem + '.last.json')
        self.history = self._load_history()
        if not self.history:
            # Baslangic anlik goruntusu: ilk gunun "dune gore" farki hesaplansin.
            self.history = [{'day': self.cached_day, 'kitleler': _metrics_snapshot(termux.report(sim))}]
            self._save_history()
        # Son cikti, sunucu yeniden baslasa da geri gelsin (kucuk yan dosya).
        last = self._load_last()
        self.last_output = last.get('output', '')
        self.last_command = last.get('command', '')

    def record_history_snapshot(self):
        day = _day(self.sim)
        self.cached_day = day
        current = {'day': day, 'kitleler': _metrics_snapshot(termux.report(self.sim))}
        if self.history and self.history[-1]['day'] == day:
            self.history[-1] = current
        else:
            self.history.append(current)
        self.history = self.history[-HISTORY_LIMIT:]
        self._save_history()

    def _load_history(self):
        try:
            data = json.loads(self.history_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return []
        return data[-HISTORY_LIMIT:] if isinstance(data, list) else []

    def _save_history(self):
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            self.history_path.write_text(
                json.dumps(self.history, ensure_ascii=False), encoding='utf-8')
        except OSError:
            pass  # gecmis olmasa da arayuz calisir

    def _load_last(self):
        try:
            data = json.loads(self.last_path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                return {}
            return {'output': data.get('output', '') if isinstance(data.get('output', ''), str) else '',
                    'command': data.get('command', '') if isinstance(data.get('command', ''), str) else ''}
        except (OSError, ValueError):
            return {}

    def _save_last(self):
        try:
            self.last_path.parent.mkdir(parents=True, exist_ok=True)
            self.last_path.write_text(json.dumps(
                {'output': self.last_output, 'command': self.last_command},
                ensure_ascii=False), encoding='utf-8')
        except OSError:
            pass  # son cikti kaybolabilir; arayuz calismaya devam eder

    def redact(self, text):
        key = os.environ.get(getattr(self.advisor, 'key_env', ''), '') or \
              os.environ.get('PEOPLE1000_API_KEY', '')
        return text.replace(key, '[REDACTED]') if key and isinstance(text, str) else text

    def save(self):
        self.cached_day = _day(self.sim)
        self.sim.save(self.state_path)


def _bos_baglanti():
    """Secili gun yokken kart baglanti ozeti."""
    return {'bagli': 0, 'toplam': len(GROUPS), 'eksik': list(GROUPS),
            'kesik': False, 'yarim': False, 'karakter': 0, 'baslik': 0,
            'kaynak': 'yok', 'durum': 'yok', 'aciklama': 'Henüz AI anlatımı yok.'}


def _baglanti_ozeti(gun):
    """Bir senaryo gununun 6 kartla baglanti teshisi (arayuz + denetim)."""
    if not gun:
        return _bos_baglanti()
    bagli = gun.get('bagli', 0)
    eksik = gun.get('eksik', list(GROUPS))
    eski = gun.get('kaynak') == 'eski-ozet'
    metin_var = bool(gun.get('metin'))
    if not metin_var:
        durum = 'yok'
    elif eski:
        durum = 'eski'
    elif bagli == len(GROUPS):
        durum = 'tam'
    else:
        durum = 'kismi'
    if durum == 'tam':
        aciklama = '6 kartın tamamı kendi AI metnine bağlı; tam metin gösteriliyor.'
    elif durum == 'eski':
        aciklama = ('Eski kayıt: yalnızca 600 karakterlik özet var, tam metin '
                    'yok. Yeni bir Devam/Olay ile tam metin üretilebilir.')
    elif durum == 'kismi':
        aciklama = (f'{bagli}/6 kartta kitleye özel bölüm bulundu; '
                    f'{len(eksik)} kart günün ortak metnine bağlı.')
    else:
        aciklama = 'Bu gün için AI metni kayıtta yok.'
    return {'bagli': bagli, 'toplam': len(GROUPS), 'eksik': eksik,
            'kesik': bool(gun.get('kesik')), 'yarim': bool(gun.get('yarim')),
            'karakter': gun.get('karakter', 0), 'baslik': gun.get('baslik', 0),
            'kaynak': gun.get('kaynak', 'yok'), 'durum': durum,
            'aciklama': aciklama}


def build_state(pilot, secili_gun=None):
    """GET /api/state icin tum ekran verisi. Anahtar icermez, diske yazmaz.

    secili_gun: kartlarda gosterilecek senaryo gunu; verilmezse en son gun.
    """
    with pilot.lock:
        r = termux.report(pilot.sim)
        day = _day(pilot.sim)
        pilot.cached_day = day
        current = {'day': day, 'kitleler': _metrics_snapshot(r)}
        if pilot.history and pilot.history[-1]['day'] == day:
            pilot.history[-1] = current
        else:
            pilot.history.append(current)
        pilot.history = pilot.history[-HISTORY_LIMIT:]
        previous = pilot.history[-2]['kitleler'] if len(pilot.history) > 1 else {}

        wm = r.get('world_metrics', {})
        rev = r.get('reviews', {})
        statuses = rev.get('statuses', {})
        meta = pilot.sim.protocol['termux_pilot']
        diag = r.get('diagnostics', {})
        q = r.get('operator_questions', {})
        chain = meta.get('scenario_chain')
        scenario = {'var': bool(chain), 'ilk_olay': '', 'gun': 0, 'seviye': 'ordinary',
                    'alan': 'ordinary', 'gecmis': [], 'gunler': {}, 'secili_gun': None,
                    'ai_var': False, 'baglanti': _bos_baglanti()}
        if chain:
            gunler = {}
            gecmis = []
            for h in chain.get('history', []):
                # Yeni kayitlarda TAM metin; eski kayitlarda yalnizca 600
                # karakterlik ozet vardir ve bu acikca isaretlenir. Kartlara
                # giden metin hicbir karakter siniriyla kesilmez.
                eski = 'full_text' not in h
                tam = h.get('full_text') or h.get('summary') or ''
                parsed = analyze_scenario(tam, legacy=eski)
                d = h.get('day')
                gunler[str(d)] = {
                    'day': d, 'event': h.get('event', ''),
                    'dal': h.get('branch', ''),
                    'motor_etkisi': h.get('engine_effects') or {},
                    'sinir': h.get('allowed_extremes', ''),
                    'metin': tam, 'genel': parsed['genel'],
                    'ortak': parsed['ortak'], 'kitleler': parsed['kitleler'],
                    'kesik': parsed['kesik'], 'yarim': parsed['yarim'],
                    'bagli': parsed['bagli'], 'eksik': parsed['eksik'],
                    'baslik': parsed['baslik'], 'karakter': parsed['karakter'],
                    'kaynak': 'eski-ozet' if eski else 'tam-metin',
                }
                gecmis.append(gunler[str(d)])
            son_gun = str(chain.get('day', 0)) if gunler else None
            if secili_gun is not None and str(secili_gun) in gunler:
                son_gun = str(secili_gun)
            elif son_gun not in gunler and gecmis:
                son_gun = str(gecmis[-1]['day'])
            scenario = {'var': True, 'ilk_olay': chain.get('initial_event', ''),
                        'gun': chain.get('day', 0),
                        'seviye': chain.get('tier', 'ordinary'),
                        'alan': chain.get('domain') or termux.classify_domain(chain.get('initial_event', '')),
                        'gecmis': gecmis,
                        'gunler': gunler, 'secili_gun': son_gun,
                        'ai_var': any(g['kitleler'] or g['metin'] for g in gunler.values()),
                        'baglanti': _baglanti_ozeti(gunler.get(son_gun))}
        # Kartlara atanacak AI metni ve psikolojik durum: secili gunun 6 kitlesi.
        secili = scenario['gunler'].get(scenario['secili_gun'], {}) if scenario['var'] else {}
        ai_kitleler = secili.get('kitleler', {}) if isinstance(secili, dict) else {}
        ortak_metin = '\n\n'.join(
            x for x in (secili.get('ortak', ''), secili.get('genel', '')) if x)
        eski_kayit = secili.get('kaynak') == 'eski-ozet'
        upto_day = (int(scenario['secili_gun'])
                    if scenario['var'] and scenario['secili_gun'] and str(scenario['secili_gun']).isdigit()
                    else None)
        psych_map = psychology.group_summary(
            pilot.sim, chain if scenario['var'] else None, upto_day=upto_day)
        events = [{'time': e.get('time'), 'kind': e.get('kind', '')}
                  for e in pilot.sim.log[-12:]]
        settings = termux.settings(pilot.advisor)
        cards = kitle_cards(r, previous)
        for c in cards:
            metin = ai_kitleler.get(c['id'], '')
            c['ai_metni'] = metin
            c['ai_gun'] = secili.get('day') if metin else None
            c['ai_kesik'] = bool(eski_kayit) if metin else False
            c['ai_durum'] = ('eski' if eski_kayit else 'tam') if metin else (
                'ortak' if ortak_metin else 'yok')
            c['ai_ortak'] = '' if metin else ortak_metin
            c['ai_karakter'] = len(metin)
            c['ai_kaynak'] = secili.get('kaynak', 'yok')
            c['psikoloji'] = psych_map.get(c['id'], {})
        return _json_safe({
            'baglanti': scenario['baglanti'],
            'day': day,
            'mode': 'offline' if settings.get('mode') == 'offline' else 'live',
            'settings': settings,
            'kitleler': cards,
            'dunya': {
                'taraf_degisimi': wm.get('alignment_changes', 0),
                'ideoloji_degisimi': wm.get('core_changes', 0),
                'ortalama_sadakat': wm.get('mean_private_loyalty'),
                'ortalama_guven': wm.get('mean_trust'),
                'kayiplar': wm.get('losses'),
            },
            'api': {
                'deneme': rev.get('attempts', 0),
                'kabul': statuses.get('accepted', 0),
                'ag_istekleri': rev.get('network_attempts', 0),
                'soru': q.get('attempts', 0), 'soru_limiti': q.get('limit', 0),
                'teshis': diag.get('attempts', 0), 'teshis_limiti': diag.get('limit', 10),
            },
            'limitler': {
                'toplam': pilot.sim.behavior_profile['agenda_dynamics'].get('total_review_limit'),
                'gunluk': pilot.sim.behavior_profile['agenda_dynamics'].get('daily_review_limit'),
            },
            'senaryo': scenario,
            'sosyal_zihin': psychology.social_mind_overview(psych_map),
            'hafiza': r.get('institutional_memory', {}),
            'olaylar': events,
            'ozet_metni': termux.turkce_ozet(pilot.sim),
            'son_cikti': pilot.last_output,
            'son_komut': pilot.last_command,
            'gecmis_gunler': [h['day'] for h in pilot.history],
        })


def _text(payload):
    value = payload.get('text', '')
    if not isinstance(value, str) or not 0 < len(value.strip()) <= MAX_TEXT:
        raise ValueError(f'Metin 1–{MAX_TEXT} karakter olmali.')
    return value.strip()


def _int(payload, key, lo, hi, default=None):
    value = payload.get(key, default)
    if type(value) is bool or not isinstance(value, (int, float)):
        raise ValueError(f'{key} sayisal olmali.')
    value = int(value)
    if not lo <= value <= hi or value != payload.get(key, default):
        raise ValueError(f'{key} {lo}–{hi} arasinda tam sayi olmali.')
    return value


def execute_command(pilot, payload):
    """Terminal komutlarinin aynisini calistirir; (mesaj, yeni durum) dondurur."""
    if not isinstance(payload, dict):
        raise ValueError('Gecersiz istek.')
    cmd = payload.get('cmd')
    if cmd not in COMMANDS:
        raise ValueError('Bilinmeyen komut.')
    confirm = payload.get('confirm') is True
    with pilot.lock:
        sim, advisor, meta = pilot.sim, pilot.advisor, pilot.sim.protocol['termux_pilot']
        out = ''
        if cmd in ('gun', 'ilerle'):
            count = 1 if cmd == 'gun' else _int(payload, 'count', 1, MAX_DAYS, 1)
            for _ in range(count):
                pilot.session.day(checkpoint=pilot.state_path)
                pilot.record_history_snapshot()
            out = f'{count} gun ilerletildi. Simulasyon zamani: {sim.time} dk.'
        elif cmd == 'ozet':
            out = termux.turkce_ozet(sim)
        elif cmd == 'rapor':
            out = json.dumps(termux.report(sim), ensure_ascii=False, indent=2)
        elif cmd == 'ayar':
            out = json.dumps(termux.settings(advisor), ensure_ascii=False, indent=2)
        elif cmd == 'yardim':
            out = termux.HELP
        elif cmd == 'kaydet':
            pilot.save(); pilot.record_history_snapshot(); out = 'Kaydedildi.'
        elif cmd == 'sor':
            question = _text(payload)
            try:
                out = termux.start_scenario(sim, question, advisor)
                pilot.record_history_snapshot()
            finally:
                pilot.save()
        elif cmd == 'devam':
            count = _int(payload, 'count', 1, MAX_DAYS, 1)
            try:
                out = '\n\n'.join(termux.advance_scenario_days(
                    sim, advisor, count, checkpoint=pilot.state_path))
                pilot.record_history_snapshot()
            finally:
                pilot.save()
        elif cmd == 'olay':
            custom = _text(payload)
            try:
                out = '\n\n'.join(termux.advance_scenario_days(
                    sim, advisor, 1, checkpoint=pilot.state_path, custom_event=custom))
                pilot.record_history_snapshot()
            finally:
                pilot.save()
        elif cmd in ('baglanti', 'modeller'):
            if not confirm:
                raise ValueError('Bu komut 1 metadata istegi atar; once onay verin.')
            if not isinstance(advisor, GeminiAdvisor):
                raise ValueError('Metadata denetimi yalnizca Gemini adaptorunde var.')
            try:
                out = json.dumps(termux.metadata_check(
                    sim, advisor, list_models=cmd == 'modeller'), ensure_ascii=False, indent=2)
                out += '\nBu yalniz metadata kontrolu; uretim veya ucretsiz kota garantisi vermez.'
            finally:
                pilot.save()
        elif cmd == 'uretim-test':
            if not confirm:
                raise ValueError('Bu komut 1 uretim istegi atar; once onay verin.')
            # Acik onay verilmis tek uretim denemesi, eski kayitta dolmus olan
            # soru/senaryo sayacina takilmasin (sor/devam'daki gibi 1 artir).
            if isinstance(advisor, OpenAICompatibleAdvisor) and \
                    meta['question_attempts'] >= meta['question_limit']:
                meta['question_limit'] = meta['question_attempts'] + 1
            try:
                out = termux.ask_operator(sim, 'Kisa baglanti testi.', advisor, connection_test=True)
            finally:
                pilot.save()
        elif cmd == 'bekleme':
            if not isinstance(advisor, OpenAICompatibleAdvisor):
                raise ValueError('Cevrimdisi modda bekleme suresi kullanilmaz.')
            sec = _int(payload, 'seconds', 0, 60, 6)
            advisor.min_interval = sec
            out = f'İstekler arasi en az bekleme suresi {sec} sn.'
        elif cmd == 'limit':
            total = _int(payload, 'total', 1, 200, 30)
            daily = _int(payload, 'daily', 1, 200, 10)
            if not 1 <= daily <= total <= 200:
                raise ValueError('1 <= gunluk <= toplam <= 200 olmali.')
            sim.behavior_profile['agenda_dynamics'].update(
                total_review_limit=total, daily_review_limit=daily)
            meta.setdefault('budget_changes', []).append(
                {'time': sim.time, 'total': total, 'daily': daily})
            pilot.save(); out = 'Acik istek tavani guncellendi; harcama garantisi degildir.'
        elif cmd == 'sor-limit':
            qlim = _int(payload, 'count', 1, 200, 5)
            meta['question_limit'] = qlim
            pilot.save(); out = f'Soru/senaryo deneme siniri {qlim} olarak guncellendi.'
        elif cmd == 'token-limit':
            if not isinstance(advisor, OpenAICompatibleAdvisor):
                raise ValueError('Cevrimdisi modda cikti token siniri kullanilmaz.')
            tok = _int(payload, 'tokens', 256, 8192, 2048)
            advisor.max_output_tokens = tok
            if 'timeout' in payload:
                advisor.timeout = _int(payload, 'timeout', 5, 120, advisor.timeout)
            out = f'Cikti token siniri {tok} (zaman asimi: {advisor.timeout} sn) olarak guncellendi.'

        pilot.last_output = pilot.redact(str(out))[:OUTPUT_LIMIT]
        pilot.last_command = cmd
        pilot._save_last()
        # Yeni bir senaryo gunu uretildiyse kartlar otomatik o gune gecer;
        # diger komutlarda kullanicinin sectigi gun korunur.
        secili = None if cmd in ('sor', 'devam', 'olay') else payload.get('gun')
        return pilot.last_output, build_state(pilot, secili_gun=secili)


class Handler(BaseHTTPRequestHandler):
    server_version = 'People1000UI/0.1'

    def _send(self, status, body, content_type, extra=None):
        data = body.encode('utf-8') if isinstance(body, str) else body
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, status, obj, extra=None):
        self._send(status, json.dumps(_json_safe(obj), ensure_ascii=False),
                   'application/json; charset=utf-8', extra)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ('/', '/index.html'):
            return self._send(200, PAGE, 'text/html; charset=utf-8')
        if path == '/api/state':
            try:
                query = urlsplit(self.path).query
                gun = None
                for part in query.split('&'):
                    if part.startswith('gun='):
                        gun = part[4:]
                        break
                return self._json(200, {'ok': True, 'state': build_state(self.server.pilot, gun)})
            except Exception as exc:
                return self._json(500, {'ok': False, 'error': self.server.pilot.redact(str(exc))})
        if path == '/api/health':
            # Hafif baglanti nabzi: kilit beklemeden anlik gun sayisini dondurur.
            try:
                day = getattr(self.server.pilot, 'cached_day', 0)
                return self._json(200, {'ok': True, 'day': day,
                                        'kart': len(termux.ROLE_INFO),
                                        'server': self.server_version})
            except Exception as exc:
                return self._json(500, {'ok': False,
                                        'error': self.server.pilot.redact(str(exc))})
        if path == '/api/export':
            with self.server.pilot.lock:
                data = termux.report(self.server.pilot.sim)
            return self._json(200, data, {
                'Content-Disposition': 'attachment; filename="people1000-rapor.json"'})
        return self._send(404, 'Bulunamadi.', 'text/plain; charset=utf-8')

    def do_POST(self):
        if urlsplit(self.path).path != '/api/command':
            return self._send(404, 'Bulunamadi.', 'text/plain; charset=utf-8')
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return self._json(400, {'ok': False, 'error': 'Gecersiz uzunluk.'})
        if not 0 < length <= 65536:
            return self._json(413, {'ok': False, 'error': 'Istek cok buyuk.'})
        try:
            payload = json.loads(self.rfile.read(length).decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return self._json(400, {'ok': False, 'error': 'Gecersiz JSON.'})
        try:
            message, state = execute_command(self.server.pilot, payload)
            return self._json(200, {'ok': True, 'message': message, 'state': state})
        except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
            err_body = {
                'ok': False,
                'error': self.server.pilot.redact(str(exc)) or 'Komut basarisiz.',
            }
            if getattr(exc, 'kind', None):
                err_body['error_kind'] = exc.kind
            if getattr(exc, 'http_status', None) is not None:
                err_body['http_status'] = exc.http_status
            if getattr(exc, 'retry_after', None) is not None:
                err_body['retry_after'] = exc.retry_after
            try:
                err_body['state'] = build_state(self.server.pilot)
            except Exception:
                pass
            return self._json(400, err_body)

    def log_message(self, fmt, *args):
        pass  # anahtar/istek govdesi icerebilecek ham erisim gunlukleri yazilmaz


class WebServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def create_server(host, port, pilot):
    server = WebServer((host, port), Handler)
    server.pilot = pilot
    return server


def main():
    p = argparse.ArgumentParser(description='People1000 yerel web arayuzu (Termux)')
    p.add_argument('--state', type=Path, default=Path('runs/phone-pilot.json'))
    p.add_argument('--offline', action='store_true', help='API kullanma (ucretsiz deneme)')
    p.add_argument('--host', default='127.0.0.1', help='Dinlenecek adres (Termux: 127.0.0.1)')
    p.add_argument('--port', type=int, default=8501)
    p.add_argument('--new', action='store_true', help='Yeni deney; var kaydi ezmez')
    p.add_argument('--open', action='store_true', dest='open_browser',
                   help='Termux tarayicisini acmayi dene')
    args = p.parse_args()
    if args.new and args.state.exists():
        p.error('Dosya var. Yeni bir --state yolu sec; kayit ezilmedi.')
    if args.offline:
        advisor = ReferenceAdvisor()
    else:
        try:
            advisor = advisor_from_environment()
        except ValueError as exc:
            p.error(str(exc))
    sim = Simulation.load(args.state) if args.state.exists() else termux.create_pilot()
    if 'termux_pilot' not in sim.protocol:
        p.error('Bu kayit terminal pilotuna ait degil; farkli --state sec.')
    args.state.parent.mkdir(parents=True, exist_ok=True)
    sim.save(args.state)
    pilot = WebPilot(sim, advisor, args.state)
    server = create_server(args.host, args.port, pilot)
    url = f'http://{args.host}:{args.port}/'
    mode = 'CEVRIMDISI' if args.offline else 'CANLI API'
    print(f'People1000 web arayuzu: {url}  [{mode}]', flush=True)
    print('Anahtar yalnizca bu surecte; tarayiciya gonderilmez. Durdurmak icin CTRL+C.', flush=True)
    if args.open_browser:
        try:
            subprocess.run(['termux-open', url], timeout=5, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            print('termux-open bulunamadi; adresi tarayicida elle acin.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        pilot.save()
        print('Kaydedildi.', flush=True)


PAGE = r'''<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#060911">
<meta name="color-scheme" content="dark">
<title>People1000 — Anlatım Konsolu</title>
<style>
:root{--bg:#060911;--panel:rgba(17,25,43,.78);--panel2:rgba(12,19,34,.94);
--line:rgba(126,156,214,.16);--line2:rgba(126,156,214,.32);
--txt:#eaf1ff;--muted:#8b9cb9;--dim:#66768f;
--cyan:#5ee7f0;--blue:#7aa2ff;--violet:#b391ff;--gold:#ffce7a;
--green:#63e6a9;--red:#ff7d90;--radius:18px;--shadow:0 20px 55px rgba(0,0,0,.42)}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;min-height:100vh;color:var(--txt);font-size:15px;line-height:1.5;
font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
-webkit-font-smoothing:antialiased;-webkit-text-size-adjust:100%;
background:radial-gradient(1100px 620px at 12% -8%,rgba(93,124,255,.17),transparent 62%),
radial-gradient(900px 520px at 97% -4%,rgba(94,231,240,.10),transparent 58%),
radial-gradient(700px 500px at 50% 108%,rgba(179,145,255,.09),transparent 60%),var(--bg);
background-attachment:fixed}
body::before{content:"";position:fixed;inset:0;pointer-events:none;opacity:.4;z-index:0;
background-image:linear-gradient(rgba(126,156,214,.045) 1px,transparent 1px),
linear-gradient(90deg,rgba(126,156,214,.045) 1px,transparent 1px);background-size:46px 46px;
-webkit-mask-image:linear-gradient(to bottom,black,transparent 78%);
mask-image:linear-gradient(to bottom,black,transparent 78%)}
button,input,select,a.btn{font:inherit}
button{cursor:pointer;touch-action:manipulation}
button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{
outline:2px solid var(--cyan);outline-offset:2px}
.topbar{position:sticky;top:0;z-index:40;display:flex;align-items:center;gap:14px;
justify-content:space-between;padding:11px clamp(14px,3vw,32px);
background:rgba(6,9,17,.84);backdrop-filter:blur(20px);border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:11px;font-weight:800;letter-spacing:.15em;font-size:14px;white-space:nowrap}
.brand-mark{width:25px;height:25px;border-radius:9px;position:relative;flex:none;
background:conic-gradient(from 210deg,var(--cyan),var(--blue),var(--violet),var(--cyan));
box-shadow:0 0 24px rgba(94,231,240,.32)}
.brand-mark::after{content:"";position:absolute;inset:6px;border-radius:50%;background:#070c17}
.brand b{color:var(--cyan)}
.brand small{display:block;font-size:9px;letter-spacing:.19em;color:var(--dim);font-weight:700;margin-top:1px}
.badges{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.badge{font-size:11px;padding:6px 11px;border-radius:999px;background:rgba(23,33,55,.8);
border:1px solid var(--line);color:var(--muted);white-space:nowrap;font-weight:600;letter-spacing:.02em}
.badge.strong{color:var(--txt)}
.badge.live{color:var(--green);border-color:rgba(99,230,169,.34);background:rgba(99,230,169,.07)}
.badge.offline{color:var(--gold);border-color:rgba(255,206,122,.3);background:rgba(255,206,122,.07)}
.conn{font-size:10.5px;font-weight:800;letter-spacing:.08em;padding:6px 11px;border-radius:999px;
border:1px solid var(--line);white-space:nowrap}
.conn.ok{color:var(--green);border-color:rgba(99,230,169,.3);background:rgba(99,230,169,.06)}
.conn.off{color:var(--red);border-color:rgba(255,125,144,.35);background:rgba(255,125,144,.08)}
.icon{background:rgba(23,33,55,.8);border:1px solid var(--line);color:var(--txt);
width:36px;height:36px;border-radius:11px;font-size:17px;display:inline-flex;align-items:center;justify-content:center}
.icon:hover{border-color:var(--cyan);color:var(--cyan)}
main{position:relative;z-index:1;max-width:1220px;margin:0 auto;padding:22px clamp(14px,3vw,32px) 60px}
.section{margin-top:26px}
.section-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;
flex-wrap:wrap;margin-bottom:12px}
h2{font-size:13px;margin:0;letter-spacing:.13em;text-transform:uppercase;color:#dce7fb;font-weight:800}
h2::before{content:"";display:inline-block;width:6px;height:6px;border-radius:2px;
background:linear-gradient(135deg,var(--cyan),var(--violet));margin-right:9px;vertical-align:2px}
.muted{color:var(--muted);font-size:11.5px}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(138px,1fr));gap:10px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:12px 13px;
backdrop-filter:blur(12px);transition:border-color .2s,transform .2s}
.stat:hover{border-color:var(--line2);transform:translateY(-2px)}
.stat .k{font-size:9.5px;color:var(--dim);text-transform:uppercase;letter-spacing:.11em;font-weight:800}
.stat .v{font-size:17px;font-weight:750;margin-top:5px;word-break:break-word;
font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.link-banner{display:flex;align-items:center;gap:14px;margin-top:12px;padding:13px 16px;
border-radius:14px;border:1px solid var(--line);background:var(--panel);backdrop-filter:blur(12px)}
.link-banner.tam{border-color:rgba(99,230,169,.34);background:linear-gradient(90deg,rgba(99,230,169,.09),rgba(17,25,43,.7))}
.link-banner.eski{border-color:rgba(255,206,122,.38);background:linear-gradient(90deg,rgba(255,206,122,.09),rgba(17,25,43,.7))}
.link-banner.kismi{border-color:rgba(179,145,255,.36);background:linear-gradient(90deg,rgba(179,145,255,.09),rgba(17,25,43,.7))}
.lb-icon{width:32px;height:32px;flex:none;border-radius:10px;display:grid;place-items:center;
font-weight:900;background:rgba(126,156,214,.12);border:1px solid var(--line)}
.link-banner.tam .lb-icon{color:var(--green);background:rgba(99,230,169,.12)}
.link-banner.eski .lb-icon{color:var(--gold);background:rgba(255,206,122,.12)}
.link-banner.kismi .lb-icon{color:var(--violet);background:rgba(179,145,255,.12)}
.lb-text{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}
.lb-text strong{font-size:13px;letter-spacing:.01em}
.lb-text span{font-size:11.5px;color:var(--muted)}
.lb-count{font-size:20px;font-weight:800;font-variant-numeric:tabular-nums;letter-spacing:-.02em;white-space:nowrap}
.rail{position:relative;display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;
padding:18px 12px 12px;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
backdrop-filter:blur(12px);overflow:hidden}
.rail::before{content:"";position:absolute;left:9%;right:9%;top:34px;height:2px;border-radius:2px;
background:linear-gradient(90deg,rgba(94,231,240,.1),rgba(122,162,255,.55),rgba(94,231,240,.1))}
.rail-node{position:relative;z-index:1;display:flex;flex-direction:column;align-items:center;gap:7px;
background:none;border:0;padding:0;color:var(--muted);min-width:0}
.rail-node:hover .rail-name{color:var(--txt)}
.rail-dot{width:15px;height:15px;border-radius:50%;border:2px solid var(--line2);
background:#0b1120;box-shadow:0 0 0 5px #0d1526;transition:.2s}
.rail-node.tam .rail-dot{background:var(--green);border-color:var(--green);box-shadow:0 0 0 5px #0d1526,0 0 16px rgba(99,230,169,.55)}
.rail-node.eski .rail-dot{background:var(--gold);border-color:var(--gold);box-shadow:0 0 0 5px #0d1526,0 0 16px rgba(255,206,122,.45)}
.rail-node.ortak .rail-dot{background:var(--violet);border-color:var(--violet);box-shadow:0 0 0 5px #0d1526,0 0 16px rgba(179,145,255,.4)}
.rail-name{font-size:11px;font-weight:700;text-align:center;line-height:1.25;
overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%;transition:color .2s}
.rail-day{font-size:9.5px;color:var(--dim);font-variant-numeric:tabular-nums}
.rail-help{margin:9px 2px 0}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;vertical-align:1px;margin:0 3px}
.dot.ok{background:var(--green)}.dot.warn{background:var(--gold)}.dot.mid{background:var(--violet)}.dot.off{background:#3d4b63}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(325px,1fr));gap:14px}
.card{position:relative;background:linear-gradient(165deg,rgba(25,36,59,.93),rgba(12,19,33,.96));
border:1px solid var(--line);border-radius:var(--radius);padding:16px;display:flex;flex-direction:column;
gap:11px;box-shadow:var(--shadow);overflow:hidden;transition:border-color .25s,transform .25s,box-shadow .25s}
.card::before{content:"";position:absolute;top:0;left:14px;right:14px;height:1px;
background:linear-gradient(90deg,transparent,rgba(94,231,240,.5),transparent)}
.card:hover{border-color:var(--line2);transform:translateY(-3px)}
.card.flash{animation:flash 1.15s ease}
@keyframes flash{0%,100%{box-shadow:var(--shadow)}35%{box-shadow:0 0 0 2px var(--cyan),0 20px 60px rgba(94,231,240,.25)}}
.card.empty{opacity:.9}
.card-head{display:flex;align-items:flex-start;gap:10px}
.num{display:inline-grid;place-items:center;width:29px;height:29px;flex:none;border-radius:10px;
background:linear-gradient(140deg,rgba(94,231,240,.18),rgba(122,162,255,.12));
border:1px solid rgba(94,231,240,.22);color:var(--cyan);font-weight:800;font-size:12px}
.card h3{margin:0;font-size:14.5px;line-height:1.3;font-weight:750;flex:1;min-width:0}
.pill{font-size:8.5px;font-weight:800;letter-spacing:.06em;padding:5px 8px;border-radius:999px;
white-space:nowrap;border:1px solid var(--line2);color:var(--muted);flex:none}
.pill.tam{color:var(--green);border-color:rgba(99,230,169,.4);background:rgba(99,230,169,.08)}
.pill.eski{color:var(--gold);border-color:rgba(255,206,122,.4);background:rgba(255,206,122,.08)}
.pill.ortak{color:var(--violet);border-color:rgba(179,145,255,.4);background:rgba(179,145,255,.08)}
.pill.yok{border-style:dashed}
.role-short{font-size:11px;color:var(--dim);margin:-4px 0 0;line-height:1.4;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.action{font-weight:750;font-size:13.5px;color:#dfeaff}
.expr{font-size:11px;color:var(--muted);margin-top:-7px}
.metrics{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:2px 0}
.metric-label{font-size:10px;color:var(--muted);margin-bottom:6px;display:flex;justify-content:space-between;gap:4px}
.metric-label b{color:var(--txt);font-variant-numeric:tabular-nums}
.bar{height:6px;border-radius:99px;background:rgba(4,8,16,.85);border:1px solid var(--line);overflow:hidden}
.fill{height:100%;border-radius:99px;background:linear-gradient(90deg,var(--blue),var(--cyan));transition:width .55s cubic-bezier(.2,.8,.2,1)}
.delta{font-size:10px;margin-top:5px;color:var(--dim)}
.delta.up{color:var(--green)}.delta.down{color:var(--red)}
.agenda-muted{font-size:10.5px;color:var(--dim);padding:6px 10px;border-radius:9px;
background:rgba(10,16,28,.55);border:1px dashed var(--line)}
.psych-panel{background:rgba(10,17,31,.78);border:1px solid rgba(126,156,214,.18);
border-radius:12px;padding:10px 11px;display:flex;flex-direction:column;gap:8px}
.psych-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}
.psych-mode{font-size:10.5px;font-weight:750;color:var(--cyan);letter-spacing:.02em}
.psych-expr{font-size:9.5px;color:var(--muted);padding:3px 7px;border-radius:999px;
border:1px solid var(--line);background:rgba(17,26,44,.75)}
.psych-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px 10px}
.pitem-label{font-size:9.5px;color:var(--muted);display:flex;justify-content:space-between;gap:4px;margin-bottom:3px}
.pitem-label b{color:var(--txt);font-variant-numeric:tabular-nums}
.pbar{height:5px;border-radius:99px;background:rgba(4,8,16,.85);border:1px solid var(--line);overflow:hidden}
.pfill{height:100%;border-radius:99px;transition:width .45s ease}
.pfill.comfort{background:linear-gradient(90deg,#3da88e,var(--green))}
.pfill.fear{background:linear-gradient(90deg,#d99a4e,var(--gold))}
.pfill.anger{background:linear-gradient(90deg,#d95c68,var(--red))}
.pfill.defense{background:linear-gradient(90deg,var(--blue),var(--violet))}
.psych-note{font-size:10.5px;color:#b8c7df;line-height:1.42}
.subwings{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;padding-top:4px;
border-top:1px solid rgba(126,156,214,.12)}
.sw-chip{background:rgba(15,24,42,.85);border:1px solid var(--line);border-radius:8px;padding:5px 7px;
font-size:9.5px;line-height:1.35;color:var(--muted)}
.sw-chip strong{display:block;color:var(--txt);font-size:9.5px;margin-bottom:1px}
.deep-tags{display:flex;flex-wrap:wrap;gap:5px;padding-top:4px;border-top:1px dashed rgba(126,156,214,.14)}
.dtag{font-size:9.5px;padding:3px 7px;border-radius:999px;background:rgba(16,25,44,.9);
border:1px solid var(--line);color:#b9c9e4;font-variant-numeric:tabular-nums}
.dtag.alert{color:var(--red);border-color:rgba(255,125,144,.38);background:rgba(255,125,144,.09)}
.dtag.warn{color:var(--gold);border-color:rgba(255,206,122,.36);background:rgba(255,206,122,.08)}
.dtag.ok{color:var(--green);border-color:rgba(99,230,169,.34);background:rgba(99,230,169,.07)}
.radar-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:10px}
.rcard{background:linear-gradient(155deg,rgba(20,31,52,.88),rgba(11,17,30,.95));
border:1px solid var(--line);border-radius:14px;padding:11px 12px;display:flex;flex-direction:column;gap:6px}
.rcard .rk{font-size:9.5px;color:var(--dim);text-transform:uppercase;letter-spacing:.09em;font-weight:800}
.rcard .rv{font-size:16px;font-weight:800;font-variant-numeric:tabular-nums;display:flex;align-items:baseline;justify-content:space-between;gap:6px}
.rcard .rs{font-size:10px;color:var(--muted);line-height:1.35}
.mem-strip{margin-top:10px;padding:11px 14px;border-radius:13px;border:1px solid var(--line);
background:rgba(13,20,36,.82);display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px}
.mem-strip .mtxt{font-size:11.5px;color:#c9d7ef;flex:1 1 280px}
.mem-pills{display:flex;flex-wrap:wrap;gap:6px}
.presets{display:flex;flex-wrap:wrap;gap:6px;margin:-3px 0 10px}
.preset{background:rgba(18,28,48,.78);border:1px dashed var(--line2);color:var(--muted);
border-radius:999px;padding:4px 10px;font-size:10.5px;transition:.16s}
.preset:hover{color:var(--cyan);border-color:var(--cyan);border-style:solid}
.ai-box{border:1px solid rgba(122,162,255,.26);border-radius:13px;overflow:hidden;
background:linear-gradient(150deg,rgba(20,34,60,.9),rgba(10,17,31,.9))}
.ai-box.eski{border-color:rgba(255,206,122,.4);background:linear-gradient(150deg,rgba(52,40,22,.75),rgba(15,18,26,.9))}
.ai-box.ortak{border-color:rgba(179,145,255,.36);background:linear-gradient(150deg,rgba(36,27,59,.8),rgba(12,17,29,.9))}
.ai-box.yok{border:1px dashed var(--line2);background:rgba(10,16,28,.6)}
.ai-head{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:9px 11px;
border-bottom:1px solid rgba(126,156,214,.14);font-size:9px;letter-spacing:.09em;font-weight:800;
color:var(--cyan);text-transform:uppercase}
.ai-box.eski .ai-head{color:var(--gold)}.ai-box.ortak .ai-head{color:var(--violet)}
.ai-tools{display:flex;align-items:center;gap:7px}
.ai-tag{font-size:8.5px;color:var(--muted);letter-spacing:.06em;border:1px solid var(--line);
padding:3px 6px;border-radius:6px;white-space:nowrap}
.mini{background:rgba(126,156,214,.09);border:1px solid var(--line);color:var(--muted);
border-radius:7px;padding:3px 7px;font-size:9.5px;font-weight:700;letter-spacing:.02em}
.mini:hover{color:var(--cyan);border-color:var(--cyan)}
.ai-body{padding:11px 12px;font-size:12.5px;line-height:1.65;white-space:pre-wrap;
word-break:break-word;color:#dce7fb;max-height:none}
.ai-body.clamped{max-height:230px;overflow:hidden;
-webkit-mask-image:linear-gradient(to bottom,black 72%,transparent);
mask-image:linear-gradient(to bottom,black 72%,transparent)}
.ai-foot{display:flex;align-items:center;justify-content:space-between;gap:8px;
padding:7px 11px;border-top:1px solid rgba(126,156,214,.14);flex-wrap:wrap}
.ai-foot .note{font-size:10px;color:var(--muted)}
.ai-yok{padding:13px;font-size:11.5px;color:var(--muted);line-height:1.5}
.ai-yok b{color:#c9d7ef;display:block;margin-bottom:3px;font-size:11.5px}
.motor{font-size:11.5px;color:var(--muted);border-top:1px dashed var(--line);padding-top:9px;line-height:1.5}
.motor b{color:#cdd9ee}
.detail{border-top:1px solid var(--line);padding-top:9px;font-size:11.5px;color:var(--muted)}
.detail summary{cursor:pointer;color:var(--cyan);font-weight:700;padding:2px 0;font-size:11.5px}
.detail p{margin:8px 0;line-height:1.55}
.note{background:rgba(8,12,20,.7);border-left:3px solid var(--gold);padding:8px 10px;
border-radius:7px;white-space:pre-wrap;word-break:break-word;color:#d8c9a8}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
padding:15px;backdrop-filter:blur(12px)}
.row{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin-bottom:10px}
.row:last-child{margin-bottom:0}
.btn{background:rgba(31,44,71,.75);color:var(--txt);border:1px solid var(--line2);border-radius:11px;
padding:10px 15px;min-height:42px;font-weight:650;font-size:13px;text-decoration:none;
display:inline-flex;align-items:center;justify-content:center;gap:7px;transition:.18s}
.btn:hover{border-color:var(--cyan);background:rgba(39,58,91,.85);transform:translateY(-1px)}
.btn:disabled{opacity:.4;cursor:wait;transform:none}
.btn.primary{background:linear-gradient(120deg,#2f6fe0,#4f8bff);border-color:#5b94ff;color:#fff;
box-shadow:0 8px 24px rgba(58,120,240,.28)}
.btn.accent{background:linear-gradient(120deg,rgba(94,231,240,.16),rgba(122,162,255,.16));border-color:rgba(94,231,240,.4);color:#dffaff}
.btn.warn{border-color:rgba(255,206,122,.4);color:var(--gold)}
input,select{background:rgba(6,10,19,.82);color:var(--txt);border:1px solid var(--line2);
border-radius:11px;min-height:42px;padding:9px 12px;min-width:0}
input{flex:1 1 220px}
input::placeholder{color:var(--dim)}
input[type=number]{flex:0 0 96px;min-width:84px}
.day-pick{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.day-pick label{font-size:11px;color:var(--muted);font-weight:700;letter-spacing:.04em}
.day-pick select{min-height:36px;padding:6px 10px;font-size:12px;border-radius:9px}
.advanced summary{cursor:pointer;color:var(--muted);font-size:12px;padding:8px 0;font-weight:650}
.timeline{position:relative;display:flex;flex-direction:column;gap:11px;padding-left:20px}
.timeline::before{content:"";position:absolute;left:5px;top:8px;bottom:8px;width:1px;
background:linear-gradient(to bottom,var(--cyan),rgba(122,162,255,.25),transparent)}
.day{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:13px 15px;
backdrop-filter:blur(10px)}
.day::before{content:"";position:absolute;left:-19px;top:19px;width:9px;height:9px;border-radius:50%;
background:var(--blue);border:2px solid #0a1120;box-shadow:0 0 12px rgba(122,162,255,.6)}
.day-no{font-size:9.5px;color:var(--cyan);font-weight:800;letter-spacing:.13em;text-transform:uppercase}
.day-event{font-weight:650;margin:5px 0 8px;font-size:13px;line-height:1.5}
.day-genel{font-size:12px;color:#cddbf2;background:rgba(94,231,240,.055);
border-left:2px solid rgba(94,231,240,.5);padding:9px 11px;border-radius:8px;
white-space:pre-wrap;word-break:break-word;margin:8px 0}
.day-sum{font-size:12px;color:#cdd7e3;white-space:pre-wrap;word-break:break-word;
max-height:420px;overflow:auto;padding:10px;background:rgba(5,9,17,.7);border-radius:8px}
.day-limit{font-size:10.5px;color:var(--gold);margin-top:8px;line-height:1.5}
.day-meta{display:flex;gap:7px;flex-wrap:wrap;margin-top:8px}
.day-meta .badge{font-size:9.5px;padding:4px 8px}
.output-wrap{background:rgba(6,10,18,.85);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.output-head{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:9px 13px;
border-bottom:1px solid var(--line);font-size:10.5px;color:var(--muted)}
.output{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;padding:14px;
font-size:11.5px;line-height:1.6;white-space:pre-wrap;word-break:break-word;
overflow:auto;max-height:460px;margin:0;color:#cbd8ee}
.events{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.chip{font-size:10px;background:rgba(17,26,44,.9);border:1px solid var(--line);border-radius:999px;
padding:4px 9px;color:var(--muted)}
footer{margin-top:34px;padding:16px 2px;color:var(--dim);font-size:11px;
border-top:1px solid var(--line);line-height:1.7}
#status{font-size:11.5px;color:var(--gold);min-height:18px;margin-top:11px}
.toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%) translateY(18px);
background:rgba(25,37,61,.97);border:1px solid var(--line2);color:var(--txt);padding:11px 18px;
border-radius:12px;font-size:12.5px;opacity:0;pointer-events:none;transition:.22s;z-index:60;
max-width:90vw;text-align:center;box-shadow:var(--shadow)}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.toast.err{border-color:var(--red)}
@media(max-width:880px){.rail{grid-template-columns:repeat(3,minmax(0,1fr));row-gap:16px}
.rail::before{display:none}}
@media(max-width:620px){main{padding:18px 13px 46px}.cards{grid-template-columns:1fr}
.rail{grid-template-columns:repeat(2,minmax(0,1fr))}.summary{grid-template-columns:repeat(2,minmax(0,1fr))}
.btn{flex:1 1 auto}.topbar{padding:10px 13px}.brand small{display:none}
.badge.hide-sm{display:none}.link-banner{padding:11px 12px;gap:10px}.lb-count{font-size:16px}}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}html{scroll-behavior:auto}}
</style>
</head>
<body>
<header class="topbar">
  <div class="brand"><span class="brand-mark"></span><span>PEOPLE<b>1000</b><small>ANLATIM KONSOLU</small></span></div>
  <div class="badges">
    <span id="conn" class="conn off">○ BAĞLANIYOR</span>
    <span id="modeBadge" class="badge">—</span>
    <span id="dayBadge" class="badge strong">Gün —</span>
    <button id="refreshBtn" class="icon" title="Durumu yenile" aria-label="Durumu yenile">↻</button>
  </div>
</header>
<main>
  <section class="summary" id="summary"></section>
  <div id="linkBanner" class="link-banner"></div>

  <section class="section">
    <div class="section-head">
      <h2>Toplumsal zihin ve kırılganlık radarı</h2>
      <span class="muted">v3.5 derin sosyal psikoloji göstergeleri (0 ek API isteği)</span>
    </div>
    <div id="mindRadar" class="radar-grid"></div>
    <div id="memoryStrip" class="mem-strip"></div>
  </section>

  <section class="section">
    <div class="section-head"><h2>Anlatım → kitle bağlantıları</h2><span id="railInfo" class="muted"></span></div>
    <div id="rail" class="rail"></div>
    <p class="rail-help muted">Düğüme dokun = ilgili karta git.
      <span class="dot ok"></span>kendi tam metni <span class="dot warn"></span>eski özet
      <span class="dot mid"></span>ortak metin <span class="dot off"></span>bekliyor</p>
  </section>

  <section class="section">
    <div class="section-head">
      <h2>6 Kitle</h2>
      <div class="day-pick">
        <label for="aiGun">Anlatım günü</label>
        <select id="aiGun"></select>
        <span id="aiKaynak" class="muted"></span>
      </div>
    </div>
    <div class="cards" id="cards"></div>
  </section>

  <section class="section">
    <div class="section-head"><h2>Komutlar</h2><span class="muted hide-sm">1 Başlat/Devam = 1 API isteği · Motor hesabı = 0 ek API isteği</span></div>
    <div class="panel">
      <div class="row">
        <button data-cmd="gun" class="btn primary">▸ Gün ilerlet</button>
        <button data-cmd="ilerle" data-count="3" class="btn">İlerle 3</button>
        <button data-cmd="ozet" class="btn">Özet</button>
        <button data-cmd="rapor" class="btn">Rapor</button>
        <button data-cmd="ayar" class="btn">Ayar</button>
        <button data-cmd="kaydet" class="btn">Kaydet</button>
      </div>
      <div class="row">
        <input id="sorText" maxlength="2000" placeholder="Yeni olay / senaryo (Gün 1)">
        <button data-cmd="sor" class="btn accent">✦ Başlat</button>
      </div>
      <div class="presets">
        <button type="button" class="preset" data-fill="sorText" data-val="Büyük maden faciası yaşandı, denetim ihmali iddiası var">⚡ Maden faciası &amp; ihmal</button>
        <button type="button" class="preset" data-fill="sorText" data-val="Büyük ihale yolsuzluğu ortaya çıktı ve sert fiyat artışı başladı">⚡ İhale yolsuzluğu &amp; fiyat şoku</button>
        <button type="button" class="preset" data-fill="sorText" data-val="Organize sanayi fabrikasında büyük yangın çıktı, güvenlik açığı tartışılıyor">⚡ Fabrika yangını</button>
      </div>
      <div class="row">
        <button data-cmd="devam" data-count="1" class="btn">Devam 1</button>
        <button data-cmd="devam" data-count="3" class="btn">Devam 3</button>
        <input id="devamCount" type="number" min="1" max="30" value="10" aria-label="Çoklu devam gün sayısı" style="max-width:78px">
        <button data-cmd="devam" data-custom-count="1" class="btn accent">Devam (Gün)</button>
        <button id="stopBtn" type="button" class="btn warn" hidden>■ Durdur</button>
      </div>
      <div class="row">
        <input id="olayText" maxlength="2000" placeholder="Zincire yeni gelişme ekle (ör. içeriden belge sızdı / sıkı önlem alındı)">
        <button data-cmd="olay" class="btn">Olay ekle</button>
      </div>
      <div class="presets">
        <button type="button" class="preset" data-fill="olayText" data-val="Bağımsız denetim başlatıldı, sorumlu üst yönetici istifa etti ve güvenlik önlem alındı">✓ Şeffaf denetim &amp; istifa</button>
        <button type="button" class="preset" data-fill="olayText" data-val="İçeriden daha önce sümenaltı edilmiş resmi denetim uyarısı belgesi sızdı">📄 İçeriden belge sızdı</button>
        <button type="button" class="preset" data-fill="olayText" data-val="Bağımsız gözlemci ve uzmanlar kanıta dayalı teknik uyarı raporu yayınladı">🔬 Gözlemci teknik uyarısı</button>
        <button type="button" class="preset" data-fill="olayText" data-val="Yayın yasağı getirildi ve sert eleştiri yapan yorumculara gözaltı işlemi yapıldı">⚠ Yayın yasağı &amp; gözaltı</button>
        <button type="button" class="preset" data-fill="olayText" data-val="Halk güvenlik ve geçim tepkisiyle günlük hayat boykotu başlattı">✊ Toplumsal boykot</button>
      </div>
      <details class="advanced">
        <summary>Tanılama ve sınırlar — aç</summary>
        <div class="row">
          <button data-cmd="baglanti" data-confirm="1" class="btn warn">Bağlantı</button>
          <button data-cmd="modeller" data-confirm="1" class="btn warn">Modeller</button>
          <button data-cmd="uretim-test" data-confirm="1" class="btn warn">Üretim testi</button>
        </div>
        <div class="row">
          <input id="beklemeVal" type="number" min="0" max="60" step="1" value="6" aria-label="Bekleme saniyesi">
          <button data-cmd="bekleme" class="btn">Bekleme (sn)</button>
          <input id="limitTotal" type="number" min="1" max="200" value="30" aria-label="Toplam limit">
          <input id="limitDaily" type="number" min="1" max="200" value="10" aria-label="Günlük limit">
          <button data-cmd="limit" class="btn">Limit</button>
        </div>
        <div class="row">
          <input id="sorLimitVal" type="number" min="1" max="200" value="20" aria-label="Soru limiti">
          <button data-cmd="sor-limit" class="btn">Soru limiti</button>
          <input id="tokenLimitVal" type="number" min="256" max="8192" step="128" value="2048" aria-label="Çıktı token sınırı">
          <input id="timeoutVal" type="number" min="5" max="120" step="5" value="20" aria-label="Zaman aşımı saniyesi">
          <button data-cmd="token-limit" class="btn">Token / Süre</button>
        </div>
        <div class="row">
          <a class="btn" href="/api/export" download>Raporu indir (JSON)</a>
          <button data-cmd="yardim" class="btn">Yardım</button>
        </div>
      </details>
      <div id="status"></div>
    </div>
  </section>

  <section class="section" id="scenarioSection">
    <div class="section-head"><h2>Senaryo zinciri</h2><span id="scenarioBadge" class="muted"></span></div>
    <div class="timeline" id="timeline"></div>
  </section>

  <section class="section">
    <div class="section-head"><h2>Son çıktı</h2><span id="lastCmd" class="muted"></span></div>
    <div class="output-wrap">
      <div class="output-head"><span>Sunucunun döndürdüğü ham çıktı</span>
        <button type="button" class="mini" data-copy="output">Kopyala</button></div>
      <pre id="output" class="output">Henüz komut çalıştırılmadı.</pre>
    </div>
    <div class="events" id="events"></div>
  </section>

  <footer>
    Bu arayüz yalnızca bu sunucuya bağlanır. API anahtarı sayfaya gelmez; tüm istekler
    sunucudan sağlayıcıya gider. AI anlatımı motorun gerçekleşmiş sonucu değildir;
    "Motor özeti" satırı simülasyonun sayısal durumudur. Kitle karakterleri ve
    davranış kuralları bu arayüzde değiştirilmez.
  </footer>
</main>
<div id="toast" class="toast"></div>
<script>
"use strict";
const $=s=>document.querySelector(s);
let state=null,busy=false,firstLoad=true,stopRequested=false;
const DURUM={tam:"AI BAĞLI",eski:"ESKİ KAYIT",ortak:"ORTAK METİN",yok:"BEKLİYOR"};
function node(tag,cls,text){const e=document.createElement(tag);
  if(cls)e.className=cls;if(text!==undefined&&text!==null)e.textContent=String(text);return e;}
function toast(msg,err){const t=$("#toast");t.textContent=msg;
  t.className="toast show"+(err?" err":"");setTimeout(()=>{t.className="toast";},2900);}
function setConn(ok){const e=$("#conn");e.className="conn "+(ok?"ok":"off");
  e.textContent=ok?"● SUNUCU BAĞLI":"○ BAĞLANTI YOK";}
function showOutput(t){$("#output").textContent=t||"(çıktı yok)";}
function setBusy(v,msg,cancellable){busy=v;document.querySelectorAll("[data-cmd]").forEach(b=>b.disabled=v);
  const sb=$("#stopBtn");if(sb)sb.hidden=!(v&&cancellable);
  $("#status").textContent=v?(msg||"Çalışıyor…"):"";}
function stat(k,v){const d=node("div","stat");
  d.append(node("div","k",k),node("div","v",v));return d;}
function pbar(label,val,tone,extraText){
  const w=node("div","pitem"),lab=node("div","pitem-label");
  lab.append(node("span","",label),node("b","",extraText||(val===null||val===undefined?"—":"%"+val)));
  const bar=node("div","pbar"),fill=node("div","pfill "+(tone||"comfort"));
  fill.style.width=(val===null||val===undefined?0:Math.max(0,Math.min(100,val)))+"%";
  bar.append(fill);w.append(lab,bar);return w;}
function dtag(text,tone){return node("span","dtag"+(tone?" "+tone:""),text);}
function psychBox(c){
  const ps=c.psikoloji;
  if(!ps||!ps.baskin_etiket)return null;
  const p=node("div","psych-panel");
  const head=node("div","psych-head");
  head.append(node("span","psych-mode","Psikoloji · "+ps.baskin_etiket),
    node("span","psych-expr",ps.ifade_etiketi||"Açık ifade"));
  p.append(head);
  const g=node("div","psych-grid");
  g.append(
    pbar("Konfor / Huzur",ps.konfor,"comfort"),
    pbar("Korku / Otosansür",ps.korku,"fear"),
    pbar("Öfke / Bastırılmış",ps.ofke,"anger","%"+(ps.ofke||0)+" (İç: %"+(ps.bastirilmis_ofke||0)+")"),
    pbar("Savunma / Eşik",ps.savunma,"defense","Sav %"+(ps.savunma||0)+" · Aşan %"+(ps.esik_asan_oran||0))
  );
  if((ps.tukenmislik||0)>=8){
    g.append(pbar("Tükenmişlik",ps.tukenmislik,"fear"),
             pbar("Tahammül Eşiği",ps.tahammul_esigi,"defense"));
  }
  p.append(g);
  const tags=node("div","deep-tags");
  if(c.id==="power_aligned"){
    tags.append(dtag("Aracı Güveni %"+(ps.araci_guveni??75),(ps.araci_guveni??75)<45?"warn":""));
    if((ps.suc_kaydirma_oran||0)>0)tags.append(dtag("Suç Kaydırma %"+ps.suc_kaydirma_oran,"warn"));
    if((ps.kuskun_oran||0)>0)tags.append(dtag("Küskün / Sessiz Kopuş %"+ps.kuskun_oran,"alert"));
  }else if(c.id==="opposition"){
    if((ps.cogulcu_cehalet||0)>=10)tags.append(dtag("Çoğulcu Cehalet %"+ps.cogulcu_cehalet,"warn"));
    if((ps.kuskun_oran||0)>0)tags.append(dtag("Küskün Kopuş %"+ps.kuskun_oran,"alert"));
    tags.append(dtag("Eylem İtkisi %"+(ps.eylem_itkisi||0)));
  }else if(c.id==="authority"){
    tags.append(dtag("İç Çatlak: "+(ps.ic_catlak_sayisi||0)+" yönetici"));
    tags.append(dtag("Sızıntı Eğilimi %"+(ps.ic_sizinti_egilimi||0),(ps.ic_sizinti_egilimi||0)>=45?"alert":""));
  }else if(c.id==="discontented"){
    if((ps.goreli_yoksunluk||0)>=8)tags.append(dtag("Göreli Yoksunluk %"+ps.goreli_yoksunluk,"alert"));
    tags.append(dtag("Dayanışma Gücü %"+(ps.dayanisma_kapasitesi??100),(ps.dayanisma_kapasitesi??100)<55?"warn":"ok"));
  }else if(c.id==="observer"){
    tags.append(dtag("Epistemik Alarm %"+(ps.epistemik_alarm||0),(ps.epistemik_alarm||0)>=60?"alert":""));
    if((ps.uyari_hazir_oran||0)>0)tags.append(dtag("TEKNİK UYARI EŞİĞİ AŞILDI","alert"));
  }
  if(tags.childNodes.length)p.append(tags);
  if(ps.alt_kanatlar){
    const sw=node("div","subwings");
    const names={pro_A:"A Yanlısı Medya",pro_B:"B Yanlısı Medya",neutral_commercial:"Tarafsız / Ticari"};
    ["pro_A","pro_B","neutral_commercial"].forEach(k=>{
      const x=ps.alt_kanatlar[k];if(!x)return;
      const chip=node("div","sw-chip");
      chip.append(node("strong","",names[k]||k),
        document.createTextNode((x.ifade_etiketi||x.baskin_etiket||"")+" · Korku %"+(x.korku||0)));
      sw.append(chip);
    });
    p.append(sw);
  }
  if(ps.yorum)p.append(node("div","psych-note",ps.yorum));
  return p;}
function renderMindRadar(s){
  const el=$("#mindRadar"),ms=$("#memoryStrip");
  if(!el||!ms)return;
  el.replaceChildren();ms.replaceChildren();
  const z=s.sosyal_zihin||{};
  const items=[
    {k:"Sahte Uyum Riski",v:z.sahte_uyum_riski??0,tone:"fear",sub:"Görünür uyum ile içsel tepki/otosansür makası"},
    {k:"Yay Boşalma Gerilimi",v:z.yay_bosalma_potansiyeli??0,tone:"anger",sub:"Bastırılmış öfke + adaletsizlik birikimi"},
    {k:"Küskün / Gri Seçmen",v:z.kuskun_secmen_orani??0,tone:"defense",sub:"Taraf değiştirmeden sessizce çekilen taban"},
    {k:"İktidar Aracı Güveni",v:z.iktidar_araci_guveni??75,tone:"comfort",sub:"Bürokrasiye suç kaydırma tamponu (düşerse duvar çatlar)"},
    {k:"Göreli Yoksunluk",v:z.goreli_yoksunluk??0,tone:"anger",sub:"İmtiyaz uçurumu · Dayanışma gücü %"+(z.dayanisma_kapasitesi??100)},
    {k:"Gözlemci Alarmı",v:z.gozlemci_epistemik_alarm??0,tone:"defense",sub:z.gozlemci_uyari_hazir?"Teknik uyarı eşiğinde (Cassandra)":"6 kanallı çapraz izleme"}
  ];
  items.forEach(it=>{
    const c=node("div","rcard"),bar=node("div","pbar"),fill=node("div","pfill "+it.tone);
    fill.style.width=Math.max(0,Math.min(100,it.v))+"%";bar.append(fill);
    c.append(node("div","rk",it.k),node("div","rv","%"+it.v),bar,node("div","rs",it.sub));
    el.append(c);
  });
  const h=s.hafiza||{};
  ms.append(node("div","mtxt","Toplumsal Hafıza: "+(h.yorum||"Henüz kapanmış geçmiş kriz yok.")));
  const pills=node("div","mem-pills");
  pills.append(
    dtag("Geçmiş Kriz: "+(h.gecmis_kriz_sayisi||0)),
    dtag("Örtbas İzi %"+(h.ortbas_izi||0),(h.ortbas_izi||0)>=20?"alert":""),
    dtag("Günah Keçisi İzi %"+(h.gunah_kecisi_izi||0),(h.gunah_kecisi_izi||0)>=20?"warn":""),
    dtag("Onarım Kredisi %"+(h.onarim_kredisi||0),(h.onarim_kredisi||0)>0?"ok":"")
  );
  ms.append(pills);}
function metric(label,val,delta){const w=node("div","metric");
  const lab=node("div","metric-label");lab.append(node("span","",label),
    node("b","",val===null||val===undefined?"—":val+"%"));w.append(lab);
  const bar=node("div","bar"),fill=node("div","fill");
  fill.style.width=(val===null||val===undefined?0:Math.max(0,Math.min(100,val)))+"%";
  bar.append(fill);w.append(bar);
  w.append(node("div","delta "+(delta>0?"up":delta<0?"down":""),
    delta===null||delta===undefined||delta===0?"Düne göre değişim yok":
    (delta>0?"▲ +":"▼ ")+delta+" puan (düne göre)"));
  return w;}
function copyText(text,label){
  if(!text){toast("Kopyalanacak metin yok",true);return;}
  const done=()=>toast((label||"Metin")+" kopyalandı");
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(done).catch(()=>legacyCopy(text,done));
  }else legacyCopy(text,done);}
function legacyCopy(text,done){const ta=document.createElement("textarea");
  ta.value=text;ta.style.position="fixed";ta.style.opacity="0";document.body.append(ta);
  ta.select();try{document.execCommand("copy");done();}catch(e){toast("Kopyalanamadı",true);}ta.remove();}
function aiBox(c){
  const box=node("div","ai-box "+c.ai_durum);
  if(c.ai_durum==="yok"){
    box.className="ai-box yok";
    const p=node("div","ai-yok");p.append(node("b","","AI anlatımı bekleniyor"),
      document.createTextNode("Bu kart, “Başlat”, “Devam” veya “Olay ekle” ile üretilen "+
        "o güne ait kitleye özel metne otomatik bağlanır."));
    box.append(p);return box;}
  const ortak=c.ai_durum==="ortak";
  const metin=ortak?c.ai_ortak:c.ai_metni;
  const head=node("div","ai-head");
  head.append(node("span","",ortak?"GÜNÜN ORTAK ANLATIMI":"KİTLEYE ÖZEL ANLATIM"));
  const tools=node("div","ai-tools");
  tools.append(node("span","ai-tag",c.ai_gun?"GÜN "+c.ai_gun:"—"));
  if(!ortak)tools.append(node("span","ai-tag",
    c.ai_kaynak==="eski-ozet"?"600 KR. ÖZET":"TAM METİN"));
  const cp=node("button","mini","Kopyala");cp.type="button";
  cp.addEventListener("click",()=>copyText(metin,"Anlatım"));
  tools.append(cp);head.append(tools);box.append(head);
  const body=node("div","ai-body",metin||"(boş)");
  let toggle=null;
  if((metin||"").length>620){body.classList.add("clamped");
    toggle=node("button","mini","Tamamını göster ↓");toggle.type="button";
    toggle.addEventListener("click",()=>{const cl=body.classList.toggle("clamped");
      toggle.textContent=cl?"Tamamını göster ↓":"Kısalt ↑";});}
  box.append(body);
  const foot=node("div","ai-foot");
  const note=node("span","note");
  if(c.ai_durum==="eski")note.textContent="Bu kayıtta tam metin yok; eski 600 karakterlik özet var. "+
    "Cümle burada yarım kalabilir — yeni bir Devam/Olay tam metin üretir.";
  else if(ortak)note.textContent="AI yanıtında bu kitleye özel başlık bulunamadı; "+
    "günün ortak metni gösteriliyor. Kitleye ait uydurma metin eklenmez.";
  else note.textContent=(metin||"").length+" karakter · metnin tamamı kartta, kısaltma yok.";
  foot.append(note);if(toggle)foot.append(toggle);box.append(foot);
  return box;}
function card(c){
  const d=node("article","card"+(c.var?"":" empty"));d.id="card-"+c.id;
  const head=node("div","card-head");
  head.append(node("span","num",c.sira),node("h3","",c.ad),
    node("span","pill "+c.ai_durum,DURUM[c.ai_durum]||"BEKLİYOR"));d.append(head);
  d.append(node("div","role-short",c.tanim));
  const pb=psychBox(c);if(pb)d.append(pb);
  if(c.var){
    d.append(node("div","action",c.eylem));
    if(c.ifade)d.append(node("div","expr",c.ifade));
    const m=node("div","metrics");
    m.append(metric("Yeterlilik",c.yeterlilik,c.fark_yeterlilik),
      metric("Usul",c.usul,c.fark_usul));d.append(m);
  }else{
    d.append(node("div","agenda-muted","Sıradan atama gündemi: henüz gün ilerletilmedi (“Gün ilerlet” ile çalışır)."));
  }
  d.append(aiBox(c));
  const motor=node("div","motor");motor.append(node("b","","Motor özeti · "),
    document.createTextNode(c.ozet));d.append(motor);
  const det=node("details","detail");
  det.append(node("summary","",c.model_notu?"Rol tanımı + model notu":"Rol tanımı"));
  det.append(node("p","",c.tanim));
  if(c.model_notu)det.append(node("p","note","Model notu: "+c.model_notu));
  d.append(det);return d;}
function renderBanner(s){
  const b=s.baglanti||{},el=$("#linkBanner");
  el.className="link-banner "+(b.durum||"yok");el.replaceChildren();
  el.append(node("div","lb-icon",b.durum==="tam"?"✓":b.durum==="eski"?"!":b.durum==="kismi"?"◐":"·"));
  const txt=node("div","lb-text");
  const title={tam:"Tüm kartlar bağlı",eski:"Eski kayıt — eksik metin",
    kismi:"Kısmi bağlantı",yok:"Anlatım bekleniyor"}[b.durum]||"Bağlantı durumu";
  txt.append(node("strong","",title),node("span","",b.aciklama||""));
  if(b.yarim)txt.append(node("span","","Uyarı: yanıt cümle ortasında bitmiş olabilir; kayıttaki metnin tamamı gösteriliyor."));
  el.append(txt,node("div","lb-count",(b.bagli||0)+" / "+(b.toplam||6)));}
function renderRail(s){
  const rail=$("#rail");rail.replaceChildren();
  s.kitleler.forEach(c=>{const b=node("button","rail-node "+c.ai_durum);
    b.type="button";b.title=c.ad+" — "+(DURUM[c.ai_durum]||"");
    b.append(node("span","rail-dot"),node("span","rail-name",c.ad),
      node("span","rail-day",c.ai_gun?"GÜN "+c.ai_gun:"—"));
    b.addEventListener("click",()=>{const el=$("#card-"+c.id);if(!el)return;
      el.scrollIntoView({behavior:"smooth",block:"center"});
      el.classList.remove("flash");void el.offsetWidth;el.classList.add("flash");
      setTimeout(()=>el.classList.remove("flash"),1250);});
    rail.append(b);});
  const b=s.baglanti||{};
  $("#railInfo").textContent=(b.bagli||0)+"/"+(b.toplam||6)+" kitle · "+
    (b.kaynak==="tam-metin"?"tam metin":b.kaynak==="eski-ozet"?"eski özet":"kayıt yok")+
    " · "+(b.karakter||0)+" karakter";}
function renderTimeline(s){
  const tl=$("#timeline");tl.replaceChildren();
  $("#scenarioBadge").textContent=s.senaryo.var?
    ("Gün "+s.senaryo.gun+" · "+s.senaryo.gecmis.length+" adım · "+
     s.senaryo.gecmis.length+" günün tam metni kayıtlı"):"Henüz zincir yok";
  if(!s.senaryo.var){
    tl.append(node("p","muted","Yukarıya bir olay yazıp “Başlat” de; sonra “Devam” ile zinciri ilerlet."));
    return;}
  const ilk=node("div","day");
  ilk.append(node("div","day-no","BAŞLANGIÇ"),node("div","day-event",s.senaryo.ilk_olay));
  if(s.hafiza&&s.hafiza.gecmis_kriz_sayisi>0){
    ilk.append(node("div","day-limit","Toplumsal hafıza: "+s.hafiza.yorum));
  }
  tl.append(ilk);
  s.senaryo.gecmis.forEach(h=>{
    const e=node("div","day");
    e.append(node("div","day-no","GÜN "+h.day+(h.dal?" · DAL: "+h.dal:"")),node("div","day-event",h.event||"(gelişme yok)"));
    if(h.genel)e.append(node("div","day-genel",h.genel));
    const det=node("details","detail");
    det.append(node("summary","","Günün tam metni"+
      (h.kaynak==="eski-ozet"?" (eski kayıt: 600 kr. özet)":" ("+(h.karakter||0)+" karakter)")));
    det.append(node("div","day-sum",h.metin||"(metin yok)"));
    e.append(det);
    if(h.sinir)e.append(node("div","day-limit","Nedensel sınır: "+h.sinir));
    const meta=node("div","day-meta");
    meta.append(node("span","badge","Kartlar: "+(h.bagli||0)+" / 6"),
      node("span","badge",h.kaynak==="eski-ozet"?"ESKİ ÖZET":"TAM METİN"));
    if(h.motor_etkisi&&h.motor_etkisi.sim_day){
      const me=h.motor_etkisi;
      meta.append(node("span","badge","Motor Gün "+me.sim_day+" · Güven %"+(me.mean_trust??"—")+" · Fiyat x"+(me.price??1)));
      if(me.employer_cut_workers>0)meta.append(node("span","badge","İşveren kesintisi: "+me.employer_cut_workers+" çalışan"));
      if(me.self_censored_blocks>0)meta.append(node("span","badge","Otosansür engeli: "+me.self_censored_blocks));
      if(me.disengaged_citizens>0)meta.append(node("span","badge","Küskün kopuş: "+me.disengaged_citizens+" kişi"));
      if(me.observer_warnings>0)meta.append(node("span","badge","Gözlemci teknik uyarısı: "+me.observer_warnings));
    }
    if(h.eksik&&h.eksik.length)meta.append(node("span","badge","Ayrı bölüm yok: "+h.eksik.length+" kitle"));
    if(h.kesik)meta.append(node("span","badge","KIRPILMIŞ"));
    e.append(meta);tl.append(e);});}
function render(s){
  state=s;
  $("#modeBadge").textContent=s.mode==="offline"?"ÇEVRİMDIŞI":"CANLI API";
  $("#modeBadge").className="badge "+(s.mode==="offline"?"offline":"live");
  $("#dayBadge").textContent="Gün "+s.day;
  const sum=$("#summary");sum.replaceChildren();
  sum.append(stat("Gün",s.day),stat("Taraf değişimi",s.dunya.taraf_degisimi),
    stat("İdeoloji değişimi",s.dunya.ideoloji_degisimi),
    stat("API değerlendirme",s.api.deneme+" / "+s.api.kabul+" kabul"),
    stat("Soru / sınır",s.api.soru+" / "+s.api.soru_limiti),
    stat("Model",s.settings.model||"çevrimdışı"),
    stat("Bekleme",(s.settings.min_interval_seconds||0)+" sn"));
  renderBanner(s);renderMindRadar(s);renderRail(s);
  const cards=$("#cards");cards.replaceChildren();
  s.kitleler.forEach(c=>cards.append(card(c)));
  const sel=$("#aiGun");sel.replaceChildren();
  const gunler=Object.keys(s.senaryo.gunler||{});
  gunler.forEach(g=>{const o=node("option","","Gün "+g);o.value=g;sel.append(o);});
  sel.disabled=!gunler.length;
  if(s.senaryo.secili_gun)sel.value=String(s.senaryo.secili_gun);
  const b=s.baglanti||{};
  $("#aiKaynak").textContent=(b.bagli||0)+"/"+(b.toplam||6)+" bağlı · "+
    (b.kaynak==="tam-metin"?"tam metin":b.kaynak==="eski-ozet"?"eski özet":"metin yok");
  renderTimeline(s);
  const ev=$("#events");ev.replaceChildren();
  (s.olaylar||[]).slice(-10).reverse().forEach(x=>ev.append(node("span","chip",x.kind)));
  if(Number(s.limitler.toplam))$("#limitTotal").value=s.limitler.toplam;
  if(Number(s.limitler.gunluk))$("#limitDaily").value=s.limitler.gunluk;
  if(s.settings.min_interval_seconds!==undefined&&s.settings.min_interval_seconds!==null)
    $("#beklemeVal").value=s.settings.min_interval_seconds;
  if(Number(s.settings.max_output_tokens))$("#tokenLimitVal").value=s.settings.max_output_tokens;
  if(Number(s.settings.timeout_seconds))$("#timeoutVal").value=s.settings.timeout_seconds;
  if(Number(s.api.soru_limiti))$("#sorLimitVal").value=s.api.soru_limiti;
  if(firstLoad){firstLoad=false;
    if(s.son_cikti)showOutput(s.son_cikti);
    if(s.son_komut)$("#lastCmd").textContent="Son komut: "+s.son_komut;}}
async function load(){
  const cur=$("#aiGun").value;
  try{const r=await fetch("/api/state"+(cur?"?gun="+encodeURIComponent(cur):""),
    {cache:"no-store"});const j=await r.json();
    if(j.ok){render(j.state);setConn(true);}else{toast(j.error||"Durum alınamadı",true);setConn(false);}
  }catch(e){setConn(false);toast("Sunucuya ulaşılamadı",true);}}
async function ping(){if(busy)return;
  try{const r=await fetch("/api/health?t="+Date.now(),{cache:"no-store"});
    const j=await r.json();setConn(!!j.ok);}catch(e){setConn(false);}}
function explainError(j){
  let msg=j.error||"Komut başarısız.";
  if(j.http_status===429){
    const wait=j.retry_after?(" (Önerilen bekleme: "+j.retry_after+" sn)"):"";
    msg+=" — İpucu: Bekleme süresini (sn) artırıp tekrar deneyin"+wait+".";
  }else if(/token sınırında kesildi|MAX_TOKENS/i.test(msg)){
    msg+=" — İpucu: 'Tanılama ve sınırlar' altından Çıktı Token sınırını artırabilirsiniz.";
  }
  return msg;}
async function run(cmd,opts){
  if(busy)return;
  const payload=Object.assign({cmd:cmd},opts||{});
  const cur=$("#aiGun").value;if(cur)payload.gun=cur;
  if(payload.confirm&&!window.confirm("Bu işlem 1 API isteği / kota kullanabilir. Devam?"))return;
  const totalSteps=((cmd==="devam"||cmd==="ilerle")&&Number(payload.count)>1)?Number(payload.count):1;
  stopRequested=false;
  setBusy(true,totalSteps>1?(cmd+" (1 / "+totalSteps+") çalışıyor…"):(cmd+" çalışıyor…"),totalSteps>1);
  try{
    if(totalSteps>1){
      const logs=[];let completed=0;
      for(let i=1;i<=totalSteps;i++){
        if(stopRequested){toast(completed+" gün tamamlandıktan sonra durduruldu",false);break;}
        setBusy(true,cmd+" ("+i+" / "+totalSteps+". gün) çalışıyor…",true);
        const stepPayload=Object.assign({},payload,{count:1});
        delete stepPayload.gun;
        const r=await fetch("/api/command",{method:"POST",
          headers:{"Content-Type":"application/json"},body:JSON.stringify(stepPayload)});
        const j=await r.json();setConn(true);
        if(!j.ok){
          if(j.state)render(j.state);
          const em=explainError(j);
          showOutput((logs.length?logs.join("\n\n")+"\n\n":"")+"HATA ("+i+". adım): "+em);
          toast(em,true);return;
        }
        completed=i;logs.push(j.message);render(j.state);showOutput(logs.join("\n\n"));
        $("#lastCmd").textContent="Son komut: "+cmd+" ("+completed+"/"+totalSteps+")";
      }
      if(!stopRequested)toast(completed+" gün tamamlandı",false);
      return;
    }
    const r=await fetch("/api/command",{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const j=await r.json();setConn(true);
    if(!j.ok){
      if(j.state)render(j.state);
      const em=explainError(j);
      showOutput("HATA: "+em);toast(em,true);return;
    }
    render(j.state);showOutput(j.message);$("#lastCmd").textContent="Son komut: "+cmd;
    toast("Tamam",false);
  }catch(e){setConn(false);showOutput("Bağlantı hatası: "+e);toast("Sunucuya ulaşılamadı",true);}
  finally{setBusy(false,"",false);}}
const stopBtnEl=$("#stopBtn");
if(stopBtnEl)stopBtnEl.addEventListener("click",()=>{stopRequested=true;stopBtnEl.disabled=true;
  $("#status").textContent="Mevcut gün bitince durdurulacak…";setTimeout(()=>{stopBtnEl.disabled=false;},600);});
document.querySelectorAll("[data-cmd]").forEach(b=>b.addEventListener("click",()=>{
  const cmd=b.dataset.cmd,o={};
  if(b.dataset.count)o.count=Number(b.dataset.count);
  if(b.dataset.customCount)o.count=Number($("#devamCount").value||10);
  if(b.dataset.confirm)o.confirm=true;
  if(cmd==="sor"||cmd==="olay"){
    const t=(cmd==="sor"?$("#sorText"):$("#olayText")).value.trim();
    if(!t){toast("Önce bir metin yaz",true);return;}o.text=t;}
  if(cmd==="bekleme")o.seconds=Number($("#beklemeVal").value);
  if(cmd==="limit"){o.total=Number($("#limitTotal").value);o.daily=Number($("#limitDaily").value);}
  if(cmd==="sor-limit")o.count=Number($("#sorLimitVal").value);
  if(cmd==="token-limit"){o.tokens=Number($("#tokenLimitVal").value);o.timeout=Number($("#timeoutVal").value);}
  run(cmd,o);}));
["sorText","olayText"].forEach(id=>$("#"+id).addEventListener("keydown",e=>{
  if(e.key==="Enter"){e.preventDefault();
    document.querySelector('[data-cmd="'+(id==="sorText"?"sor":"olay")+'"]').click();}}));
$("#aiGun").addEventListener("change",e=>{
  if(busy)return;const gun=e.target.value;
  setBusy(true,"Gün "+gun+" yükleniyor…");
  fetch("/api/state?gun="+encodeURIComponent(gun)+"&t="+Date.now(),{cache:"no-store"})
    .then(r=>r.json()).then(j=>{if(j.ok){render(j.state);toast("Gün "+gun+" gösteriliyor",false);setConn(true);}
      else toast(j.error||"Gün açılamadı",true);})
    .catch(()=>{setConn(false);toast("Sunucuya ulaşılamadı",true);})
    .finally(()=>setBusy(false));});
$("#refreshBtn").addEventListener("click",()=>{if(!busy)load();});
document.querySelectorAll("[data-fill]").forEach(b=>b.addEventListener("click",()=>{
  const inp=$("#"+b.dataset.fill);if(!inp)return;
  inp.value=b.dataset.val||"";inp.focus();
  toast("Şablon metin kutusuna yazıldı (istek göndermek için düğmeye basın)");}));
document.querySelectorAll("[data-copy]").forEach(b=>b.addEventListener("click",()=>{
  copyText($("#"+b.dataset.copy).textContent,"Çıktı");}));
setInterval(ping,20000);
load();
</script>
</body>
</html>
'''


if __name__ == '__main__':
    main()
