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

## 5. Teknik sonuçlar (bu kararlardan çıkan)

- **Render ücretsiz planında dosya sistemi kalıcı değil.** SQLite her yeniden başlatmada sıfırlanır. Kullanıcı, etkinlik ve geri bildirim verileri için `DATABASE_URL` ile **Render Postgres** kullanılır. Yerelde SQLite kullanılır. Ayrıntı: `docs/DEPLOY.md`.
- Tek bir Render web servisi kullanılır: FastAPI hem API'yi ve WebSocket'i hem de derlenmiş ön ucu sunar. Böylece CORS ve çerez karmaşası olmaz.
- Asistan yalnızca sunucunun hesapladığı karşılaştırma nesnesini okur. Yeni veri uydurmaz.
