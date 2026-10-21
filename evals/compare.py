"""Print every retrieval benchmark run side by side, oldest first."""
import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
runs = sorted((json.loads(p.read_text()) for p in RESULTS.glob("retrieval_*.json")),
              key=lambda r: r["timestamp"])

print(f"{'run':<22}{'model':<22}{'filter':<8}{'hit@1':<8}{'hit@4':<8}{'hit@8':<8}{'mrr':<8}{'junk':<7}misses")
print("-" * 120)
for r in runs:
    s = r["summary"]
    misses = [c["id"] for c in r["cases"] if not c["first_relevant_rank"]]
    model = r["embedding_model"].split("/")[-1][:20]
    filt = "yes" if r.get("filter_boilerplate") else "no"
    print(f"{r['label']:<22}{model:<22}{filt:<8}{s['hit@1']:<8}{s['hit@4']:<8}{s['hit@8']:<8}"
          f"{s['mrr']:<8}{s['boilerplate_rate']:<7}{', '.join(misses) or '-'}")
