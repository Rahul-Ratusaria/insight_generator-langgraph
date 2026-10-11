# InsightForge v2 — Complete End-to-End Technical Walkthrough

This guide follows one sample upload from PDF bytes to a reviewed business insight. It is intended both as learning material and an interview explanation. Read the source modules alongside each section.

## 1. Problem and scope

Business PDFs contain numbers spread across sections, pages, tables, and diagrams. Extracting a figure is not the same as explaining it. The objective is to obtain **reproducible, bounded analysis**, with exact traceability to reported evidence, avoiding fabricated figures or fabricated business context.

A 2025 revenue of 1,200,000 and 2026 revenue of 1,440,000 supports a 20% growth calculation. It does not establish *why* revenue grew or whether profitability improved. The system separates the verified observation, the computed arithmetic, the proposed question to investigate, and assumptions.

## 2. User journey

Start Streamlit, upload the sample PDF, choose demo mode, select pages, click Analyze report. The app creates a temporary local PDF, passes it to `run_job`, receives structured `JobOutput`, and visualizes calculated insights, metrics, evidence audit and downloads. A `finally` clause deletes the temporary upload after processing. All persisted records refer to content hash/job ID, not a persistent user PDF copy.

## 3. Environment and dependencies

`pyproject.toml` defines a Python package under `src/`, with LangGraph, Pydantic, PyMuPDF, Streamlit, pandas and Excel writer dependencies. Python's isolated `.venv` is used to avoid package conflicts. The app is started with `.venv\Scripts\python.exe -m streamlit run app.py` on Windows. The optional OpenAI SDK is used only when OpenAI mode is selected, with an API key exposed as an environment variable.

## 4. PDF ingestion (`pdf.py`)

`inspect_pdf(path, start, end)` opens the document with PyMuPDF, rejects unreadable/encrypted PDFs, iterates the requested pages, extracts human-readable text, and classifies pages heuristically. `PageData` holds `number`, `text`, `page_type`, and `has_images`. The classifier is heuristic; it is not a document-layout-trained model. `page_png_data_url` can rasterize a page for optional OpenAI vision input. `pdf_fingerprint` hashes the file bytes with SHA-256.

## 5. Job identity and caching (`service.py`, `storage.py`)

`job_key` hashes the PDF fingerprint together with provider, model, and page range; thus equivalent inputs share one persistent run identifier. SQLite stores a `jobs` row and one serialized Pydantic `PageResult` per page, keyed by `(job_id,page)`. On repeat runs, previously saved pages are loaded and graph execution is skipped unless `force=True`. Partial progress can be resumed after a later run. This cache is separate from LangGraph's optional internal checkpointer: the version here uses application-level SQLite caching.

For a clean test after replacing source code, use **Reprocess cached pages** because previously saved page payloads reflect the old generation rules.

## 6. LangGraph state (`graph.py`)

The per-page `PageState` TypedDict carries source page text, page number, provider, model, intermediate insights, token usage, evidence validation results, and final page payload. Nodes receive state and return partial dictionaries, which LangGraph merges into state. The compiled graph is deterministic in its routing rules.

## 7. Graph node 1: generate

`generate` chooses `demo_insights` for free, literal observation extraction, or `openai_insights` for structured model generation. Demo takes numeric source lines verbatim and stores the exact same lines as `Evidence.quote`. It deliberately does not claim to infer causes. OpenAI uses `responses.parse` and the Pydantic `PageLLMOutput` schema, with a constrained system instruction to quote exact source text, avoid unsupported numbers, and abstain on image-only pages.

## 8. Graph node 2: validate

`validate` calls `validate_insights`. The validator checks (a) evidence was supplied; (b) cited page matches the processed page; (c) quote exists in normalized extracted text; and (d) numerical literals in the observation appear in its cited quotes. It rejects unsupported page observations. This validation is primarily **syntactic/evidence-presence verification**; it does not prove the semantic interpretation is correct. An empty or image-only page receives a review issue.

## 9. Conditional review routing

After validation, `route_after_validation` returns `accepted` or `review`. Accepted flows directly to `finalize_page`; review flows via `flag_for_review` to `finalize_page`. This exhibits an actual LangGraph conditional edge rather than a purely linear sequence. Review is a status for manual inspection, not an implemented human-in-the-loop UI approval system.

## 10. Persistence of page results

`finalize` writes a `PageResult` with accepted observations, issues, page type, source length and usage metrics. `service.py` stores that payload in SQLite. Exceptions are raised with the offending page number and are not saved as successful terminal pages, letting a subsequent run retry processing.

## 11. Typed KPI extraction (`analytics.py`)

After all selected pages have been loaded from SQLite, `extract_metrics` iterates **accepted pages only**. Narrow, fully anchored regex patterns identify known forms such as `Revenue 2025: 1,200,000` and `North region revenue: 500,000`. Each `Metric` stores a stable key, label, numeric value, unit, page number, and original verbatim line. Unsupported rows remain as observations or are skipped—no implied number conversion, currency, year, or target is guessed.

Example: `Revenue 2025: 1,200,000` becomes `Metric(key='revenue_2025', value=1200000, page=1, quote='Revenue 2025: 1,200,000')`.

## 12. Deterministic comparisons

`calculate_insights` builds a mapping from metric keys to the unique matching metric. If the same metric key occurs more than once, it is removed from eligible comparisons (ambiguous source scope). For two consecutive revenue years with earlier value > 0, the computation is:

