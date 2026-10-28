"""AI/anlati metnini 6 kitle bolumune ayirir (yalnizca standart kutuphane).

Hem Gemini'nin `sor`/`devam` ciktilari hem cevrimdisi `_offline_scenario_day`
ayni baslik yapisini kullanir:

    **1. Iktidar Yanlilari (power_aligned)**
      ...
    **4. Zenginler ve Sosyal Medya Etki Ekibi (wealthy)**
      ... 3 alt kanat ...
    **Günün Genel Özeti:** ...

Ayrıştırıcı metnin *içeriğini* değiştirmez; yalnızca markdown işaretlerini
temizler ve bölümleri ayırır. **Karakter sınırıyla kesme yoktur**: kartlara
giden metin, kayıttaki tam metnin ilgili bölümünün tamamıdır. Eski 600
karakterlik özet kayıtları `legacy=True` ile işaretlenir; arayüz bunu açıkça
"ESKİ KAYIT" olarak gösterir, tam metinmiş gibi sunmaz.

Gerçek AI çıktıları biçim açısından değişkendir; bu yüzden şu durumlar da
desteklenir: numarasız kalın başlıklar, `###` başlıklar, `1)` / `4 -` /
`1:` numaralandırmaları, başlıkla aynı satırda başlayan gövde metni, farklı
"genel özet" adları (`Sonuç`, `Genel Değerlendirme`, `Kapanış` ...), giriş
paragrafında geçen "genel özet" ifadesi ve Zenginler bölümündeki 3 alt kanat
başlığı. Kitle kimlikleri/özelikleri bu modülde tanımlanmaz; `ROLE_INFO`
(termux) ve davranış profilleri değiştirilmez.
"""
from __future__ import annotations

import re

GROUPS = ('power_aligned', 'opposition', 'authority',
          'wealthy', 'discontented', 'observer')

# Arama için ASCII'ye indirgenmiş anahtar kelimeler. Kitlelerin tanımı/sırası
# burada değiştirilmez; yalnızca AI'ın kullanabileceği başlık eş anlamlıları.
KEYWORDS = {
    'power_aligned': ('iktidar yanli', 'iktidar destek', 'power aligned',
                      'power_aligned', 'yandas', 'rejim yanli', 'iktidar kutbu'),
    'opposition': ('muhalif', 'muhalefet', 'opposition'),
    'authority': ('yonetici', 'otorite', 'authority', 'burokrasi',
                  'idare', 'kurum yonetimi'),
    'wealthy': ('zengin', 'sosyal medya', 'wealthy', 'sermaye',
                'medya ve sermaye'),
    'discontented': ('hosnutsuz', 'discontented', 'huzursuz', 'emekci',
                     'gecim sikintisi'),
    'observer': ('gozlemci', 'observer', 'izleyen kesim'),
}

_ID_TOKEN = re.compile(
    r'\b(power[ _\-]?aligned|opposition|authority|wealthy|discontented|observer)\b',
    re.IGNORECASE)
# 1. / 1) / 1: / 4 - / (2) / 1 –  gibi numaralandirmalar.
_NUMBER = re.compile(r'^\(?\s*(\d{1,2})\s*[)\].:\-–—]\s*(.+)$')
_BOLD = re.compile(r'^\*{1,2}(.+?)\*{1,2}\s*(.*)$')
_HEADING_MARK = re.compile(r'^\s*(?:#{1,6}\s|>\s|[•\-\*\+]\s+)')
_RULE = re.compile(r'^[=\-_*#`~\s]+$')
_SUBWING = re.compile(
    r'(a kutbu|b kutbu|a yanlisi|b yanlisi|tarafsiz|ticari|a kanadi|b kanadi'
    r'|^\([abc]\)\s|^\*\*\([abc]\))', re.IGNORECASE)
# Normalize edilmiş metinde "genel özet / sonuç / değerlendirme" ailesi.
_SUMMARY = re.compile(
    r'(genel\s*ozet|gunun\s*(?:genel\s*)?ozet|\bozet\b'
    r'|genel\s*degerlendirme|\bdegerlendirme\b|\bsonuc\b|kapanis'
    r'|son\s*soz|genel\s*bakis|genel\s*durum|nihai\s*degerlendirme)',
    re.IGNORECASE)
