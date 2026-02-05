"""Main UI logic of the BEACON-Design app."""
import streamlit as st
import uuid
from typing import Dict, Any, List

from app.parse_input_files import extract_text_and_tokens
from app.generate_llm_output import generate_outline, check_alignment, generate_questions
from app.export_docx import build_outline_docx, build_questions_docx
from app.display_outline import display_editable_outline, display_static_outline
from app.display_questions import display_editable_question, display_static_question
from app.save_load_progress import save_load_panel, apply_pending_restore
import app.constants as const
from app.session_state_utils import (
    init_session_state,
    sig_alignment,
    sig_question_gen,
    sig_outline,
    sig_questions,
    compute_step_readiness,
    clear_outline_widget_state,
    clear_alignment,
    clear_questions,
    clear_module_dependent_outputs,
    apply_module_content,
    reset_uploaded_content,
    reset_session,
)

################################################
# App setup
################################################
# Page config
st.set_page_config(page_title="BEACON - Design", page_icon="🌟", layout="wide", initial_sidebar_state="collapsed")

# Apply any pending restore from saved session state
apply_pending_restore()

# Initialize session state
ss = st.session_state
init_session_state(ss)

################################################
# Title and warning based on current mock setting
mock_warning = "   :red[⚠️ MOCK MODE is ON]"
st.title(f"🌟📐 BEACON - Design{mock_warning if ss['MOCK_MODE'] else ''}")
st.markdown("##### _Smarter course design—powered by AI._")

################################################
# Sidebar for settings
################################################
with st.sidebar:


    # # If mock mode was toggled: confirm and clear everything and go back to Step 1
    # @st.dialog("Confirm Action", dismissible=False, width="small")
    # def _on_mock_mode_change():
    #     st.write("This will will clear everything. Are you sure you want to proceed?")
    #     col1, col2 = st.columns(2)
    #     with col1:
    #         if st.button("Confirm"):
    #             # If mock mode was toggled, clear everything and go back to Step 1
    #             ss.pop("outline", None)
    #             clear_module_dependent_outputs(ss)
    #             reset_uploaded_content(ss)
    #             ss["current_step"] = 1
    #             st.rerun() # Rerun to dismiss the dialog and update the app state
    #     with col2:
    #         if st.button("Cancel"):
    #             #st.session_state.show_confirm_dialog = False # Optionally manage dialog visibility
    #             ss["MOCK_MODE"] = not ss["MOCK_MODE"]
    #             st.rerun()

    # --- Settings ---
    st.markdown("### Settings")

    # Toggle mock mode
    st.toggle("Mock mode", key="MOCK_MODE", on_change=reset_session, args=(ss, True))
    # Select model
    model_options = ["gpt-4.1-nano", "gpt-4.1-mini", "gpt-4.1"]
    st.selectbox("OpenAI model", model_options, key="OPENAI_MODEL",
                 disabled=ss["MOCK_MODE"])

    # Save/load progress ---
    save_load_panel()

    # Reset button to start over with clean slate
    if st.button("Reset session"):
        reset_session(ss)


################################################
# Visual Stepper
################################################
def render_stepper():
    st.write("")


    outline = "Plan your course structure"
    upload = "Add your module files"
    LOs = "Define and analyze learning objectives"
    quest_gen = "Create questions with AI support"
    export = "Export questions to Microsoft Word"
    
    steps = [outline, upload, LOs, quest_gen, export]

    #############
    # Short button labels (clickable)
    step_labels = [
        "📚 1. Outline",
        "📂 2a. Module ->",
        "🎯 2b. Objectives ->",
        "✍️ 2c. Questions ->",
        "📄 2d. Final Output",
    ]


    #########

    # wrap the whole stepper in a bordered "card"
    with st.container(border=True):
        # slightly larger gaps between steps
        cols = st.columns(len(steps), gap="medium")
        for i, (col, step_name) in enumerate(zip(cols, steps)):
            with col:
                # Clickable button to navigate directly to the step
                #red, orange, yellow, green, blue, violet, gray/grey, rainbow,
                if st.button(f"**{step_labels[i]}**", type="tertiary",
                             disabled=not ss["is_ready_for_step"][i+1], key=f"step_btn_{i+1}"):
                    ss["current_step"] = i + 1
                    st.rerun()
                # Description + Visual indication of current/completed/upcoming steps
                if i + 1 == ss["current_step"]:
                    # active step: prominent info callout
                    st.info(step_name)
                elif i + 1 < ss["current_step"]:
                    # completed step: success callout
                    st.success(step_name)
                else:
                    # upcoming step: subtle border box (not plain text)
                    #with st.container(border=True):
                    st.markdown(f":grey[{step_name}]")

    # crisp separation from the rest of the page
    #st.divider()

