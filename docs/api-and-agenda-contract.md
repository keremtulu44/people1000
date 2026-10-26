# API değerlendirmesi ve normal gündem sözleşmesi

**Durum güncellemesi:** İlk uygulama v3.3'te yapıldı; aşağıdaki metin başlangıç
tasarım sözleşmesidir. "Henüz uygulanmadı" ifadeleri ilk kayıt anını anlatır.
Güncel uygulama ve kalan sınırlar: [teknik belge](agenda-api-implementation.md);
[deney sonucu](../reports/character-v33-report.md).

Kayıt: 25 Ekim 2026. Kullanıcıyla netleştirilen tasarım ve kabul koşullarıdır.
**Çalışan API entegrasyonu veya uygulanmış normal-gündem motoru iddiası değildir.**
Bu kayıt deney katsayılarını değiştirmez; duraklatılan araştırma yeniden başlatılmadı.

## 1. API çağrısının birimi kişi/gün değildir

Rutin ekonomi, zaman, teslimat ve basit durum güncellemelerini motor yürütür.
Önemli karar noktalarında ilgili durum özeti hazırlanır; API'ye ilgili kişi veya
tarafın karakteri ve çıkarları içinde ne yapmasının anlaşılır olacağı sorulur.
Her kişi için her gün ayrı istek zorunluluğu yoktur. Birlikte değerlendirme,
gizli bilgileri başka kişilerin kararına sızdırmamalı veya aynı kesimdeki kişileri
tek zihne dönüştürmemelidir. Güvenli paketleme ve kesin çağrı politikası henüz
uygulanmış değildir; istek sayısı/ücreti ölçülmüş gibi sunulmamalıdır.

Özet; erişilebilir olayları, önceki yerel deneyimleri, ilgili ilişkileri, kişinin
karakterini, çıkarlarını ve mevcut seçeneklerini taşır. Dünya yöneticisinin
bildiği her şey kişinin bildiği şey değildir. Her çağrı karakteri sıfırlamaz.

API seçenekleri, beklenen yararları, riskleri, belirsizlikleri ve önerilen eylemi
sunabilir. Mantıklı, tarafsız veya toplum için en iyi demek değildir; kişinin
karakteri ve çıkarları içinde anlaşılır demektir. Motor eylemin yetkisini,
kaynağını, zamanını ve bütçesini denetler. API tahmini gerçekleşmiş sonuç değildir.

## 2. Normal gündem, taraf/ideoloji değerlendirmesi değildir

Örnek: bir yönetici yakınını göreve atar; yeterlilik tartışılır; yönetici deneyim
ve diploma açıklaması yapar; ilgili kanıtlar bazı kişilere ulaşır.

Bu sıradan olayda değişebilecek alanlar:
- Atanan kişinin yeterliliği hakkındaki olay-özel kanaat ve belirsizlik.
- İlgili açıklamayı/kanıtı kabul etme veya reddetme.
- Bu atamayı uygun bulma, söyleyeceği söz, eleştiri/savunma veya bekleme.

**Bu akışın kendisi kişinin tarafını, ideolojisini, temel yönelimini veya genel
siyasi desteğini değiştirmez.** Bir muhalif yeterliliği kabul ederken atama
usulüne itirazını ve muhalifliğini koruyabilir. Bir atamayı doğru bulmak genel
liderlik desteği veya kamuya siyasi destek beyanı değildir.

Olay-özel kanaat, genel liderlik güveni, özel bağlılık, kamuya destek, taraf ve
ideoloji ayrı alanlardır. API'nin normal-gündem yanıtı derin bağlılık alanlarına
yazma yetkisi taşımamalıdır. Normal kanaat güncellemesi dolaylı genel kanıt/güven
birikimi üzerinden de otomatik taraf değişimi üretmemelidir. Sıradan olayları
tekrarlayarak bu sınırın aşılmasına izin verilmemeli; başka yapısal olayların nasıl
ayrı ele alınacağı ayrıca tanımlanmalıdır. Genel olarak bütün taraf değişimleri
yasaklanmış değildir; bu örneğin kapsamı sıradan gündemdir.

Yönetici açıklaması önce iddiadır. Gerçekten doğrulanan bilgi ile açıklamanın
kendisi ayrılır; yalnız ulaşan/öğrenilen kanıt kullanılabilir. API mevcut kanıta
yeni diploma, geçmiş başarı veya gizli doğruluk ekleyemez.

## 3. Karakter farkları korunur; sonuç oranı yazılmaz

- Güç yanlısı kendi yöneticisinin atamasını savunabilir; açıklamayı savunmasının
  gerekçesi yapabilir.
- Muhalif kayırmacılık eleştirisi yapabilir; yeterlilik kanıtını kabul etse bile
  seçilme biçimine itirazını koruyabilir.
- Başka yönetici sözleri benimsemekten çok kurumsal çıkar ve konumunu değerlendirir;
  konuşabilir veya sessiz kalabilir. Yakın çevresinin dışarıya sessizliği içsel
  onay sayılmaz.
- Zengin doğrudan tartışmaya karışmadan kendi ilişkilerine/işine etkisini izleyebilir.
- Tepkisel huzursuzun yakınması, örgütlenmesi ve fiili katılımı farklıdır.
- Gözlemci iddia ile doğrulamayı ayırır; otomatik kitle önderi olmaz.

Bunlar aynı kesimdeki herkese aynı cümleyi yazdıran senaryo değildir. Bilgi,
ilişki, geçmiş ve risk farklılıkları tepkinin biçimini ve zamanını farklılaştırır.
İkna olan kişi oranı, tarafların eşitlenmesi veya değişim yüzdesi hedeflenmez.

## 4. Uygulama öncesi kabul testleri

1. Normal atama + doğrulanan yeterlilik: olay kanaati değişebilir; taraf,
   temel yönelim, genel siyasi destek ve özel bağlılık bu yol üzerinden değişmez.
2. Aynı normal olayı tekrarlamak, dolaylı derin bağlılık birikimi yaratmaz.
3. Olay-özel kanaati kabul eden muhalif muhalif kalabilir; güç yanlısı savunmasını
   yeni gerekçeyle sürdürebilir. Ortak gerçek kabulü ortak siyasi kimlik değildir.
4. Okunmamış açıklama veya ulaşmamış kanıt karar girdisi olmaz.
5. API derin alan değişikliği veya uydurma kanıt önerirse motor reddeder.
6. API'nin etki tahmini motorun gerçekleşmiş sonucu yerine yazılmaz.
7. Tekrarlanan değerlendirmeler karakter/geçmişi korur; toplu çağrı gizli bilgi
   sızıntısı yaratmaz. Rutin ilerleme gereksiz kişi/gün çağrısı gerektirmez.

Sonraki uygulamada bu sözleşme motor sınırları ve testlerle gerçekleştirilmelidir.
Mevcut 127 testin bu yeni API tasarımını doğruladığı iddia edilmez.
