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
git clone --branch arena/2869026b-people1000 --single-branch https://github.com/keremtulu44/people1000.git
cd people1000
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m society.termux --help
```

Klasör zaten varsa tekrar clone etmeyin. Önceden bu dalı klonladıysanız repo
klasöründe `git pull --ff-only` ve sanal ortam etkinleştirmesi yeterlidir.
Termux'ta pip'i `pip install --upgrade pip` ile güncellemeyin; paket yöneticisini kullanın.

### Tek komutla kurulum (önerilen)

Paketler yüklüyse aşağıdaki üç komut sanal ortamı, `.env.example` ayarını ve
anahtar girişini halleder; eski Groq/`gemini-flash-latest` satırlarını temizler.
Script ağ isteği göndermez, yalnızca yüklü adaptörü/modeli yazdırır ve isterseniz
canlı pilotu başlatır.

```bash
cd "$HOME/people1000"
git pull --ff-only origin arena/2869026b-people1000
bash tools/termux_setup.sh
```

**Sağlayıcı değişince anahtar da değişir.** Groq anahtarı Gemini uç noktasında
çalışmaz. Script `gsk_` ile başlayan anahtarı veya farklı bir sağlayıcı adresini
görürse eski anahtarı **korumaz**, yenisini sorar. Aynı Gemini anahtarını
kullanacaksanız "Kayıtlı anahtarı kullanayım mı? [E/h]" sorusuna `E` deyin.
Anahtarı sonradan değiştirmek için:

```bash
bash tools/termux_setup.sh --new-key
```

Script boş anahtar girişinde ayar dosyasına dokunmaz. Elle kurmak isterseniz
3. bölümdeki adımlar aynı ayarı yapar.

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

**Önerilen yol (Gemini, sabit model):** depodaki `.env.example` adresi/modeli
içerir; yalnızca anahtarı siz eklersiniz. Yanlış model adı yazma ihtimali kalmaz.

```bash
cd "$HOME/people1000"
mkdir -p "$HOME/.config/people1000"
cp .env.example "$HOME/.config/people1000/api.env"
chmod 600 "$HOME/.config/people1000/api.env"
read -r -s -p "AI Studio API anahtarı (ekranda görünmez): " KEY
printf '\n'
printf 'export PEOPLE1000_API_KEY=%q\n' "$KEY" >> "$HOME/.config/people1000/api.env"
unset KEY
source "$HOME/.config/people1000/api.env"
```

Groq veya başka bir OpenAI-uyumlu sağlayıcı kullanacaksanız adresi/modeli elle
girin; anahtar yine aynı gizli `read` ile yazılır:

```bash
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
gerekir. Native Gemini generateContent adresi otomatik tanınır; ayrıntılar aşağıdadır.
Native Anthropic bu adaptörde desteklenmez. OpenAI-uyumlu sağlayıcının
`response_format` ve `max_completion_tokens` alanlarını desteklemesi gerekir.
Anahtarı doğrulamak için `cat api.env`, `env` veya `echo $PEOPLE1000_API_KEY`
kullanmayın; ekran görüntüsü/paylaşımda anahtar sızabilir.

Nano ile düzenlemek gerekirse:

```bash
nano "$HOME/.config/people1000/api.env"
```

Termux ek tuş satırındaki CTRL ile `CTRL+O`, Enter, `CTRL+X` kaydeder/çıkar.
`source "$HOME/.config/people1000/api.env"` değişiklikleri mevcut oturuma yükler.
Anahtarı değiştirmek için 3. bölümdeki `cp` + gizli `read` adımlarını baştan
çalıştırın; var olan dosyaya ikinci bir anahtar satırı eklemeyin.

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
- `sor`: yeni bir olay/senaryoyu (Gün 1) başlatır; canlı modda 1 API isteği.
- `devam` / `devam 10`, `olay`: senaryo zincirini ilerletir; her gün 1 istek.
- `ozet`: 6 kitleyi Türkçe özetler; API kullanmaz.
- `bekleme 6`: istekler arası asgari süreyi değiştirir.
- `limit 40 15`: toplam/günlük gündem inceleme tavanını açıkça yükseltir.
- `sor-limit 30`: senaryo adım sınırını açıkça yükseltir.
- `kaydet`, `cik`: checkpoint.

