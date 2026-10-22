"""Prompt-injection guardrails for the audit agent.

Layer 1, input sanitization: column names and group values reach the LLM, so any that fall
outside a strict allowlist (letters, digits, spaces, _ - . ; max 40 chars) are replaced with
neutral aliases before the agent sees them. An allowlist is used instead of keyword filters,
which both miss reworded attacks and block legitimate labels (a group named "low income").
Layer 2, prompt hardening, lives in graph.py.
Layer 3, output policy: deterministic checks on the final report.
"""
import re

import pandas as pd

SAFE_LABEL = re.compile(r"^[A-Za-z0-9 _\-.]{1,40}$")
URL_RE = re.compile(r"https?://[^\s)\]]+|www\.[^\s)\]]+", re.I)
ALLOWED_URL_PARTS = ("nist.gov", "doi.org/10.6028")
RISK_SECTION_RE = re.compile(r"(#+\s*Risk level\s*\n)(.*?)(?=\n#|\Z)", re.S | re.I)


def is_unsafe_label(value) -> bool:
    return not SAFE_LABEL.match(str(value).strip())


def sanitize_inputs(df: pd.DataFrame, label_col: str, group_col: str, privileged: str, unprivileged: str):
    """Alias unsafe column names and group values. Returns the cleaned inputs plus findings."""
    findings = []

    col_map = {}
    for i, c in enumerate(df.columns, start=1):
        if c != "text" and is_unsafe_label(c):
            col_map[c] = f"column_{i}"
            findings.append({"kind": "column name", "original": str(c)[:120], "alias": col_map[c]})
    df = df.rename(columns=col_map)
    label_col = col_map.get(label_col, label_col)
    group_col = col_map.get(group_col, group_col)

    values = df[group_col].astype(str).str.strip()
    val_map = {}
    for j, v in enumerate(sorted(values.unique()), start=1):
        if is_unsafe_label(v):
            val_map[v] = f"group_{j}"
            findings.append({"kind": "group value", "original": v[:120], "alias": val_map[v]})
    if val_map:
        df = df.copy()
        df[group_col] = values.replace(val_map)

    privileged = val_map.get(str(privileged).strip(), str(privileged))
    unprivileged = val_map.get(str(unprivileged).strip(), str(unprivileged))
    return df, label_col, group_col, privileged, unprivileged, findings


def risk_level(report: str) -> str:
    m = RISK_SECTION_RE.search(report)
    text = m.group(2) if m else report
    w = re.search(r"\b(low|medium|high)\b", text, re.I)
    return w.group(1).lower() if w else "unparsed"


def enforce_output_policy(report: str, metrics: dict) -> tuple[str, list]:
    """Remove non-NIST links; reject a Low rating when disparate impact fails the four-fifths rule."""
    issues = []

    bad_urls = {u for u in URL_RE.findall(report) if not any(p in u.lower() for p in ALLOWED_URL_PARTS)}
    for u in bad_urls:
        report = report.replace(u, "[link removed by policy check]")
    if bad_urls:
        issues.append(f"Removed {len(bad_urls)} unapproved link(s).")

    di = (metrics.get("disparate_impact") or {}).get("disparate_impact")
    if di is not None and di < 0.8 and risk_level(report) == "low":
        note = (f"**High** (set by automated policy check: disparate impact of {di} fails the "
                "four-fifths rule, so the model's rating of Low was rejected).\n")
        if RISK_SECTION_RE.search(report):
            report = RISK_SECTION_RE.sub(lambda m: m.group(1) + note, report, count=1)
        else:
            report = "## Risk level\n" + note + "\n" + report
        issues.append("Risk level 'Low' contradicted the metrics and was overridden to High.")

    return report, issues
