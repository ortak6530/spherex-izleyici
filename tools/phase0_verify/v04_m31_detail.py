"""Phase 0 verification: QR2 vs QR3 split, datalink resolution for one M31 image."""

import collections
import pyvo
from astropy.table import Table
from astropy.time import Time

tab = Table.read("data/m31_obscore.ecsv", format="ascii.ecsv")
tab["month"] = [t.strftime("%Y-%m") for t in Time(tab["t_min"], format="mjd").datetime]
for coll in sorted(set(tab["obs_collection"])):
    sub = tab[tab["obs_collection"] == coll]
    print(coll, "rows", len(sub), "months", sorted(collections.Counter(sub["month"]).items()))
    print(
        "   creation dates:",
        sorted(set(str(x)[:10] for x in sub["obs_creation_date"]))[:3],
        "...",
        sorted(set(str(x)[:10] for x in sub["obs_creation_date"]))[-3:],
    )
    print(
        "   release dates:",
        sorted(set(str(x)[:10] for x in sub["obs_release_date"]))[:2],
        "...",
        sorted(set(str(x)[:10] for x in sub["obs_release_date"]))[-2:],
    )
    print("   access_url ex:", sub["access_url"][0])
    print("   obs_id ex:", sub["obs_id"][0], "| target_name:", sub["target_name"][0])

# Same obs_id in both releases?
ids = collections.defaultdict(set)
for r in tab:
    ids[str(r["obs_id"])].add(str(r["obs_collection"]))
print("obs_ids in both collections:", sum(1 for v in ids.values() if len(v) > 1), "of", len(ids))

# Per (band) list of distinct visits
print("\nexposures per month per band:")
for b in sorted(set(tab["energy_bandpassname"])):
    sub = tab[tab["energy_bandpassname"] == b]
    print(" ", b, sorted(collections.Counter(sub["month"]).items()))

# Datalink for one QR2 and one QR3 row
for coll in sorted(set(tab["obs_collection"])):
    row = tab[tab["obs_collection"] == coll][0]
    print(f"\n--- datalink for {coll} {row['obs_id']} ---")
    dl = pyvo.dal.adhoc.DatalinkResults.from_result_url(str(row["access_url"]))
    for d in dl:
        print(
            f"  semantics={d.semantics!s:<14} type={d['content_type']!s:<30} "
            f"len={d['content_length']!s:<10} desc={str(d['description'])[:60]!s:<60} url={d.access_url}"
        )
