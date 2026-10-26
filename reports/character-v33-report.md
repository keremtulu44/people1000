# v3.3 — uygulama ve geniş araştırmanın genel sonucu

**25 Ekim 2026 · Önce kodlama, sonra sabit modelle deney.**

## Kısa sonuç

Konuştuğumuz iki ayrım kodda uygulandı:

1. **Normal gündemde kanaat güncellenmesi, taraf/ideoloji değişimi değildir.**
   Atama hakkında açıklama, yeterlilik belgesi, itiraz ve bekleme ayrı bir olay
   kanalında işleniyor. Bu kanal genel siyasi destek veya bağlılığa yazamıyor.
2. **API bir kişi/gün konuşması değil, önemli bilgi değişiminde özet değerlendirmesi.**
   Aynı kamusal bilgi ve rol bağlamını paylaşanlar tek değerlendirmeden yararlanıyor;
   özel para, sadakat ve başkalarının gizli anıları özet paketine konmuyor.

**808 ana koşu tamamlandı.** Ayrıca önerinin fiilen uygulanmasını sınayan
**24 ek koşu + 4 müdahalesiz kontrol** çalıştırıldı. Böylece 836 deney/kontrol
koşusu var; dört birebir devam kontrolü ve eski kaynak karşılaştırması bu sayıya
şişirme amacıyla eklenmedi.

Genel değerlendirme: **gündem–kimlik ayrımı ve API sınırı çalışıyor; karakter
modeli hâlâ sınırlı bir araştırma modeli.** Her kesimin bütün sosyal özelliklerinin
tamamlandığı veya gerçek insanların davranışının doğrulandığı sonucu çıkarılamaz.

## 1. Neler kodlandı?

- `society/agenda.py`: yerel olay öğrenimi, iddia–kanıt ayrımı, yeterlilik/usul
  kanaatleri, rolü koruyan özetler ve yalnız gündeme ait yanıt eylemi.
- `society/agenda_api.py`: isteğe bağlı HTTPS/OpenAI-uyumlu adaptör, kesin JSON
  şeması, kimlik/güvenlik sınırları, çağrı ve sağlayıcı bildirirse token kaydı.
- `society/session.py`: günlük durma/kaydetme/yönetici raporu ve müdahalesiz çok gün
  ilerletme. Bunlar aynı motoru kullanıyor; web paneli eklenmedi.
- `behavior-v32.json`: önceki profil korunuyor. Varsayılan v3.3; eski grup,
  ekonomik/siyasi dinamik ve karakter katsayıları aynı kaldı.
- Yeni senaryo yürütücüsü, deney kurulum testleri, ölçüm ve doğrulama araçları eklendi.

API yanıtı yalnız izin verilen yaklaşımı önerebilir. Taraf, ideoloji, genel
siyasi destek veya uydurma belge alanı eklerse reddedilir. Etki tahmini gerçekleşmiş
sonuç diye işlenmez. Yerel yanıt, bedelsiz kitlesel yayın sayılmaz; diğer kişilerin
öğrenmesi ayrıca gerçek iletişim ve okuma gerektirir.

**Gerçek ücretli API kullanılmadı.** Adaptör sahte HTTP yanıtıyla kontrol edildi;
geniş araştırma açık kurallı `ReferenceAdvisor` ile çevrimdışı çalıştı. Gerçek
LLM kalitesi, sağlayıcı uyumluluğu, gecikme ve token maliyeti ölçülmüş değildir.

[Teknik kullanım ve uygulama sınırları](../docs/agenda-api-implementation.md).

## 2. Araştırmanın kapsamı

| Kapsam | Sayı |
|---|---:|
| Ana deney/kontrol koşusu | 808 |
| Farklı senaryo adı | 108 |
| Güncel v3.3 koşusu | 720 |
| Yeniden çalıştırılan eşleştirilmiş v3.2 kontrolü | 32 |
| Açık tarihsel v2 / v3.0 kontrolü | 28 + 28 |
| Normal gündem koşusu (ana toplam içinde) | 84 |
| Ölçekler | 100 / 1000 kişi |
| Süreler | 30 / 180 simülasyon günü |
| Doğrulanan gerçek kişi-gün kaydı | 2.928.000 |
| Gerçek gün sonu grup dağılımı | 156.240 |
| Hash ile doğrulanan kalıcı kanıt dosyası | 1.616 |

Önceki 612 deney tanımı tekrarlandı; karakter mekanizmaları, gündem ve yeni
karşılaştırmalar ayrıca eklendi. Duraklatılmış v3.2 araştırmasının **98 koşusu
bu sonuçlara karıştırılmadı**. Eski 612 koşuluk rapor da tarihsel olarak korundu.

