# Results: poisoning ProDVa's retrieval corpus

This document reports what we actually measured. All numbers are from the released
`ProDVa-Molinst-SwissProtCLAP` deployment on the full, unmodified 712,248-record supporting
corpus, using the frozen decoding settings shipped with the model (top-16 retrieval,
temperature 0.7, top_k 950, 256 new tokens). Confidence intervals are 95% cluster bootstraps
over the evaluation queries (10,000 resamples). Everything is in silico.

## The short version

Inserting a text–protein record into ProDVa's corpus is a real, targeted attack: a record can
be retrieved for a specific request, and when it is, it measurably changes the generated
protein and can make that protein carry the attacker's benign domain — something the clean
model never does. But whether the attack lands depends almost entirely on two properties of
the *deployment*, not of the model:

1. **How the users phrase requests.** The Mol-Instructions benchmark writes every request in
   the same rigid template, and the corpus is built from those same templated strings. That
   shared phrasing makes the retrieval bar extremely high, so only a near-verbatim copy of a
   request wins retrieval. The moment requests are ordinary free text, the bar collapses and
   the attack becomes far more effective — on the *same* corpus.
2. **How large / redundant the corpus is.** With 712K near-duplicate descriptions, every
   request already has ~16 near-identical neighbours that a poison must beat. This is what makes
   the benchmark look robust; it is an emergent property of corpus density, not of the encoder.

## How the attack works

ProDVa answers a request by embedding it with PubMedBERT, retrieving the top-16 most similar
corpus descriptions, collecting the InterPro **fragments** of those 16 proteins into a dynamic
vocabulary, and then generating a protein by sampling ordinary tokens *and* whole fragments.

A poison is an ordinary record whose description is a retrieval key and whose sequence is a
benign payload. If it wins a top-16 slot, the payload's domain enters the dynamic vocabulary
and can be emitted into the output. Inserting a poison touches three attacker-writable files
(the corpus/index, the description→sequence map, and the sequence→fragments map); the code
paths are documented in [verified_facts.md](verified_facts.md) and [code_map.md](code_map.md).

The **payload** throughout is a benign LacI-family periplasmic sugar-binding protein — a 253-aa
sugar-binding domain plus LacI helix-turn-helix domains. It has pure binding/regulatory
function, no harm-relevant catalysis, and its authentic domain annotations already ship in the
dataset, so no annotation had to be fabricated.

## What we measure

- **Poison@16** — did the poison enter the request's top-16 (retrieval capture)?
- **Change-from-clean** — for the same request and random seed, does the poisoned run produce
  a different protein than the clean run? We reseed per (request, seed) so that when the poison
  is *not* retrieved the two runs are byte-identical; any difference is therefore caused by the
  poison alone.
- **Gain of function** — does the generated protein acquire the payload's domain? We detect it
  by profile-HMM homology (`phmmer`, payload domain as the query, E < 1e-3) — the same homology
  principle InterPro's member databases use, and it catches partial acquisitions, not just exact
  copies.

## Main results (100 held-out evaluation queries, 8 seeds)

**Retrieval capture.**

| Attack | Poison@16 |
|---|---|
| Random control — same payload, unrelated description | 0.00 (0/100) |
| Targeted, genuinely paraphrased poison | 0.21 |
| Targeted, near-duplicate poison | 0.58 [0.48, 0.68] |
| Targeted, near-duplicate poison, **free-text requests** | 0.97 [0.93, 1.00] |
| Universal hubs (1500 records), templated requests | 0.14 [0.08, 0.21] |
| Universal hubs (1500 records), **free-text requests** | 0.60 [0.50, 0.70] |

**End-to-end effect, conditional on capture.** The clean model never produces the payload
domain in any arm (0 of ~730–740 clean generations).

| Attack arm | change \| captured | gain-of-function \| captured |
|---|---|---|
| Near-duplicate × templated | 0.62 [0.54, 0.70] | 0.19 [0.11, 0.29] |
| Near-duplicate × free-text | 0.62 [0.55, 0.69] | 0.21 [0.14, 0.28] |
| Universal hubs (1500) × free-text | 0.66 [0.58, 0.74] | 0.26 [0.17, 0.36] |

The random control captures nothing (0/100): a record with the same payload but an unrelated
description is never retrieved, so the effect comes from *targeting*, not from merely adding a
record. This is the specificity result the whole causal story rests on.

## The two things that govern success

**Query phrasing.** Stripping the template off the requests (turning them into ordinary
free-text descriptions of the same functions) drops the retrieval bar from cosine ~0.93 to
~0.83 without touching the corpus. That single change roughly triples targeted capture and
lifts the universal attack from essentially zero to 0.60 at 1500 hubs. In other words, the
benchmark's rigid template — shared between queries and corpus — is much of what protects it;
a natural-language deployment is considerably more exposed. The universal budget sweep (both
phrasings) is in `figures/figure1_retrieval_capture` (panel b); the end-to-end change and
gain-of-function are in `figures/figure2_downstream_effect`.

**Corpus density.** A retrieval-only analysis that sub-samples the shipped index's own vectors
(no deployment was actually shrunk) shows capture is governed by corpus size: as the corpus
thins from 712K toward a few thousand records — the scale of a realistic curated lab index —
the retrieval bar falls and both attacks strengthen monotonically. This is why the full
benchmark corpus resists poisoning: it is saturated with near-duplicate descriptions, an
emergent robustness rather than a defended one. (Reported as a retrieval-only analysis; not
plotted as a figure here.)

## What this means

The mechanism is genuine and specific, and it clears the bar in realistic conditions
(free-text requests, and/or a corpus that isn't the entire training set used verbatim). On the
benchmark as shipped, the potent version of the attack requires near-verbatim descriptions —
exactly what a near-duplicate filter would flag — while the stealthy, genuinely-paraphrased
version is weak. That contrast is itself the defense-relevant finding: ProDVa's out-of-the-box
robustness comes from corpus redundancy and a uniform query template, not from anything that
would survive a more natural deployment.

## Safety

The payload is a benign, well-characterized binding domain; the result is about the attacker's
*control over generation*, not about any property of what was generated. No sequence produced
here was synthesized, ordered, or expressed. The repository releases construction code and the
attack inputs only — not any poisoned index, corpus, or mapping file.

## Promising future directions (not run here)

- **Structural plausibility with ESMFold.** Confirm that poisoned proteins remain foldable
  (pLDDT within a few points of clean); "acquires the domain *and stays a plausible protein*"
  is a materially stronger claim than change alone. This is the single highest-value addition.
- **Official InterProScan annotation** of the generated proteins, to replace the homology proxy
  with the gold-standard accession label for gain-of-function.
- **Genuinely-distinct poisons at scale.** The stealthy (paraphrased) arm is hand-crafted for 30
  targets; an LLM-based paraphraser would extend it to the full evaluation set.
- **Gradient-optimized universal hubs.** The universal results use coherent, unoptimized hubs;
  HotFlip-style optimization could raise free-text universal capture further, since the
  retrieved description is discarded and can be arbitrary.
