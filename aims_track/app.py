"""AIFairTrack: fairness metrics, an agentic NIST-grounded risk report, and NIST policy Q&A."""
import sys
from pathlib import Path

# Make the project root importable when run via `streamlit run aims_track/app.py`
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from aims_track.modules.metrics import group_rates, disparate_impact, max_rate_gap
from aims_track.agent.graph import run_audit
from aims_track.rag.qa import answer_policy_question

EXAMPLES = ROOT / "aims_track" / "examples"
SAMPLES = {
    "NLP sample": EXAMPLES / "example_nlp.csv",
    "AR/VR annotations sample": EXAMPLES / "example_arvr.csv",
}


GROUP_HINTS = ("group", "protected_group", "demographic", "gender", "race", "age_group")
LABEL_HINTS = ("predicted_label", "prediction", "label", "outcome", "y_pred")


def default_index(options: list, hints: tuple) -> int:
    """Pick the first option whose name matches a hint, so columns aren't swapped by default."""
    lowered = [o.lower() for o in options]
    for h in hints:
        if h in lowered:
            return lowered.index(h)
    return 0


def citation_badge(check: dict):
    if check["passed"]:
        st.success(f"All {check['citations_found']} citations verified against retrieved NIST passages.")
    elif check["unverified"]:
        st.warning(f"Unverified citations (not in retrieved passages): {', '.join(check['unverified'])}")
    else:
        st.warning("The response contains no citations.")


st.set_page_config(page_title="AIFairTrack", page_icon="✅", layout="wide")
st.title("AIFairTrack — AI Fairness & Risk Monitoring")
st.caption(
    "Fairness metrics are computed in Python. Risk reports are written by an AI agent "
    "grounded in the NIST AI Risk Management Framework, with every citation verified."
)

audit_tab, ask_tab = st.tabs(["Fairness audit", "Ask NIST"])

# ---------------------------------------------------------------- Audit tab
with audit_tab:
    sample_choice = st.selectbox("Load sample data", ["None", *SAMPLES])
    uploaded = st.file_uploader("Or upload a CSV", type=["csv"])

    df, source_name = None, None
    if uploaded is not None:
        df, source_name = pd.read_csv(uploaded), uploaded.name
    elif sample_choice != "None":
        df, source_name = pd.read_csv(SAMPLES[sample_choice]), sample_choice

    if df is None:
        st.info("Choose a sample or upload a CSV (columns like `text`, `predicted_label`, `group`) to begin.")
    else:
        st.subheader("Preview")
        st.dataframe(df.head())

        c1, c2 = st.columns(2)
        with c1:
            group_options = [c for c in df.columns if c != "text"]
            group_col = st.selectbox("Protected group column", group_options,
                                     index=default_index(group_options, GROUP_HINTS))
            label_options = [c for c in df.columns if c not in (group_col, "text")]
            if not label_options:
                st.error("The CSV needs a label column besides the group and text columns.")
                st.stop()
            label_col = st.selectbox("Prediction/label column", label_options,
                                     index=default_index(label_options, LABEL_HINTS))
            positive_label = st.text_input("Positive label value", value="1").strip()
        with c2:
            groups = df[group_col].astype(str).str.strip().unique().tolist()
            privileged = st.selectbox("Privileged group", groups, index=0)
            unprivileged = st.selectbox("Unprivileged group", groups, index=len(groups) - 1)

        # Clear old results whenever the data or settings change
        config_key = (source_name, len(df), group_col, label_col, positive_label, privileged, unprivileged)
        if st.session_state.get("config_key") != config_key:
            st.session_state.config_key = config_key
            st.session_state.metrics = None
            st.session_state.audit = None

        if st.button("Evaluate", type="primary"):
            d = df.copy()
            d[group_col] = d[group_col].astype(str).str.strip()
            d[label_col] = d[label_col].astype(str).str.strip()
            label_values = sorted(d[label_col].unique().tolist())
            if positive_label not in label_values:
                st.error(
                    f"Positive label '{positive_label}' doesn't appear in column '{label_col}'. "
                    f"Values found: {label_values[:10]}. Check that the group and label "
                    "columns aren't swapped."
                )
                st.stop()
            st.session_state.metrics = {
                "rates": group_rates(d, label_col, group_col, positive_label),
                "di": disparate_impact(d, label_col, group_col, privileged, unprivileged, positive_label),
                "gap": max_rate_gap(d, label_col, group_col, positive_label),
            }

        m = st.session_state.get("metrics")
        if m:
            st.subheader("Group positive rates")
            st.dataframe(m["rates"])

            k1, k2, k3 = st.columns(3)
            k1.metric("Disparate impact", "N/A" if m["di"] is None else f"{m['di']:.3f}")
            k2.metric("Max rate gap", f"{m['gap']:.3f}")
            k3.metric("Fairness score (demo)", f"{max(0, min(100, 100 - m['gap'] * 100)):.1f}/100")

            out = m["rates"].copy()
            out["disparate_impact"] = m["di"]
            out["max_rate_gap"] = m["gap"]
            st.download_button("Download metrics CSV", out.to_csv(index=False),
                               file_name="aifairtrack_metrics.csv", mime="text/csv")

            st.divider()
            st.subheader("AI risk report")
            st.caption("An agent searches NIST guidance and writes a cited report. Takes 20 to 60 seconds.")

            if st.button("Generate AI risk report"):
                with st.spinner("Agent is analyzing the metrics and searching NIST guidance..."):
                    try:
                        st.session_state.audit = run_audit(
                            df, label_col, group_col, positive_label, privileged, unprivileged
                        )
                    except Exception as e:
                        st.error(f"Report generation failed: {e}")

            a = st.session_state.get("audit")
            if a:
                citation_badge(a["citation_check"])
                for f in a.get("input_findings", []):
                    st.warning(f"Possible prompt injection in a {f['kind']}: shown to the agent as "
                               f"'{f['alias']}' instead. Original: {f['original']}")
                for issue in a.get("policy_check", {}).get("issues", []):
                    st.warning(f"Policy check: {issue}")
                st.caption(f"Model: {a['model_used']}  ·  NIST passages retrieved: {len(a['retrieved'])}")
                st.markdown(a["report"])
                st.download_button("Download report (Markdown)", a["report"],
                                   file_name="aifairtrack_report.md", mime="text/markdown")

# ---------------------------------------------------------------- Ask NIST tab
with ask_tab:
    st.write(
        "Ask about the NIST AI Risk Management Framework (AI 100-1) or the Generative AI "
        "Profile (AI 600-1). Answers come only from retrieved passages and cite their pages."
    )
    question = st.text_input(
        "Your question",
        placeholder="What does NIST recommend for measuring bias across demographic groups?",
    )
    if st.button("Ask") and question.strip():
        with st.spinner("Searching NIST documents..."):
            try:
                st.session_state.qa = answer_policy_question(question)
            except Exception as e:
                st.error(f"Answer failed: {e}")

    qa = st.session_state.get("qa")
    if qa:
        citation_badge(qa["citation_check"])
        st.markdown(qa["answer"])
        with st.expander("Retrieved NIST passages"):
            for p in qa["passages"]:
                st.markdown(f"**{p['source']} p.{p['page']}**")
                st.caption(p["text"][:600])