################################################
# 1 Course Outline
################################################
def render_step_1():
    st.header("📚 Course Outline")
    st.markdown("""⚠️ Before drafting any learning content, it is essential to first create a clear and detailed course outline.

A course outline acts as a blueprint for the course, ensuring a goal-oriented, logical, and structured learning experience for participants. Once finalized, it helps streamline the entire course development process.
""")
    with st.expander("**Structure of an IMF course**", expanded=False):
        st.markdown(const.COURSE_STRUCTURE_GUIDANCE)
    
    st.markdown("The first step (1. Outline) of this application offers AI-powered support to generate a course outline using any source materials you upload. The more relevant the materials, the better the AI can assist you in structuring your course effectively.")
    # --- User Inputs ---
    files = st.file_uploader(
        "**Upload Source Materials (e.g., papers, presentations, notes)**",
        help="Upload any source materials that will help the AI understand the course context and content.",
        type=["pdf","docx","pptx","txt"],
        accept_multiple_files=True,
        key=f"source_file_uploader_{ss["uploader_key"]}",
        disabled=ss["MOCK_MODE"]
        ) or []
    
    # In mock mode, override with the mock file
    if ss["MOCK_MODE"]:
        files = [const.create_mock_file("assets/mock_uploaded_file.txt")]

    # Compute a stable signature for the current files (for cache keying)
    current_file_keys = tuple((f.name, f.size, getattr(f, "last_modified", None)) for f in files)

    # Process files
    if files:
        with st.spinner("Extracting text. Please wait..."):
            try:
                text, tokens = extract_text_and_tokens(files, file_keys=current_file_keys)
            except Exception as e:
                st.error(e)
                text, tokens = "", 0

        ss["course_files"] = [f.name for f in files]
        ss["course_text"] = text
        ss["course_tokens"] = tokens

        if ss["course_tokens"] > const.MODULE_TOKEN_LIMIT:
            st.error(f"Souce material exceeds {const.MODULE_TOKEN_LIMIT:,} tokens. Reduce content to proceed.")
    
    with st.expander(":small[:grey[View uploaded files and extracted text]]", expanded=False):
        # Display currently uploaded files
        if ss["course_files"]:
            st.caption("Currently uploaded files (To change, use file picker above):")
            current_files = "\n".join([f"{i+1}. {fname}" for i, fname in enumerate(ss["course_files"])])
            st.markdown(current_files)

        # Display token count & preview from session (stable across reruns)
        st.caption(f"Estimated tokens: {ss.get('course_tokens', 0):,}")
        st.caption("Preview first 5,000 characters")
        st.text_area("Preview", (ss.get("course_text") or "")[:5000], height=150, disabled=True, label_visibility="collapsed")
    
    # Additional instructor guidance for the AI
    #  In mock mode, pre-fill with example
    if ss["MOCK_MODE"]:
        ss["outline_guidance"] = "Title should be Public Debt Sustainability. Create 1 module only."
    
    if "outline_guidance_key" not in ss:
        ss["outline_guidance_key"] = ss["outline_guidance"]
    ss["outline_guidance"] = st.text_area("**Additional Guidance for the AI (optional)**",
                                    key="outline_guidance_key",
                                    help="Enter any guidance for the AI to consider when generating the outline. For example, specify the number of modules, key topics to cover, or any special focus areas.",
                                    height=80, max_chars=300, disabled=ss["MOCK_MODE"])

    # --- Generate Outline ---
    #is_ready = bool(ss.get("course_text")) and ss.get("course_tokens", 0) <= const.MODULE_TOKEN_LIMIT
    is_ready = True #bool(ss.get("course_text")) ! user can geenrate outline with no source material
    if st.button("Generate Course Outline", type="primary", disabled=not is_ready):
        with st.spinner("Analyzing documents and generating outline... This may take a moment."):
            clear_outline_widget_state(ss)
            ss['outline'] = generate_outline(ss["outline_guidance"].strip(), ss["course_text"])
            ss["outline_sig"] = sig_outline(ss.get("outline"))
            ss["outline_docx_file"] = b""
            ss["outline_doc_sig"] = None
            st.rerun()

    # --- Display/Edit/Export Output ---
    if 'outline' in ss:

        # Switch between static and editable outline view
        st.write("")
        st.toggle("Editable outline", key="editable_outline", value=False, help="Switch between editable and static outline view. In editable mode, you can modify module and section titles, add or remove sections, and edit section-level objectives.")
        # Display the formatted outline
        if ss["editable_outline"]:
            display_editable_outline(ss['outline'])
        else:
            display_static_outline(ss['outline'])

        current_outline_sig = sig_outline(ss.get("outline"))
        if ss.get("outline_sig") != current_outline_sig:
            ss["outline_sig"] = current_outline_sig

        # Export outline to DOCX
        st.markdown("---")
        st.markdown("#### Export outline")
        cols = st.columns([1, 1])
        with cols[0]:
            if st.button("Build outline DOCX"):
                ss["outline_docx_file"] = build_outline_docx(ss["outline"])
                ss["outline_doc_sig"] = current_outline_sig
        with cols[1]:
            doc_ready = bool(ss.get("outline_docx_file")) and ss.get("outline_doc_sig") == current_outline_sig
            if ss.get("outline_docx_file") and not doc_ready:
                help_msg = "Outline changed. Rebuild the DOCX to download the latest version."
            else:
                help_msg = "Build the outline DOCX before downloading."
            st.download_button(
                "Download outline",
                data=ss.get("outline_docx_file", b""),
                file_name="course_outline.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                disabled=not doc_ready,
                help=help_msg if not doc_ready else "",
                type="primary" if doc_ready else "secondary"
            )

    # --- Navigation ---
    st.divider()
    cols = st.columns([1, 1])
    with cols[1]:
        if st.button("Next: Module level planning →", disabled=not ss["is_ready_for_step"][2]):
            ss["current_step"] = 2
            st.rerun()
