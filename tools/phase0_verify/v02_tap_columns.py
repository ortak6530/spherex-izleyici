"""Phase 0 verification: column lists for SPHEREx TAP tables."""

import pyvo

svc = pyvo.dal.TAPService("https://irsa.ipac.caltech.edu/TAP")
for t in [
    "spherex.obscore",
    "spherex.observation",
    "spherex.plane",
    "spherex.artifact",
    "spherex.provenance_input",
]:
    q = (
        f"SELECT column_name, datatype, unit, description FROM TAP_SCHEMA.columns "
        f"WHERE table_name = '{t}' ORDER BY column_index"
    )
    res = svc.run_sync(q).to_table()
    print(f"\n=== {t} ({len(res)} columns) ===")
    for r in res:
        print(
            f"  {r['column_name']:<28} {str(r['datatype']):<10} {str(r['unit']):<8} {str(r['description'])[:110]}"
        )
