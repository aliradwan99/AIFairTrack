"""Single-step RAG: retrieve NIST passages, answer only from them, verify citations."""
import re

from aims_track.agent.llm import get_llm, call_with_fallback
from aims_track.rag.retriever import search_policy

CITATION_RE = re.compile(r"\[(NIST_AI_\d{3}-1)\s+p\.\s*(\d+)\]")

PROMPT = """Answer the question using ONLY the NIST passages below.
Cite every claim in exactly this format: [NIST_AI_100-1 p.22].
If the passages do not contain the answer, say so plainly instead of guessing.

Question: {question}

Passages:
{passages}"""


def answer_policy_question(question: str, k: int = 5) -> dict:
    passages = search_policy(question, k=k)
    block = "\n\n".join(f"[{p['source']} p.{p['page']}]\n{p['text']}" for p in passages)
    prompt = PROMPT.format(question=question, passages=block)

    answer, model_name = call_with_fallback(lambda m: get_llm(m).invoke(prompt).text)

    allowed = {(p["source"], int(p["page"])) for p in passages}
    cited = [(s, int(n)) for s, n in CITATION_RE.findall(answer)]
    unverified = sorted({c for c in cited if c not in allowed})
    return {
        "answer": answer,
        "passages": passages,
        "model_used": model_name,
        "citation_check": {
            "citations_found": len(cited),
            "unverified": [f"{s} p.{n}" for s, n in unverified],
            "passed": len(cited) > 0 and not unverified,
        },
    }


if __name__ == "__main__":
    r = answer_policy_question("What does NIST recommend for measuring bias across demographic groups?")
    print(r["answer"])
    print("Citation check:", r["citation_check"])