################################################
# 2 Upload Course Content
################################################
def render_step_2():
    st.header("📂 Upload Module Material")  
    st.markdown( """You can upload any content that you will use to develop the module.
                A draft module plan works best, but you can also upload background papers, guidance notes,
                presentations, or any other documents that you plan to use for writing the module content.""")
    files: List[Any] = []
    upload_col, import_col = st.columns([8, 3], gap="large", vertical_alignment="center")
    with upload_col:
        files = st.file_uploader(
            "Maximum 27,000 tokens of text (about 20,000 words or 40 single-spaced pages)",
            type=["pdf", "docx", "pptx", "txt"],
            accept_multiple_files=True,
            key=f"module_file_uploader_{ss['uploader_key']}",
            disabled=ss["MOCK_MODE"],
        ) or []
        if ss["MOCK_MODE"]:
            files = [const.create_mock_file("assets/mock_uploaded_file.txt")]
    with import_col:
        import_disabled = not bool(ss.get("course_text"))
        if st.button(
            "📥 Import source files from Outline step",
            help="Import all source material uploaded for the course outline",
            disabled=import_disabled,
        ):
            course_files = list(ss.get("course_files") or [])
            apply_module_content(ss, ss.get("course_text", ""), ss.get("course_tokens", 0) or 0, course_files)
            st.rerun()

