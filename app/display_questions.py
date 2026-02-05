"""UI elements to display AI-generated questions in editable and static formats."""

from typing import Any, Dict, List
import streamlit as st


def create_empty_question() -> Dict[str, Any]:
    """Return a blank question scaffold for manual authoring."""
    return {
        "stem": "",
        "options": [
            {"id": "A", "text": "", "option_rationale": ""},
            {"id": "B", "text": "", "option_rationale": ""},
            {"id": "C", "text": "", "option_rationale": ""},
            {"id": "D", "text": "", "option_rationale": ""},
        ],
        "correct_option_id": "A",
        "contentReference": "",
        "cognitive_rationale": "",
    }


def display_editable_question(lo_id: str, idx: int, q: Dict[str, Any]) -> bool:
    """
    Render a question with editable fields for stem, options, and metadata.
    Args:
        lo_id: The LO ID associated with the question (for unique key generation).
        idx: The index of the question (for unique key generation).
        q: The question data dictionary to be edited.
    """
    stem_cols = st.columns([1, 30], vertical_alignment="center")
    with stem_cols[0]:
        delete_clicked = st.button("", icon="❌",key=f"delete_q_{lo_id}_{idx}", help="Delete this question")
    with stem_cols[1]:
        q["stem"] = st.text_area(
            "Question",
            q.get("stem", ""),
            height=70,
            label_visibility="collapsed",
            key=f"stem_{lo_id}_{idx}",
        )
    # Answer options
    for opt in q.get("options", []):
        cols = st.columns([1, 30], vertical_alignment="center")
        with cols[0]:
            st.markdown(
                f"<span style='white-space:nowrap; font-weight:600;'>({opt['id']})</span>", # <--- Keep option ID on one line and bold
                unsafe_allow_html=True,
                )
        with cols[1]:
            opt["text"] = st.text_input(
                "",
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
    return delete_clicked


def clear_reindexed_question_widget_state(
    lo_id: str,
    start_idx: int,
    questions: List[Dict[str, Any]],
) -> None:
    """Clear widget state for question rows whose indices shift after deletion."""
    if start_idx < 0 or start_idx >= len(questions):
        return

    option_ids: set[str] = {"A", "B", "C", "D"}
    for question in questions[start_idx:]:
        for opt in question.get("options", []):
            opt_id = str(opt.get("id", "")).strip()
            if opt_id:
                option_ids.add(opt_id)

    for idx in range(start_idx, len(questions)):
        fixed_keys = [
            f"delete_q_{lo_id}_{idx}",
            f"stem_{lo_id}_{idx}",
            f"correct_option_{lo_id}_{idx}",
            f"content_reference_{lo_id}_{idx}",
            f"cognitive_rationale_{lo_id}_{idx}",
        ]
        for key in fixed_keys:
            st.session_state.pop(key, None)

        for opt_id in option_ids:
            st.session_state.pop(f"opt_text_{lo_id}_{idx}_{opt_id}", None)
            st.session_state.pop(f"option_rationale_{lo_id}_{idx}_{opt_id}", None)

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
