"""Tests for the usage log. Each test writes to its own temporary database."""

from logger import get_events, log_event


def _use_temp_db(monkeypatch, tmp_path):
    monkeypatch.setattr("logger.LOG_DIR", tmp_path)
    monkeypatch.setattr("logger.DB_PATH", tmp_path / "usage.db")


def _log(**overrides):
    fields = {
        "user": "demo_user",
        "decision": "allow",
        "reasons": [],
        "safe_question": "",
        "sources_used": [],
        "warnings": [],
        "answer_chars": 12,
        "latency_ms": 5,
    }
    fields.update(overrides)
    log_event(**fields)


def test_blocked_event_stores_no_question_text(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)
    secret = "password: hunter2 for the Mesa Verde SCADA login"

    _log(
        decision="block",
        reasons=["Contains text that looks like a password"],
        safe_question=secret,
        answer_chars=0,
    )

    events = get_events()
    assert len(events) == 1
    assert events[0]["decision"] == "block"
    assert events[0]["safe_question"] == ""

    stored = (tmp_path / "usage.db").read_bytes()
    assert secret.encode() not in stored
    assert b"hunter2" not in stored


def test_allowed_event_stores_the_safe_question(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)
    safe_question = "What is the BOD5 limit for secondary treatment?"

    _log(decision="allow", safe_question=safe_question)

    events = get_events()
    assert len(events) == 1
    assert events[0]["decision"] == "allow"
    assert events[0]["safe_question"] == safe_question
