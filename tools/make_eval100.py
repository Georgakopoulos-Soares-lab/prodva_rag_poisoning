#!/usr/bin/env python
"""Expand EVAL 30 -> 100 (preserving the original 30 + 70 new), and auto-generate poison
variants + free-text queries for all 100. Retrieval-only ablations use these."""
import json, re, hashlib, random, pathlib
ROOT = pathlib.Path("/scratch/10899/kimopro/prodva_rag_poison")
A = ROOT/"artifacts/attack"

test = json.load(open(ROOT/"artifacts/upstream/dataset/test.json"))
dev = [json.loads(l) for l in open(A/"targets_dev.jsonl")]
ev30 = [json.loads(l) for l in open(A/"targets_eval.jsonl")]
used = {r["test_index"] for r in dev} | {r["test_index"] for r in ev30}
rng = random.Random(20250902)
pool = [i for i in range(len(test)) if i not in used and 120 <= len(test[i]["instruction"]) <= 1200]
new70 = rng.sample(pool, 70)
ev100 = list(ev30) + [{"target_id": f"MI-TEST-{i:05d}", "test_index": i,
                       "prompt": test[i]["instruction"].strip(),
                       "reference_sequence": test[i]["sequence"].strip(),
                       "prompt_sha256": hashlib.sha256(test[i]["instruction"].strip().encode()).hexdigest()}
                      for i in new70]
with open(A/"targets_eval100.jsonl","w") as f:
    for r in ev100: f.write(json.dumps(r)+"\n")
json.dump([{"instruction":r["prompt"],"sequence":r["reference_sequence"],"target_id":r["target_id"]} for r in ev100],
          open(A/"targets_eval100_as_test.json","w"))

OPENERS=["Develop a protein sequence with increased stability under specific condition.",
 "Design a protein sequence that is tailored to the desired application.",
 "Create a protein sequence that satisfies the following specifications:",
 "Generate a protein sequence optimized for the following function requirements.",
 "Synthesize a protein sequence that has the desired solubility or other physical properties for the intended use.",
 "Construct a protein sequence with the desired structural and functional characteristics.",
 "Design a functional protein sequence with the following characteristics:",
 "Create a protein sequence with the necessary features to perform the desired function.",
 "Generate a protein sequence that meets the functional requirements while minimizing unwanted side effects."]
def opener_swap(prompt, tid):
    p=re.sub(r"\s*The designed protein sequence is\.?\s*$","",prompt.strip())
    m=re.match(r"^(.*?[.:])\s*(1\.\s.*)$", p, flags=re.S)
    oo,body=(m.group(1),m.group(2)) if m else ("",p)
    h=int(hashlib.sha256(tid.encode()).hexdigest(),16); op=OPENERS[h%len(OPENERS)]
    if op.strip()==oo.strip(): op=OPENERS[(h+1)%len(OPENERS)]
    return op, body
SUBS=[("The protein must exhibit the following characteristics:","The protein should display these features:"),
 ("The protein must be able to","The protein should carry out"),("The designed protein must have","The protein should contain"),
 ("The designed protein must possess","The protein should provide"),("The designed protein should have","The protein should include"),
 ("should be able to","should carry out"),("must exhibit","should display"),("The designed protein","The engineered protein")]
def near_dup(prompt,tid):
    op,body=opener_swap(prompt,tid)
    for a,b in SUBS: body=body.replace(a,b)
    return f"{op} {body}".strip()
def distinct(prompt,tid):
    op,body=opener_swap(prompt,tid)
    body=re.sub(r"\([^)]*\)"," ",body)                    # drop parentheticals (chem)
    body=re.sub(r"[^.]*=[^.]*\.?"," ",body)               # drop clauses with reaction equations
    body=re.sub(r"\s*\d+\.\s"," ",body)                   # drop clause numbering
    for a,b in SUBS: body=body.replace(a,b)
    body=re.sub(r"\s+"," ",body).strip()
    words=body.split()
    if len(words)>40: body=" ".join(words[:40])           # compress to reduce overlap
    return f"{op} {body}".strip()
def strip_template(desc):
    m=re.search(r"\b1\.\s",desc); b=desc[m.end():] if m else desc
    b=re.sub(r"\s*\d+\.\s"," ",b); b=re.sub(r"\s*The designed protein sequence is\.?\s*$","",b)
    return re.sub(r"\s+"," ",b).strip()

payload=json.load(open(A/"payload.json"))
# random control pool (unrelated prompts, not in dev/eval100)
usedx=used|set(new70); rc_pool=[i for i in range(len(test)) if i not in usedx and 120<=len(test[i]["instruction"])<=1200]
rc=random.Random(4242).sample(rc_pool,100)

def dump(name, descfn=None, texts=None):
    with open(A/name,"w") as f:
        for k,r in enumerate(ev100):
            d = texts[k] if texts is not None else descfn(r["prompt"], r["target_id"])
            f.write(json.dumps({"poison_id":f"P-{k:03d}","target_id":r["target_id"],"description":d,
                "description_sha256":hashlib.sha256(d.encode()).hexdigest(),"payload_name":payload["payload_name"]})+"\n")
dump("poison_records_eval100_neardup.jsonl", near_dup)
dump("poison_records_eval100_distinct.jsonl", distinct)
dump("poison_records_eval100_random.jsonl", texts=[test[i]["instruction"].strip() for i in rc])
with open(A/"targets_eval100_freetext.jsonl","w") as f:
    for r in ev100:
        ft=strip_template(r["prompt"])
        f.write(json.dumps({"target_id":r["target_id"],"test_index":r["test_index"],"prompt":ft,
            "reference_sequence":r["reference_sequence"],"prompt_sha256":hashlib.sha256(ft.encode()).hexdigest()})+"\n")

def cw(s): return set(w for w in re.findall(r"[a-z0-9]+",s.lower()) if len(w)>3)
BOIL=cw("develop design create generate synthesize construct protein sequence designed engineered should must able perform function functional characteristics following specific specifications desired activity properties condition intended requirements features include contain provide display carry within order")
import statistics as st
for name in ["neardup","distinct"]:
    recs=[json.loads(l) for l in open(A/f"poison_records_eval100_{name}.jsonl")]
    js=[]
    for r,t in zip(recs,ev100):
        tw=cw(t["prompt"])-BOIL; pw=cw(r["description"])-BOIL
        js.append(len(tw&pw)/len(tw|pw) if (tw|pw) else 0)
    print(f"{name}: function-Jaccard median={st.median(js):.2f} min={min(js):.2f} max={max(js):.2f} n>0.5={sum(j>0.5 for j in js)}")
print(f"EVAL now {len(ev100)} (30 preserved + 70 new)")
