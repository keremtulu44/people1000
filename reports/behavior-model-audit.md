# Davranış modeli: koddan başlangıç denetimi

2026-10-25. Önceki raporlar yerine `society/engine.py`, `behavior.py`, JSON profil,
CLI ve iki test modülü okundu. Başlangıç komutu: `python -m unittest discover -s tests -q`;
36 test, OK (0.558 s). Bu sayı yeni davranışların testi değildir.

## Gerçekte bulunanlar

- `beliefs`: konu tahmini ve tek kanıt kimliği; `alignment`: kutup etiketi;
  `private_loyalty`, `public_support`: ayrı fakat çoğunlukla sabit skalerler.
- `traits`/`initial_traits`: güncel/başlangıç ayrımı var; temel yönelim değişimi yok.
- `losses`: parasal toplam; `change_evidence`: kullanılmayan alan; `pressure`: birikiyor
  ancak özel kanaate uygulanmıyor. Yönetici bazlı güven ve alternatif çekiciliği yok.
- Etkin parametreler: `pressure_response`, `topic_change_threshold`, otorite kapısı,
  `belief_step`. Diğer altı aralıktan otorite duyarlılığı dahil çoğu yalnızca bağlama
  yazılıyor. Akran direnci sayısal karar üretmiyor.
- Gelir/gider doğrudan deneyim hafızasına ekleniyor. Yönetici mesajları sadece
  erişilebilen kenarlardan teslim/okuma olaylarıyla geliyor. Ekonomik tahminle
  gerçekleşen kişisel sonuç arasında güven güncellemesi yok.
- Fiilî eylem `decisions` ve `action_applied/rejected` kayıtları; kamu beyanı otomatik
  olarak komşulara iletilmiyor. Başkasının özel desteğini öğrenme yolu olmamalı.
- Günlük rutin önce, diğer eşzamanlı olaylar FIFO. Bütçeler günde bir yenileniyor.
  Mesajlarda kaynak anlık görüntüsü, teslim ve okuma zamanları ayrılmış.
- Snapshot RNG, kuyruk, günlük defter ve yanıtları saklıyor. Yeni özet durum alanları
  snapshot'a dahil edilirse günlük davranış da aynı şekilde sürdürülebilir.
- Kuyruk olay günlüğü nedensel kimlik taşıyor; günlük son ölçümleri ve deney kimliği
  yok. Kenar/karar/yanıt aramaları lineer; uzun koşularda ölçülmeli.

## Uygulama planı (bu görevde uygulanacak)

1. Ayrı `dynamics.py`: sınırlı özet durum, yerel deneyim, kaynak bazlı güven,
   tahmin penceresi, akran kamu sinyalleri, alternatif, ayrılma bedeli ve histerezis.
2. Günlük yerel ekonomik gözlemden sonra davranış olayı; okunmuş mesajdan sonra
   mesaj etkisi. Yeni dünya bilgisi özel duruma doğrudan kopyalanmayacak.
3. Sürümlü profilin katsayılarını etkinleştirme; davranış kapalı kontrol kolu.
4. Birim/davranış/entegrasyon testleri; sonra pilot ve dondurulmuş A/B/C/D koşulları.
5. 20 eşleştirilmiş tohum, 30 gün, 100 kişi; ayrıca 1000 kişi uzun koşular ve
   duyarlılık. Ham kayıtlar `runs/behavior/`, küçük tablolar/analiz `reports/`.

Yeni denklemler deney varsayımıdır. Etkiyi üretmek için sonuçlara bakıp parametre
ayarını gizlice değiştirmek yok; pilot değişikliği varsa ayrıca kaydedilecek.

## Uygulama sonrası durum

Plan uygulanmıştır. Yedi kesim parametresi etkin; eski `change_evidence`, `losses`,
`pressure`, `private_loyalty` alanları yeniden kullanıldı. Yeni kaynak güveni,
öngörü, yerel kamu bilgisi ve uzun vadeli yönelim ayrı `behavior` özetinde tutulur.
Günlük tüm geçmişi toplayan karar yerine olay bazlı artımlı güncellemeler vardır.

Ek mühendislik düzeltmeleri: gelecek deney müdahaleleri `external_action` olarak
snapshot kuyruğuna taşındı; temel yönelim sıfıra indiğinde sıfır değişim için
sahte yeni geçiş olayı üretilmesi engellendi; uzun deneylerde olay güvenlik
bütçesi açıkça nüfus/gün ölçeğinde sağlandı. Son güvenlik düzeltmesi 30/60 günlük
koşuların ulaştığı durumları değiştirmez (bu koşulda temel yönelim değişimi yok).

Son durum: 54 test başarılı; 260 nihai karşılaştırmalı 30 günlük koşu ve 6 adet
60 günlük doğrulama yörüngesi tamamlandı. Geliştirme sırasındaki başarısızlıklar,
ön seri, nihai deneyler ve belirsiz bulgular `behavior-experiments.md` içinde
ayrı açıklanmıştır. Büyük kayıtlar Git dışı `runs/`; yeniden üretim komutları
README ve güncel davranış belgesindedir.
