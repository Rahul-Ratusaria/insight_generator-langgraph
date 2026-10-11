# Evaluation Plan — InsightForge v2

## Claims that can be demonstrated

- The bundled sample exposes typed reported metrics and deterministic annual revenue and two-region comparisons.
- Source quotes, page references and calculation strings appear alongside every derived finding.
- A blank page is routed to review; ungrounded numeric statements are rejected by the basic validator.
- SQLite caching skips completed page graph work on identical PDF bytes, provider, model and page range.
- The codebase contains unit tests and a GitHub Actions test workflow.

## What has not been benchmarked

No external benchmark of accuracy, cost, performance, or long-running reliability has been performed. No OCR, arbitrary chart parsing, semantic verification or production security claim should be made. OpenAI results and price depend on selected model and API conditions.

## Suggested held-out benchmark

Curate 50-100 PDF pages stratified by text, true tables, chart-only, scanned, misleading captions, duplicate KPIs and missing units. Human label each reported metric, canonical entity, period, value, unit, and exact citation. Record: extraction precision/recall, arithmetic accuracy, evidence exact-match rate, unsupported-claim acceptance rate, review precision/recall, mean runtime/page, and model input/output tokens. Set clear thresholds before claiming production readiness.

## Audit risks

1. Regex matches can be correct syntactically but wrong semantically if report scope differs.
2. Page-level quote existence does not ensure the conclusion is true.
3. Two revenue lines may have different units, currencies or definitions; formula output carries explicit caveats.
4. The sample is synthetic; successful tests on it do not establish generalized performance.
5. Ambiguous duplicate metric keys are dropped rather than reconciled.
