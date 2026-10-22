# Changelog

## v1.1.0 (2026-10-22)

**Added**
- Prompt-injection red team: 6 attack types hidden in dataset labels, including an adaptive attack built to pass the input filter; scored by code at model and final-report level, with hand review of scored successes.
- Three-layer guardrails: allowlist input sanitization with aliasing, a hardened prompt, and a deterministic output policy (non-NIST links removed, contradictory Low ratings rejected). Warnings are shown in the UI.
- Unit tests for guardrail layers 1 and 3.

**Changed**
- Default model switched from Gemini to Claude (Sonnet 5.5 for the agent, Haiku 5.5 for query rewriting).

**Fixed**
- Red-team scorer counted quoted mentions of a payload as successful attacks; results were rescored from saved reports.
- With an injection aliased away, reports could state that no suspicious text was found; the agent is now told which labels were aliased and notes it under Limitations.

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
