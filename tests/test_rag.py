"""Governance tests for answer(): the raw question never leaves the input check."""

import pytest

import rag

HIT = {
    "text": "BOD5 limits are 45 mg/L monthly average.",
    "metadata": {
        "title": "Test Permit",
        "publisher": "Test Board",
        "published_date": "2025-07-01",
        "status": "final",
        "page": 6,
        "source_url": "https://example.com/permit.pdf",
    },
    "distance": 0.1,
}


@pytest.fixture
def calls(monkeypatch):
    """Record everything answer() sends to search, Claude, and the log."""
    seen = {"search": [], "claude": [], "log": []}

    def fake_search(question, k=8):
        seen["search"].append(question)
        return seen.get("hits", [HIT])

    def fake_claude(prompt):
        seen["claude"].append(prompt)
        return "The BOD5 limit is 45 mg/L [1]."

    monkeypatch.setattr(rag, "search", fake_search)
    monkeypatch.setattr(rag, "ask_claude", fake_claude)
    monkeypatch.setattr(rag, "log_event", lambda **fields: seen["log"].append(fields))
    return seen


def test_redacted_question_never_reaches_search_claude_or_log(calls):
    rag.answer("What are the Mesa Verde limits? Email jo@city.example.")

    sent = calls["search"] + calls["claude"] + [str(event) for event in calls["log"]]
    for text in sent:
        assert "Mesa Verde" not in text
        assert "jo@city.example" not in text
    assert calls["log"][0]["decision"] == "redact"


def test_blocked_question_is_not_searched_sent_or_logged(calls):
    result = rag.answer("The SCADA password: hunter2 is broken.")

    assert result["decision"] == "block"
    assert calls["search"] == []
    assert calls["claude"] == []
    assert calls["log"][0]["safe_question"] == ""
    assert "hunter2" not in str(calls["log"])


def test_no_search_hits_skips_claude(calls):
    calls["hits"] = []
    result = rag.answer("What is the BOD5 limit?")

    assert calls["claude"] == []
    assert result["answer"] == rag.NOT_FOUND_MESSAGE
    assert result["sources"] == []


def test_only_cited_sources_are_kept_with_their_numbers(calls, monkeypatch):
    calls["hits"] = [HIT, HIT, HIT, HIT]
    monkeypatch.setattr(rag, "ask_claude", lambda prompt: "Limits are 45 mg/L [3] and 56 mg/L [1, 4].")

    result = rag.answer("What are the BOD5 limits?")

    assert [source["number"] for source in result["sources"]] == [1, 3, 4]
    assert len(calls["log"][0]["sources_used"]) == 3


def test_uncited_reply_has_no_sources(calls, monkeypatch):
    monkeypatch.setattr(rag, "ask_claude", lambda prompt: rag.NOT_FOUND_MESSAGE)

    result = rag.answer("What is the capital of France?")

    assert result["sources"] == []
    assert calls["log"][0]["sources_used"] == []


@pytest.mark.parametrize(
    "user",
    ["Mesa Verde ops", "jo@city.example", "760-555-0199", "password=hunter2", "confidential"],
)
def test_sensitive_user_name_is_logged_as_redacted(calls, user):
    rag.answer("What is the BOD5 limit?", user=user)

    assert calls["log"][0]["user"] == rag.REDACTED_USER


def test_plain_user_name_is_logged_as_given(calls):
    rag.answer("What is the BOD5 limit?", user="Jimmy Thomas")

    assert calls["log"][0]["user"] == "Jimmy Thomas"


def test_error_is_logged_without_the_raw_question(calls, monkeypatch):
    def failing_claude(prompt):
        raise RuntimeError("Claude call failed: timed out after 120 seconds.")

    monkeypatch.setattr(rag, "ask_claude", failing_claude)
    with pytest.raises(RuntimeError):
        rag.answer("What are the Mesa Verde limits?")

    event = calls["log"][0]
    assert "timed out" in event["error"]
    assert "Mesa Verde" not in str(event)
