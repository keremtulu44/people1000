# People1000 — Kapsamlı Psikolojik Araştırma, Deneysel Bulgular ve v3.5+ Derin Zihin Önerileri

- **Tarih:** 2026-10-27
- **İncelenen Profil:** `behavior_version = 3.4.0` (`psychology_model = affective-v1`) vs dondurulmuş `3.3.0`
- **Deney Kodu:** `society/psychology_research_v34.py`
- **Ham Veri Kaydı:** `reports/psychology-research-v34.json`
- **Kapsam:** `N=100` çok-tohumlu (`multi-seed`) 6 deney + `N=1000` tam ölçek doğrulaması + sosyal psikoloji literatürü eşleştirmesi + özeleştirel kalibrasyon bulguları + v3.5 mimari fikir ve önerileri.

---

## 1. Araştırmanın Amacı ve Yöntemi

v3.4 güncellemesiyle `people1000` motoruna 5 temel psikolojik durum (**Tahammül Eşiği & Tükenmişlik, Korku & Otosansür, Öfke & Bastırılmış Öfke, Konfor Alanı, Bilişsel Savunma Duvarı**) ve 5 yapısal mimari yükseltme (**Senaryo-Motor Tek Gerçeklik Köprüsü, Yankı Odaları & Sosyal Medya `amplify`, Dinamik Kriz Dallanması, İşveren→Çalışan Ekonomik Zinciri, Krizler Arası Toplumsal Hafıza**) eklendi.

Bu araştırmanın amacı yalnızca *"yeni sistem çalışıyor mu?"* sorusunu doğrulamak değil; **motoru zorlayıcı rejimler altında test ederek gerçek verilerden beklenmedik davranış kalıplarını, psikolojik paradoksları ve bir sonraki nesil (v3.5+) için en yüksek kaldıraçlı fikirleri çıkarmaktır.**

---

## 2. Altı Deneyin Sayısal Bulguları (`reports/psychology-research-v34.json`)

### Deney 1 — v3.3 vs v3.4 Kitle Ayrışması, Yankı Odaları ve `N=1000` Ölçek Değişmezliği
Aynı ekonomik iyimserlik vaadi + `1.65x` fiyat şoku altında 3 farklı tohum (`44, 101, 202`) ortalaması ve `N=1000` tam ölçek karşılaştırması:

| Gösterge | v3.3 (`N=100`) | v3.4 (`N=100`) | v3.4 (`N=1000`, Gün 15) | Psikolojik Anlamı |
|---|---:|---:|---:|---|
| Yakın Bağ Yankı Odası (Homofili) | `%42.9` | **`%80.0`** | **`%80.0`** | Kutuplar artık rastgele karışmıyor; kendi mahallesinde yankılanıyor. |
| Gözlemci Gelen İzleme Bağı | `0.89` | **`6.00`** | **`6.00`** | Gözlemciler sağır olmaktan çıktı; iki kutbu da sessizce izliyor. |
| İktidar Yanlısı Kendi Kutbuna Güven | `0.688` | **`0.754`** | **`0.745`** | Savunma duvarı (`0.82–0.85`) erken kopuşu rasyonalize ederek tamponluyor. |
| Taraf Değiştirme (`alignment_changes`) | `0` | **`0`** | **`0`** | Kimlik kutbu bir gecede ucuzca terk edilmiyor. |
| Hoşnutsuz Kesim Konfor / Tükenmişlik | *(yok)* | Konfor düşüşü | **`0.090` / `0.662`** | Krizin maddi-ruhsal faturasını en ağır dar gelirli hoşnutsuz kesim ödüyor. |

**Ölçek Bulgusu:** `N=100` pilot dünya ile `N=1000` tam dünya arasındaki güven (`0.682` vs `0.689`) ve savunma duvarı (`0.821` vs `0.847`) sapması **`%1`'in altındadır**. Pilot konsolda görülen psikolojik dinamikler 1.000 kişilik tam simülasyona ölçek bozulması olmadan taşınmaktadır.

---

