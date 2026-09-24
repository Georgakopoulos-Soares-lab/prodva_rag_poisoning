# S0 Recon — Verified Facts

**Repo:** `github.com/sornkL/ProDVa`
**Pinned commit:** `ff2d41c8be77a27c116c2b70fc1255441ede4107` (2025-11-23, "fix config file examples and update README")
**Clone path:** `third_party/ProDVa/`
**Resolved:** 2026-08-10 by static code reading. Items needing runtime confirmation against the downloaded checkpoint are flagged **[confirm@S1]**.

Legend: ✅ resolved from code · ⚠️ resolved but confirm at runtime · 🎯 attack-critical.

---

## Summary of attack-relevant conclusions

1. **Poisoning requires THREE files, not one** (all attacker-writable, all read by the eval path):
   - the **supporting-corpus / data file** (`instruction` field → builds the FAISS index),
   - the **`protein_sequence_mapping_file`** (`instruction` → `sequence`, keyed by description string),
   - the **`protein_fragment_mapping_file`** (`sequence` → `phrases[]`, keyed by sequence string).
2. **`[V-6]` resolves maximally favorably:** at inference, fragments come from a **precomputed mapping file** (`ProteinFragmentSampler`), keyed by the raw sequence. The attacker fully controls what fragments a payload contributes. No live InterProScan at inference.
3. **The retrieval metric is L2 on L2-normalized embeddings ⇒ pure cosine/angular ranking.** There is **no raw-inner-product norm lever**, so Attack-U method **H2 (norm hub) is inapplicable by construction** — report as a mild robustness property, not a failed arm.
4. **Fragment block is contiguous and index-addressable** (`ids ≥ static_vocab`); the existing `DVALogitsProcessor.index_fill_` is a ready-made template for the Control-3 mask.
5. **`eval.yaml` default `batch_size: 1`** ⇒ no cross-prompt candidate-set leakage in the default config (`[V-14]` benign as configured).
6. **RNG is a single global seed set once per run** (`[V-11]`): one generation per prompt per run; R seeds = R runs. Per-(prompt,seed) counterfactual RNG matching across conditions is **not** achievable without a per-prompt reseed patch — see S6 note.

---

## V-checklist resolutions

### `[V-1]` ✅🎯 Retriever location & name
`FAISSRetriever` — `src/dvagen/infer/retriever.py:42`. Retrieval call:
`self.vector_store.similarity_search(query, k=top_k)` — `retriever.py:91`.
`RandomRetriever` also exists (`retriever.py:26`) but is not used by eval.
**LOG HOOK A** goes in `retrieve_documents` (`retriever.py:90-94`). Note: `similarity_search` returns **no scores**; to log scores use `similarity_search_with_score` (returns L2 distance).

### `[V-2]` ✅🎯 What the index stores; hit→sequence mapping
- Index docs built as `langchain_core.documents.Document(description, metadata={"id": idx})` where `idx` = position in `data_file` — `retriever.py:78-81`. So each hit carries **both** the description text (`page_content`) and an **integer corpus id** (`metadata["id"]`).
- `retrieve_documents` returns `Document(content=page_content, id=metadata["id"])` — `retriever.py:92-94`.
- Hit → sequence: `infer.py:123-125` loads `protein_sequence_mapping_file` into a dict **keyed by `instruction` (description string)**; lookup is `sequence_mappings[doc.content]` — `infer.py:129`.
- **Consequence:** poison flagging (hook A) can use the integer `id`; sequence resolution is by **description string**. Poison insertion touches 3 files (see summary). A retrieved description absent from the sequence-mapping file → `KeyError` (so the mapping must contain every corpus description).

### `[V-3]` ✅🎯 Backend / index type / normalization
- Backend: **LangChain-community FAISS** (`langchain_community.vectorstores.FAISS`) + `langchain_huggingface.HuggingFaceEmbeddings` — `retriever.py:8-9,54-58`.
- Embeddings **L2-normalized**: `encode_kwargs={"normalize_embeddings": True}` — `retriever.py:57`.
- Index built by `FAISS.from_documents(...)` — `retriever.py:82`. LangChain default `distance_strategy = EUCLIDEAN_L2` ⇒ **`IndexFlatL2`**. On login/dev with CUDA, index is moved to GPU: `faiss.index_cpu_to_all_gpus` — `retriever.py:88`.
- **Score semantics:** L2 distance on L2-normalized vectors, where `‖a−b‖² = 2 − 2·cos(a,b)` ⇒ ranking by ascending L2 ≡ descending cosine. **Report as "L2 distance on L2-normalized embeddings (monotone in cosine)"; do not call it a similarity.**

