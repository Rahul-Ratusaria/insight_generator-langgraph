from io import BytesIO
import pandas as pd
from .models import JobOutput


def to_markdown(job: JobOutput) -> str:
    lines = [f"# Insights: {job.file_name}", "", f"Job: `{job.job_id}` | Provider: {job.provider}", "", "## Executive summary", job.executive_summary, ""]
    lines.extend(["## Calculated business insights", ""])
    for i in job.analytical_insights:
        lines.extend([f"### {i.title}", i.observation, "", f"**Calculation:** {i.calculation}",
                      f"**Action to investigate:** {i.implication}", f"**Caveat:** {i.caveat}"])
        lines.extend(f"- Source p.{e.page}: {e.quote}" for e in i.evidence)
        lines.append("")
    for p in job.pages:
        lines.extend([f"## Page {p.page} — {p.status}", ""])
        for i in p.insights:
            lines.extend([f"- **Observation:** {i.observation}", f"  - **Implication:** {i.implication}", f"  - **Confidence:** {i.confidence}"])
            for e in i.evidence:
                lines.append(f"  - **Evidence (p. {e.page}):** {e.quote}")
        for issue in p.issues:
            lines.append(f"- **Review:** {issue}")
        lines.append("")
    return "\n".join(lines)


def to_excel(job: JobOutput) -> bytes:
    rows = [{"page": p.page, "status": p.status, "observation": i.observation,
             "implication": i.implication, "confidence": i.confidence,
             "citations": " | ".join(f"p.{e.page}: {e.quote}" for e in i.evidence)}
            for p in job.pages for i in p.insights]
    summary = [{"page": p.page, "status": p.status, "insights": len(p.insights),
                "issues": "; ".join(p.issues), "input_tokens": p.tokens_in, "output_tokens": p.tokens_out}
               for p in job.pages]
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(rows, columns=["page", "status", "observation", "implication", "confidence", "citations"]).to_excel(writer, sheet_name="Insights", index=False)
        pd.DataFrame(summary).to_excel(writer, sheet_name="Page QA", index=False)
        pd.DataFrame([m.model_dump() for m in job.metrics], columns=["key", "label", "value", "unit", "page", "quote"]).to_excel(writer, sheet_name="Metrics", index=False)
        pd.DataFrame([{"title": i.title, "observation": i.observation, "implication": i.implication,
                       "formula": i.calculation, "caveat": i.caveat,
                       "sources": " | ".join(f"p.{e.page}: {e.quote}" for e in i.evidence)}
                      for i in job.analytical_insights],
                     columns=["title", "observation", "implication", "formula", "caveat", "sources"]).to_excel(writer, sheet_name="Calculated Insights", index=False)
    return output.getvalue()
