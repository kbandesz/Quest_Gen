import streamlit as st
import io, os, uuid
from typing import List, Dict, Optional
from dotenv import load_dotenv
import hashlib

from app.parsing import extract_text_and_tokens
from app.generation import check_alignment, generate_questions, set_runtime_config
from app.export import build_docx
import app.constants as const

# Load environment variables (OpenAI API key) from .env
load_dotenv()

# Cached file parsing
@st.cache_data(show_spinner=False)
def _extract_cached_text_and_tokens(file_keys, files):
    """Cache extraction results keyed by stable file metadata."""
    return extract_text_and_tokens(files)


# Signatures used for detecting changes in user inputs
def _sig_module(text: str) -> str:
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()

def _sig_alignment(lo_text: str, intended_level: str, module_sig: str) -> str:
    # Alignment depends on original LO text + intended level + course text
    payload = f"{lo_text}||{intended_level}||{module_sig}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()

def _sig_generation(final_lo_text: str, intended_level: str, module_sig: str) -> str:
    # Generation depends on final LO text + intended level + module text
    payload = f"{final_lo_text}||{intended_level}||{module_sig}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()

def _sig_questions(questions_by_lo: Dict[str, list]) -> str:
    """Stable signature over all editable question fields."""
    
    parts = []
    # Sort by LO id for stability
    for lo_id in sorted(questions_by_lo.keys()):
        qs = questions_by_lo.get(lo_id) or []
        for qi, q in enumerate(qs):
            parts.append(f"{lo_id}#{qi}|stem:{q.get('stem','')}")
            parts.append(f"{lo_id}#{qi}|correct:{q.get('correct_option_id','')}")
            parts.append(f"{lo_id}#{qi}|contentRef:{q.get('contentReference','')}")
            parts.append(f"{lo_id}#{qi}|cog:{q.get('cognitive_rationale','')}")
            # Options in stable order by option id (A,B,C,D)
            for opt in sorted(q.get('options', []), key=lambda o: o.get('id','')):
                parts.append(f"{lo_id}#{qi}|opt:{opt.get('id','')}|txt:{opt.get('text','')}")
                parts.append(f"{lo_id}#{qi}|opt:{opt.get('id','')}|rat:{opt.get('option_rationale','')}")
    blob = "\n".join(parts)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


################################################
# App setup
################################################
st.set_page_config(page_title="QGenAi", page_icon=":mortar_board:", layout="wide", initial_sidebar_state="collapsed")
st.title(":mortar_board: QGenAi")
st.write("_The AI-Aid to Write Instructionally Sound Learning Objectives and Assessment Questions_")

# Initialize session state
ss = st.session_state
ss.setdefault("current_step", 1)
ss.setdefault("uploader_key", 0)  # to force reset of uploader widget
ss.setdefault("uploaded_files", [])
ss.setdefault("processed_file_keys", None)
ss.setdefault("module_text", "")
ss.setdefault("module_tokens", 0)
ss.setdefault("module_sig", "")
ss.setdefault("los", [])
ss.setdefault("questions", {})
ss.setdefault("questions_sig", None)
ss.setdefault("docx_file", None)

ss.setdefault("MOCK_MODE", True)
ss.setdefault("__prev_mock_mode__", ss["MOCK_MODE"])
ss.setdefault("OPENAI_MODEL", "gpt-4.1-nano")

# Apply runtime config to generation module on each rerun (current values)
set_runtime_config(ss["MOCK_MODE"], ss["OPENAI_MODEL"])

# Banner based on current mock setting
if ss["MOCK_MODE"]:
    st.warning(f"⚠️ MOCK MODE is ON — course material and AI responses are canned.")
st.text("")


# --------------------------------------------------------------
# Helpers for clearing derived state
# --------------------------------------------------------------
def clear_alignment(lo: Dict) -> None:
    """Remove alignment-related fields for a learning objective."""
    lo.pop("alignment", None)
    lo.pop("final_text", None)
    lo.pop("alignment_sig", None)
    lo.pop("generation_sig", None)
    ss.pop(f"sug_{lo['id']}", None)


def clear_questions(lo_id: Optional[str] = None) -> None:
    """Clear generated questions and dependent artifacts."""
    if lo_id:
        ss["questions"].pop(lo_id, None)
    else:
        ss["questions"].clear()
    ss.pop("docx_file", None)
    ss.pop("questions_sig", None)


def clear_module_dependent_outputs() -> None:
    """Clear all outputs that depend on uploaded module content."""
    ss["los"].clear()
    clear_questions()


