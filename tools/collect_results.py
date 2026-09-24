#!/usr/bin/env python
"""Gather the final n=100 numbers into a single JSON that the figure scripts read.
Pulls retrieval capture + universal budget sweep from attack_analysis_100.json, distinct/random
capture (with bootstrap CI) from the p16 row files, and downstream change/gain-of-function from
the analyze_ci outputs. Pure aggregation -- no recomputation of scientific quantities."""
import json, random, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]; R = ROOT/"runs/attack"

def boot_ci(flags, reps=10000, seed=1):
    rng = random.Random(seed); n = len(flags)
    if n == 0: return [0.0, 0.0, 0.0]
    vals = [sum(flags[rng.randrange(n)] for _ in range(n))/n for _ in range(reps)]
    vals.sort(); return [sum(flags)/n, vals[int(.025*reps)], vals[int(.975*reps)]]

def p16_rate(path):
    rows = json.load(open(path))["rows"]
    return boot_ci([1 if r["poison_rank"] is not None else 0 for r in rows])

def main():
    aa = json.load(open(R/"attack_analysis_100.json"))
    out = {"n_queries": aa["n_queries"], "ms": aa["ms"], "retrieval": {}, "sweep": {}, "downstream": {}}
    for style in ("templated", "free_text"):
        s = aa["styles"][style]
        out["retrieval"][style] = {
            "bar": s["bar_median"],
            "targeted_neardup": s["attackT_neardup"],           # [rate, lo, hi]
            "universal_m1500": s["attackU"][-1],                 # [rate, lo, hi] at m=1500
        }
        out["sweep"][style] = s["attackU"]                       # list of [rate, lo, hi] per m
    # context arms (templated)
    out["retrieval"]["templated"]["targeted_distinct"] = p16_rate(R/"p16_100_distinct_templated.json")
    out["retrieval"]["templated"]["random_control"]    = p16_rate(R/"p16_100_random_templated.json")
    # downstream end-to-end
    for key, f in [("neardup_templated", "e2e_neardup_templated.json"),
                   ("neardup_freetext",  "e2e_neardup_freetext.json"),
                   ("universal_freetext","e2e_universal_freetext.json")]:
        p = R/f
        if p.exists():
            d = json.load(open(p))
            out["downstream"][key] = {"captured": d["captured_targets"],
                                      "change": d["change_cap"], "gof": d["gof_cap"],
                                      "clean_gof": d["clean_gof"]}
    json.dump(out, open(R/"summary_100.json", "w"), indent=2)
    print("wrote runs/attack/summary_100.json")
    print(json.dumps(out["retrieval"], indent=2))
    print("downstream arms:", list(out["downstream"]))

if __name__ == "__main__":
    main()
