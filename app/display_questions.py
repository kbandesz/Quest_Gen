"""UI elements to display AI-generated questions in editable and static formats."""

from typing import Any, Dict, List

import streamlit as st


# def _lo_title(lo: Dict[str, Any]) -> str:
#     """Get the display title for a learning objective."""
#     return lo.get("final_text") or lo.get("text") or "(no text)"


def display_editable_questions(los: List[Dict[str, Any]], questions: Dict[str, List[Dict[str, Any]]]):
    """Render questions with editable fields for stems, options, and metadata."""
    # Go over all LOs
    for lo in los:
        qs = questions.get(lo["id"], [])
        if not qs:
            continue

        with st.container(border=True):
            st.subheader(lo.get("final_text"))
            for idx, q in enumerate(qs):
                with st.expander(f"**Question {idx + 1}: {q.get('stem', 'N/A')}**", expanded=False):
                #with st.expander(f"Question {idx + 1}", expanded=False):
                    # Question stem
                    q["stem"] = st.text_area(
                        f"Question {idx + 1}",
                        q.get("stem", ""),
                        key=f"stem_{lo['id']}_{idx}",
                        height=70,
                        label_visibility="collapsed",
                    )
                    # Answer options
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
                    # Correct answer
                    current = ["A", "B", "C", "D"].index(q.get("correct_option_id", "A"))
                    q["correct_option_id"] = st.radio(
                        "Correct option",
                        ["A", "B", "C", "D"],
                        index=current,
                        horizontal=True,
                        key=f"radio_{lo['id']}_{idx}",
                    )
                    # Feedback for each option
                    st.markdown("Feedback")
                    for opt in q.get("options", []):
                        opt["option_rationale"] = st.text_area(
                            f"**({opt['id']})**",
                            opt.get("option_rationale", ""),
                            key=f"rat_{lo['id']}_{idx}_{opt['id']}",
                            height=70,
                        )
                    # Content reference and cognitive rationale
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
    # Go over all LOs
    for lo in los:
        qs = questions.get(lo["id"], [])
        if not qs:
            continue

        with st.container(border=True):
            st.subheader(lo.get("final_text"))
            for idx, q in enumerate(qs):
                with st.expander(f"**Question {idx + 1}: {q.get('stem', 'N/A')}**", expanded=False):
                    # Question stem
                    #st.markdown(f"### **{q.get('stem', 'N/A')}**")
                    # Answer options
                    for opt in q.get("options", []):
                        is_correct = opt.get("id") == q.get("correct_option_id")
                        indicator = "✅" if is_correct else "❌"
                        st.markdown(f"{indicator} **({opt.get('id', '?')})**  {opt.get('text', '')}")
                    # Feedback for each option
                    st.markdown("**Feedback**")
                    for opt in q.get("options", []):
                        st.markdown(f"**({opt['id']})** {opt.get('option_rationale', '')}")

                    # Content reference and cognitive rationale
                    st.markdown(f"**Content reference:** {q.get('contentReference')}")
                    st.markdown(f"**Rationale for Bloom level:** {q.get('cognitive_rationale')}")

                    #st.markdown("---")
