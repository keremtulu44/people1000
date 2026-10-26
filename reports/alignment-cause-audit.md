# Bağlılık değişim nedenleri — teşhis ve kalibrasyon kanıtı

## Kapsam ve değiştirilmeyenler
**Davranış profili v2.0.0 ve katsayıları değiştirilmedi. Kalibrasyon yapılmadı.** Yapısal karar denklemleri normal kolda aynıdır; yalnızca açıklanabilirlik alanları ve isimlendirilmiş ablation anahtarları eklendi.
260 eski koşu ve 56204 eski geçiş incelendi. 840 yeni 30 günlük koşu tamamlandı: 100 kişide 20 tohum × 4 şok × 2 açıklama × 4 mekanizma = 640; 1000 kişide 5 tohum aynı matris = 160; 100 kişide 20 tohum × akran açık/kapalı pozitif kontrol = 40. Toplam 840.
100 kişilik ana sonuçlar 20 tohumla; 1000 kişilik sonuçlar 5 tohumla keşifsel ölçek doğrulamasıdır, aynı kesinlikte değildir. Tam matris ve geçiş kayıtlarının maliyetini sınırlamak için bu ayrım protokole baştan yazıldı.
Şoklar: yok, %10 hafif, %40 orta, %80 şiddetli. Fiyat olayı dakika 60. Açıklama kollarında gün 1/8/15/22, aynı yönetici ve aynı ilk iki alıcı, beklenen zarar iddiası 0. Müdahalesiz kolda yönetici açıklaması eklenmez. Aynı tohum/başlangıç, aynı politika ve parametreler korunur.

## 1. Eski kayıtlar neyi gerçekten gösteriyor?
Eski 56204 geçişin 52791 tanesinde öğrenilmiş yönetici açıklaması yoktu. Bu, yüksek geçişi açıklama veya güven aşınmasının tek başına açıklayamayacağını gösterir; ekonomik etki ile başlangıç güveni ayrıca sınandı.
Eski kayıtta geçişin eski/yeni kutbu, eşik, çekicilik, çıkış bedeli, yük, güvensizlik ve birikmiş kanıt var. Aynı handler’ın behavior_updated kaydındaki loyalty_before tarihsel özel sadakati açıkça kaydeder; bu alan kullanılabilir, gelecekteki gözlem değildir.
Ancak geçiş öncesi tam konu durumu, açık destek/kutup anlık görüntüsü, tam başlangıç güven haritası, maruz kalma özeti ve kanıt bileşenleri yoktur. Bunlar son durumdan doldurulmadı; eski çıkarımda null/eksik olarak işaretlendi. Önceki bir core değişimi varsa yalnızca o kayıt raporlandı; siyasi geçiş temel yönelim değişimi sayılmadı.
Her eski geçiş runs/diagnosis/legacy-transitions.jsonl.gz içinde; örnek ve kapsam reports/diagnosis/legacy-audit.json içinde. Yeni koşular eksik alanları karar anında kaydeder.

## 2. Normal mekanizma altında şok şiddeti
Oran = en az bir kere siyasi bağlılık değiştiren kişi / nüfus. Tekrar geçişler bu orana iki kere eklenmez.

