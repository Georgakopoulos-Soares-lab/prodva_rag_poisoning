#!/bin/bash
#SBATCH -J prodva-setup
#SBATCH -o logs/slurm/setup-%j.out
#SBATCH -e logs/slurm/setup-%j.err
#SBATCH -p development
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 02:00:00
#
# Builds the prodva-poison-gen environment and finishes downloading the
# released checkpoint and corpus.
#
# This has to run on a compute node: the login node's memory cap kills both the
# conda solve and the 7 GB checkpoint download.
#
# Submit with:  sbatch -A $PRODVA_POISON_ACCOUNT slurm/setup_env.slurm

set -uo pipefail

ROOT=/scratch/10899/kimopro/prodva_rag_poison
cd "$ROOT"
source env/project_env.sh

echo "=============================================================="
echo "host        : $(hostname)"
echo "cores       : $(nproc)"
echo "memory      : $(free -g | awk '/^Mem:/{print $2}') GB"
echo "started     : $(date -Is)"
echo "=============================================================="

echo
echo "### Step 0: can this node reach the internet?"
CONN_OK=1
curl -s -o /dev/null -w "  huggingface.co     -> %{http_code}\n" --max-time 30 https://huggingface.co || CONN_OK=0
curl -s -o /dev/null -w "  conda.anaconda.org -> %{http_code}\n" --max-time 30 https://conda.anaconda.org/conda-forge/noarch/repodata.json || CONN_OK=0
if [[ $CONN_OK -eq 0 ]]; then
  echo "  !! No outbound internet from this partition."
  echo "  !! Re-submit to a partition that has it (try: vm-small)."
  exit 20
fi

echo
echo "### Step 1: build the conda environment"
bash env/setup_gen_env.sh
ENV_RC=$?
echo "### env build exit code: $ENV_RC"

echo
echo "### Step 2: finish downloading checkpoint + corpus"
if [[ -x "$PRODVA_POISON_GEN_ENV/bin/python" ]]; then
  PY="$PRODVA_POISON_GEN_ENV/bin/python"
else
  echo "  (environment missing, falling back to the base interpreter)"
  PY=python
fi
"$PY" tools/download_upstream.py --what all
DL_RC=$?
echo "### download exit code: $DL_RC"

echo
echo "### Step 3: what we ended up with"
du -sh artifacts/upstream/* 2>/dev/null
echo
find artifacts/upstream -type f -printf "%10s  %p\n" 2>/dev/null | sort -k2 | head -40

echo
echo "finished    : $(date -Is)"
[[ $ENV_RC -eq 0 && $DL_RC -eq 0 ]] || exit 1
