#!/usr/bin/env python
"""Generate m universal HUB records (H0: free-text description nearest each k-means centroid of
the free-text surrogate), each paired with the fixed payload. Output usable by
build_poison_deployment.py to build a hub index."""
import json, re, hashlib, argparse, pathlib, random, numpy as np, torch
from langchain_huggingface import HuggingFaceEmbeddings
from sklearn.cluster import KMeans

ROOT=pathlib.Path(__file__).resolve().parents[1]; A=ROOT/"artifacts/attack"
DEVICE="cuda" if torch.cuda.is_available() else "cpu"
def strip_t(d):
    m=re.search(r"\b1\.\s",d); b=d[m.end():] if m else d
    b=re.sub(r"\s*\d+\.\s"," ",b); b=re.sub(r"\s*The designed protein sequence is\.?\s*$","",b)
    return re.sub(r"\s+"," ",b).strip()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--m",type=int,default=1500)
    ap.add_argument("--n_surrogate",type=int,default=6000)
    ap.add_argument("--out",default=str(A/"hub_records_ft_m1500.jsonl"))
    args=ap.parse_args()
    enc=str(ROOT/"artifacts/upstream/embedder")
    emb=HuggingFaceEmbeddings(model_name=enc,model_kwargs={"device":DEVICE},encode_kwargs={"normalize_embeddings":True})
    test=json.load(open(ROOT/"artifacts/upstream/dataset/test.json"))
    dev={json.loads(l)["test_index"] for l in open(A/"targets_dev.jsonl")}
    ev={json.loads(l)["test_index"] for l in open(A/"targets_eval100.jsonl")}
    rng=random.Random(20250901)
    pool=[i for i in range(len(test)) if i not in dev and i not in ev and 120<=len(test[i]["instruction"])<=1200]
    sidx=rng.sample(pool,min(args.n_surrogate,len(pool)))
    surro=[strip_t(test[i]["instruction"].strip()) for i in sidx]
    S=np.array(emb.embed_documents(surro),dtype=np.float32)
    km=KMeans(n_clusters=args.m,n_init=1,random_state=0).fit(S)
    payload=json.load(open(A/"payload.json"))
    seen=set()
    with open(args.out,"w") as f:
        k=0
        for c in km.cluster_centers_:
            i=int(np.argmax(S@c))
            if i in seen: continue
            seen.add(i); d=surro[i]
            f.write(json.dumps({"poison_id":f"HUB-{k:04d}","target_id":f"HUB-{k:04d}","description":d,
                "description_sha256":hashlib.sha256(d.encode()).hexdigest(),"payload_name":payload["payload_name"]})+"\n")
            k+=1
    print(f"wrote {k} unique hub records (m={args.m}) -> {args.out}")

if __name__=="__main__":
    main()
