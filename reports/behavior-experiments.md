# Birikimli davranış — çalıştırılmış deneyler ve değerlendirme

Tarih: 2026-10-25. Model: davranış v2.0.0; deney protokolü v1.1.0.
**Bu sonuçlar gerçek toplumlar hakkında kanıt değildir.** Tüm sayılar çalıştırılmış koşulardan üretilmiştir.

## 1. Kapsam ve önceden belirlenen protokol
Nihai veri: **260 tamamlanmış 30 günlük koşu**. Her iki nüfusta A/B/C/D × 20 eşleştirilmiş tohum = 160 ana koşu. 100 kişide beş ek kol × 20 = 100 tamamlayıcı koşu.
Koşu betiğinin toplam duvar süresi (sıkıştırma/kayıt dahil): 211.33 saniye.
A: dakika 60’ta fiyat ×1.8; B: aynı şok + gün 1/8/15/22’de iki erişilebilir alıcıya yönetici tahmini; C: aynı açıklama yalnızca BFS ağ bölgesine; D: B, birikimli modül kapalı.
Ek kollar: iki kat güven aşınması, düşük bağlılık eşiği, düşük gözlemci temel direnci, tek baskı eylemi ve gün 22’de doğru tahmine geçiş.
Güçlü %80 fiyat şoku özellikle stres koşuludur. Doğal/toplumsal sıklık iddiası yoktur. Başarı beklenen siyasi sonuç değildir.
Profil ve protokol deneyden önce `behavior-protocol.json` içine yazıldı. Ana koşular arasında sonuca göre katsayı ayarı yapılmadı.

## 2. Toplu sonuçlar
Aşağıdaki geçiş sayısı **olay sayısıdır**, benzersiz kişi sayısı değildir. Sonraki sütun benzersiz kişileri gösterir.

| Nüfus | Kol | Geçiş ort. | Değişen kişi ort. | Erişen kişi ort. | Açık–özel şiddet farkı | Güven aşınması olayı | Temel değişim |
|---:|---|---:|---:|---:|---:|---:|---:|
| 100 | A | 71.850 | 71.800 | 0.000 | 0.233 | 0.000 | 0.000 |
| 100 | B | 74.150 | 73.350 | 20.700 | 0.231 | 180.950 | 0.000 |
| 100 | C | 72.550 | 72.400 | 5.350 | 0.232 | 48.800 | 0.000 |
| 100 | D | 0.000 | 0.000 | 20.700 | 0.000 | 0.000 | 0.000 |
| 100 | erosion_fast | 74.150 | 73.350 | 20.700 | 0.231 | 95.850 | 0.000 |
| 100 | observer_less_resistant | 74.150 | 73.350 | 20.700 | 0.231 | 180.950 | 0.000 |
| 100 | pressure | 74.150 | 73.350 | 20.700 | 0.231 | 180.950 | 0.000 |
| 100 | recovery | 73.750 | 73.250 | 20.700 | 0.232 | 180.950 | 0.000 |
| 100 | threshold_low | 98.550 | 85.900 | 20.700 | 0.228 | 180.950 | 0.000 |
| 1000 | A | 729.950 | 728.700 | 0.000 | 0.228 | 0.000 | 0.000 |
| 1000 | B | 736.100 | 732.050 | 56.200 | 0.227 | 464.300 | 0.000 |
| 1000 | C | 730.850 | 729.300 | 6.750 | 0.228 | 58.300 | 0.000 |
| 1000 | D | 0.000 | 0.000 | 56.200 | 0.000 | 0.000 | 0.000 |

## 3. Eşleştirilmiş farklar ve tohumlar arası değişkenlik
Farklar aynı tohumdaki deney eksi kontrol. Aralıklar 1.96×standart hata normal yaklaşımıdır; 20 tohumda betimleyici, çoklu test düzeltmesiz ve gerçek topluma genellenemez.

