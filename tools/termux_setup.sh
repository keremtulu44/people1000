#!/usr/bin/env bash
# People1000 — Gemini pilotunu Termux'ta tek komutla kurar.
# Sadece docs/termux-pilot.md icindeki adimlari otomatiklestirir; yeni ozellik eklemez.
#
#   cd "$HOME/people1000"
#   git pull --ff-only origin arena/2869026b-people1000
#   bash tools/termux_setup.sh
#
# Anahtar ekrana yazilmaz; repo disinda, 600 izinli dosyada tutulur.
# Bu script HIC ag istegi gondermez (pip install disinda); dogrulama cevrimdisidir.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
CONF_DIR="$HOME/.config/people1000"
CONF="$CONF_DIR/api.env"
EXAMPLE="$REPO/.env.example"

command -v python3 >/dev/null 2>&1 || { echo "Python yok. Termux'ta: pkg install python git nano -y"; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' || { echo "Python 3.11+ gerekli."; exit 1; }
[ -f "$EXAMPLE" ] || { echo ".env.example yok. once: git pull --ff-only origin arena/2869026b-people1000"; exit 1; }

# 1) Sanal ortam: varsa yeniden kurma, paket zaten yukluyse tekrar kurma.
if [ ! -d .venv ]; then python3 -m venv .venv; fi
# shellcheck source=/dev/null
source .venv/bin/activate
if [ ! -x .venv/bin/people1000 ]; then
  echo "Paket kuruluyor (ilk kurulum)..."
  python -m pip install -e . --disable-pip-version-check
fi

# 2) Ayar dosyasi: anahtari koru, diger satirlari guncel sablonla esitle.
# Boylece eski Groq adresi veya gemini-flash-latest takma adi kalmaz.
mkdir -p "$CONF_DIR"
umask 077
TMP="$(mktemp "$CONF_DIR/api.env.XXXXXX")"
if [ -f "$CONF" ]; then
  grep -E '^[[:space:]]*export PEOPLE1000_API_KEY=' "$CONF" > "$TMP" || true
  echo "Mevcut anahtar korundu; model/adres/hiz satirlari guncellendi."
else
  : > "$TMP"
fi
grep -E '^export ' "$EXAMPLE" | grep -v 'PEOPLE1000_API_KEY' >> "$TMP"
mv "$TMP" "$CONF"
chmod 600 "$CONF"

# 3) Anahtar yoksa bir kez iste. Deger ekrana/gunluge yazilmaz.
if ! grep -qE '^[[:space:]]*export PEOPLE1000_API_KEY=' "$CONF"; then
  read -r -s -p "AI Studio API anahtari (ekranda gorunmez): " KEY || true
  printf '\n'
  if [ -z "${KEY:-}" ]; then echo "Anahtar bos; iptal edildi."; exit 1; fi
  printf 'export PEOPLE1000_API_KEY=%q\n' "$KEY" >> "$CONF"
  unset KEY
fi

# 4) Ağ isteği OLMADAN dogrula: hangi adaptor/model yuklendi?
# shellcheck source=/dev/null
source "$CONF"
python - <<'PY'
from society.agenda_api import advisor_from_environment
a = advisor_from_environment()
print("Adaptor :", type(a).__name__)
print("Model   :", a.model)
print("Adres   :", a.endpoint)
print("Bekleme :", a.min_interval, "sn")
print("Cikti   :", a.max_output_tokens, "token")
PY

echo
echo "Kurulum tamam. Sonraki komutlar:"
echo "  source .venv/bin/activate && source \"$CONF\""
echo "  python -m society.termux --offline --state runs/offline-pilot.json   # ucretsiz deneme"
echo "  python -m society.termux --state runs/gemini-pilot.json                # canli"
read -r -p "Simdi canli pilotu baslatayim mi? [e/H] " RUN || true
if [ "${RUN:-}" = "e" ] || [ "${RUN:-}" = "E" ]; then
  exec python -m society.termux --state runs/gemini-pilot.json
fi
