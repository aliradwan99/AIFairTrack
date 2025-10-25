import streamlit as st
import pandas as pd
from modules.metrics import group_rates, disparate_impact, max_rate_gap
from io import StringIO

st.set_page_config(page_title="AIFairTrack", page_icon="✅")

st.title("AIFairTrack — AI Fairness & Risk Monitoring Dashboard")
st.write("Upload a CSV (columns: `text`, `predicted_label`, `group`) or use a sample.")

sample_choice = st.selectbox("Load sample data?", ["None","NLP sample","AR/VR annotations sample"])

def load_sample(name):
    if name=="NLP sample":
        return pd.read_csv("aims_track/examples/example_nlp.csv")
    if name=="AR/VR annotations sample":
        return pd.read_csv("aims_track/examples/example_arvr.csv")
    return None

df = None
if sample_choice != "None":
    df = load_sample(sample_choice)

uploaded = st.file_uploader("Or upload CSV", type=["csv"])

if uploaded is not None:
    df = pd.read_csv(uploaded)

if df is not None:
    st.subheader("Preview")
    st.dataframe(df.head())

    group_col = st.selectbox("Protected group column", options=[c for c in df.columns if c!="text"])
    label_col = st.selectbox("Prediction/label column", options=[c for c in df.columns if c!=group_col])

    positive_label = st.number_input("Positive label value", value=1, step=1)
    privileged = st.text_input("Privileged group value (e.g., 'A')", value=str(df[group_col].unique()[0]))
    unprivileged = st.text_input("Unprivileged group value (e.g., 'B')", value=str(df[group_col].unique()[-1]))

    if st.button("Evaluate"):
        rates = group_rates(df, label_col, group_col, positive_label)
        st.subheader("Group Positive Rates")
        st.dataframe(rates)

        di = disparate_impact(df, label_col, group_col, privileged, unprivileged, positive_label)
        gap = max_rate_gap(df, label_col, group_col, positive_label)
        st.markdown(f"**Disparate Impact (unprivileged/privileged):** `{di if di is not None else 'N/A'}`")
        st.markdown(f"**Max Positive Rate Gap:** `{gap:.3f}`")

        # Simple composite fairness score (for demo only)
        score = 100 - (gap * 100)
        score = max(0, min(100, score))
        st.metric("Composite Fairness Score (demo)", f"{score:.1f}/100")

        # Recommendations (basic demo rules)
        recs = []
        if di is not None and (di < 0.8 or di > 1.25):
            recs.append("Consider rebalancing dataset (oversample underrepresented groups).")
        if gap > 0.2:
            recs.append("Investigate feature leakage and labeling guidelines; add fairness regularization.")
        if not recs:
            recs.append("No major issues detected in this quick check; consider deeper metrics for production.")

        st.subheader("Recommendations")
        for r in recs:
            st.write("- ", r)

        # Export
        if st.button("Export CSV Report"):
            out = rates.copy()
            out["disparate_impact"] = di
            out["max_rate_gap"] = gap
            out.to_csv("benchmarks/results_sample.csv", index=False)
            st.success("Saved to benchmarks/results_sample.csv")

else:
    st.info("Choose a sample or upload a CSV to begin.")