Makro şoklar, ani/kademeli/tekrarlanan deneyimler, kaynak türleri, karşıt
mesajlar, siyasi sorumluluk ve alternatif fayda, sözleşme müdahaleleri, toplantı,
karşılaşma, kurumsal rekabet, öz-gelişim ve atama gündemi kapsandı.

Ana gündem deneylerinde `Wait` politikası kullanılarak başka otonom siyasi
kararların etkisi dışarıda tutuldu; özetler yine gerçek değerlendirme arayüzünden
geçti. Ek 24 koşuda `AgendaOnly` öneriyi gerçekten `agenda_response` eylemine
çevirdi. Dört aynı-tohum kontrolüyle birlikte değerlendirildi. Ek çalışma,
ana çalışma dondurulduktan sonra ayrıca beyan edilmiş uygulama kontrolüdür.

## 3. Atama örneği gerçekten nasıl sonuçlandı?

| Denenen durum | Gözlenen model sonucu |
|---|---|
| Atama dünyada kaydedildi ama kişi öğrenmedi | Kişide gündem bilgisi ve değerlendirme çağrısı oluşmadı. |
| Yönetici yalnız açıklama yaptı | Bazı olay-özel kanaatler kaynak/karaktere göre hareket etti; açıklama belge sayılmadı. |
| Yönetici veya gözlemci yalnız açıklamayı okudu | Doğrulanmamış yeterlilik iddiasını gerçek kabul etmedi. |
| Senaryoda doğru olduğu tanımlanan yeterlilik belgesi ulaştı | Yalnız yeterlilik bilgisi güncellendi; usul kanaati ayrı kaldı. |
| Belge gönderildi ama okunmadı | Hedef kişi belgedeki bilgiyi öğrenmiş sayılmadı. |
| Önce iddia geldi, sonra iddiayı çürüten gerçek belge ulaştı | Yeterlilik kanaati belgeye göre düzeldi; siyasi kimlik değişmedi. |
| Aynı açıklama veya duyuru tekrarlandı | Ek siyasi kanıt birikmedi; aynı bilgi gereksiz yeni özet çağrısı üretmedi. |

**84 gündem karşılaştırmasında taraf, kamuya siyasi destek, özel bağlılık,
temel yönelim ve genel siyasi değişim kanıtı kontrol koşuluyla birebir aynı kaldı.**
100 kişiliklerde müdahalesiz aynı-tohum `Wait` koşusu; 1000 kişiliklerde yalnız
duyuru ile belge eklenen aynı-tohum koşusu karşılaştırıldı. Sadece “taraf değiştiren
sıfır” denilmedi; bütün kişilerin son derin durum vektörleri denetlendi.

Ek çalışmada **412 gündem yanıtı fiilen uygulandı**; 24 koşunun tamamı dört
müdahalesiz kontrolle derin durum bakımından eşleşti. Bu sırada modelin normal
günlük ekonomik ilerlemesi durdurulmadı. Dolayısıyla “hiçbir şey değişmedi” değil,
**bu sıradan olay siyasi kimliğe taşınmadı** sonucu var.

Belge sonrası yeterlilik değerinin 1 olması, gerçek hayatta herkesin yüzde yüz
ikna olacağı iddiası değildir: senaryodaki açık doğrulanmış bilginin model içi
kodlamasıdır. Usulün adilliği, yöneticinin genel güvenilirliği veya bütün kişinin
niteliği bundan çıkarılmadı.

## 4. API çağrısını kişi sayısından ayırabildik mi?

Evet, bu sınırlı gündem deneyinde:

| 30 günlük koşul | Bilgilendirilen ölçek | Çevrimdışı yeni özet incelemesi |
|---|---:|---:|
| Olay kimseye duyurulmadı | 100 kişilik dünya | 0 |
| Atama duyurusu | 100 kişilik dünyada seçilmiş hedefler ve kaynaklar | 7 |
| Açıklama | Aynı küçük hedef grubu | 13 |
| Duyuru + doğrudan yeterlilik belgesi | Aynı küçük hedef grubu | 13 |
| Atama duyurusu | 1000 kişinin tamamı | 8 |
| Duyuru + doğrudan belge | 1000 kişinin tamamı | 16 |

100 kişilik hedef deneyleri bütün nüfusu bilgilendirmez; bunların sayısı 1000
kişilik tam nüfus deneyiyle doğrudan ölçek katsayısı gibi karşılaştırılamaz.

1000 kişinin her gün ayrı isteği yerine bu tek gündemde **8 veya 16 ortak rol/bilgi
paketi** yeterli oldu. Bu, karmaşık her 30 günlük sürecin 16 istek tutacağı anlamına
gelmez. Farklı bilgi kümeleri, kaynaklar ve yeni olaylar çağrı sayısını artırabilir.
Ana çalışmada toplam **1.049 çevrimdışı özet incelemesi**, **0 ağ isteği** var.
Gerçek token/ücret hesabı için daha sonra gerçek sağlayıcıyla kısa pilot gerekir.

