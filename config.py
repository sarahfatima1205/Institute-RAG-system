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
# Context window sent with every chat request (Ollama's default is too small for RAG + tools).
# Passed per request, so it works without setting OLLAMA_CONTEXT_LENGTH on the server (e.g. snap installs).
NUM_CTX = int(os.getenv("NUM_CTX", "8192"))

# "ollama" for real use, "hash" = tiny offline embedder used only for unit tests
EMBED_BACKEND = os.getenv("EMBED_BACKEND", "ollama")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

# --- RAG --------------------------------------------------------------------
TOP_K = int(os.getenv("TOP_K", "4"))
# Cosine similarity below this => "no relevant document" => agent must refuse.
# Tune this with eval/evaluate.py (it is the main out-of-scope guard).
# nomic-embed-text on this corpus: in-scope ~0.74-0.84, off-topic ~0.51-0.69 (0.45 let everything through).
MIN_SIM = float(os.getenv("MIN_SIM", "0.60" if EMBED_BACKEND == "ollama" else "0.12"))
# Re-ranking: candidates fetched before keeping TOP_K, and the weight of keyword overlap added to the
# cosine similarity (0 = pure embedding search). MIN_SIM is still applied to the raw cosine similarity.
CANDIDATES = int(os.getenv("CANDIDATES", "40"))
# 0.25 chosen by a sweep over 16 policy questions: correct passage in the top 4 for 10/16 at 0, 12/16 at 0.25.
LEX_WEIGHT = float(os.getenv("LEX_WEIGHT", "0.25"))
CHUNK_CHARS = int(os.getenv("CHUNK_CHARS", "900"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))
COLLECTION = "iitj_docs"
