"""Thin async wrapper around the ADK Runner, returning answer + tool trace (used by CLI and eval)."""
import asyncio
import re
import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

import tools

APP = "iitj_helpdesk"
REFUSED = re.compile(r"i don['’]?t know", re.I)


def ensure_logged(question: str, answer: str, calls: list[dict]) -> bool:
    """8B models sometimes say "I don't know ... forwarded to a human" without calling
    log_unanswered_question; log it for them so the human queue is complete. Returns True if it did."""
    if not REFUSED.search(answer) or any(c["tool"] == "log_unanswered_question" for c in calls):
        return False
    tools.log_unanswered_question(question, "auto-logged: agent replied \"I don't know\" without logging")
    return True


class Helpdesk:
    def __init__(self, agent):
        self.agent = agent
        self.sessions = InMemorySessionService()
        self.runner = Runner(agent=agent, app_name=APP, session_service=self.sessions)

    async def ask(self, question: str, session_id: str | None = None) -> dict:
        sid = session_id or uuid.uuid4().hex
        user = "student"
        if await self.sessions.get_session(app_name=APP, user_id=user, session_id=sid) is None:
            await self.sessions.create_session(app_name=APP, user_id=user, session_id=sid)
        msg = types.Content(role="user", parts=[types.Part(text=question)])
        answer, calls, results, agents = "", [], [], []
        async for ev in self.runner.run_async(user_id=user, session_id=sid, new_message=msg):
            if ev.author and ev.author not in agents and ev.author != "user":
                agents.append(ev.author)
            for fc in ev.get_function_calls() or []:
                calls.append({"agent": ev.author, "tool": fc.name, "args": dict(fc.args or {})})
            for fr in ev.get_function_responses() or []:
                results.append({"tool": fr.name, "response": fr.response})
            if ev.is_final_response() and ev.content and ev.content.parts:
                answer = "".join(p.text or "" for p in ev.content.parts if not p.thought)
        answer = answer.strip()
        auto = ensure_logged(question, answer, calls)  # not added to calls: the eval reports the model's own logging
        return {"answer": answer, "tool_calls": calls, "tool_results": results, "agents": agents, "session": sid,
                "auto_logged": auto}

    def ask_sync(self, question: str, session_id: str | None = None) -> dict:
        return asyncio.run(self.ask(question, session_id))
