# v3.1 — rahatsızlık, destek ve gerçek katılım ayrımı

## Uygulanan ilk aşama

- **Ekonomik zarar tek başına temel yönelimi düşürmüyor.** Bu aşamada ideolojinin içeriği tasarlanmadığından yeni bir otomatik ideoloji-değişim kuralı eklenmedi. Mevcut `core_orientation`, ideolojinin tüm içeriği sayılmıyor.
- **Desteği çekmek ayrı eylem:** `withdraw_support` kamu desteğini sıfırlar/kamu bağlılığını tarafsız yapar; kişinin siyasi bağlılığını, özel sadakatini veya temel yönelimini değiştirmez. Referans politika, yerel sorumluluk atfı ve nötr düzeyin altına inmiş özel sadakat varsa bunu kendi seçebilir. Karşı tarafı desteklemek zorunlu değildir.
- **Davet, katılım değildir.** Kayıtlı bir buluşma, başlangıç/bitiş zamanı ve yer etiketi var. Katılım açık bir eylem; aynı anda iki buluşmaya katılınamaz. Yalnız kalan kişi kolektif güç kazanmaz. En az iki gerçek katılımcı birlikteyken barışçıl ortak ifade durumu oluşur; ayrılınca/buluşma bitince söner. Özel rahatsızlık ayrıca devam edebilir.
- **Yerel bilgi:** davet yalnız okununca öğrenilir. Katılmayanlara küresel katılımcı sayısı gösterilmez. Mesaj başlıkları artık gizli bağlılığı değil kamuya açıklanmış bağlılığı taşır.
- İlk iki kesimin mevkili-kaynak kapısı katılım kararında da korunur. Önce akrandan davet duymak, daha sonra güvenilen mevkili açıklamasını kabul etmeyi engellemez; aynı kaynağın tekrarları yeni katılımcı sayılmaz. Gözlemciler referans politikada kendiliğinden toplu eyleme katılmaz. Başka birinin buluşmasına mevkili/zengin katılımı için gelir bağımlılığı kaybı gerekir; kendi düzenledikleri buluşma ayrı değerlendirilir. Bunlar kapsamlı burjuva stratejisi değil, bu aşamanın açık sınırlı kurallarıdır.

## Gerçekten çalıştırılan kontroller

**99 test geçti; önceki 84 test silinmedi.** Yeni 15 test; uzun süreli ekonomik baskı/temel yönelim ayrımını, ayrı destek çekmeyi, kaynak kapılarını, okunmamış daveti, yalnızlığı, gerçek katılımı, ayrılmayı, bütçeleri, özel/kamu bilgisini ve kaydet/devamı sınar.

Beş tohum × iki koşuldan oluşan **10 kısa kontrol koşusu** ayrıca çalıştırıldı:

| Durum | Gerçek katılımcı | Kolektif ifade |
|---|---:|---|
| Davetler okunuyor; katılım engelleniyor | her tohumda 0 | oluşmadı |
| Aynı çağrıda özerk katılım açık | 9, 7, 5, 6, 4 | katılımla oluştu; bitişte her koşuda söndü |

Aynı tohum çiftlerinde ekonomik kayıp eşitti. Rahatsızlık sürerken buluşmanın bitebilmesi doğrulandı. Bu kısa kontrol, ideoloji değişiminin uzun dönem kanıtı değildir; uzun baskı ayrımı ayrıca hedefli birim testinde sınandı. Katılım sonrası iletişim akışı farklılaşabilir; çalışma yalnız fiziksel katılım kontrolüdür, geniş nedensel/gerçekçilik deneyi değildir.

Eski **v2** korundu. **v3.0** da `behavior-v3.json` olarak donduruldu; eski 120 koşuluk betik artık açıkça o profili kullanır. Bir v3.0 koşusunun bütün ajanları ve olay günlüğü arşivle birebir tekrarlandı; eski v2 teşhis analizörü de çalıştırıldı. `groups`, `dynamics`, `belief_step` sayıları değişmedi; sonuçları %20–30'a yaklaştırmak için ayar yapılmadı.

## Sınırlar — çözülmüş sayılmamalı

- Toplantıyı başlatma bu aşamada senaryo müdahalesi; davet sonrası katılım özerk. Coğrafi ulaşım, şiddet veya kurumları değiştiren bir isyan motoru yok. Yer, soyut buluşma etiketi; takvim doğrulanmış, kalabalık vaadi yok.
- Güç endeksi `(katılımcı−1)/katılımcı`, yerel birlikte bulunma göstergesidir; toplumun güç yüzdesi değildir. Kitle içi bütün psikolojik yönlendirmelerin doğrulandığı iddia edilmiyor.
- Katılım için mevcut kişisel risk/ekonomik rahatsızlık ve kaynak güveni kullanılıyor; karar karşılaştırması `rahatsızlık × risk + kaynak güvenilirliği > 1 − risk`. Bu bir model varsayımıdır, doğrulanmış psikoloji yasası değildir. Eylemler günlük bütçeden düşer; buluşma süresi en fazla bir gün.
- Alışma/beklenti güncellemesi, ideolojilerin içeriği, burjuvaların bütün çıkar stratejileri, iletişim rejimleri ve v3.0 denetimindeki tarafsızların ilk kutup geçişi sorunu bu aşamada yeniden tasarlanmadı. Hepsinin çözüldüğü söylenmiyor.

[Test çıktısı](collective-tests.txt) · [10 koşunun verisi](collective-check.json) · [Tarihsel tekrar kontrolü](collective-legacy-check.txt)

```bash
python -m unittest discover -s tests -v
python -m society.collective_check
```

Yeni eylemler: `create_gathering(place,start,end)`, `attend_gathering(gathering_id)`, `leave_gathering(gathering_id)`, `withdraw_support`. Normal `send` eylemine `gathering_id` eklemek, bilinen buluşmanın davetini sınırlı ağdan yollar. Bunlar JSON proposal alanlarıdır; Python fonksiyon çağrısı imzaları değildir.
