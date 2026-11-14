# Mimari — SPHEREx Gökyüzü İzleyici

> **Durum:** v0.2, **onaylandı** (2026-11-12) · Kararlar: [`DECISIONS.md`](DECISIONS.md) · Yayın: [`DEPLOY.md`](DEPLOY.md)
> Canlı doğrulama bulguları için bkz. [`DATA_SOURCES.md`](DATA_SOURCES.md). Bu belgedeki "⚠" işaretleri o belgedeki bulgulara dayanır.
> **v0.2 değişiklikleri:** dış yapay zekâ yerine kural tabanlı asistan; WebSocket; Excel dışa aktarma; EmailJS ile hesaplar; Render + Postgres; 32 saatlik takvim (§12).
> **2026-11-14:** Hubble ↔ Webb (§6.7, `/telescopes`, MAST, `astroquery.mast`) **iptal edildi (kapsam dışı)** — DECISIONS §4g. Aşağıdaki MAST/telescopes satırları yalnızca tarihçe olarak duruyor; kodu yok.

---

## 1. Amaç ve ilkeler

- **Çekirdek:** Gökyüzünün zaman içinde nasıl değiştiğini hızlı ve dürüst biçimde göstermek. Diğer her özellik bunu destekler.
- **Herkese açık:** Arama, görüntüleme ve karşılaştırma hesapsız yapılabilir. Hesap yalnızca ek özellikler içindir.
- **Uydurma veri yok:** Her sayı ve görüntü gerçek bir kaynağa dayanır. Kaynak, sürüm ve alınma zamanı yanıtla birlikte taşınır. Önbellekten gelen yanıt "önbellekten" diye işaretlenir.
- **Sürüm farkındalığı:** Her görüntü kaydı `release` (QR2/QR3/DR1…), dosya sürümü (`l2b-vNN-…`) ve boru hattı sürümünü (`VERSION`) taşır. Önbellek sürüme göre ayrılır.
- **Dürüst bilim iletişimi:** SPHEREx görüntüsü tek renkli bir fotoğraf değildir, bir LVF kesitidir. Karşılaştırmalarda Δλ, sürüm ve kalibrasyon farkları, atmosferik çizgiler ve çözünürlük açıkça gösterilir. M31 denemesinde ham farkın %20'lik sahte bir "parlama" gösterdiği görüldü (DATA_SOURCES §4.7).

## 2. Faz 0 bulgularının mimariye etkisi

| Bulgu | Mimari karar |
|---|---|
| QR3 canlı, DR1 hazırlanıyor, kalibrasyon aileleri R6 (QR2) ve R7 (QR3/DR1) | Yapılandırma dosyasıyla tanımlanan **çoklu sürüm modeli** (§5). Karşılaştırma politikası "kalibrasyon ailesi" düzeyinde. |
| QR2 içinde bile boru hattı sürümü değişiyor | `pipeline_version` her görüntüde saklanır ve karşılaştırma ekranında gösterilir. |
| Kesitler PSF/EPSF yüzünden 4–5 MB, IRSA 503 döndürebiliyor | Görüntüleyicide az sayıda kesit için **kesit servisi**. Çok sayıda pozlama gereken işler (dalga boyu indeksi, spektrum) için **HTTP Range ile kısmi okuma**. Küresel eşzamanlılık sınırı, Retry-After desteği ve devre kesici. |
| TAP M31 sorgusu 19 sn, SIA2 1,8 sn | Etkileşimli aramada önce SIA2, eksikleri TAP ile tamamla. Sonuçlar önbelleğe alınır. Toplu tarama TAP ile yapılır. |
| Bayrak başlık biçimi sürüme göre değişiyor (`MP_*` / `MSKN*`) | `FlagSchema` her dosyanın başlığından okunur. Maskeler bit numarasıyla değil, **ad listesiyle** tanımlanır. |
| astropy W-WCS'e SIP uyguluyor (λ hatası 16 nm'ye kadar) | Dalga boyu araması kendi bilinear fonksiyonumuzla ham piksel koordinatlarında yapılır. Birim testiyle doğrulanır. |
| CDS kısmi kesintide (SIMBAD 404, Sesame IDIA aynasına yönleniyor) | Uç nokta listesi yapılandırılabilir, yedekli: SIMBAD için Strasbourg → Harvard/CfA, Sesame yönlendirmesi izin listesinde. Sesame yanıtı temel bilgi için yedek kaynak. |
| "WISE 0855" Sesame'de çözülmüyor | Belirsiz girişte SIMBAD `LIKE` + Wikidata araması ile öneri listesi. |
| Güneş sistemi cisimleri Sesame'de yok, MOST SPHEREx'i destekliyor | `SolarSystemResolver` (JPL SBDB) ve hareketli cisim kareleri için MOST. |
| Windows deposu CDS sertifikasını tanımıyor | Tüm dış istekler tek bir `httpx` istemcisinden ve `certifi` ile çıkar. |

## 3. Teknoloji yığını (onay bekliyor)

