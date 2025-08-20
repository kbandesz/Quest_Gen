
import streamlit as st, os, uuid
from typing import List, Dict
from dotenv import load_dotenv
import hashlib
from app.parsing import extract_text_and_tokens
from app.generation import check_alignment, generate_questions
from app.export import build_docx

# Load environment variables from .env
load_dotenv()


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

st.set_page_config(page_title="Bloom Alignment & Question Generator", page_icon="🧠", layout="wide")
st.title("Bloom Alignment Analyzer & Question Generator (MVP)")

if os.getenv("MOCK_MODE","false").lower() in {"1","true","yes"}:
    st.warning("⚠️ MOCK MODE is ON – all AI responses are canned.")

if "module_text" not in st.session_state:
    st.session_state["module_text"]=""
if "module_sig" not in st.session_state:
    st.session_state["module_sig"]=""
if "los" not in st.session_state:
    st.session_state["los"]=[]
if "questions" not in st.session_state:
    st.session_state["questions"]={}

with st.sidebar:
    if st.button("Reset session"):
        st.session_state.clear()
        st.rerun()

# 1 Upload Course Content
st.header("1) Upload Course Material")
files=st.file_uploader(
    "Maximum 3 files (PDF, DOCX, TXT)",
    type=["pdf","docx","txt"],
    accept_multiple_files=True
    )
if files:
    if len(files)>3:
        st.error("Please upload at most 3 files.")
        st.stop()
    text,tokens=extract_text_and_tokens(files)
    st.session_state["module_text"]=text
    st.caption(f"Estimated tokens: {tokens:,}")
    if tokens>25000:
        st.error("Module exceeds 25k tokens.")
        st.stop()
    st.text_area("Preview", text[:1200], height=150, disabled=True)

    # ── Invalidate all LOs if module content changed ─────────────────────
    new_mod_sig = _sig_module(st.session_state["module_text"])
    prev_mod_sig = st.session_state.get("module_sig")
    st.session_state["module_sig"] = new_mod_sig
    if prev_mod_sig and prev_mod_sig != new_mod_sig:
        for lo in st.session_state.get("los", []):
            lo.pop("alignment", None)
            lo.pop("final_text", None)
            lo.pop("alignment_sig", None)
            lo.pop("generation_sig", None)
        st.session_state.get("questions", {}).clear()
        st.info("Module content changed — cleared alignment and questions for all LOs.")


# 2 Learning Objectives
st.header("2) Enter Learning Objectives & Intended Bloom Level")
if st.button("Add Learning Objective"):
    st.session_state["los"].append({
        "id":str(uuid.uuid4()),
        "text":"",
        "intended_level":"Remember",
        "alignment": None,
        "final_text": None,
        "alignment_sig": None,
        "generation_sig": None
        })

for i, lo in enumerate(list(st.session_state["los"])):
    with st.container(border=True):
        prev_text = lo.get("text","")
        prev_level = lo.get("intended_level","Analyze")

        lo["text"] = st.text_area(f"**Objective #{i+1}**", value=prev_text, key=f"lo_text_{lo['id']}")
        lo["intended_level"] = st.selectbox(
            "Intended Bloom level", BLOOM_LEVELS,
            index=BLOOM_LEVELS.index(prev_level),
            key=f"lo_level_{lo['id']}"
        )        

        # ── Per-LO invalidation when LO text or intended level changes ────
        module_sig = st.session_state.get("module_sig","")
        current_align_sig = _sig_alignment(lo["text"], lo["intended_level"], module_sig)
        prev_align_sig = lo.get("alignment_sig")     
        if prev_align_sig and prev_align_sig != current_align_sig:
            lo.pop("alignment", None)
            lo.pop("final_text", None)
            lo.pop("generation_sig", None)
            st.session_state["questions"].pop(lo["id"], None)
            lo["alignment_sig"] = None
            st.info(f"Cleared alignment and questions for LO #{i+1} due to changes.")        


        cols=st.columns(3)
        if cols[0].button("Delete", key=f"del_{lo['id']}"):
            st.session_state["los"].remove(lo)
            st.rerun()
        if cols[1].button("Set final = current", key=f"setfinal_{lo['id']}"):
            lo["final_text"]=lo["text"]

