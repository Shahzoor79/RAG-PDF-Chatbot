import io
import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pypdf.errors import PyPdfError
from starlette.concurrency import run_in_threadpool

import rag

MAX_BYTES = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024

app = FastAPI(title="PDF RAG chatbot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    k: int = Field(4, ge=1, le=20)


def gemini_error(e: Exception) -> HTTPException:
    # 502 = our server is fine, the upstream (Gemini) failed. Cut the message so it stays readable.
    return HTTPException(502, f"Gemini API error: {str(e)[:200]}")


@app.get("/health")
def health():
    return {"indexed": rag.load_store() is not None}


@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    chunk_size: int = Form(1000),
    chunk_overlap: int = Form(200),
):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Only .pdf files are supported.")
    if not 100 <= chunk_size <= 4000:
        raise HTTPException(422, "chunk_size must be between 100 and 4000.")
    if not 0 <= chunk_overlap < chunk_size:
        raise HTTPException(422, "chunk_overlap must be 0 or more and smaller than chunk_size.")

    data = await file.read(MAX_BYTES + 1)  # read one byte past the limit just to detect "too big"
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"File is larger than {MAX_BYTES // 1024 // 1024} MB.")

    try:
        # ingest blocks (PDF parsing + network), so keep it off the event loop
        return await run_in_threadpool(
            rag.ingest, io.BytesIO(data), file.filename, chunk_size, chunk_overlap
        )
    except ValueError as e:  # no extractable text
        raise HTTPException(422, str(e))
    except PyPdfError:
        raise HTTPException(400, "Could not read this PDF (corrupt or password-protected).")
    except RuntimeError as e:  # missing API key
        raise HTTPException(500, str(e))
    except Exception as e:
        raise gemini_error(e)


@app.post("/ask")
def ask(req: AskRequest):  # plain def: FastAPI runs it in a worker thread
    try:
        return rag.ask(req.question, req.k)
    except LookupError as e:
        raise HTTPException(409, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise gemini_error(e)
