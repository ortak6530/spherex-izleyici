# Yayın (Render)

Site tek bir Render **Docker web servisi** olarak çalışır. FastAPI hem API'yi ve WebSocket'i (`/ws`) hem de derlenmiş ön ucu sunar. Veriler (kullanıcılar, olaylar, geri bildirim) Render **Postgres** veritabanında tutulur. Tanım dosyası: `render.yaml` (Blueprint).

## İlk yayın (yaklaşık 15 dk)

1. GitHub'da boş bir depo açın (özel olabilir). Ardından proje klasöründe:
   ```powershell
   git remote add origin https://github.com/<kullanici>/<depo>.git
   git push -u origin main
   ```
2. Render panelinde **New → Blueprint** seçin, depoyu bağlayın. `render.yaml` dosyası okunur, web servisi ve `spherex-db` veritabanı birlikte oluşturulur.
3. `sync: false` olan değişkenleri panele girin. Bunlar sohbette paylaşılmaz.
   - `PUBLIC_BASE_URL`: Render'ın verdiği adres, ör. `https://spherex-izleyici.onrender.com`
   - `ADMIN_EMAIL`, `EMAILJS_*` (hesaplar fazından önce gerekmez), `WIKIMEDIA_USER_AGENT`
   - `SECRET_KEY` ve `IP_HASH_SALT` Render tarafından otomatik üretilir.
4. İlk derleme birkaç dakika sürer. Sonrasında kontrol için `https://<adres>/api/v1/health` adresi `{"status":"ok"}` döndürmeli.

Her `git push` otomatik olarak yeniden yayınlanır (`autoDeploy: true`).

**Yayından sonra ve demodan önce önbelleği ısıtın.** Render diski her yayında sıfırlanır; ilk ziyaretçi IRSA'yı beklemesin:

```powershell
backend\.venv\Scripts\python.exe tools\prewarm.py --base https://spherex-izleyici.onrender.com
```

Araç 3I/ATLAS, Barnard Yıldızı, WISE 0855 ve Luhman 16 için arayüzün açtığı her şeyi bir kez ister. Yalnızca standart kütüphaneyi kullanır. Sıcak önbellekte yaklaşık 1 dk, soğuk önbellekte birkaç dakika sürer.

> Not: Bu bilgisayarda Docker kurulu olmadığı için imaj yerelde derlenip denenmedi. İlk derleme Render'da yapılacak. Hata olursa derleme günlüğünü paylaşmanız yeterli.

## Ücretsiz planın sınırları ve çözümleri

Koşullar Render'ın kendi belgelerine göre değişebilir, güncel hallerini panelden kontrol edin.

| Sorun | Etki | Çözüm |
|---|---|---|
| **Uyku:** 15 dakika istek gelmezse servis durur | İlk ziyaretçi soğuk başlangıç bekler. Python ve astropy içeren bir imaj için yaklaşık 30–60 sn. | (1) Harici bir zamanlayıcı (ör. cron-job.org veya UptimeRobot) her 10 dakikada `GET /api/v1/health` çağırarak servisi uyanık tutar. Ücretsiz planın aylık örnek saati tek bir servisin sürekli çalışmasına yeter. (2) Demodan 2–3 dakika önce siteyi açın. (3) Arayüz yavaş ilk yanıtta "sunucu uyanıyor" mesajı gösterecek (sonraki fazlarda). |
| **Kalıcı olmayan disk:** yeniden başlatma ve yayında dosya sistemi sıfırlanır | SQLite ve dosya önbelleği silinir | Kalıcı veriler Postgres'te tutulur. Dosya önbelleği (FITS kesitleri) yeniden üretilebilir. Demo cisimleri başlangıçta arka planda yeniden ısıtılır (Hubble/Webb fazı). |
| **512 MB bellek** | Büyük FITS dosyaları belleği doldurabilir | Yalnızca kesitler ve Range ile kısmi okuma kullanılır, tam 70 MB'lık dosyalar indirilmez. Kesit boyutu en fazla 0,5°. `CACHE_MAX_GB=1`. |
| **Ücretsiz Postgres'in süresi sınırlı** (oluşturulduktan yaklaşık 30 gün sonra) | Yarışmadan sonra veritabanı silinebilir | Teslim için yeterli. Uzun süre kullanmak için ücretli plana geçmek ya da verileri dışa aktarmak gerekir. |
| **Tek örnek** | Hız sınırı ve WebSocket abonelikleri süreç içinde tutuluyor | Tek örnek için doğru tasarım. Ölçeklenecekse paylaşılan bir depoya (Redis) geçilir. |

## Yerelde çalıştırma

```powershell
# Arka uç (bir kez)
py -3.13 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
backend\.venv\Scripts\python.exe -m pip install -e backend
Copy-Item .env.example .env   # sonra doldurun
cd backend; .venv\Scripts\alembic.exe upgrade head; cd ..

# Ön uç (bir kez)
cd frontend; npm install; npm run build; cd ..

# Tek sunucu (API + derlenmiş ön uç): http://127.0.0.1:8000
backend\.venv\Scripts\python.exe -m uvicorn skytracker.main:app --port 8000

# Geliştirme (anında yenileme): ayrı terminalde `cd frontend; npm run dev` → http://localhost:5173
```

## Testler

```powershell
cd backend; .venv\Scripts\python.exe -m pytest -q; .venv\Scripts\ruff.exe check src tests
cd frontend; npx tsc -b; npx eslint .; npx vitest run
```