# 3 Alignment
st.header("3) Alignment Check")
if st.button("Run alignment", disabled= not st.session_state["module_text"] or not st.session_state["los"]):
    for lo in st.session_state["los"]:
        lo["alignment"]=check_alignment(lo["intended_level"], lo["text"], st.session_state["module_text"])
        # store signature for alignment result
        lo["alignment_sig"] = _sig_alignment(
            lo["text"], lo["intended_level"], st.session_state.get("module_sig","")
        )         
        # auto-fill final text if consistent and not set
        if lo["alignment"]["label"]=="consistent" and not lo.get("final_text"):
            lo["final_text"]=lo["text"]

for i, lo in enumerate(list(st.session_state["los"])):
    if not lo.get("alignment"): continue
    with st.container(border=True):
        st.subheader(f"LO #{i+1}: {lo['text'][:80]}")
        label=lo["alignment"]["label"]
        color={"consistent":"green","ambiguous":"orange","inconsistent":"red"}[label]
        st.markdown(f"**Alignment:** :{color}[{label}]")
        if lo["alignment"]["reasons"]:
            st.markdown("- " + "\n- ".join(lo["alignment"]["reasons"]))

        suggested = lo["alignment"].get("suggested_lo")
        if suggested:
            prev_final = lo.get("final_text", suggested)
            lo["final_text"] = st.text_area("Suggested rewrite (editable)", value=prev_final, key=f"sug_{lo['id']}")

            # ── If final_text edited, invalidate questions only ───────────
            module_sig = st.session_state.get("module_sig","")
            current_gen_sig = _sig_generation(lo.get("final_text") or lo["text"], lo["intended_level"], module_sig)
            prev_gen_sig = lo.get("generation_sig")
            if prev_gen_sig and prev_gen_sig != current_gen_sig:
                st.session_state["questions"].pop(lo["id"], None)
                lo["generation_sig"] = None
                st.info("Cleared questions for this LO due to final text change.")            
            
            if st.button("Accept suggested as final", key=f"accept_{lo['id']}"):
                st.success("Accepted. Final LO updated.")
        else:
            st.caption(f"No rewrite suggested.")

# 4 Generate
st.header("4) Generate Questions")
if st.button("Generate MCQs", disabled= not st.session_state["module_text"] or not st.session_state["los"]):
    for lo in st.session_state["los"]:
        final_text = lo.get("final_text") or lo["text"]
        payload=generate_questions(final_text, lo["intended_level"], st.session_state["module_text"], n_questions=2)
        st.session_state["questions"][lo["id"]]=payload["questions"]
        # store signature for question generation
        lo["generation_sig"] = _sig_generation(
            lo.get("final_text") or lo["text"],
            lo["intended_level"],
            st.session_state.get("module_sig","")
        )        

for lo in st.session_state["los"]:
    qs=st.session_state["questions"].get(lo["id"],[])
    if not qs: continue
    with st.container(border=True):
        st.subheader(f"Questions for LO: {lo.get('final_text') or lo['text'][:40]}...")
        for idx,q in enumerate(qs):
            q["stem"]=st.text_area(f"Stem {idx+1}", q["stem"], key=f"stem_{lo['id']}_{idx}")
            for opt in q["options"]:
                opt["text"]=st.text_input(f"({opt['id']})", opt["text"], key=f"opt_{lo['id']}_{idx}_{opt['id']}")
            current=["A","B","C","D"].index(q["correct_option_id"])
            q["correct_option_id"]=st.radio("Correct option", ["A","B","C","D"], index=current, horizontal=True, key=f"radio_{lo['id']}_{idx}")
            q["cognitive_rationale"]=st.text_area("Rationale", q.get("cognitive_rationale",""), key=f"rat_{lo['id']}_{idx}")

# 5 Export
st.header("5) Export DOCX")
if st.button("Download DOCX"):
    doc=build_docx(st.session_state["los"], st.session_state["questions"])
    st.download_button("Download", data=doc, file_name="assessment_questions.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
