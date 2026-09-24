"""Download the released ProDVa checkpoint and its supporting corpus.

Everything lands under artifacts/upstream/ inside this project. Nothing is
shared with any other project on this machine.

Run:  python tools/download_upstream.py [--what all|checkpoint|dataset]
"""

import argparse
import json
import os
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEST = ROOT / "artifacts" / "upstream"

REPOS = {
    "checkpoint": dict(
        repo_id="nwliu/ProDVa-Molinst-SwissProtCLAP",
        repo_type="model",
        local_dir=DEST / "checkpoint",
    ),
    "dataset": dict(
        repo_id="nwliu/Molinst-SwissProtCLAP",
        repo_type="dataset",
        local_dir=DEST / "dataset",
    ),
    # The retrieval encoder. The paper says only "PubMedBERT ... using the txtai
    # framework"; this is the sentence-transformers PubMedBERT published by the
    # author of txtai, and it is the only obvious candidate that matches the
    # shipped index (768 dims, mean pooling, L2-normalised).
    # tools/verify_encoder.py checks this empirically rather than assuming it.
    "embedder": dict(
        repo_id="NeuML/pubmedbert-base-embeddings",
        repo_type="model",
        local_dir=DEST / "embedder",
    ),
}


def download(key: str) -> pathlib.Path:
    from huggingface_hub import snapshot_download

    spec = REPOS[key]
    spec["local_dir"].mkdir(parents=True, exist_ok=True)
    print(f"\n=== downloading {key}: {spec['repo_id']} -> {spec['local_dir']}", flush=True)
    path = snapshot_download(
        repo_id=spec["repo_id"],
        repo_type=spec["repo_type"],
        local_dir=str(spec["local_dir"]),
        # Deliberately low: this project's interactive node is a shared VM and
        # more parallel writers than this has been enough to exhaust its memory.
        max_workers=2,
    )
    print(f"=== done: {path}", flush=True)
    return pathlib.Path(path)


def record_revisions() -> None:
    """Pin exactly which commit of each repo we downloaded, for the write-up."""
    from huggingface_hub import HfApi

    api = HfApi()
    out = {}
    for key, spec in REPOS.items():
        info = (
            api.model_info(spec["repo_id"])
            if spec["repo_type"] == "model"
            else api.dataset_info(spec["repo_id"])
        )
        out[key] = {"repo_id": spec["repo_id"], "repo_type": spec["repo_type"], "sha": info.sha}
        print(f"{key:12s} {spec['repo_id']:40s} @ {info.sha}")
    dest = DEST / "UPSTREAM_REVISIONS.json"
    dest.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--what", default="all", choices=["all", "checkpoint", "dataset"])
    args = ap.parse_args()

    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

    keys = list(REPOS) if args.what == "all" else [args.what]
    for k in keys:
        download(k)
    record_revisions()
    print("\nAll requested downloads complete.", file=sys.stderr)
