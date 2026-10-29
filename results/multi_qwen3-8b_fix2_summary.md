# Results: multi_qwen3-8b_fix2

| category | n | accuracy | groundedness | correct refusal | route | avg s/answer |
|---|---|---|---|---|---|---|
| email | 1 | 100% | - | 100% | - | 86 |
| schedule | 1 | 0% | - | 0% | - | 82 |
| ALL | 2 | 50% | - | 50% | - | 84 |

## Per question (pass pattern across runs, mean seconds, agents of last run)

| id | pass pattern | text identical across runs | mean s | agents |
|---|---|---|---|---|
| E04 | 1 | yes | 86 | helpdesk_orchestrator > email_agent |
| T05 | 0 | yes | 82 | helpdesk_orchestrator > schedule_agent |

## Questions whose answers changed across runs

- none