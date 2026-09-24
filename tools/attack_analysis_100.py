#!/usr/bin/env python
"""100-query retrieval analysis with bootstrap CIs (full 712K corpus unchanged).
Computes, over 100 EVAL queries, for templated and free-text query styles:
  - retrieval bar (16th-neighbour cos)
  - Attack T near-duplicate Poison@16 (with CI)
  - Attack U universal budget sweep Universal-Poison@16(m) (with CI)
and a corpus-density curve (bar / near-dup T / universal H0 m=10) with CIs.
Regenerates figures. Genuine-distinct arm stays at the hand-crafted 30 (reported separately).
"""
import json, re, argparse, pathlib, numpy as np, torch, random
import faiss
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from sklearn.cluster import KMeans

ROOT=pathlib.Path(__file__).resolve().parents[1]; A=ROOT/"artifacts/attack"
DEVICE="cuda" if torch.cuda.is_available() else "cpu"
def strip_t(d):
    m=re.search(r"\b1\.\s",d); b=d[m.end():] if m else d
    b=re.sub(r"\s*\d+\.\s"," ",b); b=re.sub(r"\s*The designed protein sequence is\.?\s*$","",b)
    return re.sub(r"\s+"," ",b).strip()
def ci(flags, reps=10000, seed=1):
    rng=random.Random(seed); n=len(flags); v=[]
    for _ in range(reps): v.append(sum(flags[rng.randrange(n)] for _ in range(n))/n)
    v.sort(); return v[int(.025*reps)], v[int(.975*reps)]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--k",type=int,default=16); ap.add_argument("--ms",default="1,2,5,10,20,50,100,200,500,1000,1500")
    ap.add_argument("--densities",default="")   # empty => skip density (corpus not ablated)
    ap.add_argument("--n_surrogate",type=int,default=5000)
    args=ap.parse_args(); ms=[int(x) for x in args.ms.split(",")]
    enc=str(ROOT/"artifacts/upstream/embedder")
    emb=HuggingFaceEmbeddings(model_name=enc,model_kwargs={"device":DEVICE},encode_kwargs={"normalize_embeddings":True})
    ev=[json.loads(l) for l in open(A/"targets_eval100.jsonl")]
    nd={json.loads(l)["target_id"]:json.loads(l) for l in open(A/"poison_records_eval100_neardup.jsonl")}
    QT=np.array(emb.embed_documents([t["prompt"] for t in ev]),dtype=np.float32)
    QF=np.array(emb.embed_documents([strip_t(t["prompt"]) for t in ev]),dtype=np.float32)
    Pnd=np.array(emb.embed_documents([nd[t["target_id"]]["description"] for t in ev]),dtype=np.float32)
    # surrogate for hubs (exclude dev + all 100 eval)
    test=json.load(open(ROOT/"artifacts/upstream/dataset/test.json"))
    dev={json.loads(l)["test_index"] for l in open(A/"targets_dev.jsonl")}
    evx={t["test_index"] for t in ev}; rng=random.Random(20250901)
    pool=[i for i in range(len(test)) if i not in dev and i not in evx and 120<=len(test[i]["instruction"])<=1200]
    sidx=rng.sample(pool,args.n_surrogate)
    ST=np.array(emb.embed_documents([test[i]["instruction"].strip() for i in sidx]),dtype=np.float32)
    SF=np.array(emb.embed_documents([strip_t(test[i]["instruction"].strip()) for i in sidx]),dtype=np.float32)
    _idx=FAISS.load_local(str(ROOT/"artifacts/upstream/dataset/index"),emb,allow_dangerous_deserialization=True).index
    if not hasattr(_idx,"reconstruct_n"): _idx=faiss.downcast_index(_idx)
    N=_idx.ntotal; V=_idx.reconstruct_n(0,N)
    print(f"corpus {V.shape[0]} unchanged; EVAL={len(ev)}")

    def bar(Q,Vsub): s=Q@Vsub.T; return np.partition(s,-args.k,axis=1)[:,-args.k]
    res={"n_queries":len(ev),"ms":ms,"styles":{}}
    for style,Q,S in [("templated",QT,ST),("free_text",QF,SF)]:
        b=bar(Q,V); pflags=[int(x) for x in (np.sum(Q*Pnd,axis=1)>b)]
        t_lo,t_hi=ci(pflags)
        u=[]
        for m in ms:
            km=KMeans(n_clusters=m,n_init=(4 if m<=50 else 1),random_state=0).fit(S)
            H=np.array([S[np.argmax(S@c)] for c in km.cluster_centers_]); best=(Q@H.T).max(axis=1)
            f=[int(x) for x in (best>b)]; lo,hi=ci(f); u.append([sum(f)/len(f),lo,hi])
        res["styles"][style]={"bar_median":float(np.median(b)),
            "attackT_neardup":[sum(pflags)/len(pflags),t_lo,t_hi],"attackU":u}
        print(f"[{style}] bar={np.median(b):.3f} T_neardup@16={sum(pflags)/len(pflags):.2f}[{t_lo:.2f},{t_hi:.2f}] "
              f"U@16(m={ms[-1]})={u[-1][0]:.2f}[{u[-1][1]:.2f},{u[-1][2]:.2f}]")
    # density curve (OPTIONAL; skipped when --densities empty -> corpus not ablated)
    dens={}
    if args.densities.strip():
        km10=KMeans(n_clusters=10,n_init=4,random_state=0).fit(ST); H10=np.array([ST[np.argmax(ST@c)] for c in km10.cluster_centers_])
        rng2=np.random.default_rng(0)
        for d in [int(x) for x in args.densities.split(",")]:
            d=min(d,V.shape[0]); sub=V if d>=V.shape[0] else V[rng2.choice(V.shape[0],d,replace=False)]
            b=bar(QT,sub); tf=[int(x) for x in (np.sum(QT*Pnd,axis=1)>b)]; uf=[int(x) for x in ((QT@H10.T).max(axis=1)>b)]
            dens[d]={"bar_median":float(np.median(b)),"T_neardup":[sum(tf)/len(tf),*ci(tf)],"U_h0_m10":[sum(uf)/len(uf),*ci(uf)]}
            print(f"d={d:>7} bar={np.median(b):.3f} T_neardup@16={sum(tf)/len(tf):.2f} U_h0m10@16={sum(uf)/len(uf):.2f}")
    res["density"]=dens
    json.dump(res,open(ROOT/"runs/attack/attack_analysis_100.json","w"),indent=2)


if __name__=="__main__":
    main()
    print("wrote runs/attack/attack_analysis_100.json (figures are produced by figures/*.py)")
