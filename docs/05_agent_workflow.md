# Agent Workflow

The term Agent refers to a stateful, multi-step business workflow that calls bounded tools. It is not an unconstrained autonomous chatbot.

| Step | Tool | Input | Output |
|---|---|---|---|
| 1 | `extract_inquiry_fields` | Raw English inquiry | `InquiryData` |
| 2 | `check_missing_fields` | Validated inquiry | Missing fields and completeness |
| 3 | `check_customer_profile` | Buyer fields | Credibility and risk evidence |
| 4 | `match_product_catalog` | Technical request | Match type and candidates |
| 5 | `calculate_lead_score` | Inquiry, customer, match | Six scores and priority |
| 6 | `select_follow_up_strategy` | Score and gaps | Route, questions, next action |
| 7 | `generate_reply_draft` | Structured decision | Guarded English draft |
| 8 | `save_lead_record` | Reviewed result | CRM lead ID |

CRM saving is intentionally triggered by the user after reviewing the draft. The workflow exposes `tool_status` so the UI and evaluation can distinguish business output from orchestration failure.

