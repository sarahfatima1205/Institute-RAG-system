"""Central configuration. Everything can be overridden with environment variables."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS_DIR = ROOT / "data" / "docs"
CSV_DIR = ROOT / "data" / "csv"
CHROMA_DIR = ROOT / "chroma_db"
LOG_DIR = ROOT / "logs"
RESULTS_DIR = ROOT / "results"
UNANSWERED_LOG = LOG_DIR / "unanswered_questions.csv"

# --- Models (all local via Ollama, fits in 16 GB RAM) -----------------------
# NOTE: use the "ollama_chat/" prefix (not "ollama/") so LiteLLM uses the chat
# endpoint, which is what makes tool-calling work reliably.
CHAT_MODEL = os.getenv("CHAT_MODEL", "ollama_chat/qwen3:8b")
OLLAMA_HOST = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
os.environ.setdefault("OLLAMA_API_BASE", OLLAMA_HOST)

# "ollama" for real use, "hash" = tiny offline embedder used only for unit tests
EMBED_BACKEND = os.getenv("EMBED_BACKEND", "ollama")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

# --- RAG --------------------------------------------------------------------
TOP_K = int(os.getenv("TOP_K", "4"))
# Cosine similarity below this => "no relevant document" => agent must refuse.
# Tune this with eval/evaluate.py (it is the main out-of-scope guard).
MIN_SIM = float(os.getenv("MIN_SIM", "0.45" if EMBED_BACKEND == "ollama" else "0.12"))
CHUNK_CHARS = int(os.getenv("CHUNK_CHARS", "900"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))
COLLECTION = "iitj_docs"