def reset_uploaded_content() -> None:
    """Remove uploaded module data and reset uploader widget."""
    ss["uploaded_files"] = []
    ss["processed_file_keys"] = None
    ss["module_text"] = ""
    ss["module_tokens"] = 0
    ss["module_sig"] = ""
    ss["uploader_key"] += 1

################################################
# Sidebar for settings
################################################
with st.sidebar:
    if st.button("Reset session"):
        ss["uploader_key"] += 1
        ss.clear()
        st.rerun()

    # Change handler: apply model/mock and invalidate downstream state
    def _on_settings_change():
        prev_mock = ss.get("__prev_mock_mode__", ss["MOCK_MODE"])
        # 1) apply to generation runtime
        set_runtime_config(ss["MOCK_MODE"], ss["OPENAI_MODEL"])
        # 2) invalidate downstream state

        # If mock mode was toggled, clear everything and go back to Step 1
        if prev_mock != ss["MOCK_MODE"]:
            clear_module_dependent_outputs()
            reset_uploaded_content()
            ss["current_step"] = 1
            st.toast("Mock mode changed — cleared all uploaded content, LOs, and LLM output.")
        # If AI model changed, just clear LLM outputs
        else:
            for lo in ss.get("los", []):
                clear_alignment(lo)
            clear_questions()
            st.toast("Model changed — cleared all LLM output.")
        ss["__prev_mock_mode__"] = ss["MOCK_MODE"]
        # Flag for optional notice after rerun
        #ss["__settings_changed__"] = True

    st.markdown("### Runtime Settings")

    st.toggle("Mock mode", key="MOCK_MODE", on_change=_on_settings_change)
    model_options = ["gpt-4.1-nano", "gpt-4.1-mini", "gpt-4.1"]
    st.selectbox("OpenAI model", model_options, key="OPENAI_MODEL", on_change=_on_settings_change)

    # Show confirmation if settings were just changed
    # if ss.pop("__settings_changed__", False):
    #     st.warning("Settings changed — cleared any Bloom alignment and questions.")


################################################
# Visual Stepper
################################################
def render_stepper():

    upload = """
**📂 Upload**  
Add your course material files
"""

    LOs = """
**🎯 Objectives**  
Define and analyze learning objectives
"""

    generate = """
**✍️ Questions**  
Create questions with AI support
"""
    export = """
**📄 Download**  
Export questions to Microsoft Word
        """

    steps = [upload, LOs, generate, export]
    cols = st.columns(len(steps))
    for i, (col, step_name) in enumerate(zip(cols, steps)):
        with col:
            if i + 1 == ss["current_step"]:
                st.info(f"{step_name}")
            elif i + 1 < ss["current_step"]:
                st.success(f"{step_name}")
            else:
                st.markdown(f"{step_name}")

################################################
# 1 Upload Course Content
################################################
def render_step_1():
    help_upload = """**Tip:** You can upload any content that you will use to develop the course.
                A draft module plan works best, but you can also upload background papers, guidance notes,
                presentations, or any other documents that you plan to use for writing the course content."""
    st.header("📂 Upload Course Material", help=help_upload)

    files=st.file_uploader(
        "Maximum 27,000 tokens of text (about 20,000 words or 40 single-spaced pages)",
        type=["pdf","docx","pptx","txt"],
        accept_multiple_files=True,
        key=f"file_uploader_{ss["uploader_key"]}",
        disabled=ss["MOCK_MODE"]
        ) or []
    # In mock mode, override with the mock file
    if ss["MOCK_MODE"]:
        files = [const.load_mock_file()]

    # Compute a stable signature for the current files (for cache keying)
    current_file_keys = tuple((f.name, f.size, getattr(f, "last_modified", None)) for f in files)


    # Process files if they have actually changed.
    if files and current_file_keys != ss["processed_file_keys"]:
        if ss["processed_file_keys"] is not None:
            st.toast("Module content changed — LOs and questions cleared.")
        clear_module_dependent_outputs()
        ss["processed_file_keys"] = current_file_keys
        ss["uploaded_files"] = files
        try:
            text, tokens = _extract_cached_text_and_tokens(current_file_keys, files)
        except Exception as e:
            st.error(e)
            text, tokens = "", 0

        # Persist the latest parse
        ss["module_text"] = text
        ss["module_tokens"] = tokens
        prev_mod_sig = ss.get("module_sig", "")
        new_mod_sig = _sig_module(text)
        ss["module_sig"] = new_mod_sig

        if tokens > const.MODULE_TOKEN_LIMIT:
            st.error(f"Module exceeds {const.MODULE_TOKEN_LIMIT:,} tokens. Reduce content to proceed.")
        else:
            # Invalidate only if the *actual parsed text* changed
            #if prev_mod_sig and prev_mod_sig != new_mod_sig:
               # invalidate_module_outputs()
                if ss.get("los"):
                    st.info("Module content changed — LOs and questions cleared.")

    # Display currently uploaded files from the session state (stable across reruns)
    if ss["uploaded_files"]:
        st.caption("Currently uploaded files (To change, use file picker above):")
        current_files = "\n".join([f"{i+1}. {f.name}" for i, f in enumerate(ss["uploaded_files"])])
        st.markdown(current_files)

    # Display token count & preview from session (stable across reruns)
    st.caption(f"Estimated tokens: {ss.get("module_tokens", 0):,}")
    with st.expander("Preview first 5,000 characters", expanded=False):
        st.text_area("Preview", (ss.get("module_text") or "")[:5000], height=150, disabled=True, key="preview_area")
    "-----------------------------------------------------"
    
    # --- Navigation ---
    is_ready_for_step_2 = bool(ss.get("module_text")) and ss.get("module_tokens", 0) <= const.MODULE_TOKEN_LIMIT
    if st.button("Next: Define Objectives →", disabled=not is_ready_for_step_2):
        ss["current_step"] = 2
        st.rerun()

