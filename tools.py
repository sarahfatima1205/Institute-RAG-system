"""Tools exposed to the ADK agents. Plain Python functions: ADK builds the tool
schema from the type hints + docstring, so keep both accurate."""
import csv
import difflib
import re
from datetime import datetime

import config
import rag

DEPT_CODES = {
    "ME": "Mechanical Engineering", "CS": "Computer Science and Engineering",
    "EE": "Electrical Engineering", "CI": "Civil and Infrastructure Engineering",
    "CH": "Chemical Engineering", "BB": "Bioscience and Bioengineering",
    "MT": "Metallurgical and Materials Engineering", "CY": "Chemistry",
    "MA": "Mathematics", "PH": "Physics", "HS": "Humanities and Social Science",
    "DH": "Digital Humanities", "SS": "Space Science and Technology",
    "IO": "Internet of Things and Applications", "AV": "Autonomous Unmanned Vehicles",
    "QC": "Quantum Information and Computation", "CG": "Cognitive Science",
    "SH": "Smart Healthcare", "OA": "Office of Academics", "OS": "Office of Students",
}


def _courses() -> list[dict]:
    path = config.CSV_DIR / "courses.csv"
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _dept_code(text: str) -> str:
    t = text.strip().lower()
    if not t:
        return ""
    for code, name in DEPT_CODES.items():
        if t == code.lower() or t in name.lower() or name.lower() in t:
            return code
    if t.startswith("humanit"):
        return "HS"
    return t.upper()


# ------------------------------------------------------------------ RAG tool
def search_policy_documents(query: str) -> dict:
    """Search the IIT Jodhpur rules/regulations/curriculum/office-order documents.

    Use for questions about attendance, exams, grading, credits, leave, make-up
    exams, registration, degree requirements, programmes, academic calendar.

    Args:
        query: a self-contained search query, e.g. "attendance requirement major exam".

    Returns:
        dict with status 'ok' and a list of passages (each with a ready-to-copy citation),
        or status 'no_relevant_documents' if nothing relevant exists.
    """
    hits = rag.search(query)
    if not hits:
        return {
            "status": "no_relevant_documents",
            "message": "No relevant passage found. Do not guess; say you don't know and log the question.",
        }
    return {
        "status": "ok",
        "results": [
            {
                "citation": f"(Source: {h['doc']}, {h['section']})",
                "effective_date": h["effective_date"],
                "source_url": h["source_url"],
                "text": h["text"],
                **(
                    {"note": f"CURRENT RULE: this amendment replaces the older rule in {', '.join(h['replaces'])} "
                             "(those passages were withheld). Answer from this passage."}
                    if h.get("replaces") else {}
                ),
            }
            for h in hits
        ],
    }


# ----------------------------------------------------------- timetable tools
def find_course(query: str) -> dict:
    """Look up a course by code (e.g. 'CSL7570') or by name (e.g. 'Autonomous Systems').

    Returns slot, venue, credits, L-T-P, level, type, department, instructor and
    semester from the timetable CSV (source: courses.csv).
    """
    rows = _courses()
    q = query.strip().lower()
    exact = [r for r in rows if r["course_code"].lower() == q]
    if exact:
        return {"status": "ok", "source": "courses.csv", "courses": exact}
    contains = [r for r in rows if q in r["course_name"].lower() or r["course_name"].lower() in q]
    if contains:
        return {"status": "ok", "source": "courses.csv", "courses": contains}
    names = {r["course_name"].lower(): r for r in rows}
    close = difflib.get_close_matches(q, list(names), n=3, cutoff=0.6)
    if close:
        return {"status": "ok", "source": "courses.csv", "courses": [names[c] for c in close]}
    return {"status": "not_found", "message": f"No course matching '{query}' in the timetable."}


def list_courses(department: str = "", level: str = "", course_type: str = "", slot: str = "") -> dict:
    """List/count courses floated this semester, with optional filters.

    Args:
        department: name or code, e.g. 'Humanities' or 'HS'. Empty = all.
        level: course level such as '400'. Empty = all.
        course_type: 'core', 'elective' or 'open'. Empty = all.
        slot: timetable slot letter such as 'D'. Empty = all.

    Returns:
        dict with 'count' and the matching 'courses' (source: courses.csv).
    """
    rows = _courses()
    dc = _dept_code(department)
    if dc:
        rows = [r for r in rows if r["department"].upper() == dc]
    if level:
        lv = re.sub(r"\D", "", level)[:3]
        rows = [r for r in rows if r["level"].startswith(lv[:1]) and r["level"] == lv]
    if course_type:
        rows = [r for r in rows if r["course_type"].lower() == course_type.lower()]
    if slot:
        rows = [r for r in rows if r["slot"].upper() == slot.upper()]
    return {
        "status": "ok",
        "source": "courses.csv",
        "count": len(rows),
        "courses": [
            {k: r[k] for k in ("course_code", "course_name", "department", "level", "course_type", "slot", "credits")}
            for r in rows
        ],
    }