| Karşılaştırma | Geçiş farkı ort. | Yaklaşık %95 aralık | Pozitif / sıfır / negatif tohum |
|---|---:|---|---|
| 100:B-A | 2.300 | [1.729451971669712, 2.8705480283302878] | 17 / 3 / 0 |
| 100:C-B | -1.600 | [-2.158006979771476, -1.0419930202285244] | 0 / 5 / 15 |
| 100:D-B | -74.150 | [-75.53793379183819, -72.76206620816183] | 0 / 0 / 20 |
| 100:erosion_fast-B | 0.000 | [0.0, 0.0] | 0 / 20 / 0 |
| 100:threshold_low-B | 24.400 | [22.181601525993653, 26.618398474006344] | 20 / 0 / 0 |
| 100:observer_less_resistant-B | 0.000 | [0.0, 0.0] | 0 / 20 / 0 |
| 100:pressure-B | 0.000 | [0.0, 0.0] | 0 / 20 / 0 |
| 100:recovery-B | -0.400 | [-0.6982672768190514, -0.10173272318094867] | 0 / 14 / 6 |
| 1000:B-A | 6.150 | [4.321971956912098, 7.978028043087903] | 20 / 0 / 0 |
| 1000:C-B | -5.250 | [-6.967393067229637, -3.5326069327703626] | 0 / 0 / 20 |
| 1000:D-B | -736.100 | [-739.6941460006077, -732.5058539993923] | 0 / 0 / 20 |

JSON ayrıca her metrik için ortalama, medyan, min/maks, standart sapma ve betimleyici aralığı içerir.

## 4. Yerellik, algı ve bilgi yayılımı
Tüm 260 kayıtta işlenmiş olay kimliği tekrar toplamı: 0; C kapsamı dışındaki okuma: 0; son durum bütçe ihlali: 0.
Okunmamış mesaja dayanan güven/kanaat güncellemesi için ölçülen sızıntı toplamı: 0.
Sızıntı denetimi kayıtlı kanıt/öğrenme zamanını denetler; her olası yazılım hatasının bulunacağı iddiası değildir. Başlangıç kamu ilişkileri deney tanımının parçasıdır.
Ajanlar açıklamayı almadan da kendi giderlerini yaşayıp tepki verebilir. `unreached_switches` ve `unreached_topic_changes` bu yüzden tek başına sızıntı değildir.
Gerçek–algı hatası, economic_outlook kanaati olanlarda gerçek normalize zarar ile kanaat farkıdır; örneklem dışındakilere hata=0 atanmaz. Ekonomik kendi deneyimi ayrı experienced_harm konusudur.
Aşağıdaki ağ bölgesi ilk iki alıcıdan BFS ile seçilen nüfusun dörtte biridir; yönlü iletişim yolları değiştirilmez. Boş bölgede süre yoktur (—).

| Nüfus/kol | Yerel ilk erişim ort. dk | Dış ilk erişim ort. dk | Dış okuma ort. | Algı hatası ort. |
|---|---:|---:|---:|---:|
| 100:A | — | — | 0.000 | — |
| 100:B | 33.200 | 199.250 | 60.800 | 0.361 |
| 100:C | 33.200 | — | 0.000 | 0.371 |
| 100:D | 33.200 | 199.250 | 60.800 | 0.610 |
| 1000:A | — | — | 0.000 | — |
| 1000:B | 38.550 | 294.600 | 203.400 | 0.357 |
| 1000:C | 38.550 | — | 0.000 | 0.363 |
| 1000:D | 38.550 | 294.600 | 203.400 | 0.614 |

## 5. Güven, baskı, ekonomi ve eylemler
Yanlış tahmin yalnızca okunduktan sonraki günlük kişisel gözlemle güven aşındırır. Güven toparlanması doğru yeni tahminle mümkündür; tam toparlanmayan kaynak–ajan çiftleri sağdan sansürlüdür. İlk düzeye dönmemek “asla toparlanmaz” anlamına gelmez.

| Kol | Güven artışı olayı ort. | Tam toparlanan çift ort. | Sansürlü çift ort. | Reddedilen eylem ort. |
|---|---:|---:|---:|---:|
| 100:B | 0.000 | 0.000 | 20.700 | 0.800 |
| 100:recovery | 143.450 | 0.000 | 20.700 | 0.800 |
| 100:pressure | 0.000 | 0.000 | 20.700 | 0.800 |
| 1000:B | 0.000 | 0.000 | 56.200 | 0.200 |
Ekonomik kayıp dağılımları her koşunun metrics.json dosyasında kişi/kesim listeleriyle saklanır. Gelirler dışsaldır; bu model davranışlardan piyasaya geri beslenen tam ekonomi değildir. Bu nedenle A/B/C/D ekonomik kayıplarının eşit kalması beklenir.
Baskı kolunda bir yetkili, kendisine bağımlı zengine baskı yapar: uygulayanın kaynağı 2 azalır, hedefin kamu desteği pressure_response kadar artar, özel sadakat aynı anda değişmez. Hedef bunu doğrudan bilir; uzaktakilere otomatik yayın yoktur. Dolaylı yayılım yokluğu sonuç olarak korunur, varsayımsal etki eklenmez.
Ajan başına fiilî iletişim/eylem sayıları her koşunun metrics.json dosyasında; öneri, ret ve uygulamalar tam snapshot içindedir. Referans politika mesaj aktarır; günlük birikimli durum değişimi fiilî eylem diye sayılmaz.

