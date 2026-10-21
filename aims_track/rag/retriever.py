"""Search the NIST policy index and return passages with source and page citations."""
from functools import lru_cache

from langchain_chroma import Chroma

from aims_track.rag.ingest import DB_DIR, COLLECTION, get_embeddings


@lru_cache(maxsize=1)
def get_vectorstore():
    # Cached so the embedding model loads only once per session
    return Chroma(
        collection_name=COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=str(DB_DIR),
    )


def search_policy(query: str, k: int = 4) -> list[dict]:
    results = get_vectorstore().similarity_search(query, k=k)
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
