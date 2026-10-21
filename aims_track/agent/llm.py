"""Single place to configure the LLM. Switching providers is a one-line .env change."""
import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()

# Pinned on purpose: a fixed model version keeps audit results comparable run to run
DEFAULT_MODEL = "google_genai:gemini-3.6-flash"
PRIMARY_MODEL = os.getenv("LLM_MODEL", DEFAULT_MODEL)
FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "google_genai:gemini-3.5-flash")


def get_llm(model: str | None = None, temperature: float | None = None):
    # Newer Gemini models ignore temperature, so only send it when explicitly requested
    kwargs = {} if temperature is None else {"temperature": temperature}
    return init_chat_model(model or PRIMARY_MODEL, **kwargs)


if __name__ == "__main__":
    print(get_llm().invoke("Reply with exactly: connection OK").text)
