# IIT Jodhpur Academic Helpdesk — multi-agent RAG (Google ADK + Ollama + ChromaDB)

Answers questions on academic rules, curriculum, time-table and drafts leave / make-up e-mails to instructors.
Anything else → "I don't know" + the question is logged to `logs/unanswered_questions.csv` for a human.
Every answer carries `(Source: <file>, <section>)`.

## Architecture
```
student ─► helpdesk_orchestrator ─┬─► policy_agent   : search_policy_documents (Chroma RAG)
          (routes / refuses)      ├─► schedule_agent : find_course, list_courses      (courses.csv)
                                  └─► email_agent    : find_course, get_instructor_email, draft_email
 all agents: log_unanswered_question
```
`agents.build_single_agent()` = baseline (one agent, all tools); `agents.build_multi_agent()` = orchestrator version.
Refusals are enforced twice: a similarity threshold (`MIN_SIM`) in the RAG tool and explicit prompt rules.

## Setup (16 GB laptop)
```bash
ollama pull qwen3:8b && ollama pull llama3.1:8b && ollama pull nomic-embed-text
export OLLAMA_CONTEXT_LENGTH=8192          # default context is too small for RAG + tools
pip install -r requirements.txt
python scripts/download_docs.py            # run on your machine; then add the rest of the docs (checklist below)
python rag.py                              # build the vector store
python main.py --mode multi                # chat      (--mode single for baseline)
python eval/evaluate.py --mode multi  --model ollama_chat/qwen3:8b   --runs 3
python eval/evaluate.py --mode single --model ollama_chat/llama3.1:8b --runs 3
python eval/evaluate.py --compare results/multi_qwen3-8b.jsonl results/multi_llama3.1-8b.jsonl
EMBED_BACKEND=hash python -m pytest tests -q   # offline tests, no Ollama needed (7 pass)
```

## What is verified vs. what you must still do
- Verified in a sandbox: tools, chunking, Chroma retrieval, refusal threshold, e-mail drafting, agent construction (ADK imports, 4 agents build). **Not run:** end-to-end LLM calls (no Ollama there) → run the eval yourselves, tune `MIN_SIM` and the prompts.
- `data/csv/courses.csv` is **sample data** (dummy instructors/slots). Replace with the real time-table; then update expected answers for S01–S06/E01–E03 in `eval/prompts.json`.
- `data/docs/ug_regulations_2019.md` / `pg_regulations_2019.md` are paraphrased working copies of the official Academic Regulations page. Replace/augment with the official PDFs.
- **Attendance conflict:** the 2019 regulation (§4.1.9) allows students below 75% to sit exams but needs ≥ C grade; IIT Jodhpur published an *Amendment in the Attendance Policy* (applies from Sem I 2024-25) and an *Examination Policy* amendment that I could not read. Download them and make P01's expected answer follow the newest document (chunks carry `effective_date`; the agent is told to prefer the latest).
- Likewise the OE-credit answer (10) comes from the 2019 table; the 2024 curriculum may differ — check against the curriculum documents you collect.

## Document checklist (target 20–30; track in `data/docs_manifest.csv`)
Found on iitj.ac.in (Office of Academics): UG/PG regulations (2014/2018, 2019–2022, PG 2022 onwards), regulations for students from July 2020/2021, MS-by-Research 2023, joint programmes in Medical Technologies, Revised norms for continuation/assistantship (M.Tech/PhD), **Attendance amendment & Examination amendment (AY 2024-25)**, Academic Calendar AY 2026-27 (+ earlier years).
Still to collect: B.Tech/M.Tech/M.Sc curricula & course lists per department, current semester time-table + slotting pattern, course registration / add-drop / withdrawal circulars, make-up/supplementary exam notices, recent office orders & circulars, grading/ E-grade/ I-grade notices, branch-change & minor/specialisation rules, faculty list with e-mail IDs per department, leave/semester-withdrawal forms. (Anonymise personal data.)

## Team plan (4 members, ~4 weeks)
| Member | Owns | Deliverables |
|---|---|---|
| **1 — Data & Corpus** | Collect/clean 20–30 documents, `docs_manifest.csv`, PDF→text checks, chunk/metadata quality (`rag.py` loaders, `effective_date`) | corpus in `data/docs`, manifest, notes on conflicts between old/new rules |
| **2 — RAG & Tools** | Embedding model choice (nomic vs bge-m3), `MIN_SIM`/`TOP_K` tuning, `courses.csv` from real time-table, `tools.py`, unanswered-log, unit tests | working retrieval, CSV tools, tests green |
| **3 — Agents** | ADK single → multi-agent, prompts, routing reliability on 8B models, citation format, e-mail agent, CLI/UI | `agents.py`, `runtime.py`, `main.py`, demo |
| **4 — Evaluation & Report** | 20–30 prompt set + gold answers, `evaluate.py`, model swap (Qwen3-8B vs Llama-3.1-8B), run-to-run variance table, error analysis, final report/slides | `results/`, comparison, report |

| Week | Milestone |
|---|---|
| 1 | Docs collected (≥10), single-agent skeleton, CSVs, prompts v1 |
| 2 | Full corpus indexed, all tools, single agent passes smoke tests, baseline eval |
| 3 | Multi-agent version, threshold/prompt tuning, eval with 2 LLMs × 3 runs |
| 4 | Error analysis (changed answers across runs/models), report, demo |

## Known risks
8B models sometimes skip transfers or tools: lower temperature, keep tool docstrings short, consider a keyword pre-router if routing accuracy is low. Qwen3 "thinking" is disabled via `/no_think`. Use the `ollama_chat/` model prefix, not `ollama/`.
