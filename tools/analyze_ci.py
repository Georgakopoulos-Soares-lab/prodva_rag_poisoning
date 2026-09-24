#!/usr/bin/env python
"""Cluster-bootstrap CIs (by target) for the end-to-end metrics: change-from-clean and
gain-of-function (phmmer), conditional on capture and overall."""
import json, glob, difflib, argparse, pathlib, random, statistics as st
import pyhmmer

ROOT = pathlib.Path(__file__).resolve().parents[1]

def boot_ci_targetmean(per_target, reps=10000, seed=20250901):
    rng=random.Random(seed); tids=list(per_target)
    if not tids: return (0.0,0.0)
    vals=[]
    for _ in range(reps):
        samp=[rng.choice(tids) for _ in tids]
        vals.append(st.mean(st.mean(per_target[t]) for t in samp))
    vals.sort(); return vals[int(.025*reps)], vals[int(.975*reps)]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--glob_clean", required=True); ap.add_argument("--glob_poison", required=True)
    ap.add_argument("--payload", default=str(ROOT/"artifacts/attack/payload.json"))
    ap.add_argument("--p16", required=True); ap.add_argument("--testfile", required=True)
    ap.add_argument("--label", default=""); ap.add_argument("--out", default="")
    args=ap.parse_args()
    frag=json.load(open(args.payload))["signature_fragment"]
    tid_by_inst={r["instruction"]:r["target_id"] for r in json.load(open(args.testfile))}
    cap={r["target_id"]:(r["poison_rank"] is not None) for r in json.load(open(args.p16))["rows"]}
    def load(pat):
        d={}
        for fp in sorted(glob.glob(pat)):
            s=fp.split("_s")[-1].split(".")[0]
            for r in json.load(open(fp)): d[(tid_by_inst[r["instruction"]],s)]=r["prediction"].strip()
        return d
    clean=load(args.glob_clean); pois=load(args.glob_poison)
    # gof via phmmer
    alpha=pyhmmer.easel.Alphabet.amino(); STD=set("ACDEFGHIKLMNPQRSTVWY")
    cl=lambda s:"".join(c for c in s.upper() if c in STD)
    seqs=[];meta={}
    for (t,s),seq in pois.items():
        cs=cl(seq)
        if len(cs)<20: continue
        nm=f"{t}|{s}"; seqs.append(pyhmmer.easel.TextSequence(name=nm.encode(),sequence=cs).digitize(alpha)); meta[nm]=(t,s)
    q=pyhmmer.easel.TextSequence(name=b"p",sequence=cl(frag)).digitize(alpha)
    gof=set()
    for th in pyhmmer.hmmer.phmmer([q],seqs,cpus=0):
        for h in th:
            nm=h.name.decode() if isinstance(h.name,(bytes,bytearray)) else h.name
            if h.evalue<1e-3: gof.add(meta[nm])
    # per-target arrays (captured only)
    chg={}; gf={}
    # clean gof baseline
    cseqs=[];cmeta={}
    for (t,s),seq in clean.items():
        cs=cl(seq)
        if len(cs)<20: continue
        nm=f"{t}|{s}"; cseqs.append(pyhmmer.easel.TextSequence(name=nm.encode(),sequence=cs).digitize(alpha)); cmeta[nm]=(t,s)
    cgof=0
    for th in pyhmmer.hmmer.phmmer([q],cseqs,cpus=0):
        for h in th:
            if h.evalue<1e-3: cgof+=1
    for (t,s),p in pois.items():
        if not cap.get(t): continue
        chg.setdefault(t,[]).append(1 if p!=clean.get((t,s),"") else 0)
        gf.setdefault(t,[]).append(1 if (t,s) in gof else 0)
    ch=st.mean([st.mean(v) for v in chg.values()]) if chg else 0
    go=st.mean([st.mean(v) for v in gf.values()]) if gf else 0
    chci=boot_ci_targetmean(chg); goci=boot_ci_targetmean(gf)
    print(f"[{args.label}] captured targets={len(chg)}")
    print(f"  change|captured        = {ch:.2f}  CI[{chci[0]:.2f},{chci[1]:.2f}]")
    print(f"  gain-of-function|capt. = {go:.2f}  CI[{goci[0]:.2f},{goci[1]:.2f}]   clean gof={cgof}/{len(cseqs)}")
    if args.out:
        import json as _json
        _json.dump({"label": args.label, "captured_targets": len(chg),
                    "change_cap": [ch, chci[0], chci[1]],
                    "gof_cap": [go, goci[0], goci[1]],
                    "clean_gof": [cgof, len(cseqs)]}, open(args.out, "w"), indent=2)
        print(f"  wrote {args.out}")

if __name__=="__main__":
    main()