## 6. Performans ve 60 günlük yeniden üretim
Koşu başına wall_seconds başlangıç oluşturma ve simülasyonu kapsar, JSON/sıkıştırmayı kapsamaz. Toplam betik süresi bunları da kapsar. RSS sütunu süreç ömrü tepe değeridir, bağımsız koşu bellek ölçümü değildir. Snapshot baytları bellek/RAM ile aynı şey değildir.

| Nüfus/kol | Süre ort. s | Olay ort. | Hafıza kaydı ort. | Snapshot MB ort. | Sıkışmış MB ort. |
|---|---:|---:|---:|---:|---:|---:|
| 100:B | 0.135 | 6372.600 | 3098.800 | 3.464 | 0.523 |
| 1000:B | 1.676 | 60951.000 | 30291.400 | 29.211 | 4.348 |
- 100 kişilik evrede Linux süreç tepe RSS maksimumu: 55.30 MiB (bağımsız koşuya ait izole RAM ölçümü değildir).
- 1000 kişilik evrede Linux süreç tepe RSS maksimumu: 260.20 MiB (bağımsız koşuya ait izole RAM ölçümü değildir).
- 100 ajan, 60 gün, tohum 19: tam koşu, tekrar ve 15. günden kayıttan devam olmak üzere 3 tamamlanmış yörünge. Tam JSON SHA-256 eşitliği: **True**. Toplam doğrulama süresi 1.233 s; hashler behavior-verification.json içinde.
- 1000 ajan, 60 gün, tohum 19: tam koşu, tekrar ve 15. günden kayıttan devam olmak üzere 3 tamamlanmış yörünge. Tam JSON SHA-256 eşitliği: **True**. Toplam doğrulama süresi 14.014 s; hashler behavior-verification.json içinde.

## 7. Bulguların yorumu ve beklenmedik sonuçlar
- Birikim kapalı D’de özel sadakat ve bağlılık değişmez; açık modda kendi ekonomik deneyimi açıklama olmadan da değişim üretir. Bu sonuç modülün kurallarından kaynaklanır, gerçek topluma ilişkin keşif değildir.
- Açıklamanın etkisini toplam nüfus değil erişenler taşır. Nüfus 10 katına çıkınca aynı iki ilk alıcıdan mesajın eriştiği oran aynı kalmaz. Açıklama başına erişim bütçesi nüfusla ölçeklenmediğinden 100/1000 farkı yalnızca nüfus etkisi diye yorumlanamaz.
- Güçlü şok altında geçişler yüksek çıkmıştır. Bazı ajanlar tekrar geçiş yapar; return_margin ve cooldown geçişi geciktirir ama tüm salınımları engellemez. Bu tasarımın nadir değişim hedefi için kalibrasyon sorunudur; sonuç iyi görünsün diye katsayılar sonradan değiştirilmedi.
- Alternatifin varlığı/yerel görünürlüğü basit bir çekicilik sağlar; alternatifin gelecekte gerçekten daha iyi olacağı kanıtlanmış değildir. Bu basitleştirme yüksek geçişin olası nedenidir.
- Gözlemci direnci duyarlılığında 30 günde temel değişim bulunmaması, parametrenin etkisiz olduğunu kanıtlamaz; zaman ufku varsayılan eşiklere göre kısadır. Testler sonlu, güçlü koşulda değişimi doğrular.
- Güven aşınması hızındaki artış, güven yolunu değiştirirken aynı ayrık geçiş sayısını verebilir. Tek bir toplam sonuçtan mekanizma etkisizliği çıkarılamaz.

