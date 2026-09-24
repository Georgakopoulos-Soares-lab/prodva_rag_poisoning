#!/usr/bin/env python
"""Select DEV/EVAL target prompts from the held-out test set (Attack T).

NOTE: the InterPro-accession filter from plan S8.1 is DEFERRED (needs InterProScan,
which we are not running yet). For the retrieval-capture and fragment-propagation core
(Claims A, B) target accessions are not required. We select on validity + a length band
so descriptions are substantive but under PubMedBERT's 512-token limit. Reference
accessions / orthogonality will be added before the functional-corruption (TOAR) stage.
"""
import json, random, hashlib, argparse, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEED = 20250901  # TARGET_SAMPLING_SEED, per plan

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", default=str(ROOT/"artifacts/upstream/dataset/test.json"))
    ap.add_argument("--outdir", default=str(ROOT/"artifacts/attack"))
    ap.add_argument("--n_dev", type=int, default=10)
    ap.add_argument("--n_eval", type=int, default=30)
    args = ap.parse_args()

    test = json.load(open(args.test))
    # candidate filter: substantive but not over-long description; has a sequence
    cand = [ (i,r) for i,r in enumerate(test)
             if r.get("sequence") and 120 <= len(r["instruction"]) <= 1200 ]
    rng = random.Random(SEED)
    picked = rng.sample(cand, args.n_dev + args.n_eval)
    rng.shuffle(picked)
    dev, ev = picked[:args.n_dev], picked[args.n_dev:]

    outdir = pathlib.Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    def dump(rows, name):
        recs=[]
        for idx,r in rows:
            tid = f"MI-TEST-{idx:05d}"
            recs.append({"target_id": tid, "test_index": idx,
                         "prompt": r["instruction"].strip(),
                         "reference_sequence": r["sequence"].strip(),
                         "prompt_sha256": hashlib.sha256(r["instruction"].strip().encode()).hexdigest()})
        p = outdir/name
        with open(p,"w") as f:
            for rec in recs: f.write(json.dumps(rec)+"\n")
        return recs
    dev_recs = dump(dev, "targets_dev.jsonl")
    ev_recs  = dump(ev,  "targets_eval.jsonl")
    print(f"candidates: {len(cand)} | DEV: {len(dev_recs)}  EVAL: {len(ev_recs)}  (seed {SEED})")
    print(f"DEV ∩ EVAL test_index overlap: {len(set(x['test_index'] for x in dev_recs) & set(x['test_index'] for x in ev_recs))}")
    print("\n=== DEV targets (full prompts, for poison crafting) ===")
    for r in dev_recs:
        print(f"\n[{r['target_id']}] (seqlen {len(r['reference_sequence'])})\n{r['prompt']}")

if __name__ == "__main__":
    main()
