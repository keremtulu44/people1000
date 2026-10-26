# v3.3: normal gündem ve önemli karar değerlendirmesi

25 Ekim 2026. [Kullanıcı sözleşmesinin](api-and-agenda-contract.md) ilk uygulaması.
Bu belge kodda bulunanı, çevrimdışı kontrolü ve henüz doğrulanmayanı ayırır.

## Uygulanan sınırlar

- `agenda.py`: sıradan olay kaydı, yerel öğrenme, kaynak iddiası, gerçek belge,
  konu-özel yeterlilik/usul kanaati, önemli değerlendirme ve yerel yanıt.
- `agenda_api.py`: isteğe bağlı HTTPS/OpenAI-uyumlu JSON taşıma adaptörü ve karar
  sağlayıcısı. Anahtar yalnız ortam değişkeninden okunur; simülasyona kaydedilmez.
- `session.py`: tek simülasyon günü ilerletme, kontrol noktası ve yönetici raporu;
  müdahalesiz çok gün ilerletmek aynı motoru kullanır.
- Varsayılan profil v3.3; v3.2, v3.1, v3.0 ve v2 ayrıca korunur. Eski grup,
  ekonomi, siyasi dinamik ve karakter katsayıları değiştirilmedi.

### Normal gündem veri yolu

1. `agenda_create`: yönetici senaryoda olayı ve varsa gerçek belgeleri kaydeder.
   Kayıt var diye kişiler olayı veya belgeleri öğrenmez.
2. `agenda_notice`: belirli kişi olayı öğrenir. Kendi tarafı/karakteri, özellikle
   usul hakkındaki ilk değerlendirmesini etkiler; yeterlilik bilinmiyorsa .5'tir.
3. `send` + `agenda_id` + `aspect`: kaynak bir iddia iletir. Sadece teslim edilip
   okunduğunda karşı tarafa girer. Başlık `agenda:<issue>:<aspect>` olmak zorunda.
4. `agenda_evidence`: belirli kişi gerçek belgeyi edinir. Belgeyi elinde tutan
   kişi mevcut iletişim kanalı ve bütçesiyle başkasına aktarabilir. Uydurma belge
   kimliği ve belgeye aykırı sayısal iddia reddedilir.
5. Yeterlilik kanıtı yalnız yeterliliği etkiler; atama usulünün adil olduğunu veya
   yöneticinin genel olarak desteklenmesi gerektiğini kanıtlamaz.

Bu kanal genel `belief`, `trust`, `forecasts`, siyasi sorumluluk/fayda, taraf ve
bağlılık hesaplarına girmiyor. Aynı normal konuyu tekrar ederek siyasi kanıt
biriktirilemez. Buna rağmen zamansal/ekonomik başka etkiler kendi yollarından
çalışmaya devam eder; deneyde normal olayın etkisi aynı başlangıç ve aynı politika
ile ilerleyen karşı-olgusal koşuyla karşılaştırılır.

İddia ve doğrulama ayrımı katıdır: yönetici/gözlemci söylemi sıradan gerçek diye
benimsemez; açık doğrulanmış belgeyi öğrenmek ise söyleme kanmakla aynı şey değildir.
Karşı tarafın yeterlilik belgesini kabul etmek onun tarafına geçmek değildir.

## API özeti ve çağrı birimi

Değerlendirme her kişi/gün için çağrılmaz. Yeni öğrenilen gündem bilgisi önemli
inceleme tetikler. Aynı anda gelen güncellemeler birleştirilir; aynı **kamusal
bilgi + karakter rolü + atayan tarafa ilişki** tek değerlendirme paketini paylaşır.
Aynı özetin sonucu önbellekten kullanılır. Kaynak/kanıt değişince yeni paket oluşur.

Pakette kamusal olay, gerçekten okunmuş iddialar, gerçekten edinilmiş belgeler,
rol, ilgili taraf ilişkisi ve izin verilen yaklaşımlar vardır. Kişilerin gizli
parası, özel sadakati ve başka insanların anıları yoktur. Başka birinin okuduğu
bilgi, o bilgiyi okumamış kişinin paketine eklenmez. Gizli bilgileri aynı istek
altında toplayıp kişiler birbirinden habersizmiş gibi davranılmaz.

Çıktı kesin şemalıdır:

```json
{
  "approach": "question",
  "reason": "Yeterlilik kanıtını kabul ederken usulü sorgulamayı sürdürebilir.",
  "risks": ["Kişisel suçlama kanıtın kapsamını aşabilir."],
  "expected_effect": "Bu olayın tartışmasını etkileyebilir; sonuç kesin değildir."
}
```

