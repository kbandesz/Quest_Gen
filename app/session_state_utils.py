"""Utilities for managing Streamlit session state and computing signatures."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List, MutableMapping, Optional

import streamlit as st

SessionState = MutableMapping[str, Any]


def sig_module(text: Optional[str]) -> str:
    """Return a stable signature for the uploaded module text."""
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()


def sig_alignment(lo_text: str, intended_level: str, module_sig: str) -> str:
    """Signature capturing inputs that influence alignment checks."""
    payload = f"{lo_text}||{intended_level}||{module_sig}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def sig_generation(final_lo_text: str, intended_level: str, module_sig: str) -> str:
    """Signature capturing inputs that influence question generation."""
    payload = f"{final_lo_text}||{intended_level}||{module_sig}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def sig_outline(outline: Optional[Dict[str, Any]]) -> str:
    """Stable signature for generated outline content."""
    if not outline:
        return ""
    serialized = json.dumps(outline, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()


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


def clear_alignment(ss: SessionState, lo: Dict[str, Any]) -> None:
    """Remove alignment-related fields for a learning objective."""
    lo.pop("alignment", None)
    lo.pop("final_text", None)
    lo.pop("alignment_sig", None)
    lo.pop("generation_sig", None)
    if f"sug_{lo.get('id')}" in ss:
        ss.pop(f"sug_{lo.get('id')}", None)


def clear_questions(ss: SessionState, lo_id: Optional[str] = None) -> None:
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


def clear_module_dependent_outputs(ss: SessionState) -> None:
    """Clear all outputs that depend on uploaded module content."""
    ss["__last_clear_reason__"] = "module_sig_changed"
    los = ss.get("los")
    if isinstance(los, list):
        los.clear()
    else:
        ss["los"] = []
    clear_questions(ss)


def apply_module_content(ss: SessionState, text: Optional[str], tokens: Optional[int], file_names: Optional[List[str]]) -> None:
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


def reset_uploaded_content(ss: SessionState) -> None:
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
