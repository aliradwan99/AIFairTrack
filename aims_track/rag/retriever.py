"""Search the NIST policy index and return passages with source and page citations."""
import os

# Must be set before torch/tokenizers load: avoids thread clashes and crashes on macOS
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import threading

from langchain_chroma import Chroma

from aims_track.rag.ingest import DB_DIR, COLLECTION, get_embeddings

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


def search_policy(query: str, k: int = 4) -> list[dict]:
    store = get_vectorstore()
    with _search_lock:  # serialize searches; they're fast, so this costs almost nothing
        results = store.similarity_search(query, k=k)
    return [
        {
            "source": d.metadata.get("source_doc"),
            "page": d.metadata.get("page_number"),
            "text": d.page_content,
        }
        for d in results
    ]


if __name__ == "__main__":
    for q in [
        "harmful bias across demographic groups",
        "measuring fairness in AI system outputs",
    ]:
        print(f"\n=== {q} ===")
        for r in search_policy(q, k=2):
            print(f"[{r['source']} p.{r['page']}] {r['text'][:200]}...")