| Nüfus | Şok | Açıklama | Tohum | Değişen oran ort. | Medyan | Min–maks | Yaklaşık %95 aralık |
|---:|---|---|---:|---:|---:|---|---|
| 100 | none | 0 | 20 | 0.0000 | 0.0000 | 0.0000–0.0000 | [0.0, 0.0] |
| 100 | none | 1 | 20 | 0.0000 | 0.0000 | 0.0000–0.0000 | [0.0, 0.0] |
| 100 | mild | 0 | 20 | 0.0000 | 0.0000 | 0.0000–0.0000 | [0.0, 0.0] |
| 100 | mild | 1 | 20 | 0.0000 | 0.0000 | 0.0000–0.0000 | [0.0, 0.0] |
| 100 | moderate | 0 | 20 | 0.0040 | 0.0000 | 0.0000–0.0200 | [0.0013780842680850406, 0.00662191573191496] |
| 100 | moderate | 1 | 20 | 0.0050 | 0.0000 | 0.0000–0.0300 | [0.0016652704678442698, 0.00833472953215573] |
| 100 | severe | 0 | 20 | 0.7180 | 0.7150 | 0.6600–0.7900 | [0.7032502246225846, 0.7327497753774154] |
| 100 | severe | 1 | 20 | 0.7335 | 0.7300 | 0.6800–0.8100 | [0.7202161427605573, 0.7467838572394427] |
| 1000 | none | 0 | 5 | 0.0000 | 0.0000 | 0.0000–0.0000 | [0.0, 0.0] |
| 1000 | none | 1 | 5 | 0.0000 | 0.0000 | 0.0000–0.0000 | [0.0, 0.0] |
| 1000 | mild | 0 | 5 | 0.0000 | 0.0000 | 0.0000–0.0000 | [0.0, 0.0] |
| 1000 | mild | 1 | 5 | 0.0000 | 0.0000 | 0.0000–0.0000 | [0.0, 0.0] |
| 1000 | moderate | 0 | 5 | 0.0020 | 0.0010 | 0.0000–0.0050 | [0.0002469227056401651, 0.0037530772943598347] |
| 1000 | moderate | 1 | 5 | 0.0020 | 0.0010 | 0.0000–0.0050 | [0.0002469227056401651, 0.0037530772943598347] |
| 1000 | severe | 0 | 5 | 0.7268 | 0.7270 | 0.7140–0.7380 | [0.7190239609054481, 0.7345760390945519] |
| 1000 | severe | 1 | 5 | 0.7284 | 0.7300 | 0.7150–0.7410 | [0.7200936689206364, 0.7367063310793635] |

Aralıklar tohum değişkenliğinin normal yaklaşımıdır; gerçek toplum belirsizliği değildir. Özellikle 5 tohumda zayıf betimleyici aralıklardır. İlk geçiş süreleri yalnızca değişen kişilerde hesaplanır; değişmeyenler sansürlüdür ve group-summary.csv içinde ayrıca sayılır.

## 3. Kontrollü ablation sonuçları
- economic_evidence: yalnızca birikimli siyasi kanıta giren ekonomik terim sıfırdır. Gider, kayıp, burden, konu görüşü, özel sadakat ve temel yönelim kanıtı korunur. Bu nedenle “ekonomi tamamen yok” deneyi değildir.
- trust_erosion: yalnızca negatif güven güncellemesi sıfırlanır; başlangıç güvensizliği ve güven toparlanması korunur. Başlangıç güveninin etkisini izole etmez.
- peer: akran sinyali birikimi, akran çekiciliği/kanıtı ve akran konu iknası kapalıdır; mesajın ulaşması, kaynak tanınması ve otorite tahminleri korunur.
Katsayılar sabittir. Sonraki siyasi bağlılık, aynı-kutup güven havuzu, mesajın yayımlandığı kutup ve başka kararlar değişebileceğinden ablation farkı doğrudan + dolaylı toplam etkidir. Bağımsız toplanabilir nedensel pay değildir.

