"""在相同周期几何上比较局域自旋秩，不混用开链与环。"""

from __future__ import annotations

import hashlib
from pathlib import Path

import dark_operator_expansion as dark
import numpy as np
from scipy.linalg import eigh
from scipy.optimize import brentq

reference, ROOT = dark.reference, dark.ROOT
OUT = ROOT / "results/novelty_20261004/rank_geometry_probe"


def local_probe(alpha,q):
    half={"x":np.array([[0,1],[1,0]])/2,"y":np.array([[0,-1j],[1j,0]])/2,"z":np.diag([.5,-.5])}
    spins={a:[reference.site_operator(op,i) for i in range(5)] for a,op in half.items()}
    h=sum(c*spins[a][i]@spins[a][i+1] for i,c in enumerate((alpha,1,1,alpha)) for a in half)
    e,u=eigh(h)
    d=int(np.count_nonzero(abs(e-e[0])<1e-10))
    s=(d-1)/2
    p=u[:,:d]
    _,r=eigh(p.conj().T@sum(spins["z"])@p)
    states=[p@r[:,-1]]
    lower=sum(spins["x"])-1j*sum(spins["y"])
    for m in np.arange(s,-s,-1):
        states.append(lower@states[-1]/np.sqrt(s*(s+1)-m*(m-1)))
    u=np.column_stack((*states,u[:,d:]))
    ops={a:[u.conj().T@op@u for op in values] for a,values in spins.items()}
    t={a:sum(values)[:d,:d] for a,values in ops.items()}
    quad={a:(t["z"]@ta+ta@t["z"])/2-(s*(s+1)/3*np.eye(d) if a=="z" else 0) for a,ta in t.items()}
    b=sum(np.exp(1j*q*(i-2))*op for i,op in enumerate(ops["z"]))
    unit=np.eye(32)[:,:d]
    v=sum(np.kron(ops[a][4][:,:d],ops[a][0][:,:d]) for a in t)
    gaps=(e[:,None]+e[None,:]-2*e[0]).ravel()
    inv=np.zeros_like(gaps)
    inv[gaps>1e-10]=1/gaps[gaps>1e-10]
    rv=inv[:,None]*v
    kl=-np.kron(b[:d,:],unit.T)@rv-rv.conj().T@np.kron(b[:,:d],unit)
    kr=-np.kron(unit.T,b[:d,:])@rv-rv.conj().T@np.kron(unit,b[:,:d])
    lbase=[np.kron(np.eye(d),t["z"]),sum(np.kron(quad[a],t[a]) for a in t)]
    rbase=[np.kron(t["z"],np.eye(d)),sum(np.kron(t[a],quad[a]) for a in t)]
    if d==2:
        lbase,rbase=lbase[:1],rbase[:1]
    lc=np.linalg.lstsq(np.column_stack([b.ravel() for b in lbase]),kl.ravel(),rcond=None)[0]
    rc=np.linalg.lstsq(np.column_stack([b.ravel() for b in rbase]),kr.ravel(),rcond=None)[0]
    error=max(np.linalg.norm(kl-sum(c*b for c,b in zip(lc,lbase))),np.linalg.norm(kr-sum(c*b for c,b in zip(rc,rbase))))
    assert error<1e-10 and np.linalg.norm(b[:d,:d])<1e-10
    if d==2:
        lc,rc=np.append(lc,0),np.append(rc,0)
    return t,quad,float(ops["z"][0][0,0].real/s),lc,rc,float(e[d]-e[0]),float(error)


def amplitude(alpha,q):
    cell,_,_=reference.local_projection(alpha,np.linspace(0,2*np.pi,41))
    return float(np.dot(cell["c"],np.cos(q*(np.arange(5)-2))))


def geometry(alpha,q,count):
    t,quad,c1,lc,rc,gap,error=local_probe(alpha,q)
    d=len(t["z"])
    def embed(op,i):
        return np.kron(np.kron(np.eye(d**i),op),np.eye(d**(count-i-1)))
    spins={a:[embed(op,i) for i in range(count)] for a,op in t.items()}
    quads={a:[embed(op,i) for i in range(count)] for a,op in quad.items()}
    h=np.zeros((d**count,d**count),complex)
    k=h.copy()
    phases=np.exp(5j*q*np.arange(count))
    assert abs(np.exp(5j*q*count)-1)<1e-10
    dop=sum(phases[i]*spins["z"][i] for i in range(count))/np.sqrt(5*count)
    for i in range(count):
        j=(i+1)%count
        h+=c1**2*sum(spins[a][i]@spins[a][j] for a in t)
        k+=phases[i]*(lc[0]*spins["z"][j]+lc[1]*sum(quads[a][i]@spins[a][j] for a in t))
        k+=phases[j]*(rc[0]*spins["z"][i]+rc[1]*sum(spins[a][i]@quads[a][j] for a in t))
    k/=np.sqrt(5*count)
    indices=np.arange(d**count)
    mz=sum((d-1)/2-(indices//d**i)%d for i in range(count))
    target=.5 if count%2 else 0.
    ids=np.flatnonzero(abs(mz-target)<1e-10)
    h,k,dop=[op[np.ix_(ids,ids)] for op in (h,k,dop)]
    e,v=eigh(h)
    ng=int(np.count_nonzero(abs(e-e[0])<1e-10))
    ground=v[:,:ng]
    ds=dop@ground
    ks=k@ground
    ds-=ground@(ground.conj().T@ds)
    ks-=ground@(ground.conj().T@ks)
    dd=float(np.vdot(ds,ds).real/ng)
    kk=float(np.vdot(ks,ks).real/ng)
    dk=np.vdot(ds,ks)/ng
    lam=dk.real/dd
    residual=float(np.linalg.norm(ks-lam*ds)**2/ng)
    derivative=(amplitude(alpha+1e-5,q)-amplitude(alpha-1e-5,q))/2e-5
    return {"spin":(d-1)/2,"cells":count,"boundary":"PBC","alpha":float(alpha),
            "q_over_pi":float(q/np.pi),"target_sz":target,"ground_degeneracy_in_sector":ng,
            "sector_dim":len(ids),"local_gap":gap,"operator_fit_error":error,
            "W_fixed_over_beta2":kk,"W_min_over_beta2":residual,"W_D":dd,
            "lambda_real":float(lam),"lambda_imag":float(dk.imag/dd),
            "amplitude_derivative":float(derivative),"kappa":float(-lam/derivative),
            "quadrupole_coefficient_abs":float(abs(lc[1]))}


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    reference.write_json(OUT/"protocol.json",{
        "exploratory":True,"purpose":"avoid comparing exponents across different boundary conditions",
        "cells":3,"boundary":"PBC","sector":"Sz=1/2; equal average of degenerate ground states",
        "quartet_q_over_pi":14/15,"doublet_q_over_pi":8/15,
        "effective_q_mod_2pi":"2pi/3 for both","wall_limit_seconds":60,"threads":1,
        "scope":"odd ring is frustrated, not a bulk-chain extrapolation"})
    cases=[(14*np.pi/15,(-2.,-.0001)),(8*np.pi/15,(1.,4.))]
    rows=[]
    for q,bracket in cases:
        alpha=brentq(lambda a:amplitude(a,q),*bracket,xtol=1e-13)
        row=geometry(alpha,q,3)
        rows.append(row)
        print(row,flush=True)
    reference.write_json(OUT/"summary.json",{"cases":rows,"bulk_claim":False})
    reference.write_json(OUT/"sha256.json",{
        str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__),Path(reference.__file__)] + sorted(OUT.iterdir()) if p.is_file()})


if __name__=="__main__":
    main()
