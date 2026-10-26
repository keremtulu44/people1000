# Ekonomik sorumluluk ve alternatif fayda — küçük v2/v3 karşılaştırması

## Kodda bulunan iki sorun ve kapsam
`dynamics.daily` içinde ekonomik burden doğrudan evidence_economic terimine giriyordu. Aynı fonksiyondaki `.35 if alt in known_poles` bilinirliği otomatik çekicilik yapıyordu; muhalefet/çıkar ekleri de sıfırdan çekicilik üretebiliyordu.
Bunlar ayrı appraisal değerlendirmesiyle değiştirildi. Olay motoru, ilişki ağı, bütçeler ve karar doğrulama mimarisi yeniden tasarlanmadı. AI API/panel eklenmedi.

## Değişiklikler
- Varsayılan profil v3.0.0; eski v2.0.0 `society/behavior-v2.json` içinde korunuyor. groups, dynamics ve belief_step sayısal değerleri birebir aynı. Herhangi bir hedef değişim oranına göre katsayı ayarlanmadı.
- Sorumluluk: A, B, belirli yönetici, dış koşullar ve belirsiz neden ayrı hipotezler. Bilgi yoksa unknown=1. Okunmuş ifadeler kaynak güveniyle iskonto edilir; ifade doğrulanmış dünya gerçeği sayılmaz. Aynı kaynağın tekrarları bağımsız doğrulama gibi biriktirilmez.
- Fiziksel yük aynen birikir. Yeni zararın siyasi kısmı o anda algılanan sorumlu kutba yazılır. Geçmiş belirsiz kayıp, sonradan gelen suçlamayla geriye dönük etiketlenmez; A’ya yazılan yük, kişi B’ye geçince B’ye taşınmaz. Siyasi ekonomik kanıt ve özel sadakatin ekonomik tepkisi bu ayrımdan yararlanır.
- İmzalı sözleşme iptalinde hedef, kendisine bildirilen kurum/kişi ve kamu kutbunu doğrudan deneyimler. Bu atıf yalnız gelir kaybı içindir; aynı kişinin fiyat artışını da otomatik olarak o yöneticiye bağlamaz. İlgisiz ajanlar haberdar edilmez.
- Alternatif bilinirliği ayrı kayıttır ve fayda vermez. Ekonomik güvenlik, statü ve düzen konularındaki okunmuş beklenen iyileşme ifadeleri kaynak güveni ve konu direnciyle değerlendirilir. Konu görüşü/kişisel ekonomik duyarlılık, yaşanan zarar ve temel yönelim göreli çıkar ağırlıklarını belirler.
- Çekicilik, kanıtla desteklenen alternatif iyileşmesi eksi mevcut taraf için bilinen pozitif iyileşmedir; bilinmeyen alternatif, sırf mevcut taraf kötü diye fayda kazanmaz. Kesim ekleri yalnız mevcut kanıta bağlı çarpan olabilir; sıfır faydayı pozitif yapmaz.

## Gerçekten çalıştırılan küçük deney
120 koşu; 100 ajan, 5 eşleştirilmiş tohum, 30 gün; 3 şok × 2 atıf × 2 fayda × 2 sürüm. Toplam kayıt/sıkıştırma dahil 52.52 saniye.
Ağ değiştirilmedi. Aynı A-yakını yönetici, mevcut iki A-kamu bağlılıklı ve B’yi tanıyan ağ çapasıyla iletişim kuruyor. Mevcut-kutup atfı bu başlangıç A kohortu için A atfıdır; bütün nüfusun gizli bağlılığı okunup kişiye göre mesaj üretilmez. Yayılım diğer kişilere normal ağdan olur.
Belirsiz koşulda unknown ifadesi; diğerinde responsibility:A ifadesi kullanılır. Olumlu fayda koşulunda üç konuya ilişkin olumlu ifadeler, bilinirlik kontrolünde aynı zaman/kanallardan yalnız B’yi anan mesajlar gider. Her kaynakta günlük iki gönderim sınırı korunur. Pozitif ifade deneysel tanıklıktır, gerçek bir ekonomik iyileşme gerçekleşmiş sayılmaz.
Başlangıç ajan/ağ hashleri her tohumun bütün kollarında eşit; aynı şok/tohumda parasal kayıplar da bütün kollarda eşit doğrulandı. Ortalama fayda mesajı/bilinirlik erişimi her koşulda 17.6 kişiydi; eski/yeni farkı daha az erişim sağlanarak üretilmedi.
Bütçe kontrolü 384 otonom yeniden-aktarım denemesini reddetti (bir tohumun 24 kolunda 16’şar); zorlanan gönderimlerden reddedilen yok. Reddedilen denemeler ücretsiz başarılı eylem sayılmadı.

