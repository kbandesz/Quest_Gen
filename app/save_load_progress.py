# save_load_progress.py
import json
import datetime as dt
import streamlit as st
from typing import Any, Dict

# Alias for convenience
ss = st.session_state

# ---- State serialization ---------------------------------------------------

# Only persist domain-specific state that is required to rebuild the UI.
# Widget keys, uploader state, temporary helpers, etc. are intentionally
# excluded so that rehydrating the session only brings back durable data.
DOMAIN_STATE_KEYS = {
    "MOCK_MODE",
    # "__prev_mock_mode__",
    "OPENAI_MODEL",
    "course_files",
    "course_text",
    "course_tokens",
    "outline_guidance",
    "outline",
    # "outline_sig",
    # "outline_doc_sig",
    # "outline_docx_file",
    "module_files",
    "module_text",
    "module_tokens",
    "module_sig",
    "lo_material_files",
    "lo_material_text",
    "lo_material_tokens",
    "lo_material_sig",
    "los",
    "questions",
    # "questions_sig",
    "include_opts",
    "tool_step",
    "knowledge_base_step",
    "outliner_step",
    "lo_analysis_step",
    "builder_step",
    "knowledge_files",
    "tool_file_selection",
    # "prev_build_inc_opts",
    # "docx_file",
}

CURRENT_SAVE_VERSION = 2

_PERSISTED_KEY_NORMALIZERS = {
    "MOCK_MODE": lambda value: _normalize_bool("MOCK_MODE", value),
    "OPENAI_MODEL": lambda value: _normalize_str("OPENAI_MODEL", value),
    "course_files": lambda value: _normalize_list("course_files", value),
    "course_text": lambda value: _normalize_str("course_text", value),
    "course_tokens": lambda value: _normalize_int("course_tokens", value),
    "outline_guidance": lambda value: _normalize_str("outline_guidance", value),
    "outline": lambda value: _normalize_dict("outline", value),
    "module_files": lambda value: _normalize_list("module_files", value),
    "module_text": lambda value: _normalize_str("module_text", value),
    "module_tokens": lambda value: _normalize_int("module_tokens", value),
    "module_sig": lambda value: _normalize_str("module_sig", value),
    "lo_material_files": lambda value: _normalize_list("lo_material_files", value),
    "lo_material_text": lambda value: _normalize_str("lo_material_text", value),
    "lo_material_tokens": lambda value: _normalize_int("lo_material_tokens", value),
    "lo_material_sig": lambda value: _normalize_str("lo_material_sig", value),
    "los": lambda value: _normalize_list("los", value),
    "questions": lambda value: _normalize_dict("questions", value),
    "include_opts": lambda value: _normalize_dict("include_opts", value),
    "tool_step": lambda value: _normalize_str("tool_step", value),
    "knowledge_base_step": lambda value: _normalize_str("knowledge_base_step", value),
    "outliner_step": lambda value: _normalize_str("outliner_step", value),
    "lo_analysis_step": lambda value: _normalize_str("lo_analysis_step", value),
    "builder_step": lambda value: _normalize_str("builder_step", value),
    "knowledge_files": lambda value: _normalize_dict("knowledge_files", value),
    "tool_file_selection": lambda value: _normalize_dict("tool_file_selection", value),
}


