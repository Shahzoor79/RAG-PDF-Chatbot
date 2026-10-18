import { useEffect, useRef, useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

// One fetch helper so every call turns backend errors into a readable message.
async function api(path, options) {
  const res = await fetch(API + path, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = body.detail;
    // FastAPI validation errors come back as a list of objects, our own errors as a string
    throw new Error(Array.isArray(d) ? d.map((e) => e.msg).join("; ") : d || res.statusText);
  }
  return body;
}

export default function App() {
  const [doc, setDoc] = useState(null); // { source, pages, chunks } or { source: "previous upload" }
  const [chunkSize, setChunkSize] = useState(1000);
  const [overlap, setOverlap] = useState(200);
  const [k, setK] = useState(4);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  // After a backend restart the index is still on disk, so ask the server whether one exists.
  useEffect(() => {
    api("/health")
      .then((h) => h.indexed && setDoc({ source: "your previously uploaded PDF" }))
      .catch(() => setError("Cannot reach the backend. Is it running on " + API + "?"));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, asking]);

  async function upload(file) {
    if (!file) return;
    setError("");
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    form.append("chunk_size", chunkSize);
    form.append("chunk_overlap", overlap);
    try {
      setDoc(await api("/upload", { method: "POST", body: form }));
      setMessages([]); // a new document means a fresh conversation
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  }

  async function send() {
    const question = input.trim();
    if (!question || asking || !doc) return;
    setInput("");
    setError("");
    setMessages((m) => [...m, { role: "user", text: question }]);
    setAsking(true);
    try {
      const res = await api("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, k }),
      });
      setMessages((m) => [...m, { role: "bot", text: res.answer, sources: res.sources }]);
    } catch (e) {
      setError(e.message);
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="app">
      <h1>Chat with your PDF</h1>

      <section
        className={"drop" + (dragging ? " dragging" : "")}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          upload(e.dataTransfer.files[0]);
        }}
      >
        {uploading ? (
          <p>Reading, chunking and embedding your PDF. This can take a few seconds...</p>
        ) : (
          <>
            <p>{doc ? <>Ready: <b>{doc.source}</b>{doc.pages && ` (${doc.pages} pages, ${doc.chunks} chunks)`}</> : "Drop a PDF here or"}</p>
            <input type="file" accept="application/pdf" onChange={(e) => upload(e.target.files[0])} />
          </>
        )}
        <div className="settings">
          <label>Chunk size <input type="number" value={chunkSize} min="100" max="4000" step="100" onChange={(e) => setChunkSize(+e.target.value)} /></label>
          <label>Overlap <input type="number" value={overlap} min="0" step="50" onChange={(e) => setOverlap(+e.target.value)} /></label>
          <label>Passages (k) <input type="number" value={k} min="1" max="20" onChange={(e) => setK(+e.target.value)} /></label>
        </div>
        <small>Chunk size and overlap apply to the next upload; k applies to the next question.</small>
      </section>

      <section className="chat">
        {messages.length === 0 && <p className="hint">Upload a PDF, then ask a question about it.</p>}
        {messages.map((m, i) => (
          <div key={i} className={"msg " + m.role}>
            <p>{m.text}</p>
            {m.sources && (
              <details>
                <summary>Sources used ({m.sources.length})</summary>
                {m.sources.map((s, j) => (
                  <blockquote key={j}>
                    <b>Page {s.page}</b> <span className="score">similarity {s.score.toFixed(2)}</span>
                    <br />
                    {s.text}
                  </blockquote>
                ))}
              </details>
            )}
          </div>
        ))}
        {asking && <div className="msg bot loading">Searching the document and thinking...</div>}
        <div ref={bottomRef} />
      </section>

      {error && <p className="error">{error}</p>}

      <div className="ask">
        <input
          value={input}
          placeholder={doc ? "Ask a question about the PDF" : "Upload a PDF first"}
          disabled={!doc || asking}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button onClick={send} disabled={!doc || asking || !input.trim()}>Send</button>
      </div>
    </div>
  );
}
