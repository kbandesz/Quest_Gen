"""Main UI logic of the BEACON-Design app."""
import streamlit as st
import uuid
from typing import Dict, Any, List, Tuple

from app.parse_input_files import extract_text_and_tokens
from app.generate_llm_output import generate_outline, check_alignment, generate_questions, show_api_error
from app.export_docx import build_outline_docx_cached, build_questions_docx_cached
from app.display_outline import display_editable_outline, display_static_outline
from app.display_questions import (
    clear_deleted_question_widget_state,
    create_empty_question,
    display_editable_question,
    display_question_actions,
    display_static_question,
)
from app.save_load_progress import save_load_panel, apply_pending_restore
import app.constants as const
from app.session_state_utils import (
    init_session_state,
    sig_alignment,
    sig_question_gen,
    compute_step_readiness,
    clear_outline_widget_state,
    clear_alignment,
    clear_questions,
    apply_module_content,
    apply_lo_material_content,
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
mock_warning = ":red[MOCK MODE]"
st.title(f":rainbow[BEACON-Design] {mock_warning if ss['MOCK_MODE'] else ''}")
st.markdown("##### _Smarter course design—powered by AI._")

################################################
# Sidebar for settings & save/load
################################################
with st.sidebar:

    # --- Settings ---
    st.markdown("### Settings")

    # Toggle mock mode (changes are applied only after confirmation)
    ss.setdefault("mock_mode_toggle", ss.get("MOCK_MODE", True))

    def _handle_mock_mode_toggle():
        desired_mock_mode = bool(ss.get("mock_mode_toggle"))
        current_mock_mode = bool(ss.get("MOCK_MODE"))
        if desired_mock_mode == current_mock_mode:
            return
        ss["pending_mock_mode"] = desired_mock_mode
        reset_session(ss, True)

    st.toggle("Mock mode", key="mock_mode_toggle", on_change=_handle_mock_mode_toggle)
    # Select model
    model_options = ["gpt-4.1", "gpt-5-mini", "gpt-5", "gpt-5.2", "gpt-5.4"]

    current_model = ss.get("OPENAI_MODEL")
    if current_model not in model_options:
        legacy_model_map = {
            "gpt-4.1, gpt-5-mini": "gpt-4.1",
        }
        ss["OPENAI_MODEL"] = legacy_model_map.get(current_model, model_options[0])

    st.selectbox("OpenAI model", model_options, key="OPENAI_MODEL",
                 disabled=ss["MOCK_MODE"])

    # Save/load session ---
    save_load_panel()

    # Reset button to start over with clean slate
    if st.button("Reset session"):
        reset_session(ss)


################################################
# Knowledge Base
################################################
# Helpers for managing file uploads and selections across the app
def _extract_single_uploaded_file(uploaded_file) -> Tuple[str, int]:
    file_key = ((uploaded_file.name, getattr(uploaded_file, "size", None), getattr(uploaded_file, "last_modified", None)),)
    return extract_text_and_tokens([uploaded_file], file_keys=file_key)

def _build_mock_kb_entry(file_name: str, file_path: str) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as handle:
        content = handle.read().strip()
    wrapped = f"<{file_name}>\n\n{content}\n\n</{file_name}>"
    return {
        "name": file_name,
        "text": wrapped,
        "tokens": len(wrapped.split()),
        "size": len(content.encode("utf-8")),
    }

def _ensure_mock_knowledge_files() -> None:
    """Seed mock knowledge files once per entry into mock mode."""
    if not ss.get("MOCK_MODE"):
        ss.pop("mock_kb_seeded", None)
        return

    if ss.get("mock_kb_seeded"):
        return

    ss["knowledge_files"] = {
        "mock_uploaded_file_1.txt": _build_mock_kb_entry("mock_uploaded_file_1.txt", "assets/mock_uploaded_file_1.txt"),
        "mock_uploaded_file_2.txt": _build_mock_kb_entry("mock_uploaded_file_2.txt", "assets/mock_uploaded_file_2.txt"),
    }

    ss["tool_file_selection"] = {
        "Course Outliner": [],
        "Learning Objective Analysis": [],
        "Assessment Builder": [],
    }

    for widget_key in ["kb_selection_course", "kb_selection_lo", "kb_selection_builder"]:
        ss.pop(widget_key, None)

    ss["mock_kb_seeded"] = True

def _selected_kb_payload(tool_name: str) -> Tuple[List[str], str, int]:
    selected = list((ss.get("tool_file_selection") or {}).get(tool_name, []))
    kb_files = ss.get("knowledge_files") or {}
    valid_selection = [name for name in selected if name in kb_files]
    if valid_selection != selected:
        ss["tool_file_selection"][tool_name] = valid_selection

    texts: List[str] = []
    tokens = 0
    for file_name in valid_selection:
        file_payload = kb_files.get(file_name, {})
        texts.append(file_payload.get("text", ""))
        tokens += int(file_payload.get("tokens", 0) or 0)
    return valid_selection, "\n\n----- FILE BREAK -----\n\n".join([chunk for chunk in texts if chunk]), tokens


def _render_material_selection(tool_name: str, state_prefix: str):
    kb_files = ss.get("knowledge_files") or {}
    options = list(kb_files.keys())
    selected_default = list((ss.get("tool_file_selection") or {}).get(tool_name, []))

    if options:
        selected = st.pills(
            "Select materials from Knowledge Base",
            options=options,
            selection_mode="multi",
            default=selected_default,
            key=f"kb_selection_{state_prefix}",
            help="Go to Knowledge Base to upload files. Re-uploading a file with the same name replaces the previous one.",
        ) or []
        ss["tool_file_selection"][tool_name] = selected
    else:
        ss["tool_file_selection"][tool_name] = []
        st.info("No files available. Go to **Knowledge Base → Upload** to add source materials.")

# Knowledge Base Upload UI
def render_knowledge_base_upload():
    st.header("🗂️ Knowledge Base")
    st.markdown("Upload source files once, then select them in each tool's Materials step.")
    st.caption("If you upload a file with the same filename again, the new upload replaces the previous one.")

    if ss["MOCK_MODE"]:
        st.info("Mock mode is enabled: the Knowledge Base uploader is disabled and preloaded with two mock files.")

    files = st.file_uploader(
        "Upload knowledge files",
        help="Supported formats: pdf, docx, pptx, txt",
        type=["pdf", "docx", "pptx", "txt"],
        accept_multiple_files=True,
        key=f"kb_file_uploader_{ss['uploader_key']}",
        disabled=ss["MOCK_MODE"],
    ) or []

    if not files:
        ss.pop("kb_uploader_sig", None)

    if files and not ss["MOCK_MODE"]:
        current_upload_sig = tuple((f.name, getattr(f, "size", None), getattr(f, "last_modified", None)) for f in files)
        if ss.get("kb_uploader_sig") != current_upload_sig:
            with st.spinner("Extracting text. Please wait..."):
                for uploaded_file in files:
                    try:
                        text, tokens = _extract_single_uploaded_file(uploaded_file)
                    except Exception as exc:
                        st.error(exc)
                        continue
                    ss["knowledge_files"][uploaded_file.name] = {
                        "name": uploaded_file.name,
                        "text": text,
                        "tokens": tokens,
                        "size": getattr(uploaded_file, "size", 0),
                    }
            ss["kb_uploader_sig"] = current_upload_sig
            ss["uploader_key"] = ss.get("uploader_key", 0) + 1
            st.success("Knowledge Base updated.")
            st.rerun()

    if ss.get("knowledge_files"):
        st.markdown("#### Uploaded files")

        header_cols = st.columns([6, 2, 1], vertical_alignment="center")
        header_cols[1].markdown("**Tokens**")

        total_tokens = 0
        for file_name in list(ss["knowledge_files"].keys()):
            payload = ss["knowledge_files"][file_name]
            file_tokens = int(payload.get("tokens", 0) or 0)
            total_tokens += file_tokens
            row_cols = st.columns([6, 2, 1], vertical_alignment="center")
            row_cols[0].markdown(f"**{file_name}**")
            row_cols[1].caption(f"{file_tokens:,}")
            if row_cols[2].button("🗑️", key=f"drop_kb_{file_name}", help="Drop file from knowledge base"):
                selected_in = [
                    tool_name
                    for tool_name, selected_files in (ss.get("tool_file_selection") or {}).items()
                    if file_name in (selected_files or [])
                ]
                if selected_in:
                    st.warning(
                        f"Cannot drop '{file_name}' because it is selected in: {', '.join(selected_in)}. "
                        "Please unselect it in those tools first."
                    )
                else:
                    ss["knowledge_files"].pop(file_name, None)
                    st.rerun()

        footer_cols = st.columns([6, 2, 1], vertical_alignment="center")
        footer_cols[0].markdown(":blue[**TOTAL**]")
        footer_cols[1].markdown(f":blue[**{total_tokens:,}**]")
    else:
        st.info("No files uploaded yet.")

################################################
# Course Outliner
################################################
def render_outliner_materials():
    st.header("📚 Course Outline")
    st.markdown("""⚠️ Before drafting any learning content, it is essential to first create a clear and detailed course outline.

A course outline acts as a blueprint for the course, ensuring a goal-oriented, logical, and structured learning experience for participants. Once finalized, it helps streamline the entire course development process.
""")
    with st.expander("**Structure of an IMF course**", expanded=True):
        st.markdown(const.COURSE_STRUCTURE_GUIDANCE)

    st.markdown("The **Course Outliner** tool uses files from the Knowledge Base. Select relevant materials below to help AI generate a stronger outline.")
    _render_material_selection("Course Outliner", "course")

    selected_files, text, tokens = _selected_kb_payload("Course Outliner")

    ss["course_files"] = selected_files
    ss["course_text"] = text
    ss["course_tokens"] = tokens

    if ss["course_tokens"] > const.MODULE_TOKEN_LIMIT:
        st.error(f"Souce material exceeds {const.MODULE_TOKEN_LIMIT:,} tokens. You can still try, but be prepared for hitting API limits.")

    if ss["course_files"]:
        with st.expander(":small[:grey[View extracted text]]", expanded=False):
            st.caption(f"Estimated tokens: {ss.get('course_tokens', 0):,}")
            st.caption("Preview first 5,000 characters")
            st.text_area("Preview", (ss.get("course_text") or "")[:5000], height=150, disabled=True, label_visibility="collapsed")

    st.divider()
    cols = st.columns([2, 1])
    with cols[1]:
        st.button("Next: Design Outline →", on_click=lambda: ss.update({"key_outliner_nav": "Outline"}))

def render_outliner_design():
    st.header("Outline Design")
    st.markdown("""Our AI agents received detailed guidance on instructional design best practices related to course outlines. They were also instructed to design outlines that satisfy the formal requreiments of IMF courses.
                However, you can provide further instructions for generating or refining your course outline. Be parsimonious and rely on an iterative human-AI collaboration rather than trying to overload the AI with detailed requirements.
                """)
    # Additional instructor guidance for the AI
    if ss["MOCK_MODE"]:
        ss["outline_guidance"] = "Title should be Public Debt Sustainability. Create 2 moduls."

    if "outline_guidance_key" not in ss:
        ss["outline_guidance_key"] = ss["outline_guidance"]
    ss["outline_guidance"] = st.text_area(
        "**Additional Guidance for the AI (optional)**",
        key="outline_guidance_key",
        help="Enter any guidance for the AI to consider when generating the outline. For example, specify the number of modules, key topics to cover, or any special focus areas.",
        height=80,
        max_chars=300,
        disabled=ss["MOCK_MODE"],
    )

    # --- Generate Outline ---
    is_ready_for_outline = ss["outliner_readiness"]["Outline"]
    if st.button("Generate Course Outline", type="primary", disabled=not is_ready_for_outline,
                 help="Select files from the knowledge base for your outline." if not is_ready_for_outline else ""):
        ss["editable_outline"] = False #reset to static view on new generation
        with st.spinner("Analyzing documents and generating outline... This may take a moment."):
            try:
                clear_outline_widget_state(ss)
                ss['outline'] = generate_outline(ss["outline_guidance"].strip(), ss["course_text"])
            except RuntimeError as err:
                show_api_error(err)
                return
            # ss["outline_sig"] = sig_outline(ss.get("outline"))
            # ss["outline_docx_file"] = b""
            # ss["outline_doc_sig"] = None
            st.rerun()

    # --- Display/Edit/Export Output ---
    if 'outline' in ss:

        # Switch between static and editable outline view
        st.write("")
        st.toggle("Edit mode", key="editable_outline", value=False, help="Switch between editable and static outline view. In editable mode, you can modify module and section titles, add or remove sections, and edit section-level objectives.")
        # Display the formatted outline
        if ss["editable_outline"]:
            display_editable_outline(ss['outline'])
        else:
            display_static_outline(ss['outline'])

        # --- Export outline ---
        st.markdown("---")
        st.markdown("#### 📄 Export to Word")

        outline = ss.get("outline")

        st.download_button(
            "Download",
            data=lambda: build_outline_docx_cached(outline),
            file_name="course_outline.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            disabled=not bool(outline),
            help="Download outline as a Word file.",
            type="primary" if bool(outline) else "secondary"
        )

    st.divider()
    st.button("← Back: Materials for Outline", on_click=lambda: ss.update({"key_outliner_nav": "Materials"}))

################################################
# Learning Objective Analyzer
################################################
def render_lo_analysis_materials():
    st.header("📂 Select Learning Objective Analysis Material")
    st.markdown("""Select content from the Knowledge Base that you will use to analyze learning objectives.
                A draft module plan works best, but you can also select background papers, guidance notes,
                presentations, or any other supporting documents.""")

    _render_material_selection("Learning Objective Analysis", "lo")

    selected_files, text, tokens = _selected_kb_payload("Learning Objective Analysis")

    prev_lo_material_text = ss.get("lo_material_text", "")
    apply_lo_material_content(ss, text, tokens, selected_files)
    if ss.get("lo_material_text", "") != prev_lo_material_text:
        st.rerun()

    if ss.get("lo_material_tokens", 0) > const.MODULE_TOKEN_LIMIT:
        st.error(f"Module exceeds {const.MODULE_TOKEN_LIMIT:,} tokens. Reduce content to proceed.")

    if ss["lo_material_files"]:
        with st.expander("View extracted text", expanded=False):
            st.caption(f"Estimated tokens: {ss.get('lo_material_tokens', 0):,}")
            st.caption("Preview first 5,000 characters")
            st.text_area("Preview", (ss.get("lo_material_text") or "")[:5000], height=150, disabled=True, label_visibility="collapsed")

    st.divider()
    cols = st.columns([2, 1])
    with cols[1]:
        st.button("Next: Define and Analyze Objectives →",
                  on_click=lambda: ss.update({"key_lo_analysis_nav": "Objectives"}),
                  )

def render_lo_analysis_objectives():
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
    st.info("💡 Starting from scratch? You can write your own objectives below, or switch to the **Course Outliner** tool above to generate them, then import them here.")

    if ss["MOCK_MODE"] and not ss["los"]:
        ss["los"].append({
            "id": str(uuid.uuid4()),
            "text": "Mock objective 1",
            "intended_level": "Apply",
            "alignment": None,
            "final_text": None,
            "alignment_sig": None,
            "generation_sig": None,
        })


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
        module_sig = ss.get("lo_material_sig", "")
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
            st.info("Choose a Bloom level to see the definition and common verbs.")
            bloom_options = list(const.BLOOM_LEVEL_DEFS.keys())
            sel = st.selectbox("Intended Bloom level", options=bloom_options, key=lo_level_key,
                               index=None, placeholder="Select ...",
                               disabled=is_final, help="Select the intended Bloom's taxonomy level.",
                               label_visibility="visible")
            lo["intended_level"] = sel
            if lo["intended_level"]:
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
                        try:
                            lo["alignment"] = check_alignment(lo["text"], lo["intended_level"], ss["lo_material_text"])
                        except RuntimeError as err:
                            show_api_error(err)
                            return
                        lo["alignment_sig"] = sig_alignment(lo["text"], lo["intended_level"], ss.get("lo_material_sig", ""))
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

    # Import LOs from Outline
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


    #--- Check All / Accept All buttons ---
    st.write("")
    los_with_pending_alignment = [
        lo for lo in ss["los"]
        if bool((lo.get("text") or "").strip())
        and lo.get("intended_level") is not None
        and lo.get("alignment") is None
    ]
    los_ready_to_accept = [
        lo for lo in ss["los"]
        if bool((lo.get("text") or "").strip())
        and lo.get("intended_level") is not None
        and not lo.get("final_text")
    ]
    all_btn_cols = st.columns([1, 1])
    with all_btn_cols[0]:
        if st.button("Check All", type="primary", disabled=not los_with_pending_alignment):
            with st.spinner("Checking all learning objectives..."):
                for lo in los_with_pending_alignment:
                    try:
                        lo["alignment"] = check_alignment(lo["text"], lo["intended_level"], ss["lo_material_text"])
                    except RuntimeError as err:
                        show_api_error(err)
                        return
                    lo["alignment_sig"] = sig_alignment(lo["text"], lo["intended_level"], ss.get("lo_material_sig", ""))
                st.rerun()
    with all_btn_cols[1]:
        if st.button("Accept All", disabled=not los_ready_to_accept):
            for lo in los_ready_to_accept:
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
    cols = st.columns([2, 1])
    with cols[0]:
        st.button("← Back: Materials for LOs",
                  on_click=lambda: ss.update({"key_lo_analysis_nav": "Materials"}),
                  )


################################################
# Assessment Builder
################################################
def render_builder_materials():
    st.header("📂 Select Module Material")
    st.markdown("""Select content from the Knowledge Base that you will use to develop the module.
                A draft module plan works best, but you can also select background papers, guidance notes,
                presentations, or any other supporting documents.""")

    _render_material_selection("Assessment Builder", "builder")

    selected_files, text, tokens = _selected_kb_payload("Assessment Builder")

    prev_module_text = ss.get("module_text", "")
    apply_module_content(ss, text, tokens, selected_files)
    if ss.get("module_text", "") != prev_module_text:
        st.rerun()

    if ss.get("module_tokens", 0) > const.MODULE_TOKEN_LIMIT:
        st.error(f"Module exceeds {const.MODULE_TOKEN_LIMIT:,} tokens. Reduce content to proceed.")

    if ss["module_files"]:
        with st.expander("View extracted text", expanded=False):
            st.caption(f"Estimated tokens: {ss.get('module_tokens', 0):,}")
            st.caption("Preview first 5,000 characters")
            st.text_area("Preview", (ss.get("module_text") or "")[:5000], height=150, disabled=True, label_visibility="collapsed")

    st.divider()
    cols = st.columns([2, 1])
    with cols[1]:
        st.button("Next: Generate Questions →",
                  on_click=lambda: ss.update({"key_builder_nav": "Questions"}),
                  )

def render_builder_questions():
    st.header("✍️ Generate Questions")
    st.markdown(const.QUESTION_TIPS)
    # Helper to check if we can run generation
    def can_generate(ss) -> bool:
        return bool(ss["module_text"] and ss["los"] and all(lo.get("final_text") for lo in ss["los"]))
    
    # Render table: LO text and per-LO number input (default 0)
    st.markdown("##### How many new questions would you like to generate per learning objective?")
    if ss.pop("reset_question_counts", False):
        for lo in ss["los"]:
            ss[f"nq_{lo['id']}"] = 0

    header_cols = st.columns([6, 1])
    header_cols[0].markdown("**Learning objective**")
    header_cols[1].markdown("**# of Questions**")
    for lo in ss["los"]:
        nq_key = f"nq_{lo['id']}"
        if nq_key not in ss:
            ss[nq_key] = 0
        lo_display = lo.get("final_text") or lo.get("text") or "(no text)"
        row_cols = st.columns([6, 1])
        row_cols[0].markdown(lo_display)
        row_cols[1].number_input("", min_value=0, max_value=5,
                                 key=nq_key, label_visibility="collapsed")
    is_ready_for_questions = ss["builder_readiness"]["Questions"]
    if st.button("Generate Questions", type="primary", disabled=not is_ready_for_questions,
                 help="Select source material and finalize learning objectives for question generation." if not is_ready_for_questions else ""):
        with st.spinner("Generating questions..."):
            ss["editable_questions"] = False #reset to static view on new generation
            # Go over all LOs and generate questions using per-LO n
            for lo in ss["los"]:
                nq_key = f"nq_{lo['id']}"
                nq = ss.get(nq_key, 0)
                if nq==0:
                    continue
                try:
                    payload = generate_questions(
                        lo.get("final_text"),
                        lo["intended_level"],
                        ss["module_text"],
                        n_questions=nq,
                    )
                except RuntimeError as err:
                    show_api_error(err)
                    return
                existing_questions = ss["questions"].setdefault(lo["id"], [])
                existing_questions.extend(payload["questions"])
                # store signature for question generation
                lo["generation_sig"] = sig_question_gen(
                    lo.get("final_text"),
                    lo["intended_level"],
                    ss.get("module_sig", "")
                )
            ss["reset_question_counts"] = True
            st.rerun()

    # Check if there are any questions to display
    # has_questions = any(ss["questions"].get(lo["id"], []) for lo in ss["los"])
    # has_questions = True
    # Switch between static and editable questions view
    # if has_questions:
    st.write("")
    st.toggle(
        "Edit mode",
        key="editable_questions",
        value=False,
        help=(
            "Switch between editable and static question views. In editable mode, you can refine stems, options, "
            "and rationales."
        ),
    )
    # Go over all LOs, each in a container
    for lo in ss["los"]:
        qs = ss["questions"].setdefault(lo["id"], [])
        # if not qs:
        #     continue
        with st.container(border=True):
            st.subheader(lo.get("final_text"))
            # Go over all questions for this LO
            pending_delete_idx = None
            pending_move = None
            for idx, q in enumerate(qs):
                stem_preview = q.get("stem") or "(no question stem)"
                if ss["editable_questions"]:
                    question_header_cols = st.columns([10, 1], vertical_alignment="center")
                    with question_header_cols[0]:
                        st.markdown(f"**{idx + 1}. {stem_preview}**")
                    with question_header_cols[1]:
                        question_action = display_question_actions(lo["id"], idx, len(qs), q)
                        if question_action == "delete":
                            pending_delete_idx = idx
                        elif question_action == "move_up":
                            pending_move = (idx, idx - 1)
                        elif question_action == "move_down":
                            pending_move = (idx, idx + 1)

                    with st.expander("Edit question", expanded=False):
                    # Display editable question
                        display_editable_question(lo["id"], q)
                else:
                    with st.expander(f"**{idx + 1}. {stem_preview}**", expanded=False):
                        display_static_question(q)

            if ss["editable_questions"]:
                if pending_delete_idx is not None:
                    deleted_question = qs.pop(pending_delete_idx)
                    clear_deleted_question_widget_state(lo["id"], deleted_question)
                    st.rerun()

                if pending_move is not None:
                    source_idx, target_idx = pending_move
                    if 0 <= source_idx < len(qs) and 0 <= target_idx < len(qs):
                        qs[source_idx], qs[target_idx] = qs[target_idx], qs[source_idx]
                    st.rerun()

                if st.button("+ Add question manually", key=f"add_q_{lo['id']}"):
                    qs.append(create_empty_question())
                    st.rerun()



    # Export to Word
    has_questions = any(ss["questions"].get(lo["id"], []) for lo in ss["los"])
    if has_questions:
        st.subheader("", divider="blue")
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

        # Download button with on-the-fly generation (cached)
        st.markdown("")
        questions = ss.get("questions", {})
        los = ss.get("los", [])
        include = ss.get("include_opts", {})

        doc_ready = bool(los) and bool(questions)

        st.download_button(
            "Download",
            data=lambda: build_questions_docx_cached(
                los,
                questions,
                include,
            ),
            file_name="assessment_questions.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            disabled=not doc_ready,
            help="Download questions as a Word file. The file will include the metadata you selected in the checkboxes.",
            type="primary" if doc_ready else "secondary"
        )

    # --- Navigation ---
    st.divider()
    st.button("← Back: Materials for Questions",
              on_click=lambda: ss.update({"key_builder_nav": "Materials"}),
              )



################################################
# Main application router (navigation bar)
################################################

# Callback to manage navigation states
def handle_nav(parent: str):
    """Returns a callback function to handle navigation changes for a given parent component.
    The callback ensures that if the navigation key is set to None, it reverts back to the current step.
    Requires strict naming convention for session state keys.
    """
    if ss[f"key_{parent}_nav"] is None:
        ss[f"key_{parent}_nav"] = ss[f"{parent}_step"]
    else:
        ss[f"{parent}_step"] = ss[f"key_{parent}_nav"]

# Top level navigation (tool choice)
def render_tool_picker():
    if "key_tool_nav" not in ss:
        ss["key_tool_nav"] = ss["tool_step"]
    st.segmented_control(
        "Select Tool",
        ["Knowledge Base", "Course Outliner", "Learning Objective Analysis", "Assessment Builder"],
        selection_mode="single",
        format_func=lambda x: f"**{x}**",
        key="key_tool_nav",
        on_change = handle_nav(parent = "tool"),
        label_visibility="collapsed",
        width="stretch",
    )

# Level-2 navigation and routing in Knowledge Base component
def render_knowledge_base():
    if "key_knowledge_base_nav" not in ss:
        ss["key_knowledge_base_nav"] = ss["knowledge_base_step"]
    st.pills(
        "Knowledge Base Steps",
        ["Upload"],
        key="key_knowledge_base_nav",
        on_change=handle_nav(parent="knowledge_base"),
        label_visibility="collapsed",
        width="stretch",
    )
    render_knowledge_base_upload()

# Level-2 navigation and routing in Course Outliner component
def render_course_outliner():
    if "key_outliner_nav" not in ss:
        ss["key_outliner_nav"] = ss["outliner_step"]
    st.pills(
        "Outliner Steps",
        ["Materials", "Outline"],
        format_func=lambda x: f"{x} &emsp; >>>" if x != "Outline" else x,
        key="key_outliner_nav",
        on_change=handle_nav(parent = "outliner"),
        #default=ss.outliner_step,
        label_visibility="collapsed",
        width="stretch",
        )   
      
    if ss["outliner_step"] == "Materials":
        render_outliner_materials()
    elif ss["outliner_step"] == "Outline":
        render_outliner_design()

# Level-2 navigation and routing in Learning Objective Analysis component
def render_lo_analysis():
    if "key_lo_analysis_nav" not in ss:
        ss["key_lo_analysis_nav"] = ss["lo_analysis_step"]
    st.pills(
        "Learning Objective Analysis Steps",
        ["Materials", "Objectives"],
        format_func=lambda x: f"{x} &emsp; >>>" if x != "Objectives" else x,
        key="key_lo_analysis_nav",
        on_change=handle_nav(parent = "lo_analysis"),
        label_visibility="collapsed",
        width="stretch",
        )

    if ss["lo_analysis_step"] == "Materials":
        render_lo_analysis_materials()
    elif ss["lo_analysis_step"] == "Objectives":
        render_lo_analysis_objectives()

# Level-2 navigation and routing in Assessment Builder component
def render_assessment_builder():
    if "key_builder_nav" not in ss:
        ss["key_builder_nav"] = ss["builder_step"]
    st.pills(
        "Assessment Steps",
        ["Materials", "Questions"],
        format_func=lambda x: f"{x} &emsp; >>>" if x != "Questions" else x,
        key="key_builder_nav",
        on_change=handle_nav(parent = "builder"),
        label_visibility="collapsed",
        width="stretch",
        )

    if ss["builder_step"] == "Materials":
        render_builder_materials()
    elif ss["builder_step"] == "Questions":
        render_builder_questions()

# Level-1 navigation between top components
_ensure_mock_knowledge_files()
compute_step_readiness(ss)
render_tool_picker()
if ss["tool_step"] == "Knowledge Base":
    render_knowledge_base()
elif ss["tool_step"] == "Course Outliner":
    render_course_outliner()
elif ss["tool_step"] == "Learning Objective Analysis":
    render_lo_analysis()
elif ss["tool_step"] == "Assessment Builder":
    render_assessment_builder()
