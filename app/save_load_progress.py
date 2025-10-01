# save_load_progress.py
import json
import datetime as dt
import streamlit as st
from typing import Any

# Alias for convenience
ss = st.session_state

# ---- State serialization ---------------------------------------------------
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
    """Return a JSON-serializable snapshot of st.session_state."""
    out = {}
    for k, v in ss.items():
        # skip write-protected / transient widget keys and binaries
        if k.endswith("_btn") or "file_uploader" in k or k =="docx_file": #,"processed_file_keys"}:
            continue
        if _is_jsonable(v):
            out[k] = v
    return {
        "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
        "state": out
    }

def restore_state(saved_state: dict):
    data = saved_state.get("state", {})
    for k, v in data.items():
        ss[k] = v


def apply_pending_restore():
    payload = ss.pop("__PENDING_RESTORE__", None)
    if payload:
        restore_state(payload)
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
                saved_state["state"]["current_step"] = 1 # bump back to first page
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