# --- Process files based on actual content, not metadata ---
    if files:
        # Build cache key for current files
        current_file_keys = tuple((f.name, getattr(f, "size", None), getattr(f, "last_modified", None)) for f in files)

        # Call the extractor (it will use Streamlit cache if file_keys is provided)
        try:
            text, tokens = extract_text_and_tokens(files, file_keys=current_file_keys)
        except Exception as e:
            st.error(e)
            text, tokens = "", 0

        prev_module_text = ss.get("module_text", "")
        apply_module_content(ss, text, tokens, [f.name for f in files])
        
        # Rerun if module content changed to update step readiness
        if ss.get("module_text", "") != prev_module_text:
            st.rerun()

    if ss.get("module_tokens", 0) > const.MODULE_TOKEN_LIMIT:
        st.error(f"Module exceeds {const.MODULE_TOKEN_LIMIT:,} tokens. Reduce content to proceed.")

    with st.expander("View uploaded files and extracted text", expanded=False):
        # Display currently uploaded files from the session state (stable across reruns)
        if ss["module_files"]:
            st.caption("Currently uploaded files (To change, use file picker above):")
            current_files = "\n".join([f"{i+1}. {fname}" for i, fname in enumerate(ss["module_files"])])
            st.markdown(current_files)

        # Display token count & preview from session (stable across reruns)
        st.caption(f"Estimated tokens: {ss.get('module_tokens', 0):,}")
        st.caption("Preview first 5,000 characters")
        st.text_area("Preview", (ss.get("module_text") or "")[:5000], height=150, disabled=True, label_visibility="collapsed")
    
    # --- Navigation ---
    st.divider()
    cols = st.columns([1, 1])
    with cols[0]:
        if st.button("← Back: Course Outline"):
            ss["current_step"] = 1
            st.rerun()
    with cols[1]:
        if st.button("Next: Define Objectives →", disabled=not ss["is_ready_for_step"][3]):
            ss["current_step"] = 3
            st.rerun()

