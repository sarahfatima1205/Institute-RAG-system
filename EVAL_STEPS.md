# Evaluation Procedure

## Purpose
This procedure measures the performance of the IIT Jodhpur Academic Helpdesk on the 73 test prompts in
`eval/prompts.json`. No model training or fine-tuning is involved: the pre-trained models are used as downloaded,
and the evaluation records the accuracy, citation groundedness, refusal behaviour, routing and response time of
each configuration.

## Prerequisites
- Ollama installed and running, with the models `qwen3:8b`, `llama3.1:8b` and `nomic-embed-text` available.
- Python 3.11 or later.
- At least 16 GB of RAM, with other memory-intensive applications closed (8B models).
- All commands are executed from the project root directory.
- Only one evaluation should run on a machine at a time, as concurrent runs compete for the same compute
  resources and invalidate the timing measurements.

## 0. Assignment of configurations
Each team member evaluates one configuration. `<MODE>`, `<MODEL>` and `<NAME>` are used in the commands below.

| Member | `<MODE>` | `<MODEL>` | `<NAME>` (result file prefix) |
|---|---|---|---|
| A | `multi`  | `ollama_chat/qwen3:8b`    | `multi_qwen3-8b` |
| B | `single` | `ollama_chat/qwen3:8b`    | `single_qwen3-8b` |
| C | `multi`  | `ollama_chat/llama3.1:8b` | `multi_llama3.1-8b` |
| D | `single` | `ollama_chat/llama3.1:8b` | `single_llama3.1-8b` |

The model name must carry the `ollama_chat/` prefix (not `ollama/`); otherwise tool calling does not work.

## 1. Obtain the latest code
```bash
git pull
```
The checkout must include `EVAL_STEPS.md`, `eval/evaluate.py`, `eval/prompts.json` and `tools.py` in their
current versions.

## 2. Set up the Python environment (once)
```bash
python -m venv rag_env
# Linux/macOS:         source rag_env/bin/activate
# Windows PowerShell:  .\rag_env\Scripts\Activate.ps1
pip install -r requirements.txt
```
With conda: `conda create -n rag_env python=3.11`, `conda activate rag_env`, then `pip install -r requirements.txt`.

## 3. Verify Ollama and the models
```bash
ollama list
curl localhost:11434/api/version        # Windows PowerShell: Invoke-RestMethod localhost:11434/api/version
```
`ollama list` must show `qwen3:8b`, `llama3.1:8b` and `nomic-embed-text`, and the second command must return a
version number. If the server is not running, start it with `ollama serve` (Linux) or launch the Ollama
application (Windows). A missing model is installed with `ollama pull <name>`. For a remote Ollama server, set
`OLLAMA_API_BASE=http://<host>:11434` beforehand.

## 4. Run the offline tests (about 2 minutes, no model required)
```bash
# Linux/macOS
EMBED_BACKEND=hash python -m pytest tests -q
# Windows PowerShell
$env:EMBED_BACKEND="hash"; python -m pytest tests -q; Remove-Item Env:EMBED_BACKEND
```
Expected result: `16 passed`. If any test fails, do not proceed; report the failure to the team.
`EMBED_BACKEND` must be unset for all subsequent steps.

## 5. Build the search index (a few minutes; requires `nomic-embed-text`)
```bash
python rag.py
```
The expected output is `Indexed <N> chunks` with N around 1,090. The index must be rebuilt whenever a file in
`data/docs` changes.

## 6. Smoke test (single question, with timing)
```bash
python eval/evaluate.py --mode <MODE> --model <MODEL> --ids P01 --runs 1 --tag smoke
```
A successful run prints a line of the form `[1/1  95s, ...] P01 run0 acc=True grounded=True ...` followed by a
summary table.
- The first answer is slower because the model is being loaded into memory.
- Report the time per answer to the team; it determines the schedule for the full runs.
- An answer beginning with `ERROR:` indicates a setup problem (Ollama not running, model missing) and must be
  resolved before continuing. `acc=False` alone is not an error and may simply be reported.

## 7. Full evaluation
**7a. Core prompts (30 prompts, 3 runs each, 90 answers). This is the primary result.**
```bash
python eval/evaluate.py --mode <MODE> --model <MODEL> --set core --runs 3
```
**7b. Extended prompts (43 prompts covering paraphrases, near-domain traps, typographical errors, mixed-language
input, adversarial instructions and multi-turn follow-ups; 1 run each).**
```bash
python eval/evaluate.py --mode <MODE> --model <MODEL> --set extra --runs 1 --tag extra
```
Notes:
- Results are saved after every answer. An interrupted run is continued by repeating the same command with
  `--resume` appended.
- Keep the machine connected to power with sleep disabled. For remote sessions use `tmux` or `screen` so that a
  dropped connection does not terminate the run.
- Progress is reported as `[answers done/total, seconds for this answer, elapsed minutes]`.
- Measured reference (qwen3:8b, multi-agent mode, 4 cores, 16 GB RAM): 1–2 minutes per time-table answer and
  2–5 minutes per policy or e-mail answer, so step 7a takes several hours. The first answer after loading a model
  is slower.

## 8. Return the results
The `results/` directory is excluded from version control. Please send the following files:
```
results/<NAME>.jsonl              results/<NAME>_summary.md
results/<NAME>_extra.jsonl        results/<NAME>_extra_summary.md
results/<NAME>_unanswered.csv     results/<NAME>_extra_unanswered.csv
```
Please also include the machine specification (processor and RAM), the time per answer from the smoke test, and a
note of any errors or unexpected behaviour.

## 9. Comparing two result files (report team)
```bash
python eval/evaluate.py --compare results/multi_qwen3-8b.jsonl results/single_qwen3-8b.jsonl
```

## Interpreting the results
- **accuracy**: the answer contains every expected fact and none of the forbidden content (for example, the
  withdrawn attendance rule).
- **groundedness**: the answer cites a source document that the tools actually returned in that run.
- **correct refusal**: for out-of-scope questions, the answer says "I don't know" and the question was logged.
- **route**: the expected specialist agent took part (multi-agent mode only).
- **pass pattern**: for example `101` means the question passed in runs 1 and 3 and failed in run 2.
  `text identical = NO` means the wording of the answer differed between runs.
- A failed item is not necessarily a model error. The expected-answer pattern may be too strict, or retrieval
  may have returned an unsuitable passage. Inspect the recorded answer in the `.jsonl` file before attributing
  a failure to the model.

## Troubleshooting
| Symptom | Resolution |
|---|---|
| `ERROR: ... connection refused` in answers | Ollama is not running (step 3). |
| `ERROR: ... model not found` | Run `ollama pull <model>` and check the `ollama_chat/` prefix. |
| Every policy question is answered "I don't know", including P01 | The index is missing or was built with the test setting. Unset `EMBED_BACKEND` and run `python rag.py` (step 5). |
| Very slow responses or system instability | Close other applications and run one evaluation at a time. 16 GB RAM is the minimum for an 8B model. |
| `ModuleNotFoundError` | The virtual environment is not activated (step 2). |
