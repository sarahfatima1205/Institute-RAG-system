# Evaluation results (partial run)

Core prompt set: 30 prompts (13 policy, 6 time-table, 4 e-mail, 7 out-of-scope). Within the available time
each configuration answered the prompts listed below once (run 1 of the planned 3), in category-interleaved
order so that every category is sampled. Intervals are 95% Wilson score intervals; with these sample sizes
they are wide and differences between configurations are indicative, not statistically established.

| configuration | answered | accuracy | groundedness | correct refusal | routing | mean s/answer | est. full-set accuracy* |
|---|---|---|---|---|---|---|---|
| Multi-agent, Qwen3-8B | 15/30 | 15/15 (100%) | 10/11 (91%) | 4/4 (100%) | 11/11 (100%) | 70 | 100% |
| Single agent, Llama-3.1-8B | 15/30 | 13/15 (87%) | 4/11 (36%) | 4/4 (100%) | - | 64 | 86% |

\* Extrapolation: per-category accuracy weighted by each category's share of the 30 core prompts
(categories covered: Multi-agent, Qwen3-8B: policy, schedule, email, out_of_scope; Single agent, Llama-3.1-8B: policy, schedule, email, out_of_scope).

## Accuracy by category

| category | prompts | Multi-agent, Qwen3-8B | Single agent, Llama-3.1-8B |
|---|---|---|---|
| policy | 13 | 4/4 (100%, CI 51%-100%) | 3/4 (75%, CI 30%-95%) |
| schedule | 6 | 4/4 (100%, CI 51%-100%) | 4/4 (100%, CI 51%-100%) |
| email | 4 | 4/4 (100%, CI 51%-100%) | 3/4 (75%, CI 30%-95%) |
| out_of_scope | 7 | 3/3 (100%, CI 44%-100%) | 3/3 (100%, CI 44%-100%) |

## Projected time for the full evaluation (from measured seconds per answer)

| configuration | core 30 x 3 runs | extra 43 x 1 run |
|---|---|---|
| Multi-agent, Qwen3-8B | ~1.8 h | ~0.8 h |
| Single agent, Llama-3.1-8B | ~1.8 h | ~0.8 h |

## Failed answers (for error analysis)

**Multi-agent, Qwen3-8B**: none

**Single agent, Llama-3.1-8B**: P02, E02
- P02 (tools: search_policy_documents): To get a B.Tech. degree, you need to earn at least 180 credits. The distribution of these credits is given in Table 4 of the B.Tech. regulations 2018.   According to Table 4, the minimum credits to be earned in each category are as follows:  * Program: 32 credits * Core/Compulsory: 28 credits * Elec
- E02 (tools: draft_email): To: instructor.beta@example.iitj.test Subject: Request for permission to take a make-up examination – CSL7570  Dear Dr. Instructor Beta,  I missed the Minor 1 of CSL7570 (Advanced Topics in Machine Learning) due to genuine reasons. hospitalised   As per the Academic Regulations (Make-up Examinations

## Figures

- `plots/fig1_accuracy_by_category.png`
- `plots/fig2_overall_metrics.png`
- `plots/fig3_latency_by_category.png`
- `plots/fig4_per_prompt.png`