Varsayılan toplam 30 / günlük 10 gündem değerlendirmesi ve ayrıca en çok 5
operatör sorusu/üretim denemesi vardır (hatalar dahil). Gemini metadata kontrolleri
ayrı, kayıt başına toplam 10 denemeyle sınırlıdır. `limit` bu iki sayacı değiştirmez.
Bunlar kota/harcama garantisi değildir: ücretsiz katmanda kota, faturalama
bağlanmış projede bütçe söz konusudur; ikinci durumda sağlayıcı hesabından ayrıca
düşük bir harcama tavanı koyun. Hatalı ağ denemeleri de kotadan düşebilir;
otomatik retry yok.

Hazır senaryo 100 kişi, her rolden seçilmiş bir hedef ve atayan yönetici içerir.
Gereken yerlerde açıkça kontrollü kaynak bağlantıları eklenir; doğal iletişim ağı
hakkında sonuç çıkarılmamalıdır. İlk gün duyuru, sonraki günler açıklama,
4. simülasyon gününde yeterlilik belgesi gelir. Yeterlilik ile atama usulü ayrıdır.

`sor`, `devam`, `olay` bir **anlatı zinciri** üretir: `sor` Gün 1'i başlatır,
`devam` nedensel kurallarla sonraki güne geçer, `olay` kendi gelişmenizi ekler.
Bu zincir yalnızca pilot kayıt protokolünde tutulur; ajanların hafızasına, dünya
olay günlüğüne, ekonomiye veya taraf/ideoloji hesabına yazılmaz. Yani üretilen
metin motorun gerçekleşmiş sonucu değildir; `gun`/`ilerle` ile yürüyen simülasyon
durumundan ayrıdır.

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

## 6. Web arayüzü — Termux arkada, tarayıcı önde

Terminal hâlâ çalışır ama **okumak için** artık telefonunun tarayıcısını
kullanabilirsin. `society/web_ui.py` tamamen standart kütüphaneyle yazılmış yerel
bir web sunucusudur: **Streamlit, Flask, npm veya ek pip paketi gerekmez**. Motor
Termux'ta arkada çalışmaya devam eder; API anahtarı yalnızca o süreçte kalır,
tarayıcıya gönderilen HTML/JS'de anahtar yoktur.

```bash
cd "$HOME/people1000"
source .venv/bin/activate
source "$HOME/.config/people1000/api.env"
python -m society.web_ui --state runs/gemini-pilot.json --open
```

`--open` Termux tarayıcısını açmayı dener; açılmazsa adresi elle yaz:
**`http://127.0.0.1:8501`**. Ücretsiz denemek için `--offline` ekle (API
kullanmaz), yeni bir kayıt için `--new --state runs/baska.json`, port değiştirmek
için `--port 9000`. Sunucuyu arka planda bırakmak istersen:

```bash
nohup python -m society.web_ui --state runs/gemini-pilot.json > runs/web.log 2>&1 &
# durdurmak için: pkill -f society.web_ui
```

Ekranda neler var:

- Üstte gün, mod (CANLI / ÇEVRİMDIŞI), model, bekleme süresi, taraf/ideoloji
  değişimi, API deneme/kabul ve soru/sınır sayaçları.
- **6 kitle kartı** — her birinde tek cümlelik eylem, Yeterlilik/Usul yüzdesi
  (görsel çubuk), **düne göre fark oku** (`▲ +7 puan`), Türkçe özet. Statik rol
  tanımı ve model notu daraltılabilir "Detay" içinde; artık her seferinde ekranı
  doldurmuyor.
- **AI anlatımı her kartın kendi boşluğunda.** `sor`, `devam`, `olay` ile Gemini'den
  gelen "**1. İktidar Yanlıları** … **6. Gözlemciler**" biçimli metin
  `society/scenario_text.py` ile 6 bölüme ayrılır; her bölüm **kendi kartındaki**
  mavi "AI ANLATIMI · GÜN N" kutusuna yazılır (Zenginler kartında 3 alt kanat da
  aynı kutuda kalır). Motorun sayısal özeti hemen altında gri satırda durur.
  "Anlatım günü" seçicisiyle zincirin önceki günlerine dönüp o günün 6 kartlık
  metnini görebilirsin. AI metni yoksa kutu bunu açıkça belirtir.
