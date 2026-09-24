"""Auto-loaded shim (env/shims is on PYTHONPATH via env/project_env.sh).

ProDVa's FAISSRetriever moves the index to GPU with faiss.index_cpu_to_all_gpus whenever
torch sees a CUDA device (retriever.py:88). We run faiss-cpu (the GPU faiss builds are
unavailable on this cluster -- see env/setup_gen_env.sh), which cannot execute that call.
Since the released index is an exact IndexFlatL2, CPU search returns identical Top-K
results, so we neutralize that single call here rather than editing third_party/ProDVa.
"""
try:
    import faiss

    if getattr(faiss, "get_num_gpus", lambda: 0)() == 0:
        faiss.index_cpu_to_all_gpus = lambda index, *args, **kwargs: index
except Exception:
    pass
