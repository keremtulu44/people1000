# Çekirdek denetimi ve davranış yapılandırması

Tarih: 2026-10-25. Kapsam: yerel Python çekirdeği; gerçek AI API ve panel eklenmedi.

## Başlangıç

Mevcut 16 test değişmeden korundu ve ilk incelemede geçti. İncelenen parçalar:
`Simulation`, tuple tabanlı heap olay kuyruğu, günlük ekonomi, bütçeler, mesaj
aktarım/okuma, öneri/uygulama, JSON snapshot ve mevcut CLI.

## Bulgular (önem sırasıyla) ve düzeltmeler

| Öncelik | Bulgu | Düzeltme / regresyon testi (`tests/test_hardening.py`) |
|---|---|---|
| Yüksek | Gün 0 rutini daha önce harcanmış günlük bütçeyi tekrar açıyordu. | Ajan başına `budget_day`, günde yalnızca bir yenileme. `test_initial_daily_does_not_refill_spent_budget`. |
| Yüksek | Gelecek günün kararı önce kuyruğa alınırsa, sınırda günlük rutinden önce çalışıyordu. | Aynı dakikada günlük rutin önce, diğer olaylar oluşturulma sırasıyla. `test_boundary_daily_precedes_prequeued_decision`, `test_same_time_fifo_and_causal_ids`. |
| Yüksek | Farklı kimlikle aynı güne eklenmiş iki daily ekonomi ve hafızayı iki kere işliyordu. | `last_daily_day` defteri, tekrar olayında `daily_skipped` günlüğü. `test_duplicate_daily_does_not_repeat_economy`. |
| Yüksek | Bozuk eylem türü/hedef/konu crash yaratabiliyor; NaN/JSON dışı yanıtlar kaydetmeyi bozabiliyordu. | Tür/konu doğrulama, JSON sınırında hatalı yanıtı reddedilebilir işarete dönüştürme. `test_malformed_actions_no_mutation_and_snapshot_safe`. |
| Yüksek | Kanaat güncellemesi mesaj kaynağının sonradan değişmiş gizli siyasi durumuna bakıyordu. | Mesajın yayımlandığı andaki doğrulanmış kaynak bilgisi korunur, alıcı bu bilgiyle değerlendirir. `test_historical_source_metadata_not_live_private_state`. |
| Orta | Geçersiz dış olay kuyruğa girip koşuyu sürekli aynı yerde durdurabiliyordu. | Kuyruğa eklemeden payload/tür/erişim doğrulaması. `test_rejected_events_do_not_enter_queue`. |
| Orta | Baseline son hafıza kaydını mesaj sanıyordu; doğrudan deneyim için KeyError mümkündü. | Deneyim ve mesaj görünümünü ayırma, sağlayıcıda mesaj filtresi. `test_provider_ignores_nonmessage_experiences`. |
| Orta | Teslim edilme ve okunma zamanı ayrı tutulmuyordu; mesaj hafızasında konu eksikti. | `delivered_at`, `learned_at`, konu ve kaynak metadatası. `test_delivered_read_and_memory_times_are_separate`. |
| Orta | Günlük log kayıtlarının kendi log kimliği vardı ama kuyruktaki işlenen olayın kimliği yoktu. | Günlüğe `event_id` eklendi; `caused_by` ile zincir kurulabilir. `test_same_time_fifo_and_causal_ids`. |
| Düşük | Kesirli/bool bütçe ve kesirli nüfus kabul edilebiliyordu. | Negatif olmayan tam sayı bütçe, tam sayı tohum ve 100'ün katı nüfus doğrulaması. `test_config_rejects_invalid_types`. |

## Doğrulanan mevcut davranışlar

- Geçersiz/yetkisiz veya kaynağı yetersiz eylem, ajan kaynağını, bütçesini,
  kanaatini veya hedefini değiştirmiyor. Reddin denetim kaydı ve karar kimliği tutulur.
- Aynı eylem tekrar uygulanmıyor. Bu mevcut koruma kaldırılmadı.
- Bütçe aşınca okunmayan mesaj kuyrukta kalıyor; sonraki gün okunabiliyor.
- Kaynak ve aktarıcı ayrı; bilgi ulaşmadığında karar görünümüne girmiyor.
- Gözlemciye dünya gerçeği verilmez; gerçek kutup değişimi tek başına kişisel
  kanaat yaratmaz. Olay günlüğü dünya kaydıdır, kişisel hafıza değildir.
- Çoklu ara noktada (0, 1, 20, 150, 1200, 1439, 1440, 1441, 2880, 3000)
  kaydet/yükle, kesintisiz koşuyla **tam anlık görüntü eşitliği** verir.
