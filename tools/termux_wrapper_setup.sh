#!/usr/bin/env bash
# People1000 — ApiWrapper (OpenAI uyumlu) kurulumu, Termux icin.
#
#   cd "$HOME/people1000"
#   git pull --ff-only origin arena/8aad5b34-people1000   # veya main
#   bash tools/termux_wrapper_setup.sh              # adres + anahtar sorar, yazar, dogrular
#   bash tools/termux_wrapper_setup.sh --new-key    # anahtari zorla yeniden sorar
#   bash tools/termux_wrapper_setup.sh --print      # yalnizca kayitli ayari gosterir
#
# Adres ve anahtar repo DISINDA, 600 izinli dosyada tutulur:
#   $HOME/.config/people1000/wrapper.env
# Anahtar ekrana yazilmaz; bu script HIC ag istegi gondermez (pip install disinda).
# Ayrinti: docs/termux-apiwrapper.md
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
CONF_DIR="$HOME/.config/people1000"
CONF="$CONF_DIR/wrapper.env"

command -v python3 >/dev/null 2>&1 || { echo "Python yok. Termux'ta: pkg install python git nano -y"; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' || { echo "Python 3.11+ gerekli."; exit 1; }
[ -f "$REPO/society/wrapper_api.py" ] || { echo "wrapper_api.py yok. once: git pull --ff-only origin main"; exit 1; }

# 0) --print: yalnizca kayitli ayari gosterir; venv/pip calistirmaz.
if [ "${1:-}" = "--print" ]; then
  if [ ! -f "$CONF" ]; then echo "Kayitli ayar yok: $CONF"; exit 1; fi
  set -a; . "$CONF"; set +a
  exec python3 -m society.wrapper_api --check
fi

# 1) Sanal ortam ve paket (varsa yeniden kurmaz).
if [ ! -d .venv ]; then python3 -m venv .venv; fi
# shellcheck source=/dev/null
source .venv/bin/activate
if [ ! -x .venv/bin/people1000 ]; then
  echo "Paket kuruluyor (ilk kurulum)..."
  python -m pip install -e . --disable-pip-version-check
fi

OLD_URL=""; OLD_KEY=""
if [ -f "$CONF" ]; then
  OLD_URL="$(. "$CONF" >/dev/null 2>&1; printf '%s' "${WRAPPER_URL:-}")"
  OLD_KEY="$(. "$CONF" >/dev/null 2>&1; printf '%s' "${WRAPPER_API_KEY:-}")"
fi

echo "ApiWrapper ayari. Adres gizli degil; anahtar ekranda gorunmez."
if [ -n "$OLD_URL" ]; then
  read -r -p "WRAPPER_URL [Enter = kayitli: $OLD_URL]: " URL || true
else
  read -r -p "WRAPPER_URL (or. https://api-wrapper.example.com): " URL || true
fi
URL="${URL:-$OLD_URL}"
[ -n "$URL" ] || { echo "Adres bos; ayar dosyasina dokunulmadi."; exit 1; }

# 2) Adresi ag istegi atmadan dogrula ve /v1 bicimini goster.
if ! NORMALIZED="$(python -c 'import sys
from society.wrapper_api import normalize_base_url
print(normalize_base_url(sys.argv[1]))' "$URL" 2>/dev/null)"; then
  echo "Adres gecersiz. https ile baslayan tam adres girin (sonundaki / onemsiz)."
  exit 1
fi
echo "Kullanilacak taban adres: $NORMALIZED"

# 3) Anahtar: kayitli varsa sor; bos giris kayitli dosyayi bozmaz.
if [ -n "$OLD_KEY" ] && [ "${1:-}" != "--new-key" ]; then
  read -r -p "Kayitli anahtar kullanilsin mi? [E=evet / h=yeni gir] " KEEP || true
  case "${KEEP:-}" in
    h|H) OLD_KEY="" ;;
    *) echo "Mevcut anahtar korunuyor." ;;
  esac
fi
if [ -n "$OLD_KEY" ]; then
  KEY="$OLD_KEY"
else
  read -r -s -p "WRAPPER_API_KEY (ekranda gorunmez): " KEY || true
  printf '\n'
  [ -n "${KEY:-}" ] || { echo "Anahtar bos; ayar dosyasina dokunulmadi."; exit 1; }
fi

# 4) Ayari atomik yaz: repo disi, 600 izin, anahtar %q ile kacisli.
mkdir -p "$CONF_DIR"
umask 077
TMP="$(mktemp "$CONF_DIR/wrapper.env.XXXXXX")"
{
  printf '# People1000 ApiWrapper ayari — repo disinda, 600 izinli.\n'
  printf '# Yeniden kurmak icin: bash tools/termux_wrapper_setup.sh --new-key\n'
  printf 'export WRAPPER_URL=%q\n' "$URL"
  printf 'export WRAPPER_API_KEY=%q\n' "$KEY"
} > "$TMP"
mv "$TMP" "$CONF"
chmod 600 "$CONF"
unset KEY

# 5) Ag istegi OLMADAN dogrula (anahtar degeri yazdirilmaz).
set -a; . "$CONF"; set +a
python -m society.wrapper_api --check

echo
echo "Kurulum tamam. Ayar dosyasi: $CONF"
echo "Anahtari degistirmek icin: bash tools/termux_wrapper_setup.sh --new-key"
echo "Sonraki komutlar:"
echo "  source .venv/bin/activate && source \"$CONF\""
echo "  python -m society.web_ui --state runs/wrapper-pilot.json --open   # KARTLI ARAYUZ"
echo "  python -m society.termux --state runs/wrapper-pilot.json          # terminal pilotu"
echo "  python -m society.wrapper_api \"Merhaba\"                           # tek bagimsiz istek"
echo "NOT: Ayni --state dosyasini web arayuzu ve terminal AYNI ANDA acmayin."
# w = kartli web arayuzu, t = terminal pilotu, H = hicbiri.
read -r -p "Simdi neyi baslatayim? [w=web arayuzu / t=terminal / H=hicbiri] " RUN || true
case "${RUN:-}" in
  w|W) exec python -m society.web_ui --state runs/wrapper-pilot.json --open ;;
  t|T) exec python -m society.termux --state runs/wrapper-pilot.json ;;
  *) echo "Baslatilmadi. Yukaridaki komutlardan birini calistir." ;;
esac
