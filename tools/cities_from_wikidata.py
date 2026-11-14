"""Print config/cities_tr.json content: Turkish cities with coordinates from Wikidata (P625).

Usage (from the repo root):
    backend\\.venv\\Scripts\\python.exe tools\\cities_from_wikidata.py > %TEMP%\\cities.json
One SPARQL query (query.wikidata.org): for each name, the item in Turkey (P17 = Q43) with that Turkish
label, a coordinate and a population, that is not a province (Q48336) - the most populous one.
The script only prints (project rule: files change only through the editor tools); every row keeps
its QID so the coordinate can be checked at https://www.wikidata.org/wiki/<QID>.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import urllib.parse
import urllib.request

NAMES = [
    "İstanbul", "Ankara", "İzmir", "Bursa", "Antalya", "Adana", "Konya", "Gaziantep", "Şanlıurfa",
    "Kayseri", "Mersin", "Diyarbakır", "Samsun", "Eskişehir", "Trabzon", "Erzurum", "Van", "Malatya",
    "Denizli", "Sivas", "Edirne", "Çanakkale", "Muğla", "Kars",
]
SPARQL = "https://query.wikidata.org/sparql"
UA = {"User-Agent": "SPHEREx-Gokyuzu-Izleyici/0.1 (cities list builder)", "Accept": "application/sparql-results+json"}
QUERY = """
SELECT ?name ?item ?coord ?pop WHERE {
  VALUES ?name { %s }
  ?item rdfs:label ?name; wdt:P17 wd:Q43; wdt:P625 ?coord; wdt:P1082 ?pop.
  FILTER NOT EXISTS { ?item wdt:P31 wd:Q48336 }
}
"""


def main() -> int:
    values = " ".join(f'"{n}"@tr' for n in NAMES)
    url = SPARQL + "?" + urllib.parse.urlencode({"query": QUERY % values, "format": "json"})
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 - fixed https URL
        rows = json.load(r)["results"]["bindings"]
    best: dict[str, dict] = {}
    for b in rows:
        name, pop = b["name"]["value"], float(b["pop"]["value"])
        lon, lat = b["coord"]["value"].removeprefix("Point(").removesuffix(")").split()
        if name not in best or pop > best[name]["_pop"]:
            best[name] = {"name": name, "lat": round(float(lat), 4), "lon": round(float(lon), 4),
                          "wikidata": b["item"]["value"].rsplit("/", 1)[-1], "_pop": pop}
    cities = []
    for n in NAMES:
        if n in best:
            cities.append({k: v for k, v in best[n].items() if k != "_pop"})
        else:
            print(f"# not found: {n}", file=sys.stderr)
    doc = {
        "_comment": "Cities for 'Benim gökyüzümde'. Coordinates from Wikidata P625 (see each QID); "
        "printed by tools/cities_from_wikidata.py. Height is ignored (sea level).",
        "retrieved": dt.date.today().isoformat(),
        "source": "Wikidata (CC0)",
        "cities": cities,
    }
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