_SUMMARY_COLON = re.compile(r'^([^:：]{1,70}?)\s*[:：]\s*(.*)$')
_CONSTITUTIONAL_TAG = re.compile(r'\[ANAYASAL_GERIBESLEME\s*:\s*\{.*?\}\s*\]', re.IGNORECASE | re.DOTALL)


def _norm(text):
    """Türkçe karakterleri ASCII'ye indirger (yalnızca başlık eşlemesi için)."""
    s = (text or '').lower().replace('\u0307', '').replace('i\u0307', 'i')
    return ''.join({'ı': 'i', 'ş': 's', 'ğ': 'g', 'ü': 'u', 'ö': 'o',
                    'ç': 'c', 'â': 'a', 'î': 'i', 'û': 'u'}.get(c, c) for c in s)


def _group_for(title, digit=None):
    low = _norm(title)
    # Tabi niteleyicileri ("yoneticilere bagimli") ana baslik kimligi sanma.
    scrubbed = re.sub(r'\b(?:yoneticilere|otoriteye)\s+bagimli\b', ' ', low)
    matches = []
    for gid, words in KEYWORDS.items():
        matched_words = [w for w in words if w in scrubbed]
        if matched_words:
            best_len = max(len(w) for w in matched_words)
            first_pos = min(scrubbed.find(w) for w in matched_words)
            matches.append((gid, best_len, first_pos))
    if not matches:
        for gid, words in KEYWORDS.items():
            if any(word in low for word in words):
                matches.append((gid, 1, 0))
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0][0]
    matched_ids = {m[0] for m in matches}
    if digit and 1 <= digit <= len(GROUPS) and GROUPS[digit - 1] in matched_ids:
        return GROUPS[digit - 1]
    matches.sort(key=lambda item: (-item[1], item[2]))
    return matches[0][0]


def _explicit_id(title):
    match = _ID_TOKEN.search(title or '')
    if not match:
        return None
    token = re.sub(r'[^a-z]', '', _norm(match.group(1)))
    if token.startswith('power'):
        return 'power_aligned'
    return token if token in GROUPS else None


def _strip_line(raw):
    """(temiz_satir, isaretli_mi, madde_isareti_mi) döndürür."""
    s = (raw or '').strip()
    bullet = bool(re.match(r'^\s*[•\-\*\+]\s+\S', s))
    marked = bool(_HEADING_MARK.match(s))
    s = re.sub(r'^\s*#{1,6}\s*', '', s)
    s = re.sub(r'^\s*>\s*', '', s)
    if bullet:
        s = re.sub(r'^\s*[•\-\*\+]\s+', '', s)
    return s.strip(), marked, bullet


def _summary_parts(clean):
    """Genel özet başlığıysa (etiket, aynı satırdaki metin) döndürür."""
    if not clean or len(clean) > 220:
        return None
    colon = _SUMMARY_COLON.match(clean)
    if colon:
        label = colon.group(1).strip().strip('*_# `').strip()
        inline = colon.group(2).strip()
        if label and len(label.split()) <= 7 and _SUMMARY.search(_norm(label)):
            return label, inline
        return None
    # İki nokta üst üste olmayan kısa başlık: "Genel Özet", "Sonuç" ...
    label = clean.strip().strip('*_# `').strip()
    if (len(label) <= 80 and label and not label.endswith(('.', '!', '?', ';', ','))
            and len(label.split()) <= 8 and _SUMMARY.search(_norm(label))):
        return label, ''
    return None


