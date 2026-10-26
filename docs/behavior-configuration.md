# Davranış yapılandırması — deneysel sözleşme

Dosya: `society/behavior.json`. Bağımlılık: yalnızca Python standart kütüphanesi.
`schema_version: 1` biçimi, `behavior_version: 1.0.0` davranış varsayımlarını tanımlar.
Bunlar doğrulanmış toplumsal gerçekler veya kalibre edilmiş psikolojik katsayılar değildir.

## Ölçek ve örnekleme

Her parametre `[alt, üst]` kapalı aralığıdır; tüm değerler sonlu ve **0–1** içindedir.
Eşit uçlar sabit değer demektir. Ajan oluşturulurken aynı simülasyon RNG'siyle
uniform örneklenir; aynı tohum, profil, kod sürümü ve olay dizisi aynı sonucu verir.
Her kesim için ayrı aralık kaydı vardır. Varsayılan, aralığın orta noktasıyla
özetlenebilir; üretimde orta nokta değil örneklenmiş değer kullanılır.

Yeni örneklemeler RNG tüketimini değiştirdiğinden v1 ile yeni v2 başlangıç
nüfusları bit düzeyinde aynı değildir. Aynı sürüm içinde tekrarlanabilirlik testlidir.
`initial_traits` başlangıcın ayrı kopyasıdır; `traits` güncel özellik alanıdır.
Bu görev temel eğilimleri otomatik değiştiren yeni davranış eklemez.

## Yedi parametre

| Parametre | Anlam ve yön | Şu an motor kullanımı |
|---|---|---|
| `authority_sensitivity` | Yüksek değer otoriteye yüksek duyarlılık | Önceki `.7–1.0` aralığı korunur; karar bağlamına verilir, henüz sayısal kanaat ağırlığına uygulanmaz. |
| `peer_opinion_resistance` | Yüksek değer akran görüşüne yüksek direnç | İlk iki kesimde `1`; mevcut kesin otorite kapısı korunur. Diğer sayısal etkiler sonraki davranış aşamasına ayrılmıştır. |
| `economic_harm_response` | Ekonomik zarara duyarlılık; yüksek değer daha güçlü tepki | `.4–.6` yeni deney varsayımı; zarar hesabını değiştirmez, otomatik psikolojik tepki henüz yoktur. |
| `pressure_response` | Bir geçerli baskı eyleminin görünür desteğe eklediği miktar | Önceki sabit `.1` çevresinde `.08–.12` kişisel çeşitlilik; özel sadakati değiştirmez. |
| `topic_change_threshold` | Önceki tahminle yeni iddia arasındaki `abs(fark)/100` için asgari eşik | Varsayılan `0`: eski her geçerli iddiayı değerlendirme davranışı korunur. Eşiğin altındaki mesaj okunur ama kanaati değiştirmez. |
| `alignment_change_threshold` | Birikimli etkinin siyasi bağlılık değişimi için gerektireceği eşik | `.85–.95`, gözlemcide `.999–1`; yalnızca tanımlıdır. Birikim ve histerezis bu görevde eklenmedi. |
| `core_orientation_resistance` | Temel yönelimin değişime direnci | Eski `.7–.95`, gözlemcide `.999` korunur. Temel yönelim güncellemesi henüz yoktur. |

Sonradan kullanılacak parametreler bugünden davranış üretiyormuş gibi sunulmaz.
Gelecekte etkinleştirilmeleri bir davranış sürümü değişikliği ve ayrı test gerektirir.

`risk_tolerance: [.1,.6]` önceki ek özelliği korur. Eski `resistance` adı, yeni
`core_orientation_resistance` değerinin uyumluluk kopyasıdır; ayrı örneklenmez.

## Kesim varsayılanları

| Kesim | Pay | Otorite | Akran direnci | Ekonomik tepki | Baskı | Konu eşiği | Bağlılık eşiği | Temel direnç |
|---|---:|---|---|---|---|---|---|---|
| Güç/statü | 30 | .7–1 | 1 | .4–.6 | .08–.12 | 0 | .85–.95 | .7–.95 |
| Muhalefet | 30 | .7–1 | 1 | .4–.6 | .08–.12 | 0 | .85–.95 | .7–.95 |
| Yönetici | 15 | .7–1 | .7–.95 | .4–.6 | .08–.12 | 0 | .85–.95 | .7–.95 |
| Varlıklı | 12 | .7–1 | .7–.95 | .4–.6 | .08–.12 | 0 | .85–.95 | .7–.95 |
| Hoşnutsuz | 10 | .7–1 | .7–.95 | .4–.6 | .08–.12 | 0 | .85–.95 | .7–.95 |
| Gözlemci | 3 | .7–1 | .7–.95 | .4–.6 | .08–.12 | 0 | .999–1 | .999 |

Bilimsel gerekçe olmadan kesimler arasında yeni sayısal farklar icat etmek yerine,
mevcut anlamlı aralıklar ortak tutuldu. Her kesimin kaydı bağımsız düzenlenebilir.
İlk iki kesimin `requires_aligned_authority: true` kapısı ve gözlemcinin yüksek
çekirdek direnci korunur. Ağ, ekonomi ve yetki farklılıkları da ayrı mekanizmalardır.
`belief_step: .3` eski kanaat güncelleme adımıdır; alıcı–aktarıcı güveniyle çarpılır.

## Profil sağlama ve kayıt

```python
from society.behavior import load_profile
from society.engine import Simulation

profile = load_profile()
profile['groups']['observer']['parameters']['topic_change_threshold'] = [.1, .2]
sim = Simulation(behavior_profile=profile)
```

Profil kopyalanır, doğrulanır, deney protokolüne ve anlık görüntüye bütünüyle yazılır.
Yeniden yükleme diskteki güncel varsayılanı değil kayıt içindeki profili kullanır.
Dağıtılan Python paketine JSON dosyası dahil edilir. Profil/config nesnelerini
koşu sırasında doğrudan değiştirmek desteklenen bir deney müdahale yolu değildir;
yeni deney oluşturulmalıdır. Python nesneleri salt okunur/sandbox değildir.

## Eski kayıtlar

Anlık görüntü sürümü 2'dir. Sürüm 1 yüklenebilir: mevcut özellikler, para ve RNG
korunur; yeni özellikler ilgili aralığın orta noktasıyla tamamlanır. Geçmiş kaynak
kutbu sürüm 1'de tutulmadığından o kayıt için kaynak kişinin yükleme anındaki
bağlılığı kullanılır; geçmiş gerçek değer geri getirilemez. Gelen kutusundaki eski
mesajın teslim zamanı da yoksa yükleme zamanı kullanılır. Bu veri eksiklikleri yeni
kayıtlarda yoktur. Göç, sürüm 1 davranışıyla birebir devam garantisi değildir.

## Güncel durum: v2.0.0

Bu belgenin yukarıdaki etkin/rezerv tablosu **v1.0.0 denetiminin tarihsel durumudur**.
Birikimli davranış görevinde yedi parametre de etkinleştirilmiştir. Güncel
semantik, denklemler, sınırlar ve deney komutları için
[cumulative-behavior.md](cumulative-behavior.md) geçerlidir. Başlangıç aralıkları
korunmuştur; yeni küresel katsayılar JSON profilinin `dynamics` alanındadır.
