
import streamlit as st, os, uuid
from typing import List, Dict
from dotenv import load_dotenv
from app.parsing import extract_text_and_tokens
from app.generation import check_alignment, generate_questions
from app.export import build_docx

# Load environment variables from .env
load_dotenv() 

BLOOM_LEVELS=["Remember","Understand","Apply","Analyze","Evaluate","Create"]

st.set_page_config(page_title="LO → Bloom Alignment & Question Generator", page_icon="🧠", layout="wide")
st.title("LO → Bloom Alignment & Question Generator (MVP)")

if os.getenv("MOCK_MODE","false").lower() in {"1","true","yes"}:
    st.warning("⚠️ MOCK MODE is ON – all AI responses are canned.")

if "module_text" not in st.session_state:
    st.session_state["module_text"]=""
if "los" not in st.session_state:
    st.session_state["los"]=[]
if "questions" not in st.session_state:
    st.session_state["questions"]={}

with st.sidebar:
    if st.button("Reset session"):
        st.session_state.clear()
        st.rerun()

# 1 Upload
st.header("1) Upload Module Content")
file=st.file_uploader("Upload PDF, DOCX, TXT", type=["pdf","docx","txt"])
if file:
    text,tokens=extract_text_and_tokens(file)
    st.session_state["module_text"]=text
    st.caption(f"Estimated tokens: {tokens:,}")
    if tokens>30000:
        st.error("Module exceeds 30k tokens.")
        st.stop()
    st.text_area("Preview", text[:1200], height=150, disabled=True)

# 2 LOs
st.header("2) Learning Objectives")
if st.button("Add LO"):
    st.session_state["los"].append({"id":str(uuid.uuid4()),"text":"","intended_level":"Analyze","alignment":None,"final_text":None})
for lo in list(st.session_state["los"]):
    with st.container(border=True):
        lo["text"]=st.text_area("LO text", lo["text"], key=f"txt_{lo['id']}")
        lo["intended_level"]=st.selectbox("Bloom level", BLOOM_LEVELS, index=BLOOM_LEVELS.index(lo["intended_level"]), key=f"lvl_{lo['id']}")
        cols=st.columns(2)
        if cols[0].button("Delete", key=f"del_{lo['id']}"):
            st.session_state["los"].remove(lo)
            st.experimental_rerun()
        if cols[1].button("Set final=current", key=f"set_{lo['id']}"):
            lo["final_text"]=lo["text"]

# 3 Alignment
st.header("3) Alignment Check")
if st.button("Run alignment", disabled= not st.session_state["module_text"] or not st.session_state["los"]):
    for lo in st.session_state["los"]:
        lo["alignment"]=check_alignment(lo["intended_level"], lo["text"], st.session_state["module_text"])
        if lo["alignment"]["label"]=="consistent" and not lo.get("final_text"):
            lo["final_text"]=lo["text"]

for lo in st.session_state["los"]:
    if not lo.get("alignment"): continue
    with st.container(border=True):
        label=lo["alignment"]["label"]
        color={"consistent":"green","ambiguous":"orange","inconsistent":"red"}[label]
        st.subheader(f"Alignment: :{color}[{label}] – {lo['text'][:60]}")
        st.markdown("- "+"\n- ".join(lo["alignment"]["reasons"]))
        if lo["alignment"].get("suggested_lo"):
            lo["final_text"]=st.text_area("Suggested rewrite", lo["alignment"]["suggested_lo"], key=f"sug_{lo['id']}")
            if st.button("Accept suggestion", key=f"acc_{lo['id']}"):
                st.success("Accepted")
        st.caption(f"Final LO: {lo.get('final_text') or lo['text']}")

# 4 Generate
st.header("4) Generate Questions")
if st.button("Generate MCQs", disabled= not st.session_state["module_text"] or not st.session_state["los"]):
    for lo in st.session_state["los"]:
        final=lo.get("final_text") or lo["text"]
        payload=generate_questions(final, lo["intended_level"], st.session_state["module_text"], 3)
        st.session_state["questions"][lo["id"]]=payload["questions"]

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
