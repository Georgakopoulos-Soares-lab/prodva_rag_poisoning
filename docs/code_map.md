# S0 Recon — Code Map (`dvagen eval` → token/fragment logits)

**Pinned commit:** `ff2d41c8be77a27c116c2b70fc1255441ede4107`
All paths relative to `third_party/ProDVa/`.

## Annotated call chain

```
src/cli.py                              # CLI entry: dvagen chat/eval/train
  └─ dvagen/infer/eval.py :: evaluate(eval_args)            eval.py:102
       ├─ set_seed(eval_seed)                                eval.py:104   ⟵ [V-11] single global seed
       └─ predict_results(eval_args)                         eval.py:16
            ├─ prepare(...)                                  infer.py:22
            │    ├─ DVAModel.from_pretrained(device_map=auto) infer.py:53   (GPT-2 text enc + ProtGPT2 LM + ProtGPT2 phrase enc)
            │    ├─ ProteinFragmentSampler(mapping_file=…)   infer.py:83   ⟵ [V-6][V-7] fragments from FILE, keyed by sequence
            │    ├─ DVATokenizer(static_vocab=LM.vocab_size) infer.py:90   ⟵ static_vocab boundary = |V_tokens|
            │    └─ FAISSRetriever(embedding_model, vector_store_path) infer.py:100 / retriever.py:42  [V-1][V-3]
            └─ for each batch of prompts (batch_size):       eval.py:49    ([V-14] default bs=1)
                 └─ infer(model, sampler, tokenizer, retriever, queries, doc_top_k, **decoding)  infer.py:110
                      ├─ load protein_sequence_mapping_file  infer.py:123  ⟵ [V-2] dict keyed by description string
                      ├─ retriever.retrieve_documents(q, K)  retriever.py:90  ⟵ ★ LOG HOOK A (retrieval)
                      │     └─ vector_store.similarity_search(q, k=K)  retriever.py:91  (no scores; use *_with_score to log L2)
                      ├─ hits → sequences via mapping         infer.py:128-131  (sequence_mappings[doc.content])
                      ├─ phrase_sampler.sample(seq) per hit   infer.py:132-135  ⟵ ★ LOG HOOK B (vocabulary)
                      │     └─ ProteinFragmentSampler.sample  sampler.py:401  → get_fragments (mapping.get) sampler.py:337
                      ├─ tokenizer.batch_encode(...)          infer.py:136 / tokenization_dva.py:58
                      │     └─ phrase id = static_vocab + running_index  tokenization_dva.py:49  ([V-9] no dedup/cap)
                      │        per-row mask_ids for other queries' phrases tokenization_dva.py:93-99 ([V-14])
                      ├─ model.get_dva_embeddings(phrase_ids) modeling_dva.py:205
                      │     └─ dva_output_embeddings = cat([sv (V), dv (M)]) modeling_dva.py:229-230
                      └─ model.generate(..., DVALogitsProcessor(mask_phrase_ids), output_scores=visualize) infer.py:155
                            └─ DVAModel.forward → logits = h @ dva_output_embeddings.T  modeling_dva.py:320
                                                                 ⟵ ★ LOG HOOK C / MASK POINT ([V-13])
                            └─ DVALogitsProcessor.__call__ index_fill_(-inf) modeling_dva.py:360-368 (mask template)
                 └─ tokenizer.decode(...) → {decoded_sentence, ids}  infer.py:171 / tokenization_dva.py:102
       └─ save_results_path (json.dump)                       eval.py:75-77  ⟵ ★ LOG HOOK D (output)
```

## Hook placement summary

| Hook | Function / file:line | Reads | Provenance block |
|---|---|---|---|
| **A** retrieval | `FAISSRetriever.retrieve_documents` `retriever.py:90` | query, K, hit ids, L2 scores (via `_with_score`) | ordered hits, per-hit score, `is_poison` (by corpus id), poison rank |
| **B** vocabulary | phrase assembly `infer.py:132-135`; `ProteinFragmentSampler.sample` `sampler.py:401` | per-hit sequence, fragment list, type/name/description | candidate fragments w/ source corpus id, frag index, type, length |
| **C** decode | `DVAModel.forward` logits `modeling_dva.py:320`; scores via `output_scores` `infer.py:163,176` | per-step logits over V∪S | per-step sampled id, `id≥static_vocab?`, poison-fragment mass, top-5 |
| **C-mask** | `DVALogitsProcessor` `modeling_dva.py:360` (template) | poison fragment column ids | Control-3 mask |
| **D** output | `predict_results` writer `eval.py:75` | final sequence | sequence, length, config/seed hashes |

## Files to modify (S6), all additive/logging-only
- `retriever.py` — hook A (switch to `similarity_search_with_score`, thread `recorder`).
- `infer.py` — hooks B & C wiring; per-prompt reseed for `[V-11]`; recorder lifecycle.
- `modeling_dva.py` — hook C source (already exposes scores); new `DVALogitsProcessor`-style poison mask behind a config flag.
- `eval.py` — hook D, recorder flush, batch pinning.
- `configs/infer_args.py` (or a namespaced module) — add `prodva_attack.provenance_path`, `prodva_attack.mask_fragment_source_ids`.
- new `src/dvagen/provenance.py`.

## Three attacker-writable artifacts (poison insertion surface)
1. **data file** (`infer.data_file`) — `{"instruction","sequence"}[]`; `instruction` builds the index vector (`retriever.py:77`).
2. **`protein_sequence_mapping_file`** — `{"instruction","sequence"}[]` → dict keyed by `instruction` (`infer.py:125`). Must be globally unique per `[V-10]`.
3. **`protein_fragment_mapping_file`** — `{"sequence","phrases":[{phrase,type,name,description}]}[]` → dict keyed by `sequence` (`sampler.py:333`). Payload sequence must be present or it contributes 0 fragments (`[V-6]`).

## Model composition (confirm sizes @S1)
`DVAModel` = text encoder (`AutoModel`, GPT-2-family) + `language_model` (`AutoModelForCausalLM`, ProtGPT2 ≈738M) + `phrase_encoder` (`AutoModel`, ProtGPT2) — `modeling_dva.py:46-48,127-129`. Aux heads (`type_classification_head`, `description_proj`) exist but are inactive at inference (only in `forward` loss branch, `modeling_dva.py:327-343`). Loaded with `device_map="auto"` (`infer.py:54`).
