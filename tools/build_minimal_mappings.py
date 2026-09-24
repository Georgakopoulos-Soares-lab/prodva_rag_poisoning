#!/usr/bin/env python
"""Performance-only: build MINIMAL sequence- and fragment-mapping files that are a
guaranteed SUPERSET of everything the generation path can access for our targets.

Correctness argument: retrieval is deterministic and returns exactly the Top-K
(doc_top_k=16) descriptions per query. infer() only looks up sequences for those
retrieved descriptions, and the fragment sampler only looks up fragments for those
sequences. So a mapping containing the union of Top-16 hits over all targets, over BOTH
the clean and poisoned indexes, plus the poison entries, reproduces every lookup exactly.
Extra entries are harmless; we include the full union so none are missing.
"""
import json, argparse, pathlib, torch
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean_index",  default=str(ROOT/"artifacts/upstream/dataset/index"))
    ap.add_argument("--poison_index", default=str(ROOT/"indexes/poisoned_dev"))
    ap.add_argument("--encoder",      default=str(ROOT/"artifacts/upstream/embedder"))
    ap.add_argument("--full_seqmap",  default=str(ROOT/"artifacts/upstream/dataset/training.json"))
    ap.add_argument("--full_fragmap", default=str(ROOT/"artifacts/upstream/dataset/phrases.json"))
    ap.add_argument("--targets",      default=str(ROOT/"artifacts/attack/targets_dev_as_test.json"))
    ap.add_argument("--poisons",      default=str(ROOT/"artifacts/attack/poison_records_dev_v2.jsonl"))
    ap.add_argument("--payload",      default=str(ROOT/"artifacts/attack/payload.json"))
    ap.add_argument("--k", type=int, default=16)
    ap.add_argument("--out_seqmap",   default=str(ROOT/"artifacts/attack/min_seq_mapping.json"))
    ap.add_argument("--out_fragmap",  default=str(ROOT/"artifacts/attack/min_frag_mapping.json"))
    args = ap.parse_args()

    targets = json.load(open(args.targets))
    poisons = [json.loads(l) for l in open(args.poisons)]
    payload = json.load(open(args.payload))

    emb = HuggingFaceEmbeddings(model_name=args.encoder, model_kwargs={"device": DEVICE},
                                encode_kwargs={"normalize_embeddings": True})
    needed_desc = set()
    for idx_path in (args.clean_index, args.poison_index):
        vs = FAISS.load_local(idx_path, emb, allow_dangerous_deserialization=True)
        for t in targets:
            for doc in vs.similarity_search(t["instruction"], k=args.k):
                needed_desc.add(doc.page_content)
        del vs
    print(f"needed descriptions (union of Top-{args.k}, clean+poison): {len(needed_desc)}")

    # desc -> seq from the full corpus (load once, keep only needed)
    desc2seq = {}
    full = json.load(open(args.full_seqmap))
    for item in full:
        if item["instruction"] in needed_desc:
            desc2seq[item["instruction"]] = item["sequence"]
    del full
    # ensure poison descriptions map to the payload sequence
    for p in poisons:
        desc2seq[p["description"]] = payload["sequence"]
    missing = needed_desc - set(desc2seq)
    print(f"resolved {len(desc2seq)} desc->seq ; unresolved (non-poison) descriptions: {len(missing)}")

    needed_seq = set(desc2seq.values())
    # seq -> phrases from the full fragment file (load once, keep only needed)
    seq2phr = {}
    fragfull = json.load(open(args.full_fragmap))
    for item in fragfull:
        if item["sequence"] in needed_seq:
            seq2phr[item["sequence"]] = item["phrases"]
    del fragfull
    print(f"resolved {len(seq2phr)}/{len(needed_seq)} seq->phrases "
          f"(payload seq present: {payload['sequence'] in seq2phr})")

    json.dump([{"instruction": d, "sequence": s} for d, s in desc2seq.items()],
              open(args.out_seqmap, "w"))
    json.dump([{"sequence": s, "phrases": p} for s, p in seq2phr.items()],
              open(args.out_fragmap, "w"))
    import os
    print(f"wrote {args.out_seqmap} ({os.path.getsize(args.out_seqmap)//1024} KB)")
    print(f"wrote {args.out_fragmap} ({os.path.getsize(args.out_fragmap)//1024} KB)")

if __name__ == "__main__":
    main()
