# Kaynaklar ve atıflar

> Bu dosya `config/attributions.toml` dosyasından **üretilir**; elle düzenlemeyin.
> Güncel çıktı: `backend\.venv\Scripts\python.exe tools\gen_sources_md.py` (test: `--check`).
> Aynı içerik sitede **Kaynaklar** sayfasında (`/#kaynaklar`, alt bilgideki bağlantı) gösterilir.

Yarışma kuralı gereği sitenin kullandığı **her** dış kaynak burada anılır. Teşekkür metinleri
sağlayıcının sayfasından **aynen** alınmıştır; nereden ve ne zaman alındığı her metnin altında yazar.
"Planlandı" işaretli kaynaklar henüz kullanılmıyor.

| Kaynak | Durum | Kullanım amacı |
|---|---|---|
| SPHEREx (NASA / JPL / Caltech) | Kullanılıyor | Tüm SPHEREx spektral görüntüleri, kesitler, zaman ve cisim karşılaştırmaları, hareketli cisim kareleri. |
| NASA/IPAC Infrared Science Archive (IRSA) | Kullanılıyor | SPHEREx verisine erişim: SIA2 kapsam sorgusu, TAP, kesit servisi, IBE dosyaları, MOST (hareketli cisim arama). |
| SIMBAD ve Sesame (CDS, Strasbourg) | Kullanılıyor | Ad çözümleme (Sesame), cisim türü, tayf türü, paralaks, öz hareket ve aynı-tür önerileri (SIMBAD TAP; CDS ve CfA aynası). |
| JPL Solar System Dynamics (SBDB, Horizons) | Kullanılıyor | Güneş Sistemi cisimlerinin tanımı (SBDB), SPHEREx karelerindeki öngörülen konumlar (Horizons; IRSA MOST üzerinden) ve canlı konum paneli (Horizons API: şu anki RA/Dec, seçilen şehirden yükseklik ve yön). |
| Vikipedi / Wikipedia ve Wikidata | Kullanılıyor | Cisim bilgi panelindeki kısa açıklama (önce Türkçe, yoksa İngilizce) ve tanımlayıcılar; "Benim gökyüzümde" şehir koordinatları (Wikidata P625, config/cities_tr.json). |
| Gaia (ESA) | Planlandı | Öz hareket ve paralaks (ESA Gaia TAP, gaiadr3.gaia_source) ve görüntü üstü Gaia kaynak katmanı (Aşama 4). |
| CADC SSOIS (Solar System Object Image Search) | Planlandı | Güneş Sistemi cisimleri için "bu cismi başka hangi teleskoplar görmüş" listesi; yalnızca bağlantı, dosya indirme yok (Aşama 4). |
| NEOSSat (CSA / DRDC; veri CADC'de) | Planlandı | Konuma ve tarihe göre NEOSSat görüntüleri (filtresiz optik): yalnızca konum, hareket ve zaman; SPHEREx ile parlaklık karşılaştırması yapılmaz (Aşama 4). |
| WiseView (Caselden & Westin) | Planlandı | Yalnızca dış bağlantı: "Bu cismi WISE'ta yıllar boyunca izle" (Aşama 4). Gömme yok. |
| Astropy | Kullanılıyor | FITS okuma, WCS, VOTable ayrıştırma, zaman dönüşümleri. |
| Açık kaynak yazılımlar | Kullanılıyor | Sitenin yapımında kullanılan kütüphaneler (sürüm ve lisans, paket bilgisinden). |

## Veri kaynakları ve servisler

### SPHEREx (NASA / JPL / Caltech)

- **Durum:** Kullanılıyor
- **Kullanım amacı:** Tüm SPHEREx spektral görüntüleri, kesitler, zaman ve cisim karşılaştırmaları, hareketli cisim kareleri.
- **Adres:** <https://irsa.ipac.caltech.edu/Missions/spherex.html>
- **Lisans / koşullar:** IRSA'nın SPHEREx sayfasındaki zorunlu teşekkür metni yayınlarda ve bu sitede yer almalıdır.
- **DOI:** 10.26131/IRSA678 (DR1 Spectral Images) · 10.26131/IRSA679 (DR1 Spectral All-Sky Cube) · 10.26131/IRSA662 (QR3) · 10.26131/IRSA652 (QR2)

> This publication makes use of data products from the Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory and the California Institute of Technology, and is funded by the National Aeronautics and Space Administration.

Metnin alındığı yer: https://irsa.ipac.caltech.edu/Missions/spherex.html, 2026-11-13 tarihinde doğrulandı.

_Not:_ DR1 yayın tarihi: 12 Kasım 2026 (SPHEREx duyurusu).

Atıf yapılacak yayınlar:

- [Bock et al. (2026) — Mission](https://ui.adsabs.harvard.edu/abs/2026ApJ...999..139B/abstract)
- [Akeson et al. (2026) — Pipeline](https://ui.adsabs.harvard.edu/abs/2026ApJS..285...67A/abstract)
- [Crill et al. (2025) — Sky Simulator](https://ui.adsabs.harvard.edu/abs/2025ApJS..281...10C/abstract)
- [Korngut et al. (2026) — Instrument & Calibration](https://ui.adsabs.harvard.edu/abs/2026arXiv260329835K/abstract)

Başvurulan belgeler:

- [SPHEREx Explanatory Supplement](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf)
- [IRSA SPHEREx Data Explorer](https://irsa.ipac.caltech.edu/applications/spherex/)
- [SPHEREx Archive User Guide (IRSA)](https://irsa.ipac.caltech.edu/spherex-archive-documentation/)
- [IRSA: SPHEREx Data Release 1 (DR1) overview and DOIs](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_dr1.html)
- [IRSA tutorial: Introduction to SPHEREx Spectral Images (Data Overview)](https://caltech-ipac.github.io/irsa-tutorials/spherex-intro/)
- [IRSA tutorial: SPHEREx Spectral Image Cutouts](https://caltech-ipac.github.io/irsa-tutorials/spherex-cutouts/)
- [IRSA tutorial: SPHEREx PSF in Spectral Image Cutouts (PSF Models)](https://caltech-ipac.github.io/irsa-tutorials/spherex-psf/)
- [IRSA tutorial: SPHEREx Source Discovery Tool](https://caltech-ipac.github.io/irsa-tutorials/spherex-source-discovery-tool-demo/)
- [IRSA tutorial: SPHEREx Mosaic Cubes](https://caltech-ipac.github.io/irsa-tutorials/spherex-mosaic/)
- [IRSA tutorial: SPHEREx HiPS (All-Sky) Cubes](https://caltech-ipac.github.io/irsa-tutorials/spherex-hipscube/)
- [IRSA: SPHEREx observations of Comet 3I/ATLAS](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/comet3iatlas/index.html)

### NASA/IPAC Infrared Science Archive (IRSA)

- **Durum:** Kullanılıyor
- **Kullanım amacı:** SPHEREx verisine erişim: SIA2 kapsam sorgusu, TAP, kesit servisi, IBE dosyaları, MOST (hareketli cisim arama).
- **Adres:** <https://irsa.ipac.caltech.edu/>

> This research has made use of the NASA/IPAC Infrared Science Archive, which is funded by the National Aeronautics and Space Administration and operated by the California Institute of Technology.

Metnin alındığı yer: https://irsa.ipac.caltech.edu/ack.html, 2026-11-12 tarihinde doğrulandı.

Başvurulan belgeler:

- [IRSA Moving Object Search Tool (MOST)](https://irsa.ipac.caltech.edu/applications/MOST)
- [IRSA program interfaces](https://irsa.ipac.caltech.edu/voapi.html)

### SIMBAD ve Sesame (CDS, Strasbourg)

- **Durum:** Kullanılıyor
- **Kullanım amacı:** Ad çözümleme (Sesame), cisim türü, tayf türü, paralaks, öz hareket ve aynı-tür önerileri (SIMBAD TAP; CDS ve CfA aynası).
- **Adres:** <https://simbad.cds.unistra.fr/simbad/>

> This research has made use of the SIMBAD database, operated at CDS, Strasbourg, France

Metnin alındığı yer: https://simbad.cds.unistra.fr/ (Acknowledgment bölümü), 2026-11-13 tarihinde doğrulandı.

Atıf yapılacak yayınlar:

- [Wenger et al. (2000), A&AS 143, 9](https://ui.adsabs.harvard.edu/abs/2000A%26AS..143....9W)

Başvurulan belgeler:

- [CDS Sesame name resolver](https://cds.unistra.fr/cgi-bin/Sesame)

### JPL Solar System Dynamics (SBDB, Horizons)

- **Durum:** Kullanılıyor
- **Kullanım amacı:** Güneş Sistemi cisimlerinin tanımı (SBDB), SPHEREx karelerindeki öngörülen konumlar (Horizons; IRSA MOST üzerinden) ve canlı konum paneli (Horizons API: şu anki RA/Dec, seçilen şehirden yükseklik ve yön).
- **Adres:** <https://ssd.jpl.nasa.gov/>

> Solar system object data from the JPL Small-Body Database and Horizons system, NASA Jet Propulsion Laboratory.


_Not:_ Horizons sayfasında resmî bir teşekkür kalıbı bulunamadı (2026-11-13); metin bizim açıklamamızdır, alıntı değildir.

Başvurulan belgeler:

- [JPL Horizons](https://ssd.jpl.nasa.gov/horizons/)
- [JPL Small-Body Database API](https://ssd-api.jpl.nasa.gov/doc/sbdb.html)

### Vikipedi / Wikipedia ve Wikidata

- **Durum:** Kullanılıyor
- **Kullanım amacı:** Cisim bilgi panelindeki kısa açıklama (önce Türkçe, yoksa İngilizce) ve tanımlayıcılar; "Benim gökyüzümde" şehir koordinatları (Wikidata P625, config/cities_tr.json).
- **Adres:** <https://www.wikipedia.org/>
- **Lisans / koşullar:** Vikipedi metinleri CC BY-SA 4.0; Wikidata CC0.

> Short descriptions from Wikipedia (CC BY-SA 4.0) and identifiers from Wikidata (CC0).


### Gaia (ESA)

- **Durum:** Planlandı
- **Kullanım amacı:** Öz hareket ve paralaks (ESA Gaia TAP, gaiadr3.gaia_source) ve görüntü üstü Gaia kaynak katmanı (Aşama 4).
- **Adres:** <https://www.cosmos.esa.int/gaia>
- **Lisans / koşullar:** Gaia verisi CC BY-NC 3.0 IGO lisansıyla dağıtılır (https://www.cosmos.esa.int/web/gaia-users/license).

> This work has made use of data from the European Space Agency (ESA) mission Gaia (https://www.cosmos.esa.int/gaia), processed by the Gaia Data Processing and Analysis Consortium (DPAC, https://www.cosmos.esa.int/web/gaia/dpac/consortium). Funding for the DPAC has been provided by national institutions, in particular the institutions participating in the Gaia Multilateral Agreement.

Metnin alındığı yer: https://gea.esac.esa.int/archive/documentation/GDR3/Miscellaneous/sec_credit_and_citation_instructions/, 2026-11-13 tarihinde doğrulandı.

Atıf yapılacak yayınlar:

- [Gaia Collaboration et al. (2016b) — The Gaia mission](https://gea.esac.esa.int/archive/documentation/GDR3/Miscellaneous/sec_credit_and_citation_instructions/)
- [Gaia Collaboration et al. (2023j) — Gaia DR3: Summary of the contents and survey properties](https://gea.esac.esa.int/archive/documentation/GDR3/Miscellaneous/sec_credit_and_citation_instructions/)

Başvurulan belgeler:

- [Gaia data credits and acknowledgements](https://www.cosmos.esa.int/web/gaia-users/credits)

### CADC SSOIS (Solar System Object Image Search)

- **Durum:** Planlandı
- **Kullanım amacı:** Güneş Sistemi cisimleri için "bu cismi başka hangi teleskoplar görmüş" listesi; yalnızca bağlantı, dosya indirme yok (Aşama 4).
- **Adres:** <https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/ssois/>

> This research used the facilities of the Canadian Astronomy Data Centre operated by the National Research Council of Canada with the support of the Canadian Space Agency.

Metnin alındığı yer: https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/ssois/documentation.html, 2026-11-13 tarihinde doğrulandı.

Atıf yapılacak yayınlar:

- [Gwyn, Hill & Kavelaars (2012), PASP 124, 579](https://adsabs.harvard.edu/abs/2012PASP..124..579G)

Başvurulan belgeler:

- [SSOIS API documentation](https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/ssois/apidoc.html)

### NEOSSat (CSA / DRDC; veri CADC'de)

- **Durum:** Planlandı
- **Kullanım amacı:** Konuma ve tarihe göre NEOSSat görüntüleri (filtresiz optik): yalnızca konum, hareket ve zaman; SPHEREx ile parlaklık karşılaştırması yapılmaz (Aşama 4).
- **Adres:** <https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/neossat/>
- **Lisans / koşullar:** Open Government Licence – Canada (https://open.canada.ca/en/open-government-licence-canada).

> Based on data from the NEOSSat satellite, a joint mission of the Canadian Space Agency (CSA) and Defence Research and Development Canada (DRDC), with contributions from Microsat Systems Canada Inc. (MSCI), the University of Calgary, Bishop's University, and the National Research Council of Canada (NRC).

Metnin alındığı yer: https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/neossat/, 2026-11-13 tarihinde doğrulandı.

_Not:_ Lisans adı kullanıcı tarafından verildi; lisans sayfasına erişilemedi (2026-11-13, otomatik erişim reddedildi).

Başvurulan belgeler:

- [NEOSSat FITS Image User's Guide, CSA-NEOSSAT-MAN-0002 v4.00](https://data.asc-csa.gc.ca/users/OpenData_DonneesOuvertes/pub/NEOSSAT/Supporting%20Documents/CSA-NEOSSAT-MAN-0002_FITS_IMAGE_UGUIDE-v4-00.pdf)
- [CSA: NEOSSat tanıtım sayfası](https://www.asc-csa.gc.ca/eng/satellites/neossat/)
- [asc-csa/NEOSSAT_Tutorial (referans; koddan kopyalama yok)](https://github.com/asc-csa/NEOSSAT_Tutorial)

### WiseView (Caselden & Westin)

- **Durum:** Planlandı
- **Kullanım amacı:** Yalnızca dış bağlantı: "Bu cismi WISE'ta yıllar boyunca izle" (Aşama 4). Gömme yok.
- **Adres:** <https://ascl.net/1806.004>

Atıf yapılacak yayınlar:

- [Caselden, D., Westin, P. et al. (2018), WiseView, ASCL 1806.004](https://ui.adsabs.harvard.edu/abs/2018ascl.soft06004C/abstract)

Başvurulan belgeler:

- [WiseView kaynak kodu](https://github.com/backyardworlds/wiseview)

## Yazılım

### Astropy

- **Durum:** Kullanılıyor
- **Kullanım amacı:** FITS okuma, WCS, VOTable ayrıştırma, zaman dönüşümleri.
- **Adres:** <https://www.astropy.org/>
- **Lisans / koşullar:** BSD-3-Clause

Atıf yapılacak yayınlar:

- [Astropy Collaboration (2013), A&A 558, A33 — Paper I](https://ui.adsabs.harvard.edu/abs/2013A%26A...558A..33A)
- [Astropy Collaboration (2018), AJ 156, 123 — Paper II](https://ui.adsabs.harvard.edu/abs/2018AJ....156..123A)
- [Astropy Collaboration (2022), ApJ 935, 167 — Paper III](https://ui.adsabs.harvard.edu/abs/2022ApJ...935..167A)

### Açık kaynak yazılımlar

- **Durum:** Kullanılıyor
- **Kullanım amacı:** Sitenin yapımında kullanılan kütüphaneler (sürüm ve lisans, paket bilgisinden).
- **Adres:** <https://github.com/ortak6530/spherex-izleyici>

_Not:_ Arka uç: FastAPI (MIT), Uvicorn (BSD-3-Clause), NumPy (BSD-3-Clause), PyVO (BSD-3-Clause), HTTPX (BSD-3-Clause), SQLAlchemy (MIT), Alembic (MIT), Pydantic (MIT), openpyxl (MIT), Pillow (MIT-CMU), psycopg (LGPL-3.0), argon2-cffi (MIT). Ön uç: React (MIT), three.js (MIT), Framer Motion (MIT), i18next ve react-i18next (MIT), Lucide (ISC). Yazı tipleri: Inter, Exo 2, Roboto Mono (SIL OFL 1.1).
