# API/Termux öz-denetimi — 2026-10-26

## Kapsam ve dürüst sonuç

Kullanıcının yaşadığı zaman aşımı, 503 ve ardından 404 sonrasında adaptör,
istek yönlendirmesi, tanılama komutları, kullanım kaydı ve gizlilik incelendi.
Önceki küçük model önerisi gerçek hesapta üretim desteği doğrulanmadan yapıldı;
model listesinde görünmek tek başına üretim desteğini kanıtlamaz. Yeni model
önerisi veya başarılı canlı bağlantı iddiası yoktur. 404'ün kesin sebebi açık kalmıştır.
Gerçek anahtar kullanılmadı; Google erişimi, Android/Termux ve faturalandırma
bu ortamda doğrulanmadı. Testler kontrollü HTTP yanıtları kullanır.

## Bulgu ve düzeltmeler

1. `baglanti` üretim çağrısıydı ve soru kotasını tüketiyordu. Gemini'de artık
   açık onaylı model metadata GET; üretim ayrı `uretim-test` komutudur.
   Metadata başarısı metin üretimi/ücretsiz kota başarısı değildir.
2. Etkin ayarlar yeterince görünür değildi. Başlangıç ve `ayar` gerçek adaptör,
   adres, model, timeout ve token tavanını anahtarsız ve ağsız gösterir.
3. Kesilmiş/bozuk yanıtların kullanım sayıları kaybolabiliyordu. Sağlayıcının
   bildirdiği güvenli sayılar başarısızlıkta da korunur; eski kullanım temizlenir.
   Bilinmeyen kullanım sıfır kabul edilmez.
4. Standart HTTP yönlendirmeleri credential başlıklarını taşıyabilirdi.
   Artık tüm yönlendirmeler reddedilir. Gözlenmiş anahtar sızıntısı iddiası yoktur.
5. Hatalar sabit güvenli kategoriler ve varsa HTTP koduyla kaydedilir. Ham
   sağlayıcı mesajı, URL veya anahtar hata çıktısına eklenmez. 503 yanlış modelin
   kanıtı değildir; 404 nedeni uzaktan tahmin edilmez.
6. Timeout/token tavanları sınırlı ortam ayarlarıyla değiştirilebilir; düşük
   tavanın kesilme riski belgelenmiştir. Otomatik retry/fallback yoktur.
7. Metadata kontrolleri ayrı toplam 10 deneme tavanına sahiptir. `modeller`
   yalnız ilk sayfayı alır; model seçmez veya kendiliğinden sayfa istemez.
8. Anahtar karakterleri, URL/model tutarlılığı ve yanıt boyutu denetlenir.

## Kanıt

- Yeni `tests/test_api_self_audit.py`: 17 test. Metadata/üretim ayrımı, salt-okunur
  durum, sayaçlar, 404/503 ve tekrar yapılmaması, gizli bilgi, yönlendirme reddi,
  token kayıtları, model seçmeme, sınırlar, aşırı yanıt ve interaktif CLI kapsamı.
- Üç ardışık tam paket çalıştırması: her birinde **180 test, 179 başarılı,
  1 atlanan**, sıfır hata. Loglar `full-tests-1.txt`–`full-tests-3.txt`;
  süreler ve çıkış kodları `repeated-tests.json` içinde.
- Son kullanım temizleme düzeltmesinden sonra tam paket tekrar çalıştırıldı:
  **180 test, 179 başarılı, 1 atlanan** (`final-tests.txt`).
- Atlanan test eksik tarihsel v3.1 ham veri arşivine bağlıdır; gizlenmedi.
- `compileall` ve CRLF uyumlu `git diff --check` başarılı.
- Araştırma sonuçları, donmuş kaynaklar, katsayılar ve siyasi davranış kuralları
  değiştirilmedi; gündem katmanındaki değişiklik yalnız hata/kullanım kaydıdır.

## Kalan sınırlar

Bu sınırlı, tekrarlanabilir bir kod denetimidir; kesintisiz gözetim veya hatasızlık
sertifikası değildir. Yönlendirme testi handler seviyesindedir, gerçek TLS/proxy
zinciri testi değildir. Socket timeout toplam duvar saati sınırı değildir.
Yeni metadata ayrımı eski üretim hatasının kendisini çözmüş sayılmaz. Gerçek
uç nokta/model/hesap desteği bilinmeden 404 çözüldü denmemelidir.