################################################
# 2 Objectives & Alignment
################################################
def render_step_2():
    help_objectives = """Enter your course learning objectives and the intented level cognitive complexity
                    according to Bloom's Taxonomy. Don't worry if you are not familiar with Bloom's;
                    the app provides you plenty of information and tips below and
                    AI will also help you refine your objectives."""
    st.header("🎯 Learning Objectives", help=help_objectives)

    # General LO writing advice
    st.markdown(const.LO_WRITING_TIPS)

    # Visual reference (expandable pyramid)
    with st.expander("Bloom's Taxonomy Pyramid", expanded=False):
        st.image(const.BLOOM_PYRAMID_IMAGE, use_container_width=True)

    # --- Helper for finalized visual style ---
    def finalized_style(is_final):
        if is_final:
            return "background-color: #e6ffe6; border: 2px solid #2ecc40; border-radius: 6px;"
        return ""

    # --- Per-LO UI ---
    for i, lo in enumerate(list(ss["los"])):
        lo_text_key = f"lo_text_{lo['id']}"
        lo_level_key = f"lo_level_{lo['id']}"
        prev_text = lo.get("text", "")
        prev_level = lo.get("intended_level", "Remember")
        is_final = bool(lo.get("final_text"))

        # Seed widget state only once, on creation
        if lo_text_key not in ss:
            ss[lo_text_key] = prev_text
        if lo_level_key not in ss:
            ss[lo_level_key] = prev_level

        # Invalidate finalization if LO text or level changes (compare to last finalized values)
        module_sig = ss.get("module_sig", "")
        current_align_sig = _sig_alignment(ss[lo_text_key], ss[lo_level_key], module_sig)
        prev_align_sig = lo.get("alignment_sig")
        if prev_align_sig and prev_align_sig != current_align_sig:
            clear_alignment(lo)
            clear_questions(lo["id"])
            lo["final_text"] = None
            is_final = False

        # Container for LO
        with st.container(border=True):
            # --- Visual cue for finalized ---
            if is_final:
                st.markdown(
                    '<div style="background-color:#e6ffe6;border:2px solid #2ecc40;border-radius:6px;padding:0.5em 0.5em 0.5em 0.5em;margin-bottom:0.5em;">'
                    '<b>Finalized.</b> Click Re-open to edit.'
                    '</div>', unsafe_allow_html=True)

            # --- LO text area ---
            ta = st.text_area(f"**Objective #{i+1}**", key=lo_text_key, disabled=is_final,
                             label_visibility="visible",
                             help="Edit your learning objective here.")
            lo["text"] = ss[lo_text_key]

            # --- Bloom level selector ---
            sel = st.selectbox("Intended Bloom level", const.BLOOM_LEVELS, key=lo_level_key, disabled=is_final,
                               help="Select the intended Bloom's taxonomy level.",
                               index=const.BLOOM_LEVELS.index(ss[lo_level_key]),
                               label_visibility="visible")
            lo["intended_level"] = ss[lo_level_key]
            st.caption(f"##### ℹ️ {const.BLOOM_DEFS[lo['intended_level']]}")
            st.caption(f"**Common verbs:** {const.BLOOM_VERBS[lo['intended_level']]}")

            # --- Per-LO buttons ---
            btn_cols = st.columns([1, 1, 1, 1])
            with btn_cols[0]:
                if st.button("Alignment Check", key=f"align_{lo['id']}", disabled=is_final, help="Have another pair of AI eyes check your LO."):
                    lo["alignment"] = check_alignment(lo["text"], lo["intended_level"], ss["module_text"])
                    lo["alignment_sig"] = _sig_alignment(lo["text"], lo["intended_level"], ss.get("module_sig", ""))
                    st.rerun()
            with btn_cols[1]:
                if st.button("Accept as final", key=f"accept_{lo['id']}", disabled=is_final):
                    lo["final_text"] = lo["text"]
                    # Invalidate questions if needed
                    current_gen_sig = _sig_generation(lo.get("final_text"), lo["intended_level"], ss.get("module_sig", ""))
                    prev_gen_sig = lo.get("generation_sig")
                    if prev_gen_sig and prev_gen_sig != current_gen_sig:
                        clear_questions(lo["id"])
                        lo["generation_sig"] = None
                    st.rerun()
            with btn_cols[2]:
                if is_final:
                    if st.button("Re-open", key=f"unfinal_{lo['id']}"):
                        lo["final_text"] = None
                        st.rerun()
            with btn_cols[3]:
                if st.button(":x: Delete", key=f"del_{lo['id']}"):
                    ss.pop(lo_text_key, None)
                    ss.pop(lo_level_key, None)
                    ss["los"].remove(lo)
                    clear_questions(lo["id"])
                    st.rerun()

            # --- Alignment result (if available) ---
            if lo.get("alignment") is not None:
                label = lo["alignment"]["label"]
                color = {"consistent": "green", "ambiguous": "orange", "inconsistent": "red"}[label]
                st.markdown(f"**Alignment:** :{color}[{label}]")
                if lo["alignment"]["reasons"]:
                    st.markdown("- " + "\n- ".join(lo["alignment"]["reasons"]))
                if label != "consistent" and lo["alignment"].get("suggested_lo"):
                    st.markdown(f"**Suggested re-write:**\n> {lo['alignment']['suggested_lo']}")

    # --- Add-new button at the bottom ---
    if st.button("➕ Add Learning Objective", key="add_lo_bottom"):
        ss["los"].append({
            "id": str(uuid.uuid4()),
            "text": "",
            "intended_level": "Remember",
            "alignment": None,
            "final_text": None,
            "alignment_sig": None,
            "generation_sig": None
        })
        st.rerun()

    # --- Check All / Accept All buttons ---
    all_btn_cols = st.columns([1, 1])
    with all_btn_cols[0]:
        if st.button("Check All", key="check_all", disabled=not ss["los"]):
            for lo in ss["los"]:
                lo["alignment"] = check_alignment(lo["text"], lo["intended_level"], ss["module_text"])
                lo["alignment_sig"] = _sig_alignment(lo["text"], lo["intended_level"], ss.get("module_sig", ""))
            st.rerun()
    with all_btn_cols[1]:
        if st.button("Accept All", key="accept_all", disabled=not ss["los"]):
            for lo in ss["los"]:
                lo["final_text"] = lo["text"]
                # Invalidate questions if needed
                current_gen_sig = _sig_generation(lo.get("final_text"), lo["intended_level"], ss.get("module_sig", ""))
                prev_gen_sig = lo.get("generation_sig")
                if prev_gen_sig and prev_gen_sig != current_gen_sig:
                    clear_questions(lo["id"])
                    lo["generation_sig"] = None
            st.rerun()

    # --- Navigation ---
    st.divider()
    cols = st.columns([1, 1])
    with cols[0]:
        if st.button("← Back: Upload Material"):
            ss["current_step"] = 1
            st.rerun()
    with cols[1]:
        def all_los_finalized():
            if not ss.get("los"): return False
            return all(lo.get("final_text") for lo in ss["los"])
        if st.button("Next: Generate Questions →", disabled=not all_los_finalized()):
            ss["current_step"] = 3
            st.rerun()

