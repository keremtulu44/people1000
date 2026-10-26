# Geçiş teşhis kaydı ve kontrollü kapatmalar

Davranış profili `2.0.0` değiştirilmedi. Teşhis şeması `1`, deney protokolü
`diagnosis-1.0`. Bu bir kalibrasyon sürümü değil, gözlenebilirlik ve kontrollü
karşılaştırma sürümüdür.

## Normal davranışın korunması

`Config.ablation` varsayılan `none`. Diğer kabul edilen değerler:

| Değer | Kapatılan yol | Özellikle korunanlar |
|---|---|---|
| `economic_evidence` | Siyasi karar kanıtına günlük ekonomik terim | Fiyat, nakit kayıp, yük, özel sadakat, konu görüşü, temel yönelim |
| `peer` | Akran çekiciliği, akran kanıtı, akran konu iknası | Mesaj erişimi/okuma, kaynak tanınması, otorite tahmini/güveni |
| `trust_erosion` | Negatif yönetici güven güncellemesi | Başlangıç güveni/güvensizliği, toparlanma, mesajlar |

Diğer ayarlar sabit kalır. Sonraki durum farklılaşması davranışsal geri besleme
üretebilir. Ablation sonucu bir katsayının bağımsız, toplanabilir nedensel payı
olarak yorumlanmaz. Eski snapshotlarda yeni alan yoksa `none` kullanılır.

## `alignment_changed.payload.diagnostic`

- `before`: günlük güncellemeden önceki sadakat, geçişten hemen önceki sadakat,
  gün öncesi/karar anı görüşleri, kamu beyanı, temel yönelim ve baskı.
- `economic`: teşhis takibinin başlangıcı, gözlem günleri, zarar görülen günler,
  ilk zarar zamanı, ek gider toplamı, mevcut zarar/yük, para ve gelir.
- `messages_learned`: yalnızca karar anına kadar okunmuş mesajlar, kaynakları,
  teslim/öğrenme zamanları; metin tekrarı yerine kimlik/idda kaydı.
- `trust`, `trust_changes_today`: anlık kaynak güveni ve o günün değişimleri.
- `known_public_sources`, `peer_pull`: karar anındaki yerel bilgiler.
- `evidence_terms_today`, `accumulated_components`: o günün ve taşınmış siyasi
  kanıtın ayrı sayısal bileşenleri; `relief` negatif olabilir.
- `decision_score`, eşik, bedel, çekicilik, dönüş marjı ve cooldown alanları:
  uygulanan eşik testini tekrar kontrol etmeyi sağlar.
- `code_path`, `cause_event_id`: davranış olayı ve kod yolu.

Kayıt, geçişten **önce** hazırlanır; geçmiş nedenlere gelecek bilgi eklenmez.
Defter karar hesabının girdisi değildir. Eski yüklenmiş kayıtta önceden birikmiş
fakat bileşenleri bilinmeyen kanıt `unattributed` olarak tutulur; geçmiş bölünmez.
Yeni koşularda bunun dışında kalan çok küçük artıklar kayan nokta yuvarlamasıdır.

`diagnostic_exposure.tracking_start`, eski kayıttan devamda yalnızca yeni takip
süresini gösterir. Eski maruziyet süresini varmış gibi göstermez. İlk geçişte
`last_switch_day=-1000` bir başlangıç sentinelidir; gerçek bin günlük geçmiş değil.

## Saklama ve eksikler

Her yeni koşuda bütün geçişler `transitions.jsonl.gz`, son ajanlar
`agents.json.gz` dosyasındadır. Tohum 0 için her koşulun tam snapshotı da saklanır.
Diğer tohumlarda geçiş arası bütün olay geçmişi saklanmaz; gerektiğinde aynı
protokolle yeniden üretilir. Eski 260 koşunun çıkarımı ayrı legacy dosyasındadır;
eskiden tutulmayan alanlar null/eksik olarak belirtilmiştir.

Özetler `reports/diagnosis/` altında; ham veri `runs/diagnosis/` altında Git
dışındadır. Tam komutlar README ve ana denetim raporundadır. Akran pozitif kontrolü
ana matristen ayrıdır: aynı kamu desteği mesajları hem açık hem kapalı kola eklenir.
Böylece boş akran girdisindeki sıfır sonuçla çalışmayan mekanizma karıştırılmaz.

## Kalibrasyon kararı

Bu görevde parametre değiştirilmedi. İlk sonraki deneylerin önceliği alternatifin
beklenen faydası, yükün hangi kutba atfedildiği ve başlangıç güven priörünün
ayrıştırılmasıdır. Önce şok/ufuk/kesim bazında kabul edilen “nadir değişim” tanımı
ve deney hipotezleri kayda geçirilmeli; sonra eski/yeni profil ayrı tutulmalıdır.

`--legacy` komutu önceki 260 koşunun **orijinal** `state.json.gz` dosyalarını
ister. Bunlar yoksa tarihsel inceleme yeniden yapılamaz; son durumlar veya yeni
koşular eski veri gibi sunulmamalıdır. Depodaki legacy özetleri mevcut orijinal
kayıtlardan üretilmiştir. Yeni 840 koşu ise eski ham veriye bağlı olmadan diğer
üç koşu komutuyla yeniden üretilebilir; yalnız tarihsel karşılaştırma ve eski
artifact regresyon testi önceki ham verilere ihtiyaç duyar.
