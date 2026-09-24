#!/bin/bash
#SBATCH -J prodva-full100
#SBATCH -o logs/slurm/full100-%j.out
#SBATCH -e logs/slurm/full100-%j.out
#SBATCH -p gpu-a100-small
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 14:00:00

# FULL n=100 run on the UNCHANGED 712K corpus (NO density/shrinking).
# Retrieval (universal sweep to m=1500 + Poison@16 all arms, CIs, figures) + end-to-end
# generation (change + gain-of-function, CIs) for: near-dup templated, near-dup free-text,
# universal hubs (m=1500) free-text. Staged & best-effort so partial failures still leave results.
set -x
ROOT=/scratch/10899/kimopro/prodva_rag_poison
cd "$ROOT"; source env/project_env.sh; export PYTHONUNBUFFERED=1
mkdir -p runs/e2e100 runs/attack figures logs/slurm indexes
PY="$PRODVA_POISON_GEN_ENV/bin/python"; A=artifacts/attack
nvidia-smi -L

echo "### STAGE 0: free-text as_test file ###"
"$PY" - <<'PYEOF'
import json,pathlib
A=pathlib.Path("/scratch/10899/kimopro/prodva_rag_poison/artifacts/attack")
ft=[json.loads(l) for l in open(A/"targets_eval100_freetext.jsonl")]
json.dump([{"instruction":r["prompt"],"sequence":r["reference_sequence"],"target_id":r["target_id"]} for r in ft],
          open(A/"targets_eval100_freetext_as_test.json","w"))
print("wrote free-text as_test", len(ft))
PYEOF

echo "### STAGE 1: retrieval analysis (universal sweep to m=1500, CIs, figures; NO density) ###"
"$PY" tools/attack_analysis_100.py --ms 1,2,5,10,20,50,100,200,500,1000,1500 --densities "" || echo "STAGE1 FAILED"

echo "### STAGE 2: Poison@16 rows for all arms (needed to condition end-to-end) ###"
"$PY" tools/measure_poison_at16.py --targets $A/targets_eval100.jsonl --poisons $A/poison_records_eval100_neardup.jsonl  --out runs/attack/p16_100_neardup_templated.json || echo "p16 nd-templ FAILED"
"$PY" tools/measure_poison_at16.py --targets $A/targets_eval100.jsonl --poisons $A/poison_records_eval100_distinct.jsonl --out runs/attack/p16_100_distinct_templated.json || echo "p16 dist FAILED"
"$PY" tools/measure_poison_at16.py --targets $A/targets_eval100.jsonl --poisons $A/poison_records_eval100_random.jsonl   --out runs/attack/p16_100_random_templated.json || echo "p16 rand FAILED"
"$PY" tools/measure_poison_at16.py --targets $A/targets_eval100_freetext.jsonl --poisons $A/poison_records_eval100_neardup.jsonl --out runs/attack/p16_100_neardup_freetext.json || echo "p16 nd-ft FAILED"

echo "### STAGE 3: build near-dup poison index (n=100) ###"
"$PY" tools/build_poison_deployment.py --targets $A/targets_eval100.jsonl --poisons $A/poison_records_eval100_neardup.jsonl \
   --out_index indexes/poisoned_eval100_neardup --out_test $A/targets_eval100_as_test.json --skip_seqmap || echo "STAGE3 FAILED"

echo "### STAGE 4: END-TO-END near-dup TEMPLATED (clean+poison, 8 seeds) ###"
"$PY" tools/build_minimal_mappings.py --poison_index indexes/poisoned_eval100_neardup \
   --targets $A/targets_eval100_as_test.json --poisons $A/poison_records_eval100_neardup.jsonl \
   --out_seqmap $A/min_seq_100_ndt.json --out_fragmap $A/min_frag_100_ndt.json || echo "minmap ndt FAILED"
time "$PY" tools/fast_attack_driver.py --poison_index indexes/poisoned_eval100_neardup \
   --min_seqmap $A/min_seq_100_ndt.json --min_fragmap $A/min_frag_100_ndt.json \
   --targets $A/targets_eval100_as_test.json --outdir runs/e2e100/neardup_templated --seeds 1,2,3,4,5,6,7,8 || echo "gen ndt FAILED"