- Sağlayıcı hatası sonrası karar olayı korunur; kayıttan yeniden devam edilebilir.
- Aynı tohum/profil ve olaylar aynı tam kayıtla sonuçlanır. Bir dal diğerini değiştirmez.

## Değiştirilen/eklenen dosyalar ve gerekçeler

- `society/engine.py`: yukarıdaki düzeltmeler, profil enjeksiyonu, snapshot v2 ve v1 göçü.
- `society/behavior.json`: altı kesimin payları, yedi davranış aralığı, mevcut risk ve kanaat adımı.
- `society/behavior.py`: bağımlılıksız yükleme, doğrulama, tohumlu örnekleme ve eski ad uyumluluğu.
- `pyproject.toml`: JSON'u paket verisi olarak dahil etme.
- `tests/test_hardening.py`: 20 yeni test; eski `tests/test_engine.py` değiştirilmedi.
- `docs/behavior-configuration.md`: ölçek, aralık, varsayım ve aktif/rezerv parametre ayrımı.
- `README.md`: güncel sıralama/kayıt açıklaması ve belgelere bağlantı.
- `reports/`: gerçek komut çıktıları, bu denetim ve test kanıtları.

## Test/komut kanıtı

Başlangıç: `python -m unittest discover -s tests -v` — 16 test, OK.
Son tam paket: aynı komut — **36 test, OK**; ayrıntı `reports/tests.txt`.
İlk genişletilmiş koşu 32 testti ve geçti; 4 ek sınır testiyle sayı 36 oldu.
Bu görevde çalıştırılan test koşularında başarısız test görülmedi.

Ek komutlar, çıkış kodları ve çıktı dosyaları `reports/commands.json` içinde:
100/1000 ajan demo, devam koşusu ve `compileall`. Büyük snapshotlar `runs/`
altında, Git dışında bırakıldı. Duman testleri performans/gerçekçilik kanıtı değil,
yalnızca çalıştırılabilirlik kontrolüdür.

## Kalan sınırlamalar ve çözülmeyen riskler

- Tam veritabanı transaction/rollback yoktur. Bilinen bozuk girdi yolları mutasyondan
  önce engellenir; sağlayıcı hatası tekrar denenebilir. Beklenmeyen bir iç programlama
  hatasında olayın kısmen uygulanmadığına dair genel garanti yoktur.
- Snapshotlar güvenilen yerel dosyalardır; bozulmuş/düşmanca dosyalar için kapsamlı
  bütünlük şeması henüz yoktur. Tek süreçli atomik dosya değişimi kullanılır.
- Config/profil koşu ortasında doğrudan Python'dan değiştirilebilir. Desteklenen
  deney yolu yeni simülasyon oluşturmaktır; runtime değişiklik API'si henüz yoktur.
- Doğrulanmış kaynak etiketi varsayılır. Kaynak taklidi, güvenilirlik/kimlik doğrulama
  ve sonradan öğrenilen kaynak değişimleri modellenmez.
- İlk iki kesimde hâlen aynı kutuptaki otorite şartı + aktarıcı güveni kullanılır;
  ayrı kaynak güven ağının daha ayrıntılı kullanımı sonraki davranış işidir.
- Ekonomi kısmi açık modeldir; negatif birikim açığı temsil eder, iflas modeli yoktur.
- Ekonomik tepki ve siyasi/temel yönelim değişimi parametreleri tanımlı ama henüz
  otomatik davranış üretmez. Bu görev bunları gizlice etkinleştirmedi.
- Geniş ağlarda lineer aramalar ve JSON kayıtları büyür; 1000 kişilik duman testi
  uzun dönem ölçek garantisi değildir.
- Yeni davranış özellikleri RNG tüketimini değiştirdiği için eski sürümden yeni
  nüfus oluşturmak birebir aynı nüfus vermez. Eski snapshot göçünde mevcut RNG ve
  durum korunur; eksik geçmiş kaynak/teslim verisi geri getirilemez.

## Sonraki işler

1. Birikimli zarar, güven ve bağlılık için önceden belirlenmiş ölçülerle histerezis
   tasarlamak; rezerv parametreleri kontrollü ve yeni davranış sürümüyle etkinleştirmek.
2. Ayrı kaynak güveni, algılanan güç ve açık beyan/özel sadakat kararlarını geliştirmek.
3. Transaction destekli kalıcılık, dosya bütünlüğü ve sürümlü tam replay.
4. Çok tohumlu karşılaştırmalı deneyler ve performans ölçümü.
5. Bunlardan sonra şemalı/bütçeli gerçek AI entegrasyonu; panel bu görevin dışında.