**Arka uç**
- **Python 3.13** (`py -3.13 -m venv .venv`). Gerekçe: astropy 8.0.2, pyvo 1.10 ve astroquery 0.4.11 bu makinede 3.13'te doğrulandı. 3.15 için bilimsel tekerlekler doğrulanmadı.
- **FastAPI** + Uvicorn, **httpx** (async, certifi), **astropy**, **pyvo** (TAP/SIA/DataLink), **astroquery.mast**, **numpy**, **Pillow** (PNG/WebP).
- **SQLAlchemy 2 + Alembic**: yerelde SQLite (WAL), Render'da `DATABASE_URL` ile Postgres (`psycopg`). Ayarlar **pydantic-settings** (.env) ile okunur.
- **WebSocket**: FastAPI'nin yerleşik desteği (`uvicorn[standard]`). **openpyxl** ile Excel dışa aktarma. **argon2-cffi** ile kod hash'leme. Hız sınırı için basit bir token-bucket.
- **Dış yapay zekâ SDK'sı yok.** Asistan kural tabanlı, `AssistantEngine` arayüzünün arkasında duruyor.
- Yayın: tek **Dockerfile** (Node ile ön uç derlenir, Python 3.13 slim ile çalışır) + `render.yaml`.
- Kalite araçları: `ruff` (lint ve biçim), `mypy`, `pytest`.
- **Kuyruk sistemi yok** (Celery/Redis kullanılmaz). Uzun işler süreç içi iş havuzu ve DB'deki `job` tablosuyla yürür. Tek sunucu için yeterli ve maliyet doğurmaz.

**Ön uç**
- **React + Vite + TypeScript**, **Tailwind**, **Framer Motion**, **three.js** (Samanyolu).
- **react-i18next** (varsayılan `tr`, `en` iskeleti hazır), **TanStack Query** (önbellekli veri çekme).
- Spektrum grafiği: hata çubukları ve log ekseni gerekiyor. **uPlot** veya **visx** arasında Faz 2'de seçim yapılacak (Plotly'nin ağırlığından kaçınılıyor).
- Görüntüler **istemcide çizilir**: sunucu float32 diziyi ve maskeyi küçük bir ikili yanıtla gönderir. Gerdirme ve renk haritası anında değişir. PNG yalnızca küçük önizleme, paylaşım ve yapay zeka için üretilir.
- Bu bilgisayarda kurulu **UI/UX Pro Max** skill'i ve **21st.dev** bileşenleri (MCP) Faz 1'de kullanılacak.
- Kalite araçları: ESLint, Prettier, Vitest. Uçtan uca testler için Playwright (Faz 10).

## 4. Klasör yapısı (hedef)

```
spherex-izleyici/
├─ PROMPT1.md
├─ README.md                       (Faz 10)
├─ .env.example  .gitignore  .editorconfig
├─ Dockerfile  render.yaml         ← Render yayını (tek web servisi)
├─ tools/                          ← Faz 0 canlı doğrulama betikleri
├─ config/
│  ├─ releases.toml                ← veri sürümleri (QR2, QR3, DR1…) — kod değil, yapılandırma
│  ├─ upstreams.toml               ← izin verilen sunucular, aynalar, zaman aşımları, eşzamanlılık
│  ├─ demo_targets.toml            ← önceden ısıtılacak demo cisimleri
│  └─ assistant_faq.json           ← kural tabanlı asistanın soru-cevapları (kodsuz düzenlenir)
├─ backend/
│  ├─ pyproject.toml
│  ├─ alembic/  alembic.ini
│  ├─ src/skytracker/
│  │  ├─ main.py                   (FastAPI app, middleware, güvenlik başlıkları)
│  │  ├─ settings.py               (pydantic-settings)
│  │  ├─ http.py                   (tek httpx istemcisi: izin listesi, yeniden deneme, devre kesici)
│  │  ├─ db/  models.py  session.py
│  │  ├─ api/v1/                   (router'lar: resolve, sky, compare, objects, telescopes, events, feedback, admin, auth, assistant)
│  │  ├─ domain/
│  │  │  ├─ coords.py              (koordinat ayrıştırıcı — saf fonksiyonlar)
│  │  │  ├─ releases.py            (sürüm modeli ve karşılaştırma politikası)
│  │  │  ├─ flags.py               (FlagSchema: MP_* ve MSKN* çözücü; maske ön ayarları)
│  │  │  ├─ wavelength.py          (WCS-WAVE bilinear arama, SIP'siz; kanal eşleme)
│  │  │  ├─ imaging.py             (hizalama, gerdirme parametreleri, ölçek çubuğu, K/D okları)
│  │  │  ├─ photometry.py          (açıklık ve halka fotometrisi, birim dönüşümü)
│  │  │  └─ compare.py             (fark görüntüsü, normalleştirme, istatistikler, uyarılar)
│  │  ├─ providers/                (arayüz + gerçek uygulama + mock)
│  │  │  ├─ sky_data/              SkyDataProvider → spherex_irsa.py (TAP/SIA/DataLink/kesit/Range)
│  │  │  ├─ moving/                MovingObjectProvider → irsa_most.py
│  │  │  ├─ telescopes/            SpaceTelescopeProvider → mast.py
│  │  │  ├─ resolvers/             NameResolver → sesame.py, simbad.py, jpl_sbdb.py, wikidata.py
│  │  │  ├─ object_info/           ObjectInfoProvider → simbad.py, wikipedia.py
│  │  │  └─ email/                 EmailSender → emailjs.py (REST, accessToken) + console (yerel/test)
│  │  ├─ assistant/                (AssistantEngine arayüzü → RuleBasedAssistant; ileride LLM eklenebilir)
│  │  ├─ export/                   (openpyxl ile .xlsx; formül enjeksiyonu koruması)
│  │  ├─ realtime/                 (WebSocket yöneticisi: ilerleme, asistan akışı, admin akışı)
│  │  ├─ cache/                    (dosya önbelleği: sürüme göre ayrılmış; LRU boyut sınırı)
│  │  ├─ events/                   (olay günlüğü)
│  │  └─ cli.py                    (update-data, cache-prune, …)
│  └─ tests/  (unit/, fixtures/ ← gerçek yanıtlardan kaydedilmiş veriler)
├─ frontend/
│  ├─ package.json  vite.config.ts  tailwind.config.ts
│  └─ src/
│     ├─ app/  routes/  components/  features/{search,viewer,spectrum,compare,info,telescopes,assistant,feedback,admin}
│     ├─ galaxy/                   (three.js Samanyolu)
│     ├─ render/                   (renk haritaları, gerdirme, canvas çizimi)
│     ├─ i18n/{tr,en}/*.json
│     └─ lib/api.ts  events.ts
├─ data/                           (.gitignore — yalnızca yerel)
│  ├─ cache/<release>/{headers,cutouts,calib,spectra}/
│  ├─ cache/_external/{resolver,simbad,wiki,mast,most}/
│  └─ app.db
└─ docs/  DATA_SOURCES.md  ARCHITECTURE.md  DEMO.md (Faz 10)
```

