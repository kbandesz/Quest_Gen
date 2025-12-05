"""UI elements to display AI-generated questions in editable and static formats."""

from typing import Any, Dict
import streamlit as st

def display_editable_question(lo_id: str, idx: int, q: Dict[str, Any]) -> None:
    """
    Render a question with editable fields for stem, options, and metadata.
    Args:
        lo_id: The LO ID associated with the question (for unique key generation).
        idx: The index of the question (for unique key generation).
        q: The question data dictionary to be edited.
    """
    # Question stem
    q["stem"] = st.text_area(
        "Question",
        q.get("stem", ""),
        height=70,
        label_visibility="collapsed",
        key=f"stem_{lo_id}_{idx}",
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
                label_visibility="collapsed",
                key=f"opt_text_{lo_id}_{idx}_{opt['id']}",
            )
    # Correct answer
    current = ["A", "B", "C", "D"].index(q.get("correct_option_id", "A"))
    q["correct_option_id"] = st.radio(
        "Correct option",
        ["A", "B", "C", "D"],
        index=current,
        horizontal=True,
        key=f"correct_option_{lo_id}_{idx}",
    )
    # Feedback for each option
    st.markdown("Feedback")
    for opt in q.get("options", []):
        opt["option_rationale"] = st.text_area(
            f"**({opt['id']})**",
            opt.get("option_rationale", ""),
            height=70,
            key=f"option_rationale_{lo_id}_{idx}_{opt['id']}",
        )
    # Content reference and cognitive rationale
    q["contentReference"] = st.text_area(
        "Content reference",
        q.get("contentReference", ""),
        height=70,
        key=f"content_reference_{lo_id}_{idx}",
    )
    q["cognitive_rationale"] = st.text_area(
        "Rationale for Bloom level",
        q.get("cognitive_rationale", ""),
        height=70,
        key=f"cognitive_rationale_{lo_id}_{idx}",
    )

def display_static_question(q: Dict[str, Any]) -> None:
    """Render a formatted, read-only view of a question."""
    # Answer options
    st.markdown("**Answer options**")
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
