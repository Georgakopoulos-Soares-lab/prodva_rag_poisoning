#!/usr/bin/env python
"""Corpus-density ablation: does the attack succeed as the supporting corpus gets sparser?

Reuses the shipped index's OWN vectors (reconstruct + subsample) so densities are exact and
no re-embedding of the corpus is needed. For each density d we compute, on the 30 unseen EVAL
queries:
  - Poison@16 (distinct Attack T): each target's distinct poison vs its 16th clean neighbor
  - Universal-Poison@16 (Attack U, H0 m=10): any hub vs the 16th clean neighbor
  - median 16th-neighbor cosine (the 'saturation bar' that shrinks as the corpus thins)
"""
import json, argparse, pathlib, numpy as np, torch, random
import faiss
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from sklearn.cluster import KMeans

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean_index", default=str(ROOT/"artifacts/upstream/dataset/index"))
    ap.add_argument("--encoder",     default=str(ROOT/"artifacts/upstream/embedder"))
    ap.add_argument("--test",        default=str(ROOT/"artifacts/upstream/dataset/test.json"))
    ap.add_argument("--targets_eval",default=str(ROOT/"artifacts/attack/targets_eval.jsonl"))
    ap.add_argument("--targets_dev", default=str(ROOT/"artifacts/attack/targets_dev.jsonl"))
    ap.add_argument("--distinct",    default=str(ROOT/"artifacts/attack/poison_records_eval_distinct.jsonl"))
    ap.add_argument("--densities",   default="2000,10000,50000,200000,712248")
    ap.add_argument("--m", type=int, default=10)
    ap.add_argument("--k", type=int, default=16)
    ap.add_argument("--n_surrogate", type=int, default=3000)
    ap.add_argument("--out", default=str(ROOT/"runs/attack/density_ablation.json"))
    args = ap.parse_args()

    emb = HuggingFaceEmbeddings(model_name=args.encoder, model_kwargs={"device": DEVICE},
                                encode_kwargs={"normalize_embeddings": True})
    ev = [json.loads(l) for l in open(args.targets_eval)]
    tid2poison = {json.loads(l)["target_id"]: json.loads(l) for l in open(args.distinct)}
    Q = np.array(emb.embed_documents([t["prompt"] for t in ev]), dtype=np.float32)          # 30 x d
    P = np.array(emb.embed_documents([tid2poison[t["target_id"]]["description"] for t in ev]), dtype=np.float32)  # matched poison per target

    # surrogate for hubs (held-out, not DEV/EVAL)
    ev_idx={t["test_index"] for t in ev}; dev_idx={json.loads(l)["test_index"] for l in open(args.targets_dev)}
    test=json.load(open(args.test)); rng=random.Random(20250901)
    pool=[i for i in range(len(test)) if i not in ev_idx and i not in dev_idx and 120<=len(test[i]["instruction"])<=1200]
    surro_idx=rng.sample(pool, min(args.n_surrogate,len(pool)))
    Ssur=np.array(emb.embed_documents([test[i]["instruction"].strip() for i in surro_idx]),dtype=np.float32)

    # reconstruct all shipped corpus vectors
    vs = FAISS.load_local(args.clean_index, emb, allow_dangerous_deserialization=True)
    idx = vs.index
    if isinstance(idx, faiss.IndexPreTransform) or not hasattr(idx, "reconstruct_n"):
        idx = faiss.downcast_index(idx)
    N = idx.ntotal
    V = idx.reconstruct_n(0, N)                    # N x 768, normalized
    print(f"reconstructed {N} corpus vectors")

    rng2 = np.random.default_rng(0)
    results = {}
    for d in [int(x) for x in args.densities.split(",")]:
        d = min(d, N)
        sub = V if d >= N else V[rng2.choice(N, size=d, replace=False)]
        # 16th clean-neighbor cosine per EVAL query (top-k over the subsample)
        sims = Q @ sub.T                            # 30 x d cosine (normalized)
        # k-th largest per row
        kth = np.partition(sims, -args.k, axis=1)[:, -args.k]     # 16th best cosine
        # Attack T (distinct): matched poison cos vs its own 16th-clean bar
        poison_cos = np.sum(Q * P, axis=1)          # cos(query, its poison)
        t_capture = (poison_cos > kth).mean()
        # Attack U (H0, m hubs): cluster surrogate, hub = nearest surrogate to centroid
        km = KMeans(n_clusters=args.m, n_init=4, random_state=0).fit(Ssur)
        hub_vecs = np.array([Ssur[np.argmax(Ssur @ c)] for c in km.cluster_centers_])
        best_hub_cos = (Q @ hub_vecs.T).max(axis=1)
        u_capture = (best_hub_cos > kth).mean()
        results[d] = {"poison_at16_distinctT": float(t_capture),
                      "universal_poison_at16_H0": float(u_capture),
                      "median_16th_cos": float(np.median(kth)),
                      "median_poison_cos": float(np.median(poison_cos)),
                      "median_best_hub_cos": float(np.median(best_hub_cos))}
        print(f"d={d:>7}  16th_clean_cos(med)={np.median(kth):.3f}  "
              f"distinct-T Poison@16={t_capture:.2f}  Universal(H0,m={args.m})@16={u_capture:.2f}")
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(results, open(args.out,"w"), indent=2)
    print("\nStory: as d shrinks, 16th_clean_cos drops; when it falls below the poison cos (~0.85),")
    print("the functional-match attack (both targeted-distinct and universal) starts to succeed.")

if __name__ == "__main__":
    main()
