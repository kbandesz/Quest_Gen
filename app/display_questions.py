"""UI elements to display AI-generated questions in editable and static formats."""

from typing import Any, Dict, List

import streamlit as st


def _lo_title(lo: Dict[str, Any]) -> str:
    """Get the display title for a learning objective."""
    return lo.get("final_text") or lo.get("text") or "(no text)"


def display_editable_questions(los: List[Dict[str, Any]], questions: Dict[str, List[Dict[str, Any]]]):
    """Render questions with editable fields for stems, options, and metadata."""
    for lo in los:
        qs = questions.get(lo["id"], [])
        if not qs:
            continue

        with st.container(border=True):
            st.subheader(_lo_title(lo))
            for idx, q in enumerate(qs):
                with st.expander(f"Question {idx + 1}", expanded=False):
                    q["stem"] = st.text_area(
                        f"Question {idx + 1}",
                        q.get("stem", ""),
                        key=f"stem_{lo['id']}_{idx}",
                        height=70,
                        label_visibility="collapsed",
                    )

                    for opt in q.get("options", []):
                        cols = st.columns([1, 30])
                        with cols[0]:
                            st.markdown(f"**({opt['id']})**")
                        with cols[1]:
                            opt["text"] = st.text_input(
                                f"**({opt['id']})**",
                                opt.get("text", ""),
                                key=f"opt_{lo['id']}_{idx}_{opt['id']}",
                                label_visibility="collapsed",
                            )

                    current = ["A", "B", "C", "D"].index(q.get("correct_option_id", "A"))
                    q["correct_option_id"] = st.radio(
                        "Correct option",
                        ["A", "B", "C", "D"],
                        index=current,
                        horizontal=True,
                        key=f"radio_{lo['id']}_{idx}",
                    )

                    st.markdown("Feedback")
                    for opt in q.get("options", []):
                        opt["option_rationale"] = st.text_area(
                            f"**({opt['id']})**",
                            opt.get("option_rationale", ""),
                            key=f"rat_{lo['id']}_{idx}_{opt['id']}",
                            height=70,
                        )

                    q["contentReference"] = st.text_area(
                        "Content reference",
                        q.get("contentReference", ""),
                        key=f"ref_{lo['id']}_{idx}",
                        height=70,
                    )
                    q["cognitive_rationale"] = st.text_area(
                        "Rationale for Bloom level",
                        q.get("cognitive_rationale", ""),
                        key=f"cograt_{lo['id']}_{idx}",
                        height=70,
                    )


def display_static_questions(los: List[Dict[str, Any]], questions: Dict[str, List[Dict[str, Any]]]):
    """Render a formatted, read-only view of generated questions."""
    for lo in los:
        qs = questions.get(lo["id"], [])
        if not qs:
            continue

        with st.container(border=True):
            st.subheader(_lo_title(lo))
            for idx, q in enumerate(qs):
                st.markdown(f"**Question {idx + 1}:** {q.get('stem', 'N/A')}")
                st.markdown("**Options**")
                for opt in q.get("options", []):
                    is_correct = opt.get("id") == q.get("correct_option_id")
                    indicator = "✅" if is_correct else "•"
                    st.markdown(f"{indicator} **({opt.get('id', '?')})** {opt.get('text', '')}")
                    if opt.get("option_rationale"):
                        st.caption(f"Feedback: {opt['option_rationale']}")

                if q.get("cognitive_rationale"):
                    st.markdown(f"**Bloom rationale:** {q['cognitive_rationale']}")
                if q.get("contentReference"):
                    st.markdown(f"**Content reference:** {q['contentReference']}")

                st.markdown("---")