################################################
# 3 Objectives & Alignment
################################################
def render_step_3():
    help_objectives = """Enter your course learning objectives and the intented cognitive complexity
                    according to Bloom's Taxonomy. Don't worry if you are not familiar with Bloom's;
                    you will find information and tips below and AI will also help you refine your objectives."""
    st.header("🎯 Learning Objectives", help=help_objectives)

    if ss.pop("lo_import_toast", False):
        st.toast("Learning objectives imported. Don't forget to set Bloom levels for further analysis.")

    outline_modules = ((ss.get("outline") or {}).get("modules") or [])
    has_outline_modules = bool(outline_modules)

    st.markdown(const.LO_DEF)
    st.markdown("**Tips for Writing Effective Learning Objectives**")
    st.markdown("Objectives should be developed with the **_SMART_** criteria in mind: **S**pecific, **M**easurable, **A**chievable, **R**ealistic and **T**ime-bound.")
    # SMART Criteria Checklist
    with st.expander("SMART Criteria Checklist", expanded=False):
        st.markdown(const.LO_WRITING_TIPS["smart_criteria"])
    
    # Bloom's Taxonomy reference
    st.markdown(const.BLOOM_DEF)
    # Visual reference (expandable pyramid)
    with st.expander("Bloom's Taxonomy", expanded=False):
        _, center_col, _ = st.columns([1, 3, 1]) # Adjust the ratios as needed
        with center_col:
            st.image(const.BLOOM_PYRAMID_IMAGE, width=500)
        
        st.markdown("""
            To learn more:
            - [Using Bloom's Taxonomy to Write Effective Learning Objectives](https://tips.uark.edu/using-blooms-taxonomy/)
            - [Writing Course and Module Learning Objectives](https://intlmonetaryfund.sharepoint.com/teams/Section-OLTeam-ICDIP/Shared%20Documents/Forms/AllItems.aspx?id=%2Fteams%2FSection%2DOLTeam%2DICDIP%2FShared%20Documents%2FGeneral%2FOL%20Documentation%20and%20Templates%2FCourse%20Level%2F2%2E%20Design%2FCourse%20Level%20Design%2FHow%20to%20create%20objectives%2FBloom%27s%20Taxonomy%20%2D%20Objectives%2Epdf&parent=%2Fteams%2FSection%2DOLTeam%2DICDIP%2FShared%20Documents%2FGeneral%2FOL%20Documentation%20and%20Templates%2FCourse%20Level%2F2%2E%20Design%2FCourse%20Level%20Design%2FHow%20to%20create%20objectives)
            """)
    st.write("---")


    # --- Per-LO UI ---
    for i, lo in enumerate(list(ss["los"])):

        # Seed widget state only once, on creation
        lo_text_key = f"lo_text_{lo['id']}"
        lo_level_key = f"lo_level_{lo['id']}"

        if lo_text_key not in ss:
            ss[lo_text_key] = lo.get("text", "")
        if lo_level_key not in ss:
            ss[lo_level_key] = lo.get("intended_level", None)

        # Invalidate finalization if LO text or level changes (compare to last finalized values)
        is_final = bool(lo.get("final_text"))
        module_sig = ss.get("module_sig", "")
        current_align_sig = sig_alignment(ss[lo_text_key], ss[lo_level_key], module_sig)
        prev_align_sig = lo.get("alignment_sig")
        if prev_align_sig and prev_align_sig != current_align_sig:
            clear_alignment(ss, lo)
            clear_questions(ss, lo["id"])
            lo["final_text"] = None
            is_final = False

        # Container for LO
        st.write("")
        with st.container(border=True):

            # --- LO text area ---
            ta = st.text_area(f"**Objective #{i+1}**", key=lo_text_key, disabled=is_final,
                             label_visibility="visible", height=80, max_chars=170,
                             help="Edit your learning objective here.")
            lo["text"] = ta
            has_avoid_verb = any(verb.lower() in ta.lower() for verb in const.LO_WRITING_TIPS["avoid_verbs"])
            if has_avoid_verb:
                st.warning(f"⚠️ Avoid vague verbs like {', '.join(const.LO_WRITING_TIPS['avoid_verbs'])}. See tips above.")

            # --- Bloom level selector ---
            bloom_options = list(const.BLOOM_LEVEL_DEFS.keys())
            sel = st.selectbox("Intended Bloom level", options=bloom_options, key=lo_level_key,
                               index=None, placeholder="Select ...",
                               disabled=is_final, help="Select the intended Bloom's taxonomy level.",
                               label_visibility="visible")
            lo["intended_level"] = sel
            if sel is None:
                 st.info("Choose a Bloom level to see the definition and common verbs.")
            else:
                st.markdown(f"ℹ️**{const.BLOOM_LEVEL_DEFS[sel]}** \n\n **Common verbs:** {const.BLOOM_VERBS[sel]}")
            
            # --- Visual cue for finalized ---            
            if is_final:
                st.markdown(
                    '<div style="background-color:#e6ffe6;border:1px solid #2ecc40;border-radius:6px;padding:0.5em 0.5em 0.5em 0.5em;margin-bottom:0.5em;">'
                    '<b>Finalized.</b> Click Re-open to edit.'
                    '</div>', unsafe_allow_html=True)
            
            # --- Per-LO buttons ---
            btn_cols = st.columns([1, 1, 1, 1])
            with btn_cols[0]:
                can_check = (not is_final) and bool(lo["text"].strip()) and (lo["intended_level"] is not None)
                if st.button("Alignment Check", key=f"align_{lo['id']}_btn",
                             disabled=not can_check, type="primary",
                             help="Have another pair of AI eyes check your LO."
                             ):
                    with st.spinner("Checking alignment..."):
                        lo["alignment"] = check_alignment(lo["text"], lo["intended_level"], ss["module_text"])
                        lo["alignment_sig"] = sig_alignment(lo["text"], lo["intended_level"], ss.get("module_sig", ""))
                        st.rerun()
            with btn_cols[1]:
                if st.button("Accept as final", key=f"accept_{lo['id']}_btn", disabled=not can_check):
                    lo["final_text"] = lo["text"]
                    # Invalidate questions if needed
                    current_gen_sig = sig_question_gen(lo.get("final_text"), lo["intended_level"], ss.get("module_sig", ""))
                    prev_gen_sig = lo.get("generation_sig")
                    if prev_gen_sig and prev_gen_sig != current_gen_sig:
                        clear_questions(ss, lo["id"])
                        lo["generation_sig"] = None
                    st.rerun()
            with btn_cols[2]:
                if is_final:
                    if st.button("Re-open", key=f"unfinal_{lo['id']}_btn"):
                        lo["final_text"] = None
                        st.rerun()
            with btn_cols[3]:
                if st.button(":x: Delete", key=f"del_{lo['id']}_btn"):
                    ss.pop(lo_text_key, None)
                    ss.pop(lo_level_key, None)
                    #ss.pop(nq_key, None)
                    ss["los"].remove(lo)
                    clear_questions(ss, lo["id"])
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

    # --- Add / Import buttons ---
    add_col, import_col = st.columns([1, 1], vertical_alignment="center")

    # Add new LO
    with add_col:
        if st.button("➕ Add Learning Objective"):
            new_id = str(uuid.uuid4())
            ss["los"].append({
                "id": new_id,
                "text": "",
                "intended_level": None,
                "alignment": None,
                "final_text": None,
                "alignment_sig": None,
                "generation_sig": None
            })
            st.rerun()

    #Import LOs from Outline
    def _collect_module_objectives(module: Dict[str, Any]) -> List[str]:
        collected: List[str] = []
        for section in module.get("sections", []) or []:
            for objective in section.get("sectionLevelObjectives", []) or []:
                text = (objective or "").strip()
                if text:
                    collected.append(text)
        return collected
    
    # 1) Define the dialog
    @st.dialog("Import learning objectives", width="large", dismissible=False)
    def import_lo_dialog(module_labels, label_to_index, outline_modules):
        st.markdown("Select modules from your outline to import their section-level objectives.")
        selected_labels = st.multiselect(
            "Modules",
            options=module_labels,
            key="lo_import_selection",
        )
        
        def _collect_module_objectives(module: Dict[str, Any]) -> List[str]:
            """Extract all section-level objectives from a module."""
            collected: List[str] = []
            for section in module.get("sections", []) or []:
                for objective in section.get("sectionLevelObjectives", []) or []:
                    text = (objective or "").strip()
                    if text:
                        collected.append(text)
            return collected

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Cancel", key="cancel_lo_import"):
                ss["reset_lo_import_selection"] = True
                st.rerun()  # closes the dialog
        with c2:
            if st.button("OK", key="confirm_lo_import", type="primary", disabled=not selected_labels):
                for label in selected_labels:
                    module_idx = label_to_index.get(label)
                    if module_idx is None:
                        continue
                    module = outline_modules[module_idx]
                    for objective_text in _collect_module_objectives(module):
                        new_id = str(uuid.uuid4())
                        ss["los"].append({
                            "id": new_id,
                            "text": objective_text,
                            "intended_level": None,
                            "alignment": None,
                            "final_text": None,
                            "alignment_sig": None,
                            "generation_sig": None,
                        })
                ss["reset_lo_import_selection"] = True
                ss["lo_import_toast"] = True
                st.rerun()  # closes the dialog and updates page

    # 2) Open the dialog from a button
    import_help = " Choose a module from your outline and import its learning objectives"
    with import_col:
        if st.button("📥 Import objectives from Outline", key="import_lo_from_outline",
                     help=import_help, disabled=not has_outline_modules):
            # Prepare labels each time dialog is opened
            module_labels, label_to_index = [], {}
            for idx, module in enumerate(outline_modules):
                title = module.get("moduleTitle") or "Untitled module"
                label = f"Module {idx + 1}: {title}"
                module_labels.append(label)
                label_to_index[label] = idx

            # Clear previous selection when reopening
            if ss.get("reset_lo_import_selection"):
                ss.pop("lo_import_selection", None)
                ss["reset_lo_import_selection"] = False

            import_lo_dialog(module_labels, label_to_index, outline_modules)  # <-- shows modal


    # --- Check All / Accept All buttons ---
    st.write("")
    all_btn_cols = st.columns([1, 1])
    with all_btn_cols[0]:
        if st.button("Check All", type="primary", disabled=not ss["los"]):
            with st.spinner("Checking all learning objectives..."):
                for lo in ss["los"]:
                    lo["alignment"] = check_alignment(lo["text"], lo["intended_level"], ss["module_text"])
                    lo["alignment_sig"] = sig_alignment(lo["text"], lo["intended_level"], ss.get("module_sig", ""))
                st.rerun()
    with all_btn_cols[1]:
        if st.button("Accept All", disabled=not ss["los"]):
            for lo in ss["los"]:
                lo["final_text"] = lo["text"]
                # Invalidate questions if needed
                current_gen_sig = sig_question_gen(lo.get("final_text"), lo["intended_level"], ss.get("module_sig", ""))
                prev_gen_sig = lo.get("generation_sig")
                if prev_gen_sig and prev_gen_sig != current_gen_sig:
                    clear_questions(ss, lo["id"])
                    lo["generation_sig"] = None
            st.rerun()

    # --- Navigation ---
    st.divider()
    cols = st.columns([1, 1])
    with cols[0]:
        if st.button("← Back: Module Materials"):
            ss["current_step"] = 2
            st.rerun()
    with cols[1]:
        if st.button("Next: Generate Questions →", disabled=not ss["is_ready_for_step"][4]):
            ss["current_step"] = 4
            st.rerun()

