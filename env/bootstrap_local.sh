#!/bin/bash
# Runs the two heavy setup steps one after another (never concurrently) so the
# shared interactive VM does not run out of memory.
set -uo pipefail
ROOT=/scratch/10899/kimopro/prodva_rag_poison
cd "$ROOT"
source env/project_env.sh

echo "### Step 1/2: download checkpoint + corpus   $(date -Is)"
python tools/download_upstream.py --what all
echo "### download exit: $?   $(date -Is)"

echo
echo "### Step 2/2: build conda environment        $(date -Is)"
bash env/setup_gen_env.sh
echo "### env build exit: $?   $(date -Is)"
