#!/bin/bash
#SBATCH -J prodva-density
#SBATCH -o logs/slurm/density-%j.out
#SBATCH -e logs/slurm/density-%j.out
#SBATCH -p gpu-a100-small
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 00:45:00
set -x
ROOT=/scratch/10899/kimopro/prodva_rag_poison
cd "$ROOT"; source env/project_env.sh; export PYTHONUNBUFFERED=1; mkdir -p runs/attack logs/slurm
nvidia-smi -L
"$PRODVA_POISON_GEN_ENV/bin/python" tools/density_ablation.py \
  --densities 1000,2000,5000,10000,50000,200000,712248 --m 10
echo "### done ###"
