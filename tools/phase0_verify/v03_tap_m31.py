"""Phase 0 verification: SPHEREx obscore rows covering M31 (RA/Dec from Sesame later)."""

import collections
import time
import pyvo
from astropy.time import Time

RA, DEC = 10.684708, 41.268750  # M31 nucleus (approx., J2000); refined via Sesame in v05
svc = pyvo.dal.TAPService("https://irsa.ipac.caltech.edu/TAP")

q = f"""
SELECT obs_id, obs_collection, energy_bandpassname, em_min, em_max, t_min, t_max, t_exptime,
       calib_level, dataproduct_type, access_url, access_format, access_estsize,
       s_pixel_scale, s_xel1, s_xel2, target_name, obs_release_date, obs_creation_date,
       algorithm_name, target_moving
FROM spherex.obscore
WHERE CONTAINS(POINT('ICRS', {RA}, {DEC}), s_region) = 1
"""
t0 = time.time()
tab = svc.run_sync(q).to_table()
print(f"rows={len(tab)}  query_time={time.time() - t0:.1f}s")
print("collections:", collections.Counter(str(x) for x in tab["obs_collection"]))
print("dataproduct_type:", collections.Counter(str(x) for x in tab["dataproduct_type"]))
print("calib_level:", collections.Counter(int(x) for x in tab["calib_level"]))
print("bands:", sorted(collections.Counter(str(x) for x in tab["energy_bandpassname"]).items()))
print("algorithm_name:", collections.Counter(str(x) for x in tab["algorithm_name"]))
print("target_moving:", collections.Counter(str(x) for x in tab["target_moving"]))
print("access_format:", collections.Counter(str(x) for x in tab["access_format"]))

tab.sort("t_min")
tmin = Time(tab["t_min"], format="mjd")
print("first obs:", tmin[0].iso, " last obs:", tmin[-1].iso)
# Group observation days to reveal survey visits
days = collections.Counter(t.strftime("%Y-%m") for t in tmin.datetime)
print("obs per month:", sorted(days.items()))

for col in ["em_min", "em_max"]:
    print(col, "range (um):", float(tab[col].min()) * 1e6, float(tab[col].max()) * 1e6)
print("pixel scale:", set(float(x) for x in tab["s_pixel_scale"]))
print("naxis:", set((int(a), int(b)) for a, b in zip(tab["s_xel1"], tab["s_xel2"])))
est = tab["access_estsize"]
print("est size kB: masked", int(getattr(est, "mask", [False]).sum()), "of", len(est))
print("\nsample rows:")
for r in tab[:3]:
    print({k: (str(r[k])[:140]) for k in tab.colnames})
tab.write("data/m31_obscore.ecsv", format="ascii.ecsv", overwrite=True)
