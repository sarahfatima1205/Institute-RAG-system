# Results: multi_qwen3-8b

| category | n | accuracy | groundedness | correct refusal | route | avg s/answer |
|---|---|---|---|---|---|---|
| policy | 4 | 100% | 75% | - | 100% | 113 |
| email | 4 | 100% | 100% | 100% | 100% | 99 |
| out_of_scope | 3 | 100% | - | 100% | - | 16 |
| schedule | 4 | 100% | 100% | - | 100% | 38 |
| ALL | 15 | 100% | 91% | 100% | 100% | 70 |

## Per question (pass pattern across runs, mean seconds, agents of last run)

| id | pass pattern | text identical across runs | mean s | agents |
|---|---|---|---|---|
| P01 | 1 | yes | 173 | helpdesk_orchestrator > policy_agent |
| E01 | 1 | yes | 156 | helpdesk_orchestrator > email_agent |
| O01 | 1 | yes | 16 | helpdesk_orchestrator |
| P02 | 1 | yes | 97 | helpdesk_orchestrator > policy_agent |
| S02 | 1 | yes | 36 | helpdesk_orchestrator > schedule_agent |
| E02 | 1 | yes | 108 | helpdesk_orchestrator > email_agent |
| O02 | 1 | yes | 16 | helpdesk_orchestrator |
| P03 | 1 | yes | 95 | helpdesk_orchestrator > policy_agent |
| S03 | 1 | yes | 46 | helpdesk_orchestrator > schedule_agent |
| E03 | 1 | yes | 82 | helpdesk_orchestrator > email_agent |
| O03 | 1 | yes | 15 | helpdesk_orchestrator |
| P04 | 1 | yes | 85 | helpdesk_orchestrator > policy_agent |
| S04 | 1 | yes | 38 | helpdesk_orchestrator > schedule_agent |
| E04 | 1 | yes | 50 | helpdesk_orchestrator > email_agent |
| S01 | 1 | yes | 32 | helpdesk_orchestrator > schedule_agent |

Refusals the agent did not log itself (logged by the runtime guardrail): 0

## Questions whose answers changed across runs

- none