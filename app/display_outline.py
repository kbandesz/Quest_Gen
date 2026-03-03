"""UI elements to display course outlines (static and editable) from the session state."""

import streamlit as st
from typing import Dict, Any

ss = st.session_state


def _clear_outline_widget_cache():
    """Clear cached outline widgets after structural edits."""
    keys_to_remove = [key for key in ss.keys() if str(key).startswith("outline__")]
    for key in keys_to_remove:
        del ss[key]


def _new_module() -> Dict[str, Any]:
    return {
        "moduleTitle": "PLACEHOLDER: Module title",
        "overview": "PLACEHOLDER: Module overview",
        "sections": [_new_section()],
    }


def _new_section() -> Dict[str, Any]:
    return {
        "sectionTitle": "PLACEHOLDER: Section title",
        "sectionLevelObjectives": ["PLACEHOLDER: Section-level objective"],
        "units": [_new_unit()],
    }


def _new_unit() -> Dict[str, Any]:
    return {
        "unitTitle": "PLACEHOLDER: Unit title",
        "unitLevelObjective": "PLACEHOLDER: Unit-level objective",
        "keyPoints": ["PLACEHOLDER: Key point 1", "PLACEHOLDER: Key point 2"],
    }


def _delete_module(module_index: int):
    modules = ss.get("outline", {}).get("modules", [])
    if 0 <= module_index < len(modules):
        modules.pop(module_index)
        if not modules:
            modules.append(_new_module())
        _clear_outline_widget_cache()


def _move_module(module_index: int, target_index: int):
    modules = ss.get("outline", {}).get("modules", [])
    if 0 <= module_index < len(modules) and 0 <= target_index < len(modules):
        modules[module_index], modules[target_index] = modules[target_index], modules[module_index]
        _clear_outline_widget_cache()


def _add_module(insert_at: int | None = None):
    outline = ss.setdefault("outline", {})
    modules = outline.setdefault("modules", [])
    if insert_at is None or insert_at < 0 or insert_at > len(modules):
        modules.append(_new_module())
    else:
        modules.insert(insert_at, _new_module())
    _clear_outline_widget_cache()


def _add_section(module_index: int, insert_at: int | None = None):
    modules = ss.get("outline", {}).get("modules", [])
    if 0 <= module_index < len(modules):
        sections = modules[module_index].setdefault("sections", [])
        if insert_at is None or insert_at < 0 or insert_at > len(sections):
            sections.append(_new_section())
        else:
            sections.insert(insert_at, _new_section())
        _clear_outline_widget_cache()


def _delete_section(module_index: int, section_index: int):
    modules = ss.get("outline", {}).get("modules", [])
    if 0 <= module_index < len(modules):
        sections = modules[module_index].setdefault("sections", [])
        if 0 <= section_index < len(sections):
            sections.pop(section_index)
            if not sections:
                sections.append(_new_section())
            _clear_outline_widget_cache()


def _move_section(module_index: int, section_index: int, target_index: int):
    modules = ss.get("outline", {}).get("modules", [])
    if 0 <= module_index < len(modules):
        sections = modules[module_index].setdefault("sections", [])
        if 0 <= section_index < len(sections) and 0 <= target_index < len(sections):
            sections[section_index], sections[target_index] = sections[target_index], sections[section_index]
            _clear_outline_widget_cache()


def _add_unit(module_index: int, section_index: int, insert_at: int | None = None):
    modules = ss.get("outline", {}).get("modules", [])
    if 0 <= module_index < len(modules):
        sections = modules[module_index].setdefault("sections", [])
        if 0 <= section_index < len(sections):
            units = sections[section_index].setdefault("units", [])
            if insert_at is None or insert_at < 0 or insert_at > len(units):
                units.append(_new_unit())
            else:
                units.insert(insert_at, _new_unit())
            _clear_outline_widget_cache()