def _normalize_str(key: str, value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    raise ValueError(f"Invalid save file: key '{key}' must be a string")


def _normalize_bool(key: str, value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    raise ValueError(f"Invalid save file: key '{key}' must be a boolean")


def _normalize_int(key: str, value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        raise ValueError(f"Invalid save file: key '{key}' must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError(f"Invalid save file: key '{key}' must be an integer")


def _normalize_list(key: str, value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    raise ValueError(f"Invalid save file: key '{key}' must be a list")


def _normalize_dict(key: str, value: Any) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    raise ValueError(f"Invalid save file: key '{key}' must be an object")


def _migrate_saved_payload(version: int, payload: dict) -> dict:
    """Run schema migrations and return a payload in CURRENT_SAVE_VERSION format."""
    if version > CURRENT_SAVE_VERSION:
        raise ValueError(
            f"Invalid save file: unsupported version {version} (max {CURRENT_SAVE_VERSION})"
        )

    migrated = dict(payload)
    while version < CURRENT_SAVE_VERSION:
        if version == 1:
            migrated_state = dict(migrated.get("state", {}))
            migrated_state.setdefault("knowledge_base_step", "Upload")

            knowledge_files = dict(migrated_state.get("knowledge_files") or {})
            tool_file_selection = dict(migrated_state.get("tool_file_selection") or {})

            def _make_unique_name(base_name: str, existing: Dict[str, dict]) -> str:
                if base_name not in existing:
                    return base_name
                stem, dot, suffix = base_name.rpartition(".")
                stem = stem if dot else base_name
                ext = f".{suffix}" if dot else ""
                idx = 1
                while f"{stem}_{idx}{ext}" in existing:
                    idx += 1
                return f"{stem}_{idx}{ext}"

            def _seed_from_legacy(tool_name: str, text_key: str, tokens_key: str, files_key: str, fallback_name: str) -> None:
                legacy_text = (migrated_state.get(text_key) or "").strip()
                if not legacy_text:
                    return

                legacy_files = [name for name in (migrated_state.get(files_key) or []) if isinstance(name, str) and name.strip()]
                candidate_name = legacy_files[0] if len(legacy_files) == 1 else fallback_name
                kb_name = _make_unique_name(candidate_name, knowledge_files)
                knowledge_files[kb_name] = {
                    "name": kb_name,
                    "text": legacy_text,
                    "tokens": int(migrated_state.get(tokens_key) or 0),
                    "size": len(legacy_text.encode("utf-8")),
                    "migrated_from_v1": True,
                }

                selected = [name for name in (tool_file_selection.get(tool_name) or []) if isinstance(name, str)]
                if kb_name not in selected:
                    selected.append(kb_name)
                tool_file_selection[tool_name] = selected

            _seed_from_legacy("Course Outliner", "course_text", "course_tokens", "course_files", "migrated_course_materials.txt")
            _seed_from_legacy("Learning Objective Analysis", "lo_material_text", "lo_material_tokens", "lo_material_files", "migrated_lo_materials.txt")
            _seed_from_legacy("Assessment Builder", "module_text", "module_tokens", "module_files", "migrated_module_materials.txt")

            tool_file_selection.setdefault("Course Outliner", [])
            tool_file_selection.setdefault("Learning Objective Analysis", [])
            tool_file_selection.setdefault("Assessment Builder", [])

            migrated_state["knowledge_files"] = knowledge_files
            migrated_state["tool_file_selection"] = tool_file_selection
            migrated["state"] = migrated_state
            migrated["version"] = 2
            version = 2
            continue

        raise ValueError(f"Invalid save file: migration path for version {version} not implemented")

    return migrated


def _normalize_saved_payload(saved_state: dict) -> dict:
    if not isinstance(saved_state, dict):
        raise ValueError("Invalid save file: payload must be a JSON object")

    version = saved_state.get("version", 1)
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError("Invalid save file: 'version' must be an integer")

    migrated = _migrate_saved_payload(version, saved_state)

    data = migrated.get("state")
    if not isinstance(data, dict):
        raise ValueError("Invalid save file: missing 'state' payload")

    normalized = {}
    for key in DOMAIN_STATE_KEYS:
        if key not in data:
            continue
        normalizer = _PERSISTED_KEY_NORMALIZERS.get(key)
        if normalizer is None:
            continue
        normalized[key] = normalizer(data[key])

    return {
        "version": CURRENT_SAVE_VERSION,
        "state": normalized,
    }


def _is_jsonable(x: Any) -> bool:
    PRIMS = (str, int, float, bool, type(None))
    if isinstance(x, PRIMS):
        return True
    if isinstance(x, (list, tuple)):
        return all(_is_jsonable(i) for i in x)
    if isinstance(x, dict):
        return all(isinstance(k, str) and _is_jsonable(v) for k, v in x.items())
    return False

def exportable_state() -> dict:
    """Return a JSON-serializable snapshot of durable session state."""
    out = {}
    for key in sorted(DOMAIN_STATE_KEYS):
        if key not in ss:
            continue
        value = ss[key]
        if _is_jsonable(value):
            out[key] = value
    return {
        "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
        "state": out,
        "version": CURRENT_SAVE_VERSION,
    }

def restore_state(saved_state: dict):
    normalized_payload = _normalize_saved_payload(saved_state)
    data = normalized_payload["state"]

    # Clear session state so we mirror the saved snapshot
    #for key in DOMAIN_STATE_KEYS:
    #    ss.pop(key, None)

    ss.clear()

    for key in DOMAIN_STATE_KEYS:
        if key in data:
            ss[key] = data[key]

    # Always return users to the first surface of the outliner after restore
    ss["active_tool"] = "Course Outliner"
    ss["outliner_step"] = "Materials"
    ss["lo_analysis_step"] = "Materials"
    ss["builder_step"] = "Materials"


def apply_pending_restore():
    payload = ss.pop("__PENDING_RESTORE__", None)
    if payload:
        try:
            restore_state(payload)
        except Exception as exc:
            st.error(f"Could not restore saved session: {exc}")
            return
        # Remount file uploaders fresh
        ss["uploader_key"] = ss.get("uploader_key", 0) + 1
        st.rerun()                     # one more rerun so the UI binds to restored values


# ---- UI widgets ------------------------------------------------------------
def save_progress_ui():
    if "fname_key" not in ss:
        ss["fname_key"] = "saved_progress"
    with st.container(border=True):
        fname = st.text_input("File name", key="fname_key").strip()

        payload = json.dumps(exportable_state(), ensure_ascii=False, indent=2)

        st.download_button(
            "Save",
            data=payload.encode("utf-8"),
            file_name=f"{fname}.bcn",
            mime="application/json",
            disabled=not fname
        )

def load_progress_ui():
    with st.form("load_form", clear_on_submit=True):
        uploaded = st.file_uploader("Choose file (.bcn)", type=["bcn"])
        submitted = st.form_submit_button("Load", key="load_state_btn")
        if submitted and uploaded:
            try:
                saved_state = json.load(uploaded)
                ss["__PENDING_RESTORE__"] = saved_state
                st.rerun()
            except Exception as e:
                st.error(f"Could not load file: {e}")

# ---- Compose both in your app ---------------------------------------------

def save_load_panel():
    st.divider()
    st.markdown("### 💾 Save session")
    save_progress_ui()

    #st.divider()
    st.markdown("### 📤 Load session")
    load_progress_ui()
