"""Run the 10 test questions under one or more chunking configs and compare.

    python -m eval.run_eval                                  # baseline vs smaller chunks
    python -m eval.run_eval --config 1000:200:4 --config 600:120:6
    python -m eval.run_eval --retrieval-only                 # embeddings only, no Gemini answers

A config is chunk_size:chunk_overlap:k. Free-tier Gemini is rate limited, so --delay sleeps between questions.
"""
import argparse
import json
import tempfile
import time
from pathlib import Path

import rag

HERE = Path(__file__).parent


def norm(s: str) -> str:
    return s.lower().replace("\u2019", "'")  # Gemini sometimes returns a curly apostrophe


def run_config(pdf: Path, size: int, overlap: int, k: int, questions: list, delay=0.0, retrieval_only=False):
    rag.INDEX_DIR = Path(tempfile.mkdtemp())  # never touch the index the app is using
    rag._store = None
    with open(pdf, "rb") as f:
        info = rag.ingest(f, pdf.name, size, overlap)

    rows = []
    for item in questions:
        if retrieval_only:
            hits, answer = rag.retrieve(item["q"], k), None
        else:
            out = rag.ask(item["q"], k)
            hits, answer = out["sources"], out["answer"]
            time.sleep(delay)

        pages = [h["page"] for h in hits]
        answerable = item["expect"] is not None
        retrieval_ok = (item["page"] in pages) if answerable else None
        if answer is None:
            answer_ok = None
        elif answerable:
            answer_ok = any(e.lower() in norm(answer) for e in item["expect"])
        else:
            answer_ok = norm(rag.NOT_FOUND) in norm(answer)

        failure = None
        if answerable and retrieval_ok is False:
            failure = "retrieval miss"
        elif answerable and answer_ok is False:
            failure = "generation miss"
        elif not answerable and answer_ok is False:
            failure = "hallucination"
        rows.append(dict(q=item["q"], answerable=answerable, retrieval_ok=retrieval_ok,
                         answer_ok=answer_ok, failure=failure, pages=pages, answer=answer))
    return info, rows


def summarize(rows):
    ans = [r for r in rows if r["answerable"]]
    un = [r for r in rows if not r["answerable"]]
    s = {"retrieval": f"{sum(r['retrieval_ok'] for r in ans)}/{len(ans)}"}
    if rows[0]["answer_ok"] is not None:
        s["answered correctly"] = f"{sum(r['answer_ok'] for r in ans)}/{len(ans)}"
        s["unanswerable refused"] = f"{sum(r['answer_ok'] for r in un)}/{len(un)}"
    return s


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=str(HERE / "sample.pdf"))
    ap.add_argument("--questions", default=str(HERE / "questions.json"))
    ap.add_argument("--config", action="append", help="size:overlap:k (repeatable)")
    ap.add_argument("--delay", type=float, default=7.0)
    ap.add_argument("--retrieval-only", action="store_true")
    a = ap.parse_args()

    questions = json.loads(Path(a.questions).read_text())
    for cfg in a.config or ["1000:200:4", "400:80:4"]:
        size, overlap, k = map(int, cfg.split(":"))
        info, rows = run_config(Path(a.pdf), size, overlap, k, questions, a.delay, a.retrieval_only)
        print(f"\n=== chunk_size={size} overlap={overlap} k={k}  ({info['chunks']} chunks) ===")
        print(summarize(rows))
        for r in rows:
            if r["failure"]:
                print(f"  FAIL [{r['failure']}] {r['q']}\n       pages={r['pages']} answer={r['answer']!r}")
