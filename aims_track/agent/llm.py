"""Single place to configure the LLM and its fallback chain. Switching providers is a .env change."""
import os
import time

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()

# Pinned on purpose: a fixed model version keeps audit results comparable run to run
DEFAULT_MODEL = "anthropic:claude-sonnet-5-5"
PRIMARY_MODEL = os.getenv("LLM_MODEL", DEFAULT_MODEL)

# Tried in order if the primary fails. On the free tier, each model usually has its own quota.
_fallbacks = os.getenv(
    "LLM_FALLBACK_MODELS",
    "anthropic:claude-haiku-5-5",
)
MODEL_CHAIN = [PRIMARY_MODEL] + [
    m.strip() for m in _fallbacks.split(",") if m.strip() and m.strip() != PRIMARY_MODEL
]
RATE_LIMIT_WAIT_SECONDS = 45


def get_llm(model: str | None = None, temperature: float | None = None):
    # Newer Gemini models ignore temperature, so only send it when explicitly requested
    kwargs = {} if temperature is None else {"temperature": temperature}
    if (model or PRIMARY_MODEL).startswith("anthropic:"):
        kwargs.setdefault("max_tokens", 4096)  # avoid truncated reports
    return init_chat_model(model or PRIMARY_MODEL, **kwargs)


def _is_rate_limit(e: Exception) -> bool:
    msg = str(e)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg


def call_with_fallback(fn):
    """Run fn(model_name) on each model in MODEL_CHAIN until one succeeds.
    If every model is rate-limited, wait once and retry the whole chain.
    Returns (result, model_name_used)."""
    last_err = None
    for attempt in range(2):
        all_rate_limited = True
        for model_name in MODEL_CHAIN:
            try:
                return fn(model_name), model_name
            except Exception as e:
                last_err = e
                print(f"[fallback] {model_name} failed: {str(e)[:120]}")
                if not _is_rate_limit(e):
                    all_rate_limited = False
        if attempt == 0 and all_rate_limited:
            print(f"[fallback] all models rate-limited; waiting {RATE_LIMIT_WAIT_SECONDS}s, then retrying once")
            time.sleep(RATE_LIMIT_WAIT_SECONDS)
        else:
            break

    if _is_rate_limit(last_err):
        raise RuntimeError(
            "All models hit the free-tier rate limit. Wait a few minutes and try again. "
            "If it keeps happening, the daily quota is used up and resets tomorrow."
        )
    raise RuntimeError(f"All models failed. Last error: {last_err}")


if __name__ == "__main__":
    text, used = call_with_fallback(lambda m: get_llm(m).invoke("Reply with exactly: connection OK").text)
    print(f"{text}  (model: {used})")
