"""CLI chat.  python code/main.py [--mode single|multi] [--model ollama_chat/llama3.1:8b] [--ingest]"""
import argparse
import asyncio
import uuid

import agents
import config
import rag
from runtime import Helpdesk


async def chat(hd: Helpdesk):
    sid = uuid.uuid4().hex
    print("IIT Jodhpur Academic Helpdesk (type 'exit' to quit)\n")
    while True:
        q = input("You: ").strip()
        if q.lower() in ("exit", "quit", ""):
            break
        r = await hd.ask(q, sid)
        print(f"\n[{' -> '.join(r['agents'])}]\n{r['answer']}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["single", "multi"], default="multi")
    ap.add_argument("--model", default=config.CHAT_MODEL)
    ap.add_argument("--ingest", action="store_true", help="(re)build the vector store first")
    a = ap.parse_args()
    if a.ingest:
        print(f"Indexed {rag.ingest()} chunks")
    build = agents.build_multi_agent if a.mode == "multi" else agents.build_single_agent
    asyncio.run(chat(Helpdesk(build(a.model))))
