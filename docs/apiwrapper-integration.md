# ApiWrapper entegrasyonu (OpenAI uyumlu, durumsuz)

31 Ekim 2026. Bu belge projenin kullanıcının kendi OpenAI uyumlu **ApiWrapper**
servisine nasıl bağlandığını, istek/yanıt sözleşmesini, hata biçimini ve
sırların nerede tutulmadığını açıklar. Ölçülen toplum davranışı iddiası değildir.

## Yapılandırma

Adres ve anahtar kodda **sabitlenmez**; yalnızca iki ortam değişkeninden okunur:

| Değişken | Anlamı |
|---|---|
| `WRAPPER_URL` | OpenAI uyumlu servisin taban adresi |
| `WRAPPER_API_KEY` | `Authorization: Bearer …` anahtarı |

`base_url`, `WRAPPER_URL` sonundaki `/` işareti kaldırılıp `/v1` eklenerek
kurulur:

```
WRAPPER_URL=https://api-wrapper.example.com/   ->  https://api-wrapper.example.com/v1
```

Kurallar:

* Adres `https` olmalıdır. Düz `http` yalnızca `localhost`, `127.0.0.1` ve `::1`
  için kabul edilir; canlı servise anahtar şifresiz gönderilmez.
* Adreste kullanıcı/parola, sorgu (`?…`) veya parça (`#…`) olamaz.
* Adres zaten `/v1` ile bitiyorsa ikinci kez eklenmez.
* Tam uç nokta yapıştırılırsa (`…/v1/chat/completions`) taban adrese indirgenir.
* `model` sabittir: **max**. `stream` **false**. Zaman aşımı **180 saniye**.
* Anahtar değeri hiçbir zaman yanıt gövdesine, tarayıcı koduna, durum dosyasına
  veya erişim günlüğüne yazılmaz.

Şablon: [.env.example](../.env.example). Gerçek değerleri repoya koymayın;
`.env` ve `.env.*` zaten Git dışındadır.

```bash
mkdir -p "$HOME/.config/people1000"
cp .env.example "$HOME/.config/people1000/api.env"
chmod 600 "$HOME/.config/people1000/api.env"
# api.env içinde yalnızca iki satırın yorum işaretini kaldırıp doldurun:
#   export WRAPPER_URL='https://...'
#   export WRAPPER_API_KEY='...'
set -a; . "$HOME/.config/people1000/api.env"; set +a
```

## İstek sözleşmesi

Her çağrı **bağımsızdır**. Gövde her istekte sıfırdan kurulur:

```http
POST <WRAPPER_URL>/v1/chat/completions
Content-Type: application/json
Accept: application/json
Authorization: Bearer <WRAPPER_API_KEY>
```

```json
{
  "model": "max",
  "messages": [{"role": "user", "content": "<kullanıcının verdiği metin>"}],
  "stream": false
}
```

* Sohbet geçmişi, veritabanı, oturum (session) yeniden kullanımı **yoktur**.
  Önceki çağrıların mesajları sonraki isteğe eklenmez.
* `developer` rolü veya developer mode eklenmez; metin tek `user` mesajıdır.
* Yanıt yalnızca `choices[0].message.content` alanından okunur.
* `finish_reason == "length"` ise yanıt tamamlanmış sayılmaz ve hata döner.
* Yanıt gövdesi 2 MB ile sınırlıdır; aşan yanıt reddedilir.

Simülasyon katmanı (senaryo/gündem) aynı servisi `WrapperAdvisor` üzerinden
kullanır: uç nokta yine `<WRAPPER_URL>/v1/chat/completions`, model `max`, akış
kapalı, zaman aşımı 180 sn. Gündem değerlendirmesi kendi JSON sözleşmesini
kullanır; yine tek istek/tek yanıttır ve geçmiş biriktirilmez.

## Hata biçimi

Anahtar ve sağlayıcı gövdesi asla geri yansıtılmaz. Görünen bilgi:

* `HTTP <status>` — ApiWrapper'ın döndürdüğü durum kodu
* `ApiWrapper kod: <code>` — yanıt gövdesindeki `error.code` veya `error.type`
  (yalnız `[A-Za-z0-9_.:/-]`, en fazla 64 karakter; güvenli değilse gösterilmez)
* sabit Türkçe açıklama (`401` kimlik doğrulama, `429` kota, `5xx` sunucu vb.)

HTTP 200 ile birlikte `error` gövdesi dönen geçit yanıtları da hata sayılır;
`error.code` yine gösterilir, yarım yanıt başarı kabul edilmez.

Yerel web arayüzü bunu JSON olarak döndürür:

```json
{"ok": false, "error": "ApiWrapper HTTP 429 · kod: rate_limit_exceeded: …",
 "error_kind": "http_error", "http_status": 429,
 "error_code": "rate_limit_exceeded"}
```

Eşleme: kimlik/ayar hatası `500`, `WRAPPER_URL` yok/geçersiz `503`, zaman aşımı
`504`, ağ/TLS/biçim hatası `502`, metin doğrulaması `400`. ApiWrapper bir HTTP
hatası döndürdüyse aynı durum kodu korunur (`401`, `403`, `429`, `5xx` …).

Otomatik tekrar (retry) yoktur; her çağrı tek istektir.

## Nerede çalışır

* Çağrı **sunucu tarafında** yapılır: `society/wrapper_api.py` ve yerel web
  sunucusunun `/api/wrapper` yolu (`society/web_ui.py`). Tarayıcı yalnızca yerel
  sunucuya konuşur; anahtarı hiç görmez.
* Next.js kullanılmıyor; proje sıfır bağımlılıklı Python standard kütüphanesiyle
  çalışır. Route handler'ın karşılığı `POST /api/wrapper`'dır. OpenAI SDK yerine
  aynı HTTP sözleşmesi (`/v1/chat/completions`) doğrudan uygulanır; `base_url`,
  `api_key`, `model`, `stream`, `timeout` değerleri yukarıdaki gibidir.
* Erişim günlükleri kapatılmıştır; istek gövdesi ve anahtar loglanmaz.

## Deneme

```bash
python -m society.wrapper_api --check      # ağ isteği yok, anahtar gösterilmez
python -m society.wrapper_api "Merhaba"    # tek gerçek istek
python -m society.web_ui --state runs/wrapper-pilot.json
# arayüzde: "ApiWrapper Bağlantısı" paneli -> metin -> Gönder
```

Arayüz paneli her gönderimde **yeni** bir istemci kurar; önceki metinler
gönderilmez. Yanıtla birlikte model, akış durumu ve varsa token sayısı gösterilir.

## Testler

`tests/test_wrapper_api.py` ağa çıkmadan şunları doğrular: adres normalizasyonu,
tek `user` mesajı, `model=max`, `stream=false`, 180 sn zaman aşımı, bağımsız
istekler, `choices[0].message.content` ayrıştırması, HTTP durumu + ApiWrapper
hata kodu, anahtar sızdırmama, `.env.example` placeholder kuralı ve
`/api/wrapper` uç noktası.

```bash
python -m unittest tests.test_wrapper_api -v
python -m unittest discover -s tests -v
```

## Sınırlar

* Gerçek ApiWrapper servisine karşı ücretli/ canlı istek bu depodaki testlerde
  çalıştırılmaz; taşıma katmanı sahte yanıtlarla doğrulanır.
* Modelin içerik kalitesi, gecikmesi ve kotası ApiWrapper servisinize bağlıdır;
  bu depo garanti vermez.
* Gündem katmanı JSON bekler; servis JSON döndürmezse istek geçersiz sayılır ve
  simülasyona yarım karar uygulanmaz.
