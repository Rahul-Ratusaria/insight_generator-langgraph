import pytest
from insight_generator.analytics import extract_metrics, calculate_insights
from insight_generator.models import PageResult

def extract(lines):
    pages = [PageResult(page=n, page_type="table", status="accepted") for n in lines]
    metrics = extract_metrics(pages, lines)
    return metrics, calculate_insights(metrics, lines)

def test_growth_math_and_lineage():
    texts = {1: "Revenue 2025: 1,200,000\nRevenue 2026: 1,440,000"}
    metrics, findings = extract(texts)
    assert len(metrics) == 2
    assert len(findings) == 1
    assert "20.0%" in findings[0].observation
    assert {e.page for e in findings[0].evidence} == {1}

def test_regions_across_pages():
    _, findings = extract({1:"North region revenue: 500,000",2:"South region revenue: 700,000"})
    assert len(findings) == 1
    assert "40.0%" in findings[0].observation
    assert {e.page for e in findings[0].evidence} == {1,2}

def test_no_division_by_zero():
    _, findings = extract({1:"Revenue 2025: 0\nRevenue 2026: 100"})
    assert not findings

def test_duplicate_metrics_suppressed():
    _, findings = extract({1:"Revenue 2025: 100",2:"Revenue 2025: 110\nRevenue 2026: 200"})
    assert not findings

def test_unrecognized_text_not_used():
    metrics, findings = extract({1:"Revenue 2025: 1,200,000\nGrowth 300%"})
    assert len(metrics) == 1
    assert not findings

def test_reviewed_pages_excluded():
    lines = {1:"Revenue 2025: 100\nRevenue 2026: 150"}
    page = PageResult(page=1,page_type="table",status="review")
    assert not extract_metrics([page],lines)
