# Termux: klondan ApiWrapper'a — tüm komutlar

Bu kılavuz ApiWrapper (OpenAI uyumlu kendi servisiniz) bağlantısı için Termux
komutlarını tek yerde toplar: kurulum, `git pull`, ayar, doğrulama, web arayüzü,
arka planda çalıştırma, hata kodları ve güvenlik. Ayrıntılı istek sözleşmesi:
[apiwrapper-integration.md](apiwrapper-integration.md). Gemini yolu:
[termux-pilot.md](termux-pilot.md).

> **Dal notu:** ApiWrapper entegrasyonu bu oturumda
> `arena/8aad5b34-people1000` dalındadır. `main`'e birleştikten sonra normal
> `main` komutları yeterli olur. Aşağıda iki durum da yazılıdır.

## 0. Hızlı yol (kopyala-yapıştır)

Paketler kurulu ve depo zaten klonluysa:

```bash
cd "$HOME/people1000"
git fetch origin
git checkout -B arena/8aad5b34-people1000 origin/arena/8aad5b34-people1000
git pull --ff-only origin arena/8aad5b34-people1000
bash tools/termux_wrapper_setup.sh
```

Script adresi ve anahtarı sorar, `~/.config/people1000/wrapper.env` dosyasına
(600 izin) yazar, **ağ isteği atmadan** doğrular ve web arayüzünü başlatmayı
önerir. Anahtar ekranda görünmez.

## 1. Paketler

```bash
pkg update && pkg upgrade -y
pkg install python python-pip git nano -y
python --version        # 3.11 veya üzeri olmalı
```

Telefon ekranı kapanınca sunucu ölmesin diye (isteğe bağlı):

```bash
termux-wake-lock
# bırakmak için: termux-wake-unlock
```

## 2. Klonla veya güncelle (`pull`)

### İlk kez — bu dalı çek

```bash
cd "$HOME"
git clone --branch arena/8aad5b34-people1000 --single-branch \
  https://github.com/keremtulu44/people1000.git
cd people1000
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

### Depo zaten var — güncelle

```bash
cd "$HOME/people1000"
git fetch origin
git checkout -B arena/8aad5b34-people1000 origin/arena/8aad5b34-people1000
git pull --ff-only origin arena/8aad5b34-people1000
source .venv/bin/activate
```

`main`'e birleştikten sonra sadece:

```bash
cd "$HOME/people1000"
git checkout main
git pull --ff-only origin main
source .venv/bin/activate
```

`runs/` altındaki kayıtlar ve `~/.config/people1000/` ayarları `pull`
işleminden etkilenmez.

### Yerel değişiklik yüzünden pull reddedilirse

```bash
git status
# kendi değişikliğini sakla:
git stash push -m "yerel"
git pull --ff-only origin arena/8aad5b34-people1000
git stash pop        # çakışma olursa git diff ile bak
```

## 3. ApiWrapper ayarı (önerilen: tek komut)

```bash
cd "$HOME/people1000"
bash tools/termux_wrapper_setup.sh
```

Sorular:

1. **WRAPPER_URL** — ör. `https://api-wrapper.example.com` (sonundaki `/`
   önemsiz; `/v1` gerekiyorsa kendisi ekler, zaten varsa çiftlemez).
2. **WRAPPER_API_KEY** — yazarken ekranda görünmez.

Dosya: `~/.config/people1000/wrapper.env` (izin `600`, repo dışında).

Sonradan:

```bash
bash tools/termux_wrapper_setup.sh --new-key   # anahtarı yeniden sor
bash tools/termux_wrapper_setup.sh --print     # kayıtlı ayarı göster (ağ isteği yok)
```

## 4. Elle ayar (script kullanmadan)

```bash
mkdir -p "$HOME/.config/people1000"
umask 077
nano "$HOME/.config/people1000/wrapper.env"
chmod 600 "$HOME/.config/people1000/wrapper.env"
```

Dosyanın içeriği (gerçek değerleri kendiniz yazın, repoya koymayın):

```bash
export WRAPPER_URL='https://api-wrapper.example.com'
export WRAPPER_API_KEY='BURAYA_ANAHTAR'
```

Her yeni terminalde:

```bash
cd "$HOME/people1000"
source .venv/bin/activate
set -a; . "$HOME/.config/people1000/wrapper.env"; set +a
```

## 5. Doğrula (ağ isteği yok / tek istek)

```bash
cd "$HOME/people1000"
source .venv/bin/activate
set -a; . "$HOME/.config/people1000/wrapper.env"; set +a

python -m society.wrapper_api --check      # ağ isteği YOK, anahtar gösterilmez
python -m society.wrapper_api "Merhaba"    # TEK gerçek istek
```

`--check` çıktısı şöyle olmalı:

```json
{
  "adapter": "WrapperClient",
  "base_url": "https://api-wrapper.example.com/v1",
  "endpoint": "https://api-wrapper.example.com/v1/chat/completions",
  "model": "max",
  "stream": false,
  "timeout_seconds": 180.0,
  "has_key": true,
  "stateless": true
}
```

## 6. Web arayüzü

### Önde çalıştır

```bash
cd "$HOME/people1000"
source .venv/bin/activate
set -a; . "$HOME/.config/people1000/wrapper.env"; set +a
python -m society.web_ui --state runs/wrapper-pilot.json --open
```

Tarayıcı açılmazsa elle: **`http://127.0.0.1:8501`**

