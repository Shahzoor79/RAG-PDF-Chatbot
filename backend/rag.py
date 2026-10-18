"""The whole RAG pipeline in one file: extract -> chunk -> embed -> store -> retrieve -> generate."""
import os
import time
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

load_dotenv()

INDEX_DIR = Path(os.getenv("INDEX_DIR", "faiss_index"))
CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "models/gemini-embedding-001")
NOT_FOUND = "I couldn't find that in the document."

# normalize_L2 only takes effect with the default L2 index. On unit vectors, squared L2 distance
# d = 2 - 2*cosine, so retrieve() turns it back into a cosine score (1.0 = identical direction).
FAISS_KW = dict(normalize_L2=True)

PROMPT = ChatPromptTemplate.from_template(
    """You answer questions about a PDF using ONLY the context below.

Rules:
- Use only facts stated in the context. Never use outside knowledge.
- If the context does not contain the answer, reply with exactly: {not_found}
- Keep the answer short. Cite pages like (p. 3) for the passages you used.

Context:
{context}

Question: {question}"""
)

_store = None  # the in-memory FAISS index (one document at a time)


@lru_cache
def get_embeddings():
    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY is not set. Copy .env.example to .env and add your key.")
    return GoogleGenerativeAIEmbeddings(model=EMBED_MODEL, google_api_key=key)


@lru_cache
def get_llm():
    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY is not set. Copy .env.example to .env and add your key.")
    return ChatGoogleGenerativeAI(model=CHAT_MODEL, google_api_key=key, temperature=0)


def _retry(fn, tries=4):
    # shortcut: retries every error (even bad keys), fine for a demo; upgrade to retry only 429/5xx.
    for i in range(tries):
        try:
            return fn()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 ** (i + 1))  # 2s, 4s, 8s: gentle backoff for free-tier rate limits


# ---- 1. extract -------------------------------------------------------------
def extract_pages(file) -> list[Document]:
    """One Document per page so every chunk can say which page it came from."""
    reader = PdfReader(file)
    docs = [
        Document(page_content=(p.extract_text() or "").strip(), metadata={"page": i})
        for i, p in enumerate(reader.pages, start=1)
    ]
    return [d for d in docs if d.page_content]  # scanned pages come back empty


# ---- 2-4. chunk, embed, store ------------------------------------------------
def ingest(file, source: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> dict:
    global _store
    pages = extract_pages(file)
    if not pages:
        raise ValueError("No extractable text. This looks like a scanned PDF; it needs OCR first.")

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents(pages)  # metadata (page) is copied onto every chunk
    for c in chunks:
        c.metadata["source"] = source

    emb = get_embeddings()
    batches = [chunks[i : i + 50] for i in range(0, len(chunks), 50)]  # small batches = fewer 429s
    store = _retry(lambda: FAISS.from_documents(batches[0], emb, **FAISS_KW))
    for b in batches[1:]:
        _retry(lambda b=b: store.add_documents(b))

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    store.save_local(str(INDEX_DIR))
    _store = store
    return {"source": source, "pages": len(pages), "chunks": len(chunks)}


def load_store():
    """Return the index, loading it from disk after a restart."""
    global _store
    if _store is None and (INDEX_DIR / "index.faiss").exists():
        # allow_dangerous_deserialization: the docstore is a pickle. Safe here because we wrote it.
        _store = FAISS.load_local(
            str(INDEX_DIR), get_embeddings(), allow_dangerous_deserialization=True, **FAISS_KW
        )
    return _store


# ---- 5. retrieve -------------------------------------------------------------
def retrieve(question: str, k: int = 4) -> list[dict]:
    store = load_store()
    if store is None:
        raise LookupError("Upload a PDF first.")
    hits = _retry(lambda: store.similarity_search_with_score(question, k=k))
    return [
        {"text": d.page_content, "page": d.metadata["page"], "score": round(1 - float(dist) / 2, 4)}
        for d, dist in hits
    ]


# ---- 6. generate -------------------------------------------------------------
def generate(question: str, hits: list[dict]) -> str:
    context = "\n\n".join(f"[Page {h['page']}]\n{h['text']}" for h in hits)
    msg = (PROMPT | get_llm()).invoke(
        {"context": context, "question": question, "not_found": NOT_FOUND}
    )
    return msg.text.strip()


def ask(question: str, k: int = 4) -> dict:
    hits = retrieve(question, k)
    return {"answer": _retry(lambda: generate(question, hits)), "sources": hits}
