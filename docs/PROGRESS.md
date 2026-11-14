# İlerleme durumu

> **Son güncelleme:** 2026-11-14 (DR1 `ae692f9`, galaksi `af8e76d`, asistan; sıradaki: Aşama 3 j). **Her yayın Render önbelleğini siler → demodan önce son yayından sonra prewarm çalıştır.** · Teslim: **15 Kasım 2026, 16:00** · Canlı: https://spherex-izleyici.onrender.com
> Kararlar ve talimatlar: [`DECISIONS.md`](DECISIONS.md) (**geçerli plan §4e**) · Mimari: [`ARCHITECTURE.md`](ARCHITECTURE.md) · Veri kaynakları: [`DATA_SOURCES.md`](DATA_SOURCES.md) · Kaynaklar/atıflar: [`SOURCES.md`](SOURCES.md) · Yayın: [`DEPLOY.md`](DEPLOY.md)

## Geçerli plan (DECISIONS.md §4e) — durum

| Madde | Durum | Not |
|---|---|---|
| **1a** Kaynaklar sayfası + `SOURCES.md` | ✅ | 13 kaynak (`config/attributions.toml` tek kaynak). Teşekkür metinleri 2026-11-13'te sağlayıcı sayfalarından aynen alındı: SPHEREx, SIMBAD, MAST (HST/JWST), Gaia DR3 (+ lisans CC BY-NC 3.0 IGO), CADC (SSOIS belge sayfası), NEOSSat (CADC). Sitede `/#kaynaklar`, alt bilgiden bağlantı; eski atıf iletişim kutusu kaldırıldı. `SOURCES.md`, `tools/gen_sources_md.py` çıktısıdır; `tests/test_sources.py` eşitliği ve zorunlu metinleri denetler. **Bulunamayanlar:** JPL Horizons'ın resmî teşekkür kalıbı (bizim açıklamamız, "alıntı değildir" notuyla); OGL–Canada sayfası otomatik erişimi reddetti (ad talimattan). Gelecekte kullanılacak kaynaklar "Planlandı" olarak işaretli. |
| **1b** NEOSSat notları (`DATA_SOURCES.md`) | ✅ | §12: ürün sırası (CORD → COR → RAW uyarılı, CLEAN yok), 2,997″/px ve 0,86° (CSA-NEOSSAT-MAN-0002 v4.00'dan doğrulandı), CTYPE1/CRTYPE1 + CD matrisi, süzgeç anahtarları, FILTER=CLEAR → parlaklık karşılaştırması yok. "WCS = uydu yönelim tahmini" ifadesi kılavuzda bulunamadı, not düşüldü. CADC TAP henüz denenmedi (madde p). Ayrıca §4.8'e 2026-11-13 MOST doğrulaması eklendi. |
| **1c** 3I/ATLAS oynatıcı + "Koleksiyon" kartı | ✅ | Oynatıcı `239827d` (canlıda doğrulandı). Ana sayfada "Koleksiyon" kartı: "Kare kare izle" aramayı arama kutusu üzerinden başlatır (`?q=` paylaşım bağlantısı güncellenir); IRSA'nın 3I/ATLAS SPHEREx sayfasına bağlantı (200 doğrulandı). Test: `Hero.test.tsx` (+ tr/en anahtar eşitliği testi). |
| **1d-1** Geri bildirim butonu | ✅ | Üst çubukta (her sayfada). Kategori (Hata/Öneri/Veri sorunu/Diğer), mesaj (5–2000), isteğe bağlı e-posta ("yalnızca yanıt için"), sayfa + seçili cisim otomatik eklenir. `POST /api/v1/feedback` → `feedback` tablosu (Alembic `0003`, `alembic check` temiz), denetim karakterleri temizlenir, bağlam düz değerlerle sınırlı, gizli tuzak alanı (bot → kayıt yok), oturum başına ~6/saat. Testler: `test_feedback.py` (4), `FeedbackButton.test.tsx` (2). **Admin listesi Aşama 2 f'de** (admin girişi gerektiriyor). |
| **1d-2** Arama kutusunda otomatik öneri | ✅ | `GET /api/v1/suggest?q=` (+ `&local=1` anında yanıt). Kaynaklar: yerel Türkçe liste `config/names_tr.json` (49 cisim; her `query` 2026-11-13'te `/resolve` ile canlı doğrulandı, Halley/Encke için `1P`/`2P`), Sesame (yalnızca SIMBAD, tam ad), JPL SBDB, SIMBAD kimlik öneki. Her uzak kaynak 4 sn sınırlı ve paralel; düşen kaynak `unavailable` içinde bildirilir, yerel liste her zaman yanıt verir. Türkçe normalleştirme (ı/İ, ş, ğ, ü, ö, ç). "barnard" → **Barnard Yıldızı** ilk sırada. Koordinat girilince "Bu koordinatta ara". `/resolve` da tam Türkçe adı tanır ("Kutup Yıldızı" → Polaris). Ön uç: ARIA combobox/listbox, 2 karakter, 250 ms, en fazla 8, ↑/↓/Enter/Esc/Tab, eski yanıtlar atılır. **Düzeltilen hata:** `adql_str` `%`'yi sildiği için SIMBAD `LIKE` sorguları tam eşleşmeye dönüşüyordu (eski "Bunu mu demek istediniz?" önerileri de etkileniyordu). Testler: `test_suggest.py` (25), `SearchBox.test.tsx` (4). **2026-11-13 düzeltme:** tam eşleşmeler her zaman en üstte ("m3" → M 3, sonra M 31/M 33); tam eşleşme = Sesame/SBDB'nin doğrudan çözdüğü ad, yerel listede birebir ad/takma ad ya da SIMBAD kimliğinin yazılanla aynı olması (+3 test, canlıda doğrulandı). |
| **2g-1** WebSocket: yavaş sorgu ilerlemesi | ✅ | Gözlem/kesit/karşılaştırma/MOST zaten iş + WS ile çalışıyordu. Eklenenler: her ilerleme mesajında `elapsed_s`; `/objects/info` ve `/objects/similar` önbellekteyse hemen, değilse `job_id` + adımlar (`info_query`, `info_fallback` (Sesame yedeği), `similar_query`); istemcide `runMaybeJob` ve ortak `ProgressLine` (adım + saniye sayacı, 20 sn sonra "arşiv yavaş, işlem sürüyor" notu). Yeniden bağlanınca abonelikler geri yükleniyor, HTTP yoklaması her zaman yedek. Testler: `test_progress.py` (4, WS üzerinden `job_done` dahil), `ProgressLine.test.tsx` (3). Kalan WS işleri: admin canlı akışı (f) ve asistan akışı (i). |
| **2-prewarm** `tools/prewarm.py` | ✅ | 3I/ATLAS, Barnard, WISE 0855, Luhman 16. Arayüzün yaptığı istekleri sırayla yapar: ad çözümleme, bilgi paneli, aynı tür önerileri, gözlemler (Barnard D5, WISE 0855/Luhman 16 D6), varsayılan zaman karşılaştırması (ilk ve son dönem, en küçük Δλ/bant); 3I/ATLAS için MOST kareleri ve en parlak dönemin D5 kesitleri (3 paralel, en fazla 40). Yalnızca standart kütüphane, 429'da bekleyip yeniden dener. Yerelde canlı veriyle çalıştı (43 sn, 0 hata): Barnard 12,50″, WISE 0855 8,52″, Luhman 16 2,90″ ölçülen kayma; 3I/ATLAS 17/17 kesit. Test: `test_prewarm.py` (seçim mantığı arayüzle aynı). Kullanım `DEPLOY.md`'de. |
| **2e** Hesaplar (EmailJS) | ✅ canlıda doğrulandı (kullanıcı kodla giriş yaptı, 2026-11-14) | Tablolar `user_account`, `login_code`, `auth_session`, `saved_item` (Alembic `0004`, `alembic check` temiz). Kod: `secrets` ile 6 hane, yalnızca HMAC-SHA256(SECRET_KEY) saklanır, 10 dk, kod başına 5 deneme (sonra kilit), e-posta başına saatte ≤3 gönderim (+ oturum başına sınır), yalnızca en yeni kod geçerli, başarısız gönderim hakkı yemez. EmailJS REST sunucudan, `accessToken` ile; şablon değişkenleri `to_email`, `code`, `valid_minutes`, `site_url` (DECISIONS §4f). EmailJS boşsa geliştirmede kod yalnızca sunucu günlüğüne (maskeli e-postayla), üretimde 503 `EMAIL_NOT_CONFIGURED`; kod hiçbir yanıtta yok. Oturum: rastgele belirteç, httpOnly/SameSite=Lax (üretimde Secure) çerez, yalnızca SHA-256 saklanır, 30 gün. Çerezli POST'larda Origin denetimi. Admin rolü `ADMIN_EMAIL` ile (saklanmaz). Kayıtlılar: cisim listesi + çalışmalar (karşılaştırma kimliğiyle; yalnızca hesaplayan tarayıcı ya da sahibi kaydedebilir), en fazla 200. Ön uç: üst çubukta Giriş/Hesabım, iki adımlı giriş (tek kullanımlık kod alanı), cisim başlığında "Listeme ekle", karşılaştırma sonuçlarında "Çalışmayı kaydet". Testler: `test_accounts.py` (11), `Account.test.tsx` (2). Yerelde uçtan uca curl ile doğrulandı. |
| **2e-fix** Kod isteme sınırı | ✅ `1e44269` | Gönderilmeyen kod (EmailJS hatası, adres sınırı, geçersiz adres) tarayıcı hakkını yemez; 429'da `retry_after_s` + "yaklaşık N dakika". Sınırlar: tarayıcı başına art arda 5 istek, sonra 12 dk'da 1 (bellekte, yayında sıfırlanır); e-posta başına saatte 3 (veritabanında). |
| **2f** Admin paneli | 🟡 kod bitti, canlıda yönetici girişiyle **denenmedi** — aşağıdaki "Admin paneli: nerede kaldık" | `32a2723` |
| **Karşılama ekranı** (kullanıcı talimatı, 2026-11-14 sabah, Excel'den önce) | ✅ `eb6bdb3`, canlıda doğrulandı (yeni paket yayında, `/api/v1/health` 200 `db: ok`) | `components/Welcome.tsx` (`EntryGate`), `lib/entry.ts`. Mevcut arayüzün önüne konan kapı: Samanyolu arka planı üzerinde başlık, tek cümle, "Giriş yap" (mevcut e-posta + 6 haneli kod akışı ve Türkçe sınır mesajları) ve "Misafir olarak devam et"; gizlilik notu ("Giriş yaparsan arama ve liste etkinliğin site yöneticisi tarafından görülebilir." + misafir etkinliği kişisel veriyle eşleşmez). Seçim `sessionStorage`'da (yalnızca bu sekme oturumu); giriş yapmış kullanıcı görmez; çıkışta ekrana dönülür. `?q=` (cisim ve paylaşılan karşılaştırma bağlantıları), `#admin`, `#kaynaklar` ekranı atlar; `#admin` girişsizse kendi "Giriş yap" düğmesini gösterir. Telefon genişliğinde düğmeler alt alta, tam genişlik. Testler: `Welcome.test.tsx` (3: misafir + oturumda hatırlama, giriş sonrası geçiş + çıkışta dönüş, doğrudan bağlantı atlama). **Tarayıcıda elle bakılmadı** (kullanıcı kontrol edecek). |
| **2h** Excel olarak indir | ✅ `09fdb06`, canlıda doğrulandı (curl: M 31 → `m-31_2026-11-14.xlsx`, 362 gözlem satırı, indirme 200 + doğru MIME, 37 KB; `/api/v1/health` 200 `db: ok`). Tarayıcıda düğmeyle **denenmedi** | `services/export_xlsx.py` (openpyxl, saf biçimleme) + `api/v1/export.py`. `POST /export/xlsx {items:[{q,d}], filters}` iş olarak çalışır (adımlar `export_object`, `export_build` + mevcut SIA2/dalga boyu adımları, WS); `GET /export/<id>` dosyayı yalnızca isteyen tarayıcıya verir (15 dk bellekte, en fazla 30 dosya; yayında sıfırlanır). Sorgu sunucuda yeniden çözümlenir (`resolve_target`, tarayıcının koordinatına güvenilmez). Sayfalar: **Özet** (ad, SIMBAD kimliği, tür, tayf, RA/Dec derece + sa/°, uzaklık 1/paralaks, Vikipedi özeti ve bağlantısı, sayılar, notlar, kullanılan kaynakların teşekkür metinleri `attributions.toml`'dan aynen + SPHEREx atıfları), **Gözlemler** (tarih, MJD, ziyaret, sürüm, dedektör, hedefte λ, bant genişliği, yaklaşık kanal, dedektör aralığı, gözlem kimliği, boru hattı, FITS bağlantısı), **Zaman karşılaştırması** / **Cisim karşılaştırması** (yalnızca yapıldıysa; bu tarayıcının ya da kullanıcının `comparison` kayıtları, cisim başına en yeni 25; uyarılar sitedeki Türkçe metinlerle), **Hareket** (MOST: tarih, RA/Dec, r, Δ, faz, V, kare merkezine uzaklık; "öngörülen konum, ölçüm değil" notu). Formül enjeksiyonu: `= + - @` (ve sekme/CR) ile başlayan metne `'`; hiçbir hücre formül değil (testli). Sayfa başına 5.000 satır, kesilen satır sayısı Özet'te. Ham piksel yok. Dosya adı `cisimadi_YYYY-MM-DD.xlsx` (Türkçe harfler sadeleşir; çoklu: `cisim-listesi_…`). Misafir 1 cisim (fazlası 401 `LOGIN_REQUIRED_MULTI`), giriş yapan en fazla 20 (Hesabım → "Excel'e aktar", onay kutularıyla). İndirme her zaman `download` olayı olarak kaydedilir (izin yoksa IP/UA'sız) → admin "İndirme" grubu. **λ notu:** hedefteki λ sitede seçili dedektör için hesaplanır; diğer dedektörlerde yalnızca önbellekte varsa dolu (IRSA'ya yüzlerce ek istek atmamak için), Özet'te açıklandı. Filtreler (tarih, sürüm, λ) API'de hazır ve testli; arayüzdeki filtre denetimleri Aşama 3 j ile gelecek. Excel yalnızca Türkçe. Ön uç: cisim başlığında ve hareketli cisim görünümünde "Excel olarak indir". Testler: `test_export.py` (7), `ExcelButton.test.tsx` (2). Yerelde gerçek veriyle: Barnard D5 → 358 gözlem satırı; 3I/ATLAS → 364 kare + Hareket sayfası (11 sn). |
| **DR1 duyurusu** (kullanıcı talimatı, 2026-11-14) | ✅ `ae692f9` | Canlı TAP: `spherex_dr1` 945 725 görüntü (2025-04-24 → **2026-05-14 11:47 UTC**), `spherex_qr3` 362 124 (→ **2026-10-05 00:01 UTC**), QR2 TAP'ta yok. SIA2 (Barnard): DR1 240, QR3 123, QR2 0; derin alan `spherex_dr1_deep` çalışıyor. MOST DR1 döndürüyor (3I/ATLAS 364 DR1; Eros 916 DR1 + 38 QR3) → not gerekmedi. `releases.toml`: `announced = true`, DOI 10.26131/IRSA678 (+ IRSA679 All-Sky Cube), varsayılan DR1, QR2 `superseded`. IRSA teşekkür metni ack.html ile birebir (İngilizce orijinal, `lang="en"`). Ayrıntı `DATA_SOURCES.md` §4.9. |
| **Samanyolu yakınlaştırma** | ✅ `af8e76d` | `GALAXY_ZOOM = 1.4` (`galaxy/GalaxyBackground.tsx` başı; 1 = eski çerçeve). Kamera zoom'u + nokta boyutu aynı katsayıyla; okunabilirlik örtüsü 0/0,35/0,8 → 0,12/0,45/0,85. Karşılama ve ana arayüz aynı bileşen. Tarayıcıda bakılmadı. |
| **Yarı saydam paneller** | ✅ `958e9ac`, canlıda | Samanyolu'nu engelleyenler: `.glass` %78 opak + blur 14px; arka plan örtüsü (kenarlarda %85); iç kartlar `bg-space-950/50`. Şimdi `.glass` %58 + blur 8px + kenarlık %16 + ince metin gölgesi; diyalog/açılır liste/asistan/gizlilik için `.glass-strong` (%88); örtü 0,18/0,18/0,5; iç kartlar /35; görüntüleyici çerçeveleri opak; `GALAXY_ZOOM = 1.4` aynı. Kontrast hesabı (en kötü durum: panelin arkasında beyaz çekirdek): ink-100 ≥ 4,9:1; galaksi kollarında ink-100/300/400 ≥ 4,5:1. Ekran görüntüsü alınmadı (DECISIONS §4e); masaüstü/telefon görünümünü kullanıcı kontrol edecek. Yerleşim değişmedi. |
| **2g-2 + i** Kural tabanlı asistan + WS akışı | ✅ `e8bb34a` + `cf74f7b` (kullanıcı talimatı 2026-11-14) | `config/assistant_faq.json` (kodsuz düzenlenir). **Hazır düğmeler:** SPHEREx nedir?, Bu görüntüdeki renkler ne anlama geliyor?, Zaman karşılaştırmasını nasıl kullanırım?, Hareketli cisim nedir, 3I/ATLAS neden özel?, Veri nereden geliyor, ne kadar güncel?, Hubble ve Webb karşılaştırması nedir? (özelliğin henüz olmadığı açıkça yazılır), Karşılaştırmayı yorumla, Seçili cisim. Eşleşme yoksa "Bunu bilmiyorum. Şu sorulardan birini dene:" + 6 hazır soru. **Veri güncelliği:** `services/freshness.py` arşivdeki en yeni gözlemi IRSA TAP'tan arka planda okur (açılışta ve 12 saatte bir; sorgu ~2 dk sürdüğü için sohbette beklenmez); sabit tarih yok, okunmadıysa "okunuyor" denir; testte `ARCHIVE_FRESHNESS_CHECK=false`. **Cisme göre:** "renkler" ve "zaman karşılaştırması" cevaplarına açık cismin adı, türü ve SPHEREx görüntü sayısı eklenir (sayı yalnızca önbellekten: kapsam / MOST; yoksa "henüz hesaplanmadı"). **Admin günlüğü:** yalnızca `assistant_question` (soru metni, cisim, cevap türü yok; izin çerezi kuralı geçerli), admin'de "Asistan" grubu ve "Asistan sorusu" etiketi. E7 "Görüntü neden pikselli?" dahil. `services/assistant.py`: `AssistantEngine` protokolü (`reply()` metin parçaları + son `Answer`) → `RuleBasedAssistant` (ileride dil modeli aynı arayüze takılabilir). Türkçe normalleştirme + anahtar kelime ağırlıkları (4+ harf ek alır: "piksel" ~ "pikselli"); eşik altı → öneriler; mesajda yerel listeden cisim adı geçerse ya da kısa mesaj çözümlenirse cisim açılır (`open_object`). "Karşılaştırmayı yorumla" yalnızca sunucudaki `comparison` kaydından (bu tarayıcının ya da kullanıcının; başka tarayıcının kimliği okunamaz): kayma px/″ ve yön, beklenenle fark (≤ 0,5 px → "uyumlu ✓"), parlaklık farkı ± hata ve σ (≥ 3σ anlamlı), kanal, uyarılar (Excel ile aynı Türkçe metinler); değer yoksa "ölçülemedi"/"önce bir karşılaştırma yap". `POST /assistant/message` iş olarak çalışır, cevap `assistant_chunk` adımlarıyla WS'den akar (abone olmak için ≤ 1 sn beklenir), sonuç tam metni taşır (HTTP yedeği). Ön uç `features/AssistantPanel.tsx`: sağ alt "Asistan" düğmesi, sağdan çekmece (telefonda tam genişlik), panel notu, "Yazıyor…", öneri çipleri, Esc ile kapanır; yalnızca karşılaştırma kimliği gönderilir (`lib/lastComparison.ts`, cisim değişince sıfırlanır). Cevaplar yalnızca Türkçe. Testler: `test_assistant.py` (23: hazır düğmeler + sabit tarih/yüzde yok, serbest metin eşleşmesi, "Bunu bilmiyorum" + öneriler, canlı güncellik / "okunuyor", cisme göre cevap, admin'e yalnız `assistant_question`, TAP okuması, yorumlama, sahiplik, WS akışı), `AssistantPanel.test.tsx` (2). Yerel WS denemesi: ilk parça 0,06 sn, parçalar = tam metin; gerçek Luhman 16 ve WISE 0855/Luhman 16 kayıtları doğru yorumlandı. **Canlıda doğrulandı (`cf74f7b`, 2026-11-14 06:52 UTC):** güncellik IRSA'dan arka planda okundu → "en yeni SPHEREx gözlemi: 2026-10-05 (QR3) … DR1: 2026-05-14"; Barnard açıkken "358 görüntü"; eşleşmeyen soru → "Bunu bilmiyorum…" + hazır sorular; cevap parça parça. **Tarayıcıda bakılmadı.** |
| ~~Hubble ↔ Webb~~ | **iptal edildi (kapsam dışı)**, 2026-11-14 | DECISIONS §4g. Asistan sorusu kaldırıldı ("Bunu bilmiyorum"a düşer), Kaynaklar'dan HST/JWST (MAST hiç kullanılmadı) ve `upstreams.toml`'dan `mast.stsci.edu` çıkarıldı; testler bunların geri gelmesini engeller. |
| Kalan sıra (DECISIONS §4g, kullanıcı onayladı) | 🔄 | 1) veri durum çubuğu + spektrum grafiği → 2) j: gözlem filtreleri (tarih / sürüm / λ, Excel'e de; API tarafı `export.py`'de hazır), veri kalitesi satırı, canlı konum → 3) hareket izi katmanı + `docs/NEW_DATA.md`. Donma 21:00. |

## Admin paneli (2f): nerede kaldık — 2026-11-14

**Bitenler** (`32a2723`, testler: arka uç 119, ön uç 22, tsc/ESLint/ruff temiz, push'landı)
- Arka uç `api/v1/admin.py`, tümü yalnızca `ADMIN_EMAIL` oturumuyla (yoksa 401, başka hesap 403 `ADMIN_ONLY`):
  - `GET /admin/summary`: kullanıcı sayısı, son 24 saatin olayları (türlere göre), ziyaret sayısı, yeni geri bildirim, e-posta modu.
  - `GET /admin/users`: e-posta, kayıt, son giriş, kayıtlı öğe ve olay sayısı.
  - `GET /admin/events?group=search|compare|download|account|feedback&before_id=&limit=`: kısa oturum öneki ve kullanıcı e-postası gösterilir, **IP özeti hiç gösterilmez**.
  - `GET /admin/feedback?status=`, `POST /admin/feedback/{id}/status` (`new`/`read`/`done`).
  - `GET /admin/releases`: `releases.toml`'dan sürümler (salt okunur; açma/kapama yalnızca dosyadan) + önbellek boyutları.
  - `POST /admin/cache/refresh {scope}`: kapsam bir sürüm kimliği, `external` ya da `all` olabilir. Kapsamlar sabit listeden seçilir, önbellek kökünün dışına çıkılamaz (`../etc` ve `_index` → 400). Görüntü dizini (`_index`) yalnızca `all` ile silinir.
- **Canlı akış:** WebSocket `admin` konusuna yalnızca admin oturumu abone olabilir (çerez + `ADMIN_EMAIL`, bağlantı başına bir kez denetlenir).
  - Kaydedilen her olay ve her geri bildirim anında yayınlanır. `publish_nowait` senkron uç noktalardan da çalışır; izleyen admin yoksa hiçbir şey gönderilmez.
  - Olaylara giriş yapan kullanıcının kimliği (`user_id`) eklenir.
- **Ön uç:** `/#admin` (ayrı paket, 13 KB). Sekmeler: Özet, Canlı etkinlik (grup filtresi; soket kapalıysa 15 sn'de bir HTTP yenileme), Kullanıcılar, Geri bildirimler (durum düğmeleri), Veri sürümleri (önbellek boyutları + onaylı "Önbelleği yenile"). "Hesabım" penceresinde yöneticiye "Yönetici paneli" bağlantısı görünür.
- **Yazarken düzeltilen hata:** canlı olay mesajında olay türü `type` alanına yazılıyor ve mesaj türünü (`admin_event`) eziyordu; arama/karşılaştırma olayları arayüze hiç ulaşmayacaktı. Alan `event_type` oldu, iki tarafta da testi var.

**Kalanlar**
1. **Canlıda yönetici girişiyle elle deneme** (kullanıcı): Hesabım → Yönetici paneli → beş sekme. Özellikle Canlı etkinlik: başka bir sekmede arama yapınca satır anında üste gelmeli (WS).
2. ~~"İndirme" grubu, Excel (2h) gelene kadar boş kalacak.~~ Excel `09fdb06` ile geldi; indirmeler bu grupta görünür.
3. Olay listesinde "daha eski" sayfalama düğmesi yok (API `before_id` destekliyor); şimdilik son 100 olay.
4. Kullanıcı ayrıntısı (tek kullanıcının olayları) ve geri bildirime yanıt yok (kapsamda istenmedi).
5. Prewarm canlıda en son `32a2723`'ten **önce** çalıştırıldı; bu yayın önbelleği sildi. Demodan önce yeniden çalıştırılmalı: `tools\prewarm.py --base https://spherex-izleyici.onrender.com --only <cisim>` (cisim cisim).

**Bilinen hatalar / riskler**
- **Render yeniden başlatması (çözülmedi):** 2026-11-13 20:42–20:50 UTC arasında prewarm sırasında sunucu yeniden başladı, önbellek silindi ve iş kayboldu (`UNKNOWN_JOB`).
  - Yerel ölçümde bellek en fazla 162 MB (sınır 512 MB). Ücretsiz planın 0,1 CPU'su yüzünden sağlık kontrolünün zaman aşımına uğraması daha olası, ama **doğrulanmadı**.
  - Kullanıcıdan Render → Events'teki mesaj bekleniyor. "Health check failed" ise yapılacaklar: VOTable ayrıştırmasını `to_thread`'e almak, başlık okumayı en fazla 8 paralelle sınırlamak.
  - Cisim cisim prewarm (00:09–00:12) sorunsuz geçti.
- Sunucu tarafı olaylar (arama, karşılaştırma, kayıt, önbellek yenileme) yalnızca gizlilik bildirimini kabul eden ziyaretçilerde kaydedilir (KVKK kararı). Geri bildirimler ve (Excel gelince) indirmeler her zaman görünür. Bu yüzden canlı akış tüm trafiği göstermez; panelde not olarak yazıyor.
- `admin/cache/refresh` işlemi olay günlüğüne yalnızca admin tarayıcısı izin verdiyse düşer.
- Bellek içi işler ve hız sınırları her yayında ve yeniden başlatmada sıfırlanır (tek örnek tasarımı).

## Önceki oturumdan devralınan 3 iş (bitti / plana taşındı)

1. ✅ **Yayın (2026-11-13):** https://spherex-izleyici.onrender.com — depo `github.com/ortak6530/spherex-izleyici`, Render Blueprint (web + `spherex-db`), `autoDeploy`. Duman testi: `/api/v1/health` → `{"status":"ok","db":"ok"}`; M31 ve 3I/ATLAS çözümleme, MOST işi (364 kare) canlıda çalışıyor; güvenlik başlıkları ve `Secure` çerez var. Kalan: uyku önleyici zamanlayıcı (cron-job.org, 10 dk'da bir `/api/v1/health`).
2. **3I/ATLAS hareketli cisim görünümü (MOST).**
   - ✅ Arka uç (`915471d`): `providers/most.py`, `GET /moving/{tanım}/frames` (job + WS), `POST /moving/cutout` (cisme ortalı kesit, ayrı hız sınırı). MOST'a ad değil SBDB tanımı (`des`) verilir: "Ceres" belirsiz → 400, `1`/`433`/`2P`/`2025 N1` çalışır. MOST bitişi 2026-10-16'ya kırpıyor.
   - ✅ Ön uç (`features/MovingView.tsx`): dönem + dedektör seçimi (kare sayılarıyla), kesitler 3'er paralel yüklenir ve geldikçe gösterilir (en fazla 40), oynat/duraklat, ←/→/boşluk, hız 1/2/4 kare/sn, zaman kaydırıcısı, her karede zaman, RA/Dec, λ, r, Δ, faz, V, FITS bağlantısı; ortak parlaklık ölçeği seçeneği; dönemin ±3 günlük gök yolu grafiği. Varsayılan: öngörülen en parlak dönem + D5 (CO₂ 4,26 µm).
   - Başsız Edge (CDP, gerçek zamanlı) ile doğrulandı: 3I/ATLAS Aralık 2025 D5 → 17/17 kare ~60 sn'de, cisim karenin ortasında net; Ağustos 2025'te (Δ 2,8 AU) tek karede seçilmiyor.
3. **Geri bildirim butonu + arama çubuğunda otomatik öneri** → §4e madde 1d.

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

1. ~~Site henüz yayında değil.~~ 2026-11-13'te yayına alındı (Render). Ücretsiz planda 15 dk sonra uyku; zamanlayıcı henüz kurulmadı.
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
10. ~~**Hubble ↔ Webb**~~ — **iptal edildi (kapsam dışı)**, 2026-11-14 (DECISIONS §4g).
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
