"""Single-agent and multi-agent (orchestrator + 3 specialists) Academic Helpdesk using Google ADK."""
import litellm
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

import config
import tools

# LiteLLM's internal GPT-5 check prints a harmless "Provider List" banner for every ollama_chat call
litellm.suppress_debug_info = True

CITE_RULES = """
CITATION RULES (mandatory):
- Every factual sentence must end with a citation in the form (Source: <file name>, <section>),
  e.g. (Source: ug_regulations_2019.md, 8 Make-up Examinations) or (Source: courses.csv).
- Only cite documents/rows that your tools actually returned in THIS conversation.
- Never use outside knowledge about IIT Jodhpur. Use only tool output.
- If two documents disagree, prefer the one with the later effective_date and mention the other.
"""

REFUSAL_RULES = """
REFUSAL RULES (mandatory):
- If the tools return 'no_relevant_documents' / 'not_found', or the question is not about
  IIT Jodhpur academics (programmes, courses, rules, regulations, time table, instructor e-mails,
  leave/make-up e-mails), you MUST: (1) call log_unanswered_question with the user's question,
  (2) reply starting exactly with "I don't know" and say it will be forwarded to a human.
- Never guess. Never answer campus-life, transport, food, weather, placement or general-knowledge questions.
"""


def _model(name: str | None = None):
    name = name or config.CHAT_MODEL
    extra = {}
    if "qwen3" in name.lower():
        # newer Ollama ignores "/no_think" in the prompt; this sends think=false in the request instead
        extra["reasoning_effort"] = "none"
    return LiteLlm(model=name, num_ctx=config.NUM_CTX, **extra)


def _suffix(name: str | None) -> str:
    # Qwen3 has a 'thinking' mode that wastes tokens on 8B + tools; switch it off.
    return "\n/no_think" if "qwen3" in (name or config.CHAT_MODEL).lower() else ""


# ------------------------------------------------------------ single agent
def build_single_agent(model: str | None = None) -> Agent:
    return Agent(
        name="helpdesk_single",
        model=_model(model),
        description="IIT Jodhpur academic helpdesk (single agent).",
        instruction=(
            "You are the IIT Jodhpur Academic Helpdesk for students.\n"
            "Tools: search_policy_documents (rules, regulations, curriculum, credits, calendar), "
            "find_course / list_courses (slots, venues, credits, counts), get_instructor_email, "
            "draft_email (e-mail DRAFT for leave/sick leave/make-up exam; never sent), log_unanswered_question.\n"
            "Always call a tool before answering. For e-mail requests call draft_email, show the draft "
            "(To, Subject, Body) and remind the student to review it before sending.\n"
            + CITE_RULES + REFUSAL_RULES + _suffix(model)
        ),
        tools=[
            tools.search_policy_documents, tools.find_course, tools.list_courses,
            tools.get_instructor_email, tools.draft_email, tools.log_unanswered_question,
        ],
    )


# ------------------------------------------------------------- multi agent
def build_multi_agent(model: str | None = None) -> Agent:
    m = _model(model)
    sfx = _suffix(model)

    policy = Agent(
        name="policy_agent",
        model=m,
        description="Answers questions on academic rules and regulations, attendance, exams, grading, "
                    "credits/degree requirements, leave rules, programmes and curriculum, academic calendar.",
        instruction=(
            "You answer policy/curriculum questions for IIT Jodhpur students using ONLY the output of "
            "search_policy_documents. Search first (rephrase and search again if the first result is weak). "
            "Quote numbers exactly as in the passage." + CITE_RULES + REFUSAL_RULES + sfx
        ),
        tools=[tools.search_policy_documents, tools.log_unanswered_question],
    )

    schedule = Agent(
        name="schedule_agent",
        model=m,
        description="Answers questions on course slots, venues, credits, L-T-P, course codes, how many "
                    "courses a department floated, and which courses are in a slot (time table CSV).",
        instruction=(
            "You answer time-table questions using ONLY find_course and list_courses. For counts, report the "
            "'count' field and list the course codes. Cite (Source: courses.csv)." + CITE_RULES + REFUSAL_RULES + sfx
        ),
        tools=[tools.find_course, tools.list_courses, tools.log_unanswered_question],
    )

    email = Agent(
        name="email_agent",
        model=m,
        description="Finds a course instructor's e-mail and drafts an e-mail from the student for sick leave, "
                    "leave of absence or a make-up exam request.",
        instruction=(
            "You draft e-mails for students. Identify the course code (use find_course if only a name is given), "
            "the request type (sick_leave, leave, makeup_exam), number of days / exam name. Call draft_email. "
            "Show To, Subject and Body exactly as returned, then add the policy note with its citation and say "
            "this is a DRAFT that has NOT been sent and must be reviewed. If student name/roll number are unknown, "
            "leave the placeholders. If the course is not found, say so and log it." + CITE_RULES + REFUSAL_RULES + sfx
        ),
        tools=[tools.draft_email, tools.get_instructor_email, tools.find_course, tools.log_unanswered_question],
    )

    return Agent(
        name="helpdesk_orchestrator",
        model=m,
        description="Routes IIT Jodhpur academic helpdesk questions.",
        instruction=(
            "You are the router of the IIT Jodhpur Academic Helpdesk. Do not answer academic questions yourself; "
            "transfer to the right specialist:\n"
            "- policy_agent: rules, regulations, attendance, exams, grading, credits, leave rules, curriculum.\n"
            "- schedule_agent: slots, venues, course codes, credits of a course, counts of courses floated.\n"
            "- email_agent: writing an e-mail/draft to an instructor, instructor contact.\n"
            "If the question is none of these (campus facilities, food, transport, weather, general knowledge...), "
            "call log_unanswered_question and reply starting exactly with \"I don't know\"." + REFUSAL_RULES + sfx
        ),
        sub_agents=[policy, schedule, email],
        tools=[tools.log_unanswered_question],
    )
