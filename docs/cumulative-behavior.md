# Birikimli davranış v2.0.0 — deneysel model sözleşmesi

Bu model bir toplum tahmin aracı değildir. Katsayılar toplumsal gerçek olarak
kalibre edilmedi. Amaç yerel bilgi, birikim ve değişim mekanizmalarını sınamaktır.
Önceki `behavior-configuration.md` aralıkları korunur; oradaki “rezerv” statüleri
bu belgeyle aşağıdaki şekilde güncellenmiştir.

## Yedi ayrı düzey

| Düzey | Kayıt | Güncelleme kaynağı |
|---|---|---|
| Özel konu görüşü | `beliefs[topic]` | Okunmuş mesaj veya kişinin kendi gider/gelir deneyimi |
| Siyasi bağlılık | `alignment`, `private_loyalty` | Günlük birikimli değerlendirme; kutup etiketi ve yakınlık derecesi ayrı |
| Yöneticiye güven | `behavior.trust[source]` | Öğrenilmiş tahmin ile daha sonraki doğrudan deneyim arasındaki fark |
| Temel yönelim | `behavior.core_orientation` | Çok daha uzun süreli kanıt; 1 başlangıçtaki kurumsal bağlanmayı temsil eder |
| Açık beyan | `public_alignment`, `public_support` | Geçerli beyan veya baskının doğrudan görünür etkisi |
| Fiilî eylem | öneri ve `action_applied/rejected` kayıtları | Yetki, kaynak, bütçe kontrolünden geçen eylem |
| Algılanan durum | kişisel hafıza, `known`, `forecasts`, konu tahminleri | Yalnızca başlangıç yerel gözlemleri, okuma ve doğrudan deneyim |

`initial_group` ve `initial_traits` tarihsel kayıttır. Siyasi geçiş bunları veya
`traits` katsayılarını değiştirmez. Temel yönelim değişimi ayrı bir durum
boyutudur; risk toleransını ve tüm kişiliği bir anda yeniden üretmez. Açık beyan,
özel sadakat hakkında nesnel kanıt kabul edilmez. Yeni zorunlu otomatik beyan yoktur.

## Yerellik ve zaman

Başlangıçta doğrudan bağlantılı kişilerin **kamuya açık** kutup/rol bilgileri
bilinir. Özel sadakat, kaynaklar ve dünya kutup gücü öğrenilmez. Başlangıç
`known`/güven kayıtları snapshot'ta görünür; bu örtük küresel bilgi değildir.

Fiyat şoku dünyayı değiştirir. Kişi etkisini bir sonraki günlük gider hesabında
yaşar. Günlük rutinin ürettiği `behavior` olayı o kişinin yeni deneyimini işler.
Mesaj ise önce teslim edilir, dikkat bütçesi uygunsa okunur, sonra kanaat/güven
özetine girer. Geçmiş karar gerekçelerine sonraki olaylar eklenmez.

`economic_outlook` iddiası 0–100 aralığında **beklenen normalize kişisel ekonomik
zarar** anlamındadır. 0 “zarar beklemiyorum”, 80 “0.8 zarar bekliyorum” demektir.
Bu semantik yalnızca bu deney için tanımlıdır; dilin genel anlam çözümü değildir.
Mesajın kaynağı, kutbu ve iddiası yayımlanma anında sabitlenir. Gelecekteki gizli
kutup değişimi eski mesajı yeniden yorumlatmaz.

`public_support` mesajı açık beyan olarak algılanır; içerik ve kamu kutup etiketi
akran sinyali üretir. Her kamu eylemi herkese otomatik yayımlanmaz. Paylaşılmadıkça
uzaktaki ajanlar fiilî bir baskıyı veya beyanı bilmez. Standart karşılaştırma
politikası ağırlıkla açıklamaları aktarır; kendi kendine kapsamlı sosyal yaşam
üreten bir karar politikası değildir.

## Hesaplar

Harm `h = clamp((gider - temel_gider)/temel_gider + gelir_kaybı/referans_gelir)`.
Kişinin kendi gideri/geliri kullanılır; küresel güç/fiyat ajan kararına verilmez.

- Birikmiş yük: `burden = .90*burden + h*economic_harm_response`.
- Öğrenilmiş tahmin en fazla 7 gün geçerlidir. Aynı gün gözlemiyle sınanmaz.
  Tahmin–gerçekleşme farkı > .1 ise güven `.12*fark*authority_sensitivity` azalır;
  aksi hâlde `.04*(1-fark)` artar. Kaynak başına en son tahmin saklanır.
- Akran sinyali `(1-peer_opinion_resistance)*bağ_güveni*açık_beyan` ile güncellenir.
  İlk iki kesimde direnç 1 olduğundan doğrudan akran kanaat etkisi sıfırdır.
- Ekonomik konu görüşü özel olarak değişebilir. Mesaj kanaat adımı `.3*bağ_güveni`
  ile başlar; otoritede kaynak güveni ve otorite duyarlılığıyla, akranda dirençle
  çarpılır. Konu eşiğinin altındaki değişim uygulanmaz.