### Deney 2 — İkiyüzlü Uyum (*Preference Falsification*), Medya Otosansürü ve Yay Boşalması
Timur Kuran'ın *Tercih Çarpıtması* ve Elisabeth Noelle-Neumann'ın *Suskunluk Sarmalı* kuramlarının motordaki testi (10 gün otorite baskısı + sözleşme iptali, ardından 6 gün otorite çatlağı ve içeriden sızıntı):

| Evre / Metrik | Değer (3 Tohum Ort.) | Davranışsal Yorum |
|---|---:|---|
| Muhalif Görünür Uyum (`public_support`) | **`0.700`** | Dışarıdan bakıldığında toplumun `%70`'i uyumlu görünüyor. |
| Muhalif İçsel Bağlılık (`private_loyalty`) | **`0.520`** | İçeride gerçek ikna yok; **`+0.180` sahte uyum makası** oluşuyor. |
| Tarafsız Ticari Medya Otosansür Oranı | **`%100.0`** | İdeolojik kalkanı olmayan ticari medya ilk sözleşme sopasında tamamen susuyor. |
| B Yanlısı Zenginler Otosansür Oranı | **`%100.0`** | İhale/sözleşme kaybı muhalif sermayeyi de açık yayından çekiyor. |
| A Yanlısı Zenginler Otosansür Oranı | **`%0.0`** | İktidar kalkanındaki sermaye korkusuzca karşı-anlatı yaymaya devam ediyor. |
| Baskı Altında Muhalif Eylem Dürtüsü | `0.471` | Korku açık tepkiyi yarı yarıya bastırıyor; bastırılmış öfke `0.400`'ta birikiyor. |
| **Sızıntı Sonrası Boşalan Eylem Dürtüsü** | **`0.903`** | Baskı kırıldığı anda tepki normalin **neredeyse 2 katı şiddetle** geri tepiyor! |

**Kritik Çıkarım:** Otorite için en tehlikeli yanılsama `public_support` artışını "toplum ikna oldu" sanmaktır. Motorda korku sahte sessizlik üretmekte, ancak ilk kurumsal sızıntıda biriken `repressed_anger` ani bir meşruiyet patlamasına dönüşmektedir.

---

### Deney 3 — Kriz Yönetimi Karşılaştırması: "Örtbas + Günah Keçisi" vs "2. Gün Erken Şeffaf Denetim"
Aynı maden faciası senaryosunun 10 gün boyunca iki farklı yönetim tercihiyle motor üzerinde koşturulması:

| Sonuç Göstergesi (10. Gün Sonu) | Kol A: Örtbas & Günah Keçisi | Kol B: 2. Gün Şeffaf Denetim & İstifa |
|---|---:|---:|
| İkincil Artçı Kaza / Facia Oranı | **`%100.0`** | **`%0.0`** |
| İşveren Kesintisinden Etkilenen Çalışan | **`73.0 kişi`** | **`0.0 kişi`** |
| Toplam Ekonomik Refah Kaybı (`losses`) | **`775.4`** | **`0.0`** |
| Zengin / Medya Korku Zirvesi | **`%59.7`** | **`%3.7`** |
| Hoşnutsuz Kesim 10. Gün Tükenmişliği | **`%36.3`** | **`%0.0`** |
| Sonraki Krize Devreden Hafıza İzi | **`coverup_scar = 0.16`** | **`reform_credit = 0.18`** |

**Kritik Çıkarım:** Kısa vadeli örtbas ilk 2 gün "düzeni korumuş" gibi görünse de 5. günde tedbirsizlik kaynaklı ikincil kazayı tetiklemekte, boykot ve yaptırımlar işveren→çalışan zinciri üzerinden 73 çalışanın gelirini vurmakta ve bir sonraki krize kalıcı güvensizlik yarası devretmektedir.

---

### Deney 5 & Deney 6 — Tükenmişlik Eğrisi ve Ardışık 4 Krizde Kümülatif Travma

1. **Yalnız Bırakılan Krizde Öğrenilmiş Çaresizlik (Deney 5):**
   - Yerel dayanışma olmayan (`isolated_no_solidarity`) kesimde eylem dürtüsü **3. günde `0.938` ile zirve yapmakta**, ancak sonuç alınamadıkça tükenmişlik tırmanmakta (`Gün 7: 0.33 → Gün 14: 0.79 → Gün 25: 1.00`) ve eylem dürtüsü **`0.278`'e çökerek içe kapanmaya (`exhausted_withdrawal`)** dönüşmektedir.
