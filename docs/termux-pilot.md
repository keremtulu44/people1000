# Termux: klondan canlı API pilotuna

Bu terminal katmanı v3.3 araştırmasından sonra eklendi. Model davranış kuralları
ve araştırma sonuçları değiştirilmedi. API öz-denetiminin test kanıtı ve sınırları
`reports/api-self-audit/report.md` içindedir. Gerçek sağlayıcıya istek gönderilmedi;
HTTP kontrollü yanıtlarla test edildi.

## 1. Kurulum

Güncel Termux kullanın (F-Droid veya projenin resmi GitHub dağıtımı). Android
telefonun kendi terminalinde çalışır; bu işlem Arena sunucusunda API çalıştırmaz.

```bash
pkg update && pkg upgrade -y
pkg install python python-pip git nano -y
cd "$HOME"
git clone --branch arena/22f16290-people1000 --single-branch https://github.com/keremtulu44/people1000.git
cd people1000
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m society.termux --help
```

Klasör zaten varsa tekrar clone etmeyin. Önceden bu dalı klonladıysanız repo
klasöründe `git pull --ff-only` ve sanal ortam etkinleştirmesi yeterlidir.
Termux'ta pip'i `pip install --upgrade pip` ile güncellemeyin; paket yöneticisini kullanın.

## 2. Önce ücretsiz deneme

```bash
python -m society.termux --offline --state runs/offline-pilot.json
```

`gun`, `rapor`, `cik` komutlarıyla başlayın. Bu mod API çağırmaz. Canlı deneyi
ayrı kayıt yolunda başlatın; çevrimdışı kayıtların bir bölümünü canlıymış gibi saymayın.

## 3. API ayarı (anahtar sohbete ve shell geçmişine yazılmaz)

`.venv` Python paketlerini yalıtır; gizli bilgi kasası değildir. Ayar dosyası
repo dışında, yalnız kullanıcıya açık izinle tutulur. Anahtar diskte düz metindir;
telefon kilidi/yedekleme güvenliği önemlidir. Bu, şifreli anahtar kasası değildir.

```bash
mkdir -p "$HOME/.config/people1000"
umask 077
read -r -p "Tam HTTPS chat/completions adresi: " ENDPOINT
read -r -p "Sağlayıcındaki model adı: " MODEL
read -r -s -p "API anahtarı (ekranda görünmez): " KEY
printf '\n'
{
  printf 'export PEOPLE1000_API_ENDPOINT=%q\n' "$ENDPOINT"
  printf 'export PEOPLE1000_API_MODEL=%q\n' "$MODEL"
  printf 'export PEOPLE1000_API_KEY=%q\n' "$KEY"
} > "$HOME/.config/people1000/api.env"
chmod 600 "$HOME/.config/people1000/api.env"
unset KEY ENDPOINT MODEL
source "$HOME/.config/people1000/api.env"
```

OpenAI Chat Completions için adres örneği:
`https://api.openai.com/v1/chat/completions`. Model adını hesabınızın desteklediği
model olarak girin. Farklı sağlayıcı için onun OpenAI-uyumlu **tam uç noktası**
gerekir. Native Gemini generateContent adresi artık otomatik tanınır; ayrıntılar aşağıdadır. Native Anthropic bu adaptörde desteklenmez. OpenAI-uyumlu sağlayıcının
`response_format` ve `max_completion_tokens` alanlarını desteklemesi gerekir.
Anahtarı doğrulamak için `cat api.env`, `env` veya `echo $PEOPLE1000_API_KEY`
kullanmayın; ekran görüntüsü/paylaşımda anahtar sızabilir.

Nano ile düzenlemek gerekirse:

```bash
nano "$HOME/.config/people1000/api.env"
```

Termux ek tuş satırındaki CTRL ile `CTRL+O`, Enter, `CTRL+X` kaydeder/çıkar.
`source "$HOME/.config/people1000/api.env"` değişiklikleri mevcut oturuma yükler.
Anahtarı değiştirmek için gizli `read` bloğunu tekrar çalıştırabilirsiniz.

