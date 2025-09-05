import streamlit as st
import io, os, uuid
from typing import List, Dict
from dotenv import load_dotenv
import hashlib

from app.parsing import extract_text_and_tokens
from app.generation import check_alignment, generate_questions, set_runtime_config
from app.export import build_docx
from app.constants import (
    MODULE_TOKEN_LIMIT,
    LO_WRITING_TIPS,
    BLOOM_LEVELS,
    BLOOM_DEFS,
    BLOOM_VERBS,
    BLOOM_PYRAMID_IMAGE,
    mock_uploaded_file
)

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
st.set_page_config(page_title="Bloom Alignment & Question Generator", page_icon="🧠", layout="wide")
st.title(":mortar_board: Learning Objective and Question Generator")

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
################################################
# Sidebar for settings
################################################
with st.sidebar:
    if st.button("Reset session"):
        ss.clear()
        st.rerun()

    # Change handler: apply model/mock and invalidate downstream state
    def _on_settings_change():
        prev_mock = ss.get("__prev_mock_mode__", ss["MOCK_MODE"])
        # 1) apply to generation runtime
        set_runtime_config(ss["MOCK_MODE"], ss["OPENAI_MODEL"])
        # 2) invalidate alignment/finals/questions/suggestions
        for lo in ss.get("los", []):
            lo.pop("alignment", None)
            lo.pop("final_text", None)
            lo.pop("alignment_sig", None)
            lo.pop("generation_sig", None)
            ss.pop(f"sug_{lo['id']}", None)
        ss["questions"].clear()
        ss["docx_file"] = None
        # If mock mode was toggled, reset uploaded content and uploader widget
        if prev_mock != ss["MOCK_MODE"]:
            ss["uploaded_files"] = []
            ss["processed_file_keys"] = None
            ss["module_text"] = ""
            ss["module_tokens"] = 0
            ss["module_sig"] = ""
            ss.pop("module_files", None)
            ss["uploader_key"] += 1
        ss["__prev_mock_mode__"] = ss["MOCK_MODE"]
        # Flag for optional notice after rerun
        ss["__settings_changed__"] = True

    st.markdown("### Runtime Settings")

    st.toggle("Mock mode", key="MOCK_MODE", on_change=_on_settings_change)
    model_options = ["gpt-4.1-nano", "gpt-4.1-mini", "gpt-4.1"]
    st.selectbox("OpenAI model", model_options, key="OPENAI_MODEL", on_change=_on_settings_change)

    # Show confirmation if settings were just changed
    if ss.pop("__settings_changed__", False):
        st.toast("Settings changed — cleared any Bloom alignment and questions.")


################################################
# Visual Stepper
################################################
def render_stepper():
    steps = ["Upload", "Define & Align", "Generate", "Export"]
    cols = st.columns(len(steps))
    for i, (col, step_name) in enumerate(zip(cols, steps)):
        with col:
            if i + 1 == ss["current_step"]:
                st.markdown(f"**{i+1}. {step_name}**")
            elif i + 1 < ss["current_step"]:
                st.markdown(f"✅ {i+1}. {step_name}")
            else:
                st.markdown(f"_{i+1}. {step_name}_")
    "-----------------------------------------------------"

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
        files = [mock_uploaded_file]

    # Compute a stable signature for the current files (for cache keying)
    current_file_keys = tuple((f.name, f.size, getattr(f, "last_modified", None)) for f in files)


    # Process files if they have actually changed.
    if files and current_file_keys != ss["processed_file_keys"]:
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

        if tokens > MODULE_TOKEN_LIMIT:
            st.error(f"Module exceeds {MODULE_TOKEN_LIMIT:,} tokens. Reduce content to proceed.")
        else:
            # Invalidate only if the *actual parsed text* changed
            if prev_mod_sig and prev_mod_sig != new_mod_sig:
                for lo in ss.get("los", []):
                    lo.pop("alignment", None)
                    lo.pop("final_text", None)
                    ss.pop(f"sug_{lo['id']}", None)
                ss["questions"].clear()
                ss["docx_file"] = None  # clear any generated docx
                ss.pop("questions_sig", None)
                if ss.get("los"):
                    st.info("Module content changed — alignment and questions cleared.")

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
    is_ready_for_step_2 = bool(ss.get("module_text")) and ss.get("module_tokens", 0) <= MODULE_TOKEN_LIMIT
    if st.button("Next: Define Objectives →", disabled=not is_ready_for_step_2):
        ss["current_step"] = 2
        st.rerun()

