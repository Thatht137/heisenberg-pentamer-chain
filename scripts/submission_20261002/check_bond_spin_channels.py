"""把复合矢量改写为键总自旋通道，检查算符恒等式。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.linalg import eigh

import dark_operator_expansion as dark

ROOT = dark.ROOT
OUT = ROOT / "results/novelty_20261004/bond_spin_channels_v2"


def main():
    OUT.mkdir(exist_ok=False)
    dark.reference.write_json(OUT / "protocol.json", {
        "spins":[.5,1.,1.5,2.],"identity_gate":1e-12,
        "identity":"Q_i^{z mu} T_j^mu - T_i^mu Q_j^{z mu} = {T_i.T_j,T_i^z-T_j^z}/2 + s(s+1)(T_i^z-T_j^z)/3",
        "channel_coefficient":"J^2/2 - 2s(s+1)/3 for J <-> J-1",
        "scope":"exact two-site operator algebra, not a claim that all channels occur in a chain ground state"})
    rows,checks=[],[]
    for s in (.5,1.,1.5,2.):
        d=int(2*s+1)
        m=np.arange(s,-s-1,-1)
        tz=np.diag(m)
        tp=np.diag(np.sqrt(s*(s+1)-m[1:]*(m[1:]+1)),1)
        ops=[(tp+tp.T)/2,(tp-tp.T)/(2j),tz]
        quads=[(tz@t+t@tz)/2-(s*(s+1)/3*np.eye(d) if i==2 else 0) for i,t in enumerate(ops)]
        h=sum(np.kron(t,t) for t in ops)
        delta=np.kron(tz,np.eye(d))-np.kron(np.eye(d),tz)
        composite=sum(np.kron(q,t)-np.kron(t,q) for q,t in zip(quads,ops))
        rhs=(h@delta+delta@h)/2+s*(s+1)/3*delta
        residual=float(np.linalg.norm(composite-rhs))
        assert residual<1e-12
        e,v=eigh(h)
        checks.append({"spin":s,"identity_residual":residual})
        for j in range(1,int(2*s)+1):
            ej=(j*(j+1)-2*s*(s+1))/2
            ek=((j-1)*j-2*s*(s+1))/2
            pj=v[:,abs(e-ej)<1e-9]
            pk=v[:,abs(e-ek)<1e-9]
            block=pj.conj().T@delta@pk
            target=pj.conj().T@composite@pk
            coefficient=j*j/2-2*s*(s+1)/3
            error=float(np.linalg.norm(target-coefficient*block))
            assert error<1e-12 and np.linalg.norm(block)>1e-6
            row={"spin":s,"upper_bond_spin":j,"lower_bond_spin":j-1,
                 "coefficient":coefficient,"block_residual":error,
                 "delta_block_norm_squared":float(np.linalg.norm(block)**2),
                 "q_pi_link_probe_coefficient":None}
            if s==1.5:
                _,_,_,coeff,_,_,_=dark.effective_probe()
                row["q_pi_link_probe_coefficient"]=float(-coeff[0]+coeff[1]*coefficient)
            rows.append(row)
    dark.reference.write_csv(OUT / "channels.csv",rows)
    dark.reference.write_json(OUT / "summary.json",{"all_checks_pass":True,"identity_checks":checks,
        "quartet_composite_channel_coefficients":[-2.,-.5,2.],
        "doublet_composite_coefficient":0.,"ground_state_accessibility_not_assumed":True})
    files=[Path(__file__),Path(dark.__file__),*sorted(OUT.iterdir())]
    dark.reference.write_json(OUT / "sha256.json",{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files if p.is_file()})
    print(json.dumps({"identities":checks,"channels":rows},indent=2))


if __name__=="__main__":
    main()
