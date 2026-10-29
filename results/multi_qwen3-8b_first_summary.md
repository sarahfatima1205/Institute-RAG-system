# Results: multi_qwen3-8b_first

| category | n | accuracy | groundedness | correct refusal | route | avg s/answer |
|---|---|---|---|---|---|---|
| policy | 2 | 50% | 50% | - | 100% | 313 |
| schedule | 2 | 100% | 100% | - | 100% | 83 |
| email | 2 | 50% | 0% | 0% | 100% | 232 |
| out_of_scope | 1 | 100% | - | 100% | - | 72 |
| ALL | 7 | 71% | 60% | 50% | 100% | 189 |

## Per question (pass pattern across runs, mean seconds, agents of last run)

| id | pass pattern | text identical across runs | mean s | agents |
|---|---|---|---|---|
| P01 | 1 | yes | 395 | helpdesk_orchestrator > policy_agent |
| P02 | 0 | yes | 231 | helpdesk_orchestrator > policy_agent |
| S01 | 1 | yes | 64 | helpdesk_orchestrator > schedule_agent |
| S03 | 1 | yes | 102 | helpdesk_orchestrator > schedule_agent |
| E01 | 1 | yes | 392 | helpdesk_orchestrator > email_agent |
| E04 | 0 | yes | 72 | helpdesk_orchestrator > email_agent |
| O03 | 1 | yes | 72 | helpdesk_orchestrator |

## Questions whose answers changed across runs

- none