# Complete Project Walkthrough — From Zero to Working PDF Insight Generator

## 1. Goal and the user journey

Imagine a survey analytics team receiving 60 multi-page PDF reports per month. Each report contains charts, counts, percentages, geographic breakdowns, tables and executive summary pages. An analyst normally reads each page, records important numbers, verifies the sources, synthesizes implications and shares a report. This project automates the **first draft of evidence collection and narration**, without pretending that models can replace verification.

User journey: open Streamlit → upload PDF → select demo/OpenAI → choose optional page range → run → inspect accepted observations and flagged pages → download JSON, Markdown or Excel. An analyst must review flagged pages before using the deliverable externally.

## 2. Terms you need to understand

**PDF parser:** PyMuPDF opens a PDF and retrieves its digital text. PDF extraction is not the same as OCR. Scanned pages can have no text even when words are visible to a person.

**State machine / LangGraph:** An explicit graph of processing steps. Nodes are Python functions; edges define order; state is the shared typed dictionary. Here graph control is deterministic, not an autonomous tool-using agent.

**LLM structured output:** OpenAI returns a response conforming to Pydantic's `PageLLMOutput` model rather than unstructured paragraphs. This reduces formatting failures but does not guarantee factual truth.

**Evidence grounding:** Each claim must point to an exact extractable quote on the current page, making audit possible.

**Idempotence:** Repeated identical jobs can reuse committed page results and avoid duplicate API calls.

**Checkpoint vs cache:** LangGraph checkpointers can persist in-graph state between nodes. This implementation instead caches completed page results in application SQLite. Those are *not equivalent*; a crash in the middle of one page will rerun that page.

## 3. Prerequisites and dependencies

Use Python 3.11 or 3.12. Install `pyproject.toml` dependencies using `pip install -e ".[dev]"`. `langgraph` constructs workflows; `openai` optionally generates insights; `pydantic` enforces schemas; `pymupdf` extracts the PDF; `streamlit` provides UI; `pandas`/`openpyxl` export Excel; SQLite is part of Python's standard library. `pytest` executes tests.

## 4. What happens before the graph?

`run_job` in `service.py` receives a filename, provider, model, page range and optional force flag. It verifies the selected provider and checks the API key only for OpenAI mode. Next `inspect_pdf` opens the PDF, validates page ranges and extracts sorted text page-by-page.

For each page, it derives a coarse page type: text containing common numeric terms such as “revenue,” “percent,” or “total” is marked table-like; pages with drawings/images and little text are visual; otherwise generic. This heuristic is intentionally basic and should not be confused with a reliable ML classifier.

## 5. Unique job identity

`pdf_fingerprint` reads the PDF bytes incrementally and computes SHA-256. The service then hashes the PDF digest together with provider, model, first and last page. This produces a deterministic 24-character job ID. The same PDF/settings produce the same cache identity; changed settings create another job. File name itself is not part of the digest.

## 6. Database initialization

`Store` creates the data directory and opens `insights.sqlite`. Table `jobs` tracks job configuration. Table `pages` uses `(job_id, page)` as a composite primary key and stores serialized JSON page records. The page key avoids mixing pages from two different PDFs and allows safe, atomic replacement when `--force` is used.

## 7. Graph structure in detail

```mermaid
flowchart LR
  A([START]) --> B[generate_insights]
  B --> C[validate_evidence]
  C --> D[finalize_page]
  D --> E([END])
```

**Node 1 — `generate_insights`:** Receives source text, page index, mode, model and path. Demo mode uses only lines containing reported numbers. It builds cautious, literal observations from those lines; confidence is low. OpenAI mode calls `client.responses.parse` with a Pydantic response schema. Its prompt asks for no more than four insights, exact evidence quotes, noncausal implications, and no invented calculations. The model may additionally receive a rendered page image when the page is classified as visual. Token usage is recorded if the API returns it.

**Node 2 — `validate_evidence`:** Reconstructs Insight objects, checks each citation points to the current page, confirms its quote exists in the normalized extracted text, and compares every numeral in the observation against numerals in the cited quotes. Unsupported proposals are removed and an issue is logged. Blank pages and empty outputs are explicitly flagged.

**Node 3 — `finalize_page`:** Builds a Pydantic `PageResult` with accepted insights, issues, page type, source character count and token counters. A page is `accepted` only if no issues exist; otherwise it becomes `review`.

## 8. How an example travels through the system

Take the line `Revenue 2026: 1,440,000` on page 1. The demo adapter can propose the same exact line as its observation and evidence quote. Validation normalizes whitespace and capitalization, finds the same passage in the page text, checks the page number and sees that the numeric tokens match. The resulting observation is retained and the page may be accepted. If the model instead says `Revenue 2026: 1,900,000` but only cites `Revenue 2026: 1,440,000`, the new number is absent from the evidence and the proposed observation is rejected.

Crucially, **“revenue grew 20%” is not independently calculated by this version**. Even if such a computed claim would be mathematically correct, it must go through a future table-aware calculation stage rather than be invented by the language model.

## 9. Why review flags matter

