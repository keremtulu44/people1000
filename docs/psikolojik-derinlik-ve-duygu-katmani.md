# People1000 — Psikolojik Derinlik, Tahammül ve Duygu Katmanı (`v3.4 / affective-v1`)

Kayıt tarihi: 27 Ekim 2026. Bu belge, simülasyondaki 6 kitlenin kopya mizaç
aralıklarından çıkarılıp **gerçek psikolojik karşılığı olan mizaç, tahammül ve
duygu mekanizmalarıyla** çalışmasını sağlayan tasarım sözleşmesidir.

[Yaşayan toplum felsefesi](simulasyon-felsefesi.md), [altı karakter sözleşmesi](six-character-contract.md)
ve [normal gündem sınırı](api-and-agenda-contract.md) bu katmanda korunur;
hiçbir kitle kimliği silinmez veya karikatürize edilmez.

---

## 1. Temel İlke: "Süs Puanı" Değil, Karar Üreten Psikoloji

Bu katmandaki hiçbir duygu (tahammül, korku, öfke, konfor, savunma, tükenmişlik)
yalnızca ekranda görünen kozmetik bir yüzde değildir. Her psikolojik değişken
ajanın **ifade biçimini, eyleme geçme eşiğini, otosansürünü, rasyonalizasyonunu
veya içe kapanmasını** doğrudan etkiler.

---

## 2. Beş Psikolojik Durum ve Doğrudan Davranış Karşılığı

### 2.1. Tahammül Eşiği ve Tükenmişlik (`tolerance_threshold` & `exhaustion`)
* **Mekanizma:** Sorun veya maddi/kurumsal darbe başladığında kişi kendi
  `tolerance_threshold` (sabır eşiği) değerine kadar dişini sıkar. Eşik
  aşıldığında sabır kırılır ve aktif tepki (`anger`) hızla yükselir. Ancak sorun
  uzun süre çözülmez, çevreden karşılık bulunamaz veya baskı sürerse aktif öfke
  zamanla **tükenmişliğe (`exhaustion` — öğrenilmiş çaresizlik)** dönüşür.
* **Davranış karşılığı:**
  * *Eşik altı:* Sabretme / bekleme (`wait`).
  * *Eşik kırılması:* Sorgulama, destek çekme, şikâyet iletme ve buluşma/boykot arayışı.
  * *Yüksek tükenmişlik:* Kronik yıpranma eylem enerjisini artırmaz, aksine
    sönümler; kişi kabullenip içe çekilir (`exhausted_withdrawal`).

### 2.2. Korku ve Otosansür (`fear` & `expression_mode`)
* **Mekanizma:** Doğrudan yönetici baskısı (`pressure`), sözleşme/gelir iptali
  (`revoke_contract`) veya soruşturma/gözaltı atmosferiyle kişinin
  `fear_sensitivity` katsayısına bağlı olarak yükselir; tehdit azaldıkça gün gün
  yavaşça düşer.
* **Davranış karşılığı:** Korku kişinin **içsel kanaatini veya özel sadakatini
  değiştirmez**, dışarıya verdiği ifadeyi değiştirir:
  * *Düşük korku:* Açık ifade (`open` — açık eleştiri, açık katılım).
  * *Orta korku:* İmalı ve ihtiyatlı dil (`guarded`).
  * *Yüksek korku:* Tam otosansür veya zahiri uyum (`self_censored` — açık
    protestodan çekilme, sessizlik).

### 2.3. Öfke ve Bastırılmış Tepki (`anger` & `repressed_anger`)
* **Mekanizma:** Geçim darbesi, güvenlik açığı, kayırmacılık ve örtbasla `anger`
  yükselir. Kişi öfkeliyken **korku veya zoraki baskı yüzünden susmak zorunda
  kalırsa** öfkesi silinmez; `repressed_anger` (bastırılmış tepki/kin) havuzunda
  uzun süreli olarak birikir.
* **Davranış karşılığı:** Normal öfke sorgulama ve yerel dayanışma üretir.
  İçeride biriken `repressed_anger` ise otorite zayıfladığında, korku düştüğünde
  veya inkar edilemez bir sızıntı/başarısızlık kanıtlandığında normalden çok daha
  hızlı **destek çekme ve toplu itiraz boşalması** yaratır.

### 2.4. Konfor / Düzen Memnuniyeti (`comfort`)
* **Mekanizma:** Gelir gideri karşılıyorsa, birikim ve statü güvendeyse yüksek
  kalır; maddi kayıp, sözleşme iptali ve yerel sarsıntılarla düşer.
* **Davranış karşılığı:** *"Ağzımızın tadı / düzenimiz bozulmasın"* etkisi üretir.
  Yüksek konfor, mevcut kutuptan çıkış maliyetini (`exit_cost`) artırır ve riskli
  eylemlere girme isteğini düşürür.

### 2.5. Psikolojik Savunma Duvarı (`defense_wall` — Rasyonalizasyon)
* **Mekanizma:** Kişi kendi tuttuğu tarafın hatası veya sorumluluk iddiasıyla
  karşılaştığında devreye giren bilişsel kalkan (`defense_strength`).
