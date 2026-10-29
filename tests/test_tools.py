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


def test_email_days_wording():
    one = tools.draft_email("CSL7570", "leave", days="1")["body"]
    assert "for 1 day." in one and "1 days" not in one
    two = tools.draft_email("CSL7570", "leave", days="2 days")["body"]
    assert "for 2 days." in two and "days days" not in two
    assert "[number of days]" in tools.draft_email("CSL7570", "leave")["body"]


def test_email_request_types():
    assert tools.draft_email("CSL7570", "resignation")["status"] == "error"  # not silently a leave mail
    d = tools.draft_email("CSL3010", "Medical", days="3")  # alias -> sick_leave
    assert d["status"] == "ok" and d["subject"].startswith("Request for sick leave")
    assert tools.draft_email("CSL3010", "make-up exam", exam_name="Major")["subject"].endswith("CSL3010")


def test_email_policy_note_matches_programme():
    pg = tools.draft_email("CSL7570", "leave", days="2")["policy_notes"]  # level 700 = PG
    ug = tools.draft_email("CSL3010", "leave", days="2")["policy_notes"]  # level 300 = UG
    assert "pg_regulations_2019.md" in pg and "DRC" in pg and "ug_regulations" not in pg
    assert "ug_regulations_2019.md" in ug and "DUGC" not in pg
    assert "ten days" in tools.draft_email("CSL7570", "makeup_exam")["policy_notes"]


def test_keyword_overlap_rerank_helper():
    q = "How many Open Elective credits do I need for a B.Tech. degree?"
    assert rag.keyword_overlap(q, "Open Electives (OE) 10 credits for regular B.Tech.") > \
        rag.keyword_overlap(q, "Students may attend lectures in the library")
    assert rag.keyword_overlap("", "anything") == 0.0


def test_email():
    d = tools.draft_email("CSL7570", "leave", days="2")
    assert d["to"].startswith("instructor.beta@") and "2 days" in d["body"] and d["sent"] is False
    assert tools.draft_email("XYZ9999", "leave")["status"] == "not_found"


def test_log(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "UNANSWERED_LOG", tmp_path / "u.csv")
    tools.log_unanswered_question("dining?")
    assert "dining?" in (tmp_path / "u.csv").read_text()


def test_refusal_is_always_logged():
    import runtime
    config.UNANSWERED_LOG = pathlib.Path(tempfile.mkdtemp()) / "unanswered.csv"
    logged_by_agent = [{"tool": "log_unanswered_question"}]
    assert runtime.ensure_logged("Slot for Quantum Mechanics?", "I don't know. It will be forwarded.", []) is True
    assert runtime.ensure_logged("Weather?", "I don’t know.", logged_by_agent) is False  # agent already logged
    assert runtime.ensure_logged("Slot for CSL7570?", "Slot E (Source: courses.csv)", []) is False
    assert "Quantum Mechanics" in config.UNANSWERED_LOG.read_text() and "Weather" not in config.UNANSWERED_LOG.read_text()
