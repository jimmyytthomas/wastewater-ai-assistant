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
    (r"(?i)\bpassword\s*:\s*\S+", "Contains text that looks like a password"),
    (r"(?i)\b(?:api[ _-]?key|token)\s*[:=]\s*\S+", "Contains text that looks like an API key or token"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "Contains a Social Security number"),
    (r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "Contains a credit card number"),
)

# These matches are replaced with [REDACTED]. The question then continues.
REDACT_PATTERNS = (
    (r"\$\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\$\d+(?:\.\d{2})?", "Redacted a dollar amount"),
    (r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", "Redacted an email address"),
    (r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b", "Redacted a phone number"),
)

# Flag only. Do not remove the word, and do not change an allow into a redact.
FLAG_PATTERNS = (
    (r"(?i)\bconfidential\b", "confidential"),
    (r"(?i)\bproprietary\b", "proprietary"),
    (r"(?i)\binternal only\b", "internal only"),
)


def check_question(question):
    """Return decision, reasons, and the text that is safe to send to Claude."""
    block_reasons = _block_reasons(question)
    if block_reasons:
        # Nothing from a blocked question is safe to send or store.
        return {"decision": "block", "reasons": block_reasons, "safe_question": ""}

    safe_question, redact_reasons = _redact(question)
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


def _redact(question):
    """Replace client names, money, emails, and phone numbers."""
    text = question
    reasons = []

    for term in _sensitive_terms():
        pattern = re.compile(re.escape(term), re.IGNORECASE)
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


def _sensitive_terms():
    """Longer names first so a short name cannot hide inside a longer one."""
    data = json.loads(TERMS_PATH.read_text())
    return sorted(data["terms"], key=len, reverse=True)
