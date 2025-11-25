"""Utilities for managing Streamlit session state and computing signatures."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List, MutableMapping, Optional
from streamlit.runtime.state import SessionStateProxy
import streamlit as st

######## Signature computation helpers ########

def sig_outline(outline: Optional[Dict[str, Any]]) -> str:
    """Stable signature for generated outline content."""
    if not outline:
        return ""
    serialized = json.dumps(outline, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()


def sig_module(text: Optional[str]) -> str:
    """Return a stable signature for the uploaded module text."""
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()


def sig_alignment(lo_text: str, intended_level: str, module_sig: str) -> str:
    """Signature capturing inputs that influence Bloom alignment checks."""
    payload = f"{lo_text}||{intended_level}||{module_sig}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def sig_question_gen(final_lo_text: str, intended_level: str, module_sig: str) -> str:
    """Signature capturing inputs that influence question generation."""
    payload = f"{final_lo_text}||{intended_level}||{module_sig}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def sig_questions(questions_by_lo: Dict[str, Iterable[Dict[str, Any]]]) -> str:
    """Stable signature encompassing all editable question fields."""
    parts: List[str] = []
    for lo_id in sorted(questions_by_lo.keys()):
        qs = list(questions_by_lo.get(lo_id) or [])
        for qi, question in enumerate(qs):
            parts.append(f"{lo_id}#{qi}|stem:{question.get('stem', '')}")
            parts.append(f"{lo_id}#{qi}|correct:{question.get('correct_option_id', '')}")
            parts.append(f"{lo_id}#{qi}|contentRef:{question.get('contentReference', '')}")
            parts.append(f"{lo_id}#{qi}|cog:{question.get('cognitive_rationale', '')}")
            for option in sorted(question.get("options", []), key=lambda opt: opt.get("id", "")):
                opt_id = option.get("id", "")
                parts.append(f"{lo_id}#{qi}|opt:{opt_id}|txt:{option.get('text', '')}")
                parts.append(f"{lo_id}#{qi}|opt:{opt_id}|rat:{option.get('option_rationale', '')}")
    payload = "\n".join(parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()

####### Navigation helpers ########
def compute_step_readiness(ss: SessionStateProxy) -> None:
    """Compute baseline readiness for each step from session state before rendering the stepper.
    This ensures the top stepper reflects current state even though it's rendered before step content.
    """
    # Ensure list shape (index 0 unused; steps 1..5 use indices 1..5)
    if "is_ready_for_step" not in ss or not isinstance(ss["is_ready_for_step"], list) or len(ss["is_ready_for_step"]) < 6:
        ss["is_ready_for_step"] = [True]*3 + [False]*3

    # Step 1 is always reachable
    ss["is_ready_for_step"][1] = True

    # Step 2: always reachable (Step 1 can be skipped entirely)
    ss["is_ready_for_step"][2] = True
    #ss["is_ready_for_step"][2] = bool(ss.get("outline")) or bool(ss.get("course_text"))

    # Step 3: ready if module text has been provided (upload or import)
    ss["is_ready_for_step"][3] = bool(ss.get("module_text"))

    # Step 4: ready if there are learning objectives and all have been accepted/finalized
    los = ss.get("los", [])
    ss["is_ready_for_step"][4] = bool(los) and all(lo.get("final_text") for lo in los)

    # Step 5: ready if questions exist
    ss["is_ready_for_step"][5] = bool(ss.get("questions"))

####### Session state manipulation helpers ########

def clear_outline_widget_state(ss: SessionStateProxy) -> None:
    """Remove cached widget state tied to a previous outline."""
    keys_to_remove = [key for key in ss.keys() if str(key).startswith("outline__")]
    for key in keys_to_remove:
        del ss[key]


def clear_alignment(ss: SessionStateProxy, lo: Dict[str, Any]) -> None:
    """Remove alignment-related fields for a learning objective."""
    lo.pop("alignment", None)
    lo.pop("final_text", None)
    lo.pop("alignment_sig", None)
    lo.pop("generation_sig", None)
    if f"sug_{lo.get('id')}" in ss:
        ss.pop(f"sug_{lo.get('id')}", None)


def clear_questions(ss: SessionStateProxy, lo_id: Optional[str] = None) -> None:
    """Clear generated questions and dependent artifacts."""
    questions = ss.get("questions")
    if isinstance(questions, MutableMapping):
        if lo_id:
            questions.pop(lo_id, None)
        else:
            questions.clear()
            ss.pop("questions_sig", None)
    else:
        if not lo_id:
            ss.pop("questions", None)
            ss.pop("questions_sig", None)

    ss.pop("docx_file", "")
    include_opts = ss.get("include_opts")
    if isinstance(include_opts, MutableMapping):
        include_opts.clear()
    else:
        ss.pop("include_opts", None)

    prev_opts = ss.get("prev_build_inc_opts")
    if isinstance(prev_opts, MutableMapping):
        prev_opts.clear()
    else:
        ss.pop("prev_build_inc_opts", None)


def clear_module_dependent_outputs(ss: SessionStateProxy) -> None:
    """Clear all outputs that depend on uploaded module content."""
    ss["__last_clear_reason__"] = "module_sig_changed"
    los = ss.get("los")
    if isinstance(los, list):
        los.clear()
    else:
        ss["los"] = []
    clear_questions(ss)


def apply_module_content(ss: SessionStateProxy, text: Optional[str], tokens: Optional[int], file_names: Optional[List[str]]) -> None:
    """Update session state with new module content and clear dependents if needed."""
    text = text or ""
    tokens = tokens or 0
    file_names = file_names or []

    new_mod_sig = sig_module(text)
    current_sig = ss.get("module_sig")

    if current_sig and new_mod_sig != current_sig:
        st.toast("Module content changed — LOs and questions cleared.")
        clear_module_dependent_outputs(ss)

    ss["module_files"] = file_names
    ss["module_text"] = text
    ss["module_tokens"] = tokens
    ss["module_sig"] = new_mod_sig


def reset_uploaded_content(ss: SessionStateProxy) -> None:
    """Remove uploaded module data and reset uploader widget."""
    ss["course_files"] = []
    ss["module_files"] = []
    ss["outline_guidance"] = ""
    ss.pop("outline_guidance_key", None)
    ss["course_text"] = ""
    ss["course_tokens"] = 0
    ss["module_text"] = ""
    ss["module_tokens"] = 0
    ss["module_sig"] = ""
    ss["uploader_key"] = ss.get("uploader_key", 0) + 1


######## Learning objective helpers ########

def update_lo_from_widgets(ss: SessionStateProxy, lo: Dict[str, Any], new_text: str, new_level: str) -> None:
    """Apply widget values to an LO and clear dependent artifacts when signatures change."""
    lo["text"] = new_text
    lo["intended_level"] = new_level

    module_sig = ss.get("module_sig", "")
    current_align_sig = sig_alignment(new_text, new_level, module_sig)
    prev_align_sig = lo.get("alignment_sig")

    if prev_align_sig and prev_align_sig != current_align_sig:
        clear_alignment(ss, lo)
        clear_questions(ss, lo["id"])
        lo["final_text"] = None


def finalize_lo(ss: SessionStateProxy, lo: Dict[str, Any]) -> None:
    """Mark a learning objective as final and manage question signatures."""
    lo["final_text"] = lo.get("text")
    module_sig = ss.get("module_sig", "")
    current_gen_sig = sig_question_gen(lo.get("final_text"), lo.get("intended_level", ""), module_sig)
    prev_gen_sig = lo.get("generation_sig")

    if prev_gen_sig and prev_gen_sig != current_gen_sig:
        clear_questions(ss, lo["id"])

    lo["generation_sig"] = current_gen_sig


def reopen_lo(lo: Dict[str, Any]) -> None:
    """Allow editing of a previously finalized learning objective."""
    lo["final_text"] = None


def reset_lo_questions(ss: SessionStateProxy, lo: Dict[str, Any]) -> None:
    """Clear generated questions and invalidate the LO generation signature."""
    clear_questions(ss, lo.get("id"))
    lo["generation_sig"] = None


def apply_alignment_result(ss: SessionStateProxy, lo: Dict[str, Any], alignment_result: Dict[str, Any]) -> None:
    """Persist an alignment result and update its signature for the current LO state."""
    lo["alignment"] = alignment_result
    lo["alignment_sig"] = sig_alignment(lo["text"], lo["intended_level"], ss.get("module_sig", ""))