# -------------------------------------------------------------- e-mail tools
def get_instructor_email(course_code: str) -> dict:
    """Return the instructor name and e-mail address for a course code (source: courses.csv)."""
    for r in _courses():
        if r["course_code"].lower() == course_code.strip().lower():
            return {
                "status": "ok",
                "source": "courses.csv",
                "course_code": r["course_code"],
                "course_name": r["course_name"],
                "instructor": r["instructor"],
                "instructor_email": r["instructor_email"],
            }
    return {"status": "not_found", "message": f"Course code '{course_code}' not found."}


_TEMPLATES = {
    "sick_leave": (
        "Request for sick leave – {code}",
        "I am writing to inform you that I have been unwell and will be unable to attend "
        "{code} ({cname}) for {days}{when}. {reason}\n\n"
        "I will submit the medical certificate as required and will catch up on the missed "
        "lectures/assignments. Please let me know if any evaluation component falls in this period.",
    ),
    "leave": (
        "Request for leave of absence – {code}",
        "I would like to request leave from {code} ({cname}) for {days}{when}. {reason}\n\n"
        "I will catch up on the missed material and will inform you of any clash with evaluation components.",
    ),
    "makeup_exam": (
        "Request for permission to take a make-up examination – {code}",
        "I missed the {exam} of {code} ({cname}) due to genuine reasons. {reason}\n\n"
        "As per the Academic Regulations (Make-up Examinations), I request you to forward my application "
        "to the Dean (Academics) so that I may be permitted to write a make-up examination. "
        "I am attaching the supporting medical/other documents.",
    ),
}

_POLICY_NOTES = {
    "sick_leave": "Medical leave: up to 10 days per semester; apply to Convener DUGC with a medical certificate (Source: ug_regulations_2019.md, 15.2 Short Leave).",
    "leave": "Non-medical leave: up to 5 days per semester with prior approval (Source: ug_regulations_2019.md, 15.2 Short Leave).",
    "makeup_exam": "Apply to Dean (Academics) through the instructor within ten days of the missed exam, with documents (Source: ug_regulations_2019.md, 8 Make-up Examinations).",
}


def draft_email(
    course_code: str,
    request_type: str,
    student_name: str = "",
    roll_number: str = "",
    days: str = "",
    start_date: str = "",
    exam_name: str = "",
    reason: str = "",
) -> dict:
    """Create an e-mail DRAFT (never sent) from the student to a course instructor.

    Args:
        course_code: e.g. 'CSL7570'.
        request_type: one of 'sick_leave', 'leave', 'makeup_exam'.
        student_name: student's name (leave empty if unknown -> placeholder).
        roll_number: student's roll number (leave empty if unknown).
        days: number of days of leave, e.g. '2'.
        start_date: first day of leave, e.g. '28 Oct 2026' (optional).
        exam_name: for make-up requests, e.g. 'Minor 1', 'Major'.
        reason: short reason in the student's own words (optional).

    Returns:
        dict with to, subject, body and policy_notes. Student must review before sending.
    """
    info = get_instructor_email(course_code)
    if info["status"] != "ok":
        return {"status": "not_found", "message": info["message"]}
    rt = request_type if request_type in _TEMPLATES else "leave"
    subj, body = _TEMPLATES[rt]
    nd = days.strip()
    days_txt = f"{nd} day{'s' if nd not in ('', '1') else ''}" if nd else "a few days"
    when = f" starting {start_date}" if start_date else ""
    fields = dict(
        code=info["course_code"], cname=info["course_name"], days=days_txt, when=when,
        exam=exam_name or "examination", reason=(reason.strip() + " ") if reason else "",
    )
    name = student_name or "[Your Name]"
    roll = roll_number or "[Roll Number]"
    text = (
        f"Dear {info['instructor']},\n\n{body.format(**fields)}\n\n"
        f"Thank you for your understanding.\n\nRegards,\n{name}\n{roll}"
    )
    return {
        "status": "ok",
        "sent": False,
        "to": info["instructor_email"],
        "subject": subj.format(**fields),
        "body": text,
        "policy_notes": _POLICY_NOTES[rt],
        "source": "courses.csv",
        "note": "DRAFT ONLY - not sent. Student must review and edit.",
    }


# ------------------------------------------------------------- unanswered log
def log_unanswered_question(question: str, reason: str = "out of scope / no source found") -> dict:
    """Record a question the helpdesk cannot answer so a human can follow up.

    Call this whenever you answer "I don't know".
    """
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    new = not config.UNANSWERED_LOG.exists()
    with open(config.UNANSWERED_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "question", "reason"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), question, reason])
    return {"status": "logged"}
