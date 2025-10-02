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
    "__prev_mock_mode__",
    "OPENAI_MODEL",
    "course_files",
    "course_text",
    "course_tokens",
    "outline_guidance",
    "generated_outline",
    "module_files",
    "module_text",
    "module_tokens",
    "module_sig",
    "los",
    "questions",
    "questions_sig",
    "include_opts",
    "prev_build_inc_opts",
    "docx_file",
    "n_questions",
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
        "version": 1,
    }

def restore_state(saved_state: dict):
    data = saved_state.get("state", {})
    if not isinstance(data, dict):
        raise ValueError("Invalid save file: missing 'state' payload")

    # Clear any previously stored domain keys so we mirror the saved snapshot
    for key in DOMAIN_STATE_KEYS:
        ss.pop(key, None)

    for key in DOMAIN_STATE_KEYS:
        if key in data:
            ss[key] = data[key]

    # Always return to the first step so users re-orient themselves
    ss["current_step"] = 1


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
                saved_at = saved_state.get('saved_at','?')
                ss["__PENDING_RESTORE__"] = saved_state
                st.success(f"Progress saved at {saved_at} loaded. Applying…")
                st.rerun()
            except Exception as e:
                st.error(f"Could not load file: {e}")

# ---- Compose both in your app ---------------------------------------------

def save_load_panel():
    st.divider()
    st.markdown("### 💾 Save your progress")
    save_progress_ui()

    st.divider()
    st.markdown("### 📤 Load saved session")
    load_progress_ui()

