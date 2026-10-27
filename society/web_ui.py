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
from . import termux
from .scenario_text import parse_kitle_sections

MAX_TEXT = 2000
MAX_DAYS = 30
HISTORY_LIMIT = 400
COMMANDS = frozenset({
    'gun', 'ilerle', 'ozet', 'rapor', 'sor', 'devam', 'olay', 'ayar', 'kaydet',
    'yardim', 'baglanti', 'modeller', 'uretim-test', 'bekleme', 'limit', 'sor-limit'})


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
        self.history_path = self.state_path.with_suffix('.history.json')
        self.history = self._load_history()
        if not self.history:
            # Baslangic anlik goruntusu: ilk gunun "dune gore" farki hesaplansin.
            self.history = [{'day': _day(sim), 'kitleler': _metrics_snapshot(termux.report(sim))}]
            self._save_history()
        self.last_output = ''
        self.last_command = ''

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

    def redact(self, text):
        key = os.environ.get(getattr(self.advisor, 'key_env', ''), '') or \
              os.environ.get('PEOPLE1000_API_KEY', '')
        return text.replace(key, '[REDACTED]') if key and isinstance(text, str) else text

    def save(self):
        self.sim.save(self.state_path)


def build_state(pilot, secili_gun=None):
    """GET /api/state icin tum ekran verisi. Anahtar icermez.

    secili_gun: kartlarda gosterilecek senaryo gunu; verilmezse en son gun.
    """
    with pilot.lock:
        r = termux.report(pilot.sim)
        day = _day(pilot.sim)
        current = {'day': day, 'kitleler': _metrics_snapshot(r)}
        if pilot.history and pilot.history[-1]['day'] == day:
            pilot.history[-1] = current
        else:
            pilot.history.append(current)
            pilot._save_history()
        pilot.history = pilot.history[-HISTORY_LIMIT:]
        previous = pilot.history[-2]['kitleler'] if len(pilot.history) > 1 else {}

        wm = r.get('world_metrics', {})
        rev = r.get('reviews', {})
        statuses = rev.get('statuses', {})
        meta = pilot.sim.protocol['termux_pilot']
        diag = r.get('diagnostics', {})
        q = r.get('operator_questions', {})
        chain = meta.get('scenario_chain')
        scenario = {'var': bool(chain), 'ilk_olay': '', 'gun': 0, 'gecmis': [],
                    'gunler': {}, 'secili_gun': None, 'ai_var': False}
        if chain:
            gunler = {}
            gecmis = []
            for h in chain.get('history', []):
                # Eski kayitlarda full_text yoksa 600 karakterlik ozet kullanilir.
                tam = h.get('full_text') or h.get('summary') or ''
                parsed = parse_kitle_sections(tam)
                d = h.get('day')
                gunler[str(d)] = {
                    'day': d, 'event': h.get('event', ''),
                    'sinir': h.get('allowed_extremes', ''),
                    'metin': tam, 'genel': parsed['genel'],
                    'kitleler': parsed['kitleler'],
                    'kesik': 'full_text' not in h,
                }
                gecmis.append(gunler[str(d)])
            son_gun = str(chain.get('day', 0)) if gunler else None
            if secili_gun is not None and str(secili_gun) in gunler:
                son_gun = str(secili_gun)
            elif son_gun not in gunler and gecmis:
                son_gun = str(gecmis[-1]['day'])
            scenario = {'var': True, 'ilk_olay': chain.get('initial_event', ''),
                        'gun': chain.get('day', 0), 'gecmis': gecmis,
                        'gunler': gunler, 'secili_gun': son_gun,
                        'ai_var': any(g['kitleler'] for g in gunler.values())}
        # Kartlara atanacak AI metni: secili gunun 6 kitlesi.
        secili = scenario['gunler'].get(scenario['secili_gun'], {}) if scenario['var'] else {}
        ai_kitleler = secili.get('kitleler', {}) if isinstance(secili, dict) else {}
        events = [{'time': e.get('time'), 'kind': e.get('kind', '')}
                  for e in pilot.sim.log[-12:]]
        settings = termux.settings(pilot.advisor)
        cards = kitle_cards(r, previous)
        for c in cards:
            c['ai_metni'] = ai_kitleler.get(c['id'], '')
            c['ai_gun'] = secili.get('day') if c['ai_metni'] else None
            c['ai_kesik'] = bool(secili.get('kesik')) if c['ai_metni'] else False
        return _json_safe({
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
            pilot.save(); out = 'Kaydedildi.'
        elif cmd == 'sor':
            question = _text(payload)
            if isinstance(advisor, OpenAICompatibleAdvisor) and meta['question_attempts'] >= meta['question_limit']:
                meta['question_limit'] = meta['question_attempts'] + 1
            try:
                out = termux.ask_operator(sim, question, advisor)
            finally:
                pilot.save()
        elif cmd == 'devam':
            count = _int(payload, 'count', 1, MAX_DAYS, 1)
            try:
                out = '\n\n'.join(termux.advance_scenario_days(
                    sim, advisor, count, checkpoint=pilot.state_path))
            finally:
                pilot.save()
        elif cmd == 'olay':
            custom = _text(payload)
            try:
                out = '\n\n'.join(termux.advance_scenario_days(
                    sim, advisor, 1, checkpoint=pilot.state_path, custom_event=custom))
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

        pilot.last_output = pilot.redact(str(out))[:20000]
        pilot.last_command = cmd
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
            return self._json(400, {
                'ok': False, 'error': self.server.pilot.redact(str(exc)) or 'Komut basarisiz.'})

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
<meta name="theme-color" content="#0d1117">
<title>People1000 — Pilot</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--card:#1b2230;--line:#2b3546;--txt:#e6edf3;
--muted:#8b98a9;--accent:#58a6ff;--good:#3fb950;--bad:#f85149;--warn:#d29922;
--radius:14px}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--txt);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
font-size:15px;line-height:1.45;-webkit-text-size-adjust:100%}
body{padding-bottom:max(28px,env(safe-area-inset-bottom))}
.topbar{position:sticky;top:0;z-index:10;display:flex;align-items:center;justify-content:space-between;
gap:10px;padding:12px 16px;background:rgba(13,17,23,.94);backdrop-filter:blur(8px);
border-bottom:1px solid var(--line)}
.brand{font-weight:800;letter-spacing:.06em;font-size:17px}
.brand span{color:var(--accent)}
.badges{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.badge{font-size:12px;padding:5px 10px;border-radius:999px;background:var(--card);
border:1px solid var(--line);color:var(--muted);white-space:nowrap}
.badge.strong{color:var(--txt);font-weight:700}
.badge.live{color:var(--good);border-color:#1d4429}
.badge.offline{color:var(--warn);border-color:#4a3a12}
button,input,summary,a.btn{font:inherit}
button{cursor:pointer;touch-action:manipulation}
.icon{background:var(--card);border:1px solid var(--line);color:var(--txt);
width:38px;height:38px;border-radius:10px;font-size:18px}
main{max-width:1180px;margin:0 auto;padding:16px}
.section{margin-top:22px}
.section-head{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:10px}
h2{font-size:16px;margin:0;letter-spacing:.02em}
.muted{color:var(--muted);font-size:12px}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px 12px}
.stat .k{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.stat .v{font-size:18px;font-weight:700;margin-top:3px;word-break:break-word}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
padding:14px;display:flex;flex-direction:column;gap:9px;min-height:210px}
.card.empty{opacity:.68;border-style:dashed}
.card-head{display:flex;align-items:center;gap:9px}
.num{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;
border-radius:8px;background:#22304a;color:var(--accent);font-weight:800;font-size:13px;flex:none}
.card h3{margin:0;font-size:15px}
.action{font-weight:700;font-size:14px;color:var(--accent)}
.expr{font-size:12px;color:var(--muted);margin-top:-6px}
.metrics{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.metric-label{font-size:11px;color:var(--muted);margin-bottom:4px}
.bar{height:7px;border-radius:99px;background:#0d1117;border:1px solid var(--line);overflow:hidden}
.fill{height:100%;background:linear-gradient(90deg,#1f6feb,#58a6ff);border-radius:99px}
.delta{font-size:11px;margin-top:4px}
.delta.up{color:var(--good)}.delta.down{color:var(--bad)}
.summary-line{font-size:13px;color:#cdd7e3;margin:0;flex:1}
.detail{border-top:1px solid var(--line);padding-top:8px;font-size:12px;color:var(--muted)}
.detail summary{cursor:pointer;color:var(--accent);font-weight:600;padding:4px 0}
.detail p{margin:7px 0}
.note{background:#11161f;border-left:3px solid var(--warn);padding:7px 9px;border-radius:6px;
white-space:pre-wrap;word-break:break-word}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:12px}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:9px}
.row:last-child{margin-bottom:0}
.btn{background:#21283a;color:var(--txt);border:1px solid var(--line);border-radius:10px;
padding:10px 14px;min-height:42px;font-weight:600;text-decoration:none;display:inline-flex;
align-items:center;justify-content:center}
.btn:hover{border-color:var(--accent)}
.btn:disabled{opacity:.45;cursor:wait}
.btn.primary{background:#1f6feb;border-color:#1f6feb;color:#fff}
.btn.accent{background:#173a5e;border-color:#2b6cb0}
.btn.warn{border-color:#5a4415;color:#e3b341}
input{flex:1 1 190px;min-width:0;min-height:42px;background:#0d1117;color:var(--txt);
border:1px solid var(--line);border-radius:10px;padding:9px 11px}
input[type=number]{flex:0 0 92px;min-width:80px}
.advanced summary{cursor:pointer;color:var(--muted);font-size:13px;padding:6px 0}
.timeline{display:flex;flex-direction:column;gap:9px}
.day{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:11px 13px}
.day-no{font-size:11px;color:var(--accent);font-weight:800;letter-spacing:.06em}
.day-event{font-weight:600;margin:3px 0 6px}
.day-sum{font-size:13px;color:#cdd7e3;white-space:pre-wrap;word-break:break-word}
.day-limit{font-size:11px;color:var(--warn);margin-top:6px}
.day-pick{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.day-pick label{font-size:12px;color:var(--muted)}
.day-pick select{background:#0d1117;color:var(--txt);border:1px solid var(--line);
border-radius:9px;min-height:36px;padding:6px 9px;font:inherit;font-size:13px}
.ai{background:#101a2b;border:1px solid #24406b;border-left:3px solid var(--accent);
border-radius:10px;padding:10px 11px;white-space:pre-wrap;word-break:break-word;
font-size:13px;line-height:1.55;max-height:340px;overflow:auto}
.ai-head{display:flex;justify-content:space-between;gap:8px;align-items:center;
font-size:10.5px;letter-spacing:.05em;color:var(--accent);font-weight:800;
text-transform:uppercase;margin-bottom:5px}
.ai-yok{background:#151a22;border:1px dashed var(--line);border-radius:10px;
padding:10px 11px;font-size:12px;color:var(--muted)}
.ai-kesik{color:var(--warn)}
.motor{font-size:12px;color:var(--muted);border-top:1px dashed var(--line);padding-top:7px}
.motor b{color:#c6d0dc;font-weight:700}
.output{background:#080b10;border:1px solid var(--line);border-radius:12px;padding:13px;
font-size:12.5px;line-height:1.55;white-space:pre-wrap;word-break:break-word;
overflow:auto;max-height:460px;margin:0;color:#cdd7e3}
.events{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.chip{font-size:11px;background:#11161f;border:1px solid var(--line);border-radius:999px;
padding:4px 9px;color:var(--muted)}
footer{margin-top:26px;padding:14px 4px;color:var(--muted);font-size:11.5px;
border-top:1px solid var(--line)}
#status{font-size:12px;color:var(--warn);min-height:17px;margin-top:9px}
.toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(20px);
background:#21283a;border:1px solid var(--line);color:var(--txt);padding:10px 16px;
border-radius:10px;font-size:13px;opacity:0;pointer-events:none;transition:.2s;z-index:20;
max-width:90vw;text-align:center}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.toast.err{border-color:var(--bad)}
@media(max-width:600px){
 main{padding:12px}.cards{grid-template-columns:1fr}.card{min-height:0}
 .metrics{grid-template-columns:1fr 1fr}.btn{flex:1 1 auto}.row{gap:7px}
 .topbar{padding:10px 12px}}
</style>
</head>
<body>
<header class="topbar">
  <div class="brand">PEOPLE<span>1000</span></div>
  <div class="badges">
    <span id="modeBadge" class="badge">—</span>
    <span id="dayBadge" class="badge strong">Gün —</span>
    <button id="refreshBtn" class="icon" title="Yenile" aria-label="Yenile">↻</button>
  </div>
</header>
<main>
  <section class="summary" id="summary"></section>

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
    <div class="section-head"><h2>Komutlar</h2><span class="muted">Canlı istekler kotadan düşer; otomatik tekrar yok</span></div>
    <div class="panel">
      <div class="row">
        <button data-cmd="gun" class="btn primary">Gün ilerlet</button>
        <button data-cmd="ilerle" data-count="3" class="btn">İlerle 3</button>
        <button data-cmd="ozet" class="btn">Özet</button>
        <button data-cmd="rapor" class="btn">Rapor</button>
        <button data-cmd="ayar" class="btn">Ayar</button>
        <button data-cmd="kaydet" class="btn">Kaydet</button>
      </div>
      <div class="row">
        <input id="sorText" maxlength="2000" placeholder="Yeni olay / senaryo (Gün 1)">
        <button data-cmd="sor" class="btn accent">Başlat</button>
      </div>
      <div class="row">
        <button data-cmd="devam" data-count="1" class="btn">Devam 1</button>
        <button data-cmd="devam" data-count="3" class="btn">Devam 3</button>
        <input id="olayText" maxlength="2000" placeholder="Zincire yeni gelişme ekle">
        <button data-cmd="olay" class="btn">Olay ekle</button>
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
          <input id="sorLimitVal" type="number" min="1" max="200" value="5" aria-label="Soru limiti">
          <button data-cmd="sor-limit" class="btn">Soru limiti</button>
          <a class="btn" href="/api/export" download>Raporu indir (JSON)</a>
          <button data-cmd="yardim" class="btn">Yardım</button>
        </div>
      </details>
      <div id="status"></div>
    </div>
  </section>

  <section class="section">
    <div class="section-head"><h2>Senaryo zinciri</h2><span id="scenarioBadge" class="muted"></span></div>
    <div class="timeline" id="timeline"></div>
  </section>

  <section class="section">
    <div class="section-head"><h2>Son çıktı</h2><span id="lastCmd" class="muted"></span></div>
    <pre id="output" class="output">Henüz komut çalıştırılmadı.</pre>
    <div class="events" id="events"></div>
  </section>

  <footer>
    Bu arayüz yalnızca bu cihazdaki sunucuya bağlanır. API anahtarı sayfaya gelmez;
    tüm istekler sunucudan Gemini'ye gider. Web adresine taşırken anahtarı sunucuda tutmaya devam et.
  </footer>
</main>
<div id="toast" class="toast"></div>
<script>
"use strict";
const $=s=>document.querySelector(s);
let state=null,busy=false,firstLoad=true;
function node(tag,cls,text){const e=document.createElement(tag);
  if(cls)e.className=cls; if(text!==undefined&&text!==null)e.textContent=String(text);return e;}
function toast(msg,err){const t=$("#toast");t.textContent=msg;t.className="toast show"+(err?" err":"");
  setTimeout(()=>{t.className="toast";},2600);}
function showOutput(t){$("#output").textContent=t||"(çıktı yok)";}
function setBusy(v,msg){busy=v;document.querySelectorAll("[data-cmd]").forEach(b=>b.disabled=v);
  $("#status").textContent=v?(msg||"Çalışıyor…"):"";}
function stat(k,v){const d=node("div","stat");d.append(node("div","k",k),node("div","v",v));return d;}
function metric(label,val,delta){
  const w=node("div","metric");
  w.append(node("div","metric-label",label+"  "+(val===null||val===undefined?"—":val+"%")));
  const bar=node("div","bar"),fill=node("div","fill");
  fill.style.width=(val===null||val===undefined?0:Math.max(0,Math.min(100,val)))+"%";
  bar.append(fill);w.append(bar);
  if(delta!==null&&delta!==undefined&&delta!==0)
    w.append(node("div","delta "+(delta>0?"up":"down"),
      (delta>0?"▲ +":"▼ ")+delta+" puan (düne göre)"));
  return w;}
function card(c){
  const d=node("article","card"+(c.var?"":" empty"));
  const head=node("div","card-head");
  head.append(node("span","num",c.sira),node("h3","",c.ad));d.append(head);
  d.append(node("div","action",c.eylem));
  if(c.ifade)d.append(node("div","expr",c.ifade));
  const m=node("div","metrics");
  m.append(metric("Yeterlilik",c.yeterlilik,c.fark_yeterlilik),
           metric("Usul",c.usul,c.fark_usul));d.append(m);
  // Yapay zekanin bu kitleye ait metni — asil bosluk burasi.
  const ai=node("div",c.ai_metni?"ai":"ai-yok");
  if(c.ai_metni){
    const h=node("div","ai-head");
    h.append(node("span","","AI ANLATIMI · GÜN "+(c.ai_gun??"—")),
      node("span",c.ai_kesik?"ai-kesik":"",c.ai_kesik?"ESKİ KAYIT":"TAM METİN"));
    ai.append(h,node("div","",c.ai_metni));
  }else{
    ai.textContent="AI anlatımı yok. Bu alan ‘Başlat’, ‘Devam’ veya ‘Olay ekle’ ile üretilen metinle dolar.";
  }
  d.append(ai);
  d.append(node("div","motor","Motor özeti: "+c.ozet));
  const det=node("details","detail");
  det.append(node("summary","",c.model_notu?"Rol tanımı + model notu":"Rol tanımı"));
  det.append(node("p","",c.tanim));
  if(c.model_notu)det.append(node("p","note","Model notu: "+c.model_notu));
  d.append(det);return d;}
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
  const cards=$("#cards");cards.replaceChildren();
  s.kitleler.forEach(c=>cards.append(card(c)));
  // Anlatim gunu secici: ayni zincirin her gunu icin 6 karti yeniden doldurur.
  const sel=$("#aiGun");sel.replaceChildren();
  const gunler=Object.keys(s.senaryo.gunler||{});
  gunler.forEach(g=>{const o=node("option","","Gün "+g);o.value=g;sel.append(o);});
  sel.disabled=!gunler.length;
  if(s.senaryo.secili_gun)sel.value=String(s.senaryo.secili_gun);
  const sec=s.senaryo.gunler?.[s.senaryo.secili_gun];
  $("#aiKaynak").textContent=!s.senaryo.ai_var?"AI metni bekleniyor":
    (sec&&sec.kesik?"(eski kayıt: kırpılmış)":"(tam metin)");
  const tl=$("#timeline");tl.replaceChildren();
  $("#scenarioBadge").textContent=s.senaryo.var?
    ("Gün "+s.senaryo.gun+" · "+s.senaryo.gecmis.length+" adım"):"Henüz zincir yok";
  if(!s.senaryo.var){
    tl.append(node("p","muted","Yukarıya bir olay yazıp “Başlat” de; sonra “Devam” ile zinciri ilerlet."));
  }else{
    const ilk=node("div","day");
    ilk.append(node("div","day-no","BAŞLANGIÇ"),node("div","day-event",s.senaryo.ilk_olay));tl.append(ilk);
    s.senaryo.gecmis.forEach(h=>{
      const e=node("div","day");
      e.append(node("div","day-no","Gün "+h.day),node("div","day-event",h.event));
      const det=node("details","detail");
      det.append(node("summary","","Günün tam metni"+(h.kesik?" (eski kayıt: kırpılmış)":"")));
      det.append(node("div","day-sum",h.metin||h.summary||""));
      if(h.genel)det.append(node("div","day-limit","Genel özet: "+h.genel));
      e.append(det);
      if(h.sinir)e.append(node("div","day-limit","Sınır: "+h.sinir));
      tl.append(e);});
  }
  const ev=$("#events");ev.replaceChildren();
  (s.olaylar||[]).slice(-10).reverse().forEach(x=>ev.append(node("span","chip",x.kind)));
  if(Number(s.limitler.toplam))$("#limitTotal").value=s.limitler.toplam;
  if(Number(s.limitler.gunluk))$("#limitDaily").value=s.limitler.gunluk;
  if(s.settings.min_interval_seconds!==undefined&&s.settings.min_interval_seconds!==null)
    $("#beklemeVal").value=s.settings.min_interval_seconds;
  if(Number(s.api.soru_limiti))$("#sorLimitVal").value=s.api.soru_limiti;
  if(firstLoad){
    firstLoad=false;
    if(s.son_cikti)showOutput(s.son_cikti);
    if(s.son_komut)$("#lastCmd").textContent="Son komut: "+s.son_komut;
  }
}
async function load(){
  const cur=$("#aiGun").value;
  try{const r=await fetch("/api/state"+(cur?"?gun="+encodeURIComponent(cur):""),
    {cache:"no-store"});const j=await r.json();
    if(j.ok)render(j.state);else toast(j.error||"Durum alınamadı",true);
  }catch(e){toast("Sunucuya ulaşılamadı",true);}}
async function run(cmd,opts){
  if(busy)return;
  const payload=Object.assign({cmd:cmd},opts||{});
  const cur=$("#aiGun").value;
  if(cur)payload.gun=cur;
  if(payload.confirm&&!window.confirm("Bu işlem 1 API isteği / kota kullanabilir. Devam?"))return;
  setBusy(true,cmd+" çalışıyor…");
  try{
    const r=await fetch("/api/command",{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const j=await r.json();
    if(!j.ok){showOutput("HATA: "+(j.error||"Komut başarısız."));toast(j.error||"Hata",true);return;}
    render(j.state);showOutput(j.message);$("#lastCmd").textContent="Son komut: "+cmd;
    toast("Tamam",false);
  }catch(e){showOutput("Bağlantı hatası: "+e);toast("Sunucuya ulaşılamadı",true);}
  finally{setBusy(false);}}
document.querySelectorAll("[data-cmd]").forEach(b=>b.addEventListener("click",()=>{
  const cmd=b.dataset.cmd,o={};
  if(b.dataset.count)o.count=Number(b.dataset.count);
  if(b.dataset.confirm)o.confirm=true;
  if(cmd==="sor"||cmd==="olay"){
    const t=(cmd==="sor"?$("#sorText"):$("#olayText")).value.trim();
    if(!t){toast("Önce bir metin yaz",true);return;}o.text=t;}
  if(cmd==="bekleme")o.seconds=Number($("#beklemeVal").value);
  if(cmd==="limit"){o.total=Number($("#limitTotal").value);o.daily=Number($("#limitDaily").value);}
  if(cmd==="sor-limit")o.count=Number($("#sorLimitVal").value);
  run(cmd,o);}));
["sorText","olayText"].forEach(id=>$("#"+id).addEventListener("keydown",e=>{
  if(e.key==="Enter"){e.preventDefault();
    document.querySelector('[data-cmd="'+(id==="sorText"?"sor":"olay")+'"]').click();}}));
$("#aiGun").addEventListener("change",e=>{
  if(busy)return;
  const gun=e.target.value;
  setBusy(true,"Gün "+gun+" yükleniyor…");
  fetch("/api/state?gun="+encodeURIComponent(gun)+"&t="+Date.now(),{cache:"no-store"})
    .then(r=>r.json()).then(j=>{if(j.ok){render(j.state);toast("Gün "+gun+" gösteriliyor",false);}
      else toast(j.error||"Gün açılamadı",true);})
    .catch(()=>toast("Sunucuya ulaşılamadı",true))
    .finally(()=>setBusy(false));});
$("#refreshBtn").addEventListener("click",()=>{if(!busy)load();});
load();
</script>
</body>
</html>
'''


if __name__ == '__main__':
    main()
