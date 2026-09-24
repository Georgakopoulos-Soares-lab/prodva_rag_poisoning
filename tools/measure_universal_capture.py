#!/usr/bin/env python
"""Universal-Poison@16 for a prebuilt HUB index: for each query, is any hub in Top-16?
Outputs a p16-format JSON (rows with target_id, poison_rank) so measure_divergence /
measure_gain_of_function can condition on capture, plus a summary with bootstrap CI."""
import json, argparse, pathlib, random, torch
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

ROOT=pathlib.Path(__file__).resolve().parents[1]
DEVICE="cuda" if torch.cuda.is_available() else "cpu"
def ci(flags,reps=10000,seed=1):
    rng=random.Random(seed); n=len(flags); v=[sum(flags[rng.randrange(n)] for _ in range(n))/n for _ in range(reps)]
    v.sort(); return v[int(.025*reps)], v[int(.975*reps)]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--hub_index", required=True)
    ap.add_argument("--encoder", default=str(ROOT/"artifacts/upstream/embedder"))
    ap.add_argument("--targets", required=True)   # jsonl with prompt + target_id
    ap.add_argument("--k", type=int, default=16)
    ap.add_argument("--out", required=True)
    args=ap.parse_args()
    emb=HuggingFaceEmbeddings(model_name=args.encoder,model_kwargs={"device":DEVICE},encode_kwargs={"normalize_embeddings":True})
    vs=FAISS.load_local(args.hub_index, emb, allow_dangerous_deserialization=True)
    tg=[json.loads(l) for l in open(args.targets)]
    rows=[]; flags=[]
    for t in tg:
        hits=vs.similarity_search(t["prompt"], k=args.k)
        rank=None
        for r,doc in enumerate(hits,1):
            if doc.metadata.get("poison_id"): rank=r; break
        rows.append({"target_id":t["target_id"],"poison_rank":rank})
        flags.append(1 if rank is not None else 0)
    up=sum(flags)/len(flags); lo,hi=ci(flags)
    json.dump({"summary":{"universal_poison_at16":up,"ci":[lo,hi],"n":len(flags)},"rows":rows}, open(args.out,"w"), indent=2)
    print(f"Universal-Poison@16 = {sum(flags)}/{len(flags)} = {up:.2f}  CI[{lo:.2f},{hi:.2f}]  -> {args.out}")

if __name__=="__main__":
    main()
