#!/bin/bash
#SBATCH -J prodva-s1-baseline
#SBATCH -o logs/slurm/s1-baseline-%j.out
#SBATCH -e logs/slurm/s1-baseline-%j.err
#SBATCH -p gpu-a100-small
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 06:00:00
#
# S1: reproduce the published baseline on the clean, unmodified index.
# Run slurm/setup_env.slurm first.
#
# Submit with:  sbatch -A $PRODVA_POISON_ACCOUNT slurm/s1_baseline.slurm

set -uo pipefail

ROOT=/scratch/10899/kimopro/prodva_rag_poison
cd "$ROOT"
source env/project_env.sh
mkdir -p runs/s1_baseline logs/slurm

PY="$PRODVA_POISON_GEN_ENV/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Environment missing. Run slurm/setup_env.slurm first."
  exit 20
fi

echo "=============================================================="
echo "host    : $(hostname)"
echo "started : $(date -Is)"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
echo "=============================================================="

echo
echo "### Step 1: record the exact stack (goes in the write-up)"
"$PY" - <<'EOF' | tee runs/s1_baseline/environment.txt
import torch, transformers, faiss, numpy, sentence_transformers, langchain
print("python              ", __import__("sys").version.split()[0])
print("torch               ", torch.__version__, "| cuda", torch.version.cuda)
print("transformers        ", transformers.__version__)
print("faiss               ", faiss.__version__)
print("faiss GPU support   ", hasattr(faiss, "index_cpu_to_all_gpus"))
print("numpy               ", numpy.__version__)
print("sentence-transformers", sentence_transformers.__version__)
print("langchain           ", langchain.__version__)
print("gpu                 ", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NONE")
EOF

echo
echo "### Step 2: confirm the retrieval encoder actually built the shipped index"
# If this fails, everything downstream is meaningless, so stop here.
"$PY" tools/verify_encoder.py | tee runs/s1_baseline/encoder_verification.txt
if [[ ${PIPESTATUS[0]} -ne 0 ]]; then
  echo "!! Encoder mismatch. Stopping before the baseline run."
  exit 21
fi

echo
echo "### Step 3: generate 500 baseline sequences (clean index, seed 0)"
echo "    decoding: K=16, sample, T=0.7, top_k=950, max_new_tokens=256, batch=1"
time "$PRODVA_POISON_GEN_ENV/bin/dvagen" eval --config_path configs/baseline_eval.yaml
RC=$?
echo "### eval exit code: $RC"

echo
echo "### Step 4: quick look at what came out"
"$PY" - <<'EOF'
import json, pathlib, statistics as st
p = pathlib.Path("runs/s1_baseline/results_seed0.json")
if not p.exists():
    print("no results file"); raise SystemExit
r = json.load(open(p))
print(f"generations       : {len(r):,}")
seqs = [x["prediction"].strip() for x in r]
lens = sorted(len(s) for s in seqs)
print(f"length (aa)       : min={lens[0]} median={lens[len(lens)//2]} max={lens[-1]} mean={st.mean(lens):.1f}")
print(f"empty outputs     : {sum(1 for s in seqs if not s)}")
STD = set("ACDEFGHIKLMNPQRSTVWY")
print(f"non-standard chars: {sum(1 for s in seqs if set(s) - STD)}")
# In the decoded `ids`, static tokens are ints; sampled dynamic-vocabulary FRAGMENTS
# are lists (the fragment's constituent token ids). Count fragments = list elements.
used = [sum(1 for i in x.get("ids", []) if isinstance(i, list)) for x in r]
print(f"fragment picks/gen: mean={st.mean(used):.2f} max={max(used)}  "
      f"| generations using >=1 fragment: {sum(1 for u in used if u)}/{len(used)}")
EOF

echo
echo "finished: $(date -Is)"