## 5. Veri sürümü modeli

### 5.1 `config/releases.toml` (örnek; yeni sürüm = yeni blok, kod değişikliği yok)
```toml
[[release]]
id = "qr2"
label = "QR2"
status = "active"                  # active | staged | superseded | retired
calib_family = "R6"
tap_collections = ["spherex_qr2"]
deep_collections = ["spherex_qr2_deep"]
ibe_prefix = "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr2/"
s3_prefix  = "qr2/"
doi = "10.26131/IRSA652"
flags_header_style = "MP"          # MP | MSK (veya otomatik algıla)

[[release]]
id = "qr3"
label = "QR3"
status = "active"
calib_family = "R7"
tap_collections = ["spherex_qr3"]
deep_collections = ["spherex_qr3_deep"]
ibe_prefix = "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/"
s3_prefix  = "qr3/"
doi = "10.26131/IRSA662"
cross_family_correction = "l3_flux_corrections"   # pre-QR3 verisine çarpımsal düzeltme

[[release]]
id = "dr1"
label = "DR1"
status = "staged"                  # S3'te var, IBE ve TAP'ta yok (2026-11-12)
calib_family = "R7"
supersedes = { release = "qr2", period = ["2025-05-01", "2026-05-15"] }
s3_prefix = "dr1/"
```

### 5.2 Karşılaştırma politikası
- **Varsayılan:** Aynı **kalibrasyon ailesindeki** görüntüler karşılaştırılır. DR1 aktif olunca DR1 (Yıl 1) + QR3 (Yıl 2) birlikte tek R7 zaman serisi oluşturur. Bu en temiz seçenek.
- **Aileler arası** (QR2 ↔ QR3): yalnızca `l3_flux_corrections` uygulanarak ve belirgin bir uyarıyla yapılır. Ayrıntı soru listesinde.
- Aynı aile içinde bile `pipeline_version` farklıysa bilgi notu gösterilir.
- `supersedes`: DR1 aktif olunca aynı obs_id'nin QR2 kopyası varsayılan listeden çıkar ama kayıtta kalır. Eski sürüm, yeni sürüm doğrulanana kadar silinmez (Faz 3).

## 6. Bilimsel işlem hattı

### 6.1 Kapsam ve dalga boyu indeksi
1. Konum → SIA2 (her etkin koleksiyon için) → görüntü listesi (doğrudan URL, S3 anahtarı). Eksik kalanlar ve DataLink kalibrasyon bilgisi TAP'tan alınır.
2. Her görüntü için **Range ile başlık okunur** (yaklaşık 23 KB). Gök WCS'inden hedefin dedektör pikseli bulunur.
3. O görüntünün `spectral_wcs` dosyasındaki WCS-WAVE tablosu alınır (dosya sonundan Range ile okunur, sürüm ve dosya başına bir kez önbelleğe alınır). Dalga boyu **SIP'siz bilinear** aramayla hesaplanır.
4. Sonuç `image_target_sample` tablosuna yazılır: `(image, hedef, x, y, λ, bant genişliği, kanal 1–17, survey, ziyaret)`.
5. Survey numarası `SPS_EPA` ve tarihten çıkarılır. Ziyaret, 30 günden uzun boşluklarla ayrılan pozlama kümesidir.

M31 için 57 pozlama 7,1 sn'de indekslendi. Faz 2'de CWAVE haritasıyla karşılaştırılarak doğruluk ölçülecek.