def _delete_unit(module_index: int, section_index: int, unit_index: int):
    modules = ss.get("outline", {}).get("modules", [])
    if 0 <= module_index < len(modules):
        sections = modules[module_index].setdefault("sections", [])
        if 0 <= section_index < len(sections):
            units = sections[section_index].setdefault("units", [])
            if 0 <= unit_index < len(units):
                units.pop(unit_index)
                if not units:
                    units.append(_new_unit())
                _clear_outline_widget_cache()


def _move_unit(module_index: int, section_index: int, unit_index: int, target_index: int):
    modules = ss.get("outline", {}).get("modules", [])
    if 0 <= module_index < len(modules):
        sections = modules[module_index].setdefault("sections", [])
        if 0 <= section_index < len(sections):
            units = sections[section_index].setdefault("units", [])
            if 0 <= unit_index < len(units) and 0 <= target_index < len(units):
                units[unit_index], units[target_index] = units[target_index], units[unit_index]
                _clear_outline_widget_cache()


@st.dialog("Edit Unit")
def _edit_unit_dialog(module_index: int, section_index: int, unit_index: int):
    modules = ss.get("outline", {}).get("modules", [])
    if not (0 <= module_index < len(modules)):
        st.warning("Module no longer exists.")
        return

    sections = modules[module_index].setdefault("sections", [])
    if not (0 <= section_index < len(sections)):
        st.warning("Section no longer exists.")
        return

    units = sections[section_index].setdefault("units", [])
    if not (0 <= unit_index < len(units)):
        st.warning("Unit no longer exists.")
        return

    unit = units[unit_index]
    unit.setdefault("unitTitle", "")
    unit.setdefault("unitLevelObjective", "")
    unit.setdefault("keyPoints", [])

    st.caption(f"Edit Unit {section_index + 1}.{unit_index + 1}")
    title = st.text_input("Unit title", value=unit.get("unitTitle", ""), key=f"unit_dialog_title_{module_index}_{section_index}_{unit_index}")
    objective = st.text_input(
        "Unit objective",
        value=unit.get("unitLevelObjective", ""),
        key=f"unit_dialog_objective_{module_index}_{section_index}_{unit_index}",
    )
    key_points_raw = st.text_area(
        "Key points (one per line)",
        value="\n".join(unit.get("keyPoints", [])),
        key=f"unit_dialog_points_{module_index}_{section_index}_{unit_index}",
        height=180,
    )

    action_cols = st.columns([1, 1])
    with action_cols[0]:
        if st.button("Cancel", use_container_width=True):
            st.rerun()
    with action_cols[1]:
        if st.button("Save changes", type="primary", use_container_width=True):
            unit["unitTitle"] = title
            unit["unitLevelObjective"] = objective
            unit["keyPoints"] = [line.strip() for line in key_points_raw.splitlines() if line.strip()]
            _clear_outline_widget_cache()
            st.rerun()

# Helper functions for editable outline rendering
def _get_outline_node(path_parts):
    """Return the container and final key/index for a dotted outline path."""
    if "outline" not in ss:
        raise KeyError("Outline is not available in session state.")

    if not path_parts:
        raise ValueError("Path cannot be empty.")

    node: Any = ss["outline"]
    for idx, part in enumerate(path_parts[:-1]):
        next_part = path_parts[idx + 1]
        if isinstance(node, list):
            index = int(part)
            node = node[index]
        elif isinstance(node, dict):
            if part not in node:
                node[part] = [] if next_part.isdigit() else {}
            node = node[part]
        else:
            raise KeyError(f"Unsupported path segment '{part}' for node type {type(node)}")

    return node, path_parts[-1]

def _normalize_outline_input(path: str, raw_value: str, existing: Any):
    if isinstance(existing, list) or path.endswith("keyPoints"):
        lines = [line.strip() for line in (raw_value or "").splitlines()]
        return [line for line in lines if line]
    return raw_value

def _update_outline_value(path: str, widget_key: str):
    if "outline" not in ss:
        return

    raw_value = ss.get(widget_key, "")
    path_parts = path.split(".")
    parent, final_key = _get_outline_node(path_parts)

    if isinstance(parent, list):
        index = int(final_key)
        existing = parent[index] if index < len(parent) else None
        normalized = _normalize_outline_input(path, raw_value, existing)
        if index < len(parent):
            parent[index] = normalized
        else:
            parent.append(normalized)
    else:
        existing = parent.get(final_key)
        normalized = _normalize_outline_input(path, raw_value, existing)
        parent[final_key] = normalized

    ss[widget_key] = "\n".join(normalized) if isinstance(normalized, list) else normalized