## 5. Altı kesim hakkında genel bulgu

### Güç yanlısı ve muhalif

Kendi tarafındaki mevkili kaynak ile karşı kaynağın etkisi ayrıştı. Kontrollü
genel-konu deneyindeki tek hedef kişide, kendi tarafının kaynağı yaklaşık
21.04 / 20.77 puan görüş farkı üretirken karşı taraf kaynağı 0 fark üretti.
Bunlar kesimdeki herkesin kanaati veya gerçek dünya ikna oranı değildir.

Sıradan atama gündemi bu siyasi mekanizmaya karıştırılmadı. Ayrı **siyasi**
sorumluluk + alternatif fayda + %80 zarar koşulunda 100 kişiden 30 gün sonunda
ortalama **1,625 kişi** taraf değiştirdi (8 tohumda 1–2). Sorumluluk bilinmeyen
veya dışsal sayılan karşılaştırmalarda 0 çıktı. Bunlar tasarım koşullarına özgü;
hedef değişim oranı veya toplumsal tahmin değil.

### Yönetici / burjuva

Söylem kontrol deneylerinde genel-konu görüş farkı 0; geniş v3.3 koşularında
parti değişimi 0. Kurumsal rekabet ise çalışıyor; kaynak ve bekleme süresiyle
sınırlı. Bu, yönetici karakterinin sözle ikna edilen takipçiye dönüşmediğini
gösteriyor. Fakat çok boyutlu çıkar pazarlığı ve gerçek stratejik parti anlaşmaları
henüz yok; sıfır parti değişimi bütün yönetici modelinin tamamlandığını kanıtlamaz.

### Zengin

Yöneticiye sözleşme bağımlılığı ve doğrudan zarara tepki korunuyor. Tekrarlanan
sözleşme iptali deneyinde bazı kişiler desteğini çekti; taraf değişmedi. Bununla
birlikte genel-konu kaynak deneyinde zenginler her iki mevkili kaynağa da duyarlı.
Dolayısıyla bütün zengin davranışını yalnız maddi çıkar hesabıyla açıklayan tam
bir model kurulduğu iddia edilemez.

### Tepkisel huzursuz

Kontrollü yerel iletişim halkasında hafif kesintide toplantıya katılan yoktu.
Ağır kesintide dört koşuda **2–3 kişi** katıldı; yalnız bir koşuda iki kişi aynı
anda açık destekle kolektif ifade oluşturdu. Katılımı kapatan eşleştirilmiş
kolda katılım ve kolektif ifade 0 oldu. **Şikâyet, kayıt, davet ve gerçek ortak
katılım aynı şey değil.** Bu halka özellikle eklenmiş deney ağıdır; doğal nüfusa
mal edilecek bir örgütlenme olasılığı değildir.

### Gözlemci

Açıklamaları sıradan gerçek gibi benimsemedi; kontrollü genel-konu farkı 0,
parti değişimi 0. Normal 30 günlük 100 kişilik dünyada üç gözlemci toplam 90
öz-gelişim eylemi yaptı. Öz-gelişimi kapatan karşılaştırmada 0 oldu; başlangıç
kişilik/finans/ağ aynı tutuldu. Fakat bu hâlâ basit bir gelişim göstergesi,
insan muhakemesinin veya kapsamlı ideoloji çözümlemesinin modeli değil.

[Kesimlere ayrılmış ölçüm tabloları](character-research-v33/group-dossiers.md).

## 6. Kalabalık ve zaman yapısı

- Karşıt amaçlı iki toplantıdaki kişiler birbirini gördü ama aynı destek havuzuna
  yazılmadı. Açık ortak amaç ve açık destek varsa kolektif ifade oluştu.
  Aynı ortak amaçta sadece gözlem katılımı yine kolektif destek üretmedi.
- Tarihsel `crowd-two` girdilerinde iki kişinin bulunup kolektif gücün 0 olması
  hata diye gizlenmedi: eski girdide açık `support` yoktu; v3.3'te varsayılan
  katılım gözlemdir. Yeni açık destek kolları bunun için ayrıca çalıştırıldı.
- Fiyat dışı %30 kesinti erken başlayınca son gündeki sürpriz daha düşük,
  yıpranma daha yüksekti; geç başlayınca tersi çıktı. Erken/geç koşulların
  son tepki göstergeleri yaklaşık .121/.195; yıpranma .081/.029.
  Bunlar model içi göstergelerdir, psikolojik ölçüm değil.
- Fiyat dışı bu deneyler kendiliğinden para kaybı veya siyasi sorumluluk yazmadı.
  Maruziyet süreleri farklıdır; fark yalnız alışmaya mal edilmedi.

