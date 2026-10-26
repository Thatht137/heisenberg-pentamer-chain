"""以同一十五自旋周期几何检验双重态与四重态的阶数差别。"""

from __future__ import annotations

import hashlib
import itertools
import json
import time
from pathlib import Path

import validate_dark_multicell as original
import numpy as np
from scipy.sparse.linalg import LinearOperator, eigsh

reference, ROOT = original.reference, original.ROOT
OUT = ROOT / "results/novelty_20261004/same_ring_microscopic"


def main():
    start=time.perf_counter()
    OUT.mkdir(parents=True,exist_ok=False)
    source_path=ROOT/"results/novelty_20261004/rank_geometry_probe/summary.json"
    cases=json.loads(source_path.read_text())["cases"]
    reference.write_json(OUT/"protocol.json",{
        "L":15,"cells":3,"boundary":"PBC","total_sz":.5,
        "g_values":[.005,.01,.02,.04],"ground_state_average":"two degenerate Sz=1/2 ground states",
        "elastic_part":"exclude the entire ground eigenspace, not only each diagonal expectation",
        "low_window":"0<omega<Delta_local_at_root/2",
        "hypothesis":"after linear retuning quartet O(beta^2), doublet O(beta^4) or smaller",
        "first_three_quartet_slope_range":[1.8,2.2],"first_three_doublet_slope_range":[3.7,4.3],
        "quartet_smallest_coefficient_error_gate":.05,"eigen_residual_gate":1e-10,
        "threads":1,"wall_limit_seconds":600,
        "scope":"same finite frustrated odd ring; not direct evidence for an infinite unfrustrated chain",
        "cases":cases})
    states=np.array([sum(1<<i for i in inds) for inds in itertools.combinations(range(15),8)])
    sz=np.column_stack([((states>>i)&1)-.5 for i in range(15)])
    rows,lines=[],[]
    for case in cases:
        alpha,q=case["alpha"],case["q_over_pi"]*np.pi
        h0=original.sector_matrix(15,8,original.bonds(15,alpha,0))
        hb=original.sector_matrix(15,8,[(i,(i+1)%15,1.) for i in (4,9,14)])
        ha=original.sector_matrix(15,8,[(i,i+1,1.) for i in range(14) if i%5 in (0,3)])
        op=sz@np.exp(1j*q*np.arange(15))/np.sqrt(15)
        count=case["sector_dim"]
        for g in (.005,.01,.02,.04):
            beta=g*case["local_gap"]
            for mode in ("fixed","retuned"):
                shift=case["kappa"]*beta if mode=="retuned" else 0.
                h=h0+beta*hb+shift*ha
                def matvec(x):
                    if time.perf_counter()-start>600:
                        raise TimeoutError("达到同几何微观对照时间边界")
                    return h@x
                e,v=eigsh(LinearOperator(h.shape,matvec=matvec,dtype=np.float64),k=count+4,
                          which="SA",tol=1e-13,ncv=max(50,3*(count+4)),maxiter=5000,
                          v0=np.random.default_rng(20261007).normal(size=len(states)))
                order=np.argsort(e)
                e,v=e[order],v[:,order]
                gaps=e-e[0]
                errors=np.linalg.norm(h@v-v*e,axis=0)
                ng=int(np.count_nonzero(abs(gaps)<1e-9))
                low=(gaps>1e-9)&(gaps<case["local_gap"]/2)
                ground=v[:,:ng]
                sources=op[:,None]*ground
                weights=np.sum(abs(v.T@sources)**2,axis=1)/ng
                w=float(weights[low].sum())
                row={"spin":case["spin"],"g":g,"mode":mode,"alpha":float(alpha+shift),"beta":beta,
                     "W_low":w,"W_over_beta2":w/beta**2,"W_over_beta4":w/beta**4,
                     "predicted_W_over_beta2":case["W_min_over_beta2"] if mode=="retuned" else case["W_fixed_over_beta2"],
                     "ground_multiplicity_in_sector":ng,"low_excitations":int(low.sum()),
                     "max_residual":float(errors.max()),"ground_splitting":float(gaps[1]),
                     "next_state":float(gaps[count]),
                     "numeric_pass":bool(ng==2 and low.sum()==count-2 and errors.max()<1e-10),
                     "elapsed_seconds":time.perf_counter()-start}
                rows.append(row)
                lines.extend({"spin":case["spin"],"g":g,"mode":mode,"level":i,
                              "omega":float(gaps[i]),"weight":float(weights[i]),"residual":float(errors[i])}
                             for i in range(count+4))
                reference.write_csv(OUT/"comparisons.csv",rows)
                reference.write_csv(OUT/"spectral_lines.csv",lines)
                print(row,flush=True)
    slopes={}
    for spin in (1.5,.5):
        selected=[r for r in rows if r["spin"]==spin and r["mode"]=="retuned"][:3]
        slopes[str(spin)]=float(np.polyfit(np.log([r["beta"] for r in selected]),np.log([r["W_low"] for r in selected]),1)[0])
    first=next(r for r in rows if r["spin"]==1.5 and r["mode"]=="retuned")
    coefficient_error=abs(first["W_over_beta2"]/first["predicted_W_over_beta2"]-1)
    passed=all(r["numeric_pass"] for r in rows) and 1.8<slopes["1.5"]<2.2 and 3.7<slopes["0.5"]<4.3 and coefficient_error<.05
    reference.write_json(OUT/"summary.json",{"all_gates_pass":passed,"retuned_slopes_first_three":slopes,
                         "quartet_smallest_coefficient_error":coefficient_error,
                         "elapsed_seconds":time.perf_counter()-start,"bulk_claim":False})
    reference.write_json(OUT/"sha256.json",{
        str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__),Path(original.__file__),Path(reference.__file__),source_path,
                  ROOT/"scripts/autoresearch_v5/analyze_negative_phase_independent_observables.py"]
        +sorted(OUT.iterdir()) if p.is_file()})
    if not passed:
        raise SystemExit(1)


if __name__=="__main__":
    main()
