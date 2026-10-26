# People1000

Sınırlı bilgi ve iletişim altında 100–1000 kişinin zaman içinde değişimini
inceleyen **kapalı toplum simülasyonu**. Gerçek toplumları tahmin ettiği iddiası
yoktur. Gerçek AI API bağlantısı ve web paneli bu sürümde yoktur.

## Güncel davranış: v3.3 — normal gündem ve API karar katmanı

Sıradan atama/açıklama/kanıt gündemi, taraf ve ideoloji hesabından ayrıldı.
Önemli bilgi değişiminde aynı kamusal bağlamı paylaşan roller için özet incelemesi
var; her kişi/gün ayrı API isteği zorunlu değil. HTTPS/JSON adaptörü ve günlük
kontrol noktaları eklendi. **Gerçek ücretli API koşulmadı**; çevrimdışı referans
ve kontrollü HTTP yanıtlarıyla doğrulandı.

**808 ana koşu + 24 uygulama kontrolü + 4 müdahalesiz kontrol** tamamlandı.
150 test: 149 başarılı, 1 eski ham dosya eksikliği nedeniyle atlanan.

[Genel sonuç raporu](reports/character-v33-report.md) ·
[Uygulama ve kullanım](docs/agenda-api-implementation.md) ·
[Deney doğrulaması](reports/character-research-v33/validation.json)

```bash
python -m unittest discover -s tests -v
python -m society.character_research_v33
python tools/analyze_character_research_v33.py
```

Araştırma gerçek toplum/LLM davranışı doğrulaması değildir. 803 koşudan sonra
bir 1000-kişi deney kurulum hatası açık protokol yamasıyla düzeltildi; davranış
katsayıları değiştirilmedi. Önceki duraklatılmış 98 v3.2 koşusu karıştırılmadı.

## Tarihsel davranış: v3.2

Yöneticiler açıklamaları benimsemek yerine yerel kurumsal çıkarlarla rekabet eder;
%3 gözlemci sınırlı iletişimle, farklı başlangıç düzeylerinden öz-gelişim yürütür.
Kişisel deneyimde ani sürpriz, alışma ve biriken yıpranma ayrı tutulur.
Aynı yerdeki farklı toplantılar birbirini görür; **görmek, katılmak, desteklemek
ve taraf değiştirmek ayrı şeylerdir**. Yeni katılım eyleminde varsayılan
`participation: "observe"`; açık destek için `"support"` gerekir.
Günlük sessizlik/eylem değerlendirmeleri yerel gerekçeleriyle kaydedilir.

[Değişiklikler, kanıtlar ve sınırlar](reports/character-v32.md) ·
[24 küçük karşılaştırmanın verisi](reports/character-v32-check.json) ·
[Test çıktısı](reports/character-v32-tests.txt)

```bash
python -m unittest discover -s tests -v
python -m society.character_v32_check
```

Eski v3.1 profili `society/behavior-v31.json` içinde ayrıca korunur.
Aşağıdaki 612 koşuluk araştırma **v3.2 öncesi tarihsel bulgudur**; güncel kodun
sonuçları veya güncel kaynak hashleri olarak okunmamalıdır.

## Tarihsel karakter sözleşmesi araştırması

Davranış kuralları/katsayıları sabit tutularak **612 koşu** çalıştırıldı:
55 ana senaryo ve açıkça ayrılmış keşif kontrolleri; 100/1000 kişi, 30/180 gün.
107 test geçti; karakter kabul sonuçlarının hepsi başarılı değil.

[Kısa bulgular](reports/character-study-summary.md) ·
[Detaylı araştırma](reports/character-study-report.md) ·
[Altı grup dosyası](reports/character-study/group-dossiers.md) ·
[11×6 özellik matrisi](reports/character-study/feature-matrix.md) ·
[Yöntem ve sınırlar](docs/character-study-method.md)

```bash
python -m society.character_study
python -m society.character_study_followup
python -m society.character_study_report
```

Sonuçlar toplumsal gerçeklik doğrulaması değildir. Protokol ve model hashleri
korunur; ham veriler `runs/character-study/` altında Git dışındadır.

## Tarihsel davranış: v3.1

