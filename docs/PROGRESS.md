# Progress / completion status

A quick map of what was actually built and run versus what remains. The detailed numbers live
in [RESULTS.md](RESULTS.md); the code recon in [verified_facts.md](verified_facts.md).

## Done

- **Code reconnaissance.** Upstream pinned at `ff2d41c`; the full retrieval → dynamic-vocabulary
  → generation path is mapped, and the attack surface (three attacker-writable files) is
  confirmed. See verified_facts.md / code_map.md.
- **Environment + reproducibility.** A self-contained conda env (`prodva-poison-gen`), offline
  SLURM jobs, and a load-once generation harness that was verified **bit-identical** to the
  upstream `dvagen eval` (so the speedups change no results).
- **Encoder identified.** `NeuML/pubmedbert-base-embeddings` reproduces the shipped index
  exactly (cosine 1.0).
- **Clean baseline** generated on the released index.
- **Targeted attack (Attack T)** end-to-end: retrieval capture, change-from-clean, and
  gain-of-function, with clean baselines and a random control (0/100) proving specificity.
- **Universal attack (Attack U)** end-to-end: hub records evaluated on unseen queries, with a
  budget sweep up to **m = 1500**.
- **Query-phrasing analysis:** templated vs free-text requests, showing the template is much of
  what suppresses both attacks.
- **Corpus-size analysis** (retrieval-only, sub-sampling the shipped vectors) attributing the
  benchmark's robustness to corpus density.
- **Statistics + figures:** 100-query evaluation with 95% cluster-bootstrap CIs; two result
  figures in `figures/`.

## Not done (deliberately out of scope for this study)

- Structural plausibility (ESMFold) and official InterProScan annotation of generated proteins
  — see the "future directions" list in RESULTS.md; ESMFold is the highest-value next step.
- A genuinely-distinct (paraphrased) poison set beyond the hand-crafted 30 targets.
- A manuscript, formal pre-registration, and the responsible-disclosure package — these are
  write-up/process steps, not experiments.

## Scope note

The corpus was intentionally left at its full 712,248 records throughout; no sparse-corpus
*deployment* was built. The corpus-size analysis is retrieval-only, reusing the shipped index's
own vectors, and is used solely to explain the density effect.
