# İlerleme durumu

> **Son güncelleme:** 2026-11-12 gece (oturum sonu) · **Son commit:** `f841f16` · Teslim: **15 Kasım 2026, 16:00**
> Kararlar ve talimatlar: [`DECISIONS.md`](DECISIONS.md) · Mimari: [`ARCHITECTURE.md`](ARCHITECTURE.md) · Veri kaynakları: [`DATA_SOURCES.md`](DATA_SOURCES.md) · Yayın: [`DEPLOY.md`](DEPLOY.md)

## Yarın ilk yapılacak 3 iş

1. **Yayın (GitHub + Render).** Kullanıcı GitHub'da depo açar, ardından `git remote add origin … && git push -u origin main` yapar ve Render'da Blueprint'i bağlar (`docs/DEPLOY.md`). Claude Docker derleme günlüğünü takip eder, hataları düzeltir ve canlı adreste `/api/v1/health` ile duman testi yapar. Docker bu makinede yok, imaj yerelde hiç derlenmedi.
2. **3I/ATLAS hareketli cisim görünümü (MOST).**
   - Arka uç: `providers/most.py` (`POST /cgi-bin/MOST/nph-most`, `catalog=spherex`, VOTable; doğrulanmış parametreler `DATA_SOURCES.md` §4.8'de) ve `GET /moving/{designation}/frames` (job + WS).
   - Ön uç: Güneş Sistemi hedefinde, cisme ortalanmış kare kare oynatma (zaman çizelgesi, hız, her karede konum ve tarih).
3. **Geri bildirim butonu + arama çubuğunda otomatik öneri** (§4d): yerel Türkçe ad listesi, SIMBAD ve JPL; 250 ms; klavye ve ARIA.

## Bitenler

| Alan | Durum |
|---|---|
| Faz 0 | Canlı doğrulama (`DATA_SOURCES.md`), mimari, kararlar, doğrulama betikleri (`tools/phase0_verify`) |
| Faz 1 iskeleti | FastAPI + React/Vite/TS/Tailwind, i18n (tr/en), koyu uzay teması, three.js Samanyolu (yoğunluk dalgası + diferansiyel dönüş), gizlilik bildirimi (KVKK), olay günlüğü (`event`), anonim oturum çerezi, IP hash'i, güvenlik başlıkları, Dockerfile + `render.yaml` |
| Veri katmanı | Koordinat ayrıştırıcı (tüm biçimler, 22 test); Sesame, SIMBAD (ayna listesi), JPL SBDB, Wikidata/Vikipedi; SIA2 kapsamı; HTTP Range ile hedefteki λ (SIP'siz); IRSA kesitleri; sürüme duyarlı bayrak şeması (MP_/MSKN); disk önbelleği |
| Zaman karşılaştırması | Hizalama, arka plan, göreli normalleştirme, fark ve σ haritası, kayma (px ve ″, yön), açıklık fotometrisi (+%3 sistematik), kanal eşleşmesi (S5), atmosferik çizgi ve sürüm uyarıları, QR2→QR3 akı düzeltmesi, öz hareketle hedef konumu; arayüzde yan yana, yanıp sönme, kaydırma ve fark görünümleri ile sonuç paneli; `?q=&d=&compare=1` paylaşılabilir bağlantı |
| Cisim–cisim karşılaştırması | `POST /compare/objects` + arayüz: aynı türden öneriler, farklı tür uyarısı, aynı kanal ve boyut, ortak/bağımsız ölçek, SIMBAD + SPHEREx (µJy, AB) tablosu |
| Bilgi paneli | SIMBAD + Vikipedi (önce tr, yoksa en), her satırda kaynak etiketi, "bilinmiyor" |
| Jobs + WS | Yavaş işler `job_id` döndürür; ilerleme `/ws` üzerinden, HTTP yoklaması her zaman yedek; istemci otomatik yeniden bağlanır |
| Sürümler | **DR1 + QR3 varsayılan**, QR2 `superseded` (`DECISIONS.md` §4c); `announced = false` iken "resmî duyuru bekleniyor" notu gösterilir |
| Araçlar | `tools/check_release.py <sürüm>` (DR1 raporu `DECISIONS.md` §4c'de) |
| Testler | Arka uç **52 geçti** (pytest), ruff temiz · Ön uç **7 geçti** (vitest), `tsc` temiz, ESLint 0 hata / 3 uyarı (fast-refresh) |

Commit'ler: `6c64a06` Faz 0 → `0a60c43` Faz 1 → `31f65ff` veri katmanı → `68375db` zaman karşılaştırması → `fe07311` arayüz → `bb9f1cc` DR1 + cisim karşılaştırması (arka uç) → `f841f16` cisim karşılaştırması arayüzü.

## Son test sonuçları (canlı veri)

**Barnard Yıldızı, D5, DR1 → QR3** (2025-08-25 → 2026-09-22, 393 gün, aynı tarama yönü)

| | Ölçülen | Beklenen (SIMBAD öz hareketi) |
|---|---|---|
| Kayma | **12,50″ (2,04 piksel)** | **11,18″ (1,82 piksel)** |
| Yön | 347° | ~356° |

- Fark **0,22 piksel**. Δλ = 5 nm (bant genişliğinin 0,14'ü), "aynı kanal".
- Sürüm uyarısı yok, çünkü iki görüntü de R7 kalibrasyonunda.
- Fotometri yapılamadı: çekirdek doymuş/maskeli (`NO_PHOTOMETRY`).

**WISE 0855 ile Luhman 16, D6** (cisim–cisim karşılaştırması)

| | WISE 0855 (DR1, 2025-11-14) | Luhman 16 (QR3, 2026-05-25) |
|---|---|---|
| λ | 4,736 µm | 4,740 µm (Δλ 3,9 nm, aynı kanal) |
| Akı | 562 ± 236 µJy (S/N 2,4 → düşük S/N uyarısı) | 150 047 ± 4 580 µJy |
| AB kadiri | **17,03** | **10,96** |

- Değerler WISE W2 parlaklıklarıyla tutarlı (yaklaşık AB 17,2 ve 10,9).
- Uyarı: farklı tür. SIMBAD Luhman 16'yı `**` (çift/çoklu sistem) olarak sınıflandırıyor; WISE 0855 ise `BD*`.

**`tools/check_release.py dr1`:** DR1 düzeni QR3 (R7) ile aynı ✓. M31 (DR1 içinde) −1,6 ± 4,2 %, değişim yok ✓. Barnard (DR1 içinde, zıt tarama yönleri) fark 0,64 piksel ✗; bkz. bilinen sorunlar.

## Bilinen sorunlar

1. **Site henüz yayında değil.** Git uzak sunucusu yok; Dockerfile yerelde test edilmedi (Docker kurulu değil).
2. **Ağırlık merkezi sapması (doymuş yıldızlar):** Barnard'da zıt tarama yönündeki dönemler arasında 0,64 piksel uyumsuzluk var. Doymuş/maskeli çekirdek ağırlık merkezini maskesiz tarafa çekiyor. Çözüm: cilalama E1 (doymuş çekirdeği dışlayan PSF uydurma).
3. **Parlak yıldızlarda fotometri yok:** D2 ve D5'te Barnard'ın çekirdeği doymuş, parlaklık farkı "ölçülemedi" olarak gösteriliyor (uydurma yok).
4. **Arayüz tarayıcıda uçtan uca doğrulanmadı.** Başsız Edge karşılaştırma sonucunu bekleyemedi (sanal saat); kullanıcı tarayıcıda kontrol edecek. API düzeyinde test edildi.
5. **IRSA yavaşlığı:** Bir cisim ve bant için ilk gözlem işi 30–60 sn, kesit 15–45 sn sürüyor; ara sıra 503 dönüyor (yeniden deneme var). `tools/prewarm.py` henüz yok.
6. **CDS Strasbourg'da SIMBAD kesintisi:** CfA aynası kullanılıyor; aynı-tür sorgusu yaklaşık 10 sn (24 saat önbellek). CfA aynası `ILIKE` desteklemiyor.
7. **Windows'ta `uvicorn --reload` takılıyor:** kod değişince sunucuyu elle yeniden başlatın.
8. **Cisim karşılaştırması uyarılarında "Dönem A/B" ifadesi** cisimler için de kullanılıyor; "Cisim A/B" olarak düzeltilmeli.
9. **DR1:** DOI ve derin alan koleksiyon adı henüz bilinmiyor. IRSA duyurunca `announced = true` yapılacak.
10. Vikipedi özeti ara sıra zaman aşımına uğruyor (8 sn). Panel "şu an erişilemeyen kaynak" diyor.
11. `docs/demo_reference.html` (asistan görünüm örneği) klasörde yok.
12. Samanyolu: merkezde küçük bir kare izi görüldü (yalnızca SwiftShader'da görülmüş olabilir); ince ayar cilalamaya bırakıldı.

## Bekleyen talimatlar (tam liste)

Kaynaklar: `DECISIONS.md` §2, §4b, §4d. **Geçerli öncelik sırası §4d'dedir.**

1. **Yayın:** GitHub + Render. Boş site ilk 2 saat içinde yayına alınmalıydı (gecikti). Ücretsiz planın uyku sorunu ve çözümü `docs/DEPLOY.md`'de.
2. **Arayüz eksikleri**
   - 3I/ATLAS ve diğer hareketli cisimler: MOST ile kareler ve kare kare oynatma.
   - Geri bildirim butonu: kategori, mesaj, isteğe bağlı e-posta; bağlam (sayfa/cisim/sürüm) otomatik eklenir.
   - Otomatik öneri (§4d): yerel Türkçe ad listesi (JSON) + SIMBAD `ident` + JPL; 2 karakter, 250 ms, en fazla 8; koordinatta "Bu koordinatta ara"; klavye ve ARIA; SIMBAD yoksa yalnızca yerel liste.
3. **WebSocket altyapısı:**
   - Temel kısım bitti (`/ws`, iş ilerlemesi, yeniden bağlanma).
   - Kalanlar: asistan cevaplarının akışı ve admin canlı etkinlik akışı (oturumla yetkilendirilmiş `admin` konusu). HTTP yedeği her zaman çalışmalı.
4. **Hesaplar (EmailJS)**
   - Sunucu 6 haneli kod üretir; kod hash'li saklanır, 10 dk geçerlidir.
   - Kod başına en fazla 5 deneme, e-posta başına saatte en fazla 3 gönderim.
   - Gönderim `POST https://api.emailjs.com/api/v1.0/email/send` ile, `accessToken` (private key) kullanılarak. Şablon değişkenleri `to_email`, `code`.
   - Kayıtlı çalışmalar ve cisim listesi.
   - **Cuma öğlene kadar.**
5. **Admin paneli**
   - Kullanıcılar; arama, karşılaştırma ve indirme etkinlikleri (canlı); geri bildirimler.
   - Admin rolü `.env`'deki `ADMIN_EMAIL` ile belirlenir.
   - "Veri sürümleri" bölümü ve "önbelleği yenile" düğmesi.
   - **Cuma öğlene kadar.**
6. **Excel (openpyxl)**
   - Dosya adı `cisimadi_YYYY-MM-DD.xlsx`.
   - Sayfalar: Özet, Gözlemler, Zaman karşılaştırması, Cisim karşılaştırması, Hareket.
   - Formül enjeksiyonu koruması (`=`, `+`, `-`, `@` ile başlayan hücrelerin başına `'`); en fazla 5.000 satır; ham piksel yok, FITS bağlantısı var.
   - Misafir tek cisim, giriş yapan kullanıcı çoklu cisim indirebilir; indirmeler admin akışında görünür; filtreler uygulanır.
7. **Asistan (kural tabanlı, dış yapay zekâ yok)**
   - Sağ kenarda açılan panel; hızlı soru düğmeleri.
   - Türkçe normalizasyon + anahtar kelime eşleştirme; `assistant_faq.json`.
   - "Karşılaştırmayı yorumla": yalnızca `comparison` tablosundaki gerçek değerlerle.
   - "Yazıyor…" efekti ve panel notu.
   - Bir arayüz arkasında durmalı (ileride dil modeli eklenebilir).
   - SSS'ye "Görüntü neden pikselli?" sorusu eklenecek (E7).
8. **Gözlem filtreleri + veri kalitesi satırı:** tarih aralığı, veri sürümü, λ aralığı (Excel'e de uygulanır); görüntünün altında maskeli piksel oranı ve uygulanan düzeltmeler.
9. **Canlı konum (§4d):** yıldızlar için öz hareketle bugünkü RA/Dec; Güneş Sistemi için JPL Horizons, 10 sn'de bir WS ile; şehir seçimiyle "Benim gökyüzümde" (yükseklik, yön, doğuş/batış), tarayıcı konum izni yok.
10. **Hubble ↔ Webb:** MAST'tan herkese açık önizlemeler yan yana, kayıt bilgisiyle, 2′ yarıçap; yoksa "bulunamadı" mesajı; önbellek ve demo cisimleri için ön çekme.
11. **DR1 / yeni veri hazırlığı**
    - `docs/NEW_DATA.md` (adım adım kılavuz) ve `tools/prewarm.py`.
    - DR1 duyurulunca `announced = true`.
    - Sistem beklenmedik veride çökmeden eski sürümle devam etmeli.
12. **Cilalama (E1–E8)**
    1. PSF uydurma (doymuş çekirdek dışlanır).
    2. Beklenen yön ve görüntüde iki işaret (beklenen ve ölçülen konum).
    3. "Gri: güvenilmez/maskelenmiş piksel" açıklaması.
    4. Daha büyük görüntüleyici.
    5. Halk için sade özet ve uyum işareti.
    6. Yumuşatılmış/ham piksel seçeneği.
    7. "Görüntü neden pikselli?" SSS sorusu.
    8. Galaksi ince ayarı.
13. **Çalışma biçimi:** dosyalar yalnızca Edit/Write ile değiştirilir; komutlar proje kökünden çalıştırılır; her adım test edilip commit'lenir.

Takvim: kesin kapsam **Cuma akşamına** kadar yayında ve test edilmiş olmalı. Cumartesiye yeni özellik bırakılmaz.

## Yerelde çalıştırma (hatırlatma)

```powershell
# proje kökünden
backend\.venv\Scripts\python.exe -m uvicorn skytracker.main:app --host 127.0.0.1 --port 8000   # http://127.0.0.1:8000
cd frontend; npm run build; cd ..                                                                 # ön uç değişince
```
