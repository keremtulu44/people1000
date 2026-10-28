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
<meta name="theme-color" content="#070b14">
<meta name="color-scheme" content="dark">
<title>People1000 — Anlatım Konsolu</title>
<style>
:root{
  --bg:#070b14;--panel:#101829;--panel2:#0b1220;--hero:#13203a;
  --line:rgba(138,168,224,.15);--line2:rgba(138,168,224,.30);
  --txt:#edf3ff;--sub:#b9c8e2;--muted:#8496b4;--dim:#5d6e8a;
  --cyan:#5ee7f0;--blue:#6d9bff;--violet:#b592ff;--gold:#ffce7a;
  --green:#5fe3a4;--red:#ff7d90;--radius:16px;--shadow:0 16px 42px rgba(0,0,0,.38)
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;min-height:100vh;color:var(--txt);font-size:15px;line-height:1.55;
  font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased;-webkit-text-size-adjust:100%;
  background:radial-gradient(960px 500px at 15% -6%,rgba(88,128,255,.15),transparent 62%),
             radial-gradient(800px 460px at 95% 0%,rgba(94,231,240,.09),transparent 58%),var(--bg);
}
button,input,select,a.btn{font:inherit}
button{cursor:pointer;touch-action:manipulation}
button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{
  outline:2px solid var(--cyan);outline-offset:2px
}

/* ÜST ÇUBUK */
.topbar{
  position:sticky;top:0;z-index:40;display:flex;align-items:center;justify-content:space-between;
  gap:10px;padding:10px clamp(12px,3vw,28px);
  background:rgba(7,11,20,.88);backdrop-filter:blur(16px);border-bottom:1px solid var(--line)
}
.brand{display:flex;align-items:center;gap:10px;font-weight:800;letter-spacing:.12em;font-size:13.5px;white-space:nowrap}
.brand-mark{width:22px;height:22px;border-radius:7px;flex:none;
  background:linear-gradient(135deg,var(--cyan),var(--blue),var(--violet))}
.brand b{color:var(--cyan)}
.badges{display:flex;align-items:center;gap:7px;flex-wrap:wrap;justify-content:flex-end}
.badge{font-size:11px;padding:5px 10px;border-radius:999px;background:rgba(20,30,50,.85);
  border:1px solid var(--line);color:var(--muted);white-space:nowrap;font-weight:650}
.badge.strong{color:var(--txt)}
.badge.live{color:var(--green);border-color:rgba(95,227,164,.35);background:rgba(95,227,164,.08)}
.badge.offline{color:var(--gold);border-color:rgba(255,206,122,.32);background:rgba(255,206,122,.08)}
.conn{font-size:10.5px;font-weight:800;padding:5px 10px;border-radius:999px;border:1px solid var(--line);white-space:nowrap}
.conn.ok{color:var(--green);border-color:rgba(95,227,164,.3);background:rgba(95,227,164,.07)}
.conn.off{color:var(--red);border-color:rgba(255,125,144,.35);background:rgba(255,125,144,.08)}
.icon{background:rgba(20,30,50,.85);border:1px solid var(--line);color:var(--txt);
  width:34px;height:34px;border-radius:10px;font-size:16px;display:inline-flex;align-items:center;justify-content:center}
.icon:hover{border-color:var(--cyan);color:var(--cyan)}

main{max-width:1180px;margin:0 auto;padding:18px clamp(12px,3vw,28px) 56px;display:flex;flex-direction:column;gap:22px}

