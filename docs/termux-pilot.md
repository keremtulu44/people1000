# Termux: klondan canlı API pilotuna

Bu terminal katmanı v3.3 araştırmasından sonra eklendi. Model davranış kuralları
ve araştırma sonuçları değiştirilmedi. 5 yeni terminal testi ve bütün paket birlikte
çalıştırıldı: 155 test, 154 başarılı, aynı tarihsel dosya nedeniyle 1 atlanan.
Gerçek sağlayıcıya istek gönderilmedi; HTTP kontrollü yanıtla test edildi.

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
gerekir. Native Gemini/Anthropic API adresi doğrudan uyumlu değildir. Sağlayıcının
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
bir ücretli istek yapar. Sonra `gun` ile tek tek ilerleyin.

- `rapor`: yerel kayıt, ücretsiz.
- `gun`: 1 simülasyon günü; önemli noktalarda API kullanılabilir.
- `ilerle 3`: 3 gün, her gün kayıt; ilk pilotta 30 gün birden başlatmayın.
- `sor`: rapor hakkında Türkçe soru; canlı modda 1 ücretli istek.
- `limit 40 15`: toplam/günlük gündem inceleme tavanını açıkça yükseltir.
- `kaydet`, `cik`: checkpoint.

Varsayılan toplam 30 / günlük 10 gündem değerlendirmesi ve ayrıca en çok 5
operatör sorusu denemesi vardır. Bağlantı denemesi soru kotasına dahildir.
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
