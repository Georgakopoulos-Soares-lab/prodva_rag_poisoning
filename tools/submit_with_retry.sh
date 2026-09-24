#!/bin/bash
# Retry-submit the S1 baseline job to login1 until TACC's accounting-check
# service (accounting_check_prod.pl) recovers. Uses an interactive-TTY ssh
# because Lonestar6 login nodes ignore non-interactive remote commands.
# Writes the job id to logs/submitted_jobid.txt on success.
ROOT=/scratch/10899/kimopro/prodva_rag_poison
OUT="$ROOT/logs/submitted_jobid.txt"
MAX=24        # attempts
SLEEP=300     # seconds between attempts (~2 h total)

for i in $(seq 1 "$MAX"); do
  echo "[attempt $i/$MAX $(date -Is)]"
  RES=$(timeout 90 ssh -tt -o BatchMode=yes -o StrictHostKeyChecking=no login1 <<'REMOTE' 2>&1
cd /scratch/10899/kimopro/prodva_rag_poison
source env/project_env.sh
sbatch -A MCB25091 slurm/s1_baseline.slurm
exit
REMOTE
)
  RES=$(echo "$RES" | tr -d '\r')
  echo "$RES" | grep -iE "Submitted batch job|Unknown project|FAILED" | head -3
  JID=$(echo "$RES" | grep -oE "Submitted batch job [0-9]+" | grep -oE "[0-9]+" | head -1)
  if [[ -n "$JID" ]]; then
    echo "SUCCESS jobid=$JID at $(date -Is)" | tee "$OUT"
    exit 0
  fi
  [[ $i -lt $MAX ]] && sleep "$SLEEP"
done
echo "EXHAUSTED: accounting service still rejecting after $MAX attempts"
exit 1
