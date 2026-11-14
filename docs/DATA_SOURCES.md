# Veri Kaynakları — Canlı Doğrulama Notları (Faz 0)

> **Durum:** Faz 0 taslağı · **Tarih:** 2026-11-12, yaklaşık 15:20–16:45 UTC
> **Yöntem:** Tüm bilgiler bu tarihte yapılan küçük canlı çağrılarla doğrulandı (Python 3.13 + astropy/pyvo/astroquery, curl).
> Aksi belirtilmedikçe sayılar ve süreler bu testlere aittir; servis yükü değiştikçe değişir.
> **⚠ İşareti**, `PROMPT1.md` içindeki bilgiyle çelişen ya da onu güncelleyen bulguları gösterir.

---

## 0. Özet: İstemden farklı çıkan / kritik bulgular

| # | Bulgu | Etki |
|---|---|---|
| ⚠1 | **QR3 yayında** (Eylül 2026, DOI 10.26131/IRSA662). Yeni **R7** boru hattıyla işleniyor (`l2b-v27`, `VERSION 7.0.x`). QR2 artık varsayılan tek sürüm değil. | Veri sürümü modeli en baştan çok sürümlü olmalı. |
| ⚠2 | **DR1 (Yıl 1 yeniden işleme, R7) AWS S3'e yüklenmiş** (`s3://nasa-irsa-spherex/dr1/`, son değişiklik 2026-11-11). Ancak IRSA IBE'de (404) ve TAP'ta **henüz yok**, yani resmî olarak duyurulmamış. Supplement "late fall 2026" diyor. | Yakında QR2'nin yerini alacak. Faz 3'ün "yeni sürümü yapılandırmayla ekle" testi için doğal bir aday. |
| ⚠3 | IRSA, QR2 ile QR3'ün birleştirilmesinde **"dikkat"** öneriyor (kazanç kalibrasyonu değişti). QR3 ile birlikte gelen `l3_flux_corrections` dosyaları "**pre-QR3 verisi için çarpımsal akı düzeltmesi**" (piksel başına). | Zaman karşılaştırmasında sürüm/kalibrasyon ailesi kontrolü ve isteğe bağlı düzeltme gerekiyor. |
| ⚠4 | QR2'nin **kendi içinde** de boru hattı sürümü değişiyor (M31 örneğinde 6.4 → 6.5.4 → 6.5.7). Yalnızca "aynı sürüm" kuralı yeterli değil. | Her görüntü için `VERSION` saklanmalı, arayüzde gösterilmeli. |
| ⚠5 | TAP `obscore.access_url` doğrudan FITS'e değil, **DataLink** VOTable'a gidiyor. SIA2 ise doğrudan FITS URL'si ve `cloud_access` (S3 anahtarı) veriyor. | Erişim katmanı iki yolu da desteklemeli. |
| ⚠6 | `FLAGS` bit 21 (**SOURCE**, "bilinen kaynak") hata bayrağı değil, bilgi bayrağı. Tam görüntüde piksellerin %64'ünde, M31 kesitinin **%100'ünde** işaretli. "Sıfır olmayan FLAGS'ı maskele" yaklaşımı görüntüyü yok eder. | Supplement'in maske listeleri kullanılmalı (§5). |
| ⚠7 | Bayrak tanımlarının başlıktaki biçimi **sürüme göre değişiyor**: QR2'de `MP_<AD> = bit`, R7/QR3'te `MSKNnnnn/MSKMnnnn/MSKDnnnn`. R7 yeni bitler ekliyor (CROSSTALK, STREAK, GHOST*, BLOOM, SNOWBALL, HALO…). | Bayrak okuyucu iki biçimi de çözmeli. Bitler sabit kodlanmamalı. |
| ⚠8 | QR3/R7 kesitlerinde `PSF` uzantısı **yok**, yerine `EPSF` (ikili tablo) var. | Uzantı adları sürüme göre ele alınmalı. |
| ⚠9 | **ZODI çıkarılmamış.** Kelsall (1998) modeli genliği olduğundan düşük tahmin ediyor. R7, dalga boyuna bağlı ölçek çarpanı uyguluyor (`ZODIMDL`: QR2 `ModifiedKelsallModelWithHPFT`, R7 `KEL98_WAVESCL_V1`). | Bilimsel karar: §6 ve sorular. |
| ⚠10 | **astropy tuzağı:** `WCS(header, fobj=hdul, key='W')` ile kurulan dalga boyu WCS'ine SIP bozulma katsayıları da uygulanıyor. Hedefteki λ **16 nm'ye kadar** kayıyor. Kanal genişliği yaklaşık 45–55 nm. | Dalga boyu araması SIP'siz (ham piksel koordinatıyla) yapılmalı. |
| ⚠11 | CDS Strasbourg'da **kısmi kesinti:** SIMBAD web, TAP ve `sim-id` 404 ("This page is currently unavailable") veriyor. Sesame, **IDIA (Güney Afrika) aynasına** 302 ile yönlendiriyor. SIMBAD'in **Harvard/CfA aynası** çalışıyor. | Ad çözümleyici ve nesne bilgisi için yedek adres listesi gerekli. |
| ⚠12 | Sesame, istemdeki örnek **`WISE 0855` adını çözemiyor.** Tam ad (`WISE J085510.83-071442.5`) çözülüyor. | Öneri listesi için SIMBAD `LIKE` araması ve Wikidata araması kullanılmalı. |
| ⚠13 | Windows sertifika deposu, CDS'nin GEANT/HARICA zincirini tanımıyor (`urllib` SSL hatası). `certifi` ile sorun yok. | Arka uç HTTP istemcisi `certifi` kullanmalı (httpx varsayılan olarak öyle yapıyor). |
| ⚠14 | IRSA yük altında **503 "Server busy, retry later." (Retry-After: 5)** döndürüyor. | Yeniden deneme, geri çekilme ve eşzamanlılık sınırı şart. |
| 15 | Hareketli cisimler için IRSA **MOST** aracı SPHEREx'i destekliyor (`catalog=spherex`, VOTable). 3I/ATLAS için 222 kare 2,9 sn'de döndü, her karede cismin o anki konumu da var. | JPL Horizons ile kendi eşlememizi yazmaya gerek yok. |
| 16 | HTTP **Range** istekleri IBE'de ve S3'te çalışıyor (206). Başlık ve tek uzantı okumak için dosyanın tamamını indirmek gerekmiyor. | Dalga boyu indeksi ve spektrum için büyük bant genişliği kazancı sağlıyor (§4.6). |

---

## 1. Ortam

| Bileşen | Sonuç |
|---|---|
| İşletim sistemi | Windows 11 Pro 10.0.26300, PowerShell 5.1 (Git Bash de var) |
| Python | `python` = **3.15.0** (bilimsel paket yok), `py -3.14` (numpy, Pillow, matplotlib), **`py -3.13` = 3.13.17**: numpy 2.5.4, astropy 8.0.2, pyvo 1.10.0, astroquery 0.4.11, requests 2.34.2, certifi 2026.10.23. `~\.venv` de 3.13.17. |
| Node.js / npm | v26.12.0 / 11.20.0 (uv, pnpm, yarn yok) |
| Git | 2.56.0, `user.name` ve `user.email` tanımlı, `init.defaultBranch` tanımsız |
| AWS CLI | **Yok.** Gerekmiyor: kova HTTPS üzerinden imzasız listelenebiliyor (§4.5). |
| Konsol kod sayfası | **cp1254.** Python'un Türkçe dışı Unicode karakterleri basması hata veriyor → `-X utf8` / `PYTHONUTF8=1` kullanılmalı. |
| Yol | Ev dizini boşluk ve "ı" içeriyor (`E. Sarp Karabıyık`). Python ve curl sorunsuz çalıştı. Bazı yerel derleme araçları (node-gyp vb.) için risk olarak not edildi. |

