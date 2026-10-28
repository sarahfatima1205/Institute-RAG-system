"""Offline tests (no Ollama needed):  EMBED_BACKEND=hash python -m pytest tests -q"""
import os
os.environ["EMBED_BACKEND"] = "hash"
import sys, pathlib, shutil, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import config, rag, tools


def setup_module(_):
    # fixed 2-doc corpus in a temp Chroma dir: tests stay stable as data/docs grows
    # and never overwrite the real (Ollama-embedded) chroma_db/
    tmp = pathlib.Path(tempfile.mkdtemp())
    config.CHROMA_DIR = tmp / "chroma_db"
    (tmp / "docs").mkdir()
    for name in ("ug_regulations_2019.md", "pg_regulations_2019.md"):
        shutil.copy(config.DOCS_DIR / name, tmp / "docs")
    assert rag.ingest(tmp / "docs") > 20


def test_rag_attendance():
    hits = tools.search_policy_documents("attendance requirement major exam")
    assert hits["status"] == "ok"
    assert "Attendance" in hits["results"][0]["citation"]


def test_rag_make_up():
    r = tools.search_policy_documents("make-up exam how many days apply")
    assert "Make-up" in r["results"][0]["citation"]


def test_rag_refuses_irrelevant():
    assert tools.search_policy_documents("best biryani dining options hostel mess menu")["status"] == "no_relevant_documents"


def test_slot_lookup():
    assert tools.find_course("Autonomous Systems")["courses"][0]["slot"] == "D"
    assert tools.find_course("csl7570")["courses"][0]["venue"] == "LH-201"


def test_count_hs_400():
    assert tools.list_courses("Humanities", "400", "elective")["count"] == 3


def test_email():
    d = tools.draft_email("CSL7570", "leave", days="2")
    assert d["to"].startswith("instructor.beta@") and "2 days" in d["body"] and d["sent"] is False
    assert tools.draft_email("XYZ9999", "leave")["status"] == "not_found"


def test_log(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "UNANSWERED_LOG", tmp_path / "u.csv")
    tools.log_unanswered_question("dining?")
    assert "dining?" in (tmp_path / "u.csv").read_text()