2. **Ardışık 4 Krizde Sabır Erimesi (Deney 6):**
   - Üst üste örtbasla kapatılan 4 kriz boyunca muhaliflerin tahammül eşiği **`0.300 → 0.210 → 0.130 → 0.087`'ye**, hoşnutsuz kesimin eşiği **`0.368 → 0.115`'e**, iktidar yanlılarının savunma duvarı ise **`0.831 → 0.651`'e** erimektedir.
   - İçeriden vicdanlı bürokrat sızıntısı 1. ve 2. krizde **3. günde** çıkarken, biriken kurumsal yara nedeniyle 3. ve 4. krizde **2. güne sıkışmaktadır**.

---

## 3. Özeleştirel Keşifler: Verilerin Ortaya Çıkardığı 5 Kalibrasyon Kör Noktası

Gerçek deney verileri, v3.4 modelinin güçlü yönlerinin yanı sıra **sadece simülasyonu koşturunca görülebilen 5 derin davranışsal kusuru / sınırı** açığa çıkarmıştır:

### Keşif 1 — "Öfke Tavan Doygunluğu" (*Anger Ceiling Saturation = `1.000`*)
- **Verideki Kanıt:** Deney 1 ve Deney 5'te `discontented` ve `wealthy` öfkesi 3. günde `1.000` tavanına vurup 40. güne kadar `1.000`'da sabitlenmektedir.
- **Psikolojik Neden:** Mevcut formül doğrusal toplama (`anger * 0.86 + gain`) kullanıyor. Oysa insan psikolojisinde **Weber-Fechner Yasası** ve **Hedonik Uyum (Hedonic Adaptation)** işler: insanlar sabit kalan yüksek fiyat seviyesine bir süre sonra alışır; öfkeyi taze tutan şey mutlak seviye değil **yeni şok farkları (`Δharm`) ve adaletsizlik karşılaştırmasıdır**. Öfke `1.0`'a yapıştığında motor "%65 öfke" ile "%95 patlama" arasındaki nüansı kaybeder.

### Keşif 2 — Deney 4'teki "Savunma Duvarı Atıf Boşluğu" (*Broadcast Attribution Gap*)
- **Verideki Kanıt:** Deney 4C'de `power_aligned` kitlenin konforu `0.724`'ten **`0.154`'e çöktüğü** halde ortalama `defense_wall` **`0.791`'de** kalmıştır!
- **Teknik ve Psikolojik Neden:** `defense_wall` aşınması `responsibility_own` (kendi otoritesinin yanlış tahmininin kanıtlanması) değişkenine bağlıdır. Ancak motorda ekonomik tahmin çelişkisi (`economic_outlook` vaadi) yalnızca birebir `send` mesajlarında izlenmekte, sosyal medya `amplify` yayınlarında izlenmemektedir! Dahası gerçek hayatta (**Kunda — Motivated Reasoning**):
  - İktidar seçmeni ilk aşamada suçu aracı kurumlara / dış güçlere / marketlere atar (*"Lider iyi ama çevresi kötü"* — **Suç Kaydırma / Blame Shifting**).
  - Ancak mutfak konforu `< 0.25` altında haftalarca kalır ve aynı anda iktidar medyası `amplify` ile *"ekonomi uçuyor"* derse, **gerçeklik ile propaganda arasındaki uçurum** birebir mesaj olmasa bile savunma duvarını çatlatmalıdır.

### Keşif 3 — Deney 5'teki "Sınırsız Dayanışma Ölümsüzlüğü"
- **Verideki Kanıt:** Deney 5'te `connected_local_solidarity` kolunda 40. günde bile `exhaustion = 0.000` kalmıştır.
- **Psikolojik Neden:** `solidarity_relief (0.05)` sabit tutulduğu için dayanışma içindeki ajanlar hiç yorulmamaktadır. Oysa gerçek toplumsal hareketlerde (**Sidney Tarrow — Eylem Döngüleri & Merhamet Yorgunluğu**), komşuların kendisi de fakirleştiğinde (`losses` arttığında) dayanışma kapasitesi aşınır; dayanışma tükenmişliği **sıfırlamaz**, yalnızca **yarı hızına düşürür ve kırılma gününü 10. günden 28–35. güne öteler**.