## 8. Testler, geliştirme hataları ve gerçek tamamlanma
Son tam paket: **54 test, 54 başarılı**; ham çıktı behavior-test-results.txt. Eski 36 test korundu; davranış ve deney sözleşmeleri eklendi. Test başarısı gerçekçilik kanıtı değildir.
İlk eklemede zorunlu otomatik kamu beyanı eski bütçe testini bozdu; kaldırıldı. Sentetik gözlemci testinde seçilen eşik beklenenden erken değişime izin verdi; testin güçlü/zayıf koşulları ayrıldı. Bu başarısızlıklar nihai test çıktısında gizli bir geçiş diye sayılmadı.
60 günlük ilk 1000 kişi doğrulamasında run() varsayılan 100000 olay güvenlik sınırı doldu. Hata çıktısı behavior-verification-initial-failure.txt içinde korundu. Deney betiği artık nüfus×gün ölçeğinde açık olay bütçesi sağlar; çekirdeğin güvenlik sınırı kaldırılmadı. Son 60 günlük kontroller tamamlandı.
İlk uzun geliştirme serisi 260 koşuydu; sonra gelecekteki müdahalelerin snapshot dışında kaldığı bulundu. Kuyruk external_action olaylarıyla düzeltildi, ara kayıt eşitlik testi eklendi ve nihai 260 koşu yeniden çalıştırıldı. Ön seri runs/validation-v1 ve runs/behavior-v1 altında, nihai istatistiğe dahil değil. 16 kısa pilot da nihai örnekleme dahil değil.
Nihai analiz 260 karşılaştırmalı koşu + 6 adet 60 günlük doğrulama yörüngesini kapsar. Birim test içi koşular bağımsız deney örneklemi olarak sayılmadı.

## 9. Dosyalar ve kalan sınırlamalar
- engine.py: ayrı davranış/gün sonu olayları, durum alanları, kalıcı müdahaleler, yerel bağlam ve kayıt.
- dynamics.py: birikim, kaynak güveni, akran etkisi, ayrılma maliyeti, histerezis ve temel yönelim.
- behavior.json/behavior.py: davranış v2.0.0, katsayı doğrulama, eski profil için kapalı mod.
- experiments.py / verify_runs.py / analyze_experiments.py: önceden tanımlı koşular, sıkıştırılmış ham kayıtlar, tam tekrar doğrulaması ve bu raporun üretimi.
- tests/test_behavior.py, tests/test_experiments.py: mekanik testlerden ayrı davranış ve eşleştirilmiş deney testleri.
- docs/cumulative-behavior.md ve README: güncel semantik/komutlar. behavior-model-audit.md başlangıç kod denetimidir.
Bilinen sınırlar: tam transaction rollback yok; güvenilen yerel snapshot varsayımı; kayıtlar zamanla sınırsız büyür; kaynak kimliği doğrulanmış varsayılır; saf dil anlamı/yanlış hatırlama yok; gerçek AI yok. Kurumsal pazarlık, işten çıkarma yayılımı ve tam piyasa geri beslemesi yok. Baskının uzun vadeli özel psikolojik etkisi eklenmedi.
Varsayılan tüm yedi kesim parametresi etkin. resistance eski uyumluluk adıdır; bağımsız katsayı değildir. Bir kolda veya yetersiz zaman ufkunda sonuç değişmemesi, kod yolunun kullanılmadığı anlamına gelmez.

## 10. Öncelikli sonraki işler
1. Alternatif faydayı yalnızca görünürlükten ayırmak, güvenilir alternatif kanıtı istemek; nadir geçiş hedefini ayrı önceden kayıtlı deneyle kalibre etmek.
2. Histerezis/geri dönüş için daha uzun ve ekonomik toparlanma içeren çok tohumlu deneyler; salınım sürelerini ölçmek.
3. Sosyal kamu beyanlarının ajanlarca üretilip yayılacağı daha zengin ama bütçeli referans karar politikası; gerçek ekonomik geri besleme.
4. Transaction destekli kalıcılık, belleğin özet/ham arşiv ayrımı ve performans indeksleri.

## Yeniden çalıştırma
```bash
python -m unittest discover -s tests -v > reports/behavior-test-results.txt 2>&1
python -m society.experiments --seeds 20 --populations 100 1000 --days 30 --sensitivity
python -m society.verify_runs
python -m society.analyze_experiments
```
Rastgelelik yalnızca başlangıçta tüketilir; runtime koşulları yeni RNG çekmez. Bu sürümde eşleştirilmiş kolların başlangıç hashleri eşitliği kontrol edilmiştir. İleride koşullu rastgele karar eklenirse yalnızca aynı tohum eşleştirme garantisi vermez.
CSV/JSON/raporlar depoda; büyük tam kayıtlar Git dışında runs/ altında. Temiz checkout’tan bu komutlar ham kayıtları yeniden üretir. Duvar süreleri/hardware RSS farklı olabilir; davranış yörüngeleri aynı kod/profil ile deterministiktir.
