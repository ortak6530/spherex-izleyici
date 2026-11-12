# Kararlar

> Kaynak: kullanıcının Faz 0 sorularına yanıtı (2026-11-12). Yeni kararlar en alta tarihle eklenir.
> Bu dosya ile `PROMPT1.md` çelişirse **bu dosya** geçerlidir.

## 1. Zaman ve çalışma biçimi

- **Son teslim: 15 Kasım 2026, 16:00.** Gerçek yapım süresi yaklaşık 32 saat.
- Her adımın sonunda **çalışan ve commit'lenmiş** bir sürüm bırakılır.
- Yeni bir veri sürümü (QR3/DR1/…) **kod değiştirmeden, yapılandırmayla** eklenebilmelidir (`config/releases.toml`).

## 2. Kesin kapsam (öncelik sırasıyla)

1. **Veri çekme ve zaman karşılaştırması:** ad/koordinat arama, SIA2, kesit, aynı cismin iki dönemde karşılaştırılması, fark görüntüsü, MOST ile hareketli cisimler, cisim bilgisi (SIMBAD/Vikipedi).
2. **Cisim–cisim karşılaştırması:**
   - Kullanıcı ikinci bir cisim seçip yan yana karşılaştırır. Aynı türden olanlar öne çıkar (ör. iki kahverengi cüce). Farklı tür seçilebilir ama uyarı gösterilir.
   - İki görüntü aynı dalga boyu kanalında, aynı kesit boyutunda ve aynı parlaklık ölçeğinde gösterilir. Ölçek farklıysa belirtilir.
   - Yanında bir karşılaştırma tablosu olur: tür, tayf türü, uzaklık, parlaklık, öz hareket (SIMBAD) ve varsa SPHEREx ölçümleri.
3. **Arayüz:** üstte arama çubuğu, görüntüleyici (Dönem A/B, yanıp sönme, fark), cisim–cisim görünümü, bilgi paneli, hareketli Samanyolu arka planı, geri bildirim butonu.
4. **"Excel olarak indir":**
   - Cisim panelinde bir buton. Sunucu `.xlsx` dosyasını **openpyxl** ile üretir. Dosya adı: `cisimadi_YYYY-MM-DD.xlsx`.
   - Sayfalar:
     - **Özet:** ad, tür, RA/Dec, uzaklık, açıklama, veri kaynakları ve atıf metni
     - **Gözlemler:** tarih, sürüm, dedektör, λ, bant genişliği, FITS bağlantısı
     - **Zaman karşılaştırması** (yapıldıysa): dönemler, kayma (px ve ″), parlaklık farkı (%), kanal eşleşmesi, uyarılar
     - **Cisim karşılaştırması** (yapıldıysa)
     - **Hareket** (MOST sonucu varsa: tarih ve konumlar)
   - Giriş yapmış kullanıcılar kayıtlı listeden birden çok cisim seçip tek dosyada indirebilir. Misafirler tek cisim indirebilir.
   - Ham piksel verisi konmaz, FITS bağlantısı verilir. Satır sınırı yaklaşık 5.000.
   - **Formül enjeksiyonu koruması:** `=`, `+`, `-` veya `@` ile başlayan hücre değerlerinin başına `'` eklenir.
   - İndirmeler admin etkinlik akışında görünür.
5. **WebSocket (FastAPI):**
   - Yavaş sorgularda adım adım canlı ilerleme bildirilir.
   - Asistan cevapları akış halinde gelir.
   - Admin için canlı etkinlik akışı.
   - HTTP yolu her zaman yedek olarak çalışır. İstemci bağlantı koparsa otomatik yeniden bağlanır.
6. **Kullanıcı hesapları (e-posta + doğrulama kodu):**
   - Kodu sunucu üretir: 6 hane, hash'li saklanır, 10 dakika geçerli, kod başına en fazla 5 deneme, e-posta başına saatte en fazla 3 gönderim.
   - Gönderim **EmailJS REST API** ile sunucudan yapılır, private key (`accessToken`) kullanılır: `POST https://api.emailjs.com/api/v1.0/email/send`. Şablon değişkenleri: `to_email`, `code`.
   - Kullanıcı kayıtlı çalışmalarını ve cisim listesini görebilir.
