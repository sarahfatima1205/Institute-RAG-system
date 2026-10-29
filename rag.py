"""RAG pipeline: load docs -> chunk (section aware) -> embed (Ollama) -> ChromaDB."""
import csv
import hashlib
import math
import re
from html.parser import HTMLParser
from pathlib import Path

import config


# ----------------------------------------------------------------- embeddings
def _hash_embed(text: str, dim: int = 512) -> list[float]:
    """Deterministic bag-of-words embedder. ONLY for offline unit tests."""
    v = [0.0] * dim
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        v[h % dim] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def embed(texts: list[str], is_query: bool = False) -> list[list[float]]:
    if config.EMBED_BACKEND == "hash":
        return [_hash_embed(t) for t in texts]
    import ollama

    client = ollama.Client(host=config.OLLAMA_HOST)
    prefix = ""
    if "nomic" in config.EMBED_MODEL:  # nomic expects task prefixes
        prefix = "search_query: " if is_query else "search_document: "
    out: list[list[float]] = []
    for i in range(0, len(texts), 16):
        batch = [prefix + t for t in texts[i : i + 16]]
        out.extend(client.embed(model=config.EMBED_MODEL, input=batch)["embeddings"])
    return out


# ------------------------------------------------------------------- loading
def _parse_front_matter(text: str) -> tuple[dict, str]:
    meta: dict = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            for line in text[3:end].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            text = text[end + 4 :]
    return meta, text


class _Strip(HTMLParser):
    """HTML -> markdown-ish text: <h1>-<h6> become '# ' lines so the page splits into sections."""

    HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0  # inside <script>/<style>
        self.heading: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in self.HEADINGS:
            self.heading = []

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        elif tag in self.HEADINGS and self.heading is not None:
            title = " ".join("".join(self.heading).split())
            if title:  # the page has many empty <h4>/<h5> spacers
                self.parts.append(f"\n# {title}\n")
            self.heading = None

    def handle_data(self, d):
        if self.skip:
            return
        if self.heading is not None:
            self.heading.append(d)
        else:
            self.parts.append(d)


def _sections_from_text(text: str) -> list[tuple[str, str]]:
    """Split markdown-ish text on headings; returns [(section_title, body)]."""
    sections, title, buf = [], "intro", []
    for line in text.splitlines():
        if re.match(r"^#{1,6}\s+", line):
            if "".join(buf).strip():
                sections.append((title, "\n".join(buf).strip()))
            title, buf = re.sub(r"^#{1,6}\s+", "", line).strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip():
        sections.append((title, "\n".join(buf).strip()))
    return sections


def _manifest_row(name: str) -> dict:
    """source_url / effective_date for files without front matter (PDF, HTML), from data/docs_manifest.csv."""
    path = config.DOCS_DIR.parent / "docs_manifest.csv"
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["file"] == name:
                return {k: row[k] for k in ("source_url", "effective_date") if row.get(k)}
    return {}


def load_document(path: Path) -> list[tuple[str, str, dict]]:
    """Return [(section_label, text, doc_meta)] for one file."""
    suf = path.suffix.lower()
    meta = {"title": path.stem.replace("_", " "), "source_url": "", "effective_date": ""}
    meta.update(_manifest_row(path.name))
    if suf in (".md", ".txt"):
        fm, body = _parse_front_matter(path.read_text(encoding="utf-8", errors="ignore"))
        meta.update(fm)
        return [(s, t, meta) for s, t in _sections_from_text(body)]
    if suf in (".html", ".htm"):
        p = _Strip()
        p.feed(path.read_text(encoding="utf-8", errors="ignore"))
        return [(s, t, meta) for s, t in _sections_from_text("".join(p.parts))]
    if suf == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return [
            (f"p.{i}", (pg.extract_text() or ""), meta)
            for i, pg in enumerate(reader.pages, 1)
            if (pg.extract_text() or "").strip()
        ]
    return []


