#!/bin/bash
# Shared settings for this project. Source this before running anything:
#   source /scratch/10899/kimopro/prodva_rag_poison/env/project_env.sh
#
# Everything (caches, model downloads, conda packages) is kept inside the
# project directory so this study shares no state with any other project
# on this machine.

export PRODVA_POISON_ROOT=/scratch/10899/kimopro/prodva_rag_poison

# Model/dataset downloads live with the project, not in the shared cache.
export HF_HOME="$PRODVA_POISON_ROOT/hf_cache"
export HF_HUB_ENABLE_HF_TRANSFER=1

# Pip cache is project-local.
export PIP_CACHE_DIR="$PRODVA_POISON_ROOT/.pip_cache"

# NOTE: do NOT point CONDA_PKGS_DIRS at a directory inside this project.
# Doing so silently corrupts conda's package index on this filesystem: the
# index cache it writes there comes back empty, and every solve then fails with
# a misleading "python does not exist / missing channel" error. Leave conda on
# its configured cache (/scratch/10899/kimopro/conda/pkgs).

# Conda environments for this project (one per stage, all prefixed prodva-poison-).
export PRODVA_POISON_ENV_ROOT=/scratch/10899/kimopro/conda/envs
export PRODVA_POISON_GEN_ENV="$PRODVA_POISON_ENV_ROOT/prodva-poison-gen"

# SLURM allocation to charge. Change here and every job script follows.
export PRODVA_POISON_ACCOUNT=MCB25091

# The pinned upstream checkout.
export PRODVA_UPSTREAM="$PRODVA_POISON_ROOT/third_party/ProDVa"
export PRODVA_UPSTREAM_COMMIT=ff2d41c8be77a27c116c2b70fc1255441ede4107

# faiss-cpu shim: env/shims/sitecustomize.py turns ProDVa's faiss.index_cpu_to_all_gpus
# call into a no-op (we run faiss-cpu; exact IndexFlatL2 search is identical). Auto-loaded
# by every python that has this on PYTHONPATH. No ProDVa source is edited.
export PYTHONPATH="$PRODVA_POISON_ROOT/env/shims:${PYTHONPATH:-}"

# (CONDA_PKGS_DIRS is intentionally NOT set -- see note above -- so don't mkdir it;
#  referencing it here would break callers that use `set -u`.)
mkdir -p "$HF_HOME" "$PIP_CACHE_DIR"