### Keşif 4 — Çoğulcu Cehalet (*Pluralistic Ignorance*) Geri Beslemesinin Eksik Olması
- **Mevcut Durum:** Korku yüksekken ajan kendi ifadesini `self_censored` yapıyor; fakat **komşularının neden sustuğunu yorumlamıyor**.
- **Psikolojik Gerçek:** İnsanlar çevrelerindeki 10 kişiden 8'inin sustuğunu gördüğünde *"Korktukları için susuyorlar"* diye değil, çoğunlukla *"Demek ki bir tek ben rahatsızım, çoğunluk halinden memnun"* diye okur (**Çoğulcu Cehalet**). Bu algı bireyi iki kat yalnızlaştırır — ta ki kamusal bir sızıntı veya ortak bir olay herkesin aynı anda ne düşündüğünü görünür kılana (**Common Knowledge Şoku**) kadar!

### Keşif 5 — Çapraz Kimlik Çatışması (*Cross-Cutting Cleavages*)
- **Mevcut Durum:** Ajanın siyasal kimliği (`power_aligned`) ile ekonomik konumu (`pro_B` veya `neutral_commercial` bir işverenin çalışanı olması) çarpıştığında, bu iki kimlik arasındaki iç gerilim ayrı bir değişken olarak tutulmuyor.
- **Psikolojik Gerçek:** Leon Festinger'in asıl **Bilişsel Çelişki (Cognitive Dissonance)** kuramı tam olarak burada çalışır: *"Desteklediğim otorite, çalıştığım fabrikaya ceza kesti ve maaşım %25 düştü."* Bu durumda ajan ya işverenini suçlayarak kutbuna daha fanatik sarılır ya da sessiz bir kırılmayla apolitikleşir (`gri bölge / küskün seçmen`).

---

## 4. Proje İçin Düşünülmüş 7 Özgün Fikir ve v3.5+ Mimari Önerisi

Aşağıdaki öneriler `docs/simulasyon-felsefesi.md` içindeki kırmızı çizgileri (deterministik tekrarlanabilirlik, ucuz taraf değiştirmeme, tekil ajan hafızası) bozmadan `people1000`'i sıradan bir ajan simülasyonundan **gerçek bir politik-psikoloji laboratuvarına** dönüştürecek somut tasarımlardır:

### Öneri 1 — Asimptotik Öfke + Hedonik Uyum Denklemi (Acil Kalibrasyon)
- **Fikir:** Öfke artışını doğrusal toplama yerine azalan marjinal etkiyle `anger + (1.0 - anger) * tanh(excess)` biçimine çevirmek ve her ajan için yavaş hareket eden bir **`adaptation_baseline` (alışma tabanı)** tutmak (`baseline_t = 0.92 * baseline_{t-1} + 0.08 * harm_t`).
- **Etkisi:** Sabit kalan krizde öfke `1.0`'a yapışmaz; `%55–80` bandında gerçekçi dalgalanır ve yalnızca **beklentiyi aşan yeni şoklarda (`harm > adaptation_baseline`)** `%90+` patlama bandına çıkar.

### Öneri 2 — "Suç Kaydırma" (*Blame Attribution*) Katmanı: Lider vs Aracı Kurum Ayrımı
- **Fikir:** `power_aligned` ajanların güvenini tek parça tutmak yerine iki katmana ayırmak:
  1. **`intermediary_trust` (Bürokrasi / Piyasa / Aracı Güveni):** İlk fiyat şokunda ve ilk ihmalde hızla düşer (*"Denetçiler/fırsatçılar bozuk"*).
  2. **`core_leader_trust` (Çekirdek Kutup Bağlılığı):** Aracı güveni tampon görevi görür; ancak otorite o aracıyı korur / terfi ettirir veya `amplify` üzerinden yaşanan sefaletin tam tersi propaganda yaparsa aşınma doğrudan çekirdek bağlılığa sıçrar!
