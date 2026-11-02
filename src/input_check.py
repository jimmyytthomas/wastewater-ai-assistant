"""Decide whether a question may be sent to Claude.

Block keeps the question off the model entirely. Redact replaces sensitive
text with [REDACTED] and continues. Words such as "confidential" are only
flagged: they are noted in reasons and left in the question.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERMS_PATH = ROOT / "data" / "sensitive_terms.json"

# Secrets are blocked, not redacted. The original text is never sent on.
BLOCK_PATTERNS = (
    (r"\bsk-[A-Za-z0-9_\-]+", "Contains text that looks like an API key or token (starts with sk-)"),
    (r"(?i)\bpassword\s*(?:[:=]|\bis\b)\s*\S+", "Contains text that looks like a password"),
    (r"(?i)\b(?:api[ _-]?key|token)\s*[:=]\s*\S+", "Contains text that looks like an API key or token"),
    # The backreference keeps the separator consistent: 123-45-6789, 123 45 6789, or 123456789.
    (r"(?<!\d)\d{3}([-\s]?)\d{2}\1\d{4}(?!\d)", "Contains a Social Security number"),
    (r"(?<!\d)(?:\d{4}[-\s]?){3}\d{4}(?!\d)", "Contains a credit card number"),
    (r"(?<!\d)3[47]\d{2}[-\s]?\d{6}[-\s]?\d{5}(?!\d)", "Contains a credit card number"),
)

# These matches are replaced with [REDACTED]. The question then continues.
REDACT_PATTERNS = (
    # Covers $4,500.00, $4.5 million, and $250k so no part of the amount is left behind.
    (
        r"(?i)\$\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:thousand|million|billion|mm|k|m|b)\b)?",
        "Redacted a dollar amount",
    ),
    (r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", "Redacted an email address"),
    (r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)", "Redacted a phone number"),
)

# Flag only. Do not remove the word, and do not change an allow into a redact.
FLAG_PATTERNS = (
    (r"(?i)\bconfidential\b", "confidential"),
    (r"(?i)\bproprietary\b", "proprietary"),
    (r"(?i)\binternal only\b", "internal only"),
)


def check_question(question):
    """Return decision, reasons, and the text that is safe to send to Claude."""
    try:
        terms = _sensitive_terms()
    except (OSError, ValueError, KeyError, TypeError):
        # Fail closed: without the list, client names could not be redacted.
        return {
            "decision": "block",
            "reasons": [f"The sensitive-terms list ({TERMS_PATH.name}) is missing or invalid"],
            "safe_question": "",
        }

    block_reasons = _block_reasons(question)
    if block_reasons:
        # Nothing from a blocked question is safe to send or store.
        return {"decision": "block", "reasons": block_reasons, "safe_question": ""}

    safe_question, redact_reasons = _redact(question, terms)
    flag_reasons = _flag_reasons(question)
    reasons = redact_reasons + flag_reasons

    if redact_reasons:
        decision = "redact"
    else:
        decision = "allow"

    return {"decision": decision, "reasons": reasons, "safe_question": safe_question}


def _block_reasons(question):
    reasons = []
    for pattern, reason in BLOCK_PATTERNS:
        if re.search(pattern, question):
            reasons.append(reason)
    return reasons


def _redact(question, terms):
    """Replace client names, money, emails, and phone numbers."""
    text = question
    reasons = []

    for term in terms:
        pattern = _term_pattern(term)
        if pattern.search(text):
            text = pattern.sub("[REDACTED]", text)
            reasons.append("Redacted a client or project name from the sensitive-terms list")

    for pattern, reason in REDACT_PATTERNS:
        if re.search(pattern, text):
            text = re.sub(pattern, "[REDACTED]", text)
            reasons.append(reason)

    return text, reasons


def _flag_reasons(question):
    """Note sensitivity words without removing them."""
    flagged = [label for pattern, label in FLAG_PATTERNS if re.search(pattern, question)]
    if not flagged:
        return []
    words = ", ".join(f'"{word}"' for word in flagged)
    return [f"Flagged sensitive wording {words} (left in the question)"]


def _term_pattern(term):
    """Match a name in any case, with any spacing, hyphens, or underscores between its words."""
    words = term.split()
    return re.compile(r"[\s\-_]*".join(re.escape(word) for word in words), re.IGNORECASE)


def _sensitive_terms():
    """Longer names first so a short name cannot hide inside a longer one.

    Raises if the file is missing, is not valid JSON, or has no usable terms.
    """
    data = json.loads(TERMS_PATH.read_text())
    terms = data["terms"]
    if not isinstance(terms, list) or not terms:
        raise ValueError("terms must be a non-empty list")
    if not all(isinstance(term, str) and term.strip() for term in terms):
        raise ValueError("every term must be a non-empty string")
    return sorted(terms, key=len, reverse=True)
