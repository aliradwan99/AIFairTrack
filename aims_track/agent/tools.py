"""Tools the agent can call. The LLM passes column names and values; Python does the math."""
import json

import pandas as pd
from langchain_core.tools import tool

from aims_track.modules.metrics import group_rates, disparate_impact, max_rate_gap
from aims_track.rag.retriever import search_policy


def _as_str(df: pd.DataFrame, *cols: str) -> pd.DataFrame:
    """Compare everything as text, so '1' matches 1 and 'A' matches 'A '."""
    out = df.copy()
    for c in cols:
        out[c] = out[c].astype(str).str.strip()
    return out


def make_tools(df: pd.DataFrame) -> list:
    """Build the tool set for one dataset. Each tool closes over df."""

    def _missing(*cols: str):
        bad = [c for c in cols if c not in df.columns]
        if bad:
            return json.dumps({"error": f"Unknown column(s): {bad}. Available: {list(df.columns)}"})
        return None

    @tool
    def describe_dataset() -> str:
        """Describe the dataset: row count, column names, and distinct values of each
        non-text column. Call this first to learn which columns and values exist."""
        info = {"rows": len(df), "columns": list(df.columns), "distinct_values": {}}
        for c in df.columns:
            if c == "text":
                continue
            vals = df[c].astype(str).str.strip().unique().tolist()
            shown = vals[:20]
            if len(vals) > 20:
                shown.append(f"... ({len(vals)} distinct values total)")
            info["distinct_values"][c] = shown
        return json.dumps(info)

    @tool
    def get_group_rates(label_col: str, group_col: str, positive_label: str) -> str:
        """Positive-outcome rate and sample size (n) for each group.
        positive_label is the label value that counts as a positive outcome, e.g. '1'."""
        err = _missing(label_col, group_col)
        if err:
            return err
        d = _as_str(df, label_col, group_col)
        rates = group_rates(d, label_col, group_col, str(positive_label).strip())
        counts = d[group_col].value_counts()
        result = [
            {
                "group": row[group_col],
                "positive_rate": round(float(row["positive_rate"]), 4),
                "n": int(counts[row[group_col]]),
            }
            for _, row in rates.iterrows()
        ]
        return json.dumps(result)

    @tool
    def get_disparate_impact(
        label_col: str, group_col: str, privileged: str, unprivileged: str, positive_label: str
    ) -> str:
        """Disparate impact ratio: positive rate of the unprivileged group divided by that of
        the privileged group. Below 0.8 fails the four-fifths rule used to flag adverse impact."""
        err = _missing(label_col, group_col)
        if err:
            return err
        d = _as_str(df, label_col, group_col)
        di = disparate_impact(
            d, label_col, group_col,
            str(privileged).strip(), str(unprivileged).strip(), str(positive_label).strip(),
        )
        if di is None:
            return json.dumps({
                "disparate_impact": None,
                "note": "Not computable: a group value was not found, or the privileged "
                        "group has a 0% positive rate. Check values with describe_dataset.",
            })
        return json.dumps({
            "disparate_impact": round(di, 4),
            "fails_four_fifths_rule": di < 0.8,
            "outside_0.8_to_1.25_band": di < 0.8 or di > 1.25,
        })

    @tool
    def get_max_rate_gap(label_col: str, group_col: str, positive_label: str) -> str:
        """Largest difference in positive-outcome rate between any two groups (0 to 1)."""
        err = _missing(label_col, group_col)
        if err:
            return err
        d = _as_str(df, label_col, group_col)
        gap = max_rate_gap(d, label_col, group_col, str(positive_label).strip())
        return json.dumps({"max_rate_gap": round(gap, 4), "exceeds_0.2": gap > 0.2})

    @tool
    def search_nist_policy(query: str) -> str:
        """Search the NIST AI Risk Management Framework (AI 100-1) and the NIST Generative AI
        Profile (AI 600-1). Returns passages with document name and page number for citation."""
        return json.dumps(search_policy(query, k=4))

    return [describe_dataset, get_group_rates, get_disparate_impact, get_max_rate_gap, search_nist_policy]


if __name__ == "__main__":
    from aims_track.rag.ingest import ROOT

    df = pd.read_csv(ROOT / "aims_track" / "examples" / "example_nlp.csv")
    tools = {t.name: t for t in make_tools(df)}
    args = {"label_col": "predicted_label", "group_col": "group", "positive_label": "1"}

    print("describe_dataset:", tools["describe_dataset"].invoke({}))
    print("group_rates:", tools["get_group_rates"].invoke(args))
    print("disparate_impact:", tools["get_disparate_impact"].invoke({**args, "privileged": "A", "unprivileged": "B"}))
    print("max_rate_gap:", tools["get_max_rate_gap"].invoke(args))
    print("bad column test:", tools["get_group_rates"].invoke({**args, "group_col": "gender"}))
    print("nist search:", tools["search_nist_policy"].invoke({"query": "disparate impact"})[:300], "...")
