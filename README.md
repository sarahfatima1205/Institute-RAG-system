# IIT Jodhpur Academic Helpdesk — multi-agent RAG (Google ADK + Ollama + ChromaDB)

Answers questions on academic rules, curriculum, time-table and drafts leave / make-up e-mails to instructors.
Anything else → "I don't know" + the question is logged to `logs/unanswered_questions.csv` for a human.
Every answer carries `(Source: <file>, <section>)`. Everything runs locally (no API keys).

## Architecture
```
student ─► helpdesk_orchestrator ─┬─► policy_agent   : search_policy_documents (Chroma RAG)
 (CLI or web)  (routes / refuses) ├─► schedule_agent : find_course, list_courses      (courses.csv)
                                  └─► email_agent    : find_course, get_instructor_email, draft_email
 all agents: log_unanswered_question
```
- `agents.build_single_agent()` = baseline (one agent, all tools); `agents.build_multi_agent()` = orchestrator version.
- Interfaces: `main.py` (terminal chat) and `web.py` (chat page with history, same multi-agent helpdesk).
- Retrieval re-ranks a pool of `CANDIDATES` (40) chunks by cosine similarity plus `LEX_WEIGHT` (0.25) x keyword overlap,
  because long PDF chunks otherwise out-score the short passage that holds the answer (see `config.py`).
- Refusals are enforced twice: a similarity threshold (`MIN_SIM`) in the RAG tool and explicit prompt rules.
- **Newest rule wins.** Every chunk carries an `effective_date` (front matter for `.md`, `data/docs_manifest.csv`
  for PDF/HTML). An amendment declares `supersedes: <regex>` in its front matter; at index time, chunks of *older*
  documents matching it are marked `superseded_by`, and `rag.search` withholds them and returns the amendment
  instead, with a `CURRENT RULE` note. This is how the 2024 attendance and examination amendments override the
  2019/2022 regulations (see `tests/test_rag.py`).

## Setup
Tested on Ubuntu, Python 3.12, Ollama 0.40, 16–32 GB RAM, CPU only. Run everything from the project directory.
```bash
python3 -m venv rag_env && source rag_env/bin/activate     # always use this env (system python lacks the packages)
pip install -r requirements.txt
ollama pull qwen3:8b && ollama pull llama3.1:8b && ollama pull nomic-embed-text
python scripts/download_docs.py     # fetch the official PDFs/page listed in the script (already in data/docs)
python rag.py                       # build/rebuild the vector store; re-run after any change in data/docs
```
- The 8192-token context is sent with every request (`NUM_CTX` in `config.py`), so no Ollama server setting is needed.
- Qwen3 "thinking" is switched off per request (`reasoning_effort="none"` → Ollama `think: false`).
- iitj.ac.in does not send its intermediate TLS certificate; `download_docs.py` adds it from
  `scripts/sectigo_ov_r36_intermediate.pem` (verification stays on).
- Check Ollama is running: `curl localhost:11434/api/version`. Snap install: `sudo snap start ollama` / `sudo snap stop ollama`
  (to stop it auto-starting at boot: `sudo snap stop --disable ollama`). Use the snap service, not a plain
  `ollama serve`, so the models pulled by the service are found.

## Run
```bash
python main.py --mode multi                                  # terminal chat, multi-agent ('exit' to quit)
python main.py --mode single --model ollama_chat/llama3.1:8b # single-agent baseline, other model
python web.py                                                # chat page at http://127.0.0.1:8000 (Ctrl+C to stop)
```
On CPU an answer takes ~20–120 s; the first one is slower while the model loads. If port 8000 is stuck
(e.g. after Ctrl+Z instead of Ctrl+C): `fuser -k 8000/tcp`.

## Tests and evaluation
```bash
EMBED_BACKEND=hash python -m pytest tests -q   # offline (no Ollama), 17 tests, uses a temp index
python eval/evaluate.py --mode multi  --model ollama_chat/qwen3:8b    --runs 3
python eval/evaluate.py --mode single --model ollama_chat/llama3.1:8b --runs 3
python eval/evaluate.py --compare results/multi_qwen3-8b.jsonl results/single_llama3.1-8b.jsonl
```
`eval/prompts.json` has 73 prompts: the 30 `core` ones (13 policy, 6 schedule, 4 e-mail, 7 out-of-scope) and 43 `extra`
ones (paraphrases, near-domain traps, typos, mixed language, adversarial and multi-turn). Select with `--set core|extra`
or `--ids`; the full procedure for running and reporting is in `EVAL_STEPS.md`. Each item has `expect`
(regex groups that must all match), optional `reject` (regexes that must not match, e.g. a withdrawn rule) and
`sources` (files an answer may cite to count as grounded). A full run (30 × 3 runs × 2 models) takes several
hours on CPU; use `--runs 1` while tuning.

