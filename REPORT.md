# IIT Jodhpur Academic Helpdesk — Project Report

## 1. Project overview

This project implements an academic helpdesk that answers questions about IIT Jodhpur academic rules, programmes, curriculum, courses and timetable data. It can also prepare (but does not send) email drafts to course instructors for leave, sick leave and make-up examination requests.

The helpdesk is intended to answer only from the project’s documents and course data. For out-of-scope questions or questions it cannot support with available sources, the agents are instructed to say “I don't know” and log the question for human follow-up. Factual answers are expected to cite the source document or CSV.

The project is implemented in Python with Google ADK agents, LiteLLM’s Ollama connector, Ollama-hosted chat and embedding models, and ChromaDB for local vector retrieval. The default chat model is `qwen3:8b`; `llama3.1:8b` can also be selected. A single-agent baseline is provided alongside the multi-agent system.

## 2. Assignment scope and coverage

| Assignment requirement | Project implementation |
|---|---|
| Answer academic policy and curriculum questions | Policy specialist searches the indexed academic documents. |
| Answer course, slot and timetable questions | Schedule specialist searches `courses.csv` by code/name and filters or counts rows. |
| Draft leave and make-up examination emails | Email specialist resolves course/instructor information and creates a reviewable draft. No email is sent. |
| Refuse unrelated or unsupported questions | Prompt rules and retrieval thresholds direct the system to refuse; the refusal workflow logs unanswered questions. |
| Cite source material | Agent instructions require citations; retrieval results provide document/section citations and course tools identify `courses.csv` as their source. |
| Use a local setup suitable for a 16 GB computer | Local Ollama models and a persistent local ChromaDB are configured. The evaluation instructions specify 16 GB RAM as the minimum for the 8B models. |
| Compare single/multi-agent and model performance | The evaluation harness supports single and multi-agent runs, multiple models, repeated runs, and comparisons. |
| Collect 20–30 real source documents | **Not yet met:** the current document corpus has 14 files. The timetable is also sample data, not a real semester timetable. |

## 3. System design

### 3.1 Agent architecture

The multi-agent system is organized around a helpdesk orchestrator and three specialist agents:

- **Policy agent:** handles regulations, attendance, examinations, grading, credits, degree requirements, programmes, curriculum and the academic calendar. It uses document search and unanswered-question logging.
- **Schedule agent:** handles course codes, names, slots, venues, credits, course levels, types and filtered course counts using the course CSV.
- **Email agent:** resolves a course and its instructor, then drafts the requested email and attaches a relevant policy note. Unknown course codes are not guessed.
- **Helpdesk orchestrator:** routes academic questions to a specialist and refuses clearly unrelated questions.

The single-agent baseline has access to all tools directly. It supports comparisons with the orchestrated system.

### 3.2 Request and response flow

1. A student submits a question through the terminal or web interface.
2. The helpdesk sends the question to the selected ADK agent configuration.
3. The agent calls the appropriate RAG or CSV/email tool.
4. The response is composed from returned tool results, with source citations required by the instructions.
5. If the question is unsupported or out of scope, the agent should respond with “I don't know” and record the question in a CSV log.

### 3.3 Retrieval-augmented generation

The RAG pipeline loads PDF, HTML, Markdown and text documents, splits content into sections and overlapping chunks, embeds the chunks, and persists them in ChromaDB. Ollama’s `nomic-embed-text` is the configured local embedding model. The pipeline retrieves a candidate set using cosine similarity, then re-ranks candidates using keyword overlap.

The configuration includes a minimum similarity threshold, a candidate count, a top-k result count, chunk size and overlap. Documents carry source and effective-date metadata. Markdown amendments can declare which older rules they supersede; matching older passages are withheld and the newer amendment is returned with a current-rule note.

The `hash` embedding backend is reserved for offline unit tests and is not the production semantic embedding configuration.

### 3.4 Tools

- `search_policy_documents`: retrieves relevant policy passages with citations and effective-date information.
- `find_course`: searches course codes and names, including a limited fuzzy name match.
- `list_courses`: filters and counts course rows by department, level, course type and slot.
- `get_instructor_email`: returns the instructor contact listed for a course.
- `draft_email`: creates a leave, sick-leave or make-up examination email, leaves placeholders for unknown student details, includes a policy note, and marks the result as an unsent draft.
- `log_unanswered_question`: appends the timestamp, question and reason to the unanswered-question CSV.

## 4. Data and document corpus

The manifest currently lists 14 document files covering:

- Undergraduate and postgraduate regulations, including earlier regulation editions.
- The official academic regulations page.
- Attendance and examination amendments from 2024–25. The PDF circulars are scans; their Markdown transcriptions are used for indexing.
- An academic calendar for 2026–27.
- B.Tech. CSE curriculum and CSE course details.
- M.S. by Research regulations.

The document manifest records categories, source URLs, effective dates and status notes. The RAG loader uses this metadata to provide source details and to support newer-rule precedence.

