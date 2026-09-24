#!/bin/bash
# Builds the prodva-poison-gen conda environment.
# Run this on an internet-capable node with enough memory (the vm-small VM works;
# compute nodes have no internet). Safe to re-run; pass --force to rebuild.
#
# Why pip + faiss-cpu instead of conda faiss-gpu:
#   - compute nodes (development/gpu-*) have NO outbound internet, so the build
#     cannot run there;
#   - the conda-forge faiss-gpu solve exhausts memory on the login/VM nodes that
#     DO have internet;
#   - the pytorch-channel faiss-gpu build needs glibc>=2.32 and LS6 has 2.28.
#   faiss-cpu (pip, manylinux) installs cleanly here and returns IDENTICAL results
#   on the released exact IndexFlatL2 index. ProDVa's one GPU-transfer call
#   (retriever.py:88) is turned into a no-op by env/shims/sitecustomize.py.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/project_env.sh"

CONDA_BASE="$(conda info --base 2>/dev/null || echo /home1/10899/kimopro/WORK/miniconda3)"
source "$CONDA_BASE/etc/profile.d/conda.sh"

FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

if [[ -d "$PRODVA_POISON_GEN_ENV" && $FORCE -eq 0 ]]; then
  echo "Environment already exists at $PRODVA_POISON_GEN_ENV. Pass --force to rebuild."
  exit 0
fi
if [[ $FORCE -eq 1 && -d "$PRODVA_POISON_GEN_ENV" ]]; then
  echo ">>> Removing existing environment"
  conda env remove -p "$PRODVA_POISON_GEN_ENV" -y
fi

echo ">>> [1/4] Create python 3.11 env (defaults channel only; light solve)"
conda create -p "$PRODVA_POISON_GEN_ENV" -y python=3.11 pip

PY="$PRODVA_POISON_GEN_ENV/bin/python"

echo ">>> [2/4] torch 2.7.0 (CUDA 12.8 wheels; self-contained, runs on the A100 nodes)"
"$PY" -m pip install --no-input --no-cache-dir torch==2.7.0 --index-url https://download.pytorch.org/whl/cu128

echo ">>> [3/4] Pinned deps (includes faiss-cpu==1.9.0 and simple_parsing)"
"$PY" -m pip install --no-input -r "$HERE/requirements-gen.txt"

echo ">>> [4/4] ProDVa itself (editable, --no-deps)"
"$PY" -m pip install --no-input --no-deps -e "$PRODVA_UPSTREAM"

echo
echo ">>> Done. Verifying:"
"$PY" -c "
import torch, transformers, faiss, langchain, sentence_transformers, numpy, simple_parsing
print('python              ', __import__('sys').version.split()[0])
print('torch               ', torch.__version__, '| cuda build', torch.version.cuda)
print('transformers        ', transformers.__version__)
print('faiss               ', faiss.__version__, '| get_num_gpus', faiss.get_num_gpus())
print('langchain           ', langchain.__version__)
print('sentence-transformers', sentence_transformers.__version__)
print('numpy               ', numpy.__version__)
import dvagen; print('dvagen importable   ', True)
"
