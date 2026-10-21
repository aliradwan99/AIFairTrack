"""Retrieval benchmark: does search return passages that actually answer the question?

A retrieved chunk counts as relevant if it contains any of the case's evidence terms.
Evidence terms (rather than hand-picked page numbers) keep labels checkable and
independent of how the PDFs are chunked. This is a lenient proxy for relevance:
a passage that mentions a term in passing still counts.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aims_track.rag.ingest import EMBED_MODEL
from aims_track.rag.retriever import search_policy, get_vectorstore

CASES_PATH = ROOT / "evals" / "retrieval_cases.json"
RESULTS_DIR = ROOT / "evals" / "results"
BOILERPLATE_MARKERS = ("available free of charge", "doi.org/10.6028")
K = 8


def is_relevant(text: str, terms: list) -> bool:
    t = text.lower()
    return any(term.lower() in t for term in terms)


def is_boilerplate(text: str) -> bool:
    t = text.lower()
    return any(m in t for m in BOILERPLATE_MARKERS)


def check_labels(cases: list) -> tuple[int, list]:
    """Every case's evidence must exist somewhere in the index, or the label is wrong."""
    corpus = get_vectorstore().get()["documents"]
    missing = [c["id"] for c in cases if not any(is_relevant(d, c["evidence_terms"]) for d in corpus)]
    return len(corpus), missing


def evaluate(cases: list, k: int = K) -> tuple[dict, list]:
    rows = []
    for c in cases:
        results = search_policy(c["question"], k=k)
        relevant = [is_relevant(r["text"], c["evidence_terms"]) for r in results]
        first = next((i + 1 for i, hit in enumerate(relevant) if hit), None)
        rows.append({
            "id": c["id"],
            "first_relevant_rank": first,
            "boilerplate_in_top_k": sum(is_boilerplate(r["text"]) for r in results),
            "top_3": [f"{r['source']} p.{r['page']}" for r in results[:3]],
        })

    n = len(rows)
    ranks = [r["first_relevant_rank"] for r in rows]
    summary = {
        "cases": n,
        "hit@1": round(sum(1 for x in ranks if x == 1) / n, 3),
        "hit@4": round(sum(1 for x in ranks if x and x <= 4) / n, 3),
        f"hit@{k}": round(sum(1 for x in ranks if x) / n, 3),
        "mrr": round(sum(1 / x for x in ranks if x) / n, 3),
        "boilerplate_rate": round(sum(r["boilerplate_in_top_k"] for r in rows) / (n * k), 3),
    }
    return summary, rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="baseline", help="Name for this run, e.g. baseline")
    args = parser.parse_args()

    cases = json.loads(CASES_PATH.read_text())

    corpus_size, missing = check_labels(cases)
    print(f"Index: {corpus_size} chunks | embedding model: {EMBED_MODEL}")
    if missing:
        print(f"LABEL ERROR: evidence terms not found anywhere in the index for: {missing}")
        print("Fix these cases in retrieval_cases.json before trusting the scores.\n")

    summary, rows = evaluate(cases)

    print(f"\n{'case':<24}{'rank':<8}{'junk':<6}top 3 results")
    print("-" * 90)
    for r in rows:
        rank = str(r["first_relevant_rank"]) if r["first_relevant_rank"] else "MISS"
        print(f"{r['id']:<24}{rank:<8}{r['boilerplate_in_top_k']:<6}{', '.join(r['top_3'])}")

    print("\nSUMMARY")
    for key, val in summary.items():
        print(f"  {key:<18}{val}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"retrieval_{args.label}.json"
    out.write_text(json.dumps({
        "label": args.label,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "embedding_model": EMBED_MODEL,
        "index_chunks": corpus_size,
        "label_errors": missing,
        "summary": summary,
        "cases": rows,
    }, indent=2))
    print(f"\nSaved to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
