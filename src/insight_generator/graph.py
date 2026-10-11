from pathlib import Path
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from .models import PageResult
from .provider import demo_insights, openai_insights
from .validation import validate_insights

class PageState(TypedDict, total=False):
    page: int
    text: str
    page_type: str
    provider: str
    model: str
    pdf_path: str
    insights: list[dict]
    tokens_in: int
    tokens_out: int
    accepted: list[dict]
    issues: list[str]
    result: dict


def generate(state: PageState) -> dict:
    if state["provider"] == "demo":
        parsed = demo_insights(state["text"], state["page"])
        in_tokens, out_tokens = 0, 0
    else:
        parsed, in_tokens, out_tokens = openai_insights(state["text"], state["page"], state["model"], Path(state["pdf_path"]), state["page_type"] == "visual")
    return {"insights": [i.model_dump() for i in parsed.insights], "tokens_in": in_tokens, "tokens_out": out_tokens}


def validate(state: PageState) -> dict:
    from .models import Insight
    accepted, issues = validate_insights([Insight.model_validate(i) for i in state["insights"]], state["text"], state["page"])
    if not state["text"].strip():
        issues.append("No extractable text: scanned or image-only page requires human review")
    if not state["insights"]:
        issues.append("No source-grounded insights generated")
    return {"accepted": [i.model_dump() for i in accepted], "issues": issues}


def route_after_validation(state: PageState) -> str:
    """Conditional edge preserves an explicit review path for unverified claims."""
    return "review" if state["issues"] else "accepted"


def flag_review(state: PageState) -> dict:
    return {"issues": state["issues"] or ["Manual review required"]}


def finalize(state: PageState) -> dict:
    status = "review" if state["issues"] or len(state["accepted"]) < len(state["insights"]) else "accepted"
    result = PageResult(page=state["page"], page_type=state["page_type"], status=status,
        insights=state["accepted"], issues=state["issues"], source_chars=len(state["text"]),
        tokens_in=state["tokens_in"], tokens_out=state["tokens_out"])
    return {"result": result.model_dump()}


def build_graph(checkpointer=None):
    builder = StateGraph(PageState)
    builder.add_node("generate_insights", generate)
    builder.add_node("validate_evidence", validate)
    builder.add_node("finalize_page", finalize)
    builder.add_edge(START, "generate_insights")
    builder.add_edge("generate_insights", "validate_evidence")
    builder.add_node("flag_for_review", flag_review)
    builder.add_conditional_edges("validate_evidence", route_after_validation,
                                  {"review": "flag_for_review", "accepted": "finalize_page"})
    builder.add_edge("flag_for_review", "finalize_page")
    builder.add_edge("finalize_page", END)
    return builder.compile(checkpointer=checkpointer)