- Tam metin artık kayıtta saklanır; eski sürüm yalnızca ilk 600 karakteri
  tutuyordu. Eski kayıtlarda kartlar "ESKİ KAYIT" etiketiyle kırpılmış metni
  gösterir; yeni bir `sor`/`devam` çalıştırınca tam metin gelir. Sonraki günlerin
  prompt'una yine yalnızca kısa özet gider, kotayı şişirmez.
- Komut paneli: `Gün ilerlet`, `İlerle 3`, `Özet`, `Rapor`, `Ayar`, `Kaydet`,
  senaryo başlatma (`Başlat`), `Devam 1/3`, `Olay ekle`. Tanılama ve sınırlar
  açılır panelinde `Bağlantı`, `Modeller`, `Üretim testi` (onay ister), `Bekleme`,
  `Limit`, `Soru limiti`, JSON indirme.
- **Senaryo zinciri zaman çizelgesi**: başlangıç olayı + her günün gelişmesi,
  nedensel sınırı ve özeti.
- **Son çıktı** alanı: terminalde göreceğin metnin aynısı, kaydırılabilir.

"Düne göre" farkları `runs/<kayıt>.history.json` dosyasında tutulur (kayıtla
birlikte, repo dışında). Sayfa yenilenince son komutun çıktısı geri gelir.

**Dikkat edilmesi gerekenler:**

- `--host` varsayılan olarak `127.0.0.1`'dir; yani sunucu yalnızca telefonunun
  içinden erişilebilir. `0.0.0.0` yaparsan aynı Wi-Fi'daki herkes arayüze (ve
  senin kotana) erişebilir — bunu telefonunda yapma. Gerçek bir web adresine
  taşırken kimlik doğrulama ekle ve anahtarı sunucu ortamında tut.
- **Aynı `--state` dosyasını terminal pilotu ve web arayüzü ile aynı anda açma.**
  İkisi de checkpoint yazar; biri diğerinin kaydını ezer. Farklı `--state` yolu
  kullan veya önce birini kapat.
- Tanılama/üretim testi butonları onay penceresi çıkarır; otomatik retry yoktur.
  Hatalı istekler de kotadan düşebilir.

## Kalıcı Gemini ayarı — sabit model ve uç nokta (26 Ekim 2026)

Groq'tan ücretsiz Gemini'ye geçiş için seçilen değerler **kodda sabitlendi**
(`society/agenda_api.py`: `GEMINI_MODEL`/`GEMINI_ENDPOINT`) ve depodaki
`.env.example` şablonuna yazıldı. `PEOPLE1000_API_ENDPOINT` ve
`PEOPLE1000_API_MODEL` ikisi de boş bırakılırsa adaptör bu sabit değerleri
kullanır; yani elle yazmanız gereken tek şey API anahtarıdır. Şablonda aynı
değerler açıkça yazılıdır; `ayar` komutu hangisinin yüklendiğini gösterir.

```bash
export PEOPLE1000_API_ENDPOINT='https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent'
export PEOPLE1000_API_MODEL='gemini-3.5-flash-lite'
export PEOPLE1000_API_MIN_INTERVAL=6
export PEOPLE1000_MAX_OUTPUT_TOKENS=4096
```

Bu, native `generateContent` uç noktasıdır: adaptör `X-goog-api-key`,
`contents/parts`, `generationConfig` kullanır; OpenAI `messages` biçimi gönderilmez.
Google'ın OpenAI-uyumlu adresi
`https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` de
tanınır ve aynı native isteğe çevrilir; fakat tek bir yol kullanmak daha
öngörülebilirdir. Native Anthropic bu adaptörde desteklenmez.

### Neden `gemini-3.5-flash-lite`?