- Kanıt: `.96*eski + .08*burden + .12*aynı_kutba_güvensizlik*otorite_duyarlılığı
  + .05*akran_etkisi - .015*(1-h)`; alt sınır 0.
- Özel sadakat, `.08*((.5-güvensizlik)*.1 - h*ekonomik_duyarlılık)` kadar değişir.
- Alternatif ancak yerel olarak bilinen başka bir kutup varsa temel .35 çekicilik
  alır; akran sinyali ve kesime özgü çıkar etkisi eklenir.
- Çıkış maliyeti: `.15 + (1-risk)*.2 + .1*temel_yönelim`, ayrıca kesim maliyetleri.
- Geçiş için `kanıt*çekicilik > alignment_change_threshold + çıkış_maliyeti`,
  çekicilik en az .3 ve son geçişten itibaren en az 5 gün gerekir.
- **Dönüş histerezisi:** önceki kutba dönmek için aynı eşiğe ek .30 kanıt gerekir.
  Geçişte birikmiş karar kanıtı sıfırlanır; ekonomik deneyim silinmez.

Kesim kuralları: güç kesiminde düzen/otorite ek ayrılma bedeli; muhalefette kendi
otoritesine güvensizliğin alternatif çekiciliğine etkisi; yöneticide konum ve yerel
ittifak çevresi maliyeti ile gelir riski; zenginde kurumsal bağımlılık maliyeti ve
gelir kaybının alternatif çekiciliği; hoşnutsuzlarda daha zayıf kalıcı bağlanma;
gözlemcide yüksek ayrılma maliyeti ve düşük kutup çekiciliği. Bunlar ayrı
mekanizmalardır, sadece farklı başlangıç puanları değildir. Tam stratejik
kurumsal pazarlık veya algılanan seçim kazanma ihtimali modellenmez.

Temel yönelim kanıtı `h*ekonomik_duyarlılık` ile birikir. Varsayılan unutma yoktur
(`core_retention=1`). En az 14 gözlem ve `12/max(.001, 1-core_orientation_resistance)`
eşiği gerekir; geçiş boyutu .015, sonra o kanıt sıfırlanır. Gözlemcide eşik 12000,
diğerlerinde yaklaşık 40–240'tır. Bu son derece uzun zaman ölçeğidir ama sonlu
eşik nedeniyle imkânsız değildir. Parametre testleri daha kısa sentetik koşullarla
ulaşılabilirliği sınar. Temel yönelim, çıkış maliyetine geri beslenir.

Baskı hemen açık desteği ve kamu kutup beyanını etkileyebilir; özel sadakati
otomatik değiştirmez. Baskı durumu günlük .85 ile azalır. Baskıdan kaynaklı ayrı
uzun vadeli travma/öfke henüz yoktur.

## Parametre durumu

Yedi kesim parametresinin hepsi artık bir karar/güncelleme yolunda kullanılır.
`resistance` eski uyumluluk adıdır; yeni bağımsız karar katsayısı değildir.
`risk_tolerance` çıkış maliyetinde kullanılır. `dynamics` küresel katsayıları JSON
profilinde; kesime özgü yapısal maliyetler ve sayısal varsayımlar `dynamics.py`
içinde yukarıda belgelenen açık kurallardır. Eski profil v1.0, `dynamics` alanı
yoksa birikim kapalı olarak yüklenir; eski kayıt sessizce yeni kurala geçirilmez.

`Config(cumulative_enabled=False)` D kontrol koludur: ekonomik dünya, iletişim,
bütçeler ve önceki mesaj-kanaat referans kuralı korunur; yeni güven, birikim,
özel sadakat, siyasi geçiş ve temel yönelim güncellemeleri kapatılır. Dolayısıyla
D farkı tek bir katsayının değil **tüm yeni modülün** toplam etkisidir.

## Kayıt ve yeniden üretim

Olay kuyruğu gelecek `external_action` müdahalelerini de saklar. Sağlayıcılara bu
admin kuyruğu verilmez. `day_end` ölçümleri son dakikada kaydedilir. Snapshot
sürümü 2'de ek alanlar opsiyoneldir; eski dosyalara varsayılan eklenir.
Özet durum kaynak başına sınırlıdır; günlük geçmişler tekrar tekrar toplanmaz.
Hafıza ve denetim günlüğü halen büyür; sıkıştırılmış deney kayıtları Git dışındadır.

Çalıştırma:

```bash
python -m unittest discover -s tests -v
python -m society.experiments --seeds 20 --populations 100 1000 --days 30 --sensitivity
python -m society.verify_runs
python -m society.analyze_experiments
```

Önceden tanımlanmış protokol `reports/behavior-protocol.json`; koşu tablosu CSV;
sıkıştırılmış tam durumlar `runs/behavior/<id>/state.json.gz`. Açmak için standart
`gzip` kullanılır; yeniden yüklemeden önce JSON'a açılmalıdır. Sonuç özeti için
`reports/behavior-experiments.md` dosyasına bakınız.