## 4. Canlı pilot

```bash
cd "$HOME/people1000"
source .venv/bin/activate
source "$HOME/.config/people1000/api.env"
python -m society.termux --state runs/phone-pilot.json
```

Program açılması tek başına ağ isteği göndermez. `baglanti` komutu açık onayla
Gemini için bir model metadata GET isteği yapar; metin üretmez. Diğer OpenAI-uyumlu
adaptörde metin üretimi yapar. Bunlar ücretsiz kota kanıtı değildir.

- `ayar`: yüklenen gerçek adaptör/adres/model/zaman aşımı/token tavanı; ağ isteği yok, anahtar gösterilmez.
- `baglanti`: Gemini model metadata kontrolü; metin üretiminin çalıştığını kanıtlamaz.
- `modeller`: Gemini model listesinin yalnız ilk sayfası (en çok 100); otomatik model seçmez veya sayfa ilerletmez.
- `uretim-test`: açık onayla 1 kısa üretim isteği; token/kota kullanabilir.
- `rapor`: yerel kayıt, ağ isteği yok.
- `gun`: 1 simülasyon günü; önemli noktalarda API kullanılabilir.
- `ilerle 3`: 3 gün, her gün kayıt; ilk pilotta 30 gün birden başlatmayın.
- `sor`: rapor hakkında Türkçe soru; canlı modda 1 ücretli istek.
- `limit 40 15`: toplam/günlük gündem inceleme tavanını açıkça yükseltir.
- `kaydet`, `cik`: checkpoint.

Varsayılan toplam 30 / günlük 10 gündem değerlendirmesi ve ayrıca en çok 5
operatör sorusu/üretim denemesi vardır (hatalar dahil). Gemini metadata kontrolleri
ayrı, kayıt başına toplam 10 denemeyle sınırlıdır. `limit` bu iki sayacı değiştirmez.
Bunlar parasal harcama garantisi değildir; sağlayıcı hesabından ayrıca düşük bir
harcama tavanı koyun. Hatalı ağ denemeleri de ücretlenebilir; otomatik retry yok.

Hazır senaryo 100 kişi, her rolden seçilmiş bir hedef ve atayan yönetici içerir.
Gereken yerlerde açıkça kontrollü kaynak bağlantıları eklenir; doğal iletişim ağı
hakkında sonuç çıkarılmamalıdır. İlk gün duyuru, sonraki günler açıklama,
4. simülasyon gününde yeterlilik belgesi gelir. Yeterlilik ile atama usulü ayrıdır.

`sor` alanı salt okunur **yönetici rapor sorusudur**, kişinin konuşması veya
serbest metinle olay yaratma talimatı değildir. Örneğin "Muhalif yeterliliği kabul
etti mi, usule itirazı sürüyor mu?" sorulabilir. Yeni doğal dil olay ekleme arayüzü
bu pilotta yoktur. Atama eylemi taraf/ideoloji değişimi üretmez.

## 5. Sonradan devam etme / yeni kayıt

Her yeni Termux oturumunda canlı pilotun yukarıdaki dört komutunu tekrarlayın.
Aynı `--state` otomatik yüklenir; `cik` ile normal çıkın. Telefonun uyku/pil
kısıtlamaları süreci durdurabilir; uzun koşu için şarj ve uygulama pil ayarlarını
kontrol edin. Günlük checkpoint gerçek kayıt sağlar; işletim sistemi zorla
kapatmasına karşı kesintisiz hizmet garantisi değildir.

Yeni bir deneme için eski dosyayı silmeyin:

```bash
python -m society.termux --new --state runs/phone-pilot-2.json
```

Ağ/model hatasında önce adres, model, API yetkisi ve hesabın API bakiyesini
kontrol edin. Sohbet aboneliği otomatik API bakiyesi demek değildir. Yardım isterken
anahtarı veya ayar dosyasını değil, gizli bilgi içermeyen hata mesajını paylaşın.

## Gemini yerel API düzeltmesi

