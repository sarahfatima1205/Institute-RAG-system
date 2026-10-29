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
    return {
        "status": "not_found",
        "message": f"No course matching '{query}' in the timetable. Do not guess or cite anything. Call "
                   "log_unanswered_question with the student's question, then reply starting exactly with "
                   "\"I don't know\" and say it will be forwarded to a human.",
    }


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
                "level": r["level"],
                "instructor": r["instructor"],
                "instructor_email": r["instructor_email"],
            }
    return {
        "status": "not_found",
        "message": f"Course code '{course_code}' not found. Do not guess or cite anything. Call "
                   "log_unanswered_question with the student's question, then reply starting exactly with "
                   "\"I don't know\" and say it will be forwarded to a human.",
    }


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

_REQUEST_ALIASES = {
    "sick": "sick_leave", "sickleave": "sick_leave", "medical": "sick_leave", "medical_leave": "sick_leave",
    "leave_of_absence": "leave", "casual_leave": "leave",
    "makeup": "makeup_exam", "make_up": "makeup_exam", "make_up_exam": "makeup_exam",
    "makeup_examination": "makeup_exam", "make_up_examination": "makeup_exam",
}

# The note depends on the programme: courses of level 500+ are PG (M.Sc./M.Tech./Ph.D.), below that UG.
_PG_LEAVE = ("PG leave: at most 30 days per academic year including medical leave; M.Tech./M.Sc. not more than 10 days "
             "at a stretch, Ph.D. not more than 15; apply to the Convener DRC "
             "(Source: pg_regulations_2019.md, 23 Leave Rules (PG)).")
_POLICY_NOTES = {
    ("sick_leave", "ug"): "Medical leave: up to 10 days per semester; apply to Convener DUGC with a medical certificate (Source: ug_regulations_2019.md, 15.2 Short Leave).",
    ("leave", "ug"): "Non-medical leave: up to 5 days per semester with prior approval (Source: ug_regulations_2019.md, 15.2 Short Leave).",
    ("makeup_exam", "ug"): "Apply to Dean (Academics) through the instructor within ten days of the missed exam, with documents (Source: ug_regulations_2019.md, 8 Make-up Examinations).",
    ("sick_leave", "pg"): _PG_LEAVE,
    ("leave", "pg"): _PG_LEAVE,
    ("makeup_exam", "pg"): "The only make-up rule in the loaded documents is the UG one: apply to Dean (Academics) through the instructor within ten days of the missed exam, with documents (Source: ug_regulations_2019.md, 8 Make-up Examinations). PG students should confirm with the Convener DRC.",
}


def _days_text(days: str) -> str:
    """'2' / '2 days' -> '2 days', '1' -> '1 day', '' -> placeholder, free text ('a week') kept as is."""
    d = days.strip()
    if not d:
        return "[number of days]"
    m = re.fullmatch(r"(\d+)(?:\s*days?)?", d, re.I)
    if m:
        return f"{m.group(1)} day" + ("" if int(m.group(1)) == 1 else "s")
    return d


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
    key = re.sub(r"[\s\-]+", "_", request_type.strip().lower())
    rt = _REQUEST_ALIASES.get(key, key)
    if rt not in _TEMPLATES:  # never silently turn an unknown request into a leave e-mail
        return {"status": "error",
                "message": f"Unknown request_type '{request_type}'. Use one of: {', '.join(_TEMPLATES)}."}
    info = get_instructor_email(course_code)
    if info["status"] != "ok":
        return {"status": "not_found", "message": info["message"]}
    subj, body = _TEMPLATES[rt]
    when = f" starting {start_date.strip()}" if start_date.strip() else ""
    fields = dict(
        code=info["course_code"], cname=info["course_name"], days=_days_text(days), when=when,
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
        "policy_notes": _POLICY_NOTES[(rt, "pg" if int(info["level"] or 0) >= 500 else "ug")],
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