| Nüfus | Şok | Açıklama | Kapalı mekanizma | Eşleştirilmiş oran farkı ort. | Yaklaşık %95 | Negatif / sıfır / pozitif tohum |
|---:|---|---:|---|---:|---|---|
| 100 | moderate | 0 | economic_evidence | -0.0040 | [-0.00662191573191496, -0.0013780842680850406] | 7 / 13 / 0 |
| 100 | moderate | 0 | peer | 0.0000 | [0.0, 0.0] | 0 / 20 / 0 |
| 100 | moderate | 0 | trust_erosion | 0.0000 | [0.0, 0.0] | 0 / 20 / 0 |
| 100 | moderate | 1 | economic_evidence | -0.0050 | [-0.00833472953215573, -0.0016652704678442698] | 8 / 12 / 0 |
| 100 | moderate | 1 | peer | 0.0000 | [0.0, 0.0] | 0 / 20 / 0 |
| 100 | moderate | 1 | trust_erosion | -0.0010 | [-0.0023489645151589028, 0.00034896451515890295] | 2 / 18 / 0 |
| 100 | severe | 0 | economic_evidence | -0.7180 | [-0.7327497753774154, -0.7032502246225846] | 20 / 0 / 0 |
| 100 | severe | 0 | peer | 0.0000 | [0.0, 0.0] | 0 / 20 / 0 |
| 100 | severe | 0 | trust_erosion | 0.0000 | [0.0, 0.0] | 0 / 20 / 0 |
| 100 | severe | 1 | economic_evidence | -0.7335 | [-0.7467838572394427, -0.7202161427605573] | 20 / 0 / 0 |
| 100 | severe | 1 | peer | 0.0000 | [0.0, 0.0] | 0 / 20 / 0 |
| 100 | severe | 1 | trust_erosion | -0.0155 | [-0.02127154362276451, -0.009728456377235498] | 14 / 6 / 0 |
| 1000 | moderate | 0 | economic_evidence | -0.0020 | [-0.0037530772943598347, -0.0002469227056401651] | 4 / 1 / 0 |
| 1000 | moderate | 0 | peer | 0.0000 | [0.0, 0.0] | 0 / 5 / 0 |
| 1000 | moderate | 0 | trust_erosion | 0.0000 | [0.0, 0.0] | 0 / 5 / 0 |
| 1000 | moderate | 1 | economic_evidence | -0.0020 | [-0.0037530772943598347, -0.0002469227056401651] | 4 / 1 / 0 |
| 1000 | moderate | 1 | peer | 0.0000 | [0.0, 0.0] | 0 / 5 / 0 |
| 1000 | moderate | 1 | trust_erosion | 0.0000 | [0.0, 0.0] | 0 / 5 / 0 |
| 1000 | severe | 0 | economic_evidence | -0.7268 | [-0.7345760390945519, -0.7190239609054481] | 5 / 0 / 0 |
| 1000 | severe | 0 | peer | 0.0000 | [0.0, 0.0] | 0 / 5 / 0 |
| 1000 | severe | 0 | trust_erosion | 0.0000 | [0.0, 0.0] | 0 / 5 / 0 |
| 1000 | severe | 1 | economic_evidence | -0.7284 | [-0.7367063310793635, -0.7200936689206364] | 5 / 0 / 0 |
| 1000 | severe | 1 | peer | 0.0000 | [0.0, 0.0] | 0 / 5 / 0 |
| 1000 | severe | 1 | trust_erosion | -0.0014 | [-0.0025760000000000023, -0.00022400000000000024] | 3 / 2 / 0 |

Tüm şoklar ve açıklama farkları paired-*.csv / metrics.json içinde. Akran ana matrisi yalnızca ekonomik otorite açıklamaları içerir; public_support akran girdisi yoktur. Dolayısıyla buradaki sıfır fark, genel olarak akran mekanizmasının etkisiz olduğunu kanıtlamaz. Ayrı pozitif kontrolde aynı kamu destek mesajları her iki kola eklenir.

| Akran pozitif kontrolü, 100 kişi | Oran ort. | Geçiş olayı ort. |
|---|---:|---:|
| none | 0.7425 | 75.0000 |
| peer | 0.7335 | 74.1500 |

## 4. Kesim bazlı teşhis (%80 şok, normal mekanizma)
Aşağıdaki oranlar siyasi bağlılıktır; temel yönelim için ayrı sütun vardır. Gözlemcilerin konu görüşü değişebilirken siyasi bağlılığı/temel yönelimi değişmemiş olabilir.