#################################################
# 3 Generate questions
#################################################
def render_step_3():
    st.header("✍️ Generate Questions")
    st.markdown("[Tips or links to resources on writing good assessment questions.]")
    # Helper to check if we can run generation
    def can_generate(ss) -> bool:
        return bool(ss["module_text"] and ss["los"] and all(lo.get("final_text") for lo in ss["los"]))

    st.select_slider(
        "Number of questions per LO",
        options=[1, 2, 3],
        value=1,
        key="n_questions",
    )
    if st.button("Generate", disabled=not can_generate(ss)):
        for lo in ss["los"]:
            payload =   generate_questions(
                lo.get("final_text"),
                lo["intended_level"],
                ss["module_text"],
                n_questions=ss["n_questions"]
                )
            ss["questions"][lo["id"]] = payload["questions"]
            # store signature for question generation
            lo["generation_sig"] = _sig_generation(
                lo.get("final_text"),
                lo["intended_level"],
                ss.get("module_sig","")
            )
        # After regeneration, update questions_sig and clear stale DOCX
        ss["questions_sig"] = _sig_questions(ss["questions"])
        ss.pop("docx_file", None)
    
    # Go over all LOs
    for lo in ss["los"]:
        qs=ss["questions"].get(lo["id"],[])
        if not qs: continue
        with st.container(border=True):
            st.subheader(f"{lo.get('final_text')}")
            for idx,q in enumerate(qs):
                # Question stem
                st.markdown(f"**Question {idx+1}**")
                q["stem"]=st.text_area(f"Question {idx+1}", q["stem"], key=f"stem_{lo['id']}_{idx}",
                                       label_visibility="collapsed", height="content")
                # Answer options
                for opt in q["options"]:
                    cols = st.columns([1, 30])
                    with cols[0]:
                        st.markdown(f"**({opt['id']})**")
                    with cols[1]:
                        opt["text"]=st.text_input(f"**({opt['id']})**", opt["text"],
                                                  key=f"opt_{lo['id']}_{idx}_{opt['id']}",
                                                  label_visibility="collapsed")
                # Correct answer
                current=["A","B","C","D"].index(q["correct_option_id"])
                q["correct_option_id"]=st.radio("Correct option", ["A","B","C","D"], index=current, horizontal=True, key=f"radio_{lo['id']}_{idx}")
                # Feedback for each option
                st.markdown("Feedback")
                for opt in q["options"]:
                    opt["option_rationale"]=st.text_area(f"**({opt['id']})**", opt.get("option_rationale",""), key=f"rat_{lo['id']}_{idx}_{opt['id']}")
                # Content reference and cognitive rationale
                q["contentReference"]=st.text_area("Content reference", q.get("contentReference",""), key=f"ref_{lo['id']}_{idx}")
                q["cognitive_rationale"]=st.text_area("Rationale for Bloom level", q.get("cognitive_rationale",""), key=f"rat_{lo['id']}_{idx}")

    # After all widgets have applied edits, detect real changes
    new_q_sig = _sig_questions(ss.get("questions", {}))
    if ss.get("questions_sig") and ss["questions_sig"] != new_q_sig:
        # User changed questions → previously built DOCX is now stale
        ss["docx_file"] = None
    ss["questions_sig"] = new_q_sig

    # --- Navigation ---
    st.divider()
    cols = st.columns([1, 1])
    with cols[0]:
        if st.button("← Back: Define Objectives"):
            ss["current_step"] = 2
            st.rerun()
    with cols[1]:
        is_ready_for_step_4 = bool(ss.get("questions"))
        if st.button("Next: Export →", disabled=not is_ready_for_step_4):
            ss["current_step"] = 4
            st.rerun()
    
