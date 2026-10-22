"""Print every retrieval benchmark run side by side, grouped by question set, oldest first."""
import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
runs = sorted((json.loads(p.read_text()) for p in RESULTS.glob("retrieval_*.json")),
              key=lambda r: (r.get("cases_file", "retrieval_cases.json"), r["timestamp"]))

print(f"{'set':<9}{'run':<26}{'model':<18}{'rewrite':<10}{'hit@1':<8}{'hit@4':<8}{'mrr':<8}misses")
print("-" * 120)
for r in runs:
    s = r["summary"]
    qset = "heldout" if "heldout" in r.get("cases_file", "") else "dev"
    misses = [c["id"] for c in r["cases"] if not c["first_relevant_rank"]]
    model = r["embedding_model"].split("/")[-1][:16]
    print(f"{qset:<9}{r['label']:<26}{model:<18}{r.get('query_rewrite', 'off'):<10}"
          f"{s['hit@1']:<8}{s['hit@4']:<8}{s['mrr']:<8}{', '.join(misses) or '-'}")
