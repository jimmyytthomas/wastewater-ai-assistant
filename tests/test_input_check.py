"""Tests for the question input check."""

import pytest

from input_check import check_question


@pytest.mark.parametrize(
    "question",
    [
        "What is the BOD5 limit for secondary treatment?",
        "What does Order R7-2025-0017 require under 40 CFR 133.102?",
        "What does Section 60301.320 say about 2 NTU turbidity?",
    ],
)
def test_allow_normal_technical_question(question):
    result = check_question(question)

    assert result["decision"] == "allow"
    assert result["safe_question"] == question
    assert result["reasons"] == []


@pytest.mark.parametrize(
    "contents",
    [
        None,
        "{not json",
        '{"terms": []}',
        '{"terms": ["Mesa Verde", ""]}',
        '["Mesa Verde"]',
    ],
)
def test_missing_or_invalid_terms_file_blocks(monkeypatch, tmp_path, contents):
    terms_path = tmp_path / "sensitive_terms.json"
    if contents is not None:
        terms_path.write_text(contents)
    monkeypatch.setattr("input_check.TERMS_PATH", terms_path)

    result = check_question("What is the BOD5 limit for secondary treatment?")

    assert result["decision"] == "block"
    assert result["safe_question"] == ""
    assert "missing or invalid" in result["reasons"][0]


@pytest.mark.parametrize(
    "question, secret",
    [
        (
            "What is the permit status for the Mesa Verde plant?",
            "Mesa Verde",
        ),
        (
            "The upgrade bid came in at $4,500.00 last quarter.",
            "$4,500.00",
        ),
        (
            "The upgrade budget is $4.5 million this year.",
            "4.5 million",
        ),
        (
            "Send the lab result to operator@citywwtp.example today.",
            "operator@citywwtp.example",
        ),
        (
            "Call the operator at 760-555-0199 about the sample.",
            "760-555-0199",
        ),
        (
            "Call the operator at 7605550199 about the sample.",
            "7605550199",
        ),
        ("What is the permit status for the Mesa  Verde plant?", "Mesa  Verde"),
        ("What is the permit status for the MesaVerde plant?", "MesaVerde"),
        ("What is the permit status for the mesa-verde plant?", "mesa-verde"),
        ("Does BLUE BASIN need a new permit?", "BLUE BASIN"),
    ],
)
def test_redact_hides_the_original_value(question, secret):
    result = check_question(question)

    assert result["decision"] == "redact"
    assert secret not in result["safe_question"]
    assert "[REDACTED]" in result["safe_question"]


@pytest.mark.parametrize(
    "question",
    [
        "The SCADA password: hunter2 must stay off the model.",
        "The SCADA password=hunter2 must stay off the model.",
        "The SCADA password is hunter2 for the night shift.",
        "The service token is sk-testkey12345 for this call.",
        "The form lists SSN 123-45-6789 for the operator.",
        "The form lists SSN 123456789 for the operator.",
        "The form lists SSN 123 45 6789 for the operator.",
        "Bill the card 4111-1111-1111-1111 for the parts order.",
        "Bill the Amex 3782 822463 10005 for the parts order.",
        "Bill the Amex 378282246310005 for the parts order.",
    ],
)
def test_block_secrets(question):
    result = check_question(question)

    assert result["decision"] == "block"
    assert result["safe_question"] == ""
    assert result["reasons"]


def test_flag_confidential_without_redacting_it():
    question = "Is this confidential guidance covered by the permit?"
    result = check_question(question)

    assert result["decision"] == "allow"
    assert "confidential" in result["safe_question"]
    assert "[REDACTED]" not in result["safe_question"]
    assert any("confidential" in reason for reason in result["reasons"])
