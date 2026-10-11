# Decision Engine: Detailed End-to-End Walkthrough

## 1. Product goal

Transform heterogeneous analytical PDF reports into reliable **evidence -> calculation -> interpretation -> decision question** chains. A heading like “Party Vote Share” is not an insight; a comparable numerical gap with source pages and cautions is.

## 2. Why the earlier version failed

The initial demo matched fixed patterns like `Revenue 2025: ...`, so a 39-page survey PDF resulted in hundreds of extracted lines yet zero KPIs. The new engine treats tables as data and supports optional multimodal understanding.

## 3. Environment and repository

Python 3.11+, PyMuPDF, Pydantic, LangGraph, Streamlit, pandas, openpyxl; OpenAI only for image understanding and explanation. The CLI command `python -m pytest -v` tests both old and new code. The new entry point is `decision_app.py`.

## 4. Intake and page processing

The upload becomes a temporary PDF. `table_facts()` opens it with PyMuPDF, inspects pages, detects tables with `page.find_tables()` and reads text. It does not send document bytes off the machine in offline mode. Image mode renders each selected page as a PNG for multimodal analysis; that image **is transmitted to the API**.

## 5. Table parsing and evidence provenance

`ExtractedFact` carries `page`, `topic`, `row`, `column`, `value`, `unit`, `evidence`, `evidence_type` and `confidence`. These fields ensure auditability. The parser detects mostly numeric columns and attaches textual row names. Complex merged headers are conservatively marked low confidence rather than silently assigned to the wrong metrics.

## 6. Typed structured output

Pydantic defines the page-level fact schema `PageFacts` and synthesis schema `SynthesizedNotes`. The API requests parsed objects, not loose paragraphs. The system rejects model facts without populated identifiers or page references; image-only claims are flagged for review rather than accepted as audited numbers.

## 7. Graph orchestration

LangGraph routes:

`START -> ingest -> (vision | audit) -> audit -> (synthesis | final) -> END`.

`ingest` extracts tables, `vision` supplements the source where requested, `audit` computes deterministic comparisons, `synthesis` creates source-referenced decision questions, `final` builds an exportable report. Conditional edges allow the free offline path to skip all API calls.

## 8. Deterministic mathematical reasoning

`compare_facts()` groups facts by **identical table and column**, or by **identical table and row**, with identical units. It calculates extrema within each homogeneous group as a concise first-pass comparison. For percentages, the appropriate difference is percentage points:

`44.0% - 36.7% = 7.3 percentage points`.

For comparable non-percentage measurements with positive baseline:

`(new - old) / old × 100`.

The calculator does not divide by zero and does not infer that correlation establishes causation. A sample-count column can be compared descriptively, but should not be mistaken for outcomes. Extremes within categories do not imply significance or the best decision.

## 9. Multimodal understanding

For OpenAI mode, the pipeline renders all selected pages (or the configured capped subset). The model receives the page image together with extracted text, making complex charts and tables more interpretable. Vision-derived facts can be wrong: keep their review flags and verify original table labels and units. The model is told not to guess unreadable axes or missing values.

## 10. Cross-page reasoning boundaries

The current release performs reliable *within-table* comparisons and sends a balanced sample of facts from across pages to the executive synthesis. It does **not** yet prove mathematically audited cross-page comparisons when populations/periods/normalizations differ. Cross-page reasoning should remain tentative unless the same metric identifier and comparable cohort definitions are verified. This distinction is deliberate.

## 11. Decision synthesis

The model receives source fact IDs and deterministic calculation objects. It drafts: `finding`, `implication`, `suggested_next_step`, `caveat`, `priority`. Numeric analysis is computed in Python first. The model is required to avoid novel figures, causal claims, and fake benchmarks. Notes lacking valid fact IDs are dropped. This is traceability validation, not comprehensive semantic truth checking.

## 12. Neutrality and privacy

For political surveys, insights remain neutral and methodological—no audience targeting, persuasive messages or election manipulation tactics. For sensitive business reports, use offline mode or confirm contractual authorization and API data-handling rules before sending page images. Uploaded PDFs are not included in this GitHub repository.

## 13. Quality Assurance

Run `python -m pytest -v`. Tests cover percentage-point arithmetic, numeric parsing, header ambiguity, evidence schema and prior-regression tests. Because PDF templates vary, also create manual gold annotations for real pages and evaluate extraction precision/recall and citation correctness. Examine 0% and 100%, merged headers, duplicate row names, negative measurements, and multi-page tables.

## 14. Exports

The UI exports a structured JSON report for programmatic reuse, a Markdown executive brief, and an Excel workbook containing factual cells, arithmetic comparisons, decision notes and review flags. Keep the original source PDF separately for verification.

## 15. Operational workflow

Open VS Code -> install dependencies -> run tests -> launch `decision_app.py` -> upload a report -> select two representative pages -> inspect extracted labels -> verify source figures -> optionally activate API mode -> review decision synthesis -> download workbook -> document data quality.

## 16. Cost and deployment

Offline requires no model API budget. AI mode has variable per-page image and token costs; begin with 2 pages and only increase after validating quality. Production enhancements would include a persistent job queue, file-level SHA-256 caches, rate limiting, encrypted artifacts, sensitive-data redaction, manual approval records and cost dashboards.

## 17. Interview explanation

Describe the problem: prior extractor provided 256 line observations but zero useful insights. Explain the architectural shift to structured facts and provenance, deterministic numeric operators, conditional LangGraph branches and guarded executive synthesis. Show numerical calculations, review flags, and source evidence. **Avoid calling the project autonomous or claiming accuracy results that have not been benchmarked**.

## 18. Honest roadmap

Priority 1: robust multi-level table header reconstruction; Priority 2: image-text agreement verification and chart-point extraction; Priority 3: cross-page semantic metric linking and contradiction detection; Priority 4: expert annotations + statistically valid uncertainty; Priority 5: explicit human review/approval UI; Priority 6: persistence, observability, and cost testing. These items are not claimed as implemented.

## V3.1 paragraph brief

The synthesis call now asks for `BriefParagraph` objects in addition to evidence-linked `DecisionNote` objects. Each paragraph condenses related evidence into a short section and keeps source fact IDs and page references. `validate_brief_paragraphs()` checks the IDs, page set, and length before display. The graph passes the output through `synthesis` → `final`; the Streamlit Executive tab renders these paragraphs first and hides verbose notes inside an expander. Exports include them in JSON and Markdown. The guardrails in `compare_facts()` avoid meaningless `Total`/`Subtotal` versus individual category rankings and sample-bucket comparisons. Because citing correct fact IDs does not guarantee a semantically correct interpretation, analyst QA remains necessary.
