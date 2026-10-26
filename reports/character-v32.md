# v3.2 — yerel karakter davranışı düzenlemesi

25 Ekim 2026. Bu bir **uygulama ve mekanizma kontrolü** raporudur; toplumsal
geçerlilik, gerçek dünyada değişim olasılığı veya altı karakterin bütün ayrıntılarıyla
tamamlandığı iddiası değildir. Katsayılar çıktı oranlarına göre ayarlanmadı.

## Uygulanan ayrımlar

### 1. Burjuva / yönetici (%15)

- Kendi ya da karşı tarafın açıklamaları sıradan inanç, fayda, sorumluluk veya
  akran etkisi yoluna alınmıyor. Söylem, kaynağı bilinen ama doğruluğu kabul
  edilmemiş stratejik sinyal olarak tutuluyor.
- Yerel olarak bilinen yöneticilerle kurumsal konum rekabeti var. Kişinin mevcut
  konumu, risk tercihi, kendi kaynakları, geçim rezervi ve doğrudan yaşadığı
  meydan okumalar eylemi belirliyor. Rakibin gizli parası/bugünkü gücü okunmuyor.
- Rekabet kaynak harcıyor, sınırlı konum aktarıyor ve bekleme süresine tabi.
  Toplam kurumsal konum korunuyor. Kişiler aynı anda aynı davranışı yapmak
  zorunda değil; risk tercihi ve yerel ilişki bilgisi farklı.
- Kurumsal gücü azalan yöneticinin mevcut sözleşme iptali etkisi de sınırlanıyor.
  Zenginlerin yöneticiye bağımlılığı tersine çevrilmedi.
- Rekabet kendi başına parti veya temel yönelim değişimi değil. Genel taraf
  değiştirme yoluna kategorik bir rol yasağı konmadı; fakat doğrulanmamış
  açıklamalar bu kesimde alternatif çekiciliği üretmiyor.

**Sınır:** Tek boyutlu, sıfır toplamlı bir kurumsal konum soyutlamasıdır. Tam
pazar/pazarlık, farklı politika programları, çok boyutlu yönetici çıkarları ve
kurumsal çıkar nedeniyle nadir stratejik parti anlaşmaları henüz modellenmedi.

### 2. Gözlemci (%3)

- Aynı oranda korunuyor; başlangıç gelişim düzeyi kişiye göre değişiyor.
  Bu örnekleme, diğer grupların rastgelelik akışını değiştirmiyor.
- Günde bir kez, azalan marjinal ilerlemeyle öz-gelişim yapıyor. Başlangıçta az
  bağlantı; günlük okuma ve gönderme için ayrıca düşük tavanlar var.
- Temel politika otomatik propaganda aktarmıyor. Söylemleri doğru kabul etmiyor.
- Yalnız daha sonra gerçekten yaşadığı ekonomik sonuçla karşılaştırılabilen,
  süresi geçmemiş tahminleri bir kez inceliyor. İnceleme, başka önermeleri
  doğrulanmış gerçek yapmıyor; kişisel sonuç da küresel doğruluk sayılmıyor.

**Sınır:** Öz-gelişim tam bir muhakeme/ideoloji motoru değil; diğer insanları
aydınlatma veya kurtarma etkisi eklenmedi.

### 3. Ani deneyim / uzayan deneyim

Kişisel yaşam maliyeti, gelir güvencesi ve doğrudan bildirilen yerel kesintilerde:

- Beklenen düzeyden pozitif sapma **sürpriz** üretiyor.
- Beklenen düzey zamanla güncelleniyor: **alışma**.
- Süren olumsuz düzey ayrıca **yıpranma** biriktiriyor; düzelince yavaş azalıyor.
- Yerel kesinti aynı gün tepki üretebiliyor. Başka kişilere otomatik yayılmıyor.
- Gerçek para kaybı eski muhasebede kalıyor; psikolojik tepki para kaybı diye
  yazılmıyor. Kesintinin nedenine dair siyasi sorumluluk uydurulmuyor.

