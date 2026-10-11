from pathlib import Path
import hashlib
import os
from .pdf import inspect_pdf, pdf_fingerprint
from .graph import build_graph
from .models import JobOutput, PageResult
from .storage import Store
from .analytics import extract_metrics, calculate_insights


def job_key(path: Path, provider: str, model: str, start: int, end: int | None) -> str:
    # Settings are part of identity; changing them generates a new job.
    key = f"{pdf_fingerprint(path)}|{provider}|{model}|{start}|{end}"
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def run_job(pdf_path: str | Path, provider: str = "demo", model: str | None = None,
            start: int = 1, end: int | None = None, data_dir: str | Path | None = None,
            force: bool = False) -> JobOutput:
    if provider not in {"demo", "openai"}:
        raise ValueError("provider must be demo or openai")
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY required for openai provider")
    path = Path(pdf_path).resolve()
    model = model or os.getenv("INSIGHT_MODEL", "gpt-4o-mini")
    directory = Path(data_dir or os.getenv("INSIGHT_DATA_DIR", "data"))
    pages = inspect_pdf(path, start=start, end=end)
    key = job_key(path, provider, model, start, end)
    store = Store(directory / "insights.sqlite")
    try:
        store.register(key, path.name, provider, model)
        graph = build_graph()
        for page in pages:
            saved = store.get(key, page.number)
            if saved is not None and not force:
                continue
            try:
                state = graph.invoke({"page": page.number, "text": page.text, "page_type": page.page_type,
                                      "provider": provider, "model": model, "pdf_path": str(path)})
                result = PageResult.model_validate(state["result"])
            except Exception as exc:
                # Do not persist exceptions as terminal pages: retry on next invocation.
                raise RuntimeError(f"Page {page.number} processing failed; rerun to resume: {exc}") from exc
            store.save(key, result)
        results = [store.get(key, p.number) for p in pages]
        results = [p for p in results if p is not None]
        review = [p.page for p in results if p.status != "accepted"]
        text_by_page = {p.number: p.text for p in pages}
        metrics = extract_metrics(results, text_by_page)
        analytic = calculate_insights(metrics, text_by_page)
        highlights = [f"{i.title}: {i.observation}" for i in analytic]
        lines = [f"Page {p.page}: {i.observation}" for p in results if p.status == "accepted" for i in p.insights]
        summary = "Calculated insights (audited operands):\n" + ("\n".join(highlights) if highlights else "No comparable metric pairs found.")
        summary += "\n\nVerified reported observations:\n" + ("\n".join(lines[:12]) if lines else "No accepted page observations.")
        if review:
            summary += "\nPages requiring review: " + ", ".join(map(str, review))
        return JobOutput(job_id=key, file_name=path.name, provider=provider, model=model,
                         pages=results, executive_summary=summary, review_pages=review,
                         metrics=metrics, analytical_insights=analytic)
    finally:
        store.close()
