"""检验两种局域自旋的同折叠动量抵消点是否构成连续分支。"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

import probe_rank_geometry as local

ROOT, reference = local.ROOT, local.reference
OUT = ROOT/"results/novelty_20261004/compensation_family"


def main():
    start=time.perf_counter()
    OUT.mkdir(exist_ok=False)
    reference.write_json(OUT/"protocol.json",{
        "Q_over_pi":[.55,1.],"points":16,
        "quartet_q":"(Q+4pi)/5","doublet_q":"(Q+2pi)/5",
        "quartet_bracket":[-2.,-.0001],"doublet_bracket":[.01,4.],
        "root_abs_gate":1e-10,"local_operator_fit_gate":1e-9,
        "threads":1,"wall_limit_seconds":60,
        "scope":"local roots and link coefficients only, not a phase diagram or a many-body weight scan"})
    rows=[]
    for reduced in np.linspace(.55,1.,16):
        for spin,offset,bracket in ((1.5,4,(-2.,-.0001)),(.5,2,(.01,4.))):
            assert time.perf_counter()-start<60
            q=(reduced+offset)*np.pi/5
            alpha=brentq(lambda a:local.amplitude(a,q),*bracket,xtol=1e-13)
            t,_,_,lc,rc,gap,error=local.local_probe(alpha,q)
            derivative=(local.amplitude(alpha+1e-5,q)-local.amplitude(alpha-1e-5,q))/2e-5
            gamma=lc[0]*np.exp(-5j*q)+rc[0]*np.exp(5j*q)
            residual=abs(local.amplitude(alpha,q))
            assert (len(t["z"])-1)/2==spin and residual<1e-10 and error<1e-9 and gap>0 and abs(derivative)>1e-6
            rows.append({"spin":spin,"Q_over_pi":float(reduced),"q_over_pi":float(q/np.pi),
                "alpha_root":float(alpha),"local_gap":gap,"root_residual":residual,
                "A_prime":float(derivative),"quadrupole_coefficient_abs":float(abs(lc[1])),
                "scalar_gamma_real":float(gamma.real),"scalar_gamma_imag":float(gamma.imag),
                "doublet_operator_retuning_kappa":float(-gamma.real/derivative) if spin==.5 else None,
                "operator_fit_error":error})
    reference.write_csv(OUT/"roots.csv",rows)
    reference.write_json(OUT/"summary.json",{"all_checks_pass":True,"points":len(rows),
        "min_quartet_quadrupole_coefficient":min(r["quadrupole_coefficient_abs"] for r in rows if r["spin"]==1.5),
        "max_doublet_quadrupole_coefficient":max(r["quadrupole_coefficient_abs"] for r in rows if r["spin"]==.5),
        "max_root_error":max(r["root_residual"] for r in rows),
        "min_local_gap":min(r["local_gap"] for r in rows),
        "many_body_residual_claim":False,"elapsed_seconds":time.perf_counter()-start})
    files=[Path(__file__),Path(local.__file__),*sorted(OUT.iterdir())]
    reference.write_json(OUT/"sha256.json",{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files if p.is_file()})
    print((OUT/"summary.json").read_text())


if __name__=="__main__":
    main()
