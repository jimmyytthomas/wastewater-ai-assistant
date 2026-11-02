"""Tests for the question input check."""

import pytest

from input_check import check_question


def test_allow_normal_technical_question():
    question = "What is the BOD5 limit for secondary treatment?"
    result = check_question(question)

    assert result["decision"] == "allow"
    assert result["safe_question"] == question
    assert result["reasons"] == []


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
            "Send the lab result to operator@citywwtp.example today.",
            "operator@citywwtp.example",
        ),
        (
            "Call the operator at 760-555-0199 about the sample.",
            "760-555-0199",
        ),
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
        "The service token is sk-testkey12345 for this call.",
        "The form lists SSN 123-45-6789 for the operator.",
        "Bill the card 4111-1111-1111-1111 for the parts order.",
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
