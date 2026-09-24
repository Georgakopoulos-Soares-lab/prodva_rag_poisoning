"""Prove which text encoder built the released FAISS index.

The paper only says "PubMedBERT ... using the txtai framework", and neither
released repo ships the encoder. Guessing wrong would silently wreck every
retrieval measurement in this study, so we check it instead of assuming.

The test: the index was built with
    FAISS.from_documents([Document(d["instruction"]) for d in training.json])
(retriever.py:77-82), so index row i must be the embedding of record i of
training.json. Re-encode a handful of those descriptions with the candidate
model and compare against the stored rows.

A cosine similarity of ~1.0 confirms the encoder. Anything below ~0.99 means we
have the wrong model and must not proceed.

Run:  python tools/verify_encoder.py
"""

import json
import pathlib
import struct
import sys

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX = ROOT / "artifacts" / "upstream" / "dataset" / "index" / "index.faiss"
TRAIN = ROOT / "artifacts" / "upstream" / "dataset" / "training.json"
EMBEDDER = ROOT / "artifacts" / "upstream" / "embedder"

N_PROBE = 8
HEADER_BYTES = 45  # fourcc + d + ntotal + 2 dummies + is_trained + metric + size


def read_index_header():
    b = INDEX.open("rb").read(64)
    fourcc = b[:4].decode("ascii", "replace")
    (d,) = struct.unpack_from("<i", b, 4)
    (ntotal,) = struct.unpack_from("<q", b, 8)
    (metric,) = struct.unpack_from("<i", b, 33)
    return fourcc, d, ntotal, metric


def read_rows(d, n):
    with INDEX.open("rb") as f:
        f.seek(HEADER_BYTES)
        return np.frombuffer(f.read(n * d * 4), dtype="<f4").reshape(n, d)


def first_instructions(n):
    """Pull the first n records without loading the 720 MB file."""
    raw = TRAIN.open("rb").read(4_000_000).decode("utf-8", "ignore")
    dec, i, out = json.JSONDecoder(), raw.index("[") + 1, []
    while len(out) < n:
        while i < len(raw) and raw[i] in " \n\r\t,":
            i += 1
        obj, i = dec.raw_decode(raw, i)
        out.append(obj["instruction"])
    return out


def main():
    fourcc, d, ntotal, metric = read_index_header()
    print(f"index      : {fourcc}  dim={d}  ntotal={ntotal:,}  metric={'L2' if metric == 1 else metric}")

    stored = read_rows(d, N_PROBE)
    norms = np.linalg.norm(stored, axis=1)
    print(f"row norms  : {np.round(norms, 6)}  -> {'L2-normalised' if np.allclose(norms, 1, atol=1e-4) else 'NOT normalised'}")

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(str(EMBEDDER))
    print(f"encoder    : {EMBEDDER.name}  max_seq_length={model.max_seq_length}")
    print(f"modules    : {[type(m).__name__ for m in model]}")

    texts = first_instructions(N_PROBE)
    mine = model.encode(texts, normalize_embeddings=True, batch_size=8)

    cos = (stored * mine).sum(axis=1)
    print("\nrow  cosine(stored, re-encoded)")
    for i, c in enumerate(cos):
        print(f"{i:3d}  {c: .6f}   {texts[i][:56]!r}")

    worst = float(cos.min())
    print(f"\nworst cosine: {worst:.6f}")
    if worst > 0.99:
        print("RESULT: CONFIRMED - this encoder built the released index.")
        return 0
    print("RESULT: MISMATCH - wrong encoder. Do not run the baseline with it.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