7. **Admin paneli:** kullanıcılar, arama/karşılaştırma/indirme etkinlikleri (canlı), geri bildirimler. Admin rolü `.env` içindeki `ADMIN_EMAIL` ile belirlenir.
8. **Asistan (kural tabanlı, dış yapay zekâ API'si YOK):**
   - Sağ kenarda düğmeyle açılan sohbet paneli.
   - Hızlı soru düğmeleri: site tanıtımı, nasıl kullanılır, nasıl arama yapılır, SPHEREx nedir, görünümler ne demek, karşılaştırmayı yorumla, seçili cisim bilgisi.
   - Serbest metin: Türkçe karakter normalizasyonu + anahtar kelime eşleştirme. Eşleşme yoksa önerilen sorular gösterilir. Mesajda bir cisim adı geçerse o cisim açılır.
   - **"Karşılaştırmayı yorumla":** zaman ve cisim–cisim karşılaştırmasını, sunucunun hesapladığı **gerçek değerlerden** şablon cümlelerle yorumlar (kayma px ve ″, parlaklık farkı %, kanal eşleşmesi, ZODI/sürüm uyarıları, SIMBAD değerleri). Değer yoksa uydurmaz, "önce bir karşılaştırma yap" der.
   - Soru-cevaplar `assistant_faq.json` dosyasında durur, kod değiştirmeden düzenlenebilir.
   - "Yazıyor…" efekti olur. Panelde şu not yer alır: "Bu asistan hazır cevaplar ve sitenin hesapladığı verilerle çalışır."
   - Modül bir arayüzün arkasında durur. İleride bir dil modeli eklenebilir, ama şimdi eklenmez.
   - Görünüm ve davranış referansı `docs/demo_reference.html` dosyasıdır (yalnızca örnek: verileri benzetimdir, kodu doğrudan kopyalanmaz). ⚠ Dosya 2026-11-12 itibarıyla klasörde **yok**, kullanıcının eklemesi bekleniyor.
9. **Hubble ↔ Webb (en son sırada):**
   - MAST'tan herkese açık HST ve JWST önizlemeleri yan yana gösterilir, kayıt bilgisiyle (tarih, alet, filtre, bağlantı). Yarıçap 2′. FITS işlenmez.
   - Biri yoksa şu mesaj gösterilir: "Bu cisim için herkese açık Hubble/Webb görüntüsü bulunamadı".
   - MAST sonuçları önbelleğe alınır. Demo cisimlerinin (M31, M42, WISE 0855, Barnard, 3I/ATLAS) önizlemeleri önceden çekilir.

**Kapsam dışı (şimdilik):** dış dil modeli, IRSA PSF fotometrisi, FITS'ten HST/JWST işleme.

## 3. Faz 0 sorularının yanıtları

| # | Konu | Karar |
|---|---|---|
| S1 | Veri sürümü | QR2 varsayılan. QR3 ayrı ve uyarılı gösterilir. DR1 resmî olarak açılınca DR1 + QR3 (R7) varsayılan olur. S3'teki duyurulmamış DR1 kullanılmaz. |
| S2 | QR2 ↔ QR3 karşılaştırması | İzinli, ama yalnızca `l3_flux_corrections` uygulanarak ve uyarıyla |
| S3 | ZODI | Görüntülemede varsayılan `IMAGE − ZODI` (ham görünüm seçilebilir). Fark görüntüsünde ek olarak yerel arka plan çıkarılır. Fotometride halka ile yerel arka plan kullanılır. |
| S4 | Normalleştirme | Fark görüntüsünde varsayılan açık (göreli). Ölçek çarpanı gösterilir, kapatılabilir. |
| S5 | Kanal toleransı | \|Δλ\| ≤ 0,5 bant genişliği: eşleşme. 0,5–1: uyarı. > 1: karşılaştırma yapılmaz. |
| S6 | Kesit boyutu | Varsayılan 0,1°. Seçenekler 0,05 / 0,1 / 0,25 / 0,5°. Üst sınır 0,5°. |
| S7 | Hubble/Webb | Kayıt + önizleme, 2′, yalnızca PUBLIC (ayrıntı için kapsam madde 9) |
| S8 | E-posta | EmailJS REST, sunucu tarafında `accessToken` ile |
| S9 | Asistan | Dış yapay zekâ yok, kural tabanlı (kapsam madde 8) |
| S10 | Yayın | Herkese açık, **Render** (WebSocket destekli). Boş site ilk 2 saatte yayına alınır. Ücretsiz planın uyku sorunu ve çözümü `docs/DEPLOY.md` dosyasında. |
| S11 | Teslim | 15 Kasım 2026, 16:00 |
| S12 | Python | 3.13 sanal ortam |
| S13 | Git | `git init`, Faz 0 belgeleri commit'lenir, doğrulama betikleri `tools/` altına konur |
| S14 | Wikimedia User-Agent | Proje adı + depo URL'si (kişisel e-posta yok) |
| S15 | Demo hedefleri | M31, M42, WISE 0855, 3I/ATLAS, Barnard Yıldızı |
| S16 | KVKK | IP tuzlanmış hash olarak saklanır, 90 gün |

## 4. Güvenlik kuralları

- Tüm anahtarlar `.env` dosyasında durur. `.env.example` depoda yer alır, `.env` ise `.gitignore`'da.
- Anahtarlar sohbette istenmez. `.env` dosyasını kullanıcı doldurur.
- Render'da sırlar panelden ortam değişkeni olarak girilir.

## 4b. Güncel talimatlar (2026-11-12 akşam; çakışırsa bunlar geçerli)

**A) Çalışma biçimi**
- Dosya değişiklikleri yalnızca Edit/Write araçlarıyla yapılır. PowerShell ile dosya yeniden yazılmaz (`[System.IO.File]`, `.Replace`, `Set-Content`).
- Komutlar mümkün olduğunca proje kökünden ve aynı biçimde çalıştırılır (izin hatırlama için).