Port değiştirmek için:

```bash
python -m society.web_ui --state runs/wrapper-pilot.json --port 9000
```

Yeni bir kayıtla başlamak için:

```bash
python -m society.web_ui --new --state runs/wrapper-pilot-2.json
```

### Arkada çalıştır

```bash
cd "$HOME/people1000"
source .venv/bin/activate
set -a; . "$HOME/.config/people1000/wrapper.env"; set +a
mkdir -p runs
nohup python -m society.web_ui --state runs/wrapper-pilot.json > runs/web.log 2>&1 &
echo $! > runs/web.pid
```

Log ve durdurma:

```bash
tail -f runs/web.log
pkill -f society.web_ui          # veya: kill "$(cat runs/web.pid)"
```

### Arayüzde ApiWrapper paneli

**A bölümü → “ApiWrapper Bağlantısı”**: metni yaz, **Gönder**. Her gönderim
tek ve bağımsız bir istektir; önceki metinler eklenmez. Yanıtta model, akış
durumu ve varsa token sayısı görünür. Hata olursa **HTTP durum kodu** ve varsa
**ApiWrapper hata kodu** yazılır; anahtar hiçbir zaman gösterilmez.

> Aynı `--state` dosyasını web arayüzü ve terminal pilotu **aynı anda** açmayın.

## 7. Terminal pilotu (isteğe bağlı)

```bash
cd "$HOME/people1000"
source .venv/bin/activate
set -a; . "$HOME/.config/people1000/wrapper.env"; set +a
python -m society.termux --state runs/wrapper-pilot.json
```

Çevrimdışı (API'siz) deneme:

```bash
python -m society.termux --offline --state runs/offline-pilot.json
```

## 8. Güncelleme akışı (günlük)

```bash
cd "$HOME/people1000"
git pull --ff-only origin arena/8aad5b34-people1000
source .venv/bin/activate
# Ayar dosyasına DOKUNMA; anahtar orada kalır.
set -a; . "$HOME/.config/people1000/wrapper.env"; set +a
python -m society.wrapper_api --check
python -m society.web_ui --state runs/wrapper-pilot.json
```

`pyproject.toml` değişmediyse `pip install -e .` tekrar gerekmez. Gerekirse:

```bash
python -m pip install -e . --disable-pip-version-check
```

## 9. Hata kodları ve ilk bakılacaklar

| Görünen | Anlamı | Ne yapmalı |
|---|---|---|
| `HTTP 401` | Anahtar reddedildi | `bash tools/termux_wrapper_setup.sh --new-key` |
| `HTTP 403` | Anahtar yetkisi / plan / bölge | Wrapper panelinden anahtar yetkisini kontrol et |
| `HTTP 404` | Uç nokta veya **model** yok | Adresi kontrol et; wrapper `max` modelini tanımlıyor mu? |
| `HTTP 429` | Kota / hız sınırı | Bekle; aynı metni art arda göndermeyin |
| `HTTP 5xx` | Wrapper tarafı | Wrapper servisinin durumunu kontrol et |
| `zaman aşımı` | 180 sn içinde yanıt yok | Daha kısa metin dene; wrapper'ın gecikmesine bak |
| yerel `503` | `WRAPPER_URL` yok/geçersiz | `--check` çalıştır, adresi düzelt |
| yerel `500` | `WRAPPER_API_KEY` yok/biçimsiz | Anahtarı yeniden gir |

Kurallar: otomatik tekrar yoktur; her çağrı tek istektir. Hata mesajı
sağlayıcının ham gövdesini veya anahtarı göstermez. Yardım isterken **anahtarı
değil**, gizli bilgi içermeyen hata satırını paylaşın.

## 10. Güvenlik

- `WRAPPER_API_KEY` yalnızca `~/.config/people1000/wrapper.env` içinde; repo
  dışında ve `600` izinli. `.env` ve `.env.*` Git dışında.
- Anahtarı `git commit`, ekran görüntüsü, sohbet veya `runs/` dosyalarına
  koymayın. `python -m society.wrapper_api --check` anahtarı yazdırmaz.
- Web sunucusu varsayılan olarak yalnız `127.0.0.1` dinler. `--host 0.0.0.0`
  yalnız aynı Wi-Fi'daki cihazdan açmak istiyorsanız kullanın; ağdaki herkes
  paneli ve API kotanızı kullanabilir.
- Anahtar sızarsa wrapper panelinden **iptal/yenile**, sonra
  `--new-key` ile yeni anahtarı girin ve sunucuyu yeniden başlatın.

## 11. Gemini'ye dönme / çevrimdışı

ApiWrapper'ı devre dışı bırakmak için oturumda değişkeni boşaltın:

```bash
unset WRAPPER_URL WRAPPER_API_KEY
# Gemini anahtarın ~/.config/people1000/api.env içindeyse:
set -a; . "$HOME/.config/people1000/api.env"; set +a
python -m society.web_ui --state runs/gemini-pilot.json
```

Tamamen API'siz:

```bash
python -m society.web_ui --offline --state runs/offline-pilot.json
```

## 12. Testler (isteğe bağlı)

```bash
cd "$HOME/people1000"
source .venv/bin/activate
python -m unittest tests.test_wrapper_api -v
python -m unittest discover -s tests -v
```

Testler ağa çıkmaz; gerçek ApiWrapper kotanızı harcamaz.