`local_disruption` idari senaryo girdisidir; ajana dünyayı değiştirme yetkisi
vermez. Örnek: `{"target":"A0088","domain":"transport","severity":0.3}`.
Gerçek fiyat/gelir etkisi de isteniyorsa ayrıca gerçek ekonomi müdahalesi gerekir.
Bu mekanizma hazırlık yatırımı veya stok yönetimi içermez; beklenti güncellemesi
ve alışma bunun yerine tam bir hazırlık modeli olarak sunulmamalıdır.

### 4. Aynı yer ≠ aynı toplantı ≠ onay ≠ taraf değişimi

- Aynı yerde ve aynı anda fiilen bulunanlar, farklı kayıt numaralarında da
  birbirlerini görüyor. Geliş, ayrılış ve kapanışta görünüm yenileniyor.
- `attend_gathering` artık v3.2'de varsayılan olarak **gözlem katılımıdır**.
  Kolektif desteğe sayılmak için açık `participation: "support"` gerekir.
  Temel politikanın bilinçli ifade katılımları bu alanı açıkça veriyor.
- Ayrı toplantılar ancak açıkça aynı `purpose` verilmişse destek havuzunu
  paylaşabilir. Amaç boşsa birleştirme yok; `support:A` ve `support:B` ayrı kalır.
- Ortak bir konuda destek veren A ve B kişilerinin partisi yine değişmez.
  Beden sayısı, davet veya destek mesajı kendiliğinden parti dönüşümü değildir.
- Yerinde görülen diğer toplantı, otomatik katılım, güvenilir davet, onay veya
  uzaktan bilinen bir takvim kaydı haline getirilmiyor.

**Sınır:** Konumlar ayrık yer etiketleri; görüş mesafesi/ulaşım/coğrafya yok.
Aynı amaç etiketi, senaryonun açık ortak amaç beyanıdır; dilsel anlam çözümlemesi yok.

### 5. Sessizlik ve başka tepkiler

Bütün kişiler için günlük referans değerlendirmesi kaydediliyor. Karar
çağrısında da gerekçe ve önerilen/uygulanan eylem ayrı izlenebiliyor. Örnekler:
kişisel sıkıntı yok; okunmuş yerel destek yok; risk yerel hazırlığı aşıyor;
bilinen gelecek toplantı var; örgütlenme bekleme süresi; iletişim bütçesi dolu;
uygun yerel kurumsal fırsat yok; öz-gelişim tercih ediliyor.

Tepkisel huzursuzlar kişisel sıkıntıyı yakın temaslarına iletebilir. Ancak
okunmuş başka bir kişinin ilgisi ve yeterli risk/hazırlık olmadan toplantı
örgütlemiyorlar. Kayıt ve davet kimseyi gelmiş saymıyor. Desteği çekme, temel
yönelimi/partiyi değiştirmiyor. Geri destek için sadece iyi tahmin yetmiyor:
kişisel ekonomik düzelme kanıtı ve yeterli özel bağlılık da gerekiyor.

**Sınır:** Pazarlık, mekânsal kaçınma ve her kesim için ayrı alternatif eylemler
henüz yok. Eylemsizlik bu eksik mekanizmaların sosyal olarak gereksiz olduğunu
kanıtlamaz. Özel sağlayıcı kullanılırsa kaydedilen gerekçe, sağlayıcının içsel
nedeni değil **referans politika gerekçesidir** (`reason_scope`).

## Sürüm ve varsayım koruması

- Varsayılan: `behavior.json`, v3.2.0. Önceki varsayılanın birebir kopyası:
  `behavior-v31.json`. v2 ve v3.0 profilleri de yerinde.
- Altı grup, oranları ve eski grup parametreleri / `dynamics` / `belief_step`
  değiştirilmedi. Yeni varsayımlar ayrı `character_dynamics` bölümünde.
- Alışma 14 gün, yıpranma 90 gün; çalışma adımı .02; gözlemci giriş/okuma/
  iletişim tavanları 1; rekabet maliyeti 2, aktarım tavanı .1, kurumsal hedef
  risk ölçeği .5; rekabet ve örgütlenme bekleme süreleri 7 gün.
  Bunlar **doğrulanmamış tasarım varsayımları**, bulunmuş toplum sabitleri değil.
