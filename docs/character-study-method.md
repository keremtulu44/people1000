# Karakter araştırması: yöntem ve sonuçların anlamı

## Sabit tutulanlar

Davranış motoru, grup profilleri, katsayılar ve başlangıç 30/30/15/12/10/3 oranları
araştırmada değiştirilmedi. Kaynak SHA256 değerleri protokole yazıldı ve sonunda
yeniden karşılaştırıldı. Araştırma programları modelin karar kurallarını değiştirmez.
Yeni kabul/ölçüm testleri eklendi; eski testler silinmedi.

## Beş ana senaryo ailesi

| Aile | Sayı | Değişen giriş | Okunması gereken sınır |
|---|---:|---|---|
| Makro | 12 | %10/40/60/80/900 ani artış; deflasyon; kademeli artış; maliyet eşleme; geçici/tekrarlı şok; gizli güç tersine dönüşü | Gizli güç bildirilmiyor. Ani ve kademeli yolların yalnız son fiyatını eşlemek maliyeti eşlemez. |
| Bilgi | 16 | %40/%80 şok × belirsiz/A/dış koşul/yönetici atfı × yalnız bilinirlik/üç olumlu fayda ifadesi | Başlangıç A kohortuna iki temas; diğer okuyuculara normal ağdan yayılır. İfadeler nesnel hakikat değildir. |
| Kaynak | 13 | Kendi/karşı mevkili, sıradan kişi, kendi grup üyesi, zengin; sahte yetki metni; olumlu fayda; uyumlu/yanlış tahmin; tek/çok tekrar; çelişkili açıklamalar | Her grupta tek hedef. Bütün kollarda aynı kontrollü kaynak ağı; Wait politikası. Bu nüfusun tamamına mesaj yayma deneyi değildir. |
| Kitle | 9 | Mevkili/akran çağrısı; şoklu/şoksuz; yalnız mesaj; yalnız/iki katılımcı; aynı yerde ayrı kayıt; ayrılma; geç davet | Zorlanan fiziksel katılım seçim gerekçesini kanıtlamaz. Yer soyut etiket. |
| Kurum | 5 | Doğru/yanlış yönetici; tekrar iptal; baskı; iptal ardından çağrı | Yönetici kapsamı başlangıçta bağlı zenginlerdir; genel halka baskı modeli değildir. |

Ana çalışma 8 tohum/100 kişi/30 gün. Eski v2/v3.0 altı ekonomik/bilgi koşulunda
4 tohumla; 1000 kişi dört koşulda 2 tohumla; 180 gün dört koşulda 3 tohumla
karşılaştırıldı: 508 koşu.

### Ek keşif ayrımı

İlk sonuçlardan sonra siyasi yön kapsamını genişletmek için 104 koşu tanımlandı:
64 B yönüne çevrilmiş kampanya, 32 eşzamanlı kampanya ve 8 tarihsel maliyet kontrolü.
Ana koşulara karıştırılmadı. Dosya isimleri temel A senaryosunu miras alır;
mirror modu etkin planda A/B ifadelerini ve kaynak/hedefleri çevirir. Dual modu
iki planı birleştirir. Bu yüzden isimdeki A harfi tek başına etkin suçlamayı
anlatmaz; plan ve followup_mode birlikte okunmalıdır.

## Kaynak kontrolü neden ayrı?

Doğal ağda iki kaynağın aynı kişiye aynı kanaldan ulaşacağı garanti değil. Salt
kaynak-rolü sorusu için bütün mikro-kollara aynı sınırlı ek bağlantılar verildi:
güven .8, gecikme 10 dakika; kaynak kamu rolleri aynı başlangıç bilgisine eklendi.
Kişilik örnekleri değişmedi. Burada .8 model kalibrasyonu değil, kollar arasında
kanalı sabitleyen deney girdisidir. Doğal-ağ kollarıyla nüfus oranı karşılaştırması yapılmaz.

“Aligned” tarafsız hedef için A kaynağı, “opposed” B kaynağıdır; tarafsız kişinin
kendi/karşı tarafı olduğu iddia edilmez. Mevkili gruptaki “same_group” kaynağı da
mevkilidir; bu nedenle sıradan akran katsayısına değil mevkili yoluna girer.

## Ölçümler

- **Rahatsızlık/zarar:** yerel gider ve gelir deneyimi; siyasi tercih değildir.
- **Özel sadakat:** modeldeki 0–1 durum alanı; ideolojinin içeriği değildir.
- **Destek çekme:** support_withdrawn olayı; kişinin ideolojisi veya kutbu değişmiş sayılmaz.
- **Siyasi geçiş:** alignment_changed olayı; dönem içinde en az bir kez değiştiren
  kişi ve toplam olay sayısı ayrı tutulur. Geri dönüş ayrıca sayılır.
- **Temel yönelim:** core_orientation; v3.1 ilk aşamasında otomatik ekonomik değişimi
  dondurulmuştur. Sıfır değişim ideolojik gerçekçilik başarısı değildir.
- **Katılım:** gerçek attend olayı. Ortak ifade: en az iki kayıtlı katılımcıyla
  collective_expression_started. Sadece çağrı almak katılım değildir.
- **Ekonomi:** losses ile tasarruf/gelir ayrı. İptalde losses, ilerideki bütün
  vazgeçilmiş geliri toplamıyor; tasarruf farkı ayrıca değerlendirilmeli.

## Zaman, sansür ve kayıt

Ajan-gün satırları her gün 1439. dakikada gerçekten örneklenir. Giderler gün
başında işlendiği için günün 60. dakikasındaki şok ilk kez sonraki günün mali
hesabına yansır; bu muhasebe gecikmesi psikolojik bekleme süresi değildir. Buluşmalar gün
ortasında bitmiş olabilir; bu nedenle katılım olay kayıtlarından, gün-sonu gücü
ise gün-sonu durumundan okunur. Final durumu geçmişe doldurulmaz. Geçiş yapmayan
kişiye yapay bir “ilk geçiş günü” verilmez. İlk olay süreleri koşullu ölçümdür;
sıfır olay, sonsuz zamanda olamayacağının deneysel kanıtı değildir.

Tam seed-0 snapshotları, bütün koşuların final ajan/mesaj/karar/olay izleri ve
her ajan-gün kaydı saklandı. İlgili olay anındaki açıklama doğrudan
alignment_changed diagnostic içinden alınır. Son bağlılık geçmiş kaynak
başlığı diye kullanılmaz. Ham dosyalar SHA256/boyutla doğrulandı.

## İstatistik sınırı

Sekiz tohumdan kişi oranları hesaplanır; binlerce kişiyi bağımsız gözlem sayıp
sahte dar güven aralığı üretilmez. Bootstrap yalnız aynı tohum çiftlerinin farkı
üzerindedir; ampirik toplum olasılığı değildir. Ölçek koşularında çağrı sayısı
nüfusla büyütülmediği için oran düşüşü salt nüfus etkisi sayılmaz.

Ayrıca sıfır eylem her zaman dayanıklılık değildir: referans politika bazı
izinli eylemleri (organize etme, destek geri ilanı, kurumsal strateji) kendiliğinden
seçmez. Kural kilidi, eksik eylem seçimi ve gerçekten ikna olmama ayrı açıklamalardır.

[Detaylı rapor](../reports/character-study-report.md) · [Kabul sonuçları](../reports/character-study/acceptance.md)
