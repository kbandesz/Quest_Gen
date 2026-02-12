"""UI elements to display AI-generated questions in editable and static formats."""

from typing import Any, Dict, Iterable
from uuid import uuid4
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
        "_widget_id": uuid4().hex,
    }


def _ensure_question_widget_id(q: Dict[str, Any]) -> str:
    """Return a stable per-question widget identifier."""
    widget_id = q.get("_widget_id")
    if not widget_id:
        widget_id = uuid4().hex
        q["_widget_id"] = widget_id
    return str(widget_id)


def _question_widget_keys(lo_id: str, widget_id: str) -> Iterable[str]:
    """Yield all Streamlit widget state keys used by one question widget group."""
    key_prefix = f"{lo_id}_{widget_id}"
    yield f"delete_q_{key_prefix}"
    yield f"stem_{key_prefix}"
    yield f"correct_option_{key_prefix}"
    yield f"content_reference_{key_prefix}"
    yield f"cognitive_rationale_{key_prefix}"
    for option_id in ["A", "B", "C", "D"]:
        yield f"opt_text_{key_prefix}_{option_id}"
        yield f"option_rationale_{key_prefix}_{option_id}"


def clear_deleted_question_widget_state(lo_id: str, q: Dict[str, Any]) -> None:
    """Remove session-state widget values for a deleted question.

    This prevents stale values from previously deleted question widgets from
    being re-used when the app reruns.
    """
    widget_id = q.get("_widget_id")
    if not widget_id:
        return

    for key in _question_widget_keys(lo_id, str(widget_id)):
        st.session_state.pop(key, None)


def display_editable_question(lo_id: str, idx: int, q: Dict[str, Any]) -> bool:
    """
    Render a question with editable fields for stem, options, and metadata.
    Args:
        lo_id: The LO ID associated with the question (for key namespacing).
        idx: The index of the question (for display ordering only).
        q: The question data dictionary to be edited.
    """
    widget_id = _ensure_question_widget_id(q)
    key_prefix = f"{lo_id}_{widget_id}"

    stem_cols = st.columns([1, 30], vertical_alignment="center")
    with stem_cols[0]:
        delete_clicked = st.button("", icon="❌",key=f"delete_q_{key_prefix}", help="Delete this question")
    with stem_cols[1]:
        q["stem"] = st.text_area(
            "Question",
            q.get("stem", ""),
            height=70,
            label_visibility="collapsed",
            key=f"stem_{key_prefix}",
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
                key=f"opt_text_{key_prefix}_{opt['id']}",
            )
    # Correct answer
    current = ["A", "B", "C", "D"].index(q.get("correct_option_id", "A"))
    q["correct_option_id"] = st.radio(
        "Correct option",
        ["A", "B", "C", "D"],
        index=current,
        horizontal=True,
        key=f"correct_option_{key_prefix}",
    )
    # Feedback for each option
    st.markdown("Feedback")
    for opt in q.get("options", []):
        opt["option_rationale"] = st.text_area(
            f"**({opt['id']})**",
            opt.get("option_rationale", ""),
            height=70,
            key=f"option_rationale_{key_prefix}_{opt['id']}",
        )
    # Content reference and cognitive rationale
    q["contentReference"] = st.text_area(
        "Content reference",
        q.get("contentReference", ""),
        height=70,
        key=f"content_reference_{key_prefix}",
    )
    q["cognitive_rationale"] = st.text_area(
        "Rationale for Bloom level",
        q.get("cognitive_rationale", ""),
        height=70,
        key=f"cognitive_rationale_{key_prefix}",
    )
    return delete_clicked


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
