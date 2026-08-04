from backend.intent_parser import parse_intent_response


def test_parse_healthy_hampers_under_budget():
    parsed = parse_intent_response("Need healthy hampers under ?180")

    assert parsed.filters["budget"] == 180
    assert parsed.recommendation_request.budget_max == 180
    assert parsed.recommendation_request.preferred_categories == ["Healthy"]
    assert parsed.recommendation_request.include_themed_customised is False
    assert parsed.confidence > 0.5


def test_parse_item_count_and_sweet_only():
    parsed = parse_intent_response("Need 5 sweet only boxes under INR 250")

    assert parsed.recommendation_request.item_count == 5
    assert parsed.recommendation_request.sweet_preference == "sweet_only"


def test_parse_customization():
    parsed = parse_intent_response("Logo customized sweet hampers up to 300")

    assert parsed.recommendation_request.include_themed_customised is True
    assert "Sweet" in parsed.recommendation_request.preferred_categories


def test_parse_missing_budget_uses_default_and_notes():
    parsed = parse_intent_response("healthy gift box", default_budget_min=50)

    assert parsed.recommendation_request.budget_min == 50
    assert parsed.recommendation_request.budget_max == 1000
    assert parsed.notes