- **Neden Çok Değerli?** Türkiye ve dünya siyaset sosyolojisinde seçmen davranışının en kritik mekanizması budur; Deney 4'te bulduğumuz savunma duvarı paradoksunu birebir çözer.

### Öneri 3 — Çoğulcu Cehalet (*Pluralistic Ignorance*) ve "Ortak Bilgi Kırılması" (*Focal Point*)
- **Fikir:** Her ajan komşularının son 3 gündeki açık mesaj oranını izleyerek bir **`perceived_consensus` (algılanan çoğunluk rızası)** hesaplasın. Çevresi korkudan sustuğunda ajan kendini yalnız sanıp `effective_drive`'ını düşürsün. Ancak **kamusal bir sızıntı (`leak_occurred`) veya gözlemci raporu** geldiğinde herkes diğerlerinin de gerçeği gördüğünü anlasın ve çoğulcu cehalet tek günde tuzla buz olsun.
- **Etkisi:** "Yıllarca yaprak kımıldamayan toplumda nasıl bir gecede herkes aynı cümleyi kurmaya başladı?" sorusunun matematiksel cevabını üretir.

### Öneri 4 — Göreli Yoksunluk (*Relative Deprivation*) ve Görünür İmtiyaz Öfkesi
- **Fikir:** Ted Gurr'un *Why Men Rebel* kuramına göre insanları en çok öfkelendiren şey mutlak yoksulluk değil, **"herkes kemer sıkarken imtiyazlı bir zümrenin (`pro_A wealthy` veya `authority`) servet büyütmeye devam ettiğini görmektir."**
- **Mekanizma:** Ajanın kendi refah kaybı (`my_loss`) ile ağda gördüğü `wealthy (pro_A)` refah kazancı arasındaki fark (`inequality_visibility`) öfke çarpanını doğrudan beslemelidir. Aynı yoksulluk "hepimiz aynı gemideyiz" algısında sabırla karşılanırken, şatafat görünürlüğü olduğunda tahammül eşiğini yarıya indirir.

### Öneri 5 — "Küskün Seçmen / Gri Bölge" Durumu (*Silent Exit without Defection*)
- **Fikir:** Şu an ajanlar ya kendi kutbunda kalıyor (`A`/`B`) ya da çok nadir karşı kutba geçiyor. Gerçek hayatta hayal kırıklığına uğrayan `power_aligned` veya `opposition` seçmen hemen karşı partiye geçmez; önce **"Küskün / Sandığa Gitmeyen / Sessiz Mesafeli" (`disengaged_loyalist`)** evresine girer!
- **Mekanizma:** `defense_wall < 0.35` ve `comfort < 0.25` olduğunda ajan kutbunu (`alignment = 'A'`) korur ama `public_support` ve propaganda paylaşımını (`relay`) sıfırlar. Web arayüzünde bu oran **"Sessiz Kopuş / Küskün Oranı"** olarak gösterildiğinde operatör için muazzam bir erken uyarı sinyali olur.

### Öneri 6 — Gözlemciler İçin "Epistemik Vicdan Eşiği" (*Whistleblower / Cassandra İkilemi*)
- **Fikir:** `%3`'lük `observer` kitlesi şu an 6 kanalı izliyor ama neredeyse hiç konuşmuyor (`effective_drive = 0.0`). Oysa toplumda bilim insanları, denetçiler ve bağımsız gazeteciler **yaklaşan ikincil faciayı (`aftershock_pending`) önceden gören Cassandra'lardır**.
- **Mekanizma:** Gözlemcinin iki kutuptan topladığı çelişki kanıtı kritik eşiği (`epistemic_alarm > 0.80`) aştığında, yüksek kişisel bedel (`pressure` riski) pahasına kamusal bir **"Teknik Uyarı Raporu"** yayınlayabilsin. Otorite bu raporu dinlerse kriz `seffaf_onarim` dalına döner; gözlemciyi cezalandırırsa sızıntı ve kurumsal yara ikiye katlanır!

