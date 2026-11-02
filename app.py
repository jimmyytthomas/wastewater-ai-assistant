"""Web app for the wastewater document assistant.

The question check, search, Claude call, and request log all live in src/.
This file only displays them.
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# src/ is a folder of scripts, not an installed package.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from logger import get_events
from rag import answer

# Green allow, yellow redact, red block.
BADGE_COLORS = {
    "allow": "#1b7f4e",
    "redact": "#b58105",
    "block": "#b42318",
}


st.set_page_config(page_title="Wastewater Assistant", layout="wide")
st.title("Wastewater Assistant")

# The name is collected once and passed into every Ask request.
with st.sidebar:
    user = st.text_input("Your name", value="demo_user")
    st.subheader("About")
    st.write(
        "This assistant answers from public wastewater documents only, "
        "flags or blocks sensitive input, and logs every request without "
        "storing the original question."
    )

ask_tab, dashboard_tab = st.tabs(["Ask", "Governance Dashboard"])


def show_badge(decision):
    """Draw the allow / redact / block decision as a colored pill."""
    color = BADGE_COLORS.get(decision, "#555555")
    st.markdown(
        f'<span style="background:{color};color:white;padding:0.25rem 0.7rem;'
        f'border-radius:999px;font-weight:600;">{decision}</span>',
        unsafe_allow_html=True,
    )


def show_result(result):
    """Render one answer: decision, notices, text, and sources."""
    show_badge(result["decision"])

    # Notices and document warnings share the same yellow info style.
    if result.get("notice"):
        st.warning(result["notice"])
    for warning in result.get("warnings", []):
        st.warning(warning)

    st.write(result["answer"])

    st.subheader("Sources")
    if not result["sources"]:
        st.caption("No sources. A blocked question is not searched.")
        return

    for source in result["sources"]:
        label = f"[{source['number']}] {source['title']} — page {source['page']}"
        with st.expander(label):
            st.write(f"**Publisher:** {source['publisher']}")
            st.write(f"**Date:** {source['published_date']}")
            st.write(f"**Status:** {source['status']}")
            st.markdown(f"[Open source PDF]({source['source_url']})")


with ask_tab:
    question = st.text_area("Question", placeholder="Ask about permits, limits, or biosolids")
    # Store the last result so a later rerun (typing a name, switching tabs)
    # does not send the question to Claude again.
    if st.button("Ask"):
        if not question.strip():
            st.warning("Enter a question first.")
        else:
            with st.spinner("Checking the question and searching the documents..."):
                st.session_state["result"] = answer(question, user=user or "demo_user")

    if "result" in st.session_state:
        show_result(st.session_state["result"])


def _join(values):
    """Turn a logged list into one readable table cell."""
    if isinstance(values, list):
        return "; ".join(str(value) for value in values)
    return "" if values is None else str(values)


with dashboard_tab:
    events = get_events()
    frame = pd.DataFrame(events)

    if frame.empty:
        st.info("No requests logged yet.")
    else:
        decisions = frame["decision"].value_counts()
        average_latency = frame["latency_ms"].mean()

        total, allowed, redacted, blocked, latency = st.columns(5)
        total.metric("Total requests", len(frame))
        allowed.metric("Allowed", int(decisions.get("allow", 0)))
        redacted.metric("Redacted", int(decisions.get("redact", 0)))
        blocked.metric("Blocked", int(decisions.get("block", 0)))
        latency.metric("Average latency", f"{average_latency:.0f} ms")

        st.subheader("Decisions")
        st.bar_chart(decisions)

        # Count a document once per request, even if several chunks came from it.
        document_counts = (
            frame["sources_used"]
            .apply(lambda titles: list(dict.fromkeys(titles or [])))
            .explode()
            .dropna()
            .value_counts()
        )
        st.subheader("Most used documents")
        if document_counts.empty:
            st.caption("No documents have been used yet.")
        else:
            st.bar_chart(document_counts)

        recent = frame.sort_values("timestamp", ascending=False).copy()
        recent["reasons"] = recent["reasons"].apply(_join)
        recent["warnings"] = recent["warnings"].apply(_join)
        st.subheader("Recent events")
        st.dataframe(
            recent[["timestamp", "user", "decision", "reasons", "safe_question", "warnings"]],
            width="stretch",
            hide_index=True,
        )

    st.caption("Original questions are never stored. Blocked questions store no text.")
