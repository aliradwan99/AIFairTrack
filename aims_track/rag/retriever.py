"""Search the NIST policy index and return passages with source and page citations.

QUERY_REWRITE env var: "off", "plain" (default, chosen by held-out benchmark), or "taxonomy". When on, the question is
also rewritten into NIST vocabulary, both queries are searched, and results are merged
with reciprocal rank fusion, so a poor rewrite cannot fully replace the original query.
"""
import os

# Must be set before torch/tokenizers load: avoids thread clashes and crashes on macOS
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import threading

from langchain_chroma import Chroma

from aims_track.rag.ingest import DB_DIR, COLLECTION, get_embeddings

REWRITE_MODE = os.getenv("QUERY_REWRITE", "plain")
RRF_K = 60  # standard reciprocal rank fusion constant

_store = None
_store_lock = threading.Lock()
_search_lock = threading.Lock()


def get_vectorstore():
    """Load the vector store once. The lock stops parallel agent tool calls
    from opening the database and embedding model at the same time."""
    global _store
    with _store_lock:
        if _store is None:
            _store = Chroma(
                collection_name=COLLECTION,
                embedding_function=get_embeddings(),
                persist_directory=str(DB_DIR),
            )
    return _store


def _search(query: str, k: int):
    store = get_vectorstore()
    with _search_lock:  # serialize searches; they're fast, so this costs almost nothing
        return store.similarity_search(query, k=k)


def _key(d) -> tuple:
    return (d.metadata.get("source_doc"), d.metadata.get("page_number"), d.page_content[:100])


def search_policy(query: str, k: int = 4, rewrite: str | None = None) -> list[dict]:
    mode = REWRITE_MODE if rewrite is None else rewrite
    rewritten = None

    if mode == "off":
        docs = _search(query, k)
    else:
        from aims_track.rag.query_rewrite import rewrite_query  # lazy import avoids a cycle
        rewritten = rewrite_query(query, mode)
        scores, by_key = {}, {}
        for pool in (_search(query, k * 2), _search(rewritten, k * 2)):
            for rank, d in enumerate(pool, start=1):
                key = _key(d)
                by_key[key] = d
                scores[key] = scores.get(key, 0) + 1 / (RRF_K + rank)
        docs = [by_key[key] for key in sorted(scores, key=scores.get, reverse=True)[:k]]

    return [
        {
            "source": d.metadata.get("source_doc"),
            "page": d.metadata.get("page_number"),
            "text": d.page_content,
            "rewritten_query": rewritten,
        }
        for d in docs
    ]


if __name__ == "__main__":
    for q in [
        "harmful bias across demographic groups",
        "measuring fairness in AI system outputs",
    ]:
        print(f"\n=== {q} ===")
        for r in search_policy(q, k=2):
            print(f"[{r['source']} p.{r['page']}] {r['text'][:200]}...")
