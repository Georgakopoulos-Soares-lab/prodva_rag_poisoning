#!/usr/bin/env python
"""Performance-only fast harness: load model + both indexes ONCE, use minimal mappings,
and reproduce dvagen eval's per-(condition,seed) RNG exactly (set_seed once per block,
batch_size=1, targets in file order). Outputs match dvagen eval's schema so they can be
verified bit-identical against the reference runs.
"""
import json, argparse, pathlib, time
import torch
from transformers import set_seed
from dvagen.configs.model_args import PhraseSamplerType
from dvagen.infer.infer import prepare, infer
from dvagen.infer.retriever import FAISSRetriever

ROOT = pathlib.Path(__file__).resolve().parents[1]
CKPT = str(ROOT/"artifacts/upstream/checkpoint")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--encoder",      default=str(ROOT/"artifacts/upstream/embedder"))
    ap.add_argument("--clean_index",  default=str(ROOT/"artifacts/upstream/dataset/index"))
    ap.add_argument("--poison_index", default=str(ROOT/"indexes/poisoned_dev"))
    ap.add_argument("--min_seqmap",   default=str(ROOT/"artifacts/attack/min_seq_mapping.json"))
    ap.add_argument("--min_fragmap",  default=str(ROOT/"artifacts/attack/min_frag_mapping.json"))
    ap.add_argument("--targets",      default=str(ROOT/"artifacts/attack/targets_dev_as_test.json"))
    ap.add_argument("--seeds", default="1,2,3,4,5,6,7,8")
    ap.add_argument("--outdir", default=str(ROOT/"runs/attack_fast"))
    ap.add_argument("--conditions", default="clean,poison",
                    help="which conditions to generate; use 'poison' to reuse an existing clean set")
    args = ap.parse_args()

    seeds = [int(s) for s in args.seeds.split(",")]
    targets = json.load(open(args.targets))
    outdir = pathlib.Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    # load model + sampler(minimal frag) + tokenizer + CLEAN retriever ONCE
    model, sampler, tokenizer, clean_ret = prepare(
        dva_model_path=CKPT,
        retriever_embedding_model_path=args.encoder,
        text_tokenizer_path=CKPT+"/text_tokenizer",
        lm_tokenizer_path=CKPT+"/lm_tokenizer",
        phrase_tokenizer_path=CKPT+"/phrase_tokenizer",
        phrase_encoder_batch_size=100000,
        phrase_sampler_type=PhraseSamplerType.PROTEIN_FRAGMENT,
        protein_fragment_mapping_file=args.min_fragmap,
        retriever_vector_store_path=args.clean_index,
    )
    poison_ret = FAISSRetriever(embedding_model_path=args.encoder, vector_store_path=args.poison_index)
    print(f"[load] {time.time()-t0:.1f}s")

    want = set(args.conditions.split(","))
    conds = [c for c in [("clean", clean_ret), ("poison", poison_ret)] if c[0] in want]
    DEC = dict(do_sample=True, temperature=0.7, top_k=950, max_new_tokens=256)
    # PAIRED design: reseed per (target,seed) with a seed that depends ONLY on (seed, target
    # index) -- identical for clean and poison. This removes cross-target RNG drift so a
    # non-captured request yields a bit-identical protein in both conditions, and any
    # clean-vs-poison difference is caused purely by the poison. (See [V-11].)
    for seed in seeds:
        for cond, ret in conds:
            rows = []
            for idx, t in enumerate(targets):
                set_seed(seed * 100000 + idx)   # matched RNG per (target,seed) across conditions
                r = infer(model, sampler, tokenizer, ret, queries=[t["instruction"]],
                          doc_top_k=16, protein_sequence_mapping_file=args.min_seqmap,
                          return_ids=True, **DEC)
                rows.append({"instruction": t["instruction"], "prediction": r[0]["decoded_sentence"],
                             "reference": t.get("sequence","").strip(), "ids": r[0]["ids"]})
            outp = outdir/f"gen_{cond}_s{seed}.json"
            json.dump(rows, open(outp, "w"))
            print(f"[seed {seed} {cond}] wrote {outp.name}  ({time.time()-t0:.1f}s elapsed)")

if __name__ == "__main__":
    main()
