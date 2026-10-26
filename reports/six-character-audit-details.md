# v3: altı karaktere sadakat denetimi

> Tarihsel v3.0 denetimi. Sonraki sınırlı v3.1 değişiklikleri için [ilk aşama raporuna](collective-stage1.md) bakın; aşağıdaki kod referansları denetim anına aittir.

**25 Ekim 2026 — yalnız denetim.** Davranış kodu, katsayılar ve test dosyaları değiştirilmedi.
[Karakter sözleşmesi kaydedildi](../docs/six-character-contract.md). Tanımlar kurgu hedefidir, toplumsal gerçek iddiası değildir.

**Kısa hüküm:** Altı grubun hiçbiri bütün tarifiyle doğrulanmış değil. İlk iki grubun mevkili-kaynak kapısı ve zenginlerin yöneticiye bağımlılığı çalışıyor. Ancak iletişim karakterleri, senaryo yönetimi ve isyan anlatısının önemli bölümü v2'de de yoktu. **v3'te ayrıca tarafsız başlayan iki kesimin ilk kutup geçişini kapatan genel-kural etkileşimi var.** Dolayısıyla az geçiş, tek başına karakterlerin korunduğunun kanıtı değil.

## 1. Özellik matrisi

Hücreler uygulama sadakatini değerlendirir; bütün nüfusta deneysel doğrulama anlamına gelmez.
“Uygulanmamış — özgül tarif yok”, o gruba yeni bir gereklilik icat edildiği anlamına gelmez.
Kod sütunundaki referanslar aynı satırdaki bütün gruplar için geçerlidir.