#################################################
# 4 Generate questions
#################################################
def render_step_4():
    st.header("✍️ Generate Questions")
    st.markdown(const.QUESTION_TIPS)
    # Helper to check if we can run generation
    def can_generate(ss) -> bool:
        return bool(ss["module_text"] and ss["los"] and all(lo.get("final_text") for lo in ss["los"]))
    
    # Render table: LO text and per-LO number input (default 1)
    st.markdown("##### How many questions would you like per learning objective?")
    header_cols = st.columns([6, 1])
    header_cols[0].markdown("**Learning objective**")
    header_cols[1].markdown("**# of Questions**")
    for lo in ss["los"]:
        nq_key = f"nq_{lo['id']}"
        if nq_key not in ss:
            ss[nq_key] = len(ss.get("questions", {}).get(lo["id"], [])) or 1
        lo_display = lo.get("final_text") or lo.get("text") or "(no text)"
        row_cols = st.columns([6, 1])
        row_cols[0].markdown(lo_display)
        row_cols[1].number_input("", min_value=0, max_value=5,
                                 key=nq_key, label_visibility="collapsed")

    if st.button("Generate", type="primary", disabled=not can_generate(ss)):
        with st.spinner("Generating questions..."):
            # Clear all existing questions (if any)
            clear_questions(ss)
            # Go over all LOs and generate questions using per-LO n
            for lo in ss["los"]:
                nq = ss.get(f"nq_{lo['id']}", 1)
                if nq==0:
                    continue
                payload = generate_questions(
                    lo.get("final_text"),
                    lo["intended_level"],
                    ss["module_text"],
                    n_questions=nq,
                )

                ss["questions"][lo["id"]] = payload["questions"]
                # store signature for question generation
                lo["generation_sig"] = sig_question_gen(
                    lo.get("final_text"),
                    lo["intended_level"],
                    ss.get("module_sig", "")
                )
            # After regeneration, update questions_sig
            ss["questions_sig"] = sig_questions(ss["questions"])
            st.rerun()

    # Check if there are any questions to display
    has_questions = any(ss["questions"].get(lo["id"], []) for lo in ss["los"])
    # Switch between static and editable questions view
    if has_questions:
        st.write("")
        st.toggle(
            "Editable questions",
            key="editable_questions",
            value=False,
            help=(
                "Switch between editable and static question views. In editable mode, you can refine stems, options, "
                "and rationales."
            ),
        )
        # Go over all LOs, each in a container
        for lo in ss["los"]:
            qs = ss["questions"].get(lo["id"], [])
            if not qs:
                continue
            with st.container(border=True):
                st.subheader(lo.get("final_text"))
                # Go over all questions for this LO
                for idx, q in enumerate(qs):
                    with st.expander(f"**{idx + 1}. {q.get('stem', 'N/A')}**", expanded=False):
                        # Display static or editable question details based on toggle
                        if ss["editable_questions"]:
                            display_editable_question(lo["id"], idx,q)
                        else:
                            display_static_question(q)

    # After all widgets have applied edits, detect real changes
    new_q_sig = sig_questions(ss.get("questions", {}))
    if ss.get("questions_sig") and ss["questions_sig"] != new_q_sig:
        # User changed questions → previously built DOCX is now stale
        ss["docx_file"] = "" #None
    ss["questions_sig"] = new_q_sig

    # --- Navigation ---
    st.divider()
    cols = st.columns([1, 1])
    with cols[0]:
        if st.button("← Back: Define Objectives"):
            ss["current_step"] = 3
            st.rerun()
    with cols[1]:
        if st.button("Next: Export →", disabled=not ss["is_ready_for_step"][5]):
            ss["current_step"] = 5
            st.rerun()
    