| Nüfus | Açıklama | Kesim | Değişen kişi ort. | Oran | İlk geçiş gün ort.¹ | Dönüş oranı² | Konu değişim oranı | Şiddet farkı | Temel değişen kişi |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 100 | 0 | authority | 6.9500 | 0.4633 | 26.6895 | 0.0000 | 1.0000 | 0.2921 | 0.0000 |
| 100 | 0 | discontented | 0.0000 | 0.0000 | — | — | 1.0000 | 0.5000 | 0.0000 |
| 100 | 0 | observer | 0.0000 | 0.0000 | — | — | 1.0000 | 0.5000 | 0.0000 |
| 100 | 0 | opposition | 29.9000 | 0.9967 | 21.4247 | 0.0017 | 1.0000 | 0.1841 | 0.0000 |
| 100 | 0 | power_aligned | 26.7500 | 0.8917 | 24.6014 | 0.0000 | 1.0000 | 0.1447 | 0.0000 |
| 100 | 0 | wealthy | 8.2000 | 0.6833 | 25.7542 | 0.0000 | 1.0000 | 0.2099 | 0.0000 |
| 100 | 1 | authority | 7.3000 | 0.4867 | 26.4434 | 0.0000 | 1.0000 | 0.2848 | 0.0000 |
| 100 | 1 | discontented | 0.0000 | 0.0000 | — | — | 1.0000 | 0.5000 | 0.0000 |
| 100 | 1 | observer | 0.0000 | 0.0000 | — | — | 1.0000 | 0.5000 | 0.0000 |
| 100 | 1 | opposition | 29.9000 | 0.9967 | 21.4247 | 0.0267 | 1.0000 | 0.1826 | 0.0000 |
| 100 | 1 | power_aligned | 27.6000 | 0.9200 | 24.0091 | 0.0000 | 1.0000 | 0.1472 | 0.0000 |
| 100 | 1 | wealthy | 8.5500 | 0.7125 | 25.6552 | 0.0000 | 1.0000 | 0.1998 | 0.0000 |
| 1000 | 0 | authority | 73.6000 | 0.4907 | 26.6968 | 0.0000 | 1.0000 | 0.2805 | 0.0000 |
| 1000 | 0 | discontented | 0.0000 | 0.0000 | — | — | 1.0000 | 0.5000 | 0.0000 |
| 1000 | 0 | observer | 0.0000 | 0.0000 | — | — | 1.0000 | 0.5000 | 0.0000 |
| 1000 | 0 | opposition | 298.2000 | 0.9940 | 21.4830 | 0.0020 | 1.0000 | 0.1840 | 0.0000 |
| 1000 | 0 | power_aligned | 270.8000 | 0.9027 | 24.5203 | 0.0000 | 1.0000 | 0.1418 | 0.0000 |
| 1000 | 0 | wealthy | 84.2000 | 0.7017 | 25.6476 | 0.0000 | 1.0000 | 0.2025 | 0.0000 |
| 1000 | 1 | authority | 73.8000 | 0.4920 | 26.6498 | 0.0000 | 1.0000 | 0.2805 | 0.0000 |
| 1000 | 1 | discontented | 0.0000 | 0.0000 | — | — | 1.0000 | 0.5000 | 0.0000 |
| 1000 | 1 | observer | 0.0000 | 0.0000 | — | — | 1.0000 | 0.5000 | 0.0000 |
| 1000 | 1 | opposition | 298.2000 | 0.9940 | 21.4830 | 0.0087 | 1.0000 | 0.1832 | 0.0000 |
| 1000 | 1 | power_aligned | 272.0000 | 0.9067 | 24.4144 | 0.0000 | 1.0000 | 0.1429 | 0.0000 |
| 1000 | 1 | wealthy | 84.4000 | 0.7033 | 25.6419 | 0.0000 | 1.0000 | 0.2018 | 0.0000 |

¹ Yalnızca değişen ajanlar; süre özeti, değişen ajanların tohum içi ortalamalarının tohumlar arası ortalamasıdır. Değişmeyen tohumlara süre=0 atanmaz. Sağ sansür nedeniyle tüm topluma ait beklenen süre değildir. ² En az bir önceki kutbuna dönen / en az bir geçiş yapan; ilk kimliğe dönmekle her önceki kutba dönüş aynı olmayabilir. Ham kesim/tohum tabloları ayrıca saklanır.
Kayıp min/ortalama/maks ve açık–özel kutup farkını hesaba katan normalize mesafe group-summary.csv içindedir. Bu deneyde temel gider aynı olduğundan ek gider kaybı aynı şok altında kesimler arasında eşittir; tepki katsayıları ve gelir/birikim tamponları farklıdır.