Rolün izin verdiği yaklaşım dışına çıkılamaz; ek siyasi alanlar reddedilir.
Değerlendirme önerisi `agenda_response` ile, kişisel eylem bütçesi uygunsa yerel
karara dönüşür. Risk özellikleri ifadenin özel kalmasını farklılaştırabilir.
Beklenen etki gerçek etki diye yazılmaz; gerekçe metni gerçek, diploma veya
kurumsal güç üretmez. Yerel yanıt otomatik kitlesel yayın değildir: başka birinin
öğrenmesi ayrıca gerçek `send`/`relay` ve okuma gerektirir.

### Harcama ve hata davranışı

Profilde günlük 64/toplam 512 yeni özet incelemesi varsayılan üst sınırdır.
Bu tavanlar kalibrasyon değil güvenlik varsayımıdır. Önbellek kullanımı yeni
istek sayılmaz. Sınır dolarsa olay yeniden devam edilebilir halde durur; otomatik
olarak farklı bir modele/politikaya geçilmez. Taşıma hataları ve reddedilen
çıktılar kaydedilir. Ağ denemeleri ve sağlayıcı bildirirse token kullanımı ayrıdır.
Adaptörde çıktı sınırı varsayılan 500 token'dır; gerçek ücret sağlayıcı/model ve
girdi uzunluğuna bağlıdır. Uç noktanın tekrar isteği ücretlendirmeyeceği garanti
edilmez; denemeler ayrıca sayılır.

## Kullanım

Varsayılan çalışma `ReferenceAdvisor` kullanır: açık, çevrimdışı rol kurallarıdır;
gerçek bir dil modeli gibi sunulmaz. Gerçek adaptör Python tarafında bağlanabilir:

```python
from society.engine import Simulation
from society.agenda_api import AgendaProvider, OpenAICompatibleAdvisor
from society.session import Session

sim = Simulation()
# Önce geçerli, erişilebilir gündem olaylarını senaryoya ekleyin.
advisor = OpenAICompatibleAdvisor(endpoint=YOUR_HTTPS_ENDPOINT, model=YOUR_MODEL)
session = Session(sim, AgendaProvider(advisor))
report = session.day(checkpoint="runs/api-checkpoint.json")
# Burada kullanıcı raporu inceler, sim.schedule(...) ile müdahale eder.
# session.days(30) ise kullanıcı müdahalesi olmadan 30 simülasyon günü yürütür.
```

Anahtar `PEOPLE1000_API_KEY` ortam değişkeninde olmalıdır; kodda/chatte tutulmaz.
Örnekteki uç nokta/model kullanıcının sağlayıcısına göre seçilir; bu oturumda
hiçbir gerçek sağlayıcıya istek gönderilmedi veya para harcanmadı. HTTPS taşıma,
JSON yanıtı ve token kaydı kontrollü sahte yanıtla test edildi. Gerçek uç nokta
uyumluluğu, gecikme, token maliyeti ve LLM davranış kalitesi doğrulanmadı.

## Bilinen ilk-aşama sınırları

- Serbest metinden gerçek atama/ekonomi sonuçları türeten genel olay motoru yok.
  Yapılandırılmış olay ve iki açık konu alanı kullanılıyor: yeterlilik/usul.
- Özet değerlendirmesi rol seviyesinde; kişinin özel riskini uygulamada koruyor.
  Tam bireysel çıkar pazarlığı ve çok boyutlu stratejik muhakeme değil.
- API müdahalesi bu sürümde normal gündem incelemesidir; bütün kurumsal/ekonomik
  kararlar ve bütün kişilerin iç muhakemesi API'ye taşınmış değildir.
- Gündem değerlendirmesi otomatik doğal dil konuşması ve sınırsız yayılım değildir.
  Gerçek iletişim ayrıca açık/bütçeli eylemdir. Açıklama zincirleri araştırmada
  planlanmış, her girdinin kabul edilip edilmediği kaydedilmiştir.
- Normal bir olayın zamanla yapısal bir krize dönüşmesi için gizli eşik eklenmedi;
  böyle bir kapsam genişletmesi ayrı model kararı ve test gerektirir.

Test çıktısı: `reports/character-v33-tests.txt`. Geniş araştırma v3.3 için ayrı
`reports/character-research-v33/` klasöründedir; duraklatılmış 98 v3.2 koşusu
bu deneylere karıştırılmaz. Sonuçlar gerçek toplum doğrulaması değildir.
