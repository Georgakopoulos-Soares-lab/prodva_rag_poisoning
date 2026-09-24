#!/usr/bin/env python
"""Build the poisoned deployment for Attack T Claim B (fragment propagation), DEV.

Route A: copy the clean index and incrementally add the poison descriptions, each paired
with the benign payload sequence. Only two artifacts change:
  - the FAISS index (+ N poison description vectors)
  - the description->sequence mapping (+ N {poison_desc: payload_seq} entries)
The fragment mapping (phrases.json) is UNCHANGED because the payload sequence already has
its authentic fragment entry there.
"""
import json, argparse, pathlib, shutil, torch
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean_index", default=str(ROOT/"artifacts/upstream/dataset/index"))
    ap.add_argument("--encoder",     default=str(ROOT/"artifacts/upstream/embedder"))
    ap.add_argument("--clean_map",   default=str(ROOT/"artifacts/upstream/dataset/training.json"))
    ap.add_argument("--targets",     default=str(ROOT/"artifacts/attack/targets_dev.jsonl"))
    ap.add_argument("--poisons",     default=str(ROOT/"artifacts/attack/poison_records_dev_v2.jsonl"))
    ap.add_argument("--payload",     default=str(ROOT/"artifacts/attack/payload.json"))
    ap.add_argument("--out_index",   default=str(ROOT/"indexes/poisoned_dev"))
    ap.add_argument("--out_map",     default=str(ROOT/"artifacts/attack/poisoned_seq_mapping_dev.json"))
    ap.add_argument("--out_test",    default=str(ROOT/"artifacts/attack/targets_dev_as_test.json"))
    ap.add_argument("--skip_seqmap", action="store_true",
                    help="skip writing the 720MB full poisoned seq-map (fast driver uses the minimal one)")
    args = ap.parse_args()

    payload = json.load(open(args.payload))
    pseq = payload["sequence"]
    targets = [json.loads(l) for l in open(args.targets)]
    poisons = [json.loads(l) for l in open(args.poisons)]

    # target prompts as a dvagen test file
    test = [{"instruction": t["prompt"], "sequence": t["reference_sequence"],
             "target_id": t["target_id"]} for t in targets]
    json.dump(test, open(args.out_test, "w"))
    print(f"wrote target test file: {len(test)} prompts")

    # poisoned index (Route A incremental add)
    emb = HuggingFaceEmbeddings(model_name=args.encoder, model_kwargs={"device": DEVICE},
                                encode_kwargs={"normalize_embeddings": True})
    vs = FAISS.load_local(args.clean_index, emb, allow_dangerous_deserialization=True)
    n0 = vs.index.ntotal
    texts = [p["description"] for p in poisons]
    metas = [{"id": n0 + i, "poison_id": p["poison_id"], "target_id": p["target_id"]}
             for i, p in enumerate(poisons)]
    vs.add_texts(texts, metadatas=metas)
    pathlib.Path(args.out_index).mkdir(parents=True, exist_ok=True)
    vs.save_local(args.out_index)
    print(f"poisoned index: {n0} -> {vs.index.ntotal} (+{len(poisons)}) saved to {args.out_index}")

    # poisoned sequence mapping = clean corpus + poison{desc: payload_seq}
    if args.skip_seqmap:
        print("skipping full poisoned seq-map (fast driver uses the minimal mapping)")
    else:
        clean = json.load(open(args.clean_map))
        print(f"clean seq-mapping records: {len(clean)}")
        poison_map = [{"instruction": p["description"], "sequence": pseq} for p in poisons]
        json.dump(clean + poison_map, open(args.out_map, "w"))
        print(f"poisoned seq-mapping: +{len(poison_map)} -> {args.out_map}")
    print(f"payload signature fragment length: {len(payload['signature_fragment'])} aa")

if __name__ == "__main__":
    main()