* **Davranış karşılığı:** Duvar sağlamken kişi suçu *dış etkenlere, alt kademedeki
  münferit hataya veya karşı tarafın abartısına* bağlar; güven erimesi tamponlanır.
  Ancak **sürekli kişisel zarar + kendi otoritesinin çelişen vaatleri/belgeleri**
  üst üste bindiğinde savunma duvarı aşınır ve gerçek hayal kırıklığı kırılması başlar.

---

## 3. Altı Kitlenin Ayrıştırılmış Psikolojik Profili

Aralıklar `[0.0, 1.0]` kapalı ölçeğindedir ve her kitlenin toplumsal doğasına özgüdür:

| Kitle | Tahammül Eşiği | Korku Duyarlılığı | Başlangıç Konforu | Savunma Duvarı | Tükenmişlik Eğilimi | Temel Psikolojik Karşılık |
|---|---|---|---|---|---|---|
| **1. İktidar Yanlıları (`power_aligned` — %30)** | `0.65 – 0.85` | `0.25 – 0.50` | `0.65 – 0.85` | `0.75 – 0.95` | `0.25 – 0.45` | Kendi kutbunun hatalarını uzun süre rasyonalize eder; düzen konforunu korur. Yalnız ağır ve sürekli kişisel zarar savunma duvarını aşarsa sessizliğe/destek çekmeye yönelir. |
| **2. Muhalifler (`opposition` — %30)** | `0.20 – 0.40` | `0.35 – 0.65` | `0.30 – 0.50` | `0.60 – 0.80` | `0.35 – 0.55` | Usulsüzlük ve örtbasta öfkesi hızlı yükselir. Baskı sertleşince iç fikri değişmez; açık eleştiriden imalı dile çekilir ve bastırılmış öfke biriktirir. |
| **3. Yöneticiler / Otorite (`authority` — %15)** | `0.55 – 0.80` | `0.50 – 0.80` *(koltuk kaybı)* | `0.80 – 0.98` | `0.70 – 0.90` | `0.10 – 0.25` | Söylemle savrulmaz; koltuk ve kurumsal güç konforunu korur. Sıkıştığında baskı veya günah keçisi refleksi verir; küçük vicdani/dışlanmış azınlıkta aşırı örtbas sızıntı dürtüsü üretir. |
| **4. Zenginler ve Sosyal Medya (`wealthy` — %12)** | `0.20 – 0.40` *(maddi zarar)* | `0.65 – 0.95` *(yargılanma)* | `0.75 – 0.95` | Taraflı: `0.45 – 0.70`<br>Tarafsız: `0.05 – 0.20` | `0.30 – 0.50` | Motor içinde 3 gerçek alt kanada ayrılır: **A Yanlısı** algıyı yumuşatır, **B Yanlısı** ihmali büyütüp risk sınırı kollar, **Tarafsız/Ticari (`none`)** korku yükselince en hızlı otosansüre gömülür. |
| **5. Hoşnutsuz Kesim (`discontented` — %10)** | `0.25 – 0.45` | `0.30 – 0.55` | `0.05 – 0.25` | `0.05 – 0.20` | `0.60 – 0.85` | Konforu en düşük, öfkesi en hızlı biriken kesimdir. Yerel destek bulursa buluşma/boykot başlatır; yalnız kalır ve kriz uzarsa hızla tükenmişliğe ve derin güvensizliğe çekilir. |
| **6. Gözlemciler (`observer` — %3)** | `0.75 – 0.95` | `0.05 – 0.20` | `0.55 – 0.75` *(içsel mesafe)* | `0.10 – 0.25` | `0.10 – 0.25` | Propaganda ve sürü psikolojisine kapalıdır. Korkuyla biat etmez, öfkeyle sokağa dökülmez; algı ve örtbas tiyatrosunu dışarıdan soğukkanlılıkla çözümler. |

---

## 4. Korunan Kırmızı Çizgiler ("Dur ve Düşün")

1. **Ölüm, Saldırı ve İntihar Puanlaması Yoktur:** Yukarıdaki 5 psikolojik değişkenin
   hiçbiri ölüm, saldırı veya intihar üretmez; kitle yüzdesiyle trajedi yazılmaz.
2. **Sıradan Gündem Sınırı Korunur:** Normal atama/açıklama/belge gündemi
   (`agenda.py`) derin taraf ve ideoloji alanlarını değiştirmez; yalnızca ifade
   tonu kişinin korku/risk durumuna göre açık veya ihtiyatlı olur.
3. **Olay Türüne Duyarlı Nedensellik (Ezbere Şablon Yasağı):** Deprem/yangın gibi
   afetler, ekonomik/yolsuzluk krizleri, silahlı güvenlik krizleri ve sıradan
   idari gündemler birbirine karıştırılmaz; her olay kendi nedensel zinciriyle
   ve kitlelerin gerçek mizaç dağılımları üzerinden değerlendirilir.
4. **Tarihsel Sürümlerin Korunması:** `v2.0`, `v3.0`, `v3.1`, `v3.2` ve `v3.3`
   profilleri kendi JSON dosyalarında dondurulmuş olarak kalır; yeni psikolojik
   katman `v3.4.0` (`psychology_model: "affective-v1"`) ile devreye girer.