################################################
# 2 Objectives & Alignment
################################################
def render_step_2():
    st.header("🎯 Define Objectives & Check Alignment")

    # 2.a Define LOs
    # General LO writing advice
    st.markdown(LO_WRITING_TIPS)

    # Visual reference (expandable pyramid)
    with st.expander("Bloom's Taxonomy Pyramid", expanded=False):
        st.image(BLOOM_PYRAMID_IMAGE,
                use_container_width=True)

    # List of LOs (editable)
    for i, lo in enumerate(list(ss["los"])):
        with st.container(border=True):
            prev_text = lo.get("text","")
            prev_level = lo.get("intended_level","Remember")

            # ---- LO text: seed once, then bind to key
            lo_text_key = f"lo_text_{lo['id']}"
            if lo_text_key not in ss:
                ss[lo_text_key] = prev_text
            st.text_area(f"**Objective #{i+1}**", key=lo_text_key)
            lo["text"] = ss[lo_text_key]

            # ---- Intended level: seed once, then bind to key
            lo_level_key = f"lo_level_{lo['id']}"
            if lo_level_key not in ss:
                ss[lo_level_key] = prev_level
            st.selectbox("Intended Bloom level", BLOOM_LEVELS, key=lo_level_key)
            lo["intended_level"] = ss[lo_level_key]
            # Inline guidance under picker
            st.caption(f"##### ℹ️ {BLOOM_DEFS[lo['intended_level']]}")
            st.caption(f"**Common verbs:** {BLOOM_VERBS[lo['intended_level']]}")

            # ---- Per-LO invalidation when LO text or intended level changes ────
            module_sig = ss.get("module_sig","")
            current_align_sig = _sig_alignment(lo["text"], lo["intended_level"], module_sig)
            prev_align_sig = lo.get("alignment_sig")     
            if prev_align_sig and prev_align_sig != current_align_sig:
                lo.pop("alignment", None)
                lo.pop("final_text", None)
                lo.pop("generation_sig", None)
                ss["questions"].pop(lo["id"], None)
                lo["alignment_sig"] = None
                ss.pop(f"sug_{lo['id']}", None)

                st.info(f"Cleared alignment and questions for LO #{i+1} due to changes.")        


            if st.button(":x: Delete", key=f"del_{lo['id']}"):
                # Clean up widget state keys for this LO so new LOs seed cleanly
                ss.pop(lo_text_key, None)
                ss.pop(lo_level_key, None)
                ss["los"].remove(lo)
                st.rerun()

    # Add-new button at the bottom of the LO section
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
    
    # 2.b Alignment check
    st.subheader("Alignment Check")
    # Helper to check if we can run alignment
    def can_run_alignment(ss) -> bool:
        return bool(ss["module_text"] and ss["los"] and all(lo.get("text") for lo in ss["los"]))

    if st.button("Run alignment", disabled=not can_run_alignment(ss)):
        for lo in ss["los"]:
            lo["alignment"]=check_alignment(lo["text"], lo["intended_level"], ss["module_text"])
            # store signature for alignment result
            lo["alignment_sig"] = _sig_alignment(
                lo["text"], lo["intended_level"], ss.get("module_sig","")
            )

    for i, lo in enumerate(list(ss["los"])):
        if not lo.get("alignment"): continue
        with st.container(border=True):
            st.subheader(f"LO #{i+1}: {lo['text'][:80]}")
            label=lo["alignment"]["label"]
            color={"consistent":"green","ambiguous":"orange","inconsistent":"red"}[label]
            st.markdown(f"**Alignment:** :{color}[{label}]")
            if lo["alignment"]["reasons"]:
                st.markdown("- " + "\n- ".join(lo["alignment"]["reasons"]))

            # ---- Suggested rewrite: seed once, then bind to key (editable)
            sug_key = f"sug_{lo['id']}"
            if sug_key not in ss:
                ss[sug_key] = lo["alignment"].get("suggested_lo") or lo["text"]
            final = st.text_area("Suggested rewrite (editable)", key=sug_key)
            st.caption("Edits here are not saved until you click **Accept as final**.")
        
            
            if st.button("Accept as final", key=f"accept_{lo['id']}"):
                lo["final_text"] = final
                st.success("Accepted. Final LO updated.")

                # ── If final_text edited, invalidate questions only ───────────
                current_gen_sig = _sig_generation(
                    lo.get("final_text"),
                    lo["intended_level"],
                    ss.get("module_sig","")
                    )
                prev_gen_sig = lo.get("generation_sig")
                if prev_gen_sig and prev_gen_sig != current_gen_sig:
                    ss.pop(f"sug_{lo['id']}", None)
                    ss["questions"].pop(lo["id"], None)
                    lo["generation_sig"] = None
                    ss.pop("docx_file", None)
                    ss.pop("questions_sig", None)
                    st.info("Cleared questions for this LO due to final text change.")
    
    # --- Navigation ---
    st.divider()
    cols = st.columns([1, 1])
    with cols[0]:
        if st.button("← Back: Upload Material"):
            ss["current_step"] = 1
            st.rerun()
    with cols[1]:
        # Helper to check if all LOs have been finalized
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
                    opt["text"]=st.text_input(f"**({opt['id']})**", opt["text"], key=f"opt_{lo['id']}_{idx}_{opt['id']}")
                    with st.expander("Feedback", expanded=False):
                        opt["option_rationale"]=st.text_area(f"Feedback", opt.get("option_rationale",""), key=f"rat_{lo['id']}_{idx}_{opt['id']}", label_visibility="collapsed")
                current=["A","B","C","D"].index(q["correct_option_id"])
                q["correct_option_id"]=st.radio("Correct option", ["A","B","C","D"], index=current, horizontal=True, key=f"radio_{lo['id']}_{idx}")
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
    # st.header("📄 Export to Word")
    # if st.button("Build DOCX file", disabled=not ss["questions"]):
    #     doc=build_docx(ss["los"], ss["questions"])
    #     st.download_button("Download", data=doc, file_name="assessment_questions.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

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