### `[V-4]` ⚠️🎯 PubMedBERT pooling & truncation
Encoding via `HuggingFaceEmbeddings` (wraps sentence-transformers `SentenceTransformer`). Pooling and `max_seq_length` are determined by the **embedding checkpoint's** ST config, not by ProDVa code. `normalize_embeddings=True` is explicit (`retriever.py:57`). **[confirm@S1]** the exact `embedding_model_path`, its pooling (mean vs CLS), and `max_seq_length` (PubMedBERT base = 512) once the checkpoint is downloaded. Craft poison descriptions under that truncation.

### `[V-5]` ✅ Incremental add support
LangChain FAISS supports `add_texts` / `add_documents` / `merge_from` + `save_local` (persisted). Not currently invoked by ProDVa, but available ⇒ **Route A (incremental add) is feasible** for building poisoned/hub indexes cheaply (copy clean index, add `n` vectors). Current build path only ever calls `FAISS.from_documents` + `save_local` (`retriever.py:82-84`).

### `[V-6]` ✅🎯🎯 (most consequential) Fragment source at inference
**RESOLVED FAVORABLY.** Inference uses `PhraseSamplerType.PROTEIN_FRAGMENT` → `ProteinFragmentSampler(mapping_file=protein_fragment_mapping_file, format_sequence=False)` — `infer.py:83-87`. The `eval` path passes `protein_fragment_mapping_file` through `predict_results → prepare` — `eval.py:40`, and `eval.yaml:8` sets it. Fragments are read from a **precomputed JSON mapping keyed by the raw sequence** — `sampler.py:323-341`. `get_fragments` returns `[]` if the sequence is absent (`sampler.py:337-341`) ⇒ **the payload sequence MUST appear in the fragment mapping or it contributes zero fragments.** No live InterProScan at inference. The README lists `protein_fragment_mapping_file` under `train` only, but the code wires it into `eval`/`chat` as well.

### `[V-7]` ✅ phrase_sampler_type
`PhraseSamplerType` enum = `{FMM, N_WORDS, N_TOKENS, PROTEIN_FRAGMENT}` — `model_args.py:7-11`. ProDVa uses the **fourth type, `PROTEIN_FRAGMENT`** (`eval.yaml:6`). The other three are DVAGen text heuristics and are bypassed for ProDVa.

### `[V-8]` ✅🎯 Fragment length cap
For `PROTEIN_FRAGMENT`, **no length cap is applied at inference.** `ProteinFragmentSampler.sample` (`sampler.py:401-404`) does not use `phrase_max_length`. The tokenizer's `encode` step has **no** `truncation`/`max_length` (`tokenization_dva.py:50`); fragments are padded to the batch max. `phrase_max_length` / `max_phrase_length` only affect `N_TOKENS`/`N_WORDS`/FMM and the training-time `tokenize()` (`tokenization_dva.py:36-40`). **Consequence:** payload domains of any length enter the dynamic vocabulary; the only real limit is phrase-encoder memory. Screening payloads against `phrase_max_length` (plan S3) is therefore unnecessary for this deployment — note it but do not gate on it.

### `[V-9]` ✅🎯 Candidate-set dedup / order / cap
No dedup, no cap. `infer.py:132-135` flattens **all** phrases (both `is_phrase=True` fragments and `is_phrase=False` connectors) from all K retrieved sequences, in retrieval order. Duplicate fragments are **not** collapsed. DV entries are assigned ids `static_vocab + running_index` in encounter order (`tokenization_dva.py:48-49`, batch offset at `:74-77`). ⇒ "fragments contributed by the poison" = count of `is_phrase=True` entries in the payload's mapping record; fragment id → source record is reconstructable from assembly order.

### `[V-10]` ✅🎯 Ingest dedup behavior
- FAISS index: `from_documents` assigns each doc its own vector + docstore uuid; **duplicate descriptions are NOT dropped** at the index level.
- **But** the `protein_sequence_mapping_file` is a dict keyed by `instruction` (`infer.py:125`): a poison description byte-equal to an existing one would **overwrite** that key's sequence ⇒ violates "do not modify clean records." **⇒ enforce poison-description global uniqueness (plan §5.3).**
- Fragment mapping is keyed by `sequence` (`sampler.py:333-335`): if the payload sequence already exists, the entry must be **identical** to avoid a conflicting overwrite (plan §7.3).

### `[V-11]` ✅🎯 Seed propagation / generations per prompt
`set_seed(eval_seed)` is called **once** at the top of `evaluate()` — `eval.py:103-104`. `predict_results` iterates prompts in `test_data` order in batches of `eval.batch_size` (`eval.py:49-68`); **one generation per prompt per run.** ⇒ R=8 seeds = 8 separate `dvagen eval` runs with different `eval_seed`. Because RNG is global and consumed sequentially, and CLEAN vs POISONED consume different amounts of randomness (different candidate sets ⇒ different trajectories), **per-(prompt,seed) counterfactual identity is impossible without a per-prompt reseed.** Plan already frames pairing as "matched randomness, not counterfactual identity." **S6 action:** add a per-prompt `set_seed` (seed derived deterministically from `(eval_seed, target_id)`) so a given (target,seed) starts from an identical RNG state across conditions — strengthens pairing at near-zero cost.