### Kesime göre geçişteki sayısal kanıt (100 ajan, açıklamalı %80 şok)
Aşağıdaki bileşim, geçiş anındaki pozitif ekonomik/güvensizlik/akran defteridir; rahatlama ayrı negatif terimdir. Bu oranlar bağımsız nedensel paylar değildir.
| Kesim | Geçiş başına ekonomik birikim | Geçiş başına güvensizlik birikimi | Geçiş başına akran birikimi | Kodla birlikte yorum |
|---|---:|---:|---:|---|
| authority | 4.2392 | 0.5422 | 0.0000 | Ekonomik birikim + güven; konum/yerel çevre maliyeti geçişi geciktirir. |
| discontented | — | — | — | Bu kolda siyasi geçiş yok; akran girdisi olmadan çekicilik kapısı kilitli. |
| observer | — | — | — | Bu kolda siyasi geçiş ve temel değişim yok; iki değişim türü ayrı eşiklere tabidir. |
| opposition | 3.0939 | 0.4319 | 0.0000 | Ekonomik birikim + kendi otoritesine güvensizlik; güvensizlik alternatif çekiciliğine de eklenir. |
| power_aligned | 3.5662 | 0.5835 | 0.0000 | Ekonomik birikim + aynı-kutup güveni; düzen maliyeti daha yüksek. |
| wealthy | 3.9641 | 0.5258 | 0.0000 | Ekonomik birikim + güven; kurumsal bağımlılık ek çıkış bedeli getirir. |
Aynı büyüklük ve aynı eşik dağılımı varsayılmadığından kesim farkları yalnızca kanıt miktarıyla açıklanmaz. Tohum değişkenliği, dönüşler ve özel/kamu farkları diğer tablolarda ayrıdır.

## 5. Kod yolundan ölçülebilir açıklama
`engine._handle(behavior) → dynamics.daily → eligible` geçiş yoludur. Aşağıdakiler kayıt ve kodla doğrudan sınanabilir:
1. Ekonomik etki iki kademeli birikir: burden = .90×burden + harm×duyarlılık; kanıt = .96×eski_kanıt + .08×burden + .12×güvensizlik×otorite_duyarlılığı + .05×akran − rahatlama. Süren şok iki kalıcı durum üzerinden aynı eşiklere iter.
2. Alternatif kutbun yerel olarak bilinmesi tek başına .35 çekicilik sağlar. Alternatifin ekonomik olarak daha iyi olduğuna dair ayrı kanıt zorunlu değildir. Çekicilik hem kapı (≥.3) hem kanıt çarpanıdır.
3. Özel sadakat azalır ama eligible koşulunda doğrudan kullanılmaz. Bu nedenle özel sadakat düşüşü siyasi geçişi tek başına açıklayan bir kapı değildir. Kamu desteği ve baskı da bu eşikte doğrudan yoktur.
4. Mevcut başlangıç güveni 1’den düşükse hiç açıklama öğrenmeyenlerde de distrust terimi oluşur. Trust-erosion ablation bu başlangıç kanalını kapatmaz.
5. Geçişte siyasi kanıt sıfırlanır fakat ekonomik burden sıfırlanmaz. Aynı zarar yeni kutupta da sürüyorsa kanıt yeniden hızla birikir; +.30 dönüş marjı ve 5 gün bekleme dönüşü yavaşlatır ama engellemez.
6. Hoşnutsuzlarda .35×.5=.175, gözlemcilerde .35×.3=.105 çekicilik, akran girdisi olmadan .3 kapısını geçemez. Sıfır siyasi değişim yalnızca yüksek dirençten kaynaklanmaz; yapısal kapı da vardır.
7. Yönetici allies sayımı kodda aynı kutuptaki bütün known kaynaklarını sayar; yalnızca kurumsal ittifakları saymaz. Bu bir semantik basitleştirmedir; bu görevde değiştirilmedi.

Her geçişteki katkı defteri ekonomik/güvensizlik/akran/rahatlama bileşenlerini ayrı tutar; negatif toplamın sıfıra kırpılması ve geçiş sonrası sıfırlama da izlenir. Defter karara girdi olmaz. Toplamı kaydedilmiş kanıta eşittir (kayan nokta toleransı).
metrics.json threshold_arithmetic, o anda bir bileşen çıkarılsaydı eşik aşılır mıydı sorusunu yanıtlar. Bu yalnızca yerel aritmetik duyarlılıktır; bütün geçmişin değiştiği ablation yerine geçmez.

