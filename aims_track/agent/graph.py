"""LangGraph audit pipeline: compute metrics -> agent analysis with NIST retrieval -> citation check."""
import json
import re
from typing import TypedDict

import pandas as pd
from langchain.agents import create_agent
from langchain_core.messages import ToolMessage
from langgraph.graph import StateGraph, START, END

from aims_track.agent.llm import get_llm, PRIMARY_MODEL, FALLBACK_MODEL
from aims_track.agent.tools import make_tools

SYSTEM_PROMPT = """You are AIFairTrack's fairness auditor. You analyze group-level outcome metrics
for an AI system and write a concise risk report grounded in the NIST AI Risk Management Framework.

Rules:
1. Use only numbers that appear in the pre-computed metrics or in tool results. Never estimate or invent statistics.
2. Before writing, call search_nist_policy at least twice with focused queries relevant to the findings
   (for example: managing harmful bias, measuring disparities across groups, ongoing monitoring).
3. Cite NIST guidance only from passages the search tool returned, in exactly this format: [NIST_AI_100-1 p.22].
   Never cite a document or page you did not retrieve.
4. Consider sample size. Groups with n under 30 give unreliable rates; say so when it applies.
5. Be precise and neutral. Metrics show statistical disparity, not proof of intent or legal discrimination.

Report format (Markdown):
## Summary
2-3 sentences.
## Findings
The key metrics and what they mean.
## Risk level
Low, Medium, or High, with a one-sentence justification.
## NIST guidance
Relevant points, each with a citation.
## Recommended actions
3-5 specific, practical steps.
## Limitations
What this analysis cannot tell you."""

CITATION_RE = re.compile(r"\[(NIST_AI_\d{3}-1)\s+p\.\s*(\d+)\]")


class AuditState(TypedDict, total=False):
    label_col: str
    group_col: str
    positive_label: str
    privileged: str
    unprivileged: str
    metrics: dict
    report: str
    model_used: str
    retrieved: list
    citation_check: dict


def build_audit_graph(df: pd.DataFrame):
    tools = make_tools(df)
    by_name = {t.name: t for t in tools}

    def compute_metrics(state: AuditState) -> dict:
        """Deterministic step: all numbers come from Python, never from the LLM."""
        args = {k: state[k] for k in ("label_col", "group_col", "positive_label")}
        di_args = {**args, "privileged": state["privileged"], "unprivileged": state["unprivileged"]}
        return {"metrics": {
            "dataset": json.loads(by_name["describe_dataset"].invoke({})),
            "group_rates": json.loads(by_name["get_group_rates"].invoke(args)),
            "disparate_impact": json.loads(by_name["get_disparate_impact"].invoke(di_args)),
            "max_rate_gap": json.loads(by_name["get_max_rate_gap"].invoke(args)),
        }}

    def analyze(state: AuditState) -> dict:
        """Agent step: the LLM decides what to retrieve and writes the report.
        Falls back to a second model if the primary is unavailable."""
        task = (
            f"Audit configuration: label column '{state['label_col']}', group column "
            f"'{state['group_col']}', positive label '{state['positive_label']}', privileged group "
            f"'{state['privileged']}', unprivileged group '{state['unprivileged']}'.\n\n"
            f"Pre-computed metrics:\n{json.dumps(state['metrics'], indent=2)}\n\n"
            "Write the fairness risk report."
        )
        last_err = None
        for model_name in (PRIMARY_MODEL, FALLBACK_MODEL):
            try:
                agent = create_agent(get_llm(model_name), tools=tools, system_prompt=SYSTEM_PROMPT)
                result = agent.invoke({"messages": [{"role": "user", "content": task}]})
                break
            except Exception as e:
                last_err = e
                print(f"[fallback] {model_name} failed: {str(e)[:100]}")
        else:
            raise RuntimeError(f"All models failed. Last error: {last_err}")

        # Record every NIST page the agent actually retrieved, for the citation check
        retrieved = []
        for m in result["messages"]:
            if isinstance(m, ToolMessage) and m.name == "search_nist_policy":
                try:
                    for p in json.loads(m.content):
                        retrieved.append([p["source"], p["page"]])
                except (json.JSONDecodeError, TypeError, KeyError):
                    pass

        return {"report": result["messages"][-1].text, "model_used": model_name, "retrieved": retrieved}

    def check_citations(state: AuditState) -> dict:
        """Deterministic hallucination guard: every citation must match a retrieved page."""
        allowed = {(s, int(p)) for s, p in state.get("retrieved", [])}
        cited = [(s, int(p)) for s, p in CITATION_RE.findall(state["report"])]
        unverified = sorted({c for c in cited if c not in allowed})
        return {"citation_check": {
            "citations_found": len(cited),
            "unverified": [f"{s} p.{p}" for s, p in unverified],
            "passed": len(cited) > 0 and not unverified,
        }}

    g = StateGraph(AuditState)
    g.add_node("compute_metrics", compute_metrics)
    g.add_node("analyze", analyze)
    g.add_node("check_citations", check_citations)
    g.add_edge(START, "compute_metrics")
    g.add_edge("compute_metrics", "analyze")
    g.add_edge("analyze", "check_citations")
    g.add_edge("check_citations", END)
    return g.compile()


def run_audit(df: pd.DataFrame, label_col: str, group_col: str, positive_label: str,
              privileged: str, unprivileged: str) -> dict:
    graph = build_audit_graph(df)
    return graph.invoke({
        "label_col": label_col, "group_col": group_col, "positive_label": str(positive_label),
        "privileged": str(privileged), "unprivileged": str(unprivileged),
    })


if __name__ == "__main__":
    from aims_track.rag.ingest import ROOT

    df = pd.read_csv(ROOT / "aims_track" / "examples" / "example_nlp.csv")
    result = run_audit(df, "predicted_label", "group", "1", "A", "B")

    print("\n" + "=" * 70)
    print(result["report"])
    print("=" * 70)
    print("Model used:", result["model_used"])
    print("Pages retrieved:", len(result["retrieved"]))
    print("Citation check:", result["citation_check"])