**B) Takvim**
- NASA yeni veriyi (büyük olasılıkla DR1'in resmî yayını) **13 → 14 Kasım gecesi** yayınlayacak.
- Kesin kapsamın tamamı **Cuma (14 Kasım) akşamına kadar** mevcut veriyle (QR2/QR3) bitecek, yayına alınacak ve test edilecek. Cumartesiye yeni özellik bırakılmaz. Teslim: 15 Kasım 16:00.
- **Öncelik sırası:** cisim–cisim karşılaştırması > arayüzün tamamı > gözlem filtreleri > Excel > WebSocket > hesaplar (EmailJS) > admin paneli > asistan > Hubble↔Webb > DR1 hazırlığı > cilalama.

**C) Yeni veriye hazırlık**
- DR1, sürüm ayarına `enabled: false` olarak eklenir. S3'teki DR1 dosyalarıyla yalnızca geliştirme ortamında okuma, kesit, bayrak (MSKN/MSKM/MSKD) ve kalibrasyon testleri yapılır. Sitede herkese açık gösterilmez.
- `docs/NEW_DATA.md`: yeni sürüm (QR/DR) ya da farklı biçimde veri geldiğinde adım adım kılavuz (ayar ekleme, doğrulama, önbellek temizleme, demo testi, yayın).
- `tools/check_release.py <sürüm>`: TAP koleksiyonunu, S3 klasörünü ve örnek kareyi kontrol eder. Başlık, bayrak ve uzantı biçimini bilinen sürümlerle karşılaştırıp farkları raporlar. Demo cisimlerinde karşılaştırma testi yapıp sonucun beklenenle uyuşup uyuşmadığını yazar (M31: değişim yok; Barnard ve 3I/ATLAS: hareket var).
- `tools/prewarm.py`: demo cisimlerinin (M31, M42, WISE 0855, Barnard, 3I/ATLAS) görüntülerini, karşılaştırmalarını ve Hubble/Webb önizlemelerini önceden hesaplayıp önbelleğe alır.
- Sürüm açma/kapama ve varsayılan sürüm yalnızca ayardan yapılır. Admin panelinde "veri sürümleri" bölümü ve "önbelleği yenile" düğmesi bulunur.
- Yeni veri beklenmedik biçimde gelirse sistem çökmez, eski sürümle çalışmaya devam eder.