- Resmî [fiyatlandırma sayfası](https://ai.google.dev/gemini-api/docs/pricing) bu
  model için ücretsiz katmanda hem girdi hem çıktıyı **"Free of charge"** olarak
  listeler; [model sayfası](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)
  yüksek hacimli/düşük maliyetli işler için tasarlandığını, 1M girdi / 65K çıktı
  tokeni desteklediğini söyler. [Kaldırma takvimi](https://ai.google.dev/gemini-api/docs/deprecations)
  bu model için bir kapanma tarihi vermez (3.1 Flash-Lite için 7 Mayıs 2027 var).
- **Kayan takma ad kullanılmıyor.** Resmî [modeller sayfası](https://ai.google.dev/gemini-api/docs/models#model-versions)
  `gemini-flash-latest` gibi `-latest` adlarının her yeni sürümde değiştiğini, üretim
  için sabit (`stable`) model kimliği gerektiğini yazar. Önceki zaman aşımı →
  503 → 404 zincirinin en olası sebebi bu takma adın arka planındaki modelin
  değişmesidir.
- **2.5 ailesi yeni projelere kapalı.** Yeni projelerde `gemini-2.5-flash` /
  `gemini-2.5-flash-lite` için 404 "no longer available to new users" döndüğü
  rapor edilir; adaptör bu mesajı güvenli biçimde Türkçe olarak gösterir.
- **3.8/3.6 Flash ücretsiz kotada çok düşük günlük isteğe sahip.** Ekim 2026'da
  AI Studio kotası olarak paylaşılan gözlemlerde Flash için ~20 RPD, Flash-Lite
  için ~500 RPD / 15 RPM görülüyor. Google [hız sınırı belgesinde](https://ai.google.dev/gemini-api/docs/rate-limits)
  ücretsiz katmanın sabit sayılarını artık yayımlamıyor; **gerçek kotanız proje
  bazlıdır ve AI Studio → Rate limit ekranından okunmalıdır.** Günlük 100–300
  istek hedefi 500 RPD'lik gözlemlenen kotanın içinde kalır; 3.8 Flash ile aynı
  hedef ilk 20 istekte tıkanır.
- Model "çok üstün" değil; bu iş için yeterli: Türkçe rol/kanıt/iddia ayrımı
  yapan kısa JSON kararları ve 6 kitleli özetler. Daha ağır akıl yürütme isteyen
  bir modele geçilirse düşünme tokenleri çıktı tavanından düşer ve `MAX_TOKENS`
  ile yarım yanıt alma riski artar.

### Kota ve hız davranışı

Üç sınır ayrı ayrı uygulanır: RPM (dakikada istek), TPM (dakikada token), RPD
(günde istek). Herhangi biri aşılınca 429 gelir. Günlük kota **Pasifik
gece yarısı** sıfırlanır; bu Türkiye saatiyle yaklaşık sabah 10:00–11:00'dir.
Kota API anahtarı başına değil **proje başınadır**; aynı projede ikinci anahtar
kota artırmaz. Ücretsiz katmanda içerik Google ürünlerini geliştirmek için
kullanılabilir; projeye faturalama bağlamak ücretsiz katmanı kapatır.

`PEOPLE1000_API_MIN_INTERVAL=6` ardışık istekler arasında 6 saniye bekler
(≈10 istek/dakika), böylece `gun` veya `devam 10` gibi komutlarda 10 isteğin
arkaya arkaya gidip 429 alması engellenir. Bu Gemini varsayılanıdır (Groq
`5.0`, diğer sağlayıcılar `0.0`); `bekleme 6` komutuyla çalışma anında
değiştirilebilir. Pilotun
kendi tavanları (toplam 30 / günlük 10 gündem incelemesi, ayrıca en çok 5
operatör sorusu) zaten tipik günlük kullanımı kotanın çok altında tutar; kota
yine de garanti değildir.

`baglanti` tek model metadata GET isteğidir. Başarısı metin üretimi, ücret veya
kota garantisi vermez. `uretim-test` ayrıca onay gerektiren tek üretim isteğidir.
Otomatik tekrar/model değiştirme yapılmaz; 429'ta sağlayıcının `Retry-After`
süresi güvenli mesajda gösterilir. Ham hata gövdesi/anahtar yazdırılmaz;
kimlik bilgilerini korumak için HTTP yönlendirmeleri izlenmez.

İsteğe bağlı ortam ayarları (Nano ile aynı ayar dosyasına eklenebilir):
- `PEOPLE1000_API_TIMEOUT`: 1–120 saniye; Gemini varsayılanı 30, diğerleri 60.
  Bu soket zaman aşımıdır, toplam işlem süresi garantisi değildir; 404/503 çözümü değildir.
- `PEOPLE1000_MAX_OUTPUT_TOKENS`: 1–8192; Gemini varsayılanı 4096, diğerleri 500.
  6 kitleli Türkçe zincir yanıtları için yükseltildi; eski 2048 tavanı kesilmiş
  yanıt riski taşıyordu. Bu üst sınırdır; gerçek kullanım veya maliyet garantisi
  değildir.
- `PEOPLE1000_API_MIN_INTERVAL`: 0–60 saniye; Gemini varsayılanı `6.0`,
  `api.groq.com` için `5.0`, diğerlerinde `0.0`.

### Web adresine geçişte

İleride bu terminal katmanı bir web sunucusuna taşınırsa API anahtarı **yalnızca
sunucu tarafındaki ortam değişkeninde** kalmalı; tarayıcıya giden JavaScript,
HTML veya JSON içine yazılmamalı. Tarayıcı kendi sunucunuza göreli (relative) URL ile istek
atmalı, `agenda_api` adaptörü Gemini'ye sunucudan bağlanmalı. Mevcut adaptör
zaten anahtarı ortamdan okuyup snapshot/report dosyalarına yazmıyor; bu sınır
korunmalı. Web paneli bu sürümde yoktur.

Güncelleme için:

```bash
cd "$HOME/people1000"
git pull --ff-only origin arena/2869026b-people1000
source .venv/bin/activate
# Ayar dosyası zaten varsa ÜZERİNE YAZMAYIN (anahtar silinir).
# nano ile yalnızca model/adres/aralık satırlarını .env.example ile eşitleyin.
source "$HOME/.config/people1000/api.env"
python -m society.termux --state runs/gemini-pilot.json
```

`ayar` komutu gerçek adaptör, adres, model, timeout, token tavanı ve bekleme
süresini anahtarsız gösterir. Yukarıdaki model/adres resmî belgelerle
araştırılmıştır; **gerçek anahtarla Google/Android/faturalandırma doğrulaması bu
çalışma ortamında yapılmadı.** Kotanızı ve model erişimini kendi AI Studio
hesabınızda `baglanti` + `uretim-test` ile doğrulayın.

## Zincirleme senaryo komutları (`sor`, `devam`, `devam 10`, `olay`, `ozet`)

Groq (veya başka OpenAI-uyumlu sağlayıcı) hâlâ desteklenir: 3. bölümdeki elle
giriş bloğuyla `https://api.groq.com/openai/v1/chat/completions` ve hesabınızın
model adını yazın; `PEOPLE1000_API_MIN_INTERVAL` varsayılanı `5.0`'dır. Gemini
yukarıdaki sabit ayar, anahtar değiştirilerek kullanılır. Komutlar her iki
adaptörde aynıdır.

Simülasyonun karakter ve kriz zinciri felsefesi: [simulasyon-felsefesi.md](simulasyon-felsefesi.md).

- `ozet`: 6 kitleyi ayrı ayrı Türkçe açıklar ve mevcut uygulamanın özetini verir (ücretsiz).
- `sor`: Yeni bir olayı/senaryoyu (Gün 1) başlatıp 6 kitle üzerinde dener veya mevcut durumu yorumlar.
- `devam` / `devam 10`: Başlatılan senaryo zincirini nedensel kurallarla 1 gün veya 10 gün boyunca kendi kendine ileri taşır (her gün sonunda diske kaydeder ve `min_interval` kadar bekler).
- `olay`: Devam eden zincire kullanıcının kendi yeni gelişmesini ekleyip 1 gün ilerletir.
- `sor-limit 30`: `sor` / senaryo adım sınırını açıkça artırır.

Gerçek anahtarla Google/Android doğrulaması yapılmadı. Metadata istekleri de HTTP
isteğidir; ücretsiz/sınırsız olduğu varsayılmamalıdır. Hatalı üretimde sağlayıcının
bildirdiği token sayıları korunur; sayı bildirilmemesi sıfır kullanım demek değildir.