## 7. Neyi güvenle söyleyebiliriz, neyi söyleyemeyiz?

**Güvenle söyleyebildiğimiz:**

- Gündem kanaati ile derin siyasi alanları ayıran kod sınırı ve testler var.
- Kaynak açıklaması, gerçek belge ve okunmamış mesaj ayrı işleniyor.
- Aynı kamusal bağlamı paylaşanların özetleri tekrar kullanılabiliyor.
- 32 güncel v3.2/v3.3 eşleştirmesinde eski mekanizma sonuçları aynı çıktı.
- 56 tarihsel v2/v3.0 kontrolü kayıtlı eski özet sonuçlarıyla eşleşti.
- Dört v3.3 kaydet/yükle/devam kaydı byte düzeyinde eşleşti. Ek olarak donmuş
  v3.1 kaynak ile açık v3.1 profilinin 10 günlük tam kaydı da eşleşti.

**Henüz söyleyemediğimiz:**

- Gerçek LLM'nin bu rolleri hangi kalitede ve ücrette sürdüreceği.
- Mevcut iletişim ağı ve temel politikanın doğal, geniş katılımlı gündem yayılımını
  tam temsil ettiği. Birçok kampanya yalnız iki doğrudan hedef üzerinden veriliyor;
  düşük değişim sayısı otomatik olarak güçlü toplumsal direnç demek değil.
- Yönetici pazarlığı, zengin rekabeti, gözlemci muhakemesi ve doğal dil konuşma
  zincirlerinin bütün ayrıntılarıyla tamamlandığı.
- Normal gündemin yapısal krize dönüşmesinin modellenmiş olduğu. Bunun için gizli
  bir taraf değiştirme eşiği eklenmedi; ayrı açık mekanizma gerekir.

**Önerilen sonraki adım:** Modeli sonuç sayısı artsın diye yeniden ayarlamak değil;
önce tek bir gerçek API pilotunda özet → öneri → sınırlı eylem → gerçek teslimat
zincirini, bilgi sınırlarını ve token maliyetini incelemek.

## 8. Testler, hata kaydı ve kanıtlar

[Test günlüğü](character-v33-tests.txt): **150 test; 149 başarılı, 1 atlanan**.
Atlanan kontrol önceki bir deneyin eksik ham tarihsel dosyasına bağlıdır; bu
araştırmanın ham kayıtları eksikmiş gibi sunulmadı. Güncel 2.928.000 kişi-gün
satırının tamamı sayıldı ve dosya hashleri doğrulandı.

İlk çalıştırma **803 koşudan sonra** 1000 kişilik gündem kurulumunda durdu:
bütün nüfus hedefken hedeflerin dışından örnek kişi seçilmeye çalışılıyordu.
Yalnız yürütücünün örnek kaynak seçimi düzeltildi; davranış kodu ve katsayılar
aynı kaldı. İlk hata, eski yürütücü, eski protokol ve kaynak-hash değişikliği
korundu. Kalan 5 koşu çalıştırıldı. Bu hata gizlenmedi ve tamamlanmış 803 koşu
sessizce farklı modelle değiştirilmedi.

- [Ölçüm tabloları](character-research-v33/results.md)
- [Koşu bazlı CSV](character-research-v33/runs.csv) · [Kesim CSV](character-research-v33/groups.csv)
- [Denetim sonuçları](character-research-v33/validation.json)
- [Normal gündem derin durum kontrolleri](character-research-v33/ordinary-deep-state-checks.json)
- [Önerinin uygulanması ek kontrolü](character-research-v33/agenda-execution-followup.json)
- [Birebir devam kontrolleri](character-research-v33/replays.json)
- [Protokol ve açık kurulum yaması](character-research-v33/protocol.json)
- [İlk hata kaydı](character-research-v33/failures.jsonl)

Her koşunun gerçek gün sonu grup dağılımları ve nedensel olay denetimleri
`character-research-v33/evidence/` altında kalıcı sıkıştırılmış dosyalarda.
Büyük kişi-gün ham verisi `runs/character-research-v33/` altında Git dışındadır;
gelecekte ham dosyaların tamamının taşınacağı vaat edilmiyor. Rapor, hiç kaydedilmemiş
geçmişi son durumdan doldurmuyor. Sonuçlar gerçek toplum doğrulaması değildir.

Kod da sonuçla birlikte saklandı: [dondurulmuş çalıştırılabilir kaynak](character-research-v33/frozen-source.zip),
[kaynak manifesti](character-research-v33/source-manifest.json),
[son kontroller](character-research-v33/final-checks.json).
Arşiv ayrıca bağımsız klasöre açılarak 150 test yeniden çalıştırıldı:
149 başarılı, aynı tarihsel dosyaya bağlı 1 atlanan.