################################################
# 4 Export
################################################
def render_step_4():

    st.header("📄 Export to Word")
    build_disabled = not ss.get("questions")
    if st.button("Build DOCX file", disabled=build_disabled):
        ss["docx_file"] = build_docx(ss["los"], ss["questions"])
    if ss.get("docx_file"):
        st.download_button(
            "Download",
            data=ss["docx_file"],
            file_name="assessment_questions.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key="download_docx_btn"
        )        
   
    # --- Navigation ---
    st.divider()
    cols = st.columns([1, 1])
    with cols[0]:
        if st.button("← Back: Generate Questions"):
            ss["current_step"] = 3
            st.rerun()
    with cols[1]:
        if st.button("✨ Start Over"):
            # Preserve settings from sidebar
            mock_mode = ss.get("MOCK_MODE", True)
            model = ss.get("OPENAI_MODEL", "gpt-4.1-nano")
            ss.clear()
            ss["MOCK_MODE"] = mock_mode
            ss["OPENAI_MODEL"] = model
            ss["current_step"] = 1
            st.rerun()

################################################
# Main application router
################################################
render_stepper()
if ss["current_step"] == 1:
    render_step_1()
elif ss["current_step"] == 2:
    render_step_2()
elif ss["current_step"] == 3:
    render_step_3()
elif ss["current_step"] == 4:
    render_step_4()