| Şok | Atıf | Alternatif | Eski değişen kişi % ort. | Yeni % ort. | Yeni tohum min–maks % |
|---|---|---|---:|---:|---:|
| %0 | belirsiz | yalnız bilinirlik | 0.00 | 0.00 | 0–0 |
| %0 | belirsiz | olumlu kanıt | 0.00 | 0.00 | 0–0 |
| %0 | A/mevcut | yalnız bilinirlik | 0.00 | 0.00 | 0–0 |
| %0 | A/mevcut | olumlu kanıt | 0.00 | 0.00 | 0–0 |
| %40 | belirsiz | yalnız bilinirlik | 0.60 | 0.00 | 0–0 |
| %40 | belirsiz | olumlu kanıt | 0.60 | 0.00 | 0–0 |
| %40 | A/mevcut | yalnız bilinirlik | 0.60 | 0.00 | 0–0 |
| %40 | A/mevcut | olumlu kanıt | 0.60 | 1.60 | 0–4 |
| %80 | belirsiz | yalnız bilinirlik | 71.00 | 0.00 | 0–0 |
| %80 | belirsiz | olumlu kanıt | 71.00 | 0.00 | 0–0 |
| %80 | A/mevcut | yalnız bilinirlik | 71.00 | 0.00 | 0–0 |
| %80 | A/mevcut | olumlu kanıt | 71.00 | 6.80 | 4–12 |

## Yorum ve sınırlar
Yeni modelde bu pilotta belirsiz atıf veya yalnız bilinirlik tek başına ekonomik şoku siyasi geçişe çevirmedi. İki bilgi birlikteyken orta şokta ortalama %1.6, ağır şokta %6.8 geçiş görüldü. Orta şokta eski %0.6 değerinin üstüne çıkılması, düzeltmenin her sonucu zorunlu olarak aşağı bastırmadığını gösterir.
Bu, yeni oranların gerçekçi/ideal olduğunun kanıtı değildir. Beş tohum küçük örneklemdir; kanıt yalnız sınırlı A-odaklı ağ bölgesine ulaştı. Belirsiz atıf bütün siyasi değişimleri mantıksal olarak yasaklamaz; diğer güven/akran yolları korunur. Bu koşullarda eşik aşılmaması genel değişmezlik değildir.
Kaynak ifadeleri yanlış olabilir. Atıf, güvenle iskonto edilmiş kaynak görüşlerinin karışımıdır; nesnel nedensellik olasılığı değildir. İyileşme tahminleri de gerçek kazanç değil beklenen fayda görüşüdür. Eski güven/ekonomik normalizasyon sınırlamaları ve gözlemcilerin yüksek eşikleri bu görevde değiştirilmedi.
Fayda ve genel atıf ifadeleri yeni bilgi gelene kadar saklanır; olay/konu geçerlilik süreleri ve karmaşık kanıt bağımsızlığı bu küçük düzeltmede modellenmedi. Gelir iptali tanıklığı fiyat zararına yayılmayacak şekilde kapsamlandırıldı.

## Testler ve dosyalar
Mevcut testler silinmedi. Eski v2 davranış sözleşmeleri açık legacy fixture ile korunuyor; mekanik çekirdek testleri yeni varsayılanla çalışıyor. Eski experiments/diagnosis betikleri tarihsel v2 profilini açıkça kullanıyor; eski snapshot profilleri sessizce v3’e çevrilmiyor.
Yeni testler: zarar/atıf ayrımı, bilinirlilik/fayda ayrımı, güven ve konu direnci, okunmamış bilgi, dış/leader atfı, geçişte yük taşınmaması, geç gelen atfın geçmişi değiştirmemesi, gelir kapsamı, pozitif koşullarda gerçek değişim, gizli dünya/kaynak değişimleri, tekrar ve kaydet/devam.
Kaynaklar: appraisal.py; dynamics.py ve engine.py dar entegrasyonları; behavior.py sürüm seçimi; appraisal_trial.py küçük deney betiği. Profiller behavior.json / behavior-v2.json. Ham koşu sonuçları reports/appraisal/results.csv; özet ve protokol aynı klasörde; tam snapshotlar runs/appraisal/ altında Git dışında.
Eklenen deney testinde ilk çalıştırmada profil alanı adı hatalıydı (version yerine behavior_version). Hata düzeltilip tam paket yeniden çalıştırıldı; başarısız ilk çıktı appraisal-tests-initial-trial-failure.txt içinde saklandı.
Gerçek test çıktısı reports/appraisal-tests.txt. Komutlar:
```bash
python -m unittest discover -s tests -v > reports/appraisal-tests.txt 2>&1
python -m society.appraisal_trial > reports/appraisal-trial-log.txt 2>&1
```
Son kaydedilmiş tam paket: 84 test; OK. Ham çıktı esas alınmalıdır.
