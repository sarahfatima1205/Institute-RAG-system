"""Serve the Academic Helpdesk chat page. Run with: python web.py"""
import asyncio
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = 8000

PAGE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Academic Helpdesk</title>
<style>
:root{color-scheme:dark;--bg:#212121;--panel:#171717;--line:#343434;--text:#ececec;--muted:#a0a0a0;--green:#b8f28b;--bubble:#303030}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;height:100dvh}
.app{height:100%;display:flex}.sidebar{width:258px;background:var(--panel);padding:18px 13px;display:flex;flex-direction:column;gap:22px}.brand{display:flex;gap:10px;align-items:center;font-weight:650;font-size:15px}.mark{width:29px;height:29px;border-radius:9px;background:var(--green);color:#172017;display:grid;place-items:center;font-weight:800}.new{border:1px solid #454545;color:#e8e8e8;background:transparent;border-radius:9px;padding:10px 12px;text-align:left;font:inherit;cursor:pointer}.new:hover{background:#252525}.side-label{font-size:12px;color:var(--muted);padding:0 8px}.side-note{margin-top:auto;font-size:12px;color:var(--muted);padding:0 8px}.main{min-width:0;flex:1;display:flex;flex-direction:column;position:relative}.topbar{height:59px;display:flex;align-items:center;padding:0 25px;border-bottom:1px solid #2c2c2c;font-weight:600}.topbar span{margin-left:8px;color:var(--muted);font-weight:400}.messages{width:min(790px,100%);margin:0 auto;padding:35px 24px 165px;overflow:auto;flex:1}.welcome{min-height:calc(100dvh - 270px);display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}.welcome h1{font-size:30px;letter-spacing:-.6px;margin:0 0 8px}.welcome p{margin:0;color:var(--muted)}.suggestions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:28px;width:min(590px,100%)}.suggestion{background:transparent;color:#ddd;border:1px solid #414141;border-radius:13px;padding:13px;text-align:left;font:inherit;cursor:pointer}.suggestion:hover{background:#292929}.message{display:flex;gap:15px;margin:0 0 25px;align-items:flex-start}.avatar{flex:0 0 30px;width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font-size:13px}.user .avatar{background:#444}.assistant .avatar{background:var(--green);color:#1b2418;font-weight:750}.content{padding-top:3px;white-space:pre-wrap;overflow-wrap:anywhere}.user .content{background:var(--bubble);border-radius:18px;padding:10px 15px;max-width:85%}.assistant .content{max-width:calc(100% - 45px)}.typing{color:var(--muted)}.composer-wrap{position:absolute;bottom:0;left:0;right:0;padding:16px 24px 13px;background:linear-gradient(transparent,var(--bg) 20%)}.composer{max-width:740px;margin:auto;background:#2f2f2f;border:1px solid #484848;border-radius:24px;padding:8px 9px 8px 17px;display:flex;align-items:flex-end;gap:10px;box-shadow:0 5px 25px #0003}.composer:focus-within{border-color:#656565}textarea{flex:1;resize:none;max-height:160px;min-height:38px;background:transparent;border:0;outline:0;color:var(--text);font:inherit;line-height:1.45;padding:8px 0}textarea::placeholder{color:#aaa}.send{width:38px;height:38px;border:0;border-radius:50%;background:var(--green);color:#162014;font-size:20px;font-weight:700;cursor:pointer}.send:disabled{opacity:.5;cursor:default}.hint{text-align:center;color:#888;font-size:11px;margin:8px 0 0}.mobile-new{display:none}
@media(max-width:680px){.sidebar{display:none}.topbar{padding:0 16px}.mobile-new{display:block;margin-left:auto;border:0;background:transparent;color:#ddd;font-size:21px}.messages{padding:22px 15px 145px}.welcome{min-height:calc(100dvh - 235px)}.welcome h1{font-size:25px}.suggestions{grid-template-columns:1fr}.suggestion:nth-child(n+3){display:none}.composer-wrap{padding:12px 12px 9px}}
</style></head>
<body><div class="app"><aside class="sidebar"><div class="brand"><div class="mark">A</div>Academic Helpdesk</div><button class="new" id="newChat">＋ &nbsp; New chat</button><div class="side-label">IIT Jodhpur · Student support</div><div class="side-note">Answers use academic documents and course data when available.</div></aside><main class="main"><header class="topbar">Academic Helpdesk <span>· IIT Jodhpur</span><button class="mobile-new" id="mobileNew" aria-label="New chat">＋</button></header><section class="messages" id="messages"><div class="welcome" id="welcome"><h1>What can I help you with?</h1><p>Ask about academic rules, courses, or drafting an email.</p><div class="suggestions"><button class="suggestion">What is the attendance requirement for the Major exam?</button><button class="suggestion">Find a course by its name or code</button><button class="suggestion">How do I request a make-up exam?</button><button class="suggestion">Draft an email to my instructor</button></div></div></section><div class="composer-wrap"><form class="composer" id="form"><textarea id="input" rows="1" placeholder="Message Academic Helpdesk" aria-label="Message Academic Helpdesk"></textarea><button class="send" id="send" aria-label="Send message">↑</button></form><div class="hint">Academic information can be incomplete. Check cited sources.</div></div></main></div>
<script>
const messages=document.querySelector('#messages'),welcome=document.querySelector('#welcome'),input=document.querySelector('#input'),send=document.querySelector('#send');let busy=false;const sid=sessionStorage.getItem('academicHelpdeskSession')||crypto.randomUUID();sessionStorage.setItem('academicHelpdeskSession',sid);
function add(role,text,extra=''){welcome?.remove();const row=document.createElement('div');row.className=`message ${role}`;const avatar=document.createElement('div');avatar.className='avatar';avatar.textContent=role==='user'?'Y':'A';const content=document.createElement('div');content.className='content '+extra;content.textContent=text;row.append(avatar,content);messages.append(row);messages.scrollTop=messages.scrollHeight;return content}
async function submit(text){text=text.trim();if(!text||busy)return;add('user',text);input.value='';input.style.height='auto';busy=true;send.disabled=true;const pending=add('assistant','Thinking…','typing');try{const res=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:text,session:sid})});const data=await res.json();pending.textContent=data.answer||data.error||'I could not get a response.';pending.classList.remove('typing')}catch(e){pending.textContent='Could not reach the helpdesk server. Please try again.';pending.classList.remove('typing')}finally{busy=false;send.disabled=false;input.focus();messages.scrollTop=messages.scrollHeight}}
document.querySelector('#form').addEventListener('submit',e=>{e.preventDefault();submit(input.value)});input.addEventListener('input',()=>{input.style.height='auto';input.style.height=Math.min(input.scrollHeight,160)+'px'});input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();submit(input.value)}});document.querySelectorAll('.suggestion').forEach(b=>b.addEventListener('click',()=>submit(b.textContent)));function reset(){messages.innerHTML='<div class="welcome" id="welcome"><h1>What can I help you with?</h1><p>Ask about academic rules, courses, or drafting an email.</p><div class="suggestions"><button class="suggestion">What is the attendance requirement for the Major exam?</button><button class="suggestion">Find a course by its name or code</button><button class="suggestion">How do I request a make-up exam?</button><button class="suggestion">Draft an email to my instructor</button></div></div>';document.querySelectorAll('.suggestion').forEach(b=>b.addEventListener('click',()=>submit(b.textContent)));sessionStorage.setItem('academicHelpdeskSession',crypto.randomUUID())}document.querySelector('#newChat').addEventListener('click',reset);document.querySelector('#mobileNew').addEventListener('click',reset);
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    helpdesk = None
    lock = threading.Lock()

    def do_GET(self):
        if urlparse(self.path).path not in ("/", "/index.html"):
            self.send_error(404)
            return
        body = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if urlparse(self.path).path != "/api/chat":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            question = str(payload.get("question", "")).strip()
            if not question:
                raise ValueError("Please enter a question.")
            with self.lock:
                if self.helpdesk is None:
                    import agents
                    import config
                    from runtime import Helpdesk
                    self.helpdesk = Helpdesk(agents.build_multi_agent(config.CHAT_MODEL))
                result = asyncio.run(self.helpdesk.ask(question, str(payload.get("session") or uuid.uuid4().hex)))
            self._json(200, {"answer": result["answer"]})
        except Exception as exc:
            self._json(503, {"error": f"The helpdesk could not answer: {exc}"})

    def _json(self, status, value):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")


if __name__ == "__main__":
    print(f"Academic Helpdesk webpage: http://{HOST}:{PORT}")
    print("Chat answers use the existing helpdesk; no document ingestion is run at startup.")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