Ekonomik rahatsızlık tek başına temel yönelimi düşürmez. Desteği çekmek ayrı
bir eylemdir; gerçek buluşmaya katılmadan kolektif güç oluşmaz. Davet, sınırlı
iletişim ağıyla okunur; yalnız katılımcılar birlikte bulunanları görür.
[İlk aşamanın kapsamı, 99 test ve 10 kısa kontrol](reports/collective-stage1.md).
İdeoloji içeriği, alışma ve bütün karakter eksikleri henüz çözülmüş sayılmaz.

### Tarihsel v3.0 atıf/fayda düzeltmesi

Ekonomik zarar, siyasi sorumluluk ve alternatifin beklenen faydası ayrıldı.
Bilinirlik tek başına çekicilik üretmez; sorumluluk yalnız ajanın erişebildiği
mesaj/deneyimlerden çıkarılır. Sayısal profil katsayıları değiştirilmedi.
Eski profiller `society/behavior-v2.json` ve `society/behavior-v3.json` içinde korunur; ilk deney ve teşhis
komutları açıkça v2, atıf/fayda karşılaştırması ise dondurulmuş v3.0 kullanır. Eski snapshotlar kendi profilleriyle devam eder.

[Kısa değişiklik raporu ve 120 eşleştirilmiş koşunun sonuçları](reports/appraisal-change.md)
· [Ham tablo](reports/appraisal/results.csv)
· [Test çıktısı](reports/appraisal-tests.txt)

```bash
python -m society.appraisal_trial > reports/appraisal-trial-log.txt 2>&1  # dondurulmuş v3.0 karşılaştırması
python -m society.collective_check  # dondurulmuş v3.1 katılım kontrolü
```

Okunabilir mesaj konuları: `responsibility:A`, `responsibility:B`,
`responsibility:external`, `responsibility:unknown`, `responsibility:leader:<id>`;
`benefit:<A|B>:<economic_security|status|order>` ve `alternative_known:<A|B>`.
İlkinde claim 0–100 destek gücü; faydada 50 nötr, 100 iyileşme, 0 kötüleşme
ifadesidir. Bunlar tanıklıktır, doğrulanmış dünya gerçeği değildir. Bilinirlik
konusunda claim gerekmiyor. Mesajlar sıradan okuma, yetki ve bütçe kurallarına tabidir.

## Başlangıç

Python 3.11+; çekirdek ve deneyler yalnızca standart kütüphaneyi kullanır.

```bash
python -m unittest discover -s tests -v
python -m society.cli --demo --days 3 --output runs/demo.json
python -m society.cli --resume runs/demo.json --days 2 --output runs/continued.json
python -m society.cli --population 1000 --demo --days 3 --output runs/scale.json
```

`--days` mevcut andan itibaren ilerletilecek gün sayısıdır. Zaman tam sayı dakika;
günlük rutin aynı dakikadaki diğer olaylardan önce, diğerleri FIFO işlenir.
Nüfus 100'ün katıdır: başlangıç oranları 30/30/15/12/10/3 korunur.

## Çekirdek

- Başlangıç kesimi/özellikleri, siyasi bağlılık, özel sadakat, konu görüşü ve kamu
  desteği ayrı kayıtlardır.
- Yönlü, sınırlı, güven ve gecikme taşıyan bağlantılar üzerinden mesajlar yayılır.
  Asıl kaynak, aktarıcı, üretim/teslim/okuma zamanı ayrıdır.
- Günlük okuma, iletişim ve eylem bütçeleri; yetki/kaynak kontrolü ve tekrar
  uygulama koruması vardır.
- Gelir/gider, fiyat şoku ve kurumsal ekonomik bağımlılık modellenir.
- Eylemler: bekle, gönder, aktar, destek açıkla, baskı uygula, sözleşme iptal et.
- Yerel ekonomik deneyim birikir; kaynak bazlı güven aşınır/toparlanır; alternatif
  çekiciliği, çıkış maliyeti, eşikler, histerezis ve çok dirençli temel yönelim
  güncellemesi vardır.
- Olay günlüğü dünya gerçeğidir; ajanın hafızasına otomatik kopyalanmaz.
- Snapshot kuyruk, RNG, gelecek müdahaleler, deney profili ve davranış özetlerini
  saklar. Deney dalları birbirinden bağımsızdır.

