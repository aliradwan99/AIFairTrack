"""Load NIST policy PDFs, chunk them, and store embeddings in a local Chroma DB.

Configured through environment variables so retrieval experiments are reproducible:
  EMBED_MODEL          embedding model (default: BAAI/bge-base-en-v1.5, chosen by retrieval benchmark)
  FILTER_BOILERPLATE   "1" strips publication boilerplate and drops near-empty pages (default: "1")
Each configuration gets its own database folder, so experiments never overwrite each other.
"""
import os
import re
import shutil
from pathlib import Path

from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "data" / "policy_docs"
COLLECTION = "nist_policy"

EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-base-en-v1.5")
FILTER_BOILERPLATE = os.getenv("FILTER_BOILERPLATE", "1") == "1"

_slug = re.sub(r"[^a-z0-9]+", "_", EMBED_MODEL.split("/")[-1].lower()).strip("_")
DB_DIR = ROOT / "chroma_db" / f"{_slug}{'_filtered' if FILTER_BOILERPLATE else ''}"

BOILERPLATE_MARKERS = ("available free of charge", "doi.org/10.6028")
MIN_PAGE_CHARS = 200
# BGE models retrieve better when queries (not documents) carry this instruction
BGE_QUERY_PROMPT = "Represent this sentence for searching relevant passages: "


def get_embeddings():
    if "bge" in EMBED_MODEL.lower():
        return HuggingFaceEmbeddings(
            model_name=EMBED_MODEL,
            encode_kwargs={"normalize_embeddings": True},
            query_encode_kwargs={"normalize_embeddings": True, "prompt": BGE_QUERY_PROMPT},
        )
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


def clean_page(text: str) -> str:
    lines = [ln for ln in text.splitlines() if not any(m in ln.lower() for m in BOILERPLATE_MARKERS)]
    return "\n".join(lines).strip()


def load_pdf(pdf: Path) -> tuple[list[Document], int]:
    docs, dropped = [], 0
    for i, page in enumerate(PdfReader(str(pdf)).pages):
        text = page.extract_text() or ""
        if FILTER_BOILERPLATE:
            text = clean_page(text)
            if len(text) < MIN_PAGE_CHARS:
                dropped += 1
                continue
        docs.append(Document(page_content=text, metadata={"source_doc": pdf.stem, "page_number": i + 1}))
    return docs, dropped


def build_index():
    print(f"Embedding model: {EMBED_MODEL} | filter boilerplate: {FILTER_BOILERPLATE}")
    docs = []
    for pdf in sorted(DOCS_DIR.glob("*.pdf")):
        pages, dropped = load_pdf(pdf)
        docs.extend(pages)
        print(f"Loaded {pdf.name}: {len(pages)} pages kept, {dropped} dropped")

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_documents(docs)

    # Rebuild this configuration from scratch so re-running never creates duplicates
    if DB_DIR.exists():
        shutil.rmtree(DB_DIR)

    Chroma.from_documents(chunks, get_embeddings(), persist_directory=str(DB_DIR), collection_name=COLLECTION)
    print(f"Indexed {len(chunks)} chunks into {DB_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    build_index()
