import re
from pathlib import Path
from .models import PageLLMOutput, Insight, Evidence
from .pdf import page_png_data_url

SYSTEM_PROMPT = """You are a conservative business research analyst. Use ONLY the supplied page.
Return at most 4 insights. Each observation should be a factual claim supported by an EXACT
contiguous quote copied from the PAGE TEXT. The quote must contain EVERY number appearing
in the observation; never compute, estimate or invent a number. Cite the supplied 1-indexed
page number. In the implication, say 'may' when discussing possible effects; never claim
causation without direct evidence. If evidence is insufficient, return no insights.
If the image has information absent from page text, do not claim it as verified evidence.
For scanned or image-only pages, return no insights, and flag for manual review."""


def demo_insights(text: str, page: int) -> PageLLMOutput:
    """Offline source-grounded observations. Derived calculations live in analytics.py."""
    lines = [" ".join(line.split()) for line in text.splitlines()]
    lines = [line for line in lines if 5 <= len(line) <= 230 and re.search(r"\d", line)]
    return PageLLMOutput(insights=[Insight(
        observation=line,
        implication="Reported metric; assess against comparable periods, regions or established targets.",
        confidence="high", evidence=[Evidence(quote=line, page=page)]) for line in lines[:12]])


def openai_insights(text: str, page: int, model: str, pdf_path: Path | None, include_vision: bool):
    from openai import OpenAI
    client = OpenAI()
    content = [{"type": "input_text", "text": f"PAGE NUMBER: {page}\nPAGE TEXT:\n{text[:18000]}"}]
    if include_vision and pdf_path:
        content.append({"type": "input_image", "image_url": page_png_data_url(pdf_path, page)})
    response = client.responses.parse(model=model, instructions=SYSTEM_PROMPT,
        input=[{"role": "user", "content": content}], text_format=PageLLMOutput)
    if response.output_parsed is None:
        raise RuntimeError("Model did not return structured insights")
    usage = response.usage
    return response.output_parsed, int(usage.input_tokens if usage else 0), int(usage.output_tokens if usage else 0)
