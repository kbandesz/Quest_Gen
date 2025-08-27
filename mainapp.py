
import streamlit as st, os, uuid
from typing import List, Dict
from dotenv import load_dotenv
import hashlib
from app.parsing import extract_text_and_tokens
from app.generation import check_alignment, generate_questions
from app.export import build_docx

# Load environment variables from .env
load_dotenv(override=True)

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


BLOOM_LEVELS=["Remember","Understand","Apply","Analyze","Evaluate","Create"]
MODULE_TOKEN_LIMIT = 27000



st.set_page_config(page_title="Bloom Alignment & Question Generator", page_icon="🧠", layout="wide")
st.title("Bloom Alignment Analyzer & Question Generator (MVP)")

if os.getenv("MOCK_MODE","false").lower() in {"1","true","yes"}:
    st.warning("⚠️ MOCK MODE is ON – all AI responses are canned.")

# Initialize session state
ss = st.session_state
ss.setdefault("module_text", "")
ss.setdefault("module_sig", "")
ss.setdefault("los", [])
ss.setdefault("questions", {})


with st.sidebar:
    if st.button("Reset session"):
        ss.clear()
        st.rerun()

# 1 Upload Course Content
st.header("1) Upload Course Material")
files=st.file_uploader(
    "Maximum 27,000 tokens of text (about 20,000 words or 40 single-spaced pages)",
    type=["pdf","docx","txt"],
    accept_multiple_files=True
    ) or [] # This is needed to avoid NoneType later

# Extract text + token count (from cache if available)
file_keys = [(f.name, f.size, getattr(f, "last_modified", None)) for f in files]
text, tokens = _extract_cached_text_and_tokens(tuple(file_keys), files)

if tokens>MODULE_TOKEN_LIMIT:
    st.error(f"Module exceeds {MODULE_TOKEN_LIMIT:,} tokens. Remove content to proceed.")

st.caption(f"Estimated tokens: {tokens:,}")

with st.expander("Preview first 5,000 characters", expanded=False):
    # key ensures stable widget state when toggling expander
    st.text_area("Preview", text[:5000], height=150, disabled=True, key="preview_area")

# Only update session + invalidate when within token limit
prev_mod_sig = ss.get("module_sig")
if tokens<=MODULE_TOKEN_LIMIT:
    ss["module_text"] = text

    # Invalidate all LOs if module content changed
    new_mod_sig = _sig_module(text)
    if prev_mod_sig and prev_mod_sig != new_mod_sig:
        for lo in ss.get("los", []):
            lo.pop("alignment", None)
            lo.pop("final_text", None)
            lo.pop("alignment_sig", None)
            lo.pop("generation_sig", None)
            ss.pop(f"sug_{lo['id']}", None)
        ss["questions"].clear()
        if ss.get("los"):
            st.info("Module content changed — cleared any Bloom alignment and questions.")
    ss["module_sig"] = new_mod_sig

# 2 Learning Objectives
st.header("2) Enter Learning Objectives & Intended Bloom Level")
if st.button("Add Learning Objective"):
    ss["los"].append({
        "id":str(uuid.uuid4()),
        "text":"",
        "intended_level":"Remember",
        "alignment": None,
        "final_text": None,
        "alignment_sig": None,
        "generation_sig": None
        })

for i, lo in enumerate(list(ss["los"])):
    with st.container(border=True):
        prev_text = lo.get("text","")
        prev_level = lo.get("intended_level","Remember")

        # ---- LO text: seed once, then bind to key (no value= on reruns)
        lo_text_key = f"lo_text_{lo['id']}"
        if lo_text_key not in ss:
            ss[lo_text_key] = prev_text
        st.text_area(f"**Objective #{i+1}**", key=lo_text_key)
        lo["text"] = ss[lo_text_key]

        # ---- Intended level: seed once, then bind to key (avoid index races)
        lo_level_key = f"lo_level_{lo['id']}"
        if lo_level_key not in ss:
            ss[lo_level_key] = prev_level
        init_idx = BLOOM_LEVELS.index(ss[lo_level_key])
        st.selectbox("Intended Bloom level", BLOOM_LEVELS, index=init_idx, key=lo_level_key)
        lo["intended_level"] = ss[lo_level_key]      

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


        if st.button("Delete", key=f"del_{lo['id']}"):
            # Clean up widget state keys for this LO so new LOs seed cleanly
            ss.pop(lo_text_key, None)
            ss.pop(lo_level_key, None)
            ss["los"].remove(lo)
            st.rerun()

# 3 Alignment
st.header("3) Alignment Check")
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
                st.info("Cleared questions for this LO due to final text change.")   


# 4 Generate
st.header("4) Generate Questions")
# Helper to check if we can run generation
def can_generate(ss) -> bool:
    return bool(ss["module_text"] and ss["los"] and all(lo.get("final_text") for lo in ss["los"]))

if st.button("Generate MCQs", disabled=not can_generate(ss)):
    for lo in ss["los"]:
        payload=generate_questions(
            lo.get("final_text"),
            lo["intended_level"],
            ss["module_text"],
            n_questions=1
            )
        ss["questions"][lo["id"]]=payload["questions"]
        # store signature for question generation
        lo["generation_sig"] = _sig_generation(
            lo.get("final_text"),
            lo["intended_level"],
            ss.get("module_sig","")
        )        

for lo in ss["los"]:
    qs=ss["questions"].get(lo["id"],[])
    if not qs: continue
    with st.container(border=True):
        st.subheader(f"{lo.get('final_text')}")
        for idx,q in enumerate(qs):
            # Question stem
            q["stem"]=st.text_area(f"Question {idx+1}", q["stem"], key=f"stem_{lo['id']}_{idx}")
            # Answer options
            for opt in q["options"]:
                opt["text"]=st.text_input(f"**({opt['id']})**", opt["text"], key=f"opt_{lo['id']}_{idx}_{opt['id']}")
                with st.expander("Feedback", expanded=False):
                    opt["option_rationale"]=st.text_area(f"Feedback", opt.get("option_rationale",""), key=f"rat_{lo['id']}_{idx}_{opt['id']}", label_visibility="collapsed")
            current=["A","B","C","D"].index(q["correct_option_id"])
            q["correct_option_id"]=st.radio("Correct option", ["A","B","C","D"], index=current, horizontal=True, key=f"radio_{lo['id']}_{idx}")
            q["contentReference"]=st.text_area("Content reference", q.get("contentReference",""), key=f"ref_{lo['id']}_{idx}")
            q["cognitive_rationale"]=st.text_area("Rationale for Bloom level", q.get("cognitive_rationale",""), key=f"rat_{lo['id']}_{idx}")

# 5 Export
st.header("5) Export to Word")
if st.button("Build DOCX file", disabled=not ss["questions"]):
    doc=build_docx(ss["los"], ss["questions"])
    st.download_button("Download", data=doc, file_name="assessment_questions.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
