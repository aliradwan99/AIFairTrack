"""Load NIST policy PDFs, chunk them, and store embeddings in a local Chroma DB."""
import shutil
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "data" / "policy_docs"
DB_DIR = ROOT / "chroma_db"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION = "nist_policy"


def get_embeddings():
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


def build_index():
    docs = []
    for pdf in sorted(DOCS_DIR.glob("*.pdf")):
        pages = PyPDFLoader(str(pdf)).load()
        for p in pages:
            p.metadata["source_doc"] = pdf.stem
            p.metadata["page_number"] = p.metadata.get("page", 0) + 1
        docs.extend(pages)
        print(f"Loaded {pdf.name}: {len(pages)} pages")

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_documents(docs)

    # Rebuild from scratch so re-running never creates duplicate chunks
    if DB_DIR.exists():
        shutil.rmtree(DB_DIR)

    Chroma.from_documents(
        chunks,
        get_embeddings(),
        persist_directory=str(DB_DIR),
        collection_name=COLLECTION,
    )
    print(f"Indexed {len(chunks)} chunks into {DB_DIR}")


if __name__ == "__main__":
    build_index()
