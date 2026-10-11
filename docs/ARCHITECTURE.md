# Technical Architecture and Design Decisions

## Problem statement

A team analyzes multiple-page business intelligence and survey PDFs. Manually reviewing each page, extracting numerical evidence, converting observations into stakeholder implications, and creating consistent executive summaries is time-consuming. Build a local-first, evidence-first, modular LangGraph application that saves per-page results and exports validated narratives.

## Requirements mapping

| Requirement | Implementation | Caveat |
|---|---|---|
| Multi-page PDF | `fitz.open` plus page loop | No OCR for scans |
| Page-independent insights | `run_job` invokes graph separately for each page | Sequential v1 |
| Page classification | `inspect_pdf` heuristics, text/drawings | Heuristic, not trained |
| Source-grounded observations | structured provider outputs + `Evidence.quote` | Exact-text citation only |
| Validation/review | `validate_insights` / `finalize` | No entailment verifier |
| Resume/idempotence | deterministic job hash + SQLite `(job_id,page)` PK | Cache whole page result; not interrupted in-node replay |
| Checkpointable architecture | LangGraph StateGraph | SQLite stores completed pages; graph-level checkpointing optional |
| Local database ₹0 | SQLite | Single-machine, single-user |
| Executive summary | deterministic accepted-insight digest | Not generative cross-page reasoning |
| PDF vision | conditional image on visual pages via OpenAI | Image-only insights not verified/accepted |
| Cost control | demo mode; text truncation; selective images | Token metrics, no automated budgeting |
| Downloads | `export.py` JSON/Excel/Markdown | No PPT/email generation |

## Node state

`PageState` contains page number, text, classification, provider/model, path, raw proposed insight dictionaries, token counts, validated insight dictionaries, rejection issues, and finalized page result. No image byte arrays are stored in graph state; image input is created on demand by the provider.

## Pipeline

1. PDF and configuration are fingerprinted.
2. Each selected page is parsed independently.
3. SQLite is checked for a previously completed page.
4. `generate_insights` calls the offline adapter or typed Responses API.
5. `validate_evidence` checks same-page exact citations and numerical tokens.
6. `finalize_page` marks accepted or review, retaining only validated insights.
7. Page result is committed synchronously to SQLite.
8. Accepted observations become a cross-page digest and are exported.

## Why separate deterministic and LLM work?

Language models are useful for explaining business context, but poor as unverified calculators. This implementation asks for quotation-backed observations, then independently checks quotes. The next version should parse numeric measures deterministically and calculate growth/changes using Pandas, only then letting an LLM narrate the result with explicit operand references.

## Persistence and failure

`jobs` stores the fingerprint plus metadata; `pages` stores one serialized Pydantic output per page. SQLite transaction and primary key make writes atomic and overwrite-safe. If processing page N throws, completed pages 1..N-1 survive. Rerunning with the same PDF/configuration skips those pages. `--force` bypasses the skip. **Limitation:** `end=None` and `end=<last page>` yield different job keys even with identical page range.

## Failure policy

- Missing extraction: review, not fabricated insight.
- Mismatched quote or wrong page: reject the specific insight.
- Numeric mismatch: reject the specific insight.
- Unsupported model/network error: raise with page number; rerun resumes committed pages.
- Empty insights: page flagged.
- Partial page with both valid and invalid proposals: valid proposals retained, page flagged.

## Risks and next milestones

1. Add evidence span offsets and citation highlighting.
2. Add robust table extraction with column headers, unit labels, comparator selection and deterministic calculations.
3. Add a separate claim-entailment/evaluation graph and analyst approve/edit/decline actions.
4. Add a bounded conditional retry edge for rejected outputs with a maximum of one retry.
5. Add job-level reports of actual wall-clock duration, prices configured externally and human evaluation.
6. If multi-user deployment is needed, introduce auth, tenant filters, secure object storage and a production checkpointer.
