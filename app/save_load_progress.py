# save_load_progress.py
import json
import datetime as dt
import streamlit as st
from typing import Any

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
    "los",
    "questions",
    # "questions_sig",
    "include_opts",
    "active_tool",
    "outliner_step",
    "builder_step",
    # "prev_build_inc_opts",
    # "docx_file",
}

CURRENT_SAVE_VERSION = 1

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
    "los": lambda value: _normalize_list("los", value),
    "questions": lambda value: _normalize_dict("questions", value),
    "include_opts": lambda value: _normalize_dict("include_opts", value),
    "active_tool": lambda value: _normalize_str("active_tool", value),
    "outliner_step": lambda value: _normalize_str("outliner_step", value),
    "builder_step": lambda value: _normalize_str("builder_step", value),
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
        # Placeholder for future migrations, e.g.:
        # if version == 1:
        #     migrated = _migrate_v1_to_v2(migrated)
        #     version = 2
        raise ValueError(
            f"Invalid save file: migration path for version {version} not implemented"
        )

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
            file_name=f"{fname}.json",
            mime="application/json",
            disabled=not fname
        )

def load_progress_ui():
    with st.form("load_form", clear_on_submit=True):
        uploaded = st.file_uploader("Choose file (.json)", type=["json"])
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
