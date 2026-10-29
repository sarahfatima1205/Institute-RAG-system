# Results: multi_qwen3-8b_fix1

| category | n | accuracy | groundedness | correct refusal | route | avg s/answer |
|---|---|---|---|---|---|---|
| policy | 3 | 100% | 100% | - | 100% | 155 |
| email | 2 | 50% | 100% | 0% | 100% | 173 |
| ALL | 5 | 80% | 100% | 0% | 100% | 162 |

## Per question (pass pattern across runs, mean seconds, agents of last run)

| id | pass pattern | text identical across runs | mean s | agents |
|---|---|---|---|---|
| P02 | 1 | yes | 179 | helpdesk_orchestrator > policy_agent |
| P03 | 1 | yes | 158 | helpdesk_orchestrator > policy_agent |
| P06 | 1 | yes | 126 | helpdesk_orchestrator > policy_agent |
| E01 | 1 | yes | 298 | helpdesk_orchestrator > email_agent |
| E04 | 0 | yes | 48 | helpdesk_orchestrator > email_agent |

## Questions whose answers changed across runs

- none