"""Offline tests for document loading and amendment handling:  EMBED_BACKEND=hash python -m pytest tests -q"""
import os
os.environ["EMBED_BACKEND"] = "hash"
import sys, pathlib, re, shutil, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "code"))
import config, rag, tools


def setup_module(_):
    # old regulation + the 2024 amendment that replaces its attendance rule
    tmp = pathlib.Path(tempfile.mkdtemp())
    config.CHROMA_DIR = tmp / "chroma_db"
    (tmp / "docs").mkdir()
    for name in ("ug_regulations_2019.md", "attendance_amendment_2024_25.md", "examination_amendment_2024_25.md"):
        shutil.copy(config.DOCS_DIR / name, tmp / "docs")
    assert rag.ingest(tmp / "docs") > 20


def test_superseded_attendance_rule_is_withheld():
    r = tools.search_policy_documents("attendance falls below 75% allowed to appear for exams C grade")
    assert any("attendance_amendment_2024_25.md" in x["citation"] for x in r["results"])
    assert not any("Attendance Requirements" in x["citation"] for x in r["results"])  # old 4.1.9 withheld
    note = next(x["note"] for x in r["results"] if "note" in x)
    assert note.startswith("CURRENT RULE") and "ug_regulations_2019.md" in note


def test_superseded_evaluation_rule_is_withheld():
    r = tools.search_policy_documents("Minor 1 Minor 2 Major examination duration minutes")
    assert not any("4.2 Evaluation" in x["citation"] for x in r["results"])
    assert any("examination_amendment_2024_25.md" in x["citation"] for x in r["results"])


def test_unrelated_rules_not_superseded():
    r = tools.search_policy_documents("make-up exam how many days apply")
    assert "Make-up" in r["results"][0]["citation"]
    assert not any("note" in x for x in r["results"])


def test_supersede_patterns_only_hit_old_rules():
    """The amendment regexes must match the old rule text and nothing unrelated in the real corpus."""
    rules = {}
    for p in config.DOCS_DIR.glob("*.md"):
        meta = rag._parse_front_matter(p.read_text(encoding="utf-8"))[0]
        if meta.get("supersedes"):
            rules[p.name] = re.compile(meta["supersedes"], re.I)
    assert set(rules) == {"attendance_amendment_2024_25.md", "examination_amendment_2024_25.md"}
    for p in config.DOCS_DIR.glob("*"):
        for section, body, _ in rag.load_document(p):
            for name, rx in rules.items():
                if p.name != name and rx.search(body):
                    assert re.search(r"attendance|evaluation|p\.\d+", section, re.I), (p.name, section)


def test_html_split_into_sections():
    secs = [s for s, _, _ in rag.load_document(config.DOCS_DIR / "academic_regulations_page.html")]
    assert "4.1.9 Attendance Requirements" in secs and "8. Make-up Examinations" in secs