## Corpus (`data/docs`, tracked in `data/docs_manifest.csv`)
| File | What | Effective |
|---|---|---|
| `academic_regulations_page.html` | Official Academic Regulations web page (full UG+PG text, split by its headings) | 2019-07 (+ later updates) |
| `regulations_2020_onwards.pdf` | Official regulations PDF (cover: students enrolled from July 2019) | 2019-07 |
| `btech_regulations_2018.pdf` | B.Tech regulations (enrolled from July 2014, revised 21 Jul 2018) | 2018-07-21 |
| `pg_regulations_2022_onwards.pdf` | PG regulations, enrolled from July 2022 | 2022-07 |
| `rules_and_regulations_for_ms.pdf` | M.S. by Research regulations | 2023-07 |
| `attendance_amendment_2024_25.{pdf,md}` | Circular 51/682 — attendance policy amendment (PDF is a scan; `.md` is the transcription that is indexed) | 2024-07-08 |
| `examination_amendment_2024_25.{pdf,md}` | Circular 52/683 — one Minor (2 h) + one Major (3 h, ≥40%) | 2024-07-08 |
| `academic_calendar_2026_27.pdf` | Academic calendar AY 2026-27 | 2026-07 |
| `curriculum_btech_cse.pdf`, `cse_courses_details.pdf` | B.Tech CSE curriculum structure and CSE course syllabi | 2020-08 / – |
| `ug_regulations_2019.md`, `pg_regulations_2019.md` | Condensed copies of the web page, kept for short section citations (also the unit-test corpus) | 2019-07 |

`data/csv/courses.csv` is **sample time-table data** (dummy instructors and e-mails, see `data/csv/README.md`).

## Status
Verified on our machine:
- offline tests (12) green; full index builds (1090 chunks, 9 superseded);
- end-to-end with `qwen3:8b` (multi-agent) and `llama3.1:8b` (single agent): routing to all three specialists, attendance and exam-duration
  questions answered from the 2024 amendments, course look-ups, e-mail drafts, refusals + logging for
  food / placement / weather / IPL questions.

Known limitations / open items for the team:
- 8B models still occasionally paraphrase a citation or route a borderline question wrongly; the evaluation
  (and `MIN_SIM`/`TOP_K`/prompt tuning) has not been run yet.
- `MIN_SIM=0.60` blocks most off-topic questions at retrieval; some (e.g. weather → academic calendar) pass it and
  rely on the prompt rules.
- P07 (branch change CGPA): the current web page says 8.5 (7.5 SC/ST/PwD) for students admitted 2025-26 and that
  branch change is discontinued from AY 2026-27; the 2019 PDF says 8.0 (7.0). The gold answer uses 8.5.
- `courses.csv` is sample data; replacing it means updating S01–S06/E01–E03 in `eval/prompts.json`.
- Corpus has 13 files; the target was 20–30. Still useful to add: department curricula beyond CSE, current
  time-table + slotting pattern, add/drop and withdrawal circulars, make-up/supplementary exam notices,
  grading (E/I grade) notices, minor/specialisation rules, faculty e-mail list (anonymised).
  Add the URL to `scripts/download_docs.py`, a row (with `effective_date`) to `data/docs_manifest.csv`, then `python rag.py`.
  A new amendment that replaces an older rule should be a `.md` with `effective_date` and `supersedes` front matter.

## Team plan (4 members, ~4 weeks)
| Member | Owns | Deliverables |
|---|---|---|
| **1 — Data & Corpus** | Collect/clean 20–30 documents, `docs_manifest.csv`, PDF→text checks, chunk/metadata quality (`rag.py` loaders, `effective_date`) | corpus in `data/docs`, manifest, notes on conflicts between old/new rules |
| **2 — RAG & Tools** | Embedding model choice (nomic vs bge-m3), `MIN_SIM`/`TOP_K` tuning, `courses.csv` from real time-table, `tools.py`, unanswered-log, unit tests | working retrieval, CSV tools, tests green |
| **3 — Agents** | ADK single → multi-agent, prompts, routing reliability on 8B models, citation format, e-mail agent, CLI/UI | `agents.py`, `runtime.py`, `main.py`, `web.py`, demo |
| **4 — Evaluation & Report** | 20–30 prompt set + gold answers, `evaluate.py`, model swap (Qwen3-8B vs Llama-3.1-8B), run-to-run variance table, error analysis, final report/slides | `results/`, comparison, report |

| Week | Milestone |
|---|---|
| 1 | Docs collected (≥10), single-agent skeleton, CSVs, prompts v1 |
| 2 | Full corpus indexed, all tools, single agent passes smoke tests, baseline eval |
| 3 | Multi-agent version, threshold/prompt tuning, eval with 2 LLMs × 3 runs |
| 4 | Error analysis (changed answers across runs/models), report, demo |

## Known risks
8B models sometimes skip transfers or tools: keep temperature low, keep tool docstrings short, consider a keyword
pre-router if routing accuracy is low. Use the `ollama_chat/` model prefix, not `ollama/` (tool calling needs the chat endpoint).
