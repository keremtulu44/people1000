"""AI/anlati metnini 6 kitle bolumune ayirir (yalnizca standart kutuphane).

Hem Gemini'nin `sor`/`devam` ciktilari hem cevrimdisi `_offline_scenario_day`
ayni baslik yapisini kullanir:

    **1. Iktidar Yanlilari (power_aligned)**
      ...
    **4. Zenginler ve Sosyal Medya Etki Ekibi (wealthy)**
      ... 3 alt kanat ...
    **Günün Genel Ozeti:** ...

Ayristirici metni degistirmez, yalnizca bolumleri ayirir. Hic baslik
bulunamazsa bos sozluk doner; arayuz bu durumda motor ozetini gosterir.
"""
from __future__ import annotations

import re

GROUPS = ('power_aligned', 'opposition', 'authority',
          'wealthy', 'discontented', 'observer')

KEYWORDS = {
    'power_aligned': ('iktidar yanlıları', 'iktidar yanlilari', 'power_aligned', 'iktidar yanlıları'),
    'opposition': ('muhalifler', 'opposition'),
    'authority': ('yöneticiler', 'yoneticiler', 'otorite', 'authority'),
    'wealthy': ('zenginler', 'sosyal medya', 'wealthy'),
    'discontented': ('hoşnutsuz', 'hosnutsuz', 'discontented'),
    'observer': ('gözlemciler', 'gozlemciler', 'observer'),
}

_NUMBER = re.compile(r'^(\d)\s*[.)\-:]\s*(.+)$')
_GENEL = re.compile(r'g(ü|u)n(ü|u)n genel (ö|o)zeti|^genel (ö|o)zet', re.IGNORECASE)
_RULE = re.compile(r'^[=\-_*#\s]+$')
_MAX_SECTION = 6000


def _clean(line):
    s = line.strip()
    s = re.sub(r'^[•\-\*#_\s]+', '', s)
    s = re.sub(r'[\*#_\s]+$', '', s)
    return s.rstrip(':').strip()


def _group_for(title, digit):
    # Python 'İ'.lower() -> 'i̇' (i + birlesik nokta); anahtar kelimeler
    # duz 'i' ile yazildigi icin birlesik isareti kaldiriyoruz.
    low = title.lower().replace('\u0307', '')
    for gid, words in KEYWORDS.items():
        if any(word in low for word in words):
            return gid
    return None


def _find_headings(lines):
    """(satir_no, gid) ciftleri; keyword eslesmesi, yoksa numara fallback."""
    strong, weak = [], []
    for i, line in enumerate(lines):
        clean = _clean(line)
        if not clean or len(clean) > 200 or _RULE.match(line) or _GENEL.search(clean):
            continue
        m = _NUMBER.match(clean)
        if not m:
            continue
        digit, title = int(m.group(1)), m.group(2)
        gid = _group_for(title, digit)
        if gid:
            strong.append((i, gid))
        elif 1 <= digit <= 6:
            weak.append((i, GROUPS[digit - 1]))
    return strong if len(strong) >= 3 else weak


def _tidy(text):
    kept = [ln.rstrip() for ln in text
            if ln.strip() and not _RULE.match(ln)]
    out, blank = [], False
    for ln in kept:
        ln = re.sub(r'^\*{1,2}\s*', '', ln).rstrip()
        if not ln:
            blank = True
            continue
        if blank and out:
            out.append('')
        blank = False
        out.append(ln)
    return '\n'.join(out).strip()[:_MAX_SECTION]


def parse_kitle_sections(text):
    """Metni 6 kitle bolumune ayirir.

    Donus: {'kitleler': {gid: metin, ...}, 'genel': str}
    Bulunamayan kitleler sozlukte yer almaz.
    """
    if not isinstance(text, str) or not text.strip():
        return {'kitleler': {}, 'genel': ''}
    lines = text.splitlines()
    headings = _find_headings(lines)
    genel_start = next((i for i, ln in enumerate(lines)
                        if _GENEL.search(_clean(ln))), len(lines))

    sections = {}
    for n, (start, gid) in enumerate(headings):
        if gid in sections:
            continue
        end = headings[n + 1][0] if n + 1 < len(headings) else genel_start
        if end <= start:
            continue
        body = _tidy(lines[start + 1:end])
        if body:
            sections[gid] = body

    genel = ''
    if genel_start < len(lines):
        first = lines[genel_start]
        marker = re.split(r'\*{0,2}\s*[:：]\s*', _clean(first), maxsplit=1)
        rest = ([marker[1]] if len(marker) > 1 else []) + lines[genel_start + 1:]
        genel = _tidy(rest)
    return {'kitleler': sections, 'genel': genel}