### `[V-12]` ✅ Decoding defaults (freeze verbatim)
From `examples/eval.yaml`: `doc_top_k=16`; `do_sample=true`; `temperature=0.7`; `top_k=950`; `max_new_tokens=256`; **`top_p` unset**; `eval_seed=0`; `batch_size=1`; `phrase_encoder_batch_size=100000`. `eval.py:62-66` passes only `do_sample, temperature, top_k, max_new_tokens` to `infer` (not `top_p`, not `max_length`). Record these verbatim in the pre-registration. **[confirm@S1]** against any values baked into the checkpoint's `generation_config.json`.

### `[V-13]` ✅🎯 Joint softmax location & addressability
`logits = hidden_states @ dva_output_embeddings.T` — `modeling_dva.py:320`, where `dva_output_embeddings = cat([sv_output_embeddings (V), *dv_embeds (M)])` — `modeling_dva.py:229-230`. **Fragment columns are the contiguous tail `[V : V+M]`, directly index-addressable.** Fragment vs token at decode is `id >= static_vocab` (`infer.py:188`, `tokenization_dva.py:108`). **Mask point:** reuse the pattern in `DVALogitsProcessor.__call__` (`modeling_dva.py:360-368`) — `scores[i].index_fill_(0, poison_frag_ids, -inf)` — for Control-3. **LOG HOOK C** = per-step scores (available via `output_scores=True`, already used in the `visualize` path, `infer.py:163,176-193`).

