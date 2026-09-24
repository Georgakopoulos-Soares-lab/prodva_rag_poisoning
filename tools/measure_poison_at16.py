#!/usr/bin/env python
"""Attack T, Claim A -- retrieval capture (Poison@16).

Load the clean shipped index, add the poison descriptions (Route A incremental add),
and for each target check whether ITS poison enters the Top-16, at what rank, and whether
OTHER targets' poisons intrude (collateral). Retrieval is deterministic, so this is the
exact Layer-1 result. No generation, no external oracle.
"""
import json, argparse, pathlib, statistics as st
import torch
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index",   default=str(ROOT/"artifacts/upstream/dataset/index"))
    ap.add_argument("--encoder", default=str(ROOT/"artifacts/upstream/embedder"))
    ap.add_argument("--targets", default=str(ROOT/"artifacts/attack/targets_dev.jsonl"))
    ap.add_argument("--poisons", default=str(ROOT/"artifacts/attack/poison_records_dev.jsonl"))
    ap.add_argument("--k", type=int, default=16)
    ap.add_argument("--out", default=str(ROOT/"runs/attack/poison_at16_dev.json"))
    args = ap.parse_args()

    targets = [json.loads(l) for l in open(args.targets)]
    poisons = [json.loads(l) for l in open(args.poisons)]
    print(f"targets={len(targets)} poisons={len(poisons)} k={args.k} device={DEVICE}")

    emb = HuggingFaceEmbeddings(model_name=args.encoder,
                                model_kwargs={"device": DEVICE},
                                encode_kwargs={"normalize_embeddings": True})
    vs = FAISS.load_local(args.index, emb, allow_dangerous_deserialization=True)
    print(f"clean index ntotal={vs.index.ntotal}")

    # Route A: incremental add of poison descriptions (tag with metadata to identify them)
    texts = [p["description"] for p in poisons]
    metas = [{"poison_id": p["poison_id"], "target_id": p["target_id"]} for p in poisons]
    vs.add_texts(texts, metadatas=metas)
    print(f"poisoned index ntotal={vs.index.ntotal} (+{len(poisons)})")

    rows, captured, ranks, collateral_hits = [], 0, [], 0
    for t in targets:
        hits = vs.similarity_search_with_score(t["prompt"], k=args.k)
        own_rank, own_score, intruders = None, None, []
        for rank, (doc, score) in enumerate(hits, 1):
            pid = doc.metadata.get("poison_id")
            if not pid:
                continue
            if doc.metadata.get("target_id") == t["target_id"]:
                if own_rank is None:
                    own_rank, own_score = rank, float(score)
            else:
                intruders.append(pid)
        top1_clean_score = float(hits[0][1])
        k_score = float(hits[-1][1])  # the 16th (worst kept) L2 distance = the bar to beat
        if own_rank is not None:
            captured += 1; ranks.append(own_rank)
        collateral_hits += len(intruders)
        rows.append({"target_id": t["target_id"], "poison_rank": own_rank,
                     "poison_L2": own_score, "topk_L2_threshold": k_score,
                     "n_collateral_intruders": len(intruders)})
        print(f"  {t['target_id']}: poison_rank={own_rank}  poisonL2={own_score}  "
              f"16th_cleanL2={k_score:.4f}  collateral={len(intruders)}")

    N = len(targets)
    poison_at_k = captured / N
    n_pairs = N * (len(poisons) - 1)
    collateral_rate = collateral_hits / n_pairs if n_pairs else 0.0
    summary = {"poison_at_16": poison_at_k, "captured": captured, "n_targets": N,
               "median_rank": st.median(ranks) if ranks else None,
               "ranks": sorted(ranks), "collateral_rate": collateral_rate,
               "note": "L2 on L2-normalized embeddings: LOWER = closer (better)"}
    print("\n==== SUMMARY ====")
    print(f"Poison@{args.k}   : {captured}/{N} = {poison_at_k:.2f}")
    print(f"rank dist    : {sorted(ranks)}  median={summary['median_rank']}")
    print(f"collateral   : {collateral_hits}/{n_pairs} = {collateral_rate:.3f}")
    outp = pathlib.Path(args.out); outp.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"summary": summary, "rows": rows}, open(outp, "w"), indent=2)
    print(f"wrote {outp}")

if __name__ == "__main__":
    main()
