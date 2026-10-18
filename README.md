# PDF RAG Chatbot

Ask questions about a PDF and get answers grounded in the document, with the page numbers and passages used as evidence.

**Stack:** Python, FastAPI, LangChain, FAISS, Google Gemini (generation and embeddings), React (Vite).

## How it works

```
 INGEST (once per PDF)
 PDF --> extract text per page --> chunk (size, overlap) --> embed with Gemini --> FAISS index --> saved to disk
         (pypdf)                   (RecursiveCharacter       (gemini-embedding-001)  (cosine)      (faiss_index/)
                                    TextSplitter)

 ASK (every question)
 question --> embed --> FAISS top-k search --> prompt: "answer ONLY from this context" --> Gemini --> answer
                        (chunk, page, score)                                                       + sources panel
```

## Setup

You need Python 3.10+, Node 18+ and a free Gemini API key from https://aistudio.google.com/apikey.

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # then paste your key into .env
uvicorn main:app --reload                              # http://localhost:8000/docs

# frontend (new terminal)
cd frontend
npm install
npm run dev                                            # http://localhost:5173
```

Run the offline tests (no API key needed): `cd backend && python -m pytest -q`

## Evaluation

```bash
cd backend
python -m eval.run_eval                                # baseline (1000/200/4) vs smaller chunks (400/80/4)
python -m eval.run_eval --config 600:120:6 --retrieval-only
```

10 questions over `eval/sample.pdf` (7 answerable, 3 unanswerable). Each failure is labelled:
retrieval miss (right page not in top-k), generation miss (right page retrieved, wrong answer)
or hallucination (answered an unanswerable question).

Results: _paste your before/after table here after you run it._

## Screenshots

_Add screenshots here: the empty state, an answer with the "Sources used" panel open, and an unanswerable question._

## Limitations

- One document at a time: uploading a new PDF replaces the index.
- Scanned PDFs are rejected (no OCR). Tables and multi-column layouts can extract in a scrambled order.
- No authentication, no rate limiting on our own API, and the index is global, not per user.
- No conversation memory: each question is answered on its own, so "what about the second one?" will not work.
- The retry logic retries every error, including bad API keys, so a wrong key is slow to fail.
- The saved index uses pickle for chunk metadata. Only load indexes this app wrote.

## Future improvements

- OCR fallback for scanned PDFs, multiple documents with per-document filters.
- Hybrid search (BM25 plus embeddings) and a reranker for better retrieval.
- A minimum-similarity cutoff to refuse before calling the LLM.
- Streaming answers, conversation memory with question rewriting, per-user indexes.