Öneri: arka uç için `py -3.13 -m venv .venv`. 3.15 için astropy ve benzeri tekerlekler doğrulanmadı.

---

## 2. Ad çözümleme

### 2.1 CDS Sesame
- Uç nokta: `https://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/SNV?<ad>` (XML; `S`=SIMBAD, `N`=NED, `V`=VizieR sırası).
- ⚠ Şu an **302 ile `https://vizier.idia.ac.za/viz-bin/nph-sesame/...`** adresine yönlendiriyor. Yanıtta `Resolver name="S=Simbad, IDIA (via url)"` ve `INFO: from cache` görünüyor.
- Yanıt alanları: `oname`, `otype`, `jpos`, `jradeg`, `jdedeg`, `refPos`, `errRAmas/errDEmas`, `pm`, `plx`, `Vel`, `z`, `spType`, `MType`. Bu, SIMBAD kapalıyken temel bilgi için yedek olarak kullanılabilir.

| Sorgu | Sonuç | Süre |
|---|---|---|
| `M31` | `M 31`, 10.684708 / 41.268750, otype **AGN**, MType `SA(s)b`, Vel −300 km/s | 2,6 sn |
| `Betelgeuse` | `* alf Ori`, 88.792939 / 7.407064, `s*r`, spType M1-M2Ia-Iab, plx 6.55±0.83 mas | 1,5 sn |
| `Orion Nebula` | `M 42`, 83.820100 / −5.387600, `HII` | 1,6 sn |
| ⚠ `WISE 0855` | **Bulunamadı** | 7,7 sn |
| `WISE J085510.83-071442.5` | `WISEA J085510.74-071442.5`, 133.818908 / −7.247048, `BD*` | 1,7 sn |
| `3I/ATLAS`, `C/2025 N1`, `Ceres` | Bulunamadı (beklenen: Güneş sistemi kapsanmıyor) | 4,6–6,1 sn |
| `xyznotanobject123` | Bulunamadı | 6,5 sn |

- Kararsızlık: Aynı oturumda `-oxpI/S?Betelgeuse` bir kez 60 sn'de zaman aşımına uğradı, bir kez de "Nothing found" döndü. Zaman aşımı, yedek yol ve önbellek şart.
- Bulunamayan adlarda Sesame 5–8 sn sürüyor, çünkü tüm çözücüleri deniyor. JPL SBDB sorgusu paralel çalıştırılmalı.

