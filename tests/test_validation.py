from insight_generator.models import Insight, Evidence
from insight_generator.validation import validate_insights

def test_valid_citation():
    item = Insight(observation="Revenue was 120", implication="May support planning", evidence=[Evidence(quote="Revenue was 120", page=2)])
    verified, errors = validate_insights([item], "Revenue was 120", 2)
    assert len(verified) == 1 and not errors

def test_rejects_hallucinated_number():
    item = Insight(observation="Revenue grew 30%", implication="", evidence=[Evidence(quote="Revenue was 120", page=2)])
    accepted, issues = validate_insights([item], "Revenue was 120", 2)
    assert not accepted and "30%" in str(issues)

def test_rejects_nonexistent_quote_and_wrong_page():
    item = Insight(observation="Orders 5", implication="", evidence=[Evidence(quote="Orders 5", page=4)])
    accepted, issues = validate_insights([item], "Revenue 120", 2)
    assert not accepted and "wrong page" in str(issues)
