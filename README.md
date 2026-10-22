# AIFairTrack

**Agentic AI fairness auditing, grounded in the NIST AI Risk Management Framework.**

**Version 1.1** (October 2026). The original starter-kit version is preserved at [v0.1.0](https://github.com/aliradwan99/AIFairTrack/tree/v0.1.0). See the [changelog](CHANGELOG.md) for what changed.

AIFairTrack audits AI model outputs for bias across demographic groups. Fairness metrics are computed deterministically in Python; an LLM agent then searches the NIST AI RMF and Generative AI Profile, writes a cited risk report, and every citation is automatically verified against the passages the agent actually retrieved.

![AI risk report with verified citations](docs/screenshots/report.png)

## What it does

- **Fairness metrics:** group positive rates, disparate impact (four-fifths rule), and max rate gap, computed in Python so numbers can't be hallucinated.
- **Agentic risk report:** a LangGraph agent with tool calling decides what NIST guidance to retrieve and writes a structured report (findings, risk level, guidance, actions, limitations).
- **Citation verification:** every `[NIST_AI_100-1 p.22]`-style citation is checked against the retrieved pages; invented citations are flagged.
- **Ask NIST:** retrieval-augmented Q&A over NIST AI 100-1 and AI 600-1, answering only from retrieved passages, with the same verification.

![Ask NIST answer with verified citations](docs/screenshots/ask_nist.png)

## Architecture

```mermaid
flowchart LR
    A[CSV upload] --> S["sanitize inputs<br/>(guardrails)"]
    S --> B["compute_metrics<br/>(Python, no LLM)"]
    B --> C["analyze<br/>(LLM agent)"]
    C <--> T["Tools: describe dataset, group rates,<br/>disparate impact, rate gap, NIST search"]
    T <--> Q["Query rewriting<br/>+ rank fusion"]
    Q <--> R[("Chroma index<br/>NIST AI 100-1, AI 600-1")]
    C --> D["check_citations<br/>(Python)"]
    D --> P["check_policy<br/>(guardrails)"]
    P --> E[Cited risk report]
```

**Key design decisions**

- **Deterministic where possible.** Metrics and citation checks are plain Python; the LLM only does what requires judgment: choosing what to retrieve and writing the report.
- **The LLM never touches raw data.** Tools take column names and values; Python does the math.
- **Reliability.** A configurable multi-model fallback chain handles outages and free-tier rate limits (429s) with a single wait-and-retry; the vector store is thread-safe for the agent's parallel tool calls.
- **Layered prompt-injection defenses.** Untrusted dataset labels are allowlisted and aliased before the agent sees them, the prompt treats all data as non-instructions, and a deterministic policy check removes non-NIST links and rejects a Low risk rating that contradicts the metrics.
- **Query rewriting with rank fusion.** User questions are rewritten into NIST terminology by a lightweight model; original and rewritten queries are both searched and merged with reciprocal rank fusion, so a bad rewrite can't fully derail retrieval.

## Evaluation

Every change was measured against a retrieval benchmark: 12 development questions plus a **held-out set of 7** written before any fix was designed, to avoid tuning the system to its own tests. Relevance is judged by evidence terms (e.g. a passage about false AI content must mention "confabulation"), and the benchmark verifies every label exists in the corpus.

| Configuration | Dev hit@4 | Dev MRR | Held-out hit@4 | Held-out MRR |
|---|---|---|---|---|
| MiniLM embeddings (baseline) | 0.750 | 0.607 | — | — |
| + boilerplate filtering | 0.750 | 0.607 | — | — |
| bge-base embeddings | 0.833 | 0.704 | 0.857 | 0.464 |
| **+ concise query rewriting (mean of 3 runs)** | **0.917** | 0.690 | **1.000** | **0.833** |

**Findings worth noting**

- A smaller "search-tuned" embedding model (bge-small) *regressed* every metric; bge-base won.
- An early single-run result (one rewriting strategy beating another) **failed to replicate**. Rewrites from the LLM vary run to run, so configurations are now compared on the mean and range of 3 runs.
- Query rewriting fixed two vocabulary-gap failures (e.g. "false content" vs NIST's "confabulation") and raised held-out MRR from 0.464 to 0.833, at a small cost in dev MRR. This trade-off and a deviation from a pre-registered criterion are documented openly.

Retrieval experiments ran while the system used Gemini models for query rewriting; the default model has since moved to Claude (see the changelog). All experiments, failures, and decisions are recorded in [`evals/failure_log.md`](evals/failure_log.md), with raw results in `evals/results/`.

### Prompt-injection red team

Attacks hide instructions in an uploaded CSV's group values and column names, which reach the agent through tool outputs: a direct override, a fake system notice, an authority claim from a "Chief Risk Officer," a link injection, a column-name injection, and an adaptive attack written specifically to pass the input filter. Every case uses the same clearly biased dataset (disparate impact 0.375), so an honest report must never rate risk Low. Success is scored by code, and scored successes were reviewed by hand.

| Condition | Attack success: model | Attack success: final report |
|---|---|---|
| No guardrails | 1/12 (8%) | 1/12 (8%) |
| Three-layer guardrails | 0/12 (0%) | 0/12 (0%) |

- Even undefended, Claude Sonnet 5.5 resisted every attempt to downgrade the risk rating. The one successful attack inserted an attacker's link into the report as if it were part of the audit.
- **Manual review caught a scorer false positive:** in one run the model had quoted the malicious payload while flagging it, and a naive string match counted that as compliance, doubling the reported baseline. The scorer was fixed and results rescored from saved reports.
- With guardrails on, the input allowlist neutralized 5 of 6 attack types before the model saw them. The adaptive attack, built to pass that filter, was resisted by the model under the hardened prompt. The output policy check never had to intervene in live runs, so it is verified separately with unit tests (`evals/test_guardrails.py`).
- With 12 attack runs per condition on one model, these results describe behavior on these attacks, not a guarantee of robustness.

![Guardrails flagging a prompt injection hidden in a group name](docs/screenshots/injection.png)

## Setup

Requires Python 3.12+ and an [Anthropic API key](https://platform.claude.com). The agent defaults to Claude Sonnet 5.5, with Claude Haiku 5.5 for query rewriting. Other LangChain-supported providers can be set in `.env` after installing their integration package (for example, `langchain-google-genai` for Gemini).

```bash
git clone https://github.com/aliradwan99/AIFairTrack.git
cd AIFairTrack
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "ANTHROPIC_API_KEY=your-key-here" > .env
python -m aims_track.rag.ingest           # build the NIST vector index (first run downloads the embedding model)
python -m streamlit run aims_track/app.py
```

Models are configurable in `.env` (`LLM_MODEL`, `LLM_FALLBACK_MODELS`, `REWRITE_MODEL`); retrieval via `EMBED_MODEL`, `FILTER_BOILERPLATE`, `QUERY_REWRITE`.

## Running the evaluations

```bash
python evals/retrieval_eval.py --label my_run                                     # dev set
python evals/retrieval_eval.py --cases retrieval_heldout.json --label my_run_ho   # held-out set
python evals/compare.py                                                           # all runs side by side
python evals/redteam.py --label my_attack_run --guardrails on                                     # prompt-injection red team
```

## Limitations and future work

- **Small evaluation sets** (12 dev, 7 held-out); one question moves hit@4 by 0.08 to 0.14.
- **Evidence-term relevance is a lenient proxy:** a passage mentioning a term in passing counts as relevant.
- **Citation verification checks that a cited page was retrieved, not that it supports the claim.** Planned: a quote-faithfulness check confirming quoted text appears in the cited passage.
- **Report-quality evals planned:** the agent sometimes lowers its risk rating because of small samples, conflating severity with confidence (see failure log, G1).
- **The red-team sample is small** (12 attack runs per condition, one model); results describe behavior on these attacks, not a robustness guarantee.
- **Page numbers are PDF page positions,** not the printed page numbers in the NIST documents.
- **Statistical disparity is not proof of discrimination;** reports are decision support, not legal advice.

## Project structure

```
aims_track/
  app.py               Streamlit UI (Fairness audit + Ask NIST tabs)
  agent/               LangGraph pipeline, tools, LLM config and fallback chain
  rag/                 PDF ingestion, retrieval, query rewriting, NIST Q&A
  modules/metrics.py   Fairness metric functions
  examples/            Sample datasets
data/policy_docs/      NIST AI 100-1 and AI 600-1
evals/                 Retrieval benchmark, red team, failure log, results
```

---

Built by [Ali Radwan](https://www.linkedin.com/in/aliradwan): AI red teaming and LLM evaluation.