Google'ın cURL örneğindeki `generateContent` artık doğrudan desteklenir.
İstek `X-goog-api-key`, `contents/parts`, `generationConfig` kullanır;
OpenAI `messages` biçimi gönderilmez. Eski Google uyumluluk adresi de otomatik
yerel adaptöre yönlendirilir. Ücretsiz kullanım hesap/model/kotaya bağlıdır.

```bash
cd "$HOME/people1000"
git pull --ff-only origin arena/22f16290-people1000
source .venv/bin/activate
nano "$HOME/.config/people1000/api.env"
```

Adres ve model satırları (anahtarı değiştirmeyin/paylaşmayın):

```bash
export PEOPLE1000_API_ENDPOINT='https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent'
export PEOPLE1000_API_MODEL='gemini-flash-latest'
```

Kaydedip çıkınca `source "$HOME/.config/people1000/api.env"` ve
`python -m society.termux --state runs/gemini-pilot.json` çalıştırın.
`ayar` yerel etkin ayarları gösterir; önceki 404'ün kesin sebebi bu çalışma
ortamında doğrulanamadı. Yukarıdaki model adı yalnız yapılandırma örneğidir;
hesabınızda kullanılabildiği veya ücretsiz olduğu doğrulanmış değildir.

`baglanti` tek model metadata GET isteğidir. Başarısı metin üretimi, ücret veya
kota garantisi vermez. `uretim-test` ayrıca onay gerektiren tek üretim isteğidir.
Otomatik tekrar/model değiştirme yapılmaz. Ham hata gövdesi/anahtar yazdırılmaz;
kimlik bilgilerini korumak için HTTP yönlendirmeleri izlenmez.

İsteğe bağlı ortam ayarları (Nano ile aynı ayar dosyasına eklenebilir):
- `PEOPLE1000_API_TIMEOUT`: 1–120 saniye; Gemini varsayılanı 30, diğerleri 60.
  Bu soket zaman aşımıdır, toplam işlem süresi garantisi değildir; 404/503 çözümü değildir.
- `PEOPLE1000_MAX_OUTPUT_TOKENS`: 1–8192; Gemini varsayılanı 2048, diğerleri 500.
  Bu üst sınırdır; gerçek kullanım veya maliyet garantisi değildir. Çok küçük tavan
  özellikle düşünme kullanan modellerde boş/eksik yanıt verebilir.
- `PEOPLE1000_API_MIN_INTERVAL`: 0–60 saniye; `api.groq.com` için varsayılan `5.0`,
  diğerlerinde `0.0`. Dakikalık hız/token sınırına (TPM/RPM) takılmamak için ardışık
  API istekleri arasında bekler; çalışma sırasında `bekleme 5` komutuyla da değiştirilebilir.

## Groq yapılandırması ve zincirleme senaryo komutları (`sor`, `devam`, `devam 10`, `olay`, `ozet`)

Simülasyonun karakter ve kriz zinciri felsefesi: [simulasyon-felsefesi.md](simulasyon-felsefesi.md).

- `ozet`: 6 kitleyi ayrı ayrı Türkçe açıklar ve mevcut uygulamanın özetini verir (ücretsiz).
- `sor`: Yeni bir olayı/senaryoyu (Gün 1) başlatıp 6 kitle üzerinde dener veya mevcut durumu yorumlar.
- `devam` / `devam 10`: Başlatılan senaryo zincirini nedensel kurallarla 1 gün veya 10 gün boyunca kendi kendine ileri taşır (her gün sonunda diske kaydeder ve `min_interval` kadar bekler).
- `olay`: Devam eden zincire kullanıcının kendi yeni gelişmesini ekleyip 1 gün ilerletir.
- `sor-limit 30`: `sor` / senaryo adım sınırını açıkça artırır.

Gerçek anahtarla Google/Android doğrulaması yapılmadı. Metadata istekleri de HTTP
isteğidir; ücretsiz/sınırsız olduğu varsayılmamalıdır. Hatalı üretimde sağlayıcının
bildirdiği token sayıları korunur; sayı bildirilmemesi sıfır kullanım demek değildir.