/* BÖLÜM BAŞLIKLARI */
.sec-head{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.sec-title{display:flex;align-items:center;gap:9px;margin:0;font-size:13px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#dce7fb}
.step-num{display:inline-grid;place-items:center;width:22px;height:22px;border-radius:7px;
  background:rgba(94,231,240,.14);border:1px solid rgba(94,231,240,.32);color:var(--cyan);font-size:11px;font-weight:800}
.muted{color:var(--muted);font-size:12px}

/* 1. KONTROL VE SENARYO MASASI */
.desk{background:var(--panel);border:1px solid var(--line2);border-radius:var(--radius);padding:14px;box-shadow:var(--shadow)}
.desk-grid{display:flex;flex-direction:column;gap:12px}
.desk-block{background:var(--panel2);border:1px solid var(--line);border-radius:13px;padding:12px}
.desk-block.active-flow{border-color:rgba(94,231,240,.34);background:linear-gradient(160deg,rgba(19,34,62,.85),rgba(11,18,32,.95))}
.desk-block[hidden]{display:none!important}
.new-scen-details>summary{cursor:pointer;font-size:12px;font-weight:750;color:var(--cyan);list-style:none;display:flex;align-items:center;justify-content:space-between;gap:8px}
.new-scen-details>summary::-webkit-details-marker{display:none}
.new-scen-details[open]>summary{margin-bottom:9px}
.ai-body p{margin:0 0 8px}.ai-body p:last-child{margin-bottom:0}
.ai-body .bline{padding-left:12px;border-left:2px solid rgba(94,231,240,.32);margin:6px 0}
.ai-body strong{color:#fff;font-weight:750}
.block-label{font-size:11px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--cyan);margin-bottom:8px;display:flex;align-items:center;justify-content:space-between;gap:8px}
.block-label span{color:var(--muted);font-weight:600;text-transform:none;letter-spacing:0;font-size:11.5px}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.row+.row{margin-top:9px}
input,select{
  background:rgba(6,10,19,.9);color:var(--txt);border:1px solid var(--line2);
  border-radius:11px;min-height:42px;padding:9px 12px;min-width:0
}
input{flex:1 1 220px}
input::placeholder{color:var(--dim)}
input[type=number]{flex:0 0 82px;min-width:74px;text-align:center}
.btn{
  background:rgba(28,41,68,.85);color:var(--txt);border:1px solid var(--line2);border-radius:11px;
  padding:9px 14px;min-height:42px;font-weight:700;font-size:13px;text-decoration:none;
  display:inline-flex;align-items:center;justify-content:center;gap:6px;transition:.16s
}
.btn:hover{border-color:var(--cyan);background:rgba(38,56,90,.92)}
.btn:disabled{opacity:.42;cursor:wait}
.btn.primary{background:linear-gradient(120deg,#2b6be0,#4d8aff);border-color:#639aff;color:#fff;box-shadow:0 6px 20px rgba(55,118,240,.28)}
.btn.accent{background:rgba(94,231,240,.14);border-color:rgba(94,231,240,.44);color:#e3fbff}
.btn.warn{border-color:rgba(255,206,122,.4);color:var(--gold)}
.presets{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.preset{background:rgba(17,27,46,.85);border:1px dashed var(--line2);color:var(--muted);
  border-radius:999px;padding:4px 10px;font-size:11px;transition:.15s}
.preset:hover{color:var(--cyan);border-color:var(--cyan);border-style:solid}
#status{font-size:12.5px;font-weight:700;color:var(--gold);margin-top:8px;min-height:0}
#status:empty{display:none}
.tools-drawer{margin-top:10px;border-top:1px solid var(--line);padding-top:8px}
.tools-drawer summary{cursor:pointer;color:var(--muted);font-size:12px;font-weight:650;padding:4px 2px}
.tools-drawer .drawer-body{padding-top:10px;display:flex;flex-direction:column;gap:9px}

/* 2. GÜNÜN OLAY SAHNESİ (HERO KART) */
.stage{
  background:linear-gradient(160deg,rgba(22,36,66,.96),rgba(11,18,33,.98));
  border:1px solid rgba(109,155,255,.36);border-radius:18px;padding:16px 18px;
  box-shadow:var(--shadow);display:flex;flex-direction:column;gap:14px
}
.stage.empty-stage{border-style:dashed;border-color:var(--line2);background:rgba(14,22,38,.7);padding:18px}
.stage-top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;padding-bottom:12px;border-bottom:1px solid var(--line)}
.stage-topic{flex:1 1 260px;min-width:0}
.stage-kicker{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:5px}
.phase-pill{font-size:10.5px;font-weight:800;letter-spacing:.05em;padding:4px 10px;border-radius:999px;
  background:rgba(94,231,240,.13);border:1px solid rgba(94,231,240,.38);color:var(--cyan);text-transform:uppercase}
.tier-pill{font-size:10.5px;font-weight:700;padding:4px 9px;border-radius:999px;
  background:rgba(181,146,255,.12);border:1px solid rgba(181,146,255,.32);color:var(--violet)}
.stage-title{margin:0;font-size:17px;line-height:1.38;font-weight:800;color:#fff}
.day-nav{display:flex;align-items:center;gap:6px;background:rgba(7,12,23,.8);padding:5px;border-radius:12px;border:1px solid var(--line2)}
.day-nav select{min-height:34px;padding:4px 10px;font-size:13px;font-weight:750;border-radius:8px;border:0;background:transparent}
.nav-btn{background:rgba(26,39,65,.9);border:1px solid var(--line);color:var(--txt);
  width:32px;height:32px;border-radius:8px;font-weight:800;font-size:13px;display:grid;place-items:center}
.nav-btn:disabled{opacity:.3;cursor:default}
.nav-btn:not(:disabled):hover{border-color:var(--cyan);color:var(--cyan)}

.stage-body{display:grid;grid-template-columns:1.25fr 1fr;gap:12px}
.story-box{background:rgba(8,13,25,.72);border:1px solid var(--line);border-radius:13px;padding:13px 14px;display:flex;flex-direction:column;gap:7px}
.story-box.summary-box{border-left:3px solid var(--cyan);background:rgba(12,22,40,.78)}
.box-tag{font-size:10px;font-weight:800;letter-spacing:.09em;text-transform:uppercase;color:var(--cyan)}
.summary-box .box-tag{color:var(--gold)}
.story-lead{font-size:14px;font-weight:700;color:#eef4ff;line-height:1.52}
.story-text{font-size:13.5px;color:var(--sub);line-height:1.62;white-space:pre-wrap;word-break:break-word}
.engine-strip{display:flex;flex-wrap:wrap;gap:7px;padding-top:4px}
.echip{font-size:11px;font-weight:650;padding:4px 10px;border-radius:999px;background:rgba(18,28,48,.9);border:1px solid var(--line);color:var(--sub)}
.echip.warn{color:var(--gold);border-color:rgba(255,206,122,.38);background:rgba(255,206,122,.08)}
.echip.alert{color:var(--red);border-color:rgba(255,125,144,.38);background:rgba(255,125,144,.08)}

/* UYARI BANNER (Yalnızca kısmi/eski kayıt uyarısı varsa görünür) */
.link-banner{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 14px;
  border-radius:12px;border:1px solid var(--line);background:var(--panel);font-size:12px}
.link-banner.hidden{display:none}
.link-banner.eski{border-color:rgba(255,206,122,.4);color:var(--gold)}
.link-banner.kismi{border-color:rgba(181,146,255,.4);color:var(--violet)}

/* 3. TOPLUMSAL NABIZ (KOMPAKT 4'LÜ GÖSTERGE) */
.radar-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.rcard{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:11px 13px;display:flex;flex-direction:column;gap:6px}
.rcard-top{display:flex;align-items:baseline;justify-content:space-between;gap:6px}
.rcard .rk{font-size:10.5px;color:var(--sub);font-weight:750}
.rcard .rv{font-size:16px;font-weight:800;font-variant-numeric:tabular-nums}
.rcard .rs{font-size:10.5px;color:var(--muted);line-height:1.35}
.pbar{height:5px;border-radius:99px;background:rgba(4,8,16,.9);border:1px solid var(--line);overflow:hidden}
.pfill{height:100%;border-radius:99px;transition:width .4s ease}
.pfill.comfort{background:linear-gradient(90deg,#3ca98e,var(--green))}
.pfill.fear{background:linear-gradient(90deg,#d99a4e,var(--gold))}
.pfill.anger{background:linear-gradient(90deg,#d95c68,var(--red))}
.pfill.defense{background:linear-gradient(90deg,var(--blue),var(--violet))}
.mem-strip{margin-top:9px;padding:10px 13px;border-radius:12px;border:1px solid var(--line);
  background:rgba(13,21,37,.82);display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px;font-size:12px;color:var(--sub)}
.mem-strip.hidden{display:none}
.mem-pills{display:flex;flex-wrap:wrap;gap:6px}

/* HIZLI KİTLE ATLAMA ÇUBUĞU (#rail) */
.rail{display:flex;gap:7px;overflow-x:auto;padding:4px 2px 8px;scrollbar-width:thin}
.rail-node{
  flex:0 0 auto;display:inline-flex;align-items:center;gap:7px;
  background:var(--panel);border:1px solid var(--line);border-radius:999px;
  padding:7px 12px;color:var(--sub);font-size:12px;font-weight:700;white-space:nowrap;transition:.16s
}
.rail-node:hover{border-color:var(--cyan);color:var(--txt)}
.rail-dot{width:8px;height:8px;border-radius:50%;background:#41516d}
.rail-node.tam .rail-dot{background:var(--green);box-shadow:0 0 8px rgba(95,227,164,.6)}
.rail-node.eski .rail-dot{background:var(--gold)}
.rail-node.ortak .rail-dot{background:var(--violet)}

/* 4. ALTI KİTLE KARTLARI (NET HİYERARŞİ: BAŞLIK -> ANLATIM -> MİNİ PSİKOLOJİ -> DETAY) */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}
.card{
  background:linear-gradient(165deg,rgba(21,32,54,.95),rgba(11,17,30,.98));
  border:1px solid var(--line);border-radius:var(--radius);padding:15px 16px;
  display:flex;flex-direction:column;gap:12px;box-shadow:var(--shadow);transition:border-color .2s
}
.card:hover{border-color:var(--line2)}
.card.flash{animation:flash 1.1s ease}
@keyframes flash{0%,100%{box-shadow:var(--shadow)}35%{box-shadow:0 0 0 2px var(--cyan),0 16px 48px rgba(94,231,240,.25)}}

.card-head{display:flex;align-items:center;justify-content:space-between;gap:8px}
.card-id{display:flex;align-items:center;gap:9px;min-width:0}
.num{display:inline-grid;place-items:center;width:27px;height:27px;flex:none;border-radius:8px;
  background:rgba(94,231,240,.14);border:1px solid rgba(94,231,240,.28);color:var(--cyan);font-weight:800;font-size:12px}
.card h3{margin:0;font-size:15px;font-weight:800;color:#fff;line-height:1.25}
.share{font-size:11px;color:var(--muted);font-weight:650;margin-left:4px}
.mood-pill{font-size:10px;font-weight:750;padding:4px 9px;border-radius:999px;border:1px solid var(--line2);
  background:rgba(16,25,44,.9);color:var(--sub);white-space:nowrap}
.mood-pill.anger{color:var(--red);border-color:rgba(255,125,144,.38);background:rgba(255,125,144,.09)}
.mood-pill.fear{color:var(--gold);border-color:rgba(255,206,122,.38);background:rgba(255,206,122,.09)}
.mood-pill.calm{color:var(--green);border-color:rgba(95,227,164,.34);background:rgba(95,227,164,.08)}
.mood-pill.guard{color:var(--violet);border-color:rgba(181,146,255,.36);background:rgba(181,146,255,.09)}

/* KART ANA ANLATIM ALANI */
.ai-box{background:rgba(8,13,24,.72);border:1px solid rgba(118,152,220,.22);border-radius:12px;padding:12px 13px;display:flex;flex-direction:column;gap:8px}
.ai-box.yok{border-style:dashed;border-color:var(--line);background:rgba(9,14,26,.45);padding:11px 13px}
.ai-top{display:flex;align-items:center;justify-content:space-between;gap:8px}
.ai-label{font-size:10px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:var(--cyan)}
.mini{background:rgba(126,156,214,.1);border:1px solid var(--line);color:var(--muted);
  border-radius:7px;padding:3px 8px;font-size:10px;font-weight:700}
.mini:hover{color:var(--cyan);border-color:var(--cyan)}
.ai-body{font-size:13.5px;line-height:1.64;white-space:pre-wrap;word-break:break-word;color:#e4edff}
.ai-body.clamped{max-height:210px;overflow:hidden;
  -webkit-mask-image:linear-gradient(to bottom,black 74%,transparent);
  mask-image:linear-gradient(to bottom,black 74%,transparent)}
.ai-yok{font-size:12.5px;color:var(--muted);line-height:1.5}

/* ZENGİNLER 3 ALT KANAT */
.subwings{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}
.sw-chip{background:rgba(14,23,40,.9);border:1px solid var(--line);border-radius:9px;padding:6px 8px;font-size:10.5px;line-height:1.35;color:var(--muted)}
.sw-chip strong{display:block;color:var(--txt);font-size:10.5px;margin-bottom:2px}

/* KOMPAKT PSİKOLOJİ ÇUBUKLARI */
.psych-compact{background:rgba(10,16,29,.65);border:1px solid var(--line);border-radius:11px;padding:9px 11px;display:flex;flex-direction:column;gap:8px}
.psych-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px 12px}
.pitem-label{font-size:10px;color:var(--muted);display:flex;justify-content:space-between;gap:4px;margin-bottom:3px}
.pitem-label b{color:var(--txt);font-variant-numeric:tabular-nums}
.deep-tags{display:flex;flex-wrap:wrap;gap:5px}
.dtag{font-size:10px;padding:3px 8px;border-radius:999px;background:rgba(17,27,47,.9);border:1px solid var(--line);color:var(--sub);font-variant-numeric:tabular-nums}
.dtag.alert{color:var(--red);border-color:rgba(255,125,144,.38);background:rgba(255,125,144,.09)}
.dtag.warn{color:var(--gold);border-color:rgba(255,206,122,.36);background:rgba(255,206,122,.08)}
.dtag.ok{color:var(--green);border-color:rgba(95,227,164,.34);background:rgba(95,227,164,.08)}

/* KART ALT DETAY ÇEKMECESİ */
.detail{border-top:1px solid var(--line);padding-top:8px;font-size:12px;color:var(--muted)}
.detail summary{cursor:pointer;color:var(--muted);font-weight:650;font-size:11.5px}
.detail summary:hover{color:var(--cyan)}
.detail-body{padding-top:8px;display:flex;flex-direction:column;gap:7px;line-height:1.52}
.metrics{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding-top:4px}
.metric-label{font-size:10.5px;color:var(--muted);margin-bottom:4px;display:flex;justify-content:space-between}
.bar{height:5px;border-radius:99px;background:rgba(4,8,16,.9);border:1px solid var(--line);overflow:hidden}
.fill{height:100%;border-radius:99px;background:linear-gradient(90deg,var(--blue),var(--cyan))}

/* 5. GÜN GÜN KRİZ KRONOLOJİSİ */
.timeline{display:flex;flex-direction:column;gap:9px}
.day-row{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:12px 14px;display:flex;flex-direction:column;gap:6px}
.day-row.active-day{border-color:rgba(94,231,240,.45);background:rgba(18,31,56,.9)}
.day-row-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}
.day-no{font-size:11px;color:var(--cyan);font-weight:800;letter-spacing:.06em;text-transform:uppercase}
.day-event{font-size:13px;font-weight:650;color:var(--txt);line-height:1.48}
.day-genel{font-size:12px;color:var(--sub);border-left:2px solid rgba(94,231,240,.45);padding-left:9px;margin-top:2px}

/* TEKNİK KAYIT ÇEKMECESİ */
.tech-drawer{background:var(--panel2);border:1px solid var(--line);border-radius:14px;padding:11px 14px}
.tech-drawer summary{cursor:pointer;color:var(--muted);font-size:12px;font-weight:700}
.tech-body{padding-top:12px;display:flex;flex-direction:column;gap:12px}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:9px 11px}
.stat .k{font-size:9.5px;color:var(--dim);text-transform:uppercase;letter-spacing:.08em;font-weight:800}
.stat .v{font-size:15px;font-weight:750;margin-top:3px;font-variant-numeric:tabular-nums}
.output-wrap{background:#060a12;border:1px solid var(--line);border-radius:12px;overflow:hidden}
.output-head{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;border-bottom:1px solid var(--line);font-size:11px;color:var(--muted)}
.output{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;padding:12px;font-size:11.5px;line-height:1.55;white-space:pre-wrap;word-break:break-word;overflow:auto;max-height:340px;margin:0;color:#c5d4ec}
.events{display:flex;flex-wrap:wrap;gap:6px}
.chip{font-size:10px;background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:3px 9px;color:var(--muted)}

footer{padding:8px 2px 0;color:var(--dim);font-size:11px;border-top:1px solid var(--line);line-height:1.6}
.toast{position:fixed;left:50%;bottom:20px;transform:translateX(-50%) translateY(18px);
  background:rgba(22,34,58,.98);border:1px solid var(--line2);color:var(--txt);padding:10px 16px;
  border-radius:11px;font-size:12.5px;opacity:0;pointer-events:none;transition:.2s;z-index:60;max-width:92vw;text-align:center;box-shadow:var(--shadow)}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.toast.err{border-color:var(--red)}

@media(max-width:860px){
  .stage-body{grid-template-columns:1fr}
  .radar-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:600px){
  main{padding:14px 11px 44px;gap:18px}
  .cards{grid-template-columns:1fr}
  .subwings{grid-template-columns:1fr}
  .btn{flex:1 1 auto}
  .stage{padding:14px}
  .stage-title{font-size:15.5px}
}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}html{scroll-behavior:auto}}
</style>
</head>
<body>
<header class="topbar">
  <div class="brand"><span class="brand-mark"></span><span>PEOPLE<b>1000</b></span></div>
  <div class="badges">
    <span id="conn" class="conn off">○ BAĞLANIYOR</span>
    <span id="modeBadge" class="badge">—</span>
    <span id="quotaBadge" class="badge">Kota —</span>
    <span id="dayBadge" class="badge strong">Gün —</span>
    <button id="refreshBtn" class="icon" title="Yenile" aria-label="Durumu yenile">↻</button>
  </div>
</header>

<main>
  <!-- 1. OLAY GİRİŞİ VE SENARYO KONTROLÜ -->
  <section id="controlDesk">
    <div class="sec-head">
      <h2 class="sec-title"><span class="step-num">1</span> Senaryo ve Müdahale Kontrolü</h2>
      <span class="muted">1 Başlat/Devam = 1 API isteği · Motor hesabı ücretsiz</span>
    </div>
    <div class="desk">
      <div class="desk-grid">
        <div id="activeFlowBox" class="desk-block active-flow" hidden>
          <div class="block-label">Aktif Kriz Akışını İlerlet veya Müdahale Et <span id="flowHint">Mevcut senaryoyu gün gün ilerletin</span></div>
          <div class="row">
            <button data-cmd="devam" data-count="1" class="btn primary">▸ Sonraki Güne Geç (+1 Gün)</button>
            <button data-cmd="devam" data-count="3" class="btn accent">+3 Gün</button>
            <input id="devamCount" type="number" min="1" max="30" value="5" aria-label="Çoklu devam gün sayısı">
            <button data-cmd="devam" data-custom-count="1" class="btn">Çoklu İlerlet</button>
            <button id="stopBtn" type="button" class="btn warn" hidden>■ Durdur</button>
          </div>
          <div class="row">
            <input id="olayText" maxlength="2000" placeholder="Ara müdahale ekle (ör. bağımsız denetim başlatıldı / içeriden belge sızdı)">
            <button data-cmd="olay" class="btn">Müdahale Ekle</button>
          </div>
          <div class="presets">
            <button type="button" class="preset" data-fill="olayText" data-val="Bağımsız denetim başlatıldı, sorumlu üst yönetici istifa etti ve güvenlik önlem alındı">✓ Şeffaf denetim &amp; istifa</button>
            <button type="button" class="preset" data-fill="olayText" data-val="İçeriden daha önce sümenaltı edilmiş resmi denetim uyarısı belgesi sızdı">📄 Belge sızdı</button>
            <button type="button" class="preset" data-fill="olayText" data-val="Bağımsız gözlemci ve uzmanlar kanıta dayalı teknik uyarı raporu yayınladı">🔬 Uzman teknik uyarısı</button>
            <button type="button" class="preset" data-fill="olayText" data-val="Yayın yasağı getirildi ve sert eleştiri yapan yorumculara gözaltı işlemi yapıldı">⚠ Yayın yasağı &amp; gözaltı</button>
            <button type="button" class="preset" data-fill="olayText" data-val="Halk güvenlik ve geçim tepkisiyle günlük hayat boykotu başlattı">✊ Toplumsal boykot</button>
          </div>
        </div>

        <details id="newScenarioDetails" class="desk-block new-scen-details" open>
          <summary><span id="newScenarioSummary">✦ Yeni Olay / Senaryo Başlat (Gün 1)</span><span class="muted">aç / kapat</span></summary>
          <div class="row">
            <input id="sorText" maxlength="2000" placeholder="Örn: Büyük maden faciası yaşandı, denetim ihmali tartışılıyor">
            <button data-cmd="sor" class="btn primary">✦ Senaryoyu Başlat</button>
          </div>
          <div class="presets">
            <button type="button" class="preset" data-fill="sorText" data-val="Büyük maden faciası yaşandı, denetim ihmali iddiası var">⚡ Maden faciası</button>
            <button type="button" class="preset" data-fill="sorText" data-val="Büyük ihale yolsuzluğu ortaya çıktı ve sert fiyat artışı başladı">⚡ İhale yolsuzluğu &amp; zam</button>
            <button type="button" class="preset" data-fill="sorText" data-val="Organize sanayi fabrikasında büyük yangın çıktı, güvenlik açığı tartışılıyor">⚡ Fabrika yangını</button>
          </div>
        </details>
      </div>

      <div id="status"></div>

      <details class="tools-drawer">
        <summary>Diğer Araçlar: Sıradan Atama Günü, Kayıt, Kota ve API Ayarları</summary>
        <div class="drawer-body">
          <div class="row">
            <button data-cmd="gun" class="btn">Sıradan Gündem (+1 Gün)</button>
            <button data-cmd="ilerle" data-count="3" class="btn">Sıradan (+3 Gün)</button>
            <button data-cmd="ozet" class="btn">Türkçe Özet</button>
            <button data-cmd="rapor" class="btn">Ham Rapor</button>
            <button data-cmd="ayar" class="btn">Ayar</button>
            <button data-cmd="kaydet" class="btn">Kaydet</button>
            <a class="btn" href="/api/export" download>JSON İndir</a>
            <button data-cmd="yardim" class="btn">Yardım</button>
          </div>
          <div class="row">
            <input id="sorLimitVal" type="number" min="1" max="200" value="20" aria-label="Soru limiti">
            <button data-cmd="sor-limit" class="btn">Soru Limiti</button>
            <input id="beklemeVal" type="number" min="0" max="60" step="1" value="6" aria-label="Bekleme saniyesi">
            <button data-cmd="bekleme" class="btn">Bekleme (sn)</button>
            <input id="tokenLimitVal" type="number" min="256" max="8192" step="128" value="4096" aria-label="Çıktı token sınırı">
            <input id="timeoutVal" type="number" min="5" max="120" step="5" value="30" aria-label="Zaman aşımı saniyesi">
            <button data-cmd="token-limit" class="btn">Token / Süre</button>
          </div>
          <div class="row">
            <input id="limitTotal" type="number" min="1" max="200" value="30" aria-label="Toplam limit">
            <input id="limitDaily" type="number" min="1" max="200" value="10" aria-label="Günlük limit">
            <button data-cmd="limit" class="btn">Gündem Limiti</button>
            <button data-cmd="baglanti" data-confirm="1" class="btn warn">Bağlantı Testi</button>
            <button data-cmd="modeller" data-confirm="1" class="btn warn">Modeller</button>
            <button data-cmd="uretim-test" data-confirm="1" class="btn warn">Üretim Testi</button>
          </div>
        </div>
      </details>
    </div>
  </section>

  <!-- 2. GÜNÜN OLAY DURUMU VE SAHNE ÖZETİ (6 KARAKTERDEN ÖNCE GELİR!) -->
  <section id="stageSection">
    <div class="sec-head">
      <h2 class="sec-title"><span class="step-num">2</span> Günün Olay Durumu ve Genel Tablo</h2>
      <span id="aiKaynak" class="muted"></span>
    </div>
    <div id="linkBanner" class="link-banner hidden"></div>
    <div id="stageHero" class="stage empty-stage">
      <div class="stage-top">
        <div class="stage-topic">
          <div id="stageKicker" class="stage-kicker"></div>
          <h3 id="stageTitle" class="stage-title">Henüz aktif bir olay başlatılmadı</h3>
        </div>
        <div class="day-nav">
          <button id="prevDayBtn" type="button" class="nav-btn" title="Önceki gün" aria-label="Önceki gün">◀</button>
          <select id="aiGun" aria-label="Anlatım günü"></select>
          <button id="nextDayBtn" type="button" class="nav-btn" title="Sonraki gün" aria-label="Sonraki gün">▶</button>
        </div>
      </div>
      <div id="stageBody" class="stage-body"></div>
      <div id="stageEngine" class="engine-strip"></div>
    </div>
  </section>

  <!-- 3. TOPLUMSAL TANSİYON ÖZETİ -->
  <section>
    <div class="sec-head">
      <h2 class="sec-title"><span class="step-num">3</span> Toplumsal Nabız ve Kırılganlık</h2>
      <span class="muted">100 kişilik simülasyon ağının anlık psikolojik dengesi</span>
    </div>
    <div id="mindRadar" class="radar-grid"></div>
    <div id="memoryStrip" class="mem-strip hidden"></div>
  </section>

  <!-- 4. ALTI KİTLENİN TEPKİSİ -->
  <section>
    <div class="sec-head">
      <h2 class="sec-title"><span class="step-num">4</span> Altı Kitlenin Tepkisi</h2>
      <span id="railInfo" class="muted"></span>
    </div>
    <div id="rail" class="rail"></div>
    <div class="cards" id="cards"></div>
  </section>

  <!-- 5. GÜN GÜN KRİZ GEÇMİŞİ -->
  <section id="scenarioSection">
    <div class="sec-head">
      <h2 class="sec-title"><span class="step-num">5</span> Gün Gün Kriz Kronolojisi</h2>
      <span id="scenarioBadge" class="muted"></span>
    </div>
    <div class="timeline" id="timeline"></div>
  </section>

  <!-- TEKNİK KAYITLAR VE HAM ÇIKTI (KATLANABİLİR) -->
  <details class="tech-drawer">
    <summary>Teknik Sayaçlar, Motor Olayları ve Ham Çıktı <span id="lastCmd" class="muted"></span></summary>
    <div class="tech-body">
      <div class="summary" id="summary"></div>
      <div class="output-wrap">
        <div class="output-head">
          <span>Son komutun ham çıktısı</span>
          <button type="button" class="mini" data-copy="output">Kopyala</button>
        </div>
        <pre id="output" class="output">Henüz komut çalıştırılmadı.</pre>
      </div>
      <div class="events" id="events"></div>
    </div>
  </details>

  <footer>
    API anahtarı tarayıcıya gönderilmez; tüm istekler yerel sunucudan yapılır.
    Üstteki olay sahnesi ve kitle anlatımları seçili güne aittir; çubuklar motorun yerel psikolojik durumunu gösterir.
  </footer>
</main>

<div id="toast" class="toast"></div>
<script>
"use strict";
const $=s=>document.querySelector(s);
let state=null,busy=false,firstLoad=true,stopRequested=false;

const DURUM={tam:"AI BAĞLI",eski:"ESKİ ÖZET",ortak:"GÜNÜN ORTAK ANLATIMI",yok:"BEKLİYOR"};
const PAYLAR={power_aligned:"%30",opposition:"%30",authority:"%15",wealthy:"%12",discontented:"%10",observer:"%3"};
const SEVIYE_TR={
  ordinary:"Sıradan Gündem",
  institutional_crisis:"Kurumsal / Ekonomik Kriz",
  severe_security_crisis:"Ağır Güvenlik / İhmal Krizi"
};
const DAL_TR={
  standart:"Başlangıç Evresi",
  ilk_sok:"İlk Şok ve Belirsizlik",
  kurumsal_belirsizlik:"Kurumsal Belirsizlik",
  yayin_kisitlamasi:"Yayın Kısıtlaması ve Algı Savaşı",
  ihmal_sizintisi:"İçeriden Belge Sızıntısı",
  sizinti_ve_sorusturma:"Belge Sızıntısı ve Soruşturma",
  erken_sizinti:"Erken Belge İfşası",
  epistemik_teknik_uyari:"Uzman / Gözlemci Teknik Uyarısı",
  medya_yaptirimi:"Medyaya Yaptırım ve Otosansür",
  otosansur_ve_baski:"Soruşturma Baskısı ve Otosansür",
  sert_baski:"Sert Baskı ve Gözaltılar",
  artci_kriz:"Önlemsizlikten Doğan İkincil Kriz",
  toplumsal_boykot:"Toplumsal Boykot ve Panik",
  gunah_kecisi_manevrasi:"Günah Keçisi Manevrası",
  gunah_kecisi_cokusu:"Günah Keçisi İlanı ve Tekil Çöküş",
  alt_kademe_tasfiyesi:"Alt Kademe Tasfiyesi",
  seffaf_onarim:"Şeffaf Soruşturma ve Onarım",
  gecikmeli_onlem:"Gecikmeli Güvenlik Önlemleri",
  alt_kademede_kapatma:"Dosyanın Alt Kademede Kapatılması",
  sogutma_ve_yorgunluk:"Gündemi Soğutma ve Yorgunluk",
  tukenmislik_ve_kalici_guvensizlik:"Tükenmişlik ve Kalıcı Güvensizlik"
};

function cleanRoleName(raw){
  return String(raw||"").replace(/^\d+\.\s*/,"").replace(/\s*\([a-z_]+\)\s*$/i,"").trim();
}
function cleanIntroText(ortak,ev){
  if(!ortak)return "";
  const lines=String(ortak).split("\n").map(x=>x.trim()).filter(Boolean).filter(l=>
    !/^=+/.test(l)&&
    !/^SENARYO ZİNCİRİ/i.test(l)&&
    !/^Nedensel Sınır/i.test(l)&&
    !/^Motor Yansıması/i.test(l)
  ).map(l=>l.replace(/^Günün Gelişmesi[^:]*:\s*/i,"").trim()).filter(Boolean);
  const joined=lines.join("\n\n").trim();
  if(!joined)return "";
  if(ev&&joined===String(ev).trim())return "";
  return joined;
}
function dalEtiketi(d){return DAL_TR[d]||(d?String(d).replace(/_/g," "):"");}
function node(tag,cls,text){
  const e=document.createElement(tag);
  if(cls)e.className=cls;
  if(text!==undefined&&text!==null)e.textContent=String(text);
  return e;
}
function toast(msg,err){
  const t=$("#toast");t.textContent=msg;
  t.className="toast show"+(err?" err":"");
  setTimeout(()=>{t.className="toast";},2800);
}
function setConn(ok){
  const e=$("#conn");e.className="conn "+(ok?"ok":"off");
  e.textContent=ok?"● BAĞLI":"○ BAĞLANTI YOK";
}
function showOutput(t){$("#output").textContent=t||"(çıktı yok)";}
function setBusy(v,msg,cancellable){
  busy=v;
  document.querySelectorAll("[data-cmd]").forEach(b=>b.disabled=v);
  const sb=$("#stopBtn");if(sb)sb.hidden=!(v&&cancellable);
  $("#status").textContent=v?(msg||"Çalışıyor…"):"";
}
function copyText(text,label){
  if(!text){toast("Kopyalanacak metin yok",true);return;}
  const done=()=>toast((label||"Metin")+" kopyalandı");
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(done).catch(()=>legacyCopy(text,done));
  }else legacyCopy(text,done);
}
function legacyCopy(text,done){
  const ta=document.createElement("textarea");
  ta.value=text;ta.style.position="fixed";ta.style.opacity="0";document.body.append(ta);
  ta.select();try{document.execCommand("copy");done();}catch(e){toast("Kopyalanamadı",true);}ta.remove();
}
function appendRichLine(parent,line){
  /* Güvenli DOM biçimlendirme: **kalın** ve 'Başlık: açıklama' vurgusu (innerHTML yok) */
  let s=String(line||"").replace(/^\*{1,2}|\*{1,2}$/g,"");
  const parts=s.split(/(\*\*[^*]+\*\*)/g);
  if(parts.length>1){
    parts.forEach(pt=>{
      if(pt.startsWith("**")&&pt.endsWith("**")&&pt.length>4)parent.append(node("strong","",pt.slice(2,-2)));
      else if(pt)parent.append(document.createTextNode(pt));
    });
    return;
  }
  const m=s.match(/^([^:]{3,52}:)\s+(.+)$/);
  if(m){
    parent.append(node("strong","",m[1]+" "),document.createTextNode(m[2]));
  }else{
    parent.append(document.createTextNode(s));
  }
}
function fillRichBody(box,raw){
  const lines=String(raw||"(boş)").split(/\n+/).map(x=>x.trim()).filter(Boolean);
  lines.forEach(ln=>{
    const isBullet=/^[•\-\*]\s+/.test(ln);
    const clean=ln.replace(/^[•\-\*]\s+/,"").trim();
    const row=node(isBullet?"div":"p",isBullet?"bline":"");
    appendRichLine(row,clean);
    box.append(row);
  });
}
function stat(k,v){const d=node("div","stat");d.append(node("div","k",k),node("div","v",v));return d;}
function dtag(text,tone){return node("span","dtag"+(tone?" "+tone:""),text);}

function pbar(label,val,tone,extraText){
  const w=node("div","pitem"),lab=node("div","pitem-label");
  lab.append(node("span","",label),node("b","",extraText||(val===null||val===undefined?"—":"%"+val)));
  const bar=node("div","pbar"),fill=node("div","pfill "+(tone||"comfort"));
  fill.style.width=(val===null||val===undefined?0:Math.max(0,Math.min(100,val)))+"%";
  bar.append(fill);w.append(lab,bar);return w;
}

function moodClass(dom){
  if(!dom)return "";
  if(dom==="ofke_ve_itiraz"||dom==="epistemik_uyari")return "anger";
  if(dom==="korku_otosansur"||dom==="bastirilmis_ofke"||dom==="tukenmislik")return "fear";
  if(dom==="suc_kaydirma"||dom==="rasyonalizasyon_savunmasi"||dom==="kuskun_kopus"||dom==="cogulcu_cehalet")return "guard";
  return "calm";
}

/* 2. SAHNE (OLAY DURUMU VE GENEL ÖZET) */
function renderStage(s){
  const hero=$("#stageHero"),kicker=$("#stageKicker"),title=$("#stageTitle"),
        body=$("#stageBody"),eng=$("#stageEngine"),sel=$("#aiGun"),
        prevB=$("#prevDayBtn"),nextB=$("#nextDayBtn"),flowBox=$("#activeFlowBox");
  kicker.replaceChildren();body.replaceChildren();eng.replaceChildren();sel.replaceChildren();

  const gunler=Object.keys(s.senaryo.gunler||{}).sort((a,b)=>Number(a)-Number(b));
  gunler.forEach(g=>{const o=node("option","","Gün "+g);o.value=g;sel.append(o);});
  sel.disabled=!gunler.length;

  const newDet=$("#newScenarioDetails"),newSum=$("#newScenarioSummary");
  if(!s.senaryo.var||!gunler.length){
    hero.className="stage empty-stage";
    title.textContent="Henüz aktif bir olay başlatılmadı";
    const info=node("div","story-box");
    info.append(node("div","box-tag","Nasıl Başlanır?"),
      node("div","story-text","Yukarıdaki kutuya bir olay yazıp “Senaryoyu Başlat” düğmesine basın. Önce burada günün olay gelişmesi ve genel sonucu açılır, ardından aşağıda 6 kitlenin ayrı tepkilerini okursunuz."));
    body.append(info);
    prevB.disabled=true;nextB.disabled=true;
    if(flowBox)flowBox.hidden=true;
    if(newDet)newDet.open=true;
    if(newSum)newSum.textContent="✦ Yeni Olay / Senaryo Başlat (Gün 1)";
    $("#aiKaynak").textContent="";
    return;
  }

  if(flowBox)flowBox.hidden=false;
  if(newDet&&firstLoad)newDet.open=false;
  if(newSum)newSum.textContent="✦ Farklı / Yeni Bir Senaryo Başlat (Mevcut Zinciri Değiştirir)";
  hero.className="stage";
  const curKey=String(s.senaryo.secili_gun||gunler[gunler.length-1]);
  sel.value=curKey;
  const idx=gunler.indexOf(curKey);
  prevB.disabled=(idx<=0);
  nextB.disabled=(idx<0||idx>=gunler.length-1);

  const g=s.senaryo.gunler[curKey]||{};
  kicker.append(node("span","phase-pill","GÜN "+curKey+(g.dal?" · "+dalEtiketi(g.dal):"")));
  kicker.append(node("span","tier-pill",SEVIYE_TR[s.senaryo.seviye]||s.senaryo.seviye));
  title.textContent="Konu: "+s.senaryo.ilk_olay;
  $("#flowHint").textContent="Şu an "+s.senaryo.gun+". gündesiniz";

  /* Sol kutu: Bugün Ne Yaşandı? */
  const left=node("div","story-box");
  left.append(node("div","box-tag","Bugün Ne Yaşandı? (Gün "+curKey+")"));
  if(g.event)left.append(node("div","story-lead",g.event));
  const intro=cleanIntroText(g.ortak,g.event);
  if(intro)left.append(node("div","story-text",intro));
  else if(!g.event)left.append(node("div","story-text","Bu gün için giriş açıklaması kaydedilmemiş."));
  body.append(left);

  /* Sağ kutu: Günün Genel Sonucu */
  const right=node("div","story-box summary-box");
  right.append(node("div","box-tag","Günün Genel Özeti ve Sonuç"));
  if(g.genel){
    right.append(node("div","story-text",g.genel));
  }else{
    right.append(node("div","story-text","Altı kitlenin tamamı olayı kendi çıkar, korku ve tahammül eşiğine göre yorumladı; ayrıntılar aşağıdaki 6 kartta yer alıyor."));
  }
  body.append(right);

  /* Gerçek simülasyon motoru etki şeridi */
  const me=g.motor_etkisi||{};
  if(me.sim_day){
    eng.append(node("span","echip","Kurumsal Güven: %"+(me.mean_trust??"—")));
    if(me.price&&me.price!==1)eng.append(node("span","echip "+(me.price>=1.15?"warn":""),"Fiyat Çarpanı: x"+me.price));
    if(me.employer_cut_workers>0)eng.append(node("span","echip alert","İşveren Gelir Kesintisi: "+me.employer_cut_workers+" çalışan"));
    if(me.self_censored_blocks>0)eng.append(node("span","echip warn","Korku / Otosansür Engeli: "+me.self_censored_blocks+" yayın"));
    if(me.disengaged_citizens>0)eng.append(node("span","echip warn","Küskün Kopuş: "+me.disengaged_citizens+" kişi"));
    if(me.observer_warnings>0)eng.append(node("span","echip alert","Gözlemci Teknik Uyarısı: "+me.observer_warnings));
  }
  const b=s.baglanti||{};
  $("#aiKaynak").textContent="Gün "+curKey+" / "+gunler.length+" · "+(b.bagli||0)+"/6 kitle bağlı";
}

function renderBanner(s){
  const b=s.baglanti||{},el=$("#linkBanner");
  el.replaceChildren();
  /* Her şey tam veya henüz senaryo yoksa gereksiz yer kaplama */
  if(!s.senaryo.var||b.durum==="tam"||b.durum==="yok"){
    el.className="link-banner hidden";return;
  }
  el.className="link-banner "+(b.durum||"");
  el.append(node("span","",b.aciklama||""),node("b","",(b.bagli||0)+"/6 kart"));
}

/* 3. TOPLUMSAL NABIZ (SADE 4 GÖSTERGE) */
function renderMindRadar(s){
  const el=$("#mindRadar"),ms=$("#memoryStrip");
  el.replaceChildren();ms.replaceChildren();
  const z=s.sosyal_zihin||{};
  const items=[
    {k:"Sahte Uyum / Otosansür",v:z.sahte_uyum_riski??0,tone:"fear",sub:"Korkuyla susan veya imalı konuşan kesim"},
    {k:"Biriken Patlama Gerilimi",v:z.yay_bosalma_potansiyeli??0,tone:"anger",sub:"Bastırılmış öfke ve adaletsizlik hissi"},
    {k:"Küskün / Sessiz Kopuş",v:z.kuskun_secmen_orani??0,tone:"defense",sub:"Taraf değiştirmeden geri çekilen seçmen"},
    {k:"Gözlemci Teknik Alarmı",v:z.gozlemci_epistemik_alarm??0,tone:"comfort",sub:z.gozlemci_uyari_hazir?"Kritik ihmal uyarısı eşiğinde":"İki kutbu çapraz izleme düzeyi"}
  ];
  items.forEach(it=>{
    const c=node("div","rcard"),top=node("div","rcard-top"),bar=node("div","pbar"),fill=node("div","pfill "+it.tone);
    fill.style.width=Math.max(0,Math.min(100,it.v))+"%";bar.append(fill);
    top.append(node("span","rk",it.k),node("span","rv","%"+it.v));
    c.append(top,bar,node("div","rs",it.sub));
    el.append(c);
  });
  const h=s.hafiza||{};
  if((h.gecmis_kriz_sayisi||0)>0){
    ms.className="mem-strip";
    ms.append(node("span","","Toplumsal Hafıza ("+h.gecmis_kriz_sayisi+" geçmiş kriz): "+(h.yorum||"")));
    const pills=node("div","mem-pills");
    pills.append(
      dtag("Örtbas İzi %"+(h.ortbas_izi||0),(h.ortbas_izi||0)>=20?"alert":""),
      dtag("Günah Keçisi %"+(h.gunah_kecisi_izi||0),(h.gunah_kecisi_izi||0)>=20?"warn":""),
      dtag("Onarım Kredisi %"+(h.onarim_kredisi||0),(h.onarim_kredisi||0)>0?"ok":"")
    );
    ms.append(pills);
  }else{
    ms.className="mem-strip hidden";
  }
}

/* HIZLI KİTLE GEÇİŞ ÇUBUĞU */
function renderRail(s){
  const rail=$("#rail");rail.replaceChildren();
  s.kitleler.forEach(c=>{
    const b=node("button","rail-node "+c.ai_durum);
    b.type="button";
    b.append(node("span","rail-dot"),node("span","",c.sira+". "+cleanRoleName(c.ad)+" ("+(PAYLAR[c.id]||"")+")"));
    b.addEventListener("click",()=>{
      const el=$("#card-"+c.id);if(!el)return;
      el.scrollIntoView({behavior:"smooth",block:"center"});
      el.classList.remove("flash");void el.offsetWidth;el.classList.add("flash");
      setTimeout(()=>el.classList.remove("flash"),1100);
    });
    rail.append(b);
  });
  $("#railInfo").textContent="Hızlı geçiş için kitleye dokunun";
}

/* 4. KİTLE KARTI (ÖNCE ANLATIM, SONRA KOMPAKT PSİKOLOJİ, EN ALTTA DETAY ÇEKMECESİ) */
function card(c){
  const ps=c.psikoloji||{};
  const d=node("article","card");d.id="card-"+c.id;

  /* 1. Başlık */
  const head=node("div","card-head"),left=node("div","card-id");
  const titleWrap=node("h3","",cleanRoleName(c.ad));
  titleWrap.append(node("span","share",PAYLAR[c.id]||""));
  left.append(node("span","num",c.sira),titleWrap);
  head.append(left,node("span","mood-pill "+moodClass(ps.baskin_durum),ps.baskin_etiket||DURUM[c.ai_durum]||"Bekliyor"));
  d.append(head);

  /* 2. Kitle Anlatımı (Birincil Odak!) */
  const ai_durum=c.ai_durum;
  const box=node("div","ai-box "+(ai_durum==="yok"?"yok":""));
  if(ai_durum==="yok"){
    box.append(node("div","ai-yok","Henüz senaryo anlatımı yok. Yukarıdan bir olay başlattığınızda bu kitlenin tepkisi burada açılır."));
  }else{
    const ortak=(ai_durum==="ortak");
    const metin=ortak?c.ai_ortak:c.ai_metni;
    const top=node("div","ai-top");
    top.append(node("span","ai-label",ortak?"GÜNÜN ORTAK ANLATIMI":(ps.ifade_etiketi||"Kitle Tepkisi")));
    const cp=node("button","mini","Kopyala");cp.type="button";
    cp.addEventListener("click",()=>copyText(metin,cleanRoleName(c.ad)));
    top.append(cp);box.append(top);

    const body=node("div","ai-body");
    fillRichBody(body,metin);
    if((metin||"").length>680){
      body.classList.add("clamped");
      const toggle=node("button","mini","Devamını oku ↓");toggle.type="button";
      toggle.addEventListener("click",()=>{
        const cl=body.classList.toggle("clamped");
        toggle.textContent=cl?"Devamını oku ↓":"Daralt ↑";
      });
      box.append(body,toggle);
    }else{
      box.append(body);
    }
  }
  d.append(box);

  /* Zenginler için 3 Alt Kanat Özeti */
  if(ps.alt_kanatlar){
    const sw=node("div","subwings");
    const names={pro_A:"A Yanlısı Medya",pro_B:"B Yanlısı Medya",neutral_commercial:"Tarafsız / Ticari"};
    ["pro_A","pro_B","neutral_commercial"].forEach(k=>{
      const x=ps.alt_kanatlar[k];if(!x)return;
      const chip=node("div","sw-chip");
      chip.append(node("strong","",names[k]||k),
        document.createTextNode((x.ifade_etiketi||"Açık")+" · Korku %"+(x.korku||0)));
      sw.append(chip);
    });
    d.append(sw);
  }

  /* 3. Kompakt Duygu Çubukları */
  if(ps.baskin_etiket){
    const pc=node("div","psych-compact"),g=node("div","psych-grid");
    g.append(
      pbar("Konfor",ps.konfor,"comfort"),
      pbar("Korku",ps.korku,"fear"),
      pbar("Öfke",ps.ofke,"anger","%"+(ps.ofke||0)+((ps.bastirilmis_ofke||0)>5?" (İç %"+ps.bastirilmis_ofke+")":"")),
      pbar("Savunma Duvarı",ps.savunma,"defense")
    );
    pc.append(g);
    const tags=node("div","deep-tags");
    if((ps.tukenmislik||0)>=12)tags.append(dtag("Tükenmişlik %"+ps.tukenmislik,"warn"));
    if(c.id==="power_aligned"){
      tags.append(dtag("Aracı Güveni %"+(ps.araci_guveni??75),(ps.araci_guveni??75)<45?"warn":""));
      if((ps.kuskun_oran||0)>0)tags.append(dtag("Küskün Kopuş %"+ps.kuskun_oran,"alert"));
    }else if(c.id==="opposition"&&(ps.cogulcu_cehalet||0)>=12){
      tags.append(dtag("Çoğulcu Cehalet %"+ps.cogulcu_cehalet,"warn"));
    }else if(c.id==="authority"&&(ps.ic_sizinti_egilimi||0)>=15){
      tags.append(dtag("İç Sızıntı Eğilimi %"+ps.ic_sizinti_egilimi,(ps.ic_sizinti_egilimi||0)>=45?"alert":""));
    }else if(c.id==="discontented"){
      if((ps.goreli_yoksunluk||0)>=10)tags.append(dtag("Göreli Yoksunluk %"+ps.goreli_yoksunluk,"alert"));
      tags.append(dtag("Dayanışma %"+(ps.dayanisma_kapasitesi??100)));
    }else if(c.id==="observer"&&(ps.epistemik_alarm||0)>=20){
      tags.append(dtag("Epistemik Alarm %"+ps.epistemik_alarm,(ps.epistemik_alarm||0)>=60?"alert":""));
    }
    if(tags.childNodes.length)pc.append(tags);
    d.append(pc);
  }

  /* 4. İsteğe Bağlı Detay Çekmecesi (Gereksiz metin kalabalığını gizler) */
  const det=node("details","detail");
  det.append(node("summary","","Psikolojik analiz ve kitle profili"));
  const db=node("div","detail-body");
  if(ps.yorum)db.append(node("div","",ps.yorum));
  db.append(node("div","","Kitle tanımı: "+c.tanim));
  if(c.var){
    const m=node("div","metrics");
    const m1=node("div",""),m2=node("div","");
    m1.append(node("div","metric-label","Sıradan Gündem Liyakat: %"+(c.yeterlilik??50)));
    const b1=node("div","bar"),f1=node("div","fill");f1.style.width=(c.yeterlilik||0)+"%";b1.append(f1);m1.append(b1);
    m2.append(node("div","metric-label","Sıradan Gündem Usul: %"+(c.usul??50)));
    const b2=node("div","bar"),f2=node("div","fill");f2.style.width=(c.usul||0)+"%";b2.append(f2);m2.append(b2);
    m.append(m1,m2);db.append(m);
  }
  det.append(db);d.append(det);
  return d;
}

/* 5. ZAMAN ÇİZELGESİ */
function switchDay(gun){
  if(busy||!gun)return;
  setBusy(true,"Gün "+gun+" yükleniyor…");
  fetch("/api/state?gun="+encodeURIComponent(gun)+"&t="+Date.now(),{cache:"no-store"})
    .then(r=>r.json()).then(j=>{
      if(j.ok){
        render(j.state);setConn(true);
        $("#stageSection").scrollIntoView({behavior:"smooth",block:"start"});
      }else toast(j.error||"Gün açılamadı",true);
    })
    .catch(()=>{setConn(false);toast("Sunucuya ulaşılamadı",true);})
    .finally(()=>setBusy(false));
}

function renderTimeline(s){
  const tl=$("#timeline");tl.replaceChildren();
  $("#scenarioBadge").textContent=s.senaryo.var?(s.senaryo.gecmis.length+" gün kayıtlı"):"Kayıt yok";
  if(!s.senaryo.var||!s.senaryo.gecmis.length){
    tl.append(node("p","muted","Senaryo ilerledikçe her günün özeti burada kronolojik olarak birikir; istediğiniz güne tek dokunuşla dönebilirsiniz."));
    return;
  }
  const cur=String(s.senaryo.secili_gun||"");
  s.senaryo.gecmis.slice().reverse().forEach(h=>{
    const active=(String(h.day)===cur);
    const row=node("div","day-row"+(active?" active-day":""));
    const head=node("div","day-row-head");
    head.append(node("span","day-no","Gün "+h.day+(h.dal?" · "+dalEtiketi(h.dal):"")));
    const btn=node("button","mini",active?"Şu an açık":"Bu günü aç");btn.type="button";
    btn.disabled=active;
    btn.addEventListener("click",()=>switchDay(String(h.day)));
    head.append(btn);
    row.append(head,node("div","day-event",h.event||"(gelişme yok)"));
    if(h.genel)row.append(node("div","day-genel",h.genel));
    tl.append(row);
  });
}

function render(s){
  state=s;
  $("#modeBadge").textContent=s.mode==="offline"?"ÇEVRİMDIŞI":"CANLI API";
  $("#modeBadge").className="badge "+(s.mode==="offline"?"offline":"live");
  $("#quotaBadge").textContent="İstek: "+s.api.soru+"/"+s.api.soru_limiti;
  $("#dayBadge").textContent=s.senaryo.var?("Senaryo Gün "+s.senaryo.gun):("Motor Gün "+s.day);

  renderBanner(s);
  renderStage(s);
  renderMindRadar(s);
  renderRail(s);

  const cards=$("#cards");cards.replaceChildren();
  s.kitleler.forEach(c=>cards.append(card(c)));
  renderTimeline(s);

  /* Teknik çekmece */
  const sum=$("#summary");sum.replaceChildren();
  sum.append(
    stat("Motor Günü",s.day),
    stat("Taraf Değişimi",s.dunya.taraf_degisimi),
    stat("İdeoloji Değişimi",s.dunya.ideoloji_degisimi),
    stat("Soru İsteği",s.api.soru+" / "+s.api.soru_limiti),
    stat("Model",s.settings.model||"çevrimdışı"),
    stat("Bekleme",(s.settings.min_interval_seconds||0)+" sn")
  );
  const ev=$("#events");ev.replaceChildren();
  (s.olaylar||[]).slice(-10).reverse().forEach(x=>ev.append(node("span","chip",x.kind)));

  if(Number(s.limitler.toplam))$("#limitTotal").value=s.limitler.toplam;
  if(Number(s.limitler.gunluk))$("#limitDaily").value=s.limitler.gunluk;
  if(s.settings.min_interval_seconds!==undefined&&s.settings.min_interval_seconds!==null)
    $("#beklemeVal").value=s.settings.min_interval_seconds;
  if(Number(s.settings.max_output_tokens))$("#tokenLimitVal").value=s.settings.max_output_tokens;
  if(Number(s.settings.timeout_seconds))$("#timeoutVal").value=s.settings.timeout_seconds;
  if(Number(s.api.soru_limiti))$("#sorLimitVal").value=s.api.soru_limiti;
  if(firstLoad){
    firstLoad=false;
    if(s.son_cikti)showOutput(s.son_cikti);
    if(s.son_komut)$("#lastCmd").textContent="· Son komut: "+s.son_komut;
  }
}

async function load(){
  const cur=$("#aiGun").value;
  try{
    const r=await fetch("/api/state"+(cur?"?gun="+encodeURIComponent(cur):""),{cache:"no-store"});
    const j=await r.json();
    if(j.ok){render(j.state);setConn(true);}else{toast(j.error||"Durum alınamadı",true);setConn(false);}
  }catch(e){setConn(false);toast("Sunucuya ulaşılamadı",true);}
}
async function ping(){
  if(busy)return;
  try{const r=await fetch("/api/health?t="+Date.now(),{cache:"no-store"});const j=await r.json();setConn(!!j.ok);}
  catch(e){setConn(false);}
}
function explainError(j){
  let msg=j.error||"Komut başarısız.";
  if(j.http_status===429){
    const wait=j.retry_after?(" (Önerilen bekleme: "+j.retry_after+" sn)"):"";
    msg+=" — İpucu: Diğer Araçlar altından Bekleme süresini artırıp tekrar deneyin"+wait+".";
  }else if(/token sınırında kesildi|MAX_TOKENS/i.test(msg)){
    msg+=" — İpucu: Diğer Araçlar altından Token sınırını artırabilirsiniz.";
  }
  return msg;
}
async function run(cmd,opts){
  if(busy)return;
  const payload=Object.assign({cmd:cmd},opts||{});
  if(cmd!=="sor"&&cmd!=="devam"&&cmd!=="olay"){
    const cur=$("#aiGun").value;if(cur)payload.gun=cur;
  }
  if(payload.confirm&&!window.confirm("Bu işlem 1 API isteği kullanabilir. Devam?"))return;
  const totalSteps=((cmd==="devam"||cmd==="ilerle")&&Number(payload.count)>1)?Number(payload.count):1;
  stopRequested=false;
  setBusy(true,totalSteps>1?(cmd+" (1 / "+totalSteps+". gün) hazırlanıyor…"):("Yanıt üretiliyor, lütfen bekleyin…"),totalSteps>1);
  try{
    if(totalSteps>1){
      const logs=[];let completed=0;
      for(let i=1;i<=totalSteps;i++){
        if(stopRequested){toast(completed+" gün tamamlandıktan sonra durduruldu",false);break;}
        setBusy(true,cmd+" ("+i+" / "+totalSteps+". gün) üretiliyor…",true);
        const stepPayload=Object.assign({},payload,{count:1});
        delete stepPayload.gun;
        const r=await fetch("/api/command",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(stepPayload)});
        const j=await r.json();setConn(true);
        if(!j.ok){
          if(j.state)render(j.state);
          const em=explainError(j);
          showOutput((logs.length?logs.join("\n\n")+"\n\n":"")+"HATA ("+i+". adım): "+em);
          toast(em,true);return;
        }
        completed=i;logs.push(j.message);render(j.state);showOutput(logs.join("\n\n"));
        $("#lastCmd").textContent="· Son komut: "+cmd+" ("+completed+"/"+totalSteps+")";
      }
      if(!stopRequested){
        toast(completed+" gün tamamlandı",false);
        $("#stageSection").scrollIntoView({behavior:"smooth",block:"start"});
      }
      return;
    }
    const r=await fetch("/api/command",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const j=await r.json();setConn(true);
    if(!j.ok){
      if(j.state)render(j.state);
      const em=explainError(j);
      showOutput("HATA: "+em);toast(em,true);return;
    }
    render(j.state);showOutput(j.message);$("#lastCmd").textContent="· Son komut: "+cmd;
    if(cmd==="sor"||cmd==="devam"||cmd==="olay"){
      if(cmd==="sor"&&$("#newScenarioDetails"))$("#newScenarioDetails").open=false;
      if(cmd==="olay")$("#olayText").value="";
      $("#stageSection").scrollIntoView({behavior:"smooth",block:"start"});
      toast("Gün "+j.state.senaryo.gun+" sahneye yüklendi",false);
    }else{
      toast("Tamamlandı",false);
    }
  }catch(e){setConn(false);showOutput("Bağlantı hatası: "+e);toast("Sunucuya ulaşılamadı",true);}
  finally{setBusy(false,"",false);}
}

const stopBtnEl=$("#stopBtn");
if(stopBtnEl)stopBtnEl.addEventListener("click",()=>{
  stopRequested=true;stopBtnEl.disabled=true;
  $("#status").textContent="Mevcut gün bitince durdurulacak…";
  setTimeout(()=>{stopBtnEl.disabled=false;},600);
});

document.querySelectorAll("[data-cmd]").forEach(b=>b.addEventListener("click",()=>{
  const cmd=b.dataset.cmd,o={};
  if(b.dataset.count)o.count=Number(b.dataset.count);
  if(b.dataset.customCount)o.count=Number($("#devamCount").value||5);
  if(b.dataset.confirm)o.confirm=true;
  if(cmd==="sor"||cmd==="olay"){
    const t=(cmd==="sor"?$("#sorText"):$("#olayText")).value.trim();
    if(!t){toast("Önce bir olay metni yazın",true);return;}
    o.text=t;
  }
  if(cmd==="bekleme")o.seconds=Number($("#beklemeVal").value);
  if(cmd==="limit"){o.total=Number($("#limitTotal").value);o.daily=Number($("#limitDaily").value);}
  if(cmd==="sor-limit")o.count=Number($("#sorLimitVal").value);
  if(cmd==="token-limit"){o.tokens=Number($("#tokenLimitVal").value);o.timeout=Number($("#timeoutVal").value);}
  run(cmd,o);
}));

["sorText","olayText"].forEach(id=>$("#"+id).addEventListener("keydown",e=>{
  if(e.key==="Enter"){
    e.preventDefault();
    document.querySelector('[data-cmd="'+(id==="sorText"?"sor":"olay")+'"]').click();
  }
}));

$("#aiGun").addEventListener("change",e=>switchDay(e.target.value));
$("#prevDayBtn").addEventListener("click",()=>{
  if(!state||!state.senaryo.var)return;
  const gs=Object.keys(state.senaryo.gunler||{}).sort((a,b)=>Number(a)-Number(b));
  const i=gs.indexOf(String(state.senaryo.secili_gun));
  if(i>0)switchDay(gs[i-1]);
});
$("#nextDayBtn").addEventListener("click",()=>{
  if(!state||!state.senaryo.var)return;
  const gs=Object.keys(state.senaryo.gunler||{}).sort((a,b)=>Number(a)-Number(b));
  const i=gs.indexOf(String(state.senaryo.secili_gun));
  if(i>=0&&i<gs.length-1)switchDay(gs[i+1]);
});

$("#refreshBtn").addEventListener("click",()=>{if(!busy)load();});
document.querySelectorAll("[data-fill]").forEach(b=>b.addEventListener("click",()=>{
  const inp=$("#"+b.dataset.fill);if(!inp)return;
  inp.value=b.dataset.val||"";inp.focus();
  toast("Metin kutusuna yerleştirildi");
}));
document.querySelectorAll("[data-copy]").forEach(b=>b.addEventListener("click",()=>{
  copyText($("#"+b.dataset.copy).textContent,"Çıktı");
}));
setInterval(ping,20000);
load();
</script>
</body>
</html>
'''


if __name__ == '__main__':
    main()