"$PY" tools/measure_divergence.py --glob_clean "runs/e2e100/neardup_templated/gen_clean_s*.json" --glob_poison "runs/e2e100/neardup_templated/gen_poison_s*.json" --p16 runs/attack/p16_100_neardup_templated.json --testfile $A/targets_eval100_as_test.json || true
"$PY" tools/analyze_ci.py --label "NEARDUP-TEMPLATED-n100" --glob_clean "runs/e2e100/neardup_templated/gen_clean_s*.json" --glob_poison "runs/e2e100/neardup_templated/gen_poison_s*.json" --p16 runs/attack/p16_100_neardup_templated.json --testfile $A/targets_eval100_as_test.json || true

echo "### STAGE 5: END-TO-END near-dup FREE-TEXT (clean+poison, 8 seeds) ###"
"$PY" tools/build_minimal_mappings.py --poison_index indexes/poisoned_eval100_neardup \
   --targets $A/targets_eval100_freetext_as_test.json --poisons $A/poison_records_eval100_neardup.jsonl \
   --out_seqmap $A/min_seq_100_ndf.json --out_fragmap $A/min_frag_100_ndf.json || echo "minmap ndf FAILED"
time "$PY" tools/fast_attack_driver.py --poison_index indexes/poisoned_eval100_neardup \
   --min_seqmap $A/min_seq_100_ndf.json --min_fragmap $A/min_frag_100_ndf.json \
   --targets $A/targets_eval100_freetext_as_test.json --outdir runs/e2e100/neardup_freetext --seeds 1,2,3,4,5,6,7,8 || echo "gen ndf FAILED"
"$PY" tools/measure_divergence.py --glob_clean "runs/e2e100/neardup_freetext/gen_clean_s*.json" --glob_poison "runs/e2e100/neardup_freetext/gen_poison_s*.json" --p16 runs/attack/p16_100_neardup_freetext.json --testfile $A/targets_eval100_freetext_as_test.json || true
"$PY" tools/analyze_ci.py --label "NEARDUP-FREETEXT-n100" --glob_clean "runs/e2e100/neardup_freetext/gen_clean_s*.json" --glob_poison "runs/e2e100/neardup_freetext/gen_poison_s*.json" --p16 runs/attack/p16_100_neardup_freetext.json --testfile $A/targets_eval100_freetext_as_test.json || true

echo "### STAGE 6: UNIVERSAL hubs m=1500 FREE-TEXT end-to-end (best-effort, reuse free-text clean) ###"
"$PY" tools/gen_hub_records.py --m 1500 --out $A/hub_records_ft_m1500.jsonl || echo "hubgen FAILED"
"$PY" tools/build_poison_deployment.py --targets $A/targets_eval100.jsonl --poisons $A/hub_records_ft_m1500.jsonl \
   --out_index indexes/hub_eval100_ft_m1500 --out_test $A/_throwaway_test.json --skip_seqmap || echo "hub index FAILED"
"$PY" tools/measure_universal_capture.py --hub_index indexes/hub_eval100_ft_m1500 --targets $A/targets_eval100_freetext.jsonl --out runs/attack/ucap_100_ft_m1500.json || true
"$PY" tools/build_minimal_mappings.py --poison_index indexes/hub_eval100_ft_m1500 \
   --targets $A/targets_eval100_freetext_as_test.json --poisons $A/hub_records_ft_m1500.jsonl \
   --out_seqmap $A/min_seq_100_hub.json --out_fragmap $A/min_frag_100_hub.json || echo "minmap hub FAILED"
time "$PY" tools/fast_attack_driver.py --poison_index indexes/hub_eval100_ft_m1500 \
   --min_seqmap $A/min_seq_100_hub.json --min_fragmap $A/min_frag_100_hub.json \
   --targets $A/targets_eval100_freetext_as_test.json --outdir runs/e2e100/hub_freetext --conditions poison --seeds 1,2,3,4,5,6,7,8 || echo "gen hub FAILED"
# reuse the free-text CLEAN from Stage 5 (identical: clean index + same queries + same seeds)
"$PY" tools/measure_divergence.py --glob_clean "runs/e2e100/neardup_freetext/gen_clean_s*.json" --glob_poison "runs/e2e100/hub_freetext/gen_poison_s*.json" --p16 runs/attack/ucap_100_ft_m1500.json --testfile $A/targets_eval100_freetext_as_test.json || true
"$PY" tools/analyze_ci.py --label "UNIVERSAL-HUB-FREETEXT-m1500-n100" --glob_clean "runs/e2e100/neardup_freetext/gen_clean_s*.json" --glob_poison "runs/e2e100/hub_freetext/gen_poison_s*.json" --p16 runs/attack/ucap_100_ft_m1500.json --testfile $A/targets_eval100_freetext_as_test.json || true

echo "### done ###"
