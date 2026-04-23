# Backends

This directory keeps the active runtime backends used by the current
workflow-first CrossExtend-KG mainline.

## Scope

- `llm.py`
  external LLM request handling for preprocessing and attachment
- `embeddings.py`
  embedding backend construction and similarity helpers
- `faiss_cache.py`
  local embedding cache support for repeated routing runs

These files are still part of the live repository contract and are not
historical leftovers.
