import re
from .models import Insight


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def numbers(text: str) -> set[str]:
    # Extract reported numerals; this is intentionally conservative about arithmetic.
    return set(re.findall(r"(?<!\w)-?\d[\d,]*(?:\.\d+)?%?", text))


def validate_insights(insights: list[Insight], source: str, page: int) -> tuple[list[Insight], list[str]]:
    accepted, issues = [], []
    source_normalized = compact(source)
    for index, item in enumerate(insights, 1):
        reasons = []
        if not item.evidence:
            reasons.append("missing evidence")
        for ev in item.evidence:
            if ev.page != page:
                reasons.append("wrong page reference")
            if not ev.quote.strip() or compact(ev.quote) not in source_normalized:
                reasons.append("evidence quote not found verbatim in extracted page text")
        cited_text = " ".join(ev.quote for ev in item.evidence)
        unsupported = numbers(item.observation) - numbers(cited_text)
        if unsupported:
            reasons.append(f"unverified observation numbers: {sorted(unsupported)}")
        if reasons:
            issues.append(f"Insight {index}: " + "; ".join(dict.fromkeys(reasons)))
        else:
            accepted.append(item)
    return accepted, issues