- Eski araştırma ve eski kolektif kontrol komutları açıkça v3.1'e sabitlendi.
  Tarihsel 612 koşuluk araştırma ve dondurulmuş kaynak arşivi değiştirilmedi.
- Yeni kayıtların kaydet/yükle/devam et sonucu birebir eşleşmesi test ediliyor.

## Çalıştırılan kontroller

```bash
python -m unittest discover -s tests -v
python -m society.character_v32_check
python -m compileall -q society tests
```

[Test günlüğü](character-v32-tests.txt): **127 test, 126 başarılı, 1 atlanan**.
Yeni karakter sözleşmeleri için 20 test: iki tarafın söylemini karantinaya alma,
seyrek iletişim ve bütçeler, gelişim, zaman/süre sınırı olan kişisel inceleme,
rekabet kaynak/yetki/yerel bilgi koşulları, otonom ilerleme, sürpriz/yıpranma,
yerel kesinti, görünürlük/onay ayrımı, destek ayrımı, yerel ilgiyle örgütlenme,
sessizlik gerekçesi ve birebir kaydet/yükle devam kontrolü.
Atlanan test, önceki deneyin ham tarihsel dosyası bulunmadığı için
çalıştırılamayan arşiv karşılaştırmasıdır. Bu atlama gizlenmedi; ayrıca yeni
v3.1 donmuş-kaynak karşılaştırması çalıştırıldı. API veya arayüz eklenmedi.

[24 koşuluk küçük karşılaştırma](character-v32-check.json): dört tohum
(0, 44, 101, 777), 100 kişi, 92 günlük makbuz. Her tohumda v3.1/v3.2 fiyat
ani-kademeli çifti ve yalnız v3.2'de desteklenen yerel fiyat-dışı çift var.

- İki uçta da 90. gün +%30'a ulaşılır. Ani senaryoda 90. gün tek artış;
  kademelide 1–90. günler eşit düzey adımları. Sonuç 91. günün sonunda alınır.
  **Birikimli maruziyet eşit değildir**: toplam gerçek fiyat zararı ani için
  120, kademeli için 5.460 birimdir; iki sürümde aynı. Bu fark alışmaya mal edilmedi.
- Yeni modelde son maliyet/kesinti tepkisi ani için yaklaşık **.3033**,
  kademeli için **.1585**. Buna karşılık yıpranma ani **.0033**, kademeli
  **.1119**: uzayan deneyim daha az sürpriz ama daha çok birikim taşıyor.
- Fiyat-dışı kişisel kesinti tek başına para kaybı yazmadı.
- Yeni koşularda tohuma göre **151–175** kurumsal yarışma ve her koşuda
  **276** öz-gelişim eylemi var. Bunlar 92 günde bütün kesimin toplamı;
  her yöneticinin veya gözlemcinin aynı sonucu aldığı anlamına gelmiyor.
- Bu dar müdahalelerde **parti/temel yönelim değişimi, destek çekme ve toplantı
  oluşmadı**. Bu sonuç hedef değil, bir sınır: düzenli fiyat baskısının kendisi
  okunmuş ortak ilgi veya siyasi sorumluluk yaratmıyor. Örgütlenme mekanizmasının
  tetiklenmesi ayrı kontrollü sözleşme testinde doğrulandı.
- Donmuş kaynak arşivindeki v3.1 ile bugünkü motorda açık v3.1 profilinin
  **10 günlük tam kayıtları byte düzeyinde aynı** çıktı. Şok, yerel tahmin
  mesajı ve temel politika içeren bu kontrol tek bir senaryodur; bütün tarihsel
  araştırmanın yeniden üretildiği iddia edilmiyor. Profil byte'ları da aynı.

Kanıt JSON'unda koşu bazlı sayılar, karar gerekçeleri, kaynak hashleri ve eski
arşivle karşılaştırılan tam kayıt hashleri bulunuyor. Eski araştırma manifesti
bugünkü kodun manifesti olarak kullanılmıyor.
