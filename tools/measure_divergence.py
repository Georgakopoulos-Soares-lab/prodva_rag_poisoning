#!/usr/bin/env python
"""Claim B, reframed: how much does the poisoned protein DIFFER from the clean protein for
the same (request, seed)? No exact-match requirement, no collateral penalty -- every change
is a meaningful corruption. Requires the paired (per-prompt reseed) generations so that a
non-captured request is bit-identical in both conditions (difference = pure poison effect).
"""
import json, glob, difflib, argparse, pathlib, statistics as st

ROOT = pathlib.Path(__file__).resolve().parents[1]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob_clean",  default=str(ROOT/"runs/attack_fast_eval/gen_clean_s*.json"))
    ap.add_argument("--glob_poison", default=str(ROOT/"runs/attack_fast_eval/gen_poison_s*.json"))
    ap.add_argument("--payload",     default=str(ROOT/"artifacts/attack/payload.json"))
    ap.add_argument("--p16",         default=str(ROOT/"runs/attack/poison_at16_eval.json"))
    ap.add_argument("--testfile",    default=str(ROOT/"artifacts/attack/targets_eval_as_test.json"))
    args = ap.parse_args()

    frag = json.load(open(args.payload))["signature_fragment"]
    tid_by_inst = {r["instruction"]: r["target_id"] for r in json.load(open(args.testfile))}
    captured = {r["target_id"]: (r["poison_rank"] is not None)
                for r in json.load(open(args.p16))["rows"]}

    def load(pat):
        d = {}
        for fp in sorted(glob.glob(pat)):
            s = fp.split("_s")[-1].split(".")[0]
            for r in json.load(open(fp)):
                d[(tid_by_inst[r["instruction"]], s)] = r["prediction"].strip()
        return d
    clean, pois = load(args.glob_clean), load(args.glob_poison)

    per_target = {}
    changed = tot = 0
    cap_changed = cap_tot = noncap_changed = noncap_tot = 0
    divs = []; toward = 0
    for k, p in pois.items():
        c = clean.get(k, "")
        tot += 1
        ch = (p != c)
        div = 1 - difflib.SequenceMatcher(None, c, p).ratio()
        changed += ch; divs.append(div)
        sim_p = difflib.SequenceMatcher(None, p, frag).ratio()
        sim_c = difflib.SequenceMatcher(None, c, frag).ratio()
        tw = sim_p > sim_c + 0.05
        toward += tw
        tid = k[0]
        d = per_target.setdefault(tid, {"n":0,"changed":0,"div":[],"toward":0,"cap":captured.get(tid)})
        d["n"]+=1; d["changed"]+=ch; d["div"].append(div); d["toward"]+=tw
        if captured.get(tid): cap_tot+=1; cap_changed+=ch
        else:                 noncap_tot+=1; noncap_changed+=ch

    print(f"paired generations: {tot} (30 targets x 8 seeds)\n")
    print("==== CORRUPTION REACH (any change vs clean, per request x seed) ====")
    print(f"ALL requests            : {changed}/{tot} = {changed/max(tot,1):.2f}")
    print(f"  captured requests     : {cap_changed}/{cap_tot} = {cap_changed/max(cap_tot,1):.2f}")
    print(f"  non-captured requests : {noncap_changed}/{noncap_tot} = {noncap_changed/max(noncap_tot,1):.2f}"
          f"   (should be ~0 with correct pairing)")
    print(f"mean divergence (0=identical,1=different): {st.mean(divs):.3f}")
    nz=[d for d in divs if d>0.001]
    if nz: print(f"among changed: median divergence={st.median(nz):.2f}")
    print(f"moved toward payload domain vs clean     : {toward}/{tot} = {toward/tot:.2f}")

    print("\n==== per target (fraction of 8 seeds changed) ====")
    print(f"{'target':16s} {'captured':9s} {'changed':8s} {'mean_div':9s} {'toward_payload'}")
    for tid in sorted(per_target):
        d=per_target[tid]
        print(f"{tid:16s} {str(d['cap']):9s} {d['changed']/d['n']:<8.2f} "
              f"{st.mean(d['div']):<9.2f} {d['toward']/d['n']:.2f}")

if __name__ == "__main__":
    main()