def outline_text_field(label: str, path: str, value: Any, *, area: bool = False, **widget_kwargs):
    widget_key = f"outline__{path.replace('.', '__')}"

    if isinstance(value, list):
        initial_value = "\n".join(value)
    else:
        initial_value = value or ""

    if widget_key not in ss:
        ss[widget_key] = initial_value

    field_kwargs = {
        "label": label,
        "key": widget_key,
        "on_change": _update_outline_value,
        "args": (path, widget_key),
        **widget_kwargs,
    }

    if area:
        st.text_area(**field_kwargs)
    else:
        st.text_input(**field_kwargs)



def display_editable_outline(outline: Dict[str, Any]):
    """Render the editable outline using text inputs backed by session state."""

    outline.setdefault("courseLevelObjectives", [])
    outline.setdefault("modules", [])

    course_title = outline.get("courseTitle", "") or "Untitled course"
    st.header(f":blue[Course Title: {course_title}]", divider="blue")
    outline_text_field("Title", "courseTitle", outline.get("courseTitle", ""), label_visibility="collapsed")

    st.markdown("**Course-Level Objectives (one per line)**")
    outline_text_field("Objectives (one per line)", "courseLevelObjectives", 
                        "\n".join(outline.get("courseLevelObjectives", [])),
                        area=True, label_visibility="collapsed", height=150
                        )


    st.divider()

    if not outline["modules"]:
        _add_module()

    if st.button("➕ Add Module", key="add_module_button", type="primary"):
        _add_module()
        st.rerun()

    tab_labels = [f"Module {i + 1}" for i in range(len(outline["modules"]))]
    module_tabs = st.tabs(tab_labels)

    for module_index, module_tab in enumerate(module_tabs):
        module = outline["modules"][module_index]
        module.setdefault("sections", [])

        with module_tab:
            module_title = module.get("moduleTitle", "") or "Untitled module"
            module_header_cols = st.columns([8, 1], vertical_alignment="center")
            with module_header_cols[0]:
                st.subheader(f":green[Module {module_index + 1}: {module_title}]", divider="green")
            with module_header_cols[1]:
                with st.popover("⋮ Options", use_container_width=True):
                    if st.button("Move Left", key=f"move_module_left_{module_index}", use_container_width=True, disabled=module_index == 0):
                        _move_module(module_index, module_index - 1)
                        st.rerun()
                    if st.button("Move Right", key=f"move_module_right_{module_index}", use_container_width=True, disabled=module_index == len(outline["modules"]) - 1):
                        _move_module(module_index, module_index + 1)
                        st.rerun()
                    if st.button("Delete Module", key=f"delete_module_{module_index}", use_container_width=True):
                        _delete_module(module_index)
                        st.rerun()

            outline_text_field("Module title", f"modules.{module_index}.moduleTitle", module.get("moduleTitle", ""))
            outline_text_field("Module overview", f"modules.{module_index}.overview", module.get("overview", ""), area=True)

            for section_index, section in enumerate(module["sections"]):
                section.setdefault("sectionLevelObjectives", [])
                section.setdefault("units", [])

                with st.container(border=True):
                    section_header_cols = st.columns([8, 1], vertical_alignment="center")
                    with section_header_cols[0]:
                        st.markdown(f"#### :orange[Section {module_index + 1}.{section_index + 1}: {section.get('sectionTitle', 'Untitled section') or 'Untitled section'}]")
                    with section_header_cols[1]:
                        with st.popover("⋮ Options", use_container_width=True):
                            if st.button("Move Up", key=f"move_section_up_{module_index}_{section_index}", use_container_width=True, disabled=section_index == 0):
                                _move_section(module_index, section_index, section_index - 1)
                                st.rerun()
                            if st.button("Move Down", key=f"move_section_down_{module_index}_{section_index}", use_container_width=True, disabled=section_index == len(module["sections"]) - 1):
                                _move_section(module_index, section_index, section_index + 1)
                                st.rerun()
                            if st.button("Delete Section", key=f"delete_section_{module_index}_{section_index}", use_container_width=True):
                                _delete_section(module_index, section_index)
                                st.rerun()

                    outline_text_field("Section title", f"modules.{module_index}.sections.{section_index}.sectionTitle", section.get("sectionTitle", ""))
                    outline_text_field(
                        "Section objectives (one per line)",
                        f"modules.{module_index}.sections.{section_index}.sectionLevelObjectives",
                        "\n".join(section.get("sectionLevelObjectives", [])),
                        area=True,
                    )

                    st.markdown("**Units**")
                    for unit_index, unit in enumerate(section["units"]):
                        unit_name = unit.get("unitTitle", "") or "Untitled unit"
                        unit_cols = st.columns([8, 1, 1], vertical_alignment="center")
                        with unit_cols[0]:
                            st.markdown(f"📄 Unit {module_index + 1}.{section_index + 1}.{unit_index + 1}: {unit_name}")
                        with unit_cols[1]:
                            if st.button("✏️ Edit", key=f"edit_unit_{module_index}_{section_index}_{unit_index}", use_container_width=True):
                                _edit_unit_dialog(module_index, section_index, unit_index)
                        with unit_cols[2]:
                            with st.popover("⋮", use_container_width=True):
                                if st.button("Move Up", key=f"move_unit_up_{module_index}_{section_index}_{unit_index}", use_container_width=True, disabled=unit_index == 0):
                                    _move_unit(module_index, section_index, unit_index, unit_index - 1)
                                    st.rerun()
                                if st.button("Move Down", key=f"move_unit_down_{module_index}_{section_index}_{unit_index}", use_container_width=True, disabled=unit_index == len(section["units"]) - 1):
                                    _move_unit(module_index, section_index, unit_index, unit_index + 1)
                                    st.rerun()
                                if st.button("Delete", key=f"delete_unit_{module_index}_{section_index}_{unit_index}", use_container_width=True):
                                    _delete_unit(module_index, section_index, unit_index)
                                    st.rerun()

                    if st.button("➕ Add Unit", key=f"add_unit_{module_index}_{section_index}"):
                        _add_unit(module_index, section_index)
                        st.rerun()

            if st.button("➕ Add Section", key=f"add_section_{module_index}", use_container_width=True):
                _add_section(module_index)
                st.rerun()


