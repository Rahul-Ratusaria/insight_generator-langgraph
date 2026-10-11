"""Deterministic, reproducible analytics. No invented benchmarks or AI arithmetic."""
from __future__ import annotations
import re
from .models import Metric, AnalyticalInsight, Evidence, PageResult
from .validation import compact

NUM = r"(?P<value>-?\d[\d,]*(?:\.\d+)?)(?P<pct>\s*%)?"
RULES = [
    ("revenue_year", re.compile(r"^Revenue\s+(?P<year>20\d\d)\s*:\s*" + NUM + r"\s*$", re.I)),
    ("region_revenue", re.compile(r"^(?P<region>[A-Za-z][A-Za-z -]*?)\s+region revenue\s*:\s*" + NUM + r"\s*$", re.I)),
    ("retention", re.compile(r"^Customer retention\s*:\s*" + NUM + r"\s*$", re.I)),
    ("return_rate", re.compile(r"^Return rate\s*:\s*" + NUM + r"\s*$", re.I)),
    ("delivery", re.compile(r"^Average delivery time\s*:\s*" + NUM + r"\s*days?\s*$", re.I)),
    ("orders", re.compile(r"^Orders(?: in [^:]*)?\s*:\s*" + NUM + r"\s*$", re.I)),
    ("respondents", re.compile(r"^Survey respondents\s*:\s*" + NUM + r"\s*$", re.I)),
]

def extract_metrics(pages: list[PageResult], text_by_page: dict[int, str]) -> list[Metric]:
    """Only parse lines exactly matching known patterns on accepted pages."""
    metrics: list[Metric] = []
    for page in pages:
        if page.status != "accepted":
            continue
        for line in text_by_page.get(page.page, "").splitlines():
            line = " ".join(line.strip().split())
            for kind, pattern in RULES:
                match = pattern.fullmatch(line)
                if not match:
                    continue
                value = float(match.group("value").replace(",", ""))
                if kind == "revenue_year":
                    key = "revenue_" + match.group("year")
                elif kind == "region_revenue":
                    key = "region_" + re.sub(r"\W+", "_", match.group("region").lower()).strip("_") + "_revenue"
                else:
                    key = kind
                unit = "%" if match.group("pct") else ("days" if kind == "delivery" else "")
                metrics.append(Metric(key=key, label=line.split(":")[0], value=value, unit=unit, page=page.page, quote=line))
                break
    return metrics

def calculate_insights(metrics: list[Metric], text_by_page: dict[int, str]) -> list[AnalyticalInsight]:
    """Compare only precisely matched, independently traceable numeric operands."""
    unique: dict[str, Metric] = {}
    duplicated = set()
    for metric in metrics:
        if metric.key in unique:
            duplicated.add(metric.key)
        else:
            unique[metric.key] = metric
    for key in duplicated:
        unique.pop(key, None)  # ambiguous values must never be silently merged
    result: list[AnalyticalInsight] = []

    def evidence(*items: Metric) -> list[Evidence]:
        return [Evidence(page=m.page, quote=m.quote) for m in items]

    years = sorted((int(k.split("_")[1]), v) for k, v in unique.items() if re.fullmatch(r"revenue_20\d\d", k))
    for (year_a, a), (year_b, b) in zip(years, years[1:]):
        if year_b != year_a + 1 or a.value <= 0:
            continue
        difference = b.value - a.value
        growth = difference / a.value * 100
        result.append(AnalyticalInsight(
            title=f"Revenue change ({year_a}–{year_b})",
            observation=f"Reported revenue {'increased' if difference >= 0 else 'decreased'} by {abs(growth):.1f}% ({abs(difference):,.0f} units), from {a.value:,.0f} to {b.value:,.0f}.",
            implication="Investigate the drivers of the change in revenue; the report alone does not establish causation.",
            calculation=f"(({b.value:,.0f} - {a.value:,.0f}) / {a.value:,.0f}) × 100 = {growth:+.1f}%",
            evidence=evidence(a,b), metric_keys=[a.key,b.key],
            caveat="Assumes the two reported yearly revenue figures use comparable definitions and units."))
    regions = [m for k,m in unique.items() if re.fullmatch(r"region_[a-z_]+_revenue", k)]
    if len(regions) == 2 and all(x.value >= 0 for x in regions):
        low, high = sorted(regions, key=lambda m: m.value)
        if high.value > low.value and low.value > 0:
            gap = high.value - low.value
            pct = gap / low.value * 100
            high_name = high.label.split(" region")[0]
            low_name = low.label.split(" region")[0]
            result.append(AnalyticalInsight(
                title="Regional revenue gap",
                observation=f"{high_name} reported {gap:,.0f} more revenue than {low_name}, a {pct:.1f}% gap relative to {low_name}.",
                implication="Examine regional demand, distribution, pricing and reporting scope before allocating resources.",
                calculation=f"(({high.value:,.0f} - {low.value:,.0f}) / {low.value:,.0f}) × 100 = {pct:.1f}%",
                evidence=evidence(low,high), metric_keys=[low.key,high.key],
                caveat="Regional values are assumed comparable; no region-level profitability can be inferred."))
    validate_derived(result, unique, text_by_page)
    return result

def validate_derived(insights: list[AnalyticalInsight], metrics: dict[str, Metric], page_texts: dict[int, str]) -> None:
    """Fail closed on broken lineage. Arithmetic comes solely from the matched metric operands."""
    for item in insights:
        if len(item.metric_keys) != 2 or len(item.evidence) != 2:
            raise ValueError("Derived insight must have two explicit operands")
        for key, ev in zip(item.metric_keys, item.evidence):
            metric = metrics[key]
            if metric.page != ev.page or compact(metric.quote) != compact(ev.quote):
                raise ValueError("Derived insight has mismatched lineage")
            if compact(ev.quote) not in compact(page_texts.get(ev.page, "")):
                raise ValueError("Derived insight refers to non-existent source")