| Özellik | %30 güç yanlısı | %30 muhalif | %15 burjuva | %12 zengin | %10 huzursuz | %3 gözlemci | Kod |
|---|---|---|---|---|---|---|---|
| Temel bağlılık/yönelim | kısmen korunuyor — A ve düzen maliyeti; mevki/para takibi değil | kısmen korunuyor — B başlangıcı; sürekli karşıtlık yok | kısmen korunuyor — yetki var, kişisel amaç yok | kısmen korunuyor — bağımlılık var, çıkar stratejisi yok | kısmen korunuyor — tarafsız; genel nefret modellenmiyor | kısmen korunuyor — tarafsız, dirençli; özel analiz yok | E1, D1 |
| Fikir değiştirme direnci | korunuyor — halk kaynaklarına kapalı | korunuyor — aynı kapı | kısmen korunuyor — eşik var, nadirlik kanıtı yok | kısmen korunuyor — çıkış maliyeti var | kısmen korunuyor — akran direnci var; geçiş aşırı kilitli | kısmen korunuyor — temel direnç var; konu görüşü açık | E3, D1, D2, A1 |
| Kendi grubundan etkilenme | korunuyor — fikir etkisi yok; aktarım var | korunuyor — fikir etkisi yok; aktarım var | kısmen korunuyor — meslektaş mevkili sayılıyor | kısmen korunuyor — zayıf akran etkisi; rekabet yok | korunuyor — akran etkisi düşük | kısmen korunuyor — az çıkış bağlantısı, gelenler sınırlı değil | E1–E3, A1 |
| Diğer gruplardan etkilenme | korunuyor — halk değil kendi mevkili kaynağı | korunuyor — kendi tarafının mevkili kaynağı | kısmen korunuyor — genel kaynak ağırlıkları | kısmen korunuyor — genel ağırlıklar | bozulmuş — akran desteği tek başına fayda kapısını aşamıyor; isyan da yok | bozulmuş — mevkiliye sıradan konu duyarlılığı diğerleriyle aynı aralıkta | E3, A1, D1 |
| Mevkili etkisi/güven | korunuyor — bağlı mevkili kapısı | korunuyor — farklı başlangıç kutbu/mevkileri | kısmen korunuyor — kaynak güveni var, senaryo örgütü yok | korunuyor — yönetici gelirini azaltabiliyor | kısmen korunuyor — genel mevkili duyarlılığı | bozulmuş — bağımsız yorum yerine aynı yüksek mevkili duyarlılığı | E1, E3, E4, A1 |
| İletişim hızı/sıklığı | bozulmuş — özel hızlı/sık rejim yok | bozulmuş — özel hızlı/sık rejim yok | uygulanmamış — özgül hız tarifi yok | bozulmuş — diğer büyük gruplarla aynı derece/bütçe | bozulmuş — yavaşlık/patlama rejimi yok | kısmen korunuyor — tek çıkış; aynı bütçe, gelen trafik serbest | E1, E2 |
| Ekonomik zarar tepkisi | kısmen korunuyor — ortak zarar, atıfla siyasi tepki | kısmen korunuyor — aynı ekonomik duyarlılık aralığı | kısmen korunuyor — gelir/çıkış etkisi; huzur amacı yok | kısmen korunuyor — gerçek gelir bağımlılığı; işçi sömürüsü yok | kısmen korunuyor — zarar kaydı var, toplu tepki yok | kısmen korunuyor — zarar kaydı, özel muhakeme yok | E4, D1, A2 |
| Siyasi sorumluluk atfı | korunuyor — yerel bilgi ve kendi mevkili kapısı | korunuyor — aynı, ayrı başlangıç kaynakları | kısmen korunuyor — ortak atıf kuralı | kısmen korunuyor — ortak kural + gelir iptali deneyimi | kısmen korunuyor — atıf var, none kutbu eşleşmiyor | kısmen korunuyor — aynı none sorunu | A1–A2, D1 |
| Alternatifi tanıma/yönelme | kısmen korunuyor — yetkili kanıtı; güç takibi değil | kısmen korunuyor — fayda hesabı; zıtlık takibi değil | kısmen korunuyor — fayda ve müttefik çıkış maliyeti | kısmen korunuyor — fayda ve bağımlılık maliyeti | bozulmuş — ilk geçiş kapalı, aday A'ya sabitleniyor | bozulmuş — aynı ilk geçiş kilidi/A yanlılığı | A2, D1–D2 |
| Toplu tepki/isyan | uygulanmamış — koordineli kolektif eylem yok | uygulanmamış — aynı | uygulanmamış — kolektif senaryo bastırması yok | uygulanmamış — özgül toplu tepki yok | uygulanmamış — destekle isyan/kısa sönüm yok | uygulanmamış — kahramanlık/çekilme kararı yok | E2, E4 |
| Gruplar arası etkileşim | kısmen korunuyor — ağ ve kaynak kapısı | kısmen korunuyor — ağ ve kaynak kapısı | kısmen korunuyor — zengine yetki var, halka senaryo yok | kısmen korunuyor — bağımlılık işler; employer yalnız kayıt | kısmen korunuyor — mesaj ağı var, destek koalisyonu yok | kısmen korunuyor — az çıkış, gerçek izolasyon değil | E1–E4 |

### Kod anahtarı