### Geçiş anındaki aritmetik duyarlılık
Aşağıdaki yerel test, geçmişi sabit tutup yalnızca o anki birikmiş bileşeni çıkarır. Birden fazla bileşen aynı eşikte gerekli görünebilir; yüzdeler toplanamaz ve “nedensel pay” değildir.
| Nüfus | Açıklama | Geçiş | Mesajsız geçiş | Ekonomik bileşen çıkarılınca eşik geçilemeyen | Güvensizlik bileşeni çıkarılınca |
|---:|---:|---:|---:|---:|---:|
| 100 | 0 | 1437 | 1437 | 1437 | 1409 |
| 100 | 1 | 1483 | 1130 | 1483 | 1457 |
| 1000 | 0 | 3637 | 3637 | 3637 | 3576 |
| 1000 | 1 | 3655 | 3485 | 3655 | 3596 |
Bunların ana karşılaştırması tam-yörünge ablation tablosudur. Eşik anında küçük bir terim bile sonucu çevirebilir; bu durum onu en büyük üretici mekanizma yapmaz.

## 6. Eksik veri ve açıklanabilirlik sınırları
Yeni diagnostic kaydı geçişten önceki özel sadakat, günlük güncelleme öncesi ve karar anındaki konu görüşleri, kamu kutbu/desteği, temel yönelim, yerel ekonomik maruziyet, okunmuş mesajların teslim/öğrenme zamanları, kaynak güvenleri, o günün güven değişimleri, akran durumu, baskı, alternatif, maliyet, eşik ve dönüş koşullarını içerir.
Önceki güven değişimlerinin tam olay akışı yalnızca tam snapshot saklanan tohum 0 koşullarında bulunur; diğerlerinde geçiş anı anlık görüntüsü, o günkü değişimler, mesaj geçmişi ve nihai ajan kayıtları saklanır. Geçiş öncesinin kaydedilmemiş başka iç durumları sonradan üretilmez. Tüm koşular betikle yeniden üretilebilir.
İlk geçişte last_switch_day=-1000 başlangıç sentinelidir; elapsed_days değeri gerçek bin günlük maruziyet olarak yorumlanmaz. Gerçek maruziyet diagnostic_exposure alanlarında ayrı tutulur.

## 7. Kanıtın sınırı ve kalibrasyon önerileri
Ablation ve doz–yanıt sonuçları birikimli ekonomik siyasi kanıt yolunu sınar; .08 katsayısının tek başına yanlış olduğunu kanıtlamaz. Kalıcılık, zarar normalizasyonu, alternatif görünürlüğü ve eşik birlikte belirleyicidir. Başlangıç güvensizliğini güven aşınmasıyla karıştırmayın.
Öneri 1: İlk sonraki kontrollü deneyde yalnızca alternatifin “bilinmesi” ile “beklenen faydasının üstün olması” koşulunu ayırın; mevcut .35 değerini keyfî azaltmayın. Gerekçe: kodda karşılaştırmalı üstünlük şartı yok ve mesaj almayan geçişler yaygın.
Öneri 2: Ekonomik yükün hangi kutba atfedildiğini ve geçiş sonrası nasıl taşındığını ayrı hipotezlerle sınayın. Gerekçe: eski yük yeni kutupta da kanıt üretir; dönüş marjını rastgele artırmak nedeni gizleyebilir.
Öneri 3: Başlangıç güven priörünü ve sonradan güven aşınmasını ayrı kollarla sınayın; mevcut erosion ablation başlangıç kanalını ayırmaz.
Öneri 4: Akran girdisi olan/olmayan deneyleri ayırın. Boş girdi altındaki null etkiyi akran direnci katsayısına bağlamayın.
Öneri 5: Hoşnutsuz/gözlemci kapılarının bilinçli varsayım mı yoksa istenmeyen kilit mi olduğunu netleştirin. Siyasi değişim yokluğunu temel yönelim değişmezliği diye sunmayın.
Bu görevde hiçbir eski/yeni kalibre profil üretilmedi: **parametre değişikliği yok**. Eski profil hashleri ve koşu protokolleri karşılaştırıldı. Öneriler gelecek deneyler içindir.