def chunk(text: str, size: int, overlap: int) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= size:
        return [text]
    out, i = [], 0
    while i < len(text):
        j = min(len(text), i + size)
        if j < len(text):  # try to end on a sentence boundary
            k = text.rfind(". ", i + size // 2, j)
            j = k + 1 if k != -1 else j
        out.append(text[i:j].strip())
        if j >= len(text):
            break
        i = max(j - overlap, i + 1)
    return out


# -------------------------------------------------------------------- store
def _collection():
    import chromadb

    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return client.get_or_create_collection(config.COLLECTION, metadata={"hnsw:space": "cosine"})


def ingest(docs_dir: Path = config.DOCS_DIR, reset: bool = True) -> int:
    import chromadb

    if reset:
        client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        try:
            client.delete_collection(config.COLLECTION)
        except Exception:
            pass
    col = _collection()
    loaded = [(path, load_document(path)) for path in sorted(docs_dir.glob("*"))]
    # Amendments declare "supersedes: <regex>" in their front matter. Any chunk of an OLDER document
    # matching that regex is marked superseded_by=<amendment> and is withheld at search time.
    rules = [
        (path.name, secs[0][2]["effective_date"], re.compile(secs[0][2]["supersedes"], re.I))
        for path, secs in loaded
        if secs and secs[0][2].get("supersedes")
    ]
    ids, texts, metas = [], [], []
    for path, secs in loaded:
        for si, (section, body, meta) in enumerate(secs):
            for n, piece in enumerate(chunk(body, config.CHUNK_CHARS, config.CHUNK_OVERLAP)):
                # section index keeps ids unique when a document repeats a heading
                ids.append(f"{path.name}:{si}:{section}:{n}")
                # prepend title+section so each chunk is self-describing for the embedder
                texts.append(f"{meta['title']} | {section}\n{piece}")
                date = meta.get("effective_date", "")
                metas.append(
                    {
                        "doc": path.name,
                        "title": meta["title"],
                        "section": section,
                        "source_url": meta.get("source_url", ""),
                        "effective_date": date,
                        "superseded_by": next(
                            (d for d, d_date, rx in rules if d != path.name and date < d_date and rx.search(piece)), ""
                        ),
                    }
                )
    if not ids:
        return 0
    for i in range(0, len(ids), 64):
        col.add(
            ids=ids[i : i + 64],
            documents=texts[i : i + 64],
            metadatas=metas[i : i + 64],
            embeddings=embed(texts[i : i + 64]),
        )
    return len(ids)


def search(query: str, k: int = config.TOP_K) -> list[dict]:
    col = _collection()
    if col.count() == 0:
        return []
    q = embed([query], is_query=True)
    # over-fetch so that dropping superseded chunks still leaves k results
    res = col.query(query_embeddings=q, n_results=min(col.count(), k * 3))
    hits, replaced = [], {}  # replaced: amendment doc -> older docs whose matching chunks were withheld
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        sim = 1.0 - dist
        if sim < config.MIN_SIM:
            continue
        if meta.get("superseded_by"):
            replaced.setdefault(meta["superseded_by"], set()).add(meta["doc"])
            continue
        hits.append({**meta, "score": round(sim, 3), "text": doc})
    hits = hits[:k]
    for newer, older in replaced.items():
        # the question hit an outdated rule: make sure the amendment that replaced it is in the results
        if not any(h["doc"] == newer for h in hits):
            r = col.query(query_embeddings=q, n_results=1, where={"doc": newer})
            if r["ids"][0]:
                hits.insert(0, {**r["metadatas"][0][0], "score": round(1.0 - r["distances"][0][0], 3),
                                "text": r["documents"][0][0]})
        first = next((h for h in hits if h["doc"] == newer), None)
        if first:
            first["replaces"] = sorted(older)
    return hits


if __name__ == "__main__":
    print(f"Indexed {ingest()} chunks from {config.DOCS_DIR}")
