# Yeni veri geldiğinde (QR4, DR2, …)

Yeni bir SPHEREx sürümü **kod değiştirmeden**, yalnızca `config/releases.toml` ile eklenir (DECISIONS §1). Örnek uygulama: DR1, 2026-11-14 (DATA_SOURCES §4.9).

1. **Canlı kontrol** (proje kökünden):
   `backend\.venv\Scripts\python.exe tools\check_release.py <id> --out %TEMP%\rapor.md`
   - TAP ve SIA2'de koleksiyon cevap veriyor mu, S3 klasörü var mı?
   - Örnek karenin uzantıları ve bayrak biçimi bilinen düzenle (R6 = QR2, R7 = QR3/DR1) aynı mı?
   - M31 / Barnard demo karşılaştırmaları ne veriyor?
   - Düzen farklıysa durun: önce kodun okuyabildiğinden emin olun (örn. R7'de FLAGS sıkıştırılmış; `services/spectrum.py`).
2. **`releases.toml`'a blok ekleyin** (mevcut bloğu kopyalayın):
   - `id`, `label`, `status = "staged"` (önce yalnızca yerelde deneyin), `calib_family`, `sia_collections`, `deep_collections`, `ibe_prefix`, `s3_prefix`.
   - `doi` (bilinmiyorsa `""`, uydurmayın), `announced = false` + `notice` (resmî duyuru yoksa).
   - Yerine geçtiği sürüm varsa `supersedes`.
3. **Yerelde deneyin:** `status = "active"` yapın, sunucuyu başlatın, bir cisim arayın; ziyaretler, kesit, karşılaştırma ve spektrum çalışmalı. Testler: `pytest` (`test_app.py` sürüm listesini denetler; gerekiyorsa güncelleyin).
4. **Varsayılanı ve eskiyi ayarlayın:**
   - `default_release`'i yeni sürüme alın.
   - Yerine geçilen sürüm `status = "superseded"` olsun (önbelleği okunur, yeni aramada kullanılmaz).
   - Farklı kalibrasyon ailesiyse arayüz otomatik uyarı verir.
5. **Duyuru gelince:**
   - `announced = true` yapıp `notice`'i silin.
   - DOI'yi IRSA sayfasından ekleyin.
   - `config/attributions.toml` → `dois` alanına ekleyin; `tools\gen_sources_md.py` çıktısıyla `docs/SOURCES.md`'yi eşitleyin.
   - Yayın tarihini kaynağıyla yazın.
6. **Commit + push.** Render canlıya geçince:
   - Önbellek yayınla birlikte silinir. Gerekirse admin panelindeki "Veri sürümleri → Önbelleği yenile" ile sürüm sürüm de silinebilir.
   - `tools\prewarm.py --base https://spherex-izleyici.onrender.com --only <cisim>` komutunu cisim cisim çalıştırın (barnard, wise0855, luhman16, 3i_atlas).
   - `/api/v1/health` ve durum çubuğunu kontrol edin. Arşivdeki en yeni gözlem tarihi IRSA TAP'tan otomatik okunur.
7. **Beklenmedik veri:** okunamayan bir kare tek başına "hata" sayılır, iş durmaz (spektrumda `error` sayacı). Sürüm tümden sorunluysa `status = "staged"` yapın; site önceki sürümlerle çalışmayı sürdürür.

Belgeler: `DATA_SOURCES.md` (canlı bulgular), `DECISIONS.md` §4c (DR1 geçişi), `DEPLOY.md` (yayın).
