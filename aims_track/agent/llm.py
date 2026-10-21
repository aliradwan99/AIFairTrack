"""Single place to configure the LLM. Switching providers is a one-line .env change."""
import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()

# Pinned on purpose: a fixed model version keeps audit results comparable run to run
DEFAULT_MODEL = "google_genai:gemini-3.6-flash"


def get_llm(temperature: float = 0):
    # temperature=0 keeps audit reports consistent run to run
    return init_chat_model(os.getenv("LLM_MODEL", DEFAULT_MODEL), temperature=temperature)


if __name__ == "__main__":
    print(get_llm().invoke("Reply with exactly: connection OK").content)
