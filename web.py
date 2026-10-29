"""Serve the Academic Helpdesk chat page. Run with: python web.py"""
import asyncio
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = 8000

INTRO_ANSWERS = {
    "hello": "Hi! I’m the IIT Jodhpur Academic Helpdesk. I can answer questions about academic rules, courses, and instructor email drafts.",
    "identity": "I’m the IIT Jodhpur Academic Helpdesk, a chat assistant for student academic questions.",
    "work": "My job is to help with IIT Jodhpur academic regulations, course and timetable details, and drafts of emails to instructors.",
    "capabilities": "I can search the academic documents, look up courses in the timetable data, and prepare an email draft. I don’t send emails.",
    "usage": "You can ask about academic rules, attendance, exams, credits, course details, or ask me to draft an instructor email. I use the project’s documents and course data to answer.",
    "operation": "For academic rules, I search the project’s document index. For course details, I look in its timetable CSV. For email requests, I create a draft for you to review.",
    "scope": "I’m focused on IIT Jodhpur academics: regulations, courses, timetable information, and instructor email drafts. I don’t handle unrelated general questions.",
}


def intro_answer(question: str) -> str | None:
    """Answer a small allowlist of greetings and questions about this helpdesk."""
    q = " ".join(question.lower().strip().rstrip("?!., ").split())
    if q in {"hi", "hii", "hello", "hey", "hello there", "hi there", "good morning", "good afternoon"}:
        return INTRO_ANSWERS["hello"]
    if q in {"who are you", "what are you", "what is this", "what is this chatbot", "what is this bot"}:
        return INTRO_ANSWERS["identity"]
    if q in {"what do you do", "what is your work", "what is your job", "what work do you do", "what is your purpose"}:
        return INTRO_ANSWERS["work"]
    if q in {"what can you do", "what can you help with", "what can i ask you", "how can you help", "can you help me"}:
        return INTRO_ANSWERS["capabilities"]
    if q in {"how do you work", "how does this work", "how do you answer questions"}:
        return INTRO_ANSWERS["operation"]
    if q in {"what can i ask", "what topics can i ask about", "what questions can i ask", "what do you know about"}:
        return INTRO_ANSWERS["usage"]
    if q in {"what is your scope", "what are you focused on", "do you answer general questions", "can you answer anything"}:
        return INTRO_ANSWERS["scope"]
    return None