def _classify(raw):
    """Bir satırı sınıflandırır: None / {'kind': 'group'|'summary', ...}."""
    clean, marked, bullet = _strip_line(raw)
    if not clean or _RULE.match(clean) or clean.startswith('```'):
        return None
    bold = _BOLD.match(clean)
    head = (bold.group(1).strip() if bold else clean)
    inline = (bold.group(2).strip() if bold else '')

    # Önce bu satırın bir kitle başlığı olup olmadığına bakılır: "6. Gözlemciler
    # ve Sonuç" gibi başlıklar özet kelimesi içerse de kitle başlığıdır.
    numbered = _NUMBER.match(head)
    digit = int(numbered.group(1)) if numbered else None
    title = numbered.group(2) if numbered else head
    explicit = _explicit_id(head)
    groupish = bool(explicit or _group_for(title, digit) or _group_for(head, digit))

    summary = _summary_parts(head) or (None if bold else _summary_parts(clean))
    if summary and not groupish:
        label, after = summary
        if not after and inline:
            after = inline
        return {'kind': 'summary', 'label': label, 'inline': after}

    # Zenginler bölümündeki 3 alt kanat, yeni bir kitle başlığı değildir.
    probe = _norm(head)
    if _SUBWING.search(probe) and not explicit:
        return None

    # Başlıktan hemen sonra gelen metin gövdenin ilk satırıdır.
    gid = explicit
    by_keyword = False
    if not gid:
        gid = _group_for(title, digit) or _group_for(head, digit)
        by_keyword = bool(gid)

    confidence = 'strong'
    if not gid:
        if digit and 1 <= digit <= 6:
            gid, confidence = GROUPS[digit - 1], 'weak'
        else:
            return None
    elif by_keyword and not numbered:
        # Numarasız başlıklar kısa ve cümle biçiminde olmamalı. Aksi halde
        # gövdedeki "yöneticiler..." gibi kelimeler yeni bölüm başlatır ve
        # o kartın metni yanlış karta bağlanır / boş kalır.
        check = head.rstrip(':：').strip()
        if (len(check) > 60 or len(check.split()) > 7
                or check.endswith(('.', '!', '?', ';', ','))):
            return None
    if not numbered and len(head) > 200:
        return None
    return {'kind': 'group', 'gid': gid, 'digit': digit,
            'confidence': confidence, 'inline': inline, 'head': head,
            'marked': marked or bullet}


def _tidy(lines):
    """Markdown işaretlerini temizler; paragrafları korur; METNİ KESMEZ."""
    out, blank = [], False
    for raw in lines:
        s = (raw or '').rstrip()
        stripped = s.strip()
        if not stripped or _RULE.match(stripped) or stripped.startswith('```'):
            blank = True
            continue
        s = re.sub(r'^\s{0,3}#{1,6}\s*', '', s)
        s = re.sub(r'^\s*>\s*', '', s)
        s = s.replace('**', '').replace('__', '').replace('`', '')
        bullet = re.match(r'^\s*[•\-\*\+]\s+(.*)$', s)
        if bullet:
            s = '• ' + bullet.group(1)
        s = s.strip()
        if not s:
            blank = True
            continue
        if blank and out:
            out.append('')
        blank = False
        out.append(s)
    # Birden fazla boş satırı tek paragraf ayırıcısına indir.
    result, was_blank = [], False
    for line in out:
        if line == '':
            was_blank = True
            continue
        if was_blank and result:
            result.append('')
        was_blank = False
        result.append(line)
    return '\n'.join(result).strip()


def _looks_cut(text):
    """Güvenli sınır: metin cümle ortasında bitiyorsa uyarı bayrağı."""
    tail = (text or '').rstrip().rstrip('*_#= -').rstrip()
    if not tail:
        return False
    return tail[-1] not in '.!?…:;)]»”\'"'


