"""Rewrite everyday questions into NIST terminology before searching.
Targets vocabulary gaps such as R1 ("false content" vs NIST's "confabulation").

Uses a lightweight model by default: rewriting is a simple task that runs on every
search, so a Flash-Lite model is faster and has a separate, larger free-tier quota.
"""
import os

from aims_track.agent.llm import get_llm, call_with_fallback

REWRITE_MODEL = os.getenv("REWRITE_MODEL", "google_genai:gemini-3.5-flash-lite")

# The 12 generative AI risk categories as organized in NIST AI 600-1.
# Used only by the "taxonomy" mode, which lost to "plain" on held-out questions (Phase 6c).
NIST_GAI_RISKS = (
    "CBRN Information or Capabilities; Confabulation; Dangerous, Violent, or Hateful Content; "
    "Data Privacy; Environmental Impacts; Harmful Bias or Homogenization; Human-AI Configuration; "
    "Information Integrity; Information Security; Intellectual Property; "
    "Obscene, Degrading, and/or Abusive Content; Value Chain and Component Integration"
)

BASE_PROMPT = """Rewrite the question below as a short search query using the vocabulary of the
NIST AI Risk Management Framework (AI 100-1) and the NIST Generative AI Profile (AI 600-1).
Use NIST's technical terms where they differ from everyday words. Output only the query,
at most 25 words, with no explanation."""

TAXONOMY_ADDENDUM = """
For reference, NIST AI 600-1 organizes generative AI risks into these categories: {risks}."""


def _invoke(prompt: str) -> str:
    try:
        return get_llm(REWRITE_MODEL).invoke(prompt).text
    except Exception as e:
        print(f"[rewrite] {REWRITE_MODEL} failed, using main model chain: {str(e)[:100]}")
        text, _ = call_with_fallback(lambda m: get_llm(m).invoke(prompt).text)
        return text


def rewrite_query(question: str, mode: str = "plain") -> str:
    prompt = BASE_PROMPT
    if mode == "taxonomy":
        prompt += TAXONOMY_ADDENDUM.format(risks=NIST_GAI_RISKS)
    prompt += f"\n\nQuestion: {question}"
    return _invoke(prompt).strip().strip('"')


if __name__ == "__main__":
    q = "What risks does NIST identify for generative AI producing false or misleading content?"
    for mode in ("plain", "taxonomy"):
        print(f"{mode}: {rewrite_query(q, mode)}")