################################################
# 5 Export
################################################
def render_step_5():

    st.header("📄 Export to Word")
    st.markdown("")

    # Export selection: allow user to choose which metadata blocks to include
    st.markdown("##### Metadata to be included with questions:")

    # Seed checkbox states only once, on widget creation
    for block in ["lo", "bloom", "rationale", "answer", "feedback", "content"]:
        key = f"exp_inc_{block}"
        if key not in ss:
            ss[key] = ss['include_opts'].get(block, True)

    cols = st.columns([1,1])
    with cols[0]:
        inc_lo = st.checkbox("Learning objectives", key="exp_inc_lo",
                              help="Include the learning objective before its questions")
        inc_bloom = st.checkbox("Bloom levels", key="exp_inc_bloom",
                                help="Show Bloom level for each LO")
        inc_rationale = st.checkbox("Rationale for Bloom level", key="exp_inc_rationale",
                                    help="Include rationale explaining the Bloom level")
    with cols[1]:
        inc_answer = st.checkbox("Answer", key="exp_inc_answer",
                                 help="Show the correct answer option")
        inc_feedback = st.checkbox("Feedback", key="exp_inc_feedback",
                                   help="Include feedback / rationale for each option")
        inc_content = st.checkbox("Content reference", key="exp_inc_content",
                                  help="Include reference to module content for each question")
    # Persist current selection
    ss['include_opts'] = {
        "lo": inc_lo,
        "bloom": inc_bloom,
        "answer": inc_answer,
        "feedback": inc_feedback,
        "content": inc_content,
        "rationale": inc_rationale,
    }

    st.markdown("")
    cols = st.columns([1,1])
    with cols[0]:
        if st.button("Build question DOCX"):
            ss["docx_file"] = build_questions_docx(ss["los"], ss["questions"], include=ss['include_opts'])
            ss["prev_build_inc_opts"] = ss['include_opts']
    with cols[1]:
        no_docx_for_selection = not ss.get("docx_file") or ss['prev_build_inc_opts'] != ss['include_opts']
        help_string = "⚠️ Build the DOCX file to enable download for the current selection." 
        st.download_button(
            "Download questions",
            data=ss.get("docx_file", ""),
            file_name="assessment_questions.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            disabled = no_docx_for_selection,
            type="primary" if not no_docx_for_selection else "secondary",
            help=help_string if no_docx_for_selection else ""
            )        
    
    # --- Navigation ---
    st.divider()
    if st.button("← Back: Generate Questions"):
        ss["current_step"] = 4
        st.rerun()

################################################
# Main application router
################################################

compute_step_readiness(ss)
render_stepper()
if ss["current_step"] == 1:
    render_step_1()
elif ss["current_step"] == 2:
    render_step_2()
elif ss["current_step"] == 3:
    render_step_3()
elif ss["current_step"] == 4:
    render_step_4()
elif ss["current_step"] == 5:
    render_step_5()