**D) Gözlem filtreleri** (kesin kapsam, arayüzden sonra)
- Gözlem listesi tarih aralığına, veri sürümüne (QR2/QR3/DR1) ve dalga boyu aralığına (µm) göre süzülebilir. Filtreler Excel çıktısına da uygulanır.
- Görüntünün altında küçük bir "veri kalitesi" satırı: maskelenen piksel oranı ve uygulanan düzeltmeler (bayrak, kalibrasyon, ZODI).

**E) Cilalama** (Cuma, kesin kapsamdan sonra)
1. Konum ölçümü için doymuş/maskeli merkez piksellerini dışarıda bırakan PSF uydurma (Barnard'da ölçülen yön 341°, beklenen ~356°).
2. Sonuçta beklenen yön de gösterilir. Görüntüde beklenen ve ölçülen konum için iki ayrı işaret.
3. Maskeli (gri) pikseller için açıklama: "Gri: güvenilmez/maskelenmiş piksel".
4. Görüntüleyici büyütülür, sol boşluk kullanılır.
5. Sonuç kutusunun başında halk için sade bir özet ve uyum işareti (ör. "1 yılda 11,5″ kaydı — bilinen hareketle uyumlu ✓").
6. Görüntüleyicide "Yumuşatılmış / Ham pikseller" seçeneği. Halk için varsayılan yumuşatılmış; ölçümler her zaman ham veriyle yapılır.
7. Asistan SSS'sine "Görüntü neden pikselli?" sorusu: SPHEREx'in 6,2″/piksel ölçeği, tüm gökyüzünü 102 renkte tarama amacı, Hubble/Webb ile fark.
8. Galaksi arka planının ince ayarı.

## 4d. Gece talimatları (2026-11-12, oturum sonu; çakışırsa bunlar geçerli)

**Arama çubuğunda otomatik öneri**
- Kaynaklar: yerel Türkçe adlı liste (JSON) + SIMBAD `ident` araması + JPL.
- 2 karakterden sonra, 250 ms gecikmeyle, en fazla 8 öneri gösterilir.
- Girdi koordinatsa "Bu koordinatta ara" seçeneği çıkar.
- Klavye ile tam kullanım ve ARIA (combobox/listbox) desteği.
- SIMBAD erişilemezse yalnızca yerel liste kullanılır.
- ⚠ Not: SIMBAD'in CfA aynası `ILIKE` desteklemiyor (2026-11-12'de doğrulandı). Büyük/küçük harf duyarsızlığı için `LIKE` varyantları kullanılacak (`providers/simbad.suggest` gibi).

**Canlı konum**
- Yıldızlar: öz hareketle bugünkü RA/Dec.
- Güneş Sistemi cisimleri: JPL Horizons, 10 sn'de bir WebSocket ile güncellenir.
- İsteğe bağlı şehir seçimiyle "Benim gökyüzümde" görünümü: yükseklik, yön, doğuş/batış. Tarayıcı konum izni **istenmez**.

