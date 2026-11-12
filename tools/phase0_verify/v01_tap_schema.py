"""Phase 0 verification: IRSA TAP schema for SPHEREx tables."""

import sys
import numpy, astropy, pyvo, astroquery

print(
    "python",
    sys.version.split()[0],
    "| numpy",
    numpy.__version__,
    "| astropy",
    astropy.__version__,
    "| pyvo",
    pyvo.__version__,
    "| astroquery",
    astroquery.__version__,
)

svc = pyvo.dal.TAPService("https://irsa.ipac.caltech.edu/TAP")
q = "SELECT table_name, description FROM TAP_SCHEMA.tables WHERE LOWER(table_name) LIKE '%spherex%'"
res = svc.run_sync(q).to_table()
for r in res:
    print(r["table_name"], "|", str(r["description"])[:160])
