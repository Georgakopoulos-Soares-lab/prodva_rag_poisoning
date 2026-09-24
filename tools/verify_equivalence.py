#!/usr/bin/env python
"""Prove the fast harness is correctness-preserving: its outputs must be BIT-IDENTICAL to
the dvagen-eval reference for every (condition, seed) where a reference exists."""
import json, argparse, pathlib, glob

ROOT = pathlib.Path(__file__).resolve().parents[1]

def key(rows):
    return {r["instruction"]: (r["prediction"], json.dumps(r["ids"])) for r in rows}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref_dir",  default=str(ROOT/"runs/attack"))       # dvagen eval reference
    ap.add_argument("--fast_dir", default=str(ROOT/"runs/attack_fast"))  # fast driver
    args = ap.parse_args()
    n_cmp = n_ok = n_mismatch = 0
    for fast in sorted(glob.glob(f"{args.fast_dir}/gen_*_s*.json")):
        name = pathlib.Path(fast).name
        ref = pathlib.Path(args.ref_dir)/name
        if not ref.exists():
            print(f"  (no reference for {name}; skip)"); continue
        n_cmp += 1
        fk, rk = key(json.load(open(fast))), key(json.load(open(ref)))
        mism = [inst for inst in rk if fk.get(inst) != rk.get(inst)]
        if not mism and set(fk)==set(rk):
            n_ok += 1; print(f"  IDENTICAL: {name}  ({len(rk)} generations)")
        else:
            n_mismatch += 1; print(f"  MISMATCH : {name}  ({len(mism)} differing of {len(rk)})")
    print(f"\ncompared={n_cmp}  identical={n_ok}  mismatch={n_mismatch}")
    print("RESULT:", "EQUIVALENT (optimizations preserve correctness)" if n_cmp and n_mismatch==0
          else "NEEDS REVIEW")

if __name__ == "__main__":
    main()