Karar sağlayıcısı yalnızca kopyalanmış yerel gözlem alır; gerçek global fiyat/güç
ve başkalarının özel durumunu almaz. Referans sağlayıcı basit mesaj aktarım
politikasıdır; bir insan davranışı veya AI zekâsı iddiası yoktur. Sağlayıcıların
önerilerini motor doğrular; sağlayıcılara motor/veritabanı aracı verilmez.

## Deneyleri yeniden çalıştırma

```bash
python -m society.experiments --seeds 20 --populations 100 1000 --days 30 --sensitivity
python -m society.verify_runs
python -m society.analyze_experiments
```

Ana betik 160 A/B/C/D + 100 tamamlayıcı = **260 adet 30 günlük koşu** üretir.
Doğrulama betiği iki nüfus için 60 günlük tam koşu, tekrar ve ara kayıttan devamı
karşılaştırır. Tam durumlar sıkıştırılmış olarak `runs/` altında Git dışında;
küçük CSV/JSON ve analiz raporları `reports/` altındadır. Çalıştırma süreleri
hardware'e göre değişir; kayıt hacmi birkaç yüz MB olabilir.

## Belgeler ve gerçek sonuçlar

- [Başlangıç kod denetimi](reports/behavior-model-audit.md)
- [Güncel davranış sözleşmesi ve denklemler](docs/cumulative-behavior.md)
- [Sürümlü altı kesim profili](society/behavior.json)
- [Çalıştırılmış deneyler ve sınırlamalar](reports/behavior-experiments.md)
- [Koşu tablosu](reports/behavior-experiment-results.csv)
- [Ölçümler](reports/behavior-metrics.json)
- [Tam test çıktısı](reports/behavior-test-results.txt)
- [Önceki çekirdek denetimi — tarihsel](reports/core-audit.md)

## Önemli sınırlar

Katsayılar deneysel varsayımlardır, kalibre edilmiş toplumsal yasalar değildir.
Güçlü şok deneyinde bağlılık geçişleri yüksek çıkmıştır; “nadir değişim” hedefi
henüz kalibre edilmiş değildir. Alternatif görünürlüğü ile gerçek alternatif
faydasının ayrılması öncelikli sonraki iştir. Temel yönelim 30 günlük varsayılan
koşulda değişmemiştir; bu, sonsuza kadar değişmeyeceği anlamına gelmez.

Tam piyasa ve ekonomik para-korunumu, kapsamlı kurumsal pazarlık ve sürekli
özgün sosyal eylem üretimi yoktur. Tam transaction rollback yoktur. Snapshotlar
güvenilir yerel dosya varsayar; bellek ve denetim günlüğü zamanla büyür. Ajan
mesajları güvenilmeyen veridir; bu arayüz tek başına mutlak prompt-injection
koruması veya kötü niyetli Python sağlayıcılarına karşı sandbox değildir.

## Bağlılık değişimlerinin nedenleri: kalibrasyon öncesi teşhis

Katsayılar değiştirilmeden eski geçişler denetlendi; şoksuz, %10, %40 ve %80
şok koşulları açıklamalı/açıklamasız ve üç tek-kanal ablation ile karşılaştırıldı.

- [Nedenler ve kalibrasyon kanıtı](reports/alignment-cause-audit.md)
- [Kesim bazlı sonuçlar](reports/diagnosis/group-summary.csv)
- [Koşul bazlı sonuçlar](reports/diagnosis/condition-summary.csv)
- [Eşleştirilmiş ablation farkları](reports/diagnosis/paired-ablation-effects.csv)
- [Test çıktısı](reports/diagnosis-tests.txt)
- [Teşhis kayıtlarının anlamı](docs/alignment-diagnosis.md)

```bash
python -m society.diagnosis --legacy
python -m society.diagnosis --seeds 20 --population 100
python -m society.diagnosis --seeds 5 --population 1000
python -m society.diagnosis --seeds 20 --population 100 --peer-probe
python -m society.diagnosis --report
```

Yeni teşhis koşuları `runs/diagnosis/` altında tutulur; önceki deneyleri ezmez.
100 kişide 20 tohum ana çalışma, 1000 kişide 5 tohum keşifsel doğrulamadır.
Bu komutların tamamı standart kütüphaneyle, API olmadan çalışır.