def display_static_outline(outline: Dict[str, Any]):
        """
        Parses the JSON outline and displays it in a user-friendly format.
        LLM output was already converted to Python dict in generate_outline().
        """
        st.header(f":blue[Title: {outline.get('courseTitle', 'N/A')}]", divider="blue")

        st.markdown("**Course-Level Objectives**")
        for obj in outline.get("courseLevelObjectives", []):
            st.markdown(f"- {obj}")

        st.markdown("---")

        for i, module in enumerate(outline.get("modules", [])):
            st.subheader(f":green[Module {i+1}: {module.get('moduleTitle', 'N/A')}]", divider="green")        
            st.markdown(f"**Overview:** {module.get('overview', 'N/A')}")
            
            for j, section in enumerate(module.get("sections", [])):
                st.markdown(f"#### :orange[Section {j+1}: {section.get('sectionTitle', 'N/A')}]")
                
                st.markdown("**Section Objectives:**")
                for s_obj in section.get("sectionLevelObjectives", []):
                    st.markdown(f"{s_obj}")

                for k, unit in enumerate(section.get("units", [])):
                    with st.expander(f"**Unit {j+1}.{k+1}: {unit.get('unitTitle', 'N/A')}**", expanded=False):
                        st.markdown(f"**Objective:** {unit.get('unitLevelObjective', 'N/A')}")
                        st.markdown("**Key Points:**")
                        for point in unit.get("keyPoints", []):
                            st.markdown(f"  - {point}")
