"""Offline test: real PDF parsing, chunking, FAISS, persistence and API, with a fake embedder and fake LLM.

It proves the plumbing (pages, scores, persistence, errors). It says nothing about Gemini answer quality.
"""
import io
import re
import zlib
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

import main
import rag
from eval.run_eval import run_config

SAMPLE = Path(__file__).parent.parent / "eval" / "sample.pdf"


STOP = {"what", "does", "with", "that", "this", "from", "each", "have", "their", "during", "when", "many", "much"}


class BagOfWords(Embeddings):
    """Hash words into 512 buckets: similar words -> similar vectors, no network needed."""

    def _vec(self, text):
        v = np.zeros(512, dtype="float32")
        for w in re.findall(r"[a-z0-9]+", text.lower()):
            if len(w) > 3 and w not in STOP:  # crude stopword filter so questions match content words
                v[zlib.crc32(w.encode()) % 512] += 1
        return v.tolist()

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


@pytest.fixture(autouse=True)
def fakes(monkeypatch, tmp_path):
    monkeypatch.setattr(rag, "INDEX_DIR", tmp_path / "idx")
    monkeypatch.setattr(rag, "_store", None)
    monkeypatch.setattr(rag, "get_embeddings", lambda: BagOfWords())
    fake_llm = RunnableLambda(lambda pv: AIMessage(content="FAKE ANSWER from: " + pv.to_string()[:40]))
    monkeypatch.setattr(rag, "get_llm", lambda: fake_llm)


def test_upload_ask_and_persistence():
    c = TestClient(main.app)
    assert c.get("/health").json() == {"indexed": False}
    assert c.post("/ask", json={"question": "hi"}).status_code == 409  # nothing uploaded yet

    r = c.post("/upload", files={"file": ("s.pdf", SAMPLE.read_bytes(), "application/pdf")},
               data={"chunk_size": 400, "chunk_overlap": 50})
    assert r.status_code == 200 and r.json()["pages"] == 4 and r.json()["chunks"] > 4

    out = c.post("/ask", json={"question": "What is the daily meal allowance during travel?", "k": 3}).json()
    assert len(out["sources"]) == 3
    assert out["sources"][0]["page"] == 3 and "1,500" in out["sources"][0]["text"]
    scores = [h["score"] for h in out["sources"]]
    assert scores == sorted(scores, reverse=True) and all(0 <= s <= 1 for s in scores)
    same = c.post("/ask", json={"question": out["sources"][0]["text"], "k": 1}).json()["sources"][0]
    assert same["score"] > 0.99  # a chunk's own text is a perfect cosine match

    rag._store = None  # simulate a restart: the index must come back from disk
    assert c.get("/health").json() == {"indexed": True}
    assert c.post("/ask", json={"question": "notice period"}).status_code == 200


def test_upload_errors(monkeypatch):
    c = TestClient(main.app)
    pdf = ("x.pdf", SAMPLE.read_bytes(), "application/pdf")
    assert c.post("/upload", files={"file": ("a.txt", b"hi", "text/plain")}).status_code == 400
    assert c.post("/upload", files={"file": pdf}, data={"chunk_overlap": 5000}).status_code == 422
    assert c.post("/upload", files={"file": ("bad.pdf", b"not a pdf", "application/pdf")}).status_code == 400
    monkeypatch.setattr(main, "MAX_BYTES", 100)
    assert c.post("/upload", files={"file": pdf}).status_code == 413


def test_scanned_pdf_has_no_text():
    from pypdf import PdfWriter
    buf = io.BytesIO()
    w = PdfWriter()
    w.add_blank_page(300, 300)  # what a scanned page looks like to a text extractor: nothing
    w.write(buf)
    r = TestClient(main.app).post("/upload", files={"file": ("scan.pdf", buf.getvalue(), "application/pdf")})
    assert r.status_code == 422 and "scanned" in r.json()["detail"]


def test_eval_harness_runs():
    import json
    qs = json.loads((SAMPLE.parent / "questions.json").read_text())
    info, rows = run_config(SAMPLE, 400, 80, 4, qs, retrieval_only=True)
    assert len(rows) == 10 and info["chunks"] > 4
    # with fake LLM the answer scoring path must also execute
    _, rows = run_config(SAMPLE, 400, 80, 4, qs)
    assert all(r["answer_ok"] is not None for r in rows)