- **E1:** [engine.py:125–180](../society/engine.py#L125): başlangıç kutbu, servet, derece, bağlantı, bağımlılık ve başlangıç kaynak bilgisi.
- **E2:** [engine.py:24–32](../society/engine.py#L24), [76–83](../society/engine.py#L76), [389–459](../society/engine.py#L389): ortak bütçeler, her grupta aynı otomatik aktarma politikası ve olay akışı.
- **E3:** [engine.py:461–489](../society/engine.py#L461): genel konu güncellemesi/kaynak kapısı; [appraisal.py:24–73](../society/appraisal.py#L24): özel konularda aynı kapı ve kaynak ağırlıkları.
- **E4:** [engine.py:275–310](../society/engine.py#L275), [353–362](../society/engine.py#L353): eylemler ve yönetici kapsamı. Baskı/gelir iptali yalnız kendisine bağımlı hedefe uygulanabilir; başlangıçta bunlar zenginlerdir. Burjuva içindeki halkçı kişiyi susturma mekanizması değildir.
- **D1:** [dynamics.py:66–177](../society/dynamics.py#L66): zarar, güven, grup farkları, kanıt ve sadakat. **D2:** [178–228](../society/dynamics.py#L178): geçiş, dönüş eşiği, bekleme ve temel yönelim.
- **A1:** [appraisal.py:24–84](../society/appraisal.py#L24): güven ve okunmuş bilgi/gelir deneyimi. **A2:** [86–151](../society/appraisal.py#L86): atıf, fayda ve yükün kutuplara ayrılması.
- Parametre aralıkları: [v2](../society/behavior-v2.json) / [v3](../society/behavior.json). `groups`, `dynamics`, `belief_step` alanlarının eşitliği ayrıca çalıştırılarak kontrol edildi.

## 2. v3 neyi değiştirdi; genel kurallar nerede karakteri bastırıyor?

- **Değişmeyenler:** yüzdeler, kimlik, parametre aralıkları, ağ/bütçe yapısı, ilk iki grubun kaynak kapısı ve zenginin yöneticiye bağımlılığı. Kimliğin korunması davranışın tamamının korunması demek değil.
- **Bütün gruplarda değişen:** ham ekonomik yük yerine sorumlu görülen kutba yazılan yük kullanılıyor; bilinirlik/ham akran desteği artık doğrudan alternatif çekiciliği değil. Muhaliflerin güvensizlik, burjuva/zenginlerin gelir kaybı ekleri de artık sıfırdan çekicilik yaratmıyor, var olanı çarpıyor (D1).
- **Parametreler tüketiliyor ama bazıları sonucu etkileyemiyor:** mevkili duyarlılığı kaynak güveninde; akran direnci mesaj ve siyasi kanıtta; ekonomik duyarlılık yükte ve yeni fayda önceliklerinde; risk/bağlılık eşiği çıkışta; temel direnç daha derin değişimde kullanılıyor. Fakat kapı hiç açılmıyorsa son eşik parametresini değiştirmenin sonuç üretmemesi, karakterin çalıştığına kanıt değildir. Bütün grupların konu eşikleri 0; gözlemciyi bu alanda koruyan özel direnç yok.
- **Yeni, önemli kilit:** huzursuz ve gözlemci `none` başlıyor. Mevkili kaynaklar A/B; `none` için siyasi ekonomik yük ve kendi mevkili güvensizliği 0 kalıyor. Standart profilde en yüksek akran kanıtı birikimi ≤0.375. En yüksek karar skoru huzursuzda ≤0.1875, gözlemcide ≤0.1125; en düşük geçiş eşikleri sırasıyla ≥1.28 ve ≥1.729. **Başlangıç kanıtı 0 ve normal A/B mevkili kaynakları altında ilk kutup geçişi zaman uzatmakla da açılamıyor.** Bu, düşük olasılık değil genel kuralın tarafsız kesimleri kilitlemesi. v2'nin ham zarar yolu bunu yapmıyordu. Ayrıca `none` için yalnız A aday seçilmesi v2'den kalan bir yanlılık (D1/A2).
- **Gözlemci hakkında doğrudan karşı örnek:** değiştirilmemiş varsayılan ağda A0098'in bir çıkışına karşı dört girişi var. Mevkili A0061'in normal konu mesajı görüşünü 50'den **55.3756**'ya değiştirdi. Temel yönelimi 1 kaldı. Yani “özellikler değişmedi” testi, “başkasının etkisi çok az/bağımsız muhakeme var” sözleşmesini doğrulamıyor.
- **Bilgi erişimi:** v3 gerekçeleri okunmuş mesaj/kişisel deneyim kimlikleriyle kaydediliyor; yük yeni kutba taşınmıyor. Ancak mesaj başlığındaki `source_alignment`, kamu bağlılığından değil gönderenin `alignment` alanından otomatik üretiliyor ([engine.py:280](../society/engine.py#L280)). Her mesajın yeni bağlılığı açıkça ilan ettiği varsayılmıyorsa özel/kamu bilgi sınırı tartışmalıdır. Bu varsayım netleşmeden bütün geçişlere “erişilebilir bilgiyle kesin doğrulandı” denemez.

## 3. Testler neyi kanıtlıyor?

**Mevcut 84 test yeniden çalıştırıldı: OK.** [Ham çıktı](character-audit-tests.txt), [profil kontrolü, yerel karşı örnek ve analitik sınırlar](character-audit-checks.json).

- Motor/hardening testleri bütçe, yetki, yerel gözlem, tekrar üretim ve kimlik ayrımını denetliyor. Bunlar karakterin hızını, amacını veya gerçekçi değişim süresini kanıtlamaz.
- `test_behavior.py` açıkça **v2** kullanıyor. Temel yönelim testi ayrıca eşik ölçeğini değiştiriyor; varsayılan v3'ün altı karakter doğrulaması değil.
- `test_appraisal.py` atıf/fayda ayrımı için davranışsal kanıt sağlıyor; fixture çoğunlukla tek bir güç yanlısı A0001. Bir test gözlemciyi değil A0001'in gerçek geçişini gösteriyor. İki küçük trial testi de altı karakterin tamamını ölçmüyor.
- `test_observer_traits_unchanged` trait sözlüğünü karşılaştırıyor; konu görüşünü veya etkiyi değil. İlk iki grubun akran kapısına test var; ama her iki grubu, bütün mesaj türlerini ve aktarılan asıl kaynakları birlikte kapsayan tam sözleşme testi yok.

**Sonraki aşama için öneriler — bu tur eklenmedi:**

| Grup | Hedefli karakter testi |
|---|---|
| Güç yanlısı | Aynı kanıtı akran, karşı mevkili ve kendi mevkili kaynağından ver; yalnız sonuncunun konu/atıf/faydayı değiştirmesini ve akranın sadece iletici olabilmesini denetle. |
| Muhalif | Aynı testi B için simetrik yap; ayrıca karşıtlığın yalnız başlangıç etiketi mi yoksa davranış mı olduğunu ayrı sınayacak sözleşmeyi netleştir. |
| Burjuva | Eşit koşullarda müttefik/kurumsal çıkış maliyetinin gerçekten fark yaratmasını ölç. Senaryo ve halkçı azınlık için şu an uygulanmış mekanizma yok; test başarısı iddia edilemez. |
| Zengin | Doğru yönetici gelirini azaltabilsin, başka yönetici azaltamasın; bağımlılık yönünü ve bilgi kapsamını koru. Rekabet/işçi geliri etkileşimi henüz test edilecek uygulamaya sahip değil. |
| Huzursuz | Uzun süreli yerel A ve B kanıtıyla ilk geçiş kilidini görünür kıl; ayrı olarak destekli/desteksiz kısa toplu tepki sözleşmesi çıkar. Parti geçişini isyan yerine kullanma. |
| Gözlemci | Gelen/giden trafik, mevkili/akran konu etkisi ve uzun ufuktaki temel yönelim ayrı ölçülsün. Trait sabitliği yerine gerçek davranış sınansın. |

## Son ayrım

**Korunan parçalar:** oranlar/kimlikler; ilk iki kesimin kendi mevkili kaynağına bağlı fikir kapısı; zenginin kurumsal bağımlılığı; gözlemcinin derin yönelim direnci.

**Tarifle çelişen veya bozulmuş parçalar:** hızlı/yavaş iletişim ayrımının olmaması; gözlemcinin sıradan konu etkilenmesi; v3'te tarafsızların ilk geçiş kilidi. Bunların hepsi son değişikliklerden kaynaklanmıyor; v3 kilidi ile eski eksikler ayrılmalı.

**Uygulanmamış/kanıtsız parçalar:** kontrollü yönetim senaryosu, halkçı istisnalar ve susturulması, zengin rekabeti/sömürü ilişkisi, destekle başlayan ve sönen isyan, gözlemcinin özel analitik muhakemesi; ayrıca “nadir” ve “zamana yayılan” değişimin gerçekçi ölçeği. Önce bunları konuşmak gerekiyor; daha düşük bir toplam geçiş oranı bu boşlukları kapatmıyor.