### `[V-14]` ✅🎯 Batch-shared candidate sets
`batch_encode` builds a **single shared** phrase block for the whole batch (`combined_phrase_ids` concatenates every query's phrases; ids offset by cumulative count) and restricts each row to its own phrases via per-row `mask_ids` fed to `DVALogitsProcessor` — `tokenization_dva.py:58-100`, `infer.py:151,162`. So at `batch_size>1` all queries' fragments coexist in the logit space but are `-inf`-masked per row (functionally isolated, but M and fragment indices depend on batch composition). **`eval.yaml` default `batch_size: 1`** ⇒ no shared block in the default config. **Action:** keep `batch_size=1` for the study (already the default); note the throughput cost.

### `[V-15]` ✅🎯 Metric regime (norm hub feasibility)
Same resolution as `[V-3]`: **L2 on L2-normalized embeddings ⇒ angular/cosine only.** A large-norm passage gains **no** universal advantage (norms are ~1). ⇒ **Attack-U H2 (norm hub) is inapplicable by construction**; hubs must be angular (near dense query-embedding centroids). Report the normalization as a (mild) positive robustness property.

### `[V-16]` ⚠️ Ingest length limit / near-dup filtering
No per-record normalization, dedup, or near-duplicate filtering at add time in the index path (`retriever.py:73-84`) — beyond the sequence-mapping dict-key collapse noted in `[V-10]`. Hub-description length is bounded only by the encoder's `max_seq_length` (`[V-4]`, **[confirm@S1]**). `m` near-identical hub records survive as distinct index vectors (only their shared *description key* would collapse in the sequence-mapping dict — give each hub a unique description, which the hub methods do anyway).

---

---

## Confirmed against the downloaded artifacts (2026-08-10)

Downloaded to `artifacts/upstream/`, revisions pinned in `UPSTREAM_REVISIONS.json`:
checkpoint `nwliu/ProDVa-Molinst-SwissProtCLAP` @ `7dc7ff11…`, dataset
`nwliu/Molinst-SwissProtCLAP` @ `674dbb85…`.

### Model composition (from `checkpoint/config.json`)
| Component | Model | Size |
|---|---|---|
| text encoder | `gpt2` | 768 d, 12 layers |
| language model | `nferruz/ProtGPT2` | 1280 d, 36 layers, vocab **50257** |
| phrase encoder | `nferruz/ProtGPT2` | 1280 d, 36 layers |

- **`static_vocab` = 50257** — so a generated id `>= 50257` is a dynamic-vocabulary fragment. Resolves the last `[V-13]` unknown.
- `torch_dtype: float32`; checkpoint is 7.23 GB across 2 shards; `transformers_version 4.51.3`.
- `type_classification_head_num_classes: 6`.

### `[V-12]` decoding — now fully closed
`generation_config.json` contains only `{"_from_model_config": true, "transformers_version": "4.51.3"}` — **no overrides**. The `examples/eval.yaml` values are exactly what runs: `doc_top_k=16`, `do_sample=true`, `temperature=0.7`, `top_k=950`, `max_new_tokens=256`, `batch_size=1`, `eval_seed=0`.

### `[V-3]`/`[V-15]` index — now empirically confirmed, not inferred
Parsed straight from `dataset/index/index.faiss`:
- fourcc `IxF2` = **IndexFlat**, `metric_type=1` = **METRIC_L2**, `d=768`, `ntotal=712,248`.
- File size matches `45 + ntotal*d*4` **byte for byte** ⇒ plain uncompressed flat storage, no quantiser, no approximation.
- Stored row L2 norms are **exactly 1.0** ⇒ `normalize_embeddings=True` confirmed from the data itself. **L2 ranking ≡ cosine ranking**, and **H2 (norm hub) is dead by construction** — this is now an empirical result, not a code reading.
- Exact flat search ⇒ every poison record is exactly one added vector and retrieval is deterministic. Good for the paired design.

### `[V-4]`/`[V-16]` retrieval encoder
Neither released repo ships it. The paper says *"We employ PubMedBERT as the embedding model to retrieve the top K most similar descriptions using the txtai framework."* The matching sentence-transformers model — published by txtai's own author — is **`NeuML/pubmedbert-base-embeddings`**: 768 d, **mean pooling**, **max_seq_length 512**. Consistent with every observed index property.
**Not yet proven.** `tools/verify_encoder.py` settles it by re-encoding `training.json[0:8]` and comparing to index rows 0–8 (row *i* must be record *i*, per `retriever.py:77-82`). S1 is gated on this passing.

### Corpus and split sizes
| File | Records | Note |
|---|---|---|
| `training.json` | **712,248** | supporting corpus **and** the description→sequence map; exactly matches index `ntotal` |
| `validation.json` | 19,010 | |
| `test.json` | **5,876** | eval set; matches the paper's Mol-Instructions test size |
| `phrases.json` | **546,179** sequences / **1,878,306** fragments | ~3.44 fragments per sequence |

**`phrases.json` covers only 546,179 of 712,248 corpus sequences (76.7%).** So **~166K corpus proteins contribute zero fragments when retrieved.** A poison record must have its payload sequence present in `phrases.json` or it contributes nothing — reinforces `[V-6]`.

### Text-length reality (matters for §8.3 and Attack U)
| | median | p95 | max |
|---|---|---|---|
| test.json query (words) | 85 | 175 | 266 |
| corpus description (words) | 57 | 238 | 1,995 |

- **No query is truncated** at 512 tokens (max ≈ 360 tokens). Earlier concern about query truncation does not apply.
- Some **corpus descriptions do exceed 512 tokens** and are truncated. Keep poison/hub descriptions under ~380 words so they encode in full.
- **Queries and corpus records are stylistically very different**: queries are long multi-part design instructions ("Develop a protein sequence with… 1. … 2. … 3. …"), corpus records are terse UniProt-style function blurbs. Both go through the same encoder. Poison and hub descriptions should be tuned toward the **query** region of the space, not written in corpus style.

### The repo ships no metrics
`report_metrics` for `PROTEIN_DESIGN` logs *"Evaluation on protein design metrics will be supported in a future version"*, returns `None`, and the compute call is commented out (`eval.py:82-99`). **`dvagen eval` only generates sequences and writes them to JSON.** Every number in the paper's Table 2 (PPL, Rep, pLDDT, PAE, ProTrek, EvoLlama, Retrieval Accuracy, MMseqs2 diversity) must be built by us — this is real, unbudgeted S1/S10 scope.

**Free instrumentation:** saved records already contain `ids` (`eval.py:70-73`), so fragment selections (`id >= 50257`) are observable **with no code change at all** — PFSR/PFIR need no patch to hook C for the basic counts.

**Resume hazard:** `evaluate()` skips generation and re-reads the file if `save_results_path` already exists (`eval.py:107-110`). Every condition/seed must get a unique output path.

### Published baseline to reproduce (paper Table 2, Mol-Instructions, n=5,876)
| PPL | Rep | pLDDT | %>70 | PAE | %<10 | ProTrek | EvoLlama | Retrieval Acc | Diversity |
|---|---|---|---|---|---|---|---|---|---|
| 415.63 | 0.02 | 76.86 | 76.35 | 8.66 | 68.06 | 17.40 | 51.10 | 59.07 | 83.29 |

(*Natural* reference: pLDDT 80.64, PAE 9.20, ProTrek 27.00, EvoLlama 60.33.)

### Still open
- Empirical encoder confirmation (`tools/verify_encoder.py`, gated in the S1 job).
- Whether `phrase_encoder_batch_size` from the config (64) or `eval.yaml` (100000) wins at inference — cosmetic, affects speed only.
