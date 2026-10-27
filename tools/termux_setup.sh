#!/usr/bin/env bash
# People1000 — Gemini pilotunu Termux'ta tek komutla kurar.
# Sadece docs/termux-pilot.md icindeki adimlari otomatiklestirir; yeni ozellik eklemez.
#
#   cd "$HOME/people1000"
#   git pull --ff-only origin arena/5fb8114f-people1000
#   bash tools/termux_setup.sh            # anahtari sorar / degistirme imkani verir
#   bash tools/termux_setup.sh --new-key  # anahtari zorla yeniden sorar
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
[ -f "$EXAMPLE" ] || { echo ".env.example yok. once: git pull --ff-only origin arena/5fb8114f-people1000"; exit 1; }

# 1) Sanal ortam: varsa yeniden kurma, paket zaten yukluyse tekrar kurma.
if [ ! -d .venv ]; then python3 -m venv .venv; fi
# shellcheck source=/dev/null
source .venv/bin/activate
if [ ! -x .venv/bin/people1000 ]; then
  echo "Paket kuruluyor (ilk kurulum)..."
  python -m pip install -e . --disable-pip-version-check
fi

# 2) Eski ayari oku. Saglayici degismisse eski anahtar gecersizdir:
#    Groq anahtari Gemini uc noktasinda 401/403 verir. Sessizce korunmamali.
HAD_CONF=0; OLD_ENDPOINT=""; OLD_MODEL=""; OLD_KEY=""
if [ -f "$CONF" ]; then
  HAD_CONF=1
  OLD_ENDPOINT="$(. "$CONF" >/dev/null 2>&1; printf '%s' "${PEOPLE1000_API_ENDPOINT:-}")"
  OLD_MODEL="$(. "$CONF" >/dev/null 2>&1; printf '%s' "${PEOPLE1000_API_MODEL:-}")"
  OLD_KEY="$(. "$CONF" >/dev/null 2>&1; printf '%s' "${PEOPLE1000_API_KEY:-}")"
fi
PINNED_ENDPOINT="$(. "$EXAMPLE" >/dev/null 2>&1; printf '%s' "${PEOPLE1000_API_ENDPOINT:-}")"
[ -n "$PINNED_ENDPOINT" ] || { echo "Sablonda endpoint yok; git pull yapin."; exit 1; }

OLD_HOST=""; PINNED_HOST=""
if [[ "$OLD_ENDPOINT" =~ ^https://([^/]+)/ ]]; then OLD_HOST="${BASH_REMATCH[1]}"; fi
if [[ "$PINNED_ENDPOINT" =~ ^https://([^/]+)/ ]]; then PINNED_HOST="${BASH_REMATCH[1]}"; fi

NEED_KEY=0
if [ "$HAD_CONF" -eq 0 ]; then
  NEED_KEY=1
  echo "Ilk kurulum: AI Studio anahtari gerekiyor."
elif [ "${1:-}" = "--new-key" ]; then
  NEED_KEY=1
  echo "--new-key: yeni anahtar istenecek."
elif [[ "$OLD_KEY" == gsk_* ]]; then
  NEED_KEY=1
  echo "UYARI: kayitli anahtar bir Groq anahtari (gsk_...). Gemini'de calismaz."
  echo "       Yeni AI Studio anahtari isteyecegim."
elif [ -n "$OLD_HOST" ] && [ "$OLD_HOST" != "$PINNED_HOST" ]; then
  NEED_KEY=1
  echo "UYARI: onceki adres baska bir saglayiciya ait: $OLD_HOST"
  echo "       Eski anahtar gecersiz; yeni AI Studio anahtari isteyecegim."
elif [ -n "$OLD_MODEL" ] && [[ "$OLD_MODEL" != gemini* ]]; then
  NEED_KEY=1
  echo "UYARI: onceki model Gemini degil ($OLD_MODEL). Yeni anahtar isteyecegim."
else
  # Ayni saglayici: yine de sor, sessizce eski anahtari kullanma.
  read -r -p "Kayitli Gemini anahtarini kullanayim mi? [E=evet / h=yeni gir] " KEEP || true
  case "${KEEP:-}" in
    h|H) NEED_KEY=1; echo "Yeni anahtar istenecek." ;;
    *) echo "Mevcut anahtar korunuyor." ;;
  esac
fi

# 3) Yeni anahtar once degiskene alinir; bos giris eski dosyayi bozmaz.
NEW_KEY_LINE=""
if [ "$NEED_KEY" -eq 1 ]; then
  read -r -s -p "AI Studio API anahtari (ekranda gorunmez): " KEY || true
  printf '\n'
  if [ -z "${KEY:-}" ]; then echo "Anahtar bos; ayar dosyasina dokunulmadi."; exit 1; fi
  NEW_KEY_LINE="$(printf 'export PEOPLE1000_API_KEY=%q' "$KEY")"
  unset KEY
fi

# 4) Ayar dosyasini yaz: anahtar disindaki satirlar guncel sablondan gelir.
#    Boylece eski Groq adresi veya gemini-flash-latest takma adi kalmaz.
mkdir -p "$CONF_DIR"
umask 077
TMP="$(mktemp "$CONF_DIR/api.env.XXXXXX")"
if [ "$NEED_KEY" -eq 1 ]; then
  printf '%s\n' "$NEW_KEY_LINE" > "$TMP"
else
  grep -E '^[[:space:]]*export PEOPLE1000_API_KEY=' "$CONF" > "$TMP" || true
fi
grep -E '^export ' "$EXAMPLE" | grep -v 'PEOPLE1000_API_KEY' >> "$TMP"
mv "$TMP" "$CONF"
chmod 600 "$CONF"

# 5) Ag istegi OLMADAN dogrula: hangi adaptor/model yuklendi?
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
echo "Kurulum tamam. Anahtari degistirmek istersen: bash tools/termux_setup.sh --new-key"
echo "Sonraki komutlar:"
echo "  source .venv/bin/activate && source \"$CONF\""
echo "  python -m society.web_ui --state runs/gemini-pilot.json --open       # KARTLI WEB ARAYUZU"
echo "  python -m society.termux --state runs/gemini-pilot.json              # terminal pilotu"
echo "  python -m society.termux --offline --state runs/offline-pilot.json    # ucretsiz deneme"
echo "NOT: Ayni --state dosyasini web arayuzu ve terminal AYNI ANDA acmayin."
# w = kartli web arayuzu (oncelikli), t/e = eski terminal pilotu, H = hicbiri.
read -r -p "Simdi neyi baslatayim? [w=web arayuzu / t=terminal / H=hicbiri] " RUN || true
case "${RUN:-}" in
  w|W) exec python -m society.web_ui --state runs/gemini-pilot.json --open ;;
  t|T|e|E) exec python -m society.termux --state runs/gemini-pilot.json ;;
  *) echo "Baslatilmadi. Yukaridaki komutlardan birini calistir." ;;
esac