`growth_percentage = ((new_revenue - old_revenue) / old_revenue) * 100`

Sample: `((1,440,000 - 1,200,000) / 1,200,000) * 100 = +20.0%` and absolute difference = `240,000`.

For exactly two distinct region revenue metrics and a positive lower revenue, the comparison is:

`regional_gap_percentage = ((higher_revenue - lower_revenue) / lower_revenue) * 100`

Sample: `((700,000 - 500,000) / 500,000) * 100 = 40.0%`. We do not call this a market share or assert that regions comprise the complete business.

## 13. Provenance validation for calculated results

`validate_derived` checks that each finding references exactly two metric keys and exactly two `Evidence` objects, and each evidence quote matches the identified metric and is present on the specified PDF page. Arithmetic is computed from the trusted typed operands rather than inferred from text generated by a model. These are computationally grounded findings but still rely on an assumption of metric comparability.

## 14. Business implication construction

Implications are framed as possible investigative actions: examine demand, distribution, pricing, or drivers; they are not diagnoses. The output includes a confidence, caveat and quoted inputs. A retention value of 72% alone cannot be labeled underperformance without a prior baseline or target. This restraint is important for reliable business intelligence.

## 15. Executive summary construction

`run_job` builds two sections: calculated auditable insights first, and literal verified page observations second. It appends page numbers flagged for review. There is no hidden language-model synthesizer in demo mode; the summary is reproducible from the data.

## 16. Streamlit UX (`app.py`)

Sidebar settings choose the provider, model, page range, and force reprocessing. The main workflow presents four tabs: Executive intelligence (calculated findings, formulas, line citations, assumptions); Metrics explorer (metric table and a revenue bar chart); Evidence & QA (verified page observations and review issues); Export (JSON, Markdown, Excel). No credentials appear in app output.

## 17. Reports (`export.py`)

JSON serializes `JobOutput` losslessly; Markdown embeds analytical insights and their formulas, followed by detailed page evidence; Excel has `Insights`, `Page QA`, `Metrics`, and `Calculated Insights` worksheets. Quotes are intentionally retained in exports for human audits. Excel is a report, not a live connection to SQLite.

## 18. Automated verification and CI

`test_validation.py` verifies evidence rejection. `test_analytics.py` covers +20% year-over-year change, +40% interregional difference across two pages, zero denominators, duplicated metrics, unknown patterns, and reviewed pages. `test_end_to_end.py` checks PDF processing, repeat-run cache, blank-page review, a derived insight, and export worksheets. `.github/workflows/test.yml` runs tests on GitHub when the repo is published.

## 19. Known limitations and production hardening

**Current limitations:** no OCR on scanned PDFs; no reliable parsing of arbitrary table layouts or charts; no semantic NLI verifier; no dedicated human approval control; simple key-pattern recognition; no currency/period normalization; no table provenance bounding boxes; no authentication or per-user isolation; no capacity benchmarking; third-party API charges if enabled. Also, 'accepted' means the current source guard passed, not that a business statement is perfectly true.

**Next engineering steps:** introduce layout-based extraction and OCR; explicit metric ontology and unit normalization; strict prompt-independent math checks; active human decisions in UI; duplicate reconciliation; quality-labeled evaluation dataset; safe multi-user data storage; OpenTelemetry monitoring, quotas and deployment security.

## 20. Frequently asked interview questions

**Why LangGraph rather than a single function?** The flow has an explicit typed state, distinct generation and validation stages, and conditional review routing. For this small prototype, LangGraph adds modest orchestration value rather than magical reasoning; it becomes more valuable as retries, reviewer approvals, and specialized models are introduced.

**Why does the free mode calculate insights better than the LLM?** Arithmetic is computed from typed source numbers by deterministic Python functions. This prevents an LLM from introducing an unsupported percentage or making different calculations on repeat requests.

**Can the system hallucinate?** A model-generated implication can still be wrong or misleading; regex parsing can also misinterpret context. We mitigate risk through quote checks, conservative patterns and caveats, but do not claim zero hallucinations.

**Why SQLite?** Zero-license-cost storage for local persistence and interrupted-run reuse. A multi-user production service would likely use a concurrency-safe server database with access control and monitoring.

**How would you measure quality?** Create human-annotated PDFs and measure extraction precision/recall, numerical accuracy, provenance accuracy, review false negatives, time per page, and API spend per page. Also include image-heavy, duplicated, ambiguous, poorly scanned, and adversarially formatted reports.

**Where is the actual agent?** The graph has generation, evidence checking and conditional review nodes. It is a controlled workflow rather than a genuinely autonomous multi-agent system. Claiming multi-agent autonomy would misstate what this repository implements.

## 21. Exact reproducible Windows workflow

```powershell
# From repo root
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts\make_sample.py
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```

If the application was running before files were replaced, stop and restart it. Tick **Reprocess cached pages** once to refresh old observations.

## 22. Portfolio demo script (~3 minutes)

1. Explain source quality risk in financial and operational PDFs (20 s).
2. Upload sample, select offline mode, run analysis (30 s).
3. Present 20% revenue growth and 40% regional gap, show formulas and page evidence (50 s).
4. Show that retention is *not* judged without a benchmark (20 s).
5. Demonstrate Evidence & QA and a scanned/blank page review (35 s).
6. Export JSON/Excel, demonstrate cache and mention tests and limits (25 s).