### 2.2 SIMBAD (TAP)
- ⚠ `https://simbad.cds.unistra.fr/simbad/sim-tap` (astroquery'nin varsayılanı), `/simbad/`, `sim-id` ve `sim-script` **404** döndürüyor. Sayfa metni: "This page is currently unavailable". Oturum sonunda yeniden denendi, hâlâ 404.
- **Çalışan ayna:** `https://simbad.cfa.harvard.edu/simbad/sim-tap` (ayrıca `simbad.harvard.edu`). Sync uç noktası: `/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=csv&QUERY=...`
- Test sorgusu (1,0 sn):
  ```sql
  SELECT b.main_id, b.otype, b.ra, b.dec, b.sp_type, b.plx_value, b.plx_err, b.rvz_redshift,
         b.rvz_radvel, b.galdim_majaxis, f.filter, f.flux
  FROM basic AS b JOIN ident AS i ON i.oidref = b.oid
  LEFT JOIN flux AS f ON f.oidref = b.oid AND f.filter IN ('V','K')
  WHERE i.id IN ('M  31','M 31','* alf Ori','WISE J085510.83-071442.5','NAME Orion Nebula')
  ```
  Sonuçlar: alf Ori (V 0.42, K −4.05, plx 6.55); `M  31` (AGN, V 3.44, K 0.984, galdim_majaxis 199.53′); `M  42` (HII); `WISEA J085510.74-071442.5` (BD*, sp **Y2**, plx **439.0** mas). Not: SIMBAD tanımlayıcıları iki boşluklu (`M  31`) olabiliyor.
- Öneri listesi için bulanık arama: `WHERE i.id LIKE 'WISE%0855%'` → 10 aday döndü (1,8 sn), doğru nesne aralarında. Sıralama ve süzme gerekli.
- Tür etiketleri: `otypedef` tablosu (`label`, `description`), ör. `BD*` → "Brown Dwarf", `s*r` → "Red Supergiant".
- ⚠ astroquery.simbad sunucusu sabit kodlu (`conf.server = simbad.cds.unistra.fr`). Kendi TAP istemcimiz yapılandırılabilir ayna listesiyle çalışmalı.

### 2.3 Güneş sistemi cisimleri (JPL)
- SBDB: `https://ssd-api.jpl.nasa.gov/sbdb.api?sstr=<ad>` (yaklaşık 1 sn). `3I` → `C/2025 N1 (ATLAS)`, kind `cu`, "Hyperbolic Comet". `Ceres` → `1 Ceres (A801 AA)`, "Main-belt Asteroid".
- Horizons: `https://ssd.jpl.nasa.gov/api/horizons.api?format=json&COMMAND='DES=C/2025 N1;'&EPHEM_TYPE=OBSERVER&CENTER='500@399'&QUANTITIES='1'&ANG_FORMAT=DEG...` → 2025-08-10: RA 246.71065, Dec −16.78818 (yaklaşık 1 sn).

### 2.4 Wikidata ve Vikipedi
- SIMBAD kimliğinden Wikidata'ya: `action=query&list=search&srsearch=haswbstatement:"P3083=M 31"` → Q2469 → `trwiki: Andromeda Galaksisi`, `enwiki: Andromeda Galaxy`. `* alf Ori` → Q12124. (Çift boşluklu `M  31` eşleşmedi, normalleştirme gerekli.)
- Serbest arama: `wbsearchentities&search=WISE 0855` → Q16664406 "WISE 0855–0714". Öneri listesine katkı sağlar.
- Vikipedi REST özeti: `https://tr.wikipedia.org/api/rest_v1/page/summary/<başlık>`. Andromeda_Galaksisi ve Betelgeuse 200 döndü (0,3 sn). `WISE_0855−0714` Türkçe vikide 404 verdi, İngilizceye düşüldü ve 200 alındı.
- Wikimedia API'leri açıklayıcı bir User-Agent ister. İletişim bilgisi `.env` üzerinden ayarlanabilir olmalı (soru listesinde).

---

## 3. SPHEREx — IRSA TAP

### 3.1 Şema
Uç nokta `https://irsa.ipac.caltech.edu/TAP` (pyvo `TAPService`). SPHEREx tabloları:

| Tablo | Açıklama |
|---|---|
| `spherex.obscore` | IRSA ObsCore (62 sütun) |
| `spherex.observation` | CAOM Observation |
| `spherex.plane` | CAOM Plane (`obs_publisher_did` ile obscore'a bağlanıyor) |
| `spherex.artifact` | CAOM Artifact (`uri`, `producttype`, `contentlength`, `contentchecksum`) |
| `spherex.provenance_input` | Bilim düzlemi → kalibrasyon düzlemi bağlantısı |

Önemli `obscore` sütunları: `obs_id` (ör. `2025W28_1B_0480_4`), `obs_collection` (`spherex_qr2`, `spherex_qr3`), `energy_bandpassname` (`SPHEREx-D1`…`D6`), `em_min/em_max` [m], `t_min/t_max` [MJD], `t_exptime` [s], `access_url` (⚠ DataLink), `s_region`, `s_pixel_scale` (6.15″), `s_xel1/2` (2040), `target_name` (`SPS_16174`), `obs_release_date`, `obs_creation_date`, `algorithm_name` (`exposure`), `target_moving`, `access_estsize` (boş).

### 3.2 M31 kapsam sorgusu
```sql
SELECT obs_id, obs_collection, energy_bandpassname, em_min, em_max, t_min, t_max, access_url, ...
FROM spherex.obscore
WHERE CONTAINS(POINT('ICRS', 10.684708, 41.268750), s_region) = 1
```
- **361 satır, 19,2 sn** (yavaş, önbellek gerekli). Hepsi `dataproduct_type=image`, `calib_level=2`.
- Koleksiyonlar: `spherex_qr2` 305, `spherex_qr3` 56. İki koleksiyonda ortak `obs_id` yok.
- Bantlar: D1–D6 için 57–63'er satır.
- Aylara göre: 2025-07 (109), 2025-08 (4), 2025-12 (90), 2026-01 (22), 2026-07 (110), 2026-08 (26) → **3 ziyaret** (Survey 1, Survey 2, Survey 3).
- QR2 2025-07 → 2026-07 arasını, QR3 ise 2026-07 ve 2026-08'i kapsıyor (yayım 2026-09-15).

### 3.3 DataLink
`access_url` (ör. `https://irsa.ipac.caltech.edu/datalink/links/spherex?ID=ivo://irsa.ipac/spherex_qr2?2025W28_1B_0480_4/D4`) şunları döndürüyor:
- `#this`: doğrudan FITS (QR2 örneği 71,6 MB, QR3 örneği 65,9 MB)
- `#cutout`: `https://irsa.ipac.caltech.edu/ibe/cutout` (hizmet tanımı)
- `#calibration`: o görüntüde kullanılan **tam kalibrasyon dosyaları**. QR2: nonfunc, dichroic, spectral_wcs (`cal-wcs-v4-2025-254`), readnoise, abs_gain_matrix, nonlinear, dark, average_psf, gain_factors.yaml. QR3: ek olarak epsf, sip, xtalk_class2 (ecsv), zodi_scaling_v2 (ecsv), nonfunc_v2.
- FITS başlığı kalibrasyonları yalnızca UUID olarak tutuyor (`HISTORY [CALIB] spectral_wcs <uuid>`). Dosya adları için DataLink gerekli.

### 3.4 URL yapısı
```
https://irsa.ipac.caltech.edu/ibe/data/spherex/{qr2|qr3}/level2/{planlama dönemi}/l2b-v{NN}-{YYYY-DDD}/{dedektör}/
    level2_{obs_id}D{dedektör}_spx_l2b-v{NN}-{YYYY-DDD}.fits
```
- QR2 örneği: `l2b-v20-2025-260` (başlık `VERSION = '6.4+psffix1'`). QR3 örneği: `l2b-v27-2026-222` (`VERSION = '7.0.5'`).
- `l2b-vNN` dosya sürümüdür, boru hattı sürümü başlıktaki `VERSION` anahtarıdır. İkisi de saklanmalı.
- Planlama dönemi `2025W28_1B` biçiminde: hafta, yarım hafta (1/2), plan harfi. Her dönem yaklaşık 3,5 gün.

---

## 4. SPHEREx — diğer erişim yolları

### 4.1 SIA2
- `https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_qr3&POS=circle+10.684708+41.26875+0.001&RESPONSEFORMAT=VOTable` → 56 satır, **1,8 sn**.
- `access_url` **doğrudan FITS** veriyor. `cloud_access` sütunu `{"aws": {"bucket_name": "nasa-irsa-spherex", "key": "qr3/level2/...fits", "region": "us-east-1"}}` biçiminde.
- Koleksiyonlar (belgeye göre): `spherex_qr2`, `spherex_qr2_deep`, `spherex_qr3`, `spherex_qr3_deep`. Derin alanlar ekliptik kutuplarda.
- Belgeye göre SIA2, TAP'ın yaklaşık 1 gün gerisinde.

### 4.2 Kesit servisi
- Tam FITS URL'sine şu ek getiriliyor: `?center=<ra>,<dec>d&size=<derece>`.
- QR2 testi (`size=0.1`): 200, `application/fits`, **5.106.240 bayt, 13,8 sn**, 58×58 piksel.
- QR3 testi (`size=0.05`): ilk denemede **503 "Server busy, retry later." (Retry-After: 5)**, 10 sn sonra 200. 4.049.280 bayt, 15,6 sn, 29×29 piksel.
- ⚠ Kesitler PSF/ePSF uzantısını **kesmeden** içeriyor. Boyutun büyük kısmı bu: QR2 PSF küpü 101×101×121 float32 ≈ 4,9 MB, QR3 EPSF tablosu ≈ 3,9 MB. Yani küçük bir kesit bile 4–5 MB tutuyor.

### 4.3 Kesit içeriği
| Uzantı | QR2 (6.4) | QR3 (R7, 7.0.5) |
|---|---|---|
| `IMAGE` | float32, `BUNIT = MJy / sr` | aynı |
| `FLAGS` | int32, bit tanımları `MP_<AD>` biçiminde | int32, bit tanımları `MSKNnnnn/MSKMnnnn/MSKDnnnn` biçiminde |
| `VARIANCE` | float32, (MJy/sr)² | aynı |
| `ZODI` | float32, MJy/sr, `ZODIMDL = ModifiedKelsallModelWithHPFT` | `ZODIMDL = KEL98_WAVESCL_V1` |
| `PSF` / `EPSF` | `PSF` görüntü küpü (101×101×121, 11×11 bölge, 10× aşırı örnekleme) | `EPSF` ikili tablo (D3 için 451 satır = 11×41 bölge; sütunlar BINX, BINY, XCENTER, YCENTER, XWIDTH, YWIDTH, NSTAR, NEFF_MEAN, CWAVE, CBAND, EPSF[33×33]) |
| `WCS-WAVE` | ikili tablo: X(13), Y(20), VALUES(2×13×20) | X(9), Y(14), VALUES(252); kesite göre uyarlanmış |

IMAGE başlığındaki önemli anahtarlar: `DATE-OBS`, `MJD-OBS`, `MJD-AVG`, `XPOSURE` 113.58 s, `DETECTOR`, `OBSID`, `SPS_EPA` (0 / 180, hangi taramaya ait olduğunu gösteriyor), `PSF_FWHM` (QR2 D4 6,10″; R7 D3 7,45″), `OMEGA_MEDIAN` (≈37,9 arcsec², piksel katı açısı), `CRPIX1A/2A` (kesitten özgün dedektör pikseline kayma), `DETCOORD = sky` (MWIR pikselleri X'te çevrilmiş), `L2DQAFLG`, `PXSRCMSK`, `FINAST`, tüm `L2 N_*` sayaçları, uzay aracı konumu ve hızı (HIERARCH).

### 4.4 M31 kesitinde okunan değerler (QR2, D4, 2025-07-09)
- Kesitteki λ aralığı **2,426–2,449 µm**, bant genişliği 0,045–0,061 µm. Gradyan y yönünde yaklaşık **0,00037 µm/piksel**, x yönünde 0,00003 µm/piksel.
  - Sonuç: 0,1°'lik (58 px) bir kesit yaklaşık 0,02 µm'lik bir λ aralığını kapsıyor. Bu, bant genişliğinin yaklaşık yarısı. 0,5°'lik (293 px) bir kesit yaklaşık 0,11 µm kapsar, yani kesit "tek renkli" değildir.
- IMAGE medyanı 14,49 MJy/sr, ZODI medyanı 0,096 MJy/sr (M31 çekirdeğinde ZODI/IMAGE ≈ %0,7). VARIANCE medyanı 0,0195 (σ ≈ 0,14 MJy/sr).
- FLAGS: bit 21 SOURCE 3364/3364 pikselde (%100), bit 0 TRANSIENT 9, bit 1 OVERFLOW 85, bit 2 SUR_ERROR 2, bit 6 NONFUNC 5, bit 17 PERSIST 9 pikselde.

### 4.5 AWS S3 açık kovası
- `https://nasa-irsa-spherex.s3.amazonaws.com/?list-type=2&delimiter=/&prefix=...` imzasız çalışıyor (AWS CLI gerekmiyor).
- Kök önekler: **`dr1/`, `qr2/`, `qr3/`**.
- `qr3/` altında: abs_gain_matrix, aurora_template, dark, dichroic, epsf, gain_factors, he_template, **l3_flux_corrections**, level2 (ilk dönem `2026W20_2A`), nonfunc_v2, nonlinear_pars, readnoise_pars, shuttle_glow_template, sip, solid_angle_pixel_map, spectral_channels, spectral_wcs, xtalk_class1/2, **zodi_scaling_v2**.
- ⚠ **`dr1/`:** aynı ürün yapısı, ayrıca **`hips5_cube/hips_20261026/`** (Norder5 HiPS küp dosyaları). `level2` 2025W17_4B'den 2026W20_1A'ya kadar uzanıyor.
  - Örnek: `dr1/level2/2025W28_1B/l2b-v27-2026-215/4/level2_2025W28_1B_0480_4D4_spx_l2b-v27-2026-215.fits`. Obs_id QR2 ile aynı, LastModified 2026-11-11T14:32:53Z, 65 MB.
  - `https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/` **404** veriyor, TAP'ta da DR1 koleksiyonu yok. Yani dosyalar yayına hazırlanıyor ama yayınlanmadı.
- `spectral_channels` ürünleri: QR2 `cal-sch-v1-2026-106` (Downloads'taki `spectral_channels_spx_cal-sch-v1-2026-106.fits.gz` bu), QR3 ve DR1 `cal-sch-v2-2026-229`.

### 4.6 HTTP Range ile kısmi okuma
- IBE: `Range: bytes=0-39999` → **206**, `content-range: bytes 0-39999/71634240`. S3 de 206 döndürüyor.
- Başlık yerleşimi (QR2 örneği): birincil HDU 2880 bayt, IMAGE başlığı 21.920. baytta bitiyor (ilk yaklaşık 23 KB yeterli).
- spectral_wcs kalibrasyon dosyasının sonundaki `WCS-WAVE` tablosu son 17 KB'tan okunabiliyor.
- **Deneme:** M31'i kapsayan 57 D4 pozlamasının hepsi için hedefteki λ, dosya indirilmeden **7,1 sn'de** hesaplandı (8 iş parçacığı, DataLink + Range ile başlık okuma + önbelleğe alınmış WCS-WAVE).
- `l3_flux_corrections` başlığı Range ile okundu: `EXTNAME = 'L3_FLUX_CORRECTIONS'`, `COMMENT Multiplicative flux correction factor for pre-QR3 data`, 2040×2040 float32, boyutsuz.

### 4.7 Zaman ve kanal fizibilitesi (M31, D4)
Hedefteki λ, SIP'siz WCS-WAVE ile hesaplandı:

| Ziyaret | Pozlama sayısı | `SPS_EPA` | Koleksiyon | M31'deki λ değerleri (µm) |
|---|---|---|---|---|
| E1 2025-07 | 19 | 0 | QR2 | 2.442, 2.499, 2.567, … 3.675, 3.775 |
| E2 2025-12 | 19 | 180 | QR2 | 2.426, 2.475, 2.542, … 3.691, 3.792 |
| E3 2026-07 | 19 | 0 | 18 QR2 + 1 QR3 | 2.420, 2.467, 2.533, … 3.630, 3.728 |

- Her ziyarette bantın tamamı yaklaşık 17–19 adımda taranıyor. Bir dalga boyu kanalı **ziyaret başına yaklaşık 1 kez** ölçülüyor (yılda 2 kez). Derin alanlarda çok daha sık.
- "Aynı kanal" eşleşmesi mümkün ama tam değil. En yakın eşler E2'de Δλ = −15,7 nm, E3'te −21,6 nm (bant genişliği 44–54 nm). Bunun nedeni Survey 3/4'ün bilerek yarım kanal kaydırılmış olması.
- ⚠ **SIP tuzağı:** astropy'nin SIP uyguladığı W-WCS ile SIP'siz hesap arasındaki fark −16,3 ile +0,2 nm arasında.
- Üç kesitte (0,1°, en yakın λ eşleri) hızlı bir karşılaştırma yapıldı. Hizalama en yakın komşu ile WCS üzerinden yapıldı.
  - E2 − E1: ham fark medyanı **+2,61 MJy/sr**, çekirdek (7×7) oranı **1,20**. E3 − E1: medyan −0,85, çekirdek oranı 0,93.
  - ΔZODI: E2−E1 −0,005, E3−E1 +0,0001 MJy/sr, yani M31'de ihmal edilebilir düzeyde.
  - **Yorum:** M31 çekirdeğinin 6 ayda %20 parlaması fiziksel olarak beklenmez. Fark büyük olasılıkla Δλ, boru hattı sürümü (6.4 → 6.5.4), dedektör konumu (x = 677 → 1759), PSF ve maske farklarından kaynaklanıyor. **Ham fark görüntüsü yanlış "değişim" izlenimi verir.** Normalleştirme ve uyarılar zorunlu.
- Maskelenen ("kötü") piksel oranı E1'de %0,3, E2'de %1,2, E3'te %15,5 (6.5.7 sürümünün yeni bayrakları). SOURCE bayrağı üç kesitte de %100. Genişletilmiş cisimlerde arka plan, kaynak içermeyen pikselden kestirilemiyor.

### 4.8 Hareketli cisimler
- **MOST:** `POST https://irsa.ipac.caltech.edu/cgi-bin/MOST/nph-most`, multipart alanlar `catalog=spherex`, `input_type=name_input`, `obj_name=C/2025 N1`, `obs_begin=2025-08-01`, `obs_end=2025-08-16`, `output_mode=VOTable`. Sonuç: 222 eşleşen kare, 2,9 sn.
  - Sütunlar: ra_obj, dec_obj, sun_dist, geo_dist, phase, vmag, observationid, planeid, productid, mjd_start, mjd_end, exposure_time, ra1..dec4, `uri` ve diğerleri.
  - Diğer giriş türleri: NAIF ID, MPC satırı, elle yörünge elemanları. Çıktı türleri: Regular, Full, Brief, VOTable, Gator.
- **3I/ATLAS tablosu:** `https://irsa.ipac.caltech.edu/data/SPHEREx/docs/comet3iatlas/obscore_3I_Atlas.vot` → 259 satır, tamamı QR2. Tarihler 2025-08-01…08-15 ve 2025-12-08…12-14.
  - Sütunlar arasında `comet_ra`, `comet_dec` (pozlama başına öngörülen konum), `spherex_detector`, `access_url` (DataLink) var.
  - IRSA notu: düşük S/N. Cisim genişletilmiş olduğu için Spectrophotometry Tool **önerilmiyor**.
- **2026-11-13 yeniden doğrulama (DR1 sonrası):**
  - MOST artık **DR1** karelerini döndürüyor: `obj_name=2025 N1`, 2025-05-01 → bugün, **364 kare** (tamamı `dr1`, `uri` = `ibe/data/spherex/dr1/level2/...`), 6,6 sn. Dönemler: 2025-08-01…08-15, 2025-12-08…12-15, 2026-03-17…04-06. QR3 karesi yok.
  - İkinci tablo 6 saatlik efemeris: `JD, Date, RA_obs, Dec_obs, ObsDist, GeoDist, HelioDist, Phase, Vmag`.
  - **Ad biçimi:** `obj_name` için JPL SBDB'nin `des` alanı kullanılmalı. `Ceres` → 400 "Multiple matches", `2P/Encke` → 400 "HORIZONS name lookup failed", `C/2025 N1 (ATLAS)` ve `1 Ceres` → 400. Çalışanlar: `1`, `433`, `2P`, `C/2025 N1`, `2025 N1`.
  - MOST bitiş tarihini kendisi kırpıyor (`user_input_end_time` 2026-10-16 döndü).
  - Eşleşme olmayınca da 200 + VOTable döner (kare tablosu boş).
- **2026-11-14 doğrulama (DR1 resmî duyurusundan sonra, önbellek atlanarak doğrudan IRSA'ya):**
  - `2025 N1` (3I/ATLAS), 2025-05-01 → 2026-11-14: **364 DR1 karesi**, QR3 0, QR2 0 (6,3 sn). QR3 döneminde (2026-05-14 → 10-05) cisim SPHEREx karelerine düşmüyor.
  - `433` (Eros): **916 DR1 + 38 QR3** karesi (15 sn) → MOST hem DR1'i hem QR3'ü döndürüyor; QR2 hiç dönmüyor.
  - Sonuç: MOST tarafında not/uyarı gerekmiyor; durum çubuğuna ek not eklenmedi.

### 4.9 DR1 duyurusu (2026-11-14 kontrolü)
- IRSA DR1 sayfası: https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_dr1.html — "IRSA released SPHEREx Data Release 1 (DR1) in November 2026". DOI: **10.26131/IRSA678** (DR1 Spectral Images), **10.26131/IRSA679** (Spectral All-Sky Cube).
- TAP `spherex.obscore` (175 sn süren tek sorgu): `spherex_dr1` **945 725** görüntü, ilk 2025-04-24 18:01, son **2026-05-14 11:47 UTC**; `spherex_qr3` **362 124** görüntü, 2026-05-14 12:08 → **2026-10-05 00:01 UTC**; `spherex_qr2` TAP'ta yok.
- SIA2 (Barnard konumu, 0,001°): `spherex_dr1` 240, `spherex_qr3` 123, `spherex_qr2` 0 satır. Derin alan (kuzey ekliptik kutbu, 0,01°): `spherex_dr1_deep` 20 901, `spherex_qr3_deep` 7 898.
- `tools/check_release.py dr1`: dosya düzeni QR3 (R7) ile aynı (VERSION 7.0.5, 7 uzantı, MSK bayrakları, 22 bayrak); M31 −1,6 ± 4,2 % (değişim yok ✓); Barnard (DR1 içi, 202 gün) 0,64 px uyumsuz — bilinen doymuş çekirdek / ağırlık merkezi sorunu (PROGRESS bilinen sorun 2).
- `releases.toml`: DR1 `announced = true`, "duyuru bekleniyor" notu kaldırıldı, `doi`, `deep_collections = ["spherex_dr1_deep"]`. Varsayılan DR1; QR2 `superseded` (yeni aramalarda kullanılmaz).

### 4.10 Canlı konum, spektrum ve arşiv güncelliği (2026-11-14 canlı denemeler)
- **JPL Horizons API** `GET https://ssd.jpl.nasa.gov/api/horizons.api?format=json`, `EPHEM_TYPE='OBSERVER'`, `CENTER='coord@399'` + `COORD_TYPE='GEODETIC'` + `SITE_COORD='boylam,enlem,km'` (şehir) ya da `CENTER='500@399'` (yer merkezli), `QUANTITIES='1,4,9,20'`, `ANG_FORMAT='DEG'`, `CSV_FORMAT='YES'` → 1,3 sn. Sütunlar: `R.A._(ICRF)`, `DEC_(ICRF)`, `Azi_(a-app)`, `Elev_(a-app)`, kuyruklu yıldızda `T-mag`/`N-mag`, asteroitte `APmag`/`S-brt`, `delta`, `deldot`. 3I/ATLAS Ankara'dan 07:00 UTC'de 16,1° yükseklikte, T-mag 25,8, Δ 12,7 AU.
- **COMMAND biçimi (önemli):** numaralı asteroit `'433;'` (Eros). `'DES=433;'` **başka bir cisim** döndürüyor. Kuyruklu yıldızlar `'DES=1P;CAP;'`, `'DES=2P;CAP;'`, `'DES=2025 N1;CAP;'`; `CAP` olmadan 30–61 görünme kaydı listeleniyor. Geçici asteroit tanımında `CAP` hata veriyor: `'DES=2024 YR4;'` doğru, `'DES=2024 YR4;CAP;'` yanlış. Kod önce `CAP`, olmazsa `CAP`'siz dener.
- **Wikidata şehir koordinatları:** `wbsearchentities` ilk sonucu bazen ili veriyor (Erzurum → il, Q376797) ve art arda isteklerde 429 dönüyor. Tek SPARQL sorgusu (`query.wikidata.org`, yalnızca yerel araç `tools/cities_from_wikidata.py`; sunucu çağırmaz): Türkçe etiket + `P17=Q43` + P625 + P1082, il (Q48336) hariç, en kalabalık nesne → 24 şehir, `config/cities_tr.json` (QID'lerle).
- **IRSA TAP en yeni gözlem:** `SELECT TOP 1 t_min … ORDER BY t_min DESC` koleksiyon başına 105 sn ile 120 sn'den uzun sürüyor. Bu yüzden sunucu arka planda açılışta ve 12 saatte bir okuyor (`services/freshness.py`). Canlı sonuç: QR3 en yeni 2026-10-05 00:01 UTC, DR1 2026-05-14 11:47 UTC.
- **R7 L2 dosya düzeni (spektrum için Range):** PRIMARY, sıkıştırılmamış IMAGE (float32 2040×2040), **FLAGS `BINTABLE` + `ZIMAGE`, `RICE_1`, `ZTILE` 2040×1** (satır başına bir döşeme; tanımlayıcı `1PB`, yığın `PCOUNT` ≈ 12,3 MB), sıkıştırılmamış VARIANCE ve ZODI, EPSF, WCS-WAVE; dosya 66,2 MB. Hedefin ±8 satırı IMAGE ve VARIANCE'tan Range ile, FLAGS'ten tanımlayıcı + yığın parçası olarak okunur ve astropy `Rice1` ile açılır. Aynı pozlamada kesit tabanlı fotometriyle oran 1,0000 (Luhman 16 D6) ve 1,02 (WISE 0855, 0,02σ). Tam ziyaret (132 pozlama) yerelde 145 sn, canlıda 116 sn.

---

## 5. FLAGS — tanımlar ve önerilen maskeler (Supplement v2.0, Tablo 16 ve §3.3)

| Bit | Ad | Not |
|---|---|---|
| 0 | TRANSIENT | kozmik ışın vb. (ilk 10 sn kaçabilir) |
| 1 | OVERFLOW | doyumun yaklaşık yarısı |
| 2 | SUR_ERROR | |
| 4 / 5 | PHANTOM / REFERENCE | yalnızca QR2 başlığında |
| 6 | NONFUNC | hiçbir amaçla kullanılamaz |
| 7 | DICHROIC | bant 3/4 köşeleri, düşük verim |
| 9 | MISSING_DATA | |
| 10 / 11 | HOT / COLD | bilimde kullanılamaz |
| 12 | FULLSAMPLE | **yalnızca bilgi** |
| 14 | PHANMISS | |
| 15 | NONLINEAR | |
| 17 | PERSIST | |
| 19 | OUTLIER | |
| 20 | CROSSTALK | R7 |
| 21 | SOURCE | **bilgi bayrağı (bilinen kaynak)** |
| 22–24 | GHOST, GHOST_FPA, GHOST_EXT | 6.5.x ve R7 |
| 25 | STREAK | R7 |
| 26–28 | BLOOM, SNOWBALL, HALO | 6.5.3 ve sonrası, R7 |
| 29 | SATELLITE_HALO | Supplement'te var, test ettiğimiz R7 kesit başlığında yok |

- **Fotometri maskesi (Supplement önerisi):** SUR_ERROR, NONFUNC, MISSING_DATA, HOT, COLD, NONLINEAR, PERSIST, BLOOM, SNOWBALL, HALO, SATELLITE_HALO.
- **Arka plan kestirimi maskesi:** yukarıdakiler artı OVERFLOW, OUTLIER, SOURCE, TRANSIENT.
- **Mozaik aracının "kötü piksel" listesi:** TRANSIENT, SUR_ERROR, NONFUNC, DICHROIC, MISSING_DATA, HOT, COLD, PHANMISS, NONLINEAR, PERSIST, CROSSTALK, GHOST*, STREAK, BLOOM, SNOWBALL, HALO, SATELLITE_HALO. OVERFLOW, SOURCE ve OUTLIER yalnızca aktarılıyor, maskelenmiyor.
- Supplement §3.4.10: 2025W51_1A'dan (Aralık 2025) önceki QR2 görüntülerinde snowball, bloom ve halo maskesi **yok**. QR2'de crosstalk ve uydu izi maskesi eksik.

---

## 6. ZODI — Explanatory Supplement özeti (karar öncesi)

Kaynak: *SPHEREx Explanatory Supplement* v2.0 (SSDC-DP-017, 2026-08-25), §2.2, §3.2.11, §3.3, §3.4.3, §4.3.4. PDF yerel olarak (yalnızca standart kütüphaneyle) metne çevrilip okundu.

1. **Çıkarılmamış.** "Importantly, this ZL median signal is not subtracted from the LVF images." (§3.2.11). §2.2: "no zodiacal light subtraction is applied, each file includes an estimated background level".
2. **Model:** Değiştirilmiş Kelsall (1998) modeli (Planck verisiyle güncellenmiş) + Tsumura (2013) tayfı. Uzamsal ve zamansal değişimi iyi yakalıyor, ama **genliği tipik olarak olduğundan düşük tahmin ediyor**. R7'de |b| > 30° olan Yıl 1 pozlamalarından türetilmiş, dalga boyuna bağlı bir ölçek çarpanı uygulanıyor. Bu çarpan `zodi_scaling_v2` ürünü olarak da yayınlanıyor.
3. **IRSA'nın kendi kullanımı:**
   - Mozaik aracı: `data = IMAGE − ZODI`, ardından kötü pikselleri maskeliyor (§3.4.3).
   - Fotometri aracı (Tractor): ZODI'yi değil, görüntü başına küresel bir arka planı ve yerel bir arka plan bileşenini akılarla birlikte uyduruyor (§3.3).
4. **Zaman boyutu:** ZL gözlem geometrisiyle (güneş elongasyonu) değişiyor, dolayısıyla dönemler arasında farklı. M31'de (β ≈ 32°, 2,43 µm) ölçülen ΔZODI ≈ 0,005 MJy/sr, yani küçük. Düşük ekliptik enlemlerde ve sönük hedeflerde önemli olabilir.
5. **Aynı zamanda değişen ve çıkarılmamış diğer sinyaller:** atmosferik He 1,083 µm çizgisi (ZL'nin 30 katına kadar; bant 1 ve 2), aurora çizgileri, 0,78–4,64 µm arasındaki diğer hava parlaması çizgileri, shuttle glow (yaklaşık 2,9 µm ve 4,5 µm). Bunlar **zaman içinde değişir** ve sahte "değişim" üretebilir.

**Önerim** (onayınıza bağlı, ARCHITECTURE.md §6.3):
- Görselleştirme ve fark görüntüleri için varsayılan `IMAGE − ZODI` olsun, ham görünüm de seçilebilsin.
- Fark görüntüsünden önce her dönemden ayrıca sağlam bir yerel arka plan çıkarılsın. Gerekçe: QR2 modeli genliği düşük tahmin ediyor ve atmosferik çizgiler var.
- Açıklık fotometrisinde halka (annulus) ile yerel arka plan kullanılsın. Bu yöntem ZODI'yi zaten götürür. Yöntem arayüzde açıklansın.

---

## 7. Sürümler, boru hatları ve tarama yapısı (Supplement §1.4, §2.1, Tablo 4)

- **QR1:** Şubat 2026'da emekliye ayrıldı, IRSA'da yok (DOI 10.26131/IRSA629).
- **QR2:** Ekim 2025'ten itibaren, 6.4 → 6.5.6 boru hatları (gözlemlediğimiz verilerde 6.5.7 de var), DOI **10.26131/IRSA652**. Nisan 2026'da PSF başlık düzeltmesi yapıldı (`+psffix1`). QR1 ile birleştirilmemeli.
- **QR3:** Survey 3/4 verisi, R7 (7.0–7.2) boru hattı, DOI **10.26131/IRSA662**. 16 Mayıs – 19 Temmuz 2026 arasındaki ilk haftalar önce 6.5.6 ile işlendi. Bunların R7 sürümleri DR1 ile birlikte yayınlanacak. "We advise caution when combining QR2 and QR3 data."
- **DR1:** Survey 1+2'nin R7 ile yeniden işlenmiş hali, ayrıca tüm gökyüzü ürünleri (HiPS küp). **DR2:** dört taramanın tamamı.
- **Taramalar:** Survey 1/2, ilk 12,5 ayda PA = 0°/180°. Survey 3/4, ikinci 12,5 ayda. Survey 3/4, 1/2'ye göre **yarım kanal (6′)** kaydırılmış. Survey numarası `SPS_EPA` ve tarihten bulunabiliyor.
- **Kanallar:** Dedektör başına 17 kanal (1–17; 0 ve 18 kanal dışı), toplam 6 × 17 = 102. `spectral_channels` ürünü her kanal için medyan λ, WL_MIN/MAX, R ve bant genişliği tablosu içeriyor.
- **Dalga boyu doğruluğu:** WCS-WAVE yaklaşık 1 nm hassasiyetle görselleştirme için. Bilimsel analizde `spectral_wcs` ürünündeki `CWAVE`/`CBAND` haritaları (2040², sürüme özgü) kullanılmalı.
- **Fotometri belirsizliği:** IRSA aracı σ² = σ²_stat + (0,03·F)² uyguluyor (%3 sistematik).

---

## 8. Hubble ve Webb (MAST)

Test: `astroquery.mast.Observations.query_criteria(coordinates=..., radius=2′, obs_collection='HST'|'JWST', dataproduct_type='image', intentType='science')`

| Hedef | HST (satır / önizlemeli) | JWST (satır / herkese açık / önizlemeli) | Süre |
|---|---|---|---|
| M31 çekirdeği | 774 / 676 | 24 / 24 / **0** (NIRCam) | 8,6 sn / 21,7 sn |
| Orion (M42) | 1827 / 1625 | 287 / **71** / 71 | **83,6 sn** / 17,9 sn |
| (150.0, −60.5) alanı | 0 | 0 | 7,2 sn / 5,8 sn |

- `jpegURL` biçimi `mast:HST/product/x13o1101t_c0f.jpg`. İndirme adresi `https://mast.stsci.edu/api/v0.1/Download/file?uri=<uri>` → 200, 28,5 KB JPEG.
- **Özel (proprietary) kayıtlar var** (Orion JWST'de 287'nin yalnızca 71'i herkese açık). `dataRights == 'PUBLIC'` süzgeci şart.
- ⚠ `MastMissions(mission='jwst').query_region(M31)` 0 satır döndürdü, oysa CAOM 24 satır buldu. CAOM `Observations` yolu kullanılmalı.
- CAOM SIA2 (`archive.stsci.edu/vo/`) **test edilmedi.**
- Gecikme yüksek: Orion HST sorgusu 84 sn sürdü. Eşzamansız sorgu, zaman aşımı ve 24 saatlik önbellek gerekli.

---

## 9. Atıf ve teşekkür metinleri

- **SPHEREx** (IRSA ve Supplement §1.6): "This publication makes use of data products from the Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory and the California Institute of Technology, and is funded by the National Aeronautics and Space Administration."
  - DOI'ler: QR2 10.26131/IRSA652, QR3 10.26131/IRSA662 (QR1 10.26131/IRSA629).
- **AWS kaydı** (`https://registry.opendata.aws/spherex-qr/`): "SPHEREx Quick Release (QR): An All-Sky Spectral Survey was accessed on DATE from https://registry.opendata.aws/spherex-qr." ⚠ Bu sayfa yalnızca QR1/QR2 DOI'lerini listeliyor, güncel değil.
- **IRSA:** "This research has made use of the NASA/IPAC Infrared Science Archive, which is funded by the National Aeronautics and Space Administration and operated by the California Institute of Technology."
- **HST (MAST):** "…NASA/ESA Hubble Space Telescope obtained from the Space Telescope Science Institute, which is operated by the Association of Universities for Research in Astronomy, Inc., under NASA contract NAS5–26555…"
- **JWST (MAST):** "…NASA/ESA/CSA James Webb Space Telescope. The data were obtained from the Mikulski Archive for Space Telescopes at the Space Telescope Science Institute, which is operated by the Association of Universities for Research in Astronomy, Inc., under NASA contract NAS5-03127 for JWST…"
- **CDS (SIMBAD/Sesame):** Metin SIMBAD kesintisi nedeniyle canlı doğrulanamadı. Faz 10'da doğrulanacak.

---

## 10. E-posta (Faz 9 için ön bilgi)

- EmailJS REST: `POST https://api.emailjs.com/api/v1.0/email/send`, isteğe bağlı `accessToken` parametresi (hesabın özel anahtarı), hız sınırı saniyede 1 istek.
- Ücretsiz planda **ayda 200 istek ve 2 şablon** var (fiyat sayfasında doğrulandı).
- "Tarayıcı dışı uygulamalardan API'ye izin ver" hesap ayarının ayrıntısı **doğrulanmadı.** Faz 9 başında seçeneklerle birlikte doğrulanacak.

---

## 10b. Otomatik öneri için canlı ölçümler (2026-11-13)

- **SIMBAD TAP:** Strasbourg `https://simbad.cds.unistra.fr/simbad/sim-tap/sync` → **404** (HTML). Kod sıradaki aynaya (CfA) geçiyor. CfA `ident` önek sorguları ~0,5–2 sn sürüyor, bazıları 15 sn'yi aşıyor (`hd 209458`).
- CfA'da `lower()` desteklenmiyor (400), `ILIKE` de yok. Büyük/küçük harf için `LIKE` varyantları kullanılıyor.
- SIMBAD katalog numaralarını boşlukla dolduruyor (`M   3`, `NGC  1976`). Bu yüzden `m3` → `'M %3%'` kalıbı kullanılıyor: `M   3` ve `M  31` eşleşir, `MSX …`, `MCC 31`, `MZ 350` eşleşmez.
- `TOP N` sonucu rastgele bir alt küme; kısa katalog adları her zaman listeye girmeyebilir. Bu yüzden öneride tam ad için **Sesame (yalnızca SIMBAD, `-oxp/S`)** de soruluyor. `SNV`, bilinmeyen adlarda NED/VizieR'i de denediği için yavaş ve gürültülü ("barnard" → NED'den bir galaksi).
- **JPL SBDB:** kısmi adlarda 300 + `list` döner ("halley" → `2688 Halley (1982 HG1)`, `1P/Halley`). Ancak `sstr=1P/Halley` ve `sstr=Halley` bulunamıyor; `1P`, `2P`, sayı (`2688`) ve `C/2017 D3` çalışıyor.

## 10d. CADC SSOIS (2026-11-14 canlı denemeler)
- **Uç nokta:** `https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/cadcbin/ssos/ssosclf.pl`. API sayfasındaki örnek adres boş; formun `results.js` dosyası bu yolu çağırıyor. Daha önce varsayılan `/cadcbin/ssos/ssos.pl` → **404**.
- **Parametreler:** `lang=en&object=<AD>&search=bynameCADC&epoch1=1990-01-01&epoch2=<bugün>&eellipse=&eunits=arcseconds&extres=no&xyres=no&format=tsv`. `eunits` yalnızca `arcseconds`/`arcminutes` kabul ediyor; `bary` → **HTTP 500**.
- **Kapsam:** `bynameCADC`, MPCORB.DAT kullanıyor. CADC'nin kendi mesajı: "this file does not contain planets, planetary satellites, or comets".
  - Çalışanlar (asteroit): `EROS`, `433`, `CERES`, `1`, `2024 YR4`, `99942`.
  - Bulunamayanlar: `C/2025 N1` ("C/2025+N1" olarak ayrıştırıldı), `2025 N1`, `3I`, `3I/ATLAS`, `ATLAS`, `1P`.
  - `HALLEY` adı 2688 Halley asteroidini bulmuş olabilir; bu yüzden SBDB tanımı kullanılıyor.
  - Kuyruklu yıldızlar (SBDB `kind` cn/cu) **sorgulanmıyor**, "kapsam dışı" gösteriliyor. `bynameHorizons`/`bynameMPC` API sayfasının isteğiyle kullanılmıyor.
- **TSV:** `Image, MJD, Filter, Exptime, Object_RA, Object_Dec, Image_target, Telescope/Instrument, Datalink`.
  - Bulunamayınca aynı yanıt türünde HTML mesajı dönüyor.
  - Büyük yanıtlar: Eros 7 283 satır (1,2 MB, 7 sn); 99942 Apophis 15 027 satır (aralarında 300 NEOSSat karesi).
  - Yalnızca özet saklanıyor (toplam, alet dağılımı, ilk/son tarih, en yeni 50).
  - `Datalink` bazen `http://` (CASU), bazen boş. Yalnızca `https` bağlantı olarak gösteriliyor.

## 10c. Gaia DR3, ESA arşivi TAP (2026-11-14 canlı denemeler)
- `https://gea.esac.esa.int/tap-server/tap`, pyvo `TAPService.run_sync`, tablo `gaiadr3.gaia_source`. Kullanılan sütunlar: `source_id, ra, dec, ra_error, dec_error, parallax, parallax_error, pmra, pmdec, phot_g_mean_mag, ruwe, astrometric_params_solved`. Konumlar J2016.0. astroquery kullanılmıyor.
- **Hız:** 0,0707°'lik koni + `G < 19`, `TOP 500` → Barnard 424 satır 2,4 sn; M31 100 satır 1,9 sn. `COUNT(*)` 1,4 sn.
- **Kesilme:** Galaksi düzlemine yakın alanlarda 500 satır yetmiyor (Luhman 16: gerçekte 709–716 kaynak). Hedef ve yoğunluk bu yüzden ayrı sorgulardan geliyor: 15″'lik, parlaklık sınırsız koni ve `COUNT(*)`.
- **Eksik astrometri:** Luhman 16 = Gaia DR3 5353626573555863424, G 16,92, `astrometric_params_solved = 3` (yalnızca konum; öz hareket ve paralaks yok). Bu kayıtta beklenen konum "veri yok" olarak kalıyor, 0 yapılmıyor. Eşleştirme Gaia'nın kendi döneminde (J2016.0, SIMBAD konumu taşınarak) yapılıyor: ayrım 0,71″.
- **Barnard:** 4472832130942575872, ϖ 546,98 mas. Öz hareket + yıllık paralaksla beklenen kayma (DR1 2025-08 → QR3 2026-09) 11,07″; ölçülen 12,50″, fark 0,23 piksel. A'da ölçülen ağırlık merkezi Gaia beklentisine 2,39″ (0,39 piksel) uzaklıkta. Alan yoğunluğuyla 6,15″ içinde tesadüfi kaynak olasılığı %22, gözlenen ayrımda (0,003″) ~0.

## 11. Doğrulanmamış / açık kalanlar
- SIMBAD Strasbourg'un ne zaman geri döneceği. Teşekkür metni.
- CAOM SIA2 (MAST).
- IRSA Spectrophotometry Tool'un programatik API'si var mı?
- Kesit servisinde PSF/EPSF'yi dışarıda bırakan bir parametre var mı? Belgelerde yok.
- ~~DR1'in resmî yayın tarihi, TAP koleksiyon adı ve DOI'si.~~ 2026-11-14: Kasım 2026'da duyuruldu, `spherex_dr1` / `spherex_dr1_deep`, DOI 10.26131/IRSA678 (§4.9). IRSA sayfası gün vermiyor ("November 2026"); yayın tarihi 12 Kasım 2026 SPHEREx duyurusundan (IRSA'ya atfedilmez).
- `CWAVE` haritasıyla WCS-WAVE arasındaki fark ve MWIR'deki X çevirme yönü. Faz 2'de doğrulanacak.
- Derin alan koleksiyonlarının TAP'ta nasıl göründüğü. Faz 3'te bakılacak.

---

## 12. NEOSSat (planlandı — DECISIONS.md §4e madde p)

**Durum:** Yalnızca belge. Arama uç noktası (CADC CAOM/TAP, koleksiyon `NEOSSAT`) **henüz canlı denenmedi**; kod yok.

**Kaynaklar** (2026-11-13'te okundu):
- CADC NEOSSat sayfası: <https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/neossat/>. Ürün tablosu ve teşekkür metni burada; metin [`SOURCES.md`](SOURCES.md)'de aynen var.
- *NEOSSat FITS Image User's Guide*, **CSA-NEOSSAT-MAN-0002 v4.00** (PDF, 33 sayfa; CADC sayfasındaki bağlantıdan indirildi, yalnızca standart kütüphaneyle metne çevrildi).
- Lisans: Open Government Licence – Canada.

**Ürün seçimi** (CADC ürün tablosu)

| Ürün | Dosya | İçerik | Kullanım |
|---|---|---|---|
| CORD | `*_cord.fits.gz` | kırpma + overscan düzeltmesi + karanlık çıkarma (`DARK_###` başlıkları) | **1. tercih** |
| COR | `*_cor.fits.gz` | kırpma + overscan düzeltmesi | CORD yoksa |
| RAW | `*.fits`, `*.fits.gz` | işlenmemiş, overscan dahil | ikisi de yoksa, **uyarıyla** |
| CLEAN | `*_clean.fits` | eski CSA yazılımı, kırpma yok | **kullanılmaz** |

**Geometri** (kılavuz)
- Piksel ölçeği **2,997″/piksel (binning'siz)**. Binning varsa `XBINNING` / `YBINNING` ile çarpılır.
- Görüş alanı: "The field of view within the 1024 x 1024 area … is **0.86 degrees**." (CADC sayfası yuvarlak olarak "3″/pixel, 0,85°" diyor; kılavuzdaki değerler kullanılır.)
- Teleskop açıklığı gibi kılavuzda doğrulamadığımız değerler sitede yazılmaz.

**WCS**
- Kılavuzdaki WCS alanları: `WCSNAME` (sabit `celestial`), `WCSAXES`, `CRPIX`, `CTYPE`, `CUNIT`, `CDELT`, `CRVAL`, `CROTA2`, `CDx_y`. Başlık tablosunda `CRTYPE1` adı da geçiyor; bu yüzden **`CTYPE1` ve `CRTYPE1` ikisi de denenecek**, ölçek ve dönme için **CD matrisi** kullanılacak.
- WCS başlığı uzay aracının yönelim tahminlerine dayanıyor: `CRVAL1`/`CRVAL2` için kılavuzda "Right Ascension / Declination of reference pixel, **based on spacecraft ACS estimates**" yazıyor. Ayrı bir yıldız çözümü (plate solution) belirtilmiyor, dolayısıyla konum doğruluğu sınırlı olabilir. Arayüzde her durumda "**konum doğruluğu sınırlı**" notu gösterilecek. (İlk okumada bu cümle PDF metninde satırlara bölündüğü için gözden kaçmıştı; 2026-11-13'te düzeltildi.)

**Kare süzgeci** (kılavuzdaki başlık anahtarları)
- `OBSTYPE = OBJECT`.
- `SHUTTER` açık ("Shutter status (OPEN or CLOSED)").
- `DETECTOR = Science` ("Science or Star Tracker").
- `MODE` = `16 - FINE_POINT` ("stabilized relative to fixed stars") veya `14 - FINE_SLEW` ("slewing to track a moving object").
- `N_SUBIMG > 0` ve `PKT_SEQ` anomalisi olan kareler (paket sırası sayacı kesintili) elenir ya da uyarıyla gösterilir.
- **FINE_SLEW**'de yıldızlar çizgi olur. Hız `RA_VEL`, `DEC_VEL` (ve `ROL_VEL`) ile gösterilir.

**Bilimsel sınır**
- `FILTER = 'CLEAR'` (filtresiz optik). SPHEREx ile **parlaklık karşılaştırması yapılmaz**; yalnızca konum, hareket ve zaman. Arayüzde açıkça yazılır.

**Erişim**
- Arama yalnızca CADC üzerinden yapılır (koleksiyon `NEOSSAT`). `data.asc-csa.gc.ca` ham dizini **taranmaz**.