**Öncelik sırası** (§4b'deki sıranın yerini alır)
1. Yayın (GitHub + Render)
2. Arayüz eksikleri: 3I/ATLAS MOST görünümü, geri bildirim butonu, otomatik öneri
3. WebSocket altyapısı
4. Hesaplar (EmailJS)
5. Admin paneli
6. Excel
7. Asistan
8. Gözlem filtreleri + veri kalitesi satırı
9. Canlı konum
10. Hubble ↔ Webb
11. Cilalama

Hesaplar ve admin paneli **Cuma (14 Kasım) öğlene kadar** biter. 8–11. maddeler vakit kalırsa yapılır.

## 4c. DR1 geçişi (2026-11-12 akşamı)

**Olay:** IRSA, DR1'i (`spherex_dr1`) TAP ve SIA2'ye aldı ve QR2'yi bu servislerden kaldırdı. M31'de QR2 için 0 satır dönüyor; DR1'de 226, QR3'te 136 satır var. DR1 dosyaları ve kesitleri IBE'de çalışıyor (yalnızca dizin listesi 404). QR2 dosyaları doğrudan URL ile hâlâ açılıyor. IRSA'nın SPHEREx sayfası DR1'i henüz duyurmuyor.

**Karar (kullanıcı):** Varsayılan **DR1 + QR3** (ikisi de R7 kalibrasyonu). QR2 `superseded`: önbellekteki sonuçlar okunur, yeni aramada kullanılmaz. Arayüzde "resmî duyuru bekleniyor" notu gösterilir. IRSA duyurunca `config/releases.toml` dosyasında DR1 için `announced = true` yapmak notu kaldırmaya yeter.

**Barnard D5, DR1 → QR3** (2025-08-25 → 2026-09-22, 393 gün, aynı PA): ölçülen kayma **12,50″ (2,04 piksel), yön 347°**; SIMBAD öz hareketinden beklenen **11,18″ (1,82 piksel)**, yön ~356°. Fark 0,22 piksel. Δλ = 5 nm (bant genişliğinin 0,14'ü). Farklı sürüm uyarısı yok, çünkü iki görüntü de R7 kalibrasyonunda.

**`tools/check_release.py dr1` raporu (2026-11-12 21:07 UTC):**

- Ayar: status=active, announced=False, calib_family=R7, SIA koleksiyonları=['spherex_dr1']
- TAP (M31 konumu) koleksiyon satırları: spherex_dr1 = 226, spherex_qr3 = 136 → ✓ `spherex_dr1` TAP'ta var
- SIA2 `spherex_dr1` (M31): 226 görüntü
- S3 `dr1/`: abs_gain_matrix, aurora_template, dark, dichroic, epsf, gain_factors, he_template, hips5_cube, l3_flux_corrections, level2, nonfunc_v2, nonlinear_pars, readnoise_pars, shuttle_glow_template, sip, solid_angle_pixel_map, spectral_channels, spectral_wcs, xtalk_class1, xtalk_class2, zodi_scaling_v2. İlk level2 dönemi: `2025W17_4B`.
- Örnek kare `2025W33_2C_0177_1` D6 (2025-08-15):
  - VERSION 7.0.5, BUNIT MJy/sr, ZODIMDL KEL98_WAVESCL_V1
  - Uzantılar: PRIMARY, IMAGE, FLAGS, VARIANCE, ZODI, EPSF, WCS-WAVE
  - Bayrak başlığı MSK (MSKM ve MSKD de var), 22 bayrak
  - R7 (QR3) düzeniyle fark: **yok ✓**; R7 bayrak listesiyle fark: yok. (R6/QR2 düzeninden uzantılar, bayrak biçimi ve ZODI modeli farklı; beklenen bir durum.)
- Demo karşılaştırmaları (yalnızca DR1 dönemleri arasında):
  - **M31** (D2, λ 1,649 / 1,655 µm): parlaklık farkı **−1,6 ± 4,2 %** → anlamlı değişim yok ✓. Normalleştirme çarpanı 0,978. Uyarılar: NO_BACKGROUND, HIGH_MASK_FRACTION. (QR2 ile görülen sahte %20'lik "parlama" DR1'in tutarlı kalibrasyonuyla kayboldu.)
  - **Barnard** (D5, 202 gün; 2025-08 ile 2026-03 zıt tarama yönünde, PA 0°/180°): ölçülen 9,65″ (1,57 piksel), beklenen 5,74″ (0,93 piksel) → fark 0,64 piksel **✗ uyumsuz**. Olası neden: doymuş ya da maskeli çekirdek ağırlık merkezini maskesiz tarafa çekiyor ve yön 180° dönünce bu sapma toplanıyor. Çözüm cilalama maddesi E1 (doymuş çekirdeği dışlayan PSF uydurma). Aynı yönlü DR1 → QR3 çiftinde fark 0,22 piksel.
  - 3I/ATLAS: hareketli cisim görünümü (MOST) bu araçta henüz test edilmiyor, atlandı.

## 5. Teknik sonuçlar (bu kararlardan çıkan)

- **Render ücretsiz planında dosya sistemi kalıcı değil.** SQLite her yeniden başlatmada sıfırlanır. Kullanıcı, etkinlik ve geri bildirim verileri için `DATABASE_URL` ile **Render Postgres** kullanılır. Yerelde SQLite kullanılır. Ayrıntı: `docs/DEPLOY.md`.
- Tek bir Render web servisi kullanılır: FastAPI hem API'yi ve WebSocket'i hem de derlenmiş ön ucu sunar. Böylece CORS ve çerez karmaşası olmaz.
- Asistan yalnızca sunucunun hesapladığı karşılaştırma nesnesini okur. Yeni veri uydurmaz.