## 8. Dosyalar, testler ve tekrar üretim
Kod: dynamics.py (salt teşhis defteri/anlık görüntü + ablation kapıları), engine.py (doğrulanan/saklanan ablation seçeneği), diagnosis.py (eski kayıt çıkarımı ve eşleştirilmiş koşular), diagnosis_report.py (analiz). behavior.json değişmedi.
Testler: tests/test_diagnosis.py; tam paket ve gerçek sonuç reports/diagnosis-tests.txt. Eski ham artifact mevcutsa ayrıca önceki davranışla tüm ajan durumları ve geçiş zamanları karşılaştırılır; yoksa bu tek test açıkça skip olur.
Yeni normal %80 kolları önceki A/B ile 50 tohum/koşulda karşılaştırıldı; eşit sayımlar: 50. Sayım eşitliği tek başına tam yörünge eşitliği değildir; bunun için ayrı regresyon testi vardır.
Komutlar:
```bash
python -m society.diagnosis --legacy
python -m society.diagnosis --seeds 20 --population 100
python -m society.diagnosis --seeds 5 --population 1000
python -m society.diagnosis --seeds 20 --population 100 --peer-probe
python -m society.diagnosis --report
python -m unittest discover -s tests -v > reports/diagnosis-tests.txt 2>&1
```
Küçük tablolar reports/diagnosis/; her yeni geçişin ayrıntıları ve son ajanlar runs/diagnosis/<run-id>/ altında sıkıştırılmıştır. Tohum 0 tam snapshotları da saklanır. Büyük veriler Git dışında; protokol ve kodla yeniden üretilebilir.
RNG yalnızca başlangıçta tüketilir. Bütün eşleştirilmiş kolların ilk ajan/ağ hashleri aynı doğrulandı. Ablation sonrası akış farklılaşması hata değil müdahalenin dolaylı etkisi olabilir. Ölçümler model içi kanıttır, gerçek toplum yasası değildir.

### Yorum sınırı ve sonraki deney önceliği
“Nadir” için önceden belirlenmiş şok/ufuk/kesim bazlı sayısal kabul aralığı yoktu. Bu yüzden yüksek %80 şok oranı tek başına bir katsayının yanlış olduğunu kanıtlamaz. Hafif/orta/şiddetli doz farkı ve kontrollü kanal kapatmaları birlikte değerlendirilmelidir.
Ekonomik zarar normalizasyonu gider artışını esas alır; fiyat şokunda varlıklı ajan net gelirini korusa da gider artışı aynı harm değerini verir. Servet tamponu bu normalizasyonda yoktur. Kesimlere eşit zarar verilmesi kod gerçeğidir; bunun fazla değişimin nedeni olup olmadığını ayrı kırılganlık deneyi olmadan kesinleştirmiyoruz.
Yeni ana matriste baskı uygulanmadı; sıfır baskı kaydı baskının genel etkisizliğini göstermez. Akran pozitif kontrolü girdi yolunu sınar, tüm sosyal ağ davranışlarının doğrulanması değildir.

### İlave sayısal sınır bulgusu (bu görevde değiştirilmedi)
100 kişi/tohum 0/%10 şok/açıklamalı koşuda hata değerleri [0.10000000000000009]; negatif güven güncellemesi 644. Matematiksel .1 sınırı ikili kayan noktada .10000000000000009 olarak oluşuyor; error > .1 dalı aşınmayı seçiyor. Bu hassasiyet yüksek %80 şok oranının açıklaması değildir, ama hafif şok güven analizinde önemlidir. Tolerans veya sayısal temsil politikası ayrı regresyonla kararlaştırılmalı; mevcut dondurulmuş koşulara geriye dönük düzeltme uygulanmadı.

Son tam test paketi: 65 test; ham durum: OK. Sonuç dosyası değiştirilmeden saklanmıştır.