def analyze_scenario(text, legacy=False):
    """Tam tanılama ile 6 kitle bölümü.

    Donus::

        {'kitleler': {gid: metin}, 'genel': str, 'ortak': str,
         'tam_metin': str, 'bagli': int, 'toplam': 6, 'eksik': [gid, ...],
         'baslik': int, 'kesik': bool, 'yarim': bool, 'karakter': int}

    `legacy=True`: kayıtta tam metin yok, yalnızca 600 karakterlik eski özet
    var. Metin yine gösterilir ama arayüz bunu eksik/yarım olarak işaretler.
    """
    empty = {'kitleler': {}, 'genel': '', 'ortak': '', 'tam_metin': '',
             'bagli': 0, 'toplam': len(GROUPS), 'eksik': list(GROUPS),
             'baslik': 0, 'kesik': bool(legacy), 'yarim': False,
             'karakter': 0}
    if not isinstance(text, str) or not text.strip():
        return empty
    clean_text = _CONSTITUTIONAL_TAG.sub('', text)
    lines = clean_text.splitlines()
    items = [{'raw': ln, 'cand': _classify(ln)} for ln in lines]

    group_cands = [(i, it['cand']) for i, it in enumerate(items)
                   if it['cand'] and it['cand']['kind'] == 'group']
    summary_cands = [i for i, it in enumerate(items)
                     if it['cand'] and it['cand']['kind'] == 'summary']
    strong = [(i, c) for i, c in group_cands if c['confidence'] == 'strong']
    if len(strong) >= 3:
        chosen = list(strong)
        covered = {c['gid'] for _, c in chosen}
        # Numaralı ama isimsiz başlıklarla boş kalan kartları da bağla.
        for i, c in group_cands:
            if c['confidence'] == 'weak' and c['gid'] not in covered:
                covered.add(c['gid'])
                chosen.append((i, c))
    else:
        chosen = list(group_cands)
    chosen.sort(key=lambda x: x[0])

    # Aynı kitle için tekrar eden başlık sınır oluşturmaz; gövde içinde kalır.
    boundaries, seen = [], set()
    for i, c in chosen:
        if c['gid'] in seen:
            continue
        seen.add(c['gid'])
        boundaries.append((i, c))
    last_start = boundaries[-1][0] if boundaries else -1
    summary_idx = next((i for i in summary_cands if i > last_start), None)
    if not boundaries and summary_cands:
        summary_idx = summary_cands[0]

    kitleler = {}
    for n, (start, cand) in enumerate(boundaries):
        end = boundaries[n + 1][0] if n + 1 < len(boundaries) else len(lines)
        if summary_idx is not None and start < summary_idx < end:
            end = summary_idx
        body = []
        if cand.get('inline'):
            body.append(cand['inline'])
        for j in range(start + 1, end):
            other = items[j]['cand']
            if other and other['kind'] == 'group':
                # Tekrar eden başlık satırı: yalnızca içindeki metni al.
                if other.get('inline'):
                    body.append(other['inline'])
                continue
            if other and other['kind'] == 'summary' and j == summary_idx:
                continue
            body.append(items[j]['raw'])
        cleaned = _tidy(body)
        if cleaned:
            kitleler.setdefault(cand['gid'], cleaned)

    genel = ''
    if summary_idx is not None:
        gen_lines = []
        inline = items[summary_idx]['cand'].get('inline')
        if inline:
            gen_lines.append(inline)
        for j in range(summary_idx + 1, len(lines)):
            other = items[j]['cand']
            if other and other['kind'] == 'group':
                break
            if other and other['kind'] == 'summary':
                if other.get('inline'):
                    gen_lines.append(other['inline'])
                continue
            gen_lines.append(items[j]['raw'])
        genel = _tidy(gen_lines)

    ortak_end = boundaries[0][0] if boundaries else (
        summary_idx if summary_idx is not None else len(lines))
    ortak = _tidy([items[j]['raw'] for j in range(0, ortak_end)
                   if not (items[j]['cand'] and items[j]['cand']['kind'] == 'summary')])

    return {
        'kitleler': kitleler, 'genel': genel, 'ortak': ortak,
        'tam_metin': text, 'bagli': len(kitleler), 'toplam': len(GROUPS),
        'eksik': [g for g in GROUPS if g not in kitleler],
        'baslik': len(boundaries),
        # "kesik" yalnızca eski 600 karakterlik kayıtlar içindir. Başlık
        # bulunamayan tam metin "kırpılmış" değil, "ayrıştırılamamış"tır.
        'kesik': bool(legacy),
        'yarim': _looks_cut(text) and not genel,
        'karakter': len(text),
    }


def parse_kitle_sections(text):
    """Geriye uyumlu sade arayüz: {'kitleler': {gid: metin}, 'genel': str}.

    Başlık bulunamazsa tam olarak `{'kitleler': {}, 'genel': ''}` döner.
    """
    if not isinstance(text, str) or not text.strip():
        return {'kitleler': {}, 'genel': ''}
    analysed = analyze_scenario(text)
    return {'kitleler': analysed['kitleler'], 'genel': analysed['genel']}
