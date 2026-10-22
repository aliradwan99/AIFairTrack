# Changelog

## v1.0.0 (2026-10-21)

Agentic rebuild.

**Added**
- LangGraph audit agent: deterministic metric computation, LLM analysis with tool calling, and automated citation verification.
- Retrieval-augmented generation over NIST AI 100-1 and AI 600-1 (bge-base embeddings, boilerplate filtering, concise LLM query rewriting with reciprocal rank fusion).
- Ask NIST tab: question answering over the NIST documents with verified citations.
- Multi-model fallback chain with rate-limit handling; thread-safe vector store.
- Retrieval benchmark with a held-out set and repeated-run comparison; prompt-injection red-team harness; failure log documenting every experiment and decision.

**Fixed**
- Export button nested inside the Evaluate button never fired.
- Swapped default columns could make a misconfigured audit report a perfect 100/100 fairness score.
- Group values compared as text vs numbers silently returned no result.

**Removed**
- Hard-coded recommendation rules, replaced by the agent's cited risk report.

## v0.1.0 (2025-10-25)

Starter kit: Streamlit dashboard with disparate impact and max rate gap metrics, sample NLP and AR/VR datasets, whitepaper outline, and NIST policy mapping.
