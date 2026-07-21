# Functional Requirements

| ID | Requirement | Implementation |
|---|---|---|
| FR-01 | Accept pasted, TXT, and DOCX inquiries | Streamlit input and document reader |
| FR-02 | Extract the PRD inquiry schema | Rule parser or optional LLM, then Pydantic |
| FR-03 | Report missing category-specific fields | Completeness checker |
| FR-04 | Score customer credibility and flag explicit risks | Customer checker and simulated CRM |
| FR-05 | Return top three catalog candidates | SQLite product service and weighted matcher |
| FR-06 | Classify four match types | Matching decision rules |
| FR-07 | Calculate the six-dimension score | Lead scorer |
| FR-08 | Route to one of four follow-up strategies | Strategy selector |
| FR-09 | Generate a guarded English draft | Deterministic template or optional LLM |
| FR-10 | Save and filter CRM records | SQLite CRM writer and UI |
| FR-11 | Evaluate 25 labeled cases | Evaluation service and page |

## Non-functional Requirements

- Local rules-only mode must work without external services.
- Decisions must expose scores, reasons, gaps, and tool status.
- Invalid or empty input must fail clearly.
- Secrets must remain outside version control.
- The UI must stay usable on desktop and mobile widths supported by Streamlit.
- The system must not make final commercial or compliance commitments.

