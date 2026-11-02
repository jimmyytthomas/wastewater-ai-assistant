"""Answer a question from the indexed wastewater documents."""

import argparse
import time
from datetime import date

from input_check import check_question
from llm import ask_claude
from logger import log_event
from store import search


def answer(question, user="demo_user"):
    """Check the question, then search and ask Claude unless it is blocked."""
    started = time.perf_counter()
    check = check_question(question)
    decision = check["decision"]
    reasons = check["reasons"]
    # Only the checked text is searched, sent, or logged. Never the raw question.
    safe_question = check["safe_question"]

    try:
        if decision == "block":
            result = {
                "answer": _block_message(reasons),
                "sources": [],
                "warnings": [],
                "decision": decision,
                "reasons": reasons,
                "notice": None,
            }
        else:
            hits = search(safe_question, k=8)
            sources = [_source(number, hit) for number, hit in enumerate(hits, start=1)]
            reply = ask_claude(_prompt(safe_question, hits))
            result = {
                "answer": reply,
                "sources": sources,
                "warnings": _warnings(sources),
                "decision": decision,
                "reasons": reasons,
                "notice": _redaction_notice(reasons) if decision == "redact" else None,
            }
    except Exception as exc:
        _record(user, decision, reasons, safe_question, [], [], 0, started, error=str(exc))
        raise

    _record(
        user,
        decision,
        reasons,
        safe_question,
        [source["title"] for source in result["sources"]],
        result["warnings"],
        len(result["answer"]),
        started,
    )
    return result


def _prompt(question, hits):
    """Build the instruction and the numbered source excerpts."""
    blocks = []
    for number, hit in enumerate(hits, start=1):
        metadata = hit["metadata"]
        blocks.append(
            "\n".join(
                [
                    f"[{number}] {metadata['title']}",
                    f"Publisher: {metadata['publisher']}",
                    f"Published: {metadata['published_date']}",
                    f"Status: {metadata['status']}",
                    f"Page: {metadata['page']}",
                    f"URL: {metadata['source_url']}",
                    "",
                    hit["text"],
                ]
            )
        )

    sources = "\n\n".join(blocks)
    return f"""You are assisting wastewater engineers. Use only the sources below.

Rules:
- Answer ONLY from the provided sources.
- Cite sources inline as [1], [2], and so on, matching the source numbers below.
- If the sources do not contain the answer, say: "I couldn't find that in the available documents"
- Be concise and practical, written for wastewater engineers.

Sources:
{sources}

Question: {question}
"""


def _source(number, hit):
    metadata = hit["metadata"]
    return {
        "number": number,
        "title": metadata["title"],
        "page": metadata["page"],
        "publisher": metadata["publisher"],
        "published_date": metadata["published_date"],
        "status": metadata["status"],
        "source_url": metadata["source_url"],
    }


def _warnings(sources):
    warnings = []
    if any(source["status"] == "draft" for source in sources):
        warnings.append("Note: this answer uses a DRAFT document that may change.")
    if any(_is_older_than_10_years(source["published_date"]) for source in sources):
        warnings.append("Note: this answer uses a source older than 10 years.")
    return warnings


def _is_older_than_10_years(published_date):
    """True when the publication date is more than 10 years before today."""
    published = date.fromisoformat(published_date)
    today = date.today()
    try:
        ten_years_ago = today.replace(year=today.year - 10)
    except ValueError:
        # Today is Feb 29 and the year 10 years ago is not a leap year.
        ten_years_ago = today.replace(year=today.year - 10, day=28)
    return published < ten_years_ago


def _block_message(reasons):
    why = "; ".join(reasons) if reasons else "it failed the input check"
    return f"This question was blocked and was not sent to Claude. Reason: {why}."


def _redaction_notice(reasons):
    """Tell the user what was removed and why. Flag-only reasons are separate."""
    redacted = [reason for reason in reasons if reason.startswith("Redacted")]
    return (
        "Some text was replaced with [REDACTED] before this question was sent to Claude: "
        + "; ".join(redacted)
        + "."
    )


def _record(user, decision, reasons, safe_question, sources_used, warnings, answer_chars, started, error=None):
    log_event(
        user=user,
        decision=decision,
        reasons=reasons,
        safe_question=safe_question,
        sources_used=sources_used,
        warnings=warnings,
        answer_chars=answer_chars,
        latency_ms=int((time.perf_counter() - started) * 1000),
        error=error,
    )


def _print_result(result):
    print(f"Decision: {result['decision']}")
    print("Reasons:")
    if result["reasons"]:
        for reason in result["reasons"]:
            print(f"- {reason}")
    else:
        print("(none)")
    print("Notice:")
    print(result["notice"] or "(none)")
    print()
    print(result["answer"])
    print()
    print("Warnings:")
    if result["warnings"]:
        for warning in result["warnings"]:
            print(warning)
    else:
        print("(none)")
    print()
    print("Sources:")
    if not result["sources"]:
        print("(none)")
    for source in result["sources"]:
        print(
            f"[{source['number']}] {source['title']}, "
            f"page {source['page']}, {source['publisher']}, "
            f"{source['published_date']}, {source['status']}, "
            f"{source['source_url']}"
        )


if __name__ == "__main__":
    # python src/rag.py "question" --user "name"
    parser = argparse.ArgumentParser(description="Ask the wastewater document assistant.")
    parser.add_argument("question")
    parser.add_argument("--user", default="demo_user")
    args = parser.parse_args()
    _print_result(answer(args.question, user=args.user))
