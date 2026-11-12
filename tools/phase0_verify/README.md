# Faz 0 canlı doğrulama betikleri

Bu betikler `docs/DATA_SOURCES.md` dosyasındaki bulguları üretti (2026-11-12). Uygulamanın parçası değiller, yalnızca yeniden doğrulama için duruyorlar.

## Çalıştırma

Python 3.13 ile, betikler bir çalışma klasöründen çalıştırılır (betikler `data/` alt klasörüne yazar):

```powershell
mkdir $env:TEMP\spx-verify\data -Force; Set-Location $env:TEMP\spx-verify
py -3.13 -X utf8 "<repo>\tools\phase0_verify\v01_tap_schema.py"
```

## Sıra ve bağımlılıklar

- `v03_tap_m31.py`, `data/m31_obscore.ecsv` dosyasını üretir. `v04` ve `v14` bu dosyayı kullanır.
- `v05_cutout.py`, `data/m31_cutout_D4.fits` dosyasını üretir. `v06` ve `v16` bu dosyayı kullanır.
- `pdftext.py`, yalnızca standart kütüphaneyle PDF'ten metin çıkarır (Explanatory Supplement için): `py -3.13 pdftext.py in.pdf out.txt`
- `html2text.py`, indirilen HTML sayfalarını düz metne çevirir.

## Gerekli paketler

astropy, pyvo, astroquery, numpy, requests, certifi.