Silent omission makes automated analytics dangerous. A report might contain image-only pages, unreadable tables, ambiguous units or invented claims. The project marks questionable pages and does not include unverified observations in the accepted result. The currently shipped UI displays warnings. It does not yet provide an edit/approve workflow: decisions are made by the analyst outside the application.

## 10. Resuming interrupted runs

After each page finishes, it is committed to SQLite immediately. Suppose pages 1–4 complete and the API call for page 5 fails. Pages 1–4 are already stored. Restarting with identical options looks up those cached pages and resumes with page 5. Because this is page-level caching rather than LangGraph checkpoints, a partially completed page is processed again from its first node.

## 11. Aggregation and executive summary

The service assembles accepted page observations in page order, includes at most the first twelve in a deterministic cross-page digest, and appends review-page numbers. This is intentionally *not* an AI-generated cross-page analysis. A later release could find recurring themes, cross-page contradictions and recommendations, but would require stronger reference tracking and evaluation.

## 12. Exports and who uses them

`JobOutput` is the canonical data contract. JSON preserves nested objects for integration with BI pipelines; Markdown produces a stakeholder-friendly readable draft; Excel provides an `Insights` sheet plus a `Page QA` sheet listing review issues and token usage. In production, these outputs should be marked **draft until reviewed**.

## 13. Understanding Streamlit

Streamlit collects the file, mode, model, page range and `force` choice. Uploaded bytes are saved temporarily to a `.pdf` file because PyMuPDF accepts a file path in this implementation. After running, Streamlit deletes that temporary file in `finally`. Session state holds the `JobOutput` so changing download controls does not recompute the results. Streamlit itself has no authentication or job-level user isolation here; keep usage local.

## 14. Cost model and limitations

SQLite, sample generation, parsing, demo observations and exports require no purchased services. OpenAI mode incurs external API charges based on model, tokens and images. The pipeline records returned input/output tokens but does not calculate exact spend (rates change and image/token billing may vary). Its image rendering is selective to reduce unnecessary calls. Large digital documents can still use many billable tokens. The app has no cost/budget UI by design.

## 15. Testing strategy

`test_valid_citation` verifies a supported claim passes. `test_rejects_hallucinated_number` ensures invented numerals are blocked. `test_rejects_nonexistent_quote_and_wrong_page` covers bad references. End-to-end tests create small temporary PDFs, verify the offline graph returns accepted pages, export content and confirm re-running uses stable job identities. A blank page must trigger review. Run `pytest -q` on each code change and see `EVALUATION.md` for a human-grounded benchmark.

## 16. Debugging common issues

**ModuleNotFoundError:** reinstall with the editable install command; do not execute individual package files directly.

**PowerShell Activate.ps1 blocked:** use `.venv\\Scripts\\python.exe` directly, no policy change required.

**API authentication issue:** verify the environment variable in the same terminal as Streamlit. Never put keys in code or Git.

**Page flagged review:** inspect source quality, quote mismatch, scanned pages and new unsupported numerals. This may be expected, not a software failure.

**Wrong cache results after code changes:** cache keys cover file/options, not code version. Use `--force` or clear `data/insights.sqlite` when changing validation logic.

**No chart insights:** figures may not have extractable text. Although vision input may be provided, text-verifiable quotes remain mandatory; manual review or OCR/table extraction is required.

## 17. How to explain it in an interview

> “I built a LangGraph-based PDF analytical insight engine that processes each page independently. PyMuPDF extracts source text; a typed generation node proposes business observations; a deterministic validation node checks each same-page citation and numeral; and a finalization node marks pages for review when evidence is missing. SQLite caches completed pages so reruns avoid repeated API calls. The system supports a free offline mode, optional OpenAI structured generation, and JSON/Excel/Markdown outputs. I explicitly distinguish source-verification from semantic correctness and keep human review in the loop.”

Expect questions on: why LangGraph instead of a `for` loop (separation of typed stages, future branching and checkpoints); how to avoid hallucinations (exact citation checks and review queue); how to compute KPIs (deterministic Python/Pandas, planned); how to handle 500 pages (batching and rate limits, planned); what happens if the API fails (resume at page boundary); and how to measure value (timed benchmarks with analysts, not invented metrics).

## 18. How to extend the project properly

**Phase 2:** Extract tables as structured data with headers and units; compute deterministic differences, growth and rank changes; retain operands and page source locations; add manual approve/reject with comment trail.

**Phase 3:** Introduce LangGraph conditional retry (`validation → repair → validation`, max one retry), `SqliteSaver` or another checkpointer for intra-page continuation, and evaluation datasets with exact expected outputs.

**Phase 4:** Add job/task queue, secure storage, auth, user isolation, monitoring and deployment. Consider Postgres only if multi-user scale demands it, since the target local MVP requires free SQLite.

## 19. End-to-end checklist

1. Install the package and make the sample PDF.
2. Run the demo CLI and open the JSON/Excel/Markdown.
3. Launch Streamlit and compare page-by-page citations to the sample PDF.
4. Run pytest; verify the review flag on a blank page.
5. Configure OpenAI only if needed and only on nonconfidential documents.
6. Read the review warnings instead of treating all output as verified.
7. Measure analyst review time and maintain a benchmark before claiming operational savings.
8. Publish source code and documentation, not API keys or confidential reports.
