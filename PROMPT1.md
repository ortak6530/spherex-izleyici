# SPHEREx Gökyüzü İzleyici — Claude Code Proje İstemi

> **Kullanım:** Bu dosyayı projenin kök klasörüne `PROMPT.md` adıyla koy. Claude Code'u o klasörde başlat ve şunu yaz:
> `PROMPT.md dosyasını baştan sona oku. Sadece Faz 0'ı yap: kod yazma, planı ve sorularını çıkar.`
> Sonraki her faz için: `Faz 1'i yap` gibi yaz. Uzun istemi terminale yapıştırmak yerine dosyadan okutmak daha güvenlidir.

---

## 1. Çalışma kuralları (her faz için geçerli)

1. **Faz faz ilerle.** Bir fazı bitirince dur: ne yaptığını, nasıl çalıştıracağımı ve nasıl test edeceğimi yaz, onayımı bekle. Sonraki faza kendiliğinden geçme.
2. **Uydurma veri yok.** Yalnızca gerçek NASA/ESA/CDS verisi kullan. Bir servis yanıt vermezse açık bir hata veya "veri yok" durumu göster. Sahte veya örnek bilimsel veri üretme. Demo için önbellek gerekiyorsa gerçek bir yanıtı kaydet ve arayüzde "önbellekten" diye işaretle.
3. **Varsayma, doğrula.** API adreslerini, TAP tablo/sütun adlarını ve FITS başlıklarını küçük canlı çağrılarla kontrol et. Bulduklarını `docs/DATA_SOURCES.md` dosyasına yaz. Bu istemdeki bilgiler araştırmaya dayanır ama canlı sistemle çelişirse canlı sistem doğrudur, bana da söyle.
4. **Emin olmadığın kararda dur ve sor.** Özellikle: bilimsel yorum, veri sürümü, kimlik doğrulama sağlayıcısı, maliyet doğuran servisler.
5. **Sırlar** (API anahtarları, parola hash'leri, e-posta anahtarları) yalnızca `.env` dosyasında durur. `.env.example` oluştur, `.env` dosyasını `.gitignore`'a ekle. Hiçbir sır istemci (tarayıcı) koduna girmez.
6. **Ortam:** Windows 10/11, PowerShell. Python ve Node.js sürümlerini kontrol et. Eksik bir şey varsa kurmaya çalışma, bana tam komutla söyle. Tüm komutlar ve yollar Windows'ta çalışmalı.
7. **Dil:** Arayüz Türkçe (i18n altyapısı kur, sonradan İngilizce eklenebilsin). Kod ve kod yorumları İngilizce. Dokümanlar Türkçe.
8. Git kuruluysa her faz sonunda anlamlı bir commit at.

## 2. Ürün özeti

NASA Space Apps 2026 "Planet X ve SPHEREx" görevi için herkese açık bir web aracı. Görev metninin özü: SPHEREx altı ayda bir tüm gökyüzünü 102 bant yakın kızılötesi ışıkta haritalıyor, kuyruklu yıldızlar, asteroitler, kahverengi cüceler ve hatta yeni gezegenler görüntüler arasında **konum değiştirerek** kendini gösteriyor, ve hedef **herkesin gökyüzünün zaman içinde nasıl değiştiğini hızlıca görmesini sağlamak.**

Bu yüzden ürünün çekirdeği **zaman içindeki değişimi göstermek**. Diğer her şey bunu destekler.

**Önemli ilke:** Araç herkese açık olmalı. Kullanıcı hesabı olmadan da (misafir olarak) arama, görüntüleme ve karşılaştırma yapılabilmeli. Hesap yalnızca ek özellikler içindir (çalışma kaydetme, geçmiş vb.).

### Özellikler

1. **Arama (üst çubuk):** Nesne adı (ör. `M31`, `Betelgeuse`, `WISE 0855`) **veya koordinat** ile arama. Koordinat biçimleri: ondalık derece (`10.684 41.269`), saat-derece (`00h42m44s +41d16m09s`), iki nokta ayraçlı (`00:42:44.3 +41:16:09`), galaktik (`l=121.17 b=-21.57`). Ad çözümleme için CDS Sesame/SIMBAD. Güneş sistemi cisimleri (kuyruklu yıldız, asteroit) Sesame'de yok, bunlar için ayrı bir kaynak (ör. JPL Horizons) gerekir.
2. **Nesne görüntüleyici:** SPHEREx spektral görüntülerinden kesit, dalga boyu kaydırıcısı, spektrum grafiği, ölçek çubuğu, kuzey/doğu oku, renk haritası ve gerdirme seçenekleri.
3. **Karşılaştırma:**
   - **Zaman:** Aynı nesne, aynı dalga boyu kanalı, farklı gözlem tarihleri. Yan yana, kaydırma çubuğu, yanıp sönme (blink) ve fark görüntüsü.
   - **Nesne:** Aynı türden iki nesne (ör. iki kahverengi cüce). Aynı dalga boyunda yan yana, spektrumlar üst üste.
   - **Teleskop:** Aynı nesne için SPHEREx, Hubble ve Webb karşılaştırma butonu.
4. **Nesne bilgi paneli:** Bilinen genel bilgiler (tür, koordinat, parlaklık, tayf türü, uzaklık, kısa açıklama). Kaynaklar canlı sorgulanır, kısa süreli önbelleğe alınır ve her bilginin kaynağı yazılır.
5. **Yapay zeka asistanı (Claude API):** Sitenin amacını ve nasıl çalıştığını anlatır, seçilen karşılaştırmaları yorumlar.
6. **Geri bildirim butonu.**
7. **Canlı Samanyolu arka planı:** Yavaş dönen simülasyon tarzı galaksi.
8. **Yönetici paneli:** Yönetici herkesin ne yaptığını görür.
9. **Kullanıcı sistemi (EN SON):** E-posta ile hesap, e-postaya doğrulama kodu.
10. **Veri güncelleme hattı:** Şimdiki NASA verisiyle başlar, yeni gelen veriyle yeniden entegre edilebilir.

## 3. Doğrulanmış veri bilgileri

### SPHEREx (NASA/IPAC IRSA)

- Quick Release (QR) spektral görüntüleri **haftalık** yayımlanır. QR2, QR1'in yerini aldı ve IRSA API'lerinde varsayılan olandır. Gelecekte QR3 gibi sürümler çıkabilir, bu yüzden **veri sürümü her kayıtta saklanmalı.**
- Görüntü adresleri sürüm bilgisi içerir (ör. `.../qr2/level2/2025W18_1B/l2b-v20-2025-240/4/...fits`).
- Her ürün çok uzantılı FITS (MEF) spektral görüntüdür. Kesitte şu uzantılar var: `IMAGE`, `FLAGS`, `VARIANCE`, `ZODI`, `PSF`, `WCS-WAVE`. Her piksel farklı dalga boyuna karşılık gelir (LVF), dalga boyu haritası `WCS-WAVE` içindedir. **Bir spektral görüntü tek renkli bir fotoğraf değildir.** Bunu arayüzde dürüstçe anlat. Maske için `FLAGS`, hata için `VARIANCE` kullan. `ZODI` (zodyak ışığı modeli) çıkarılmış mı, nasıl kullanılmalı konusunu **Explanatory Supplement'ten oku** ve karar vermeden önce bana özetle.
- **Erişim yolları:**
  - Meta veri arama: IRSA TAP (`https://irsa.ipac.caltech.edu/TAP`, `pyvo` ile) ve SIA2 (`https://irsa.ipac.caltech.edu/SIA?`).
  - **Kesit servisi:** Görüntü URL'sinin sonuna merkez ve boyut parametresi eklenir, ör. `...fits?center=305.59875,41.14888d&size=0.01` (boyut derece). Belge: https://irsa.ipac.caltech.edu/data/SPHEREx/docs/cutout_tool.html
  - Örnek notebook (TAP ile kesit toplama): https://caltech-ipac.github.io/irsa-tutorials/spherex-cutouts
  - Toplu çekim için AWS açık veri kovası: `s3://nasa-irsa-spherex/` (`aws s3 ls --no-sign-request s3://nasa-irsa-spherex/qr2/spectral_wcs/`), AWS hesabı gerekmez.
  - Spektrofotometri aracı (zorlamalı fotometri ile spektrum çıkarır): IRSA'da mevcut. Önce kesitlerden kendi basit açıklık fotometrinle başla, gerekirse bu aracı değerlendir.
- Kuyruklu yıldız 3I/ATLAS için IRSA'da ayrı bir SPHEREx görüntü kaydı var. **Hareketli cisim demosu için iyi aday.**
- **Zaman boyutu:** İlk tüm gökyüzü haritası Aralık 2025'te tamamlandı, tarama yaklaşık altı ayda bir tekrarlanıyor, 2 yıllık ana görevde toplam 4 tarama planlı. Aynı koordinatın farklı tarihlerdeki gözlemlerini TAP'ta gözlem zamanıyla sorgula, tarama sayısını varsayma.
- Teslim takvimi (SPHEREx sitesinden): kalibre spektral görüntüler gözlemden sonra yaklaşık 2 ay içinde, tüm gökyüzü veri küpleri 2. ve 4. taramanın bitiminden 6 ay sonra. Veri küpleri çıkınca ayrı bir entegrasyon fazı gerekecek.
- Atıf: IRSA/AWS kayıt sayfalarındaki atıf biçimini sitede göster.

### Hubble ve Webb (MAST / STScI)

- Hubble ve JWST verisi MAST'ta. Yayımlanmış (özel erişim süresi dolmuş) veriyi aramak ve indirmek için hesap gerekmez.
- Programatik erişim: `astroquery.mast` (`MastMissions` ile `'hst'` ve `'jwst'`), MAST Discovery Portal API (`https://mast.stsci.edu/api`), CAOM SIA2 servisi (`https://archive.stsci.edu/vo/`, `image/jpg` ve `image/png` biçimleri destekleniyor).
- JWST için önizleme görüntüleri yakın zamanda eklendi, Hubble için "yakında" denmişti. **Önizleme olmayan kayıtları da zarif şekilde ele al.**
- **Kapsam seyrek.** Gökyüzünün küçük bir kısmı Hubble/Webb ile görüntülendi. "Bu koordinatta Hubble/Webb verisi yok" durumu normal sonuçtur, hata değil.
- Piksel ölçeği ve dalga boyu SPHEREx'ten çok farklı. Karşılaştırma ekranında bu farkı açıkça belirt (ör. "SPHEREx görüntüleri çok daha düşük uzamsal çözünürlüklüdür").

### Ad çözümleme ve nesne bilgisi

- **Sesame** (https://cds.unistra.fr/doc/sesame.htx) isimden J2000 koordinatı verir. Sorgu sırası SIMBAD, sonra NED, sonra VizieR. **Güneş sistemi cisimlerini kapsamaz.**
- SIMBAD'in kendi TAP servisi ve `astroquery.simbad` ile tür, büyüklük, tayf türü, paralaks, kırmızıya kayma gibi alanlar alınır.
- Ek olarak Vikipedi REST özeti (Türkçe, yoksa İngilizce) kullanılabilir.

### Claude API (önemli)

- **Claude Pro aboneliği API'yi kapsamaz.** Siteye Claude eklemek için Anthropic Console'da ayrı bir hesap ve API anahtarı, ayrı faturalandırma gerekir. Abonelik yalnızca claude.ai sohbetini ve Claude Code'u kapsar.
- Anahtar **yalnızca sunucuda** durur. Model adı `.env` içinde `CLAUDE_MODEL` olarak ayarlanabilir olsun (başlangıç: `claude-sonnet-5-5`, maliyet için `claude-haiku-5-5` seçeneği). Kullanıcı başına günlük istek sınırı, toplam harcama üst sınırı ve her çağrının token/maliyet kaydı olsun.

## 4. Mimari (öneri, Faz 0'da gerekçeli olarak onaylat veya değiştir)

- **Arka uç:** Python 3 + FastAPI. Gerekçe: `astropy`, `astroquery`, `pyvo`, `numpy` bilimsel hat için doğal seçim. FITS kesitlerini sunucuda işleyip PNG/WebP olarak (ve gerektiğinde ham sayısal veriyi JSON/ikili olarak) istemciye ver.
- **Ön uç:** React + Vite + TypeScript, Tailwind, Framer Motion, `three.js` (Samanyolu için). Bu bilgisayarda kurulu UI/UX Pro Max stili ve 21st.dev bileşenleri varsa kullan.
- **Veritabanı:** SQLite ile başla, SQLAlchemy + Alembic ile Postgres'e geçilebilir olsun.
- **Önbellek:** Kesit ve yanıt önbelleği `data/cache/<veri_sürümü>/` altında. Farklı veri sürümleri asla karışmasın.
- **Sağlayıcı arayüzleri:** `SkyDataProvider` (SPHEREx), `SpaceTelescopeProvider` (MAST), `NameResolver`, `ObjectInfoProvider`, `EmailSender`, `AIAssistant`. Her biri ayrı modül, sahte (mock) uygulaması test için.
- **Olay günlüğü** en baştan var: her kullanıcı eylemi bir olay olarak (anonim oturum kimliğiyle, hesap gelince `user_id` ile) kaydedilir.

## 5. Fazlar

### Faz 0 — Keşif ve plan (kod yazma)
- Bu istemi ve `docs/` klasörünü oku. Python/Node sürümlerini kontrol et.
- Canlı doğrulama (küçük çağrılar): IRSA TAP şeması ve SPHEREx tabloları, bilinen bir koordinat (ör. M31) için TAP sorgusu, tek bir kesit indirme, `FLAGS` ve `WCS-WAVE` okuma, bir Sesame sorgusu, bir MAST sorgusu. Sonuçları `docs/DATA_SOURCES.md` dosyasına yaz.
- `docs/ARCHITECTURE.md`: klasör yapısı, veri modeli, API uç noktaları, faz planı, riskler.
- Bana soracağın soruları listele (özellikle: kesit boyutu varsayılanları, zodyak ışığı işlemi, Hubble/Webb kapsamı, e-posta sağlayıcısı).
- **Kabul:** Plan onaylandı, doğrulama notları yazıldı.

### Faz 1 — Temel iskelet ve Samanyolu arka planı
- Depo yapısı, ortam yönetimi, lint/format, `.env.example`, i18n, tema (koyu uzay teması), duyarlı ana yerleşim, üst çubuk (arama alanı henüz bağlı değil).
- Canlı Samanyolu: `three.js` ile parçacık tabanlı sarmal galaksi, kollar logaritmik sarmal, iç bölgeler dışa göre hızlı döner (diferansiyel dönüş), çok yavaş hareket. `prefers-reduced-motion` ve sekme gizliyken duraklatma, zayıf cihazlarda parçacık azaltma. İçeriğin okunabilirliğini bozmayacak kadar sönük. Alt köşede "Sanatsal simülasyon, ölçekli değildir" notu.
- **Kabul:** Boş sayfa güzel görünüyor, 60 fps'e yakın, mobilde de çalışıyor.

### Faz 2 — SPHEREx veri katmanı, arama ve görüntüleyici
- Ad ve koordinat çözümleyici (tüm biçimler, belirsiz girişte öneri listesi, hata mesajları Türkçe). Birim testleri yaz.
- `SkyDataProvider`: TAP ile koordinatı kapsayan görüntüleri bul, kesit indir, `FLAGS` ile maskele, ölçekle, PNG üret. Kapsam yoksa net mesaj.
- Görüntüleyici: dalga boyu kaydırıcısı (kanal seçimi), spektrum grafiği (kendi açıklık fotometrinle, yöntemi arayüzde açıkla), gerdirme (doğrusal/asinh/log), renk haritası (algısal olarak düzgün olanlar), ölçek çubuğu, N/E oku, birimler. Üç bandı RGB'ye eşleyen "yanlış renk" seçeneği, açıkça etiketli.
- **Kabul:** M31 ve en az iki farklı nesne için ad ve koordinatla görüntü ve spektrum çıkıyor.

### Faz 3 — Veri güncelleme hattı (veri sürümü kavramı)
- `data_release` tablosu: sürüm adı (QR2 vb.), boru hattı sürümü (URL'den), alınma zamanı.
- CLI: `update-data` (yeni gözlemleri TAP'tan tara, indirmeden meta veriyi güncelle, kesitleri talep üzerine indir). Yinelenebilir (idempotent), eski sürümü yeni sürüm doğrulanana kadar silmez.
- Arayüzde "Veri sürümü: QR2 · Son güncelleme: …" göster. Karşılaştırmalar **aynı sürümde** yapılsın, farklıysa uyar.
- Gelecekte tüm gökyüzü veri küpleri ve yeni QR sürümleri için eklenti noktaları bırak.
- **Kabul:** Yeni bir sürüm çıktığında koda dokunmadan yapılandırmayla entegre edilebiliyor (belgele).

### Faz 4 — Karşılaştırma
- **Zaman:** Aynı nesne ve aynı dalga boyu kanalı için farklı gözlem tarihleri (kullanıcı listeden seçer). Yan yana, kaydırma çubuğu, yanıp sönme, fark görüntüsü. Fark istatistiği (ortalama, standart sapma, en büyük sapma konumu). Kalibrasyon ve sürüm uyumsuzluğu uyarıları. Hareketli cisimler (3I/ATLAS gibi) için kare kare oynatma.
- **Nesne:** İki nesne, tür eşleşmesi önerisi (SIMBAD `otype`), aynı dalga boyunda yan yana, spektrum üst üste (normalize seçenekli).
- **Kabul:** Her mod için en az bir gerçek örnek çalışıyor, sınırlamalar arayüzde açık.

### Faz 5 — Nesne bilgi paneli
- SIMBAD + Vikipedi, kısa TTL önbellek, her satırda kaynak etiketi. Veri yoksa "bilinmiyor" yaz, tahmin etme.
- **Kabul:** Panel, seçilen nesneyle birlikte anında dolar, kaynaklar görünür.

### Faz 6 — Hubble / Webb karşılaştırma butonu
- Aynı koordinat için MAST'ta HST ve JWST kayıtlarını bul, önizleme görüntüsü varsa göster, yoksa kayıt bilgisini ve MAST bağlantısını göster.
- Kapsam yoksa net, hata olmayan bir mesaj. Çözünürlük ve dalga boyu farkı uyarısı.
- **Kabul:** Kapsamlı bir hedefte (ör. M31 veya Orion) ve kapsamsız bir hedefte doğru davranıyor.

### Faz 7 — Claude asistanı
- Sunucu tarafı proxy. İki rol: (a) site rehberi (amaç, nasıl çalışır, bu görüntü nedir), (b) karşılaştırma yorumcusu.
- Yorumcuya yapılandırılmış gerçekler gönder: nesne kimliği/türü, koordinat, kanal, gözlem tarihleri, veri sürümü, fark istatistikleri, (isteğe bağlı) küçültülmüş görüntüler. Sistem istemi kuralları: yalnızca verilenlere dayan, ölçülen ile çıkarılanı ayır, düşük sinyal/gürültüde belirsizliği söyle, "yeni gezegen buldum" gibi iddialarda bulunma, Türkçe cevapla, akış (streaming) halinde göster.
- Günlük sınır, harcama üst sınırı, çağrı kaydı. Anahtar yoksa asistan düğmesi "yapılandırılmadı" desin, site yine çalışsın.
- **Kabul:** Bir karşılaştırma için tutarlı bir yorum üretiyor, uydurma bilgi vermiyor.

### Faz 8 — Geri bildirim, olay günlüğü ve yönetici paneli
- Geri bildirim butonu (kategori, mesaj, isteğe bağlı e-posta, bağlam: sayfa/nesne/sürüm otomatik eklenir).
- İlk ziyarette gizlilik bildirimi: hangi kullanım verileri kaydedilir (KVKK uyumu için açık, sade metin).
- Yönetici paneli: canlı etkinlik akışı, oturum/kullanıcı zaman çizelgesi, en çok aranan nesneler, hatalar, geri bildirim kutusu, CSV dışa aktarma, "yeni veriyi tara" düğmesi (Faz 3 CLI'sini çağırır).
- **Hesap sistemi gelene kadar** yönetici girişi `.env` içindeki tek bir yönetici hesabıyla (parola hash'li, httpOnly oturum çerezi) çalışsın.
- **Kabul:** Siteyi kullanırken yaptığım eylemler yönetici panelinde görünüyor.

### Faz 9 — Kullanıcı sistemi (EN SON)
- Misafir kullanım **kapanmaz.** Hesap yalnızca ek özellikler (aramalarım, kayıtlı karşılaştırmalar) içindir.
- E-posta + parola veya yalnızca e-posta kodu, e-postaya **doğrulama kodu**.
- **Güvenlik şartı:** Kod tarayıcıda üretilmez veya doğrulanmaz. Sunucu 6 haneli kodu üretir, **hash'li** saklar, 10 dakika geçerlilik, en fazla 5 deneme, yeniden gönderme bekleme süresi, IP ve e-posta başına hız sınırı. Parolalar argon2 veya bcrypt ile.
- **EmailJS hakkında:** EmailJS tarayıcıdan e-posta göndermek içindir, genel anahtarı sayfa kaynağında görünür ve kötüye kullanılabilir, ücretsiz planda aylık 200 e-posta ve 2 şablon sınırı var. Kodu istemcide üretip doğrulamak güvenli değildir. `EmailSender` arayüzü arkasında EmailJS'i **sunucu tarafından** (özel anahtarla, EmailJS belgelerinde bunun için gereken hesap ayarını doğrulayarak) kullanıp kullanamayacağını araştır. Kodlamaya başlamadan önce bana **seçenekleri artı/eksileriyle sun** (EmailJS sunucu tarafı, Supabase Auth veya Firebase Auth gibi hazır doğrulama, Resend/Brevo gibi bir e-posta API'si) ve seçimimi bekle.
- Roller (kullanıcı/yönetici), olay günlüğünü `user_id`'ye bağla, hesap silme ve dışa aktarma.
- **Kabul:** Kayıt, kod doğrulama, giriş, çıkış, misafir akışı çalışıyor, kod kötüye kullanım testlerini (yanlış kod, süre, deneme sınırı) geçiyor.

### Faz 10 — Cila, test ve teslim
- Erişilebilirlik (klavye, kontrast, aria), performans, hata durumları, yükleme iskeletleri.
- Testler: koordinat ayrıştırıcı, karşılaştırma hesapları, veri sürümü mantığı, OTP kuralları. Canlı servis yerine **gerçek yanıtlardan kaydedilmiş** test verisi kullan.
- `README.md`: kurulum, ortam değişkenleri, çalıştırma, veri güncelleme, yönetici kurulumu. Kaynaklar ve sınırlamalar sayfası (SPHEREx düşük çözünürlüklüdür, Hubble/Webb kapsamı seyrektir, QR verisi son ürün değildir). Altbilgide atıflar: NASA/IPAC IRSA (SPHEREx), MAST/STScI (Hubble, Webb), CDS Strasbourg (SIMBAD, Sesame).
- Yarışma için 3 dakikalık demo senaryosu (`docs/DEMO.md`).

## 6. Güvenlik ve gizlilik

- Tüm girdileri doğrula (koordinat, ad, boyut). Sunucu yalnızca izin verilen sunuculara (IRSA, MAST, CDS, Vikipedi) istek atsın, kullanıcıdan gelen rastgele URL'yi indirmesin (SSRF).
- Hız sınırı, CORS kısıtı, güvenli başlıklar, hata mesajlarında iç ayrıntı sızdırma.
- Yönetici ve oturum çerezleri `httpOnly`, `Secure`, `SameSite`.
- Kişisel veri en az düzeyde, gizlilik metni açık.

## 7. Başlangıç

**Şimdi yalnızca Faz 0'ı yap.** Kod yazma. Çıktın: (1) canlı doğrulama sonuçlarının özeti, (2) `docs/ARCHITECTURE.md` taslağı, (3) bana soruların.