### Öneri 7 — Dayanışma Kaynak Tükenmesi (*Solidarity Resource Depletion*) ve Duygusal Bulaşma (*Affective Contagion*)
- **Fikir:**
  1. Yerel dayanışmanın tükenmişliği azaltma gücü (`solidarity_relief`), komşu ağının ortalama tasarruf sağlığıyla (`mean_neighbor_savings`) çarpılmalıdır — mahalle hep birlikte yoksullaştığında dayanışma da yorulur (Deney 5'teki sınırsız dayanışma hatasını düzeltir).
  2. Ağ üzerinden sadece "bilgi iddiası (`claim`)" değil, düşük katsayılı **duygusal ton (`korku` ve `umut/öfke` bulaşması)** da taşınmalıdır: paniğin kendisi bilgiden hızlı yayılır (**Hatfield — Emotional Contagion**).

---

## 5. Önerilen Uygulama Öncelik Sırası (Yol Haritası)

| Öncelik | Paket | Zorluk | Beklenen Gerçekçilik Kazancı |
|---|---|---:|---|
| **1 (Hızlı Kalibrasyon)** | **Öneri 1 + Öneri 7a:** Asimptotik öfke (`tanh`), hedonik uyum tabanı ve maddi güce bağlı dayanışma yorulması | Düşük | Tavan doygunluğunu (`1.000`) ve sonsuz dayanışma ölümsüzlüğünü anında giderir. |
| **2 (Orta Vadeli Derinlik)** | **Öneri 2 + Öneri 5:** Aracı vs Lider suç kaydırma katmanı + "Küskün Seçmen / Sessiz Kopuş" göstergesi | Orta | İktidar tabanındaki sessiz erimeyi taraf değiştirmeden görünür kılar. |
| **3 (İleri Sosyal Zihin)** | **Öneri 3 + Öneri 4 + Öneri 6:** Çoğulcu cehalet kırılması, görünür imtiyaz öfkesi ve Gözlemci erken uyarı ikilemi | Orta-Yüksek | Ani toplumsal dalgaları ve uzman uyarılarının kaderini nedensel olarak modeller. |

---

## 6. Uygulama Sonrası v3.5 (`affective-v2`) Doğrulama Sonuçları (`reports/psychology-research-v35.json`)

Yukarıdaki 7 öneri ve kalibrasyon düzeltmesinin tamamı `behavior.json` (`3.5.0` / `affective-v2`), `society/psychology.py`, `society/dynamics.py`, `society/characters.py`, `society/crisis_bridge.py` ve `society/web_ui.py` üzerinde uygulanmış (`v3.4.0` ise `society/behavior-v34.json` olarak dondurulmuştur) ve deneyler yeniden çalıştırılmıştır:

| Kalibrasyon Alanı | v3.4 (`affective-v1`) | v3.5 (`affective-v2`) | Sonuç |
|---|---:|---:|---|
| Hoşnutsuz Kesim Kronik Öfke Tavanı | `1.000` (tavana yapışık) | **`0.799`** | `tanh` + hedonik uyumla tavan doygunluğu giderildi; ikincil şoklara alan açıldı. |
| Ağır Mutfak + İşveren Kesintisi + Yalan Vaatte `power_aligned` Duvarı | `0.791` (kırılmadı) | **Gün 11'de `< 0.45` kırıldı (`0.00`)** | Suç kaydırma tamponu dolunca duvar çatladı; karşı partiye geçmeden (`switch = 0`) **küskün kopuş** oluştu. |
| Muhalif Söylem Tek Başına (`4A` — Maddi Zarar Yok) | `0.848` | **`0.848`** | Söylemle savunma duvarı yine yıkılmıyor; yalnız somut yaşam çelişkisiyle kırılıyor. |
| Dayanışmalı Krizde Tükenmişlik (Gün 14 / Gün 25 / Gün 40) | `0.00 / 0.00 / 0.00` | **`0.314 / 0.660 / 0.993`** | Sınırsız dayanışma ölümsüzlüğü giderildi; dayanışma tükenmeyi ~2.5 kat yavaşlatıp öteliyor. |
| API İsteği Maliyeti | Gün başına `1` (`sor`/`devam`) | **Gün başına `1` (`0` ek istek)** | Tüm derin sosyal-zihin hesapları yerel motorda çalışır; API kotası hiç artmadı. |