### 6.2 Kesit ve görüntüleyici
- Kesitler IRSA kesit servisinden alınır (`?center=…d&size=…`). Eşzamanlılık en fazla 2–4 istek olur, 503 alınınca Retry-After beklenir. Kesitler `data/cache/<release>/cutouts/` altına FITS olarak kaydedilir.
- Sunucunun istemciye gönderdikleri:
  - IMAGE − ZODI (veya ham) float32 dizisi ve kötü piksel maskesi
  - λ haritasının özeti (min/orta/maks, gradyan yönü)
  - piksel ölçeği, kuzey açısı ve doğu yönü (WCS'ten), birim
  - kaynak, sürüm ve zaman bilgisi
- İstemci tarafı: gerdirme (doğrusal, asinh, log; yüzdelik veya zscale sınırlar), algısal olarak düzgün renk haritaları (viridis, magma, inferno, cividis, gri), ölçek çubuğu, K/D okları.
- **"Yanlış renk"** modu: üç farklı kanal R/G/B'ye eşlenir ve her kanalın λ değeri etikette yazar.
- **Varsayılan kesit boyutu:** 0,1° (yaklaşık 58 px, 6′; kesit içindeki λ yayılımı yaklaşık 0,02 µm). Ayrıntı soru listesinde.
- Kesit içinde λ değiştiği için arayüzde "bu görüntünün üst ve alt kenarı farklı dalga boylarında" notu ve isteğe bağlı bir λ eş-çizgi katmanı gösterilir.

### 6.3 ZODI ve arka plan (öneri, onayınıza bağlı)
- **Görüntüleme:** Varsayılan `IMAGE − ZODI` (IRSA Mozaik aracıyla aynı yaklaşım). "Ham" seçeneği de var.
- **Fark görüntüsü:** Her dönemden `IMAGE − ZODI` alınır, ardından sağlam bir yerel arka plan çıkarılır (σ-kırpılmış medyan; arka plan maskesi listesi kullanılır, SOURCE dahil). Kaynak içermeyen piksel kalmazsa (M31'deki gibi) arka plan çıkarılmaz ve bu açıkça belirtilir.
- **Fotometri:** Halka ile yerel arka plan kullanılır. Halka ZODI'yi kendiliğinden götürür.

### 6.4 Spektrum (kendi açıklık fotometrimiz)
- Bir ziyaretteki tüm pozlamalarda (6 bant × yaklaşık 17–19) hedefin çevresindeki küçük bölge kullanılır.
- **Bant genişliği sorunu:** Kesit servisiyle yaklaşık 110 kesit × 4–5 MB, yani nesne başına yaklaşık 0,5 GB inerdi. Bunun yerine **Range ile yalnızca gereken satırlar** okunur: IMAGE, FLAGS, VARIANCE ve ZODI'nin her biri için yaklaşık 15–25 satır × 8 KB. Böylece pozlama başına yaklaşık 0,5 MB yeterli olur. S3 ve IBE'nin ikisi de Range destekliyor. Uygulama Faz 2'de yapılıp ölçülecek.
- Yöntem:
  - Açıklık yarıçapı yaklaşık 2 px (FWHM yaklaşık 1–1,2 px), halka yaklaşık 4–7 px.
  - Supplement'in fotometri maskesi uygulanır.
  - Akı: F = Σ(I − arka plan)·Ω_piks. Ω başlıktaki `OMEGA_MEDIAN` değerinden alınır, gerekirse katı açı haritası kullanılır. Sonuç µJy olarak verilir.
  - Belirsizlik: σ² = Σ VARIANCE·Ω² + (0,03·F)².
  - Nokta: x = λ, x hatası = bant genişliği/2.
- Arayüzde yöntem açıklanır: "basit açıklık fotometrisi; IRSA'nın PSF uydurmalı aracından farklıdır; genişletilmiş kaynaklarda yalnızca açıklık içindeki ışığı ölçer".

### 6.5 Zaman karşılaştırması
1. Kullanıcı bir λ seçer. Listede her ziyaretin mevcut λ değerleri gösterilir.
2. Her ziyaret için |Δλ|'yı en küçük yapan pozlama seçilir. Δλ ve bant genişliğine oranı gösterilir.
3. Görüntüler ortak bir gök ızgarasına hizalanır (ilk dönemin WCS'i; bilinear yeniden örnekleme).
4. ZODI ve arka plan işlemi (§6.3) uygulanır. İsteğe bağlı olarak **göreli normalleştirme** yapılır (alan yıldızlarının sağlam medyan oranı) ve "normalleştirildi" etiketiyle gösterilir.
5. Görünümler: yan yana, kaydırma çubuğu, yanıp sönme (blink), fark görüntüsü (σ biriminde de).
6. İstatistikler: ortalama, standart sapma, en büyük sapmanın konumu (RA/Dec) ve anlamlılığı (VARIANCE'tan σ).
7. **Uyarılar** (her biri bir kod ve Türkçe metinle):
   - Δλ büyük
   - kalibrasyon ailesi veya boru hattı sürümü farklı
   - maskelenen piksel oranı yüksek
   - He 1,083 µm veya bilinen hava parlaması çizgisine yakın λ
   - dedektör kenarı veya dikroik bölgesi
   - genişletilmiş kaynak (arka plan çıkarılamadı)
8. **Hareketli cisimler:** MOST'tan gelen kareler ve kare başına konumla, cisme ortalanmış kare kare oynatma. 3I/ATLAS için IRSA tablosu hazır demo olarak kullanılır.
9. **Yüksek öz hareketli yıldızlar:** örneğin Barnard Yıldızı (yaklaşık 10″/yıl, 1 yılda yaklaşık 1,7 SPHEREx pikseli). Bu, "konum değiştirme" kavramı için güçlü bir aday. Faz 4'te doğrulanacak.

### 6.6 Cisim–cisim karşılaştırması
- İkinci cisim aranır. Öneri listesinde SIMBAD `otype` değeri aynı olanlar öne çıkar (ör. `BD*` için başka kahverengi cüceler). Farklı tür seçilirse uyarı gösterilir.
- İki görüntü **aynı λ kanalında** (her cisim için en yakın pozlama; Δλ gösterilir), **aynı kesit boyutunda** ve **ortak parlaklık ölçeğinde** gösterilir. Ortak ölçek, iki görüntünün birleşik yüzdeliklerinden hesaplanan tek bir gerdirme aralığıdır. Ölçek bağımsız seçilirse bu belirtilir.
- Karşılaştırma tablosu: tür, tayf türü, uzaklık (paralakstan; kaynağı yazılır), V/K parlaklığı, öz hareket (SIMBAD) ve varsa SPHEREx ölçümleri (açıklık akısı, λ).

### 6.7 ~~Hubble ↔ Webb~~ — iptal edildi (kapsam dışı), 2026-11-14

_Aşağıdaki tasarım uygulanmadı ve uygulanmayacak (DECISIONS §4g)._

- HST ve JWST önizlemeleri yan yana, kayıt bilgisiyle (tarih, alet, filtre, MAST bağlantısı). Biri yoksa "Bu cisim için herkese açık Hubble/Webb görüntüsü bulunamadı" gösterilir.
- Demo cisimlerinin sonuçları ve önizlemeleri başlangıçta arka planda önceden çekilir (`config/demo_targets.toml`).
- MAST CAOM sorgusu: 2′ yarıçap, `dataproduct_type=image`, `intentType=science`, yalnızca `dataRights=PUBLIC`. Sonuçlar alet ve filtreye göre gruplanır. SPHEREx aralığına (0,75–5 µm) düşen filtreler öne alınır.
- Önizleme JPEG'i yalnızca `mast:(HST|JWST)/product/…\.(jpg|png)` kalıbına uyan URI'ler için sunucu üzerinden gelir. Önizleme yoksa kayıt bilgisi ve MAST bağlantısı gösterilir.
- Kapsam yoksa "Bu konumda Hubble/Webb verisi yok" mesajı çıkar. Bu bir hata değil, normal sonuçtur.
- Çözünürlük ve dalga boyu farkı uyarısı gösterilir (SPHEREx 6,15″/piksel; HST/JWST piksel ölçeği yaklaşık 0,03–0,1″).

### 6.8 Nesne bilgi paneli
- SIMBAD (ayna listesi) + Sesame alanları + Wikidata (P3083) + Vikipedi özeti (önce `tr`, yoksa `en`).
- Her satırda kaynak etiketi bulunur. Bilinmeyen alana "bilinmiyor" yazılır.
- TTL: SIMBAD 24 saat, Vikipedi 24 saat, ad çözümleme 7 gün.
- SIMBAD'ın kendi sınıflandırması olduğu gibi gösterilir (ör. M31 için "AGN" ve morfolojik tür "SA(s)b").

### 6.9 Kural tabanlı asistan
- Arayüz: `AssistantEngine.reply(message, context) -> AsyncIterator[chunk]`. İlk uygulama `RuleBasedAssistant`. İleride bir LLM uygulaması aynı arayüze takılabilir.
- **Bağlam:** seçili cisim (bilgi paneli verisi) ve son `comparison` kaydı (sunucunun hesapladığı değerler). İstemciden gelen sayılar kullanılmaz, karşılaştırma kimliğiyle sunucudan okunur.
- **Eşleştirme:**
  1. Türkçe normalizasyon (küçük harf, ı/i, ş/s, ğ/g, ü/u, ö/o, ç/c, noktalama temizliği).
  2. `assistant_faq.json` içindeki anahtar kelime ve eş anlamlı ağırlıklarıyla puanlama.
  3. Eşik altında kalırsa önerilen sorular gösterilir.
  4. Mesajda cisim adı geçerse çözümleyici denenir ve cisim açılır.
- **"Karşılaştırmayı yorumla":** Şablon cümleler yalnızca mevcut alanlarla doldurulur (kayma px/″, Δ%, Δλ ve bant genişliğine oranı, kanal eşleşme durumu, sürüm/ZODI uyarıları, SIMBAD değerleri). Değer yoksa "Önce bir karşılaştırma yap" denir.
- **Akış:** Yanıt WS üzerinden parça parça gelir ("yazıyor…" efekti), WS yoksa HTTP ile tek seferde döner.

### 6.10 Excel dışa aktarma
- openpyxl ile sunucuda, bellekte üretilir. Sayfalar Özet, Gözlemler, Zaman karşılaştırması, Cisim karşılaştırması ve Hareket. Boş olan sayfa "yapılmadı" notuyla eklenir.
- Hücre güvenliği: `=`, `+`, `-` veya `@` ile başlayan her metin hücresinin başına `'` eklenir. URL'ler düz metin olarak yazılır.
- Sayfa başına en fazla 5.000 satır. Ham piksel verisi konmaz.
- Dosya adı `ascii_slug(ad)_YYYY-MM-DD.xlsx`. Her indirme bir `download` olayı üretir.

## 7. Ad ve koordinat çözümleme akışı

```
girdi ─┬─ koordinat ayrıştırıcı (yerel, saf):  ondalık | hms/dms | iki nokta | galaktik (l=, b=)
       │      └─ geçerli → ICRS (ra, dec) + "giriş biçimi" etiketi
       └─ ad
            ├─ [paralel] Sesame SNV (zaman aşımı yaklaşık 8 sn)
            ├─ [paralel] JPL SBDB (Güneş sistemi mi?)
            └─ sonuç yoksa veya belirsizse:
                 ├─ SIMBAD TAP  ident LIKE '<normalize>%'  (ayna listesi)
                 └─ Wikidata wbsearchentities
                 → öneri listesi (en fazla 8), Türkçe hata mesajı
```
Güneş sistemi cismi seçilirse konum tek değildir. Akış MOST ile "tarih aralığı → kareler" yoluna geçer.

## 8. Veri modeli (ilk sürüm)

| Tablo | Alanlar (özet) |
|---|---|
| `data_release` | id, label, status, calib_family, doi, config_hash, discovered_at, validated_at, is_default, notes |
| `spherex_image` | id, release_id, obs_id, detector, planning_period, t_start/t_end (MJD), exptime, em_min/em_max, s_region, center_ra/dec, fits_url, s3_key, file_version, pipeline_version, survey (1–4), is_deep, sps_epa, obs_release_date, header_fetched_at; **benzersiz (release_id, obs_id, detector)** |
| `image_calib` | image_id, kind (spectral_wcs, flux_correction…), url, version |
| `image_target_sample` | image_id, target_key (ra, dec yuvarlanmış), x, y, wavelength_um, bandwidth_um, channel, on_detector, method, created_at |
| `cutout` | id, image_id, ra, dec, size_deg, path, bytes, created_at, last_access |
| `photometry_point` | image_id, target_key, method, aperture_px, flux_ujy, err_ujy, n_masked, flags, created_at |
| `object_cache` | provider, key, payload (json), fetched_at, expires_at, source_url |
| `event` | id, ts, session_id, user_id (null), type, page, object_key, release_id, payload (json), ip_hash, ua_family |
| `feedback` | id, ts, session_id, user_id, category, message, email (isteğe bağlı), context (json), status |
| `job` | id, kind (update-data…), status, started_at, finished_at, log, params |
| `comparison` | id, session_id, user_id, kind (time\|object), params (json), result (json: kayma, Δ%, Δλ, uyarılar), created_at. Asistan ve Excel bu kaydı okur. |
| `user` | id, email (benzersiz, küçük harf), role (user\|admin — `ADMIN_EMAIL` ile), created_at, last_login_at, deleted_at |
| `email_code` | id, email, code_hash (argon2), expires_at (+10 dk), attempts (en fazla 5), used_at, sent_at, ip_hash |
| `saved_object` | user_id, object_key, label, ra, dec, kind, created_at |
| `user_session` | id (rastgele, çerezde), user_id, created_at, expires_at, revoked_at |

## 9. API uç noktaları (`/api/v1`, ilk taslak)

| Yöntem | Yol | Açıklama | Faz |
|---|---|---|---|
| GET | `/health` | Servis ve yukarı akış (upstream) durumu | 1 |
| GET | `/meta/releases` | Etkin sürümler, son güncelleme zamanı | 1/3 |
| GET | `/meta/attributions` | Atıf metinleri | 1 |
| POST | `/events` | İstemci olayları (toplu, `sendBeacon`) | 1 |
| GET | `/resolve?q=` | `{kind: coordinate\|object\|solar_system\|ambiguous\|not_found, candidates[]}` | 2 |
| GET | `/sky/coverage?ra&dec&release` | Ziyaret, bant ve kanala göre gruplu görüntüler ve λ değerleri | 2 |
| GET | `/sky/cutout?image_id&ra&dec&size&zodi=sub\|raw` | Kesit meta verisi + veri bağlantıları | 2 |
| GET | `/sky/cutout/{id}/data` | float32 + maske (ikili) | 2 |
| GET | `/sky/cutout/{id}.png?stretch&cmap&lo&hi` | Sunucu tarafında üretilen önizleme | 2 |
| GET | `/sky/spectrum?ra&dec&visit&release` | Fotometri noktaları ve yöntem bilgisi | 2 |
| POST | `/compare/time` | {ra, dec, λ, ziyaretler, boyut, normalleştirme} → hizalanmış kareler, fark, istatistikler, uyarılar | 4 |
| POST | `/compare/objects` | {a, b, λ} → yan yana görüntü ve spektrumlar | 4 |
| GET | `/moving/{designation}/frames?start&end` | MOST kareleri | 4 |
| GET | `/objects/{key}/info` | Bilgi paneli (kaynak etiketli) | 5 |
| ~~GET~~ | ~~`/telescopes?ra&dec&radius`~~ | iptal (kapsam dışı) | — |
| ~~GET~~ | ~~`/telescopes/preview?uri=`~~ | iptal (kapsam dışı) | — |
| POST | `/assistant/message` | Kural tabanlı asistan (HTTP yedek yolu) | M5 |
| GET | `/export/object.xlsx?key=…` | Tek cisim (misafir dahil) | M4 |
| POST | `/export/objects.xlsx` | Kayıtlı listeden birden çok cisim (giriş gerekli) | M6 |
| POST | `/feedback` | Geri bildirim | M3 |
| POST | `/auth/request-code`, `/auth/verify`, `/auth/logout` · GET `/auth/me` | E-posta kodu ile giriş | M6 |
| GET/POST/DELETE | `/me/objects`, `/me/comparisons` | Kayıtlı cisimler ve çalışmalar | M6 |
| GET | `/admin/users`, `/admin/events`, `/admin/feedback` | Admin (rol: `ADMIN_EMAIL`) | M6 |
| WS | `/ws` | Tek WebSocket kanalı: `{type: progress\|assistant_chunk\|admin_event\|ping}` | M2+ |

**WebSocket sözleşmesi:** İstemci `/ws` adresine bağlanır ve `subscribe` mesajıyla bir iş kimliğine (`job_id`) ya da admin akışına abone olur. Uzun işler (`/sky/coverage`, `/compare/time`) HTTP yanıtında hemen bir `job_id` döner, ilerleme WS üzerinden akar ve sonuç HTTP ile de alınabilir (`GET /jobs/{id}`). WS kurulamazsa istemci HTTP yoklamasına düşer. Bağlantı koparsa üstel geri çekilmeyle (1 → 30 sn) yeniden bağlanır. Admin WS'i oturum çereziyle yetkilendirilir.

**Hata sözleşmesi:** Sunucu `{code, params, provenance}` döndürür. Türkçe metin istemcideki i18n katmanında üretilir.
Hata kodları: `NO_COVERAGE`, `UPSTREAM_UNAVAILABLE`, `UPSTREAM_BUSY`, `NAME_NOT_FOUND`, `AMBIGUOUS_NAME`, `INVALID_COORDINATE`, `RATE_LIMITED`, `FROM_CACHE` (bilgi), `RELEASE_MISMATCH` (uyarı).

## 10. Önbellek

- SPHEREx dosyaları: `data/cache/<release>/…`. Sürümler asla karışmaz, anahtar her zaman `release` içerir.
- Diğer kaynaklar: `data/cache/_external/…` ve `object_cache` tablosu.
- TTL'ler:
  - kapsam listesi 24 saat (QR haftalık güncellendiği için)
  - başlık ve kalibrasyon kalıcı (dosya sürümü değişmez)
  - kesit kalıcı (LRU ile silinir)
  - SIMBAD ve Vikipedi 24 saat
  - MAST 24 saat
  - ad çözümleme 7 gün
- Disk sınırı yapılandırılabilir (varsayılan 5 GB), `cli cache-prune` ile temizlenir.
- Demo yedeği: gerçek yanıtlar kaydedilir ve arayüzde "önbellekten · alınma: 2026-11-12" etiketiyle gösterilir.

## 11. Güvenlik ve gizlilik

- **SSRF:** Sunucu yalnızca `config/upstreams.toml` listesindeki sunuculara bağlanır. Yönlendirmeler de listeyle denetlenir (ör. Sesame → `vizier.idia.ac.za`). Liste:
  - IRSA: `irsa.ipac.caltech.edu`, `nasa-irsa-spherex.s3.amazonaws.com`
  - CDS: `cds.unistra.fr`, `vizier.idia.ac.za`, `simbad.cds.unistra.fr`, `simbad.cfa.harvard.edu`
  - MAST: `mast.stsci.edu`
  - JPL: `ssd-api.jpl.nasa.gov`, `ssd.jpl.nasa.gov`
  - Wikimedia: `www.wikidata.org`, `tr.wikipedia.org`, `en.wikipedia.org`
  - E-posta: `api.emailjs.com`
  Kullanıcıdan gelen URL hiçbir zaman indirilmez.
- **Girdi doğrulama:** RA 0–360, Dec ±90, boyut 0,01–0,5°, ad uzunluğu en fazla 100 karakter. Karakter kümesi kısıtlıdır. ADQL'e giden değerler parametre olarak değil güvenli biçimde kaçışlanarak eklenir.
- Hız sınırı (IP ve oturum başına), CORS yalnızca kendi kökeninden, güvenlik başlıkları (CSP, HSTS, X-Content-Type-Options, Referrer-Policy). Hata mesajlarında iç ayrıntı yoktur.
- Oturum: sunucunun ürettiği anonim `sid` çerezi (`httpOnly`, `Secure`, `SameSite=Lax`). Yönetici çerezi ayrıdır ve `SameSite=Strict`.
- **KVKK:** IP adresi ham saklanmaz, tuzlanmış hash olarak saklanır. User-Agent'tan yalnızca tarayıcı ailesi tutulur. Saklama süresi 90 gün. Site ilk günden herkese açık olduğu için gizlilik bildirimi **Faz 1'de** geliyor.
- Sırlar yalnızca `.env` dosyasında durur, istemci koduna girmez.

## 12. Faz planı (v0.2 — 32 saatlik takvim, teslim 15 Kasım 16:00)

> **Güncelleme (12 Kasım akşamı, DECISIONS.md §4b):** Kesin kapsam **Cuma akşamına** kadar mevcut veriyle (QR2/QR3) bitecek. NASA yeni veriyi 13→14 Kasım gecesi yayınlayacak.
> Yeni öncelik sırası: cisim–cisim > arayüzün tamamı > gözlem filtreleri > Excel > WebSocket > hesaplar > admin > asistan > Hubble↔Webb > DR1 hazırlığı (`enabled: false`, `tools/check_release.py`, `tools/prewarm.py`, `docs/NEW_DATA.md`) > cilalama.
> Aşağıdaki tablo ilk plandır. Sıra yukarıdaki listeye göre uygulanır.

`PROMPT1.md`'deki 10 fazlık plan, `DECISIONS.md`'deki öncelik sırasına göre 8 faza indirildi. Her faz sonunda: çalışan sürüm, commit ve Render'a yayın.

| Faz | Süre | İçerik | Kabul |
|---|---|---|---|
| **1** | ~3 sa | Depo yapısı, venv/npm, ruff/ESLint, `.env.example`, i18n (tr/en), koyu uzay teması, üst çubuk (arama henüz bağlı değil), three.js Samanyolu, FastAPI + statik ön uç, DB/Alembic, `event` tablosu + `/events`, gizlilik bildirimi (site herkese açık olduğu için öne çekildi), `config/*.toml`, Dockerfile + `render.yaml` | Boş site yerelde ve Render'da açılıyor; `/api/v1/health` yeşil |
| **2** | ~8 sa | Koordinat ayrıştırıcı (testli), ad çözümleme (Sesame + SIMBAD aynası + JPL + öneriler), SIA2 kapsamı, Range ile dalga boyu indeksi, kesit + görüntüleyici (gerdirme, renk haritası, ölçek, K/D), WS ilerleme, temel bilgi paneli (SIMBAD/Vikipedi) | M31, M42 ve WISE 0855 ad ve koordinatla açılıyor |
| **3** | ~7 sa | Zaman karşılaştırması (Dönem A/B, yanıp sönme, kaydırma, fark; kayma px/″, parlaklık farkı %, kanal eşleşmesi, uyarılar), MOST ile hareketli cisim kareleri (3I/ATLAS), geri bildirim butonu | Gerçek bir iki dönem karşılaştırması ve 3I/ATLAS oynatma çalışıyor |
| **4** | ~4 sa | Cisim–cisim karşılaştırması (tür önerisi, ortak ölçek, tablo), tek cisim Excel indirme | İki kahverengi cüce yan yana; .xlsx açılıyor |
| **5** | ~3 sa | Kural tabanlı asistan (`assistant_faq.json`, "Karşılaştırmayı yorumla", WS akışı, "yazıyor…") | Asistan gerçek karşılaştırma değerlerini yorumluyor, değer yoksa uydurmuyor |
| **6** | ~4 sa | Hesaplar (EmailJS kodu ile giriş), kayıtlı cisimler ve çalışmalar, çoklu Excel, admin paneli (canlı akış) | Kötüye kullanım testleri (yanlış kod, süre, deneme ve gönderim sınırları) geçiyor; olaylar admin panelinde canlı görünüyor |
| ~~**7**~~ | — | ~~Hubble ↔ Webb önizlemeleri~~ — iptal edildi (kapsam dışı) | — |
| **8** | ~1–2 sa | Cila, erişilebilirlik, README, `DEMO.md`, son yayın | Demo senaryosu baştan sona çalışıyor |

- **Spektrum grafiği** (kendi açıklık fotometrimiz) kesin kapsam listesinde yok. Faz 8'de zaman kalırsa eklenecek. Cisim tablosundaki "SPHEREx ölçümleri" yalnızca seçili kanaldaki açıklık akısı olacak.
- **`update-data` CLI** yalnızca sürüm keşfi ve izlenen hedefleri kapsayacak şekilde sadeleştirildi. Faz 2'deki sürüm yapılandırmasıyla birlikte gelecek.

## 13. Riskler

| Risk | Olasılık / etki | Önlem |
|---|---|---|
| Yanıltıcı "değişim" (Δλ, kalibrasyon, sürüm, atmosferik çizgiler) | Yüksek / yüksek | Uyarı kodları, normalleştirme seçeneği, σ birimli fark görüntüsü, asistanın sistem istemindeki kurallar |
| QR2 → DR1 geçişi tam proje sırasında oluyor | Yüksek / orta | Yapılandırma tabanlı sürümler, `supersedes`, sürüme göre ayrılmış önbellek |
| IRSA yavaşlığı ve 503 (TAP 19 sn, kesit 14 sn) | Yüksek / orta | SIA2 önceliği, Range okuma, eşzamanlılık sınırı, devre kesici, önbellek, "önbellekten" demo modu |
| Kesit boyutu (PSF/EPSF nedeniyle 4–5 MB) ve bant genişliği | Yüksek / orta | Spektrum için Range ile satır okuma, kesit boyutu sınırı, disk sınırı |
| CDS kesintisi | Şu an gerçekleşmiş / orta | Ayna listesi, Sesame yedeği, "kaynak geçici olarak erişilemez" durumu |
| astropy WCS ve SIP tuzakları, MWIR'de X çevirmesi | Orta / yüksek | Kendi λ fonksiyonumuz, CWAVE ile çapraz doğrulama testi |
| ~~MAST gecikmesi ve JWST önizlemelerinin seyrekliği~~ | — | Hubble ↔ Webb iptal edildi; risk ortadan kalktı |
| Genişletilmiş kaynaklarda arka plan kestirilemiyor (SOURCE %100) | Orta / orta | Daha büyük halka ya da arka plansız mod, açık uyarı |
| Render ücretsiz planı: 15 dk hareketsizlikten sonra uyku, soğuk başlangıç (~30–60 sn), kalıcı olmayan disk, 512 MB RAM | Yüksek / orta | `docs/DEPLOY.md`: harici ping, Postgres, önbelleği başlangıçta ısıtma, bellek bilinçli işleme |
| EmailJS ücretsiz plan sınırları (ayda 200, saniyede 1) | Orta / orta | Gönderim hız sınırları, kota dolarsa net hata mesajı |
| Kural tabanlı asistanın sınırlı anlama gücü | Yüksek / düşük | Önerilen sorular, hızlı düğmeler, panel notu |
| Windows ortamı (cp1254, Türkçe karakterli yol, Python 3.15 varsayılan) | Orta / düşük | `PYTHONUTF8=1`, 3.13 venv, yol testleri |
| KVKK | Orta / yüksek | En az veri, IP hash, 90 gün saklama, ilk ziyarette bildirim |
| Süre (32 saat) | Yüksek / yüksek | Öncelik sırası, her faz sonunda yayın, kapsam dışı maddeler açıkça listelendi |

## 14. Kararlar

Faz 0'daki S1–S16 soruları yanıtlandı. Tüm kararlar [`DECISIONS.md`](DECISIONS.md) dosyasında.
