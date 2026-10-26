# Altı karakter denetimi — kısa sonuç

> Tarihsel v3.0 denetimi. Sonraki sınırlı v3.1 değişiklikleri için [ilk aşama raporuna](collective-stage1.md) bakın; aşağıdaki kod referansları denetim anına aittir.

**25 Ekim 2026.** Davranış kodu, katsayılar ve test dosyaları değiştirilmedi.
[Karakter sözleşmesi kaydedildi](../docs/six-character-contract.md).
Bunlar kurgu hedefleridir; gerçek toplumun doğrulanmış özellikleri sayılmadı.

**Sonuç: Altı karakterin bütünüyle korunduğu söylenemez.** Sorunların bir bölümü
v2'den beri eksik; bir bölümü v3 kurallarının etkileşiminden kaynaklanıyor.
Sayısal grup parametrelerinin aynı kalması, davranışın aynı kalmasını garanti etmiyor.

| Karakter | Korunan çekirdek | Eksik / çelişen taraf |
|---|---|---|
| %30 güç yanlısı | Kendi tarafının mevkili kaynağına açık; halk kaynaklarına fikir kapısı kapalı | Özel hızlı/sık iletişim yok; mevki/para gücünü izlemek yerine A başlangıcı var |
| %30 muhalif | Benzer kapı, B başlangıcı ve farklı mevkili kaynaklar | Sürekli karşıtlık davranışı değil başlangıç etiketi; iletişim yine ortak |
| %15 burjuva | Kurumsal yetki, müttefiklere bağlı çıkış maliyeti | Kontrollü senaryo, halkçı azınlık ve susturma uygulanmamış; nadir geçiş ayrıca kanıtlanmış değil |
| %12 zengin | Mevkiliye bağımlılık gerçekten gelir iptaliyle işliyor | Rekabet, halktan gelir elde etme/sömürü ve zayıf iletişim karakteri yok |
| %10 huzursuz | Tarafsız başlangıç, düşük akran etkisi | Destekle isyan ve kısa sönüm yok; v3'te ilk kutup geçişi yapısal olarak kilitleniyor |
| %3 gözlemci | Tarafsızlık, az çıkış bağlantısı ve çok dirençli temel yönelim | Gelen trafik az olmak zorunda değil; sıradan konu görüşlerinde mevkili etkisi güçlü; aynı ilk geçiş kilidi var |

## v3 için en önemli bulgu

Huzursuz ve gözlemci `none` başlıyor. Yeni ekonomik atıf kuralı A/B'ye yazıyor;
`none` için siyasi ekonomik yük ve kendi mevkili güvensizliği sıfır kalıyor.
Standart başlangıçta kalan akran kanıtının üst sınırı **0.375**. En yüksek karar
skorları huzursuzda **0.1875**, gözlemcide **0.1125**; en düşük eşikler ise
**1.28** ve **1.729**.

**Normal A/B mevkili kaynakları ve başlangıç kanıtı 0 altında bu ilk geçiş,
süreyi uzatmakla da açılamıyor.** Bu, zor ama mümkün değişim değil, genel kuralın
iki tarafsız karakteri kilitlemesi. Ayrıca `none` için yalnız A'nın aday seçilmesi
v2'den kalan bir yanlılık. Parti geçişi isyan değildir; isyanın kendisi iki sürümde de yok.
Kod: [dynamics.py:120–182](../society/dynamics.py#L120),
[appraisal.py:86–136](../society/appraisal.py#L86).

Diğer gruplarda eşikler/dirençler hâlâ kullanılıyor; fakat muhaliflerin güvensizlik,
burjuva/zenginlerin gelir kaybı ekleri artık sıfırdan çekicilik oluşturmuyor.
Bilinirlik ve ham akran desteği de tek başına çekicilik değil. Bunlar davranış
farkıdır; katsayı eşitliğiyle yok sayılamaz.

## Testler ve bilgi sınırı

- **84 mevcut test yeniden çalıştırıldı: OK.** Bu sonuç altı karakterin tümünü doğrulamıyor.
- Eski davranış testleri v2 fixture kullanıyor. v3 appraisal testleri çoğunlukla
  tek bir güç yanlısını sınayıp yeni ayrımları doğruluyor.
- Değiştirilmemiş varsayılan ağda bir gözlemciye ulaşan mevkili konu mesajı,
  görüşünü **50 → 55.3756** değiştirdi; temel yönelimi 1 kaldı. “Trait değişmedi”
  testi bu etkilenmeyi yakalamıyor.
- Geçiş gerekçelerinde okunmuş mesaj/deneyim kimlikleri var. Ancak mesajdaki
  kaynak kutbu, gönderenin kamu bağlılığından değil `alignment` alanından
  otomatik geliyor ([engine.py:280](../society/engine.py#L280)). Her mesaj açık
  bağlılık ilanı sayılmıyorsa özel/kamu bilgi sınırı ayrıca tartışılmalı.

[11 özellik × 6 grup durum matrisi, kod gerekçeleri ve her grup için hedefli test önerileri](six-character-audit-details.md)
· [Test çıktısı](character-audit-tests.txt)
· [Yerel kontrol ve analitik sınırlar](character-audit-checks.json)

## Önce neyi konuşmalıyız?

**Korunan parçalar:** mevkili-kaynak kapıları, kurumsal bağımlılık, kimlikler ve
gözlemcinin derin yönelim direnci. **Bozulmuş/çelişen parçalar:** iletişim ayrımı,
gözlemcinin sıradan etkilenmesi ve yeni tarafsızlık kilidi. **Kanıtı veya uygulaması
olmayanlar:** senaryo yönetimi, rekabet, destekli isyan, özel analitik muhakeme ve
“nadir/zamana yayılmış” değişimin kabul edilebilir ölçeği.

Senin kaygın açısından: **az değişim de tek başına doğru karakter demek değil.**
Ani kitlesel dönüşüm ile sonsuza kadar kapalı geçiş arasında ayrım yapmalıyız.
Önceki %80, fiyat şokuydu; %71 geçiş sonucu ise 30 günün toplamıydı, anlık değildi.
Bu ayrım o sonucu gerçekçi yapmaz. Bu tur hiçbir davranış düzeltmesi yapılmadı.
