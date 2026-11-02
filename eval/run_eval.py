"""Run each review question through answer() and save the results."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag import answer

QUESTIONS_PATH = Path(__file__).resolve().parent / "questions.json"
RESULTS_PATH = Path(__file__).resolve().parent / "results.md"


def main():
    questions = json.loads(QUESTIONS_PATH.read_text())
    sections = ["# Evaluation results", ""]

    for index, item in enumerate(questions, start=1):
        question = item["question"]
        expected = item["good_answer_includes"]
        print(f"\n=== {index}. {question}")

        result = answer(question)
        _print_answer(result)

        sections.extend(
            [
                f"## {index}. {question}",
                "",
                f"**A good answer should include:** {expected}",
                "",
                f"**Decision:** {result['decision']}",
                "",
                "**Answer:**",
                "",
                result["answer"],
                "",
                "**Sources:**",
                "",
                _sources_markdown(result["sources"]),
                "",
            ]
        )

    RESULTS_PATH.write_text("\n".join(sections) + "\n")
    print(f"\nSaved results to {RESULTS_PATH}")


def _print_answer(result):
    print(result["answer"])
    print("\nSources:")
    if not result["sources"]:
        print("(none)")
        return
    for source in result["sources"]:
        print(_source_line(source))


def _sources_markdown(sources):
    if not sources:
        return "(none)"
    return "\n".join(f"- {_source_line(source)}" for source in sources)


def _source_line(source):
    return (
        f"[{source['number']}] {source['title']}, "
        f"page {source['page']}, {source['publisher']}, "
        f"{source['published_date']}, {source['status']}, "
        f"{source['source_url']}"
    )


if __name__ == "__main__":
    main()