PAGE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Academic Helpdesk</title>
<style>
:root{color-scheme:dark;--bg:#212121;--panel:#171717;--line:#343434;--text:#ececec;--muted:#a0a0a0;--green:#b8f28b;--bubble:#303030}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;height:100dvh}
.assistant .content p{margin:0 0 12px}.assistant .content p:last-child{margin-bottom:0}.assistant .content ol,.assistant .content ul{margin:7px 0 14px;padding-left:27px}.assistant .content li{padding-left:2px;margin:3px 0}.assistant .content code{background:#353535;border-radius:4px;padding:2px 5px;font: .92em ui-monospace,monospace}.assistant .content a{color:#b8f28b;text-decoration:underline}
.app{height:100%;display:flex}.sidebar{width:258px;background:var(--panel);padding:18px 13px;display:flex;flex-direction:column;gap:15px}.brand{display:flex;gap:10px;align-items:center;font-weight:650;font-size:15px}.mark{width:29px;height:29px;border-radius:9px;background:var(--green);color:#172017;display:grid;place-items:center;font-weight:800}.new{border:1px solid #454545;color:#e8e8e8;background:transparent;border-radius:9px;padding:10px 12px;text-align:left;font:inherit;cursor:pointer}.new:hover{background:#252525}.side-label{font-size:12px;color:var(--muted);padding:4px 8px 0}.chat-list{overflow:auto;display:flex;flex-direction:column;gap:3px}.chat-item{display:flex;align-items:center;gap:6px}.chat-open{min-width:0;flex:1;border:0;background:transparent;color:#c9c9c9;border-radius:8px;padding:9px 10px;text-align:left;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font:13px inherit;cursor:pointer}.chat-open:hover,.chat-item.active .chat-open{background:#292929;color:#fff}.chat-delete{border:0;background:transparent;color:#888;border-radius:6px;padding:5px 8px;cursor:pointer}.chat-delete:hover{background:#3a2929;color:#ffaaaa}.side-note{margin-top:auto;font-size:12px;color:var(--muted);padding:0 8px}.main{min-width:0;flex:1;display:flex;flex-direction:column;position:relative}.topbar{height:59px;display:flex;align-items:center;padding:0 25px;border-bottom:1px solid #2c2c2c;font-weight:600}.topbar span{margin-left:8px;color:var(--muted);font-weight:400}.messages{width:min(790px,100%);margin:0 auto;padding:35px 24px 165px;overflow:auto;flex:1}.welcome{min-height:calc(100dvh - 270px);display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}.welcome h1{font-size:30px;letter-spacing:-.6px;margin:0 0 8px}.welcome p{margin:0;color:var(--muted)}.suggestions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:28px;width:min(590px,100%)}.suggestion{background:transparent;color:#ddd;border:1px solid #414141;border-radius:13px;padding:13px;text-align:left;font:inherit;cursor:pointer}.suggestion:hover{background:#292929}.message{display:flex;gap:15px;margin:0 0 25px;align-items:flex-start}.avatar{flex:0 0 30px;width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font-size:13px}.user .avatar{background:#444}.assistant .avatar{background:var(--green);color:#1b2418;font-weight:750}.content{padding-top:3px;white-space:pre-wrap;overflow-wrap:anywhere}.user .content{background:var(--bubble);border-radius:18px;padding:10px 15px;max-width:85%}.assistant .content{max-width:calc(100% - 45px)}.typing{color:var(--muted)}.composer-wrap{position:absolute;bottom:0;left:0;right:0;padding:16px 24px 13px;background:linear-gradient(transparent,var(--bg) 20%)}.composer{max-width:740px;margin:auto;background:#2f2f2f;border:1px solid #484848;border-radius:24px;padding:8px 9px 8px 17px;display:flex;align-items:flex-end;gap:10px;box-shadow:0 5px 25px #0003}.composer:focus-within{border-color:#656565}textarea{flex:1;resize:none;max-height:160px;min-height:38px;background:transparent;border:0;outline:0;color:var(--text);font:inherit;line-height:1.45;padding:8px 0}textarea::placeholder{color:#aaa}.send{width:38px;height:38px;border:0;border-radius:50%;background:var(--green);color:#162014;font-size:20px;font-weight:700;cursor:pointer}.send:disabled{opacity:.5;cursor:default}.hint{text-align:center;color:#888;font-size:11px;margin:8px 0 0}.mobile-new{display:none}
@media(max-width:680px){.sidebar{display:none}.topbar{padding:0 16px}.mobile-new{display:block;margin-left:auto;border:0;background:transparent;color:#ddd;font-size:21px}.messages{padding:22px 15px 145px}.welcome{min-height:calc(100dvh - 235px)}.welcome h1{font-size:25px}.suggestions{grid-template-columns:1fr}.suggestion:nth-child(n+3){display:none}.composer-wrap{padding:12px 12px 9px}}
</style></head>
<body><div class="app"><aside class="sidebar"><div class="brand"><div class="mark">A</div>Academic Helpdesk</div><button class="new" id="newChat">＋ &nbsp; New chat</button><div class="side-label">Recent chats</div><div class="chat-list" id="chatList"></div><div class="side-note">Ask about IIT Jodhpur academics or about this helpdesk.</div></aside><main class="main"><header class="topbar">Academic Helpdesk <span>· IIT Jodhpur</span><button class="mobile-new" id="mobileNew" aria-label="New chat">＋</button></header><section class="messages" id="messages"><div class="welcome" id="welcome"><h1>What can I help you with?</h1><p>Ask about academic rules, courses, or drafting an email.</p><div class="suggestions"><button class="suggestion">What is the attendance requirement for the Major exam?</button><button class="suggestion">Find a course by its name or code</button><button class="suggestion">How do I request a make-up exam?</button><button class="suggestion">Draft an email to my instructor</button></div></div></section><div class="composer-wrap"><form class="composer" id="form"><textarea id="input" rows="1" placeholder="Message Academic Helpdesk" aria-label="Message Academic Helpdesk"></textarea><button class="send" id="send" aria-label="Send message">↑</button></form><div class="hint">Academic information can be incomplete. Check cited sources.</div></div></main></div>
<script>
const messages=document.querySelector('#messages'),input=document.querySelector('#input'),send=document.querySelector('#send'),chatList=document.querySelector('#chatList');let busy=false;let chats=JSON.parse(localStorage.getItem('academicHelpdeskChats')||'[]'),activeId=null;
function persist(){localStorage.setItem('academicHelpdeskChats',JSON.stringify(chats));renderList()}
function renderList(){chatList.replaceChildren();for(const chat of chats){const item=document.createElement('div');item.className='chat-item'+(chat.id===activeId?' active':'');const open=document.createElement('button');open.className='chat-open';open.textContent=chat.title;open.title=chat.title;open.onclick=()=>openChat(chat.id);const del=document.createElement('button');del.className='chat-delete';del.textContent='×';del.title='Delete chat';del.onclick=e=>{e.stopPropagation();chats=chats.filter(c=>c.id!==chat.id);if(activeId===chat.id)activeId=null;persist();if(!activeId)showWelcome()};item.append(open,del);chatList.append(item)}}
function inlineMarkdown(text){let s=text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');s=s.replace(/`([^`]+)`/g,'<code>$1</code>');s=s.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/__(.+?)__/g,'<strong>$1</strong>').replace(/~~(.+?)~~/g,'<del>$1</del>').replace(/(^|[^*])\*([^*]+)\*/g,'$1<em>$2</em>');s=s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,'<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');return s}
function markdownHtml(text){const lines=text.split(/\r?\n/);let html='',paragraph=[],list=null;const closeList=()=>{if(list){html+=`</${list}>`;list=null}};const flush=()=>{if(paragraph.length){html+=`<p>${paragraph.map(inlineMarkdown).join('<br>')}</p>`;paragraph=[]}};for(const raw of lines){const line=raw.trim();if(!line){flush();closeList();continue}const heading=line.match(/^(#{1,3})\s+(.+)$/);if(heading){flush();closeList();const n=heading[1].length;html+=`<h${n}>${inlineMarkdown(heading[2])}</h${n}>`;continue}const item=line.match(/^[-*+]\s+(.+)$/);const numbered=line.match(/^\d+[.)]\s+(.+)$/);if(item||numbered){flush();const kind=item?'ul':'ol';if(list!==kind){closeList();list=kind;html+=`<${list}>`}html+=`<li>${inlineMarkdown((item||numbered)[1])}</li>`;continue}closeList();paragraph.push(line)}flush();closeList();return html}
function setMessage(content,role,text){if(role==='assistant')content.innerHTML=markdownHtml(text);else content.textContent=text}
function draw(role,text){const row=document.createElement('div');row.className=`message ${role}`;const avatar=document.createElement('div');avatar.className='avatar';avatar.textContent=role==='user'?'Y':'A';const content=document.createElement('div');content.className='content';setMessage(content,role,text);row.append(avatar,content);messages.append(row);return content}
function showWelcome(){messages.innerHTML='<div class="welcome" id="welcome"><h1>What can I help you with?</h1><p>Ask about academic rules, courses, or drafting an email.</p><div class="suggestions"><button class="suggestion">What is the attendance requirement for the Major exam?</button><button class="suggestion">Find a course by its name or code</button><button class="suggestion">How do I request a make-up exam?</button><button class="suggestion">Draft an email to my instructor</button></div></div>';document.querySelectorAll('.suggestion').forEach(b=>b.onclick=()=>submit(b.textContent))}
function ensureChat(text){if(activeId)return chats.find(c=>c.id===activeId);const chat={id:crypto.randomUUID(),session:crypto.randomUUID(),title:text.slice(0,42)+(text.length>42?'…':''),messages:[]};chats.unshift(chat);activeId=chat.id;persist();return chat}
function openChat(id){if(busy)return;activeId=id;const chat=chats.find(c=>c.id===id);messages.replaceChildren();if(!chat||!chat.messages.length){showWelcome()}else{for(const m of chat.messages)draw(m.role,m.text)}renderList();messages.scrollTop=messages.scrollHeight}
async function submit(text){text=text.trim();if(!text||busy)return;const chat=ensureChat(text);chat.messages.push({role:'user',text});messages.querySelector('.welcome')?.remove();draw('user',text);persist();input.value='';input.style.height='auto';busy=true;send.disabled=true;const pending=draw('assistant','Thinking…');pending.classList.add('typing');try{const res=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:text,session:chat.session})});const data=await res.json();const answer=data.answer||data.error||'I could not get a response.';setMessage(pending,'assistant',answer);chat.messages.push({role:'assistant',text:answer});persist()}catch(e){const answer='Could not reach the helpdesk server. Please try again.';pending.textContent=answer;chat.messages.push({role:'assistant',text:answer});persist()}finally{pending.classList.remove('typing');busy=false;send.disabled=false;input.focus();messages.scrollTop=messages.scrollHeight}}
function newChat(){if(busy)return;activeId=null;showWelcome();renderList();input.focus()}
document.querySelector('#form').addEventListener('submit',e=>{e.preventDefault();submit(input.value)});input.addEventListener('input',()=>{input.style.height='auto';input.style.height=Math.min(input.scrollHeight,160)+'px'});input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();submit(input.value)}});document.querySelector('#newChat').onclick=newChat;document.querySelector('#mobileNew').onclick=newChat;renderList();
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
            introduction = intro_answer(question)
            if introduction:
                self._json(200, {"answer": introduction})
                return
            with self.lock:
                # stored on the class: a new Handler is created per request, so self.* would rebuild
                # the agents (and lose chat sessions) on every message
                if Handler.helpdesk is None:
                    import agents
                    import config
                    from runtime import Helpdesk
                    Handler.helpdesk = Helpdesk(agents.build_multi_agent(config.CHAT_MODEL))
                result = asyncio.run(Handler.helpdesk.ask(question, str(payload.get("session") or uuid.uuid4().hex)))
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