The timetable data is in `data/csv/courses.csv`. Its accompanying README identifies it as **sample data** with placeholder course rows and dummy instructor names and email addresses. It is suitable for exercising the tools, but should not be treated as an authoritative live timetable or real faculty directory.

### Corpus gaps and data work needed

The assignment requests 20–30 real documents. The current manifest has 14 document files, leaving the corpus below that target. The project README identifies potential additions such as current timetable and slotting information, add/drop and withdrawal circulars, make-up or supplementary exam notices, grading notices, minor/specialisation rules, additional departmental curricula and an anonymised faculty email list.

Before using the system as an authoritative helpdesk, replace the sample timetable with a verified current source, retain dummy or anonymised contacts where appropriate, verify document dates and applicability, and add enough relevant source documents to meet the assignment target.

## 5. User interfaces and execution

The project provides:

- **Command-line chat:** `main.py`, with `--mode single|multi`, optional `--model`, and `--ingest` to build the vector index before starting.
- **Web chat:** `web.py`, serving a local chat page and maintaining chat history. It uses the multi-agent configuration and does not ingest documents automatically at startup.
- **Indexing:** `rag.py`, which builds or rebuilds the persistent ChromaDB collection from the configured document directory.

The README documents setup using a Python virtual environment, installing `requirements.txt`, obtaining the Ollama models, and building the vector index. The default model endpoint is local Ollama; `CHAT_MODEL`, `OLLAMA_API_BASE`, and other retrieval settings can be configured through environment variables.

The project is designed to run locally without hosted model API keys. The evaluation instructions specify Python 3.11 or later and 16 GB RAM as the minimum for running an 8B model; actual response times depend on the machine and model.

## 6. Evaluation design

The evaluation set in `eval/prompts.json` contains 73 prompts:

- **30 core prompts:** 13 policy, 6 schedule, 4 email and 7 out-of-scope questions.
- **43 extended prompts:** paraphrases, near-domain traps, typos, mixed-language input, adversarial instructions and multi-turn follow-ups.

Prompts include expected-answer patterns, rejected patterns where needed, permissible source names, refusal expectations and, for multi-agent runs, expected specialist routes. The evaluation script computes:

- **Accuracy:** expected patterns match, rejected patterns do not, and the system has not refused an in-scope question.
- **Groundedness:** a cited source is among the expected sources and was returned by a tool during that run.
- **Correct refusal:** the answer indicates that it does not know and the unanswered-question logging tool was called.
- **Routing:** the expected specialist participated in a multi-agent run.
- **Stability:** answer text and pass/fail behavior across repeated runs.
- **Response time:** per-answer duration and category averages.

The harness supports repeated runs, resuming interrupted evaluations, filtering by prompt set or ID, and comparing two result files. `EVAL_STEPS.md` describes a four-configuration comparison: multi-agent Qwen3 8B, single-agent Qwen3 8B, multi-agent Llama 3.1 8B and single-agent Llama 3.1 8B. It recommends three runs for the 30 core prompts and one run for the extended prompts.

The unit tests focus on offline retrieval and amendment handling, course lookup/count behavior, email drafting, citations/source behavior and unanswered-question logging. They use the hash embedder and do not require a live Ollama model.

## 7. Results


## 8. Current limitations and recommendations

1. **Complete the source collection.** Add at least six further real, relevant documents to reach the assignment’s minimum of 20, and preferably build toward 30. Track provenance and effective dates in the manifest.
2. **Replace sample timetable data.** Use a current, verified timetable. Update prompt gold answers to match the real data and retain anonymised contact details if needed.
3. **Run and record the planned evaluation.** Populate the Results section with per-model and per-mode metrics, machine specifications, run counts, response times, and question-level changes across repeated runs.
4. **Review citation and routing reliability.** The README notes that 8B models may occasionally paraphrase citations or route borderline questions incorrectly. Validate these behaviors using the groundedness and route metrics.
5. **Validate policy applicability.** The corpus contains documents for different admission cohorts and programmes. The system should be evaluated to ensure answers distinguish the applicable cohort and do not blend conflicting rules.
6. **Keep the index current.** Rebuild the vector store when indexed documents change, and periodically verify that downloaded or transcribed documents still match their official sources.

## 9. Conclusion

The project provides a working architecture for a local, multi-agent academic helpdesk, including policy RAG, timetable tools, draft email generation, out-of-scope logging, user interfaces and an evaluation harness. The code covers the core functional shape of the assignment. The main remaining assignment gaps are the undersized document corpus, placeholder timetable/contact data, and the performance results that are to be added after evaluation.

## Project files referenced

- `README.md` — setup, architecture, corpus status and limitations.
- `agents.py`, `runtime.py` — agent definitions and ADK execution wrapper.
- `rag.py`, `tools.py`, `config.py` — retrieval, tools and configuration.
- `main.py`, `web.py` — terminal and web interfaces.
- `data/docs_manifest.csv`, `data/docs/`, `data/csv/courses.csv` — source inventory and data.
- `eval/prompts.json`, `eval/evaluate.py`, `EVAL_STEPS.md` — evaluation prompts and procedure.
- `tests/` — offline unit tests.
