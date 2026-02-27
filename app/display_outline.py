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

    st.header(":blue[Course Title]", divider="blue")
    outline_text_field("Title", "courseTitle", outline.get("courseTitle", ""), label_visibility="collapsed")

    st.markdown("**Course-Level Objectives (one per line)**")
    outline_text_field("Objectives (one per line)", "courseLevelObjectives", 
                        "\n".join(outline.get("courseLevelObjectives", [])),
                        area=True, label_visibility="collapsed", height=150
                        )


    st.divider()


    # if st.button("➕ Add module", use_container_width=True):
    #     _add_module()
    #     st.rerun()

    for module_index, module in enumerate(outline["modules"]):
        module.setdefault("sections", [])
        module_header_cols = st.columns([6, 1, 1, 1], vertical_alignment="center")
        with module_header_cols[0]:
            st.subheader(f":green[Module {module_index + 1}]", divider="green")
        with module_header_cols[1]:
            if st.button(
                "⬆️",
                key=f"add_module_above_{module_index}",
                help="Add module above",
            ):
                _add_module(insert_at=module_index)
                st.rerun()
        with module_header_cols[2]:
            if st.button(
                "⬇️",
                key=f"add_module_below_{module_index}",
                help="Add module below",
            ):
                _add_module(insert_at=module_index + 1)
                st.rerun()
        with module_header_cols[3]:
            if st.button("🗑️", key=f"delete_module_{module_index}", help="Delete module"):
                _delete_module(module_index)
                st.rerun()

        outline_text_field(
            "Module title",
            f"modules.{module_index}.moduleTitle",
            module.get("moduleTitle", ""),
        )
        outline_text_field(
            "Module overview",
            f"modules.{module_index}.overview",
            module.get("overview", ""),
            area=True,
        )

        # if not module["sections"]:
        #     if st.button("➕ Add section", key=f"add_section_empty_{module_index}"):
        #         _add_section(module_index)
        #         st.rerun()

        for section_index, section in enumerate(module["sections"]):
            section.setdefault("sectionLevelObjectives", [])
            section.setdefault("units", [])

            section_header_cols = st.columns([6, 1, 1, 1], vertical_alignment="center")
            with section_header_cols[0]:
                st.markdown(f"#### :orange[Section {section_index + 1}]")
            with section_header_cols[1]:
                if st.button(
                    "➕⬆️",
                    key=f"add_section_above_{module_index}_{section_index}",
                    help="Add section above",
                ):
                    _add_section(module_index, insert_at=section_index)
                    st.rerun()
            with section_header_cols[2]:
                if st.button(
                    "➕⬇️",
                    key=f"add_section_below_{module_index}_{section_index}",
                    help="Add section below",
                ):
                    _add_section(module_index, insert_at=section_index + 1)
                    st.rerun()
            with section_header_cols[3]:
                if st.button(
                    "🗑️",
                    key=f"delete_section_{module_index}_{section_index}",
                    help="Delete section",
                ):
                    _delete_section(module_index, section_index)
                    st.rerun()

            outline_text_field(
                "Section title",
                f"modules.{module_index}.sections.{section_index}.sectionTitle",
                section.get("sectionTitle", ""),
            )

            outline_text_field(
                "Section objectives (one per line)",
                f"modules.{module_index}.sections.{section_index}.sectionLevelObjectives",
                "\n".join(section.get("sectionLevelObjectives", [])),
                area=True,
            )

            # if st.button("➕ Add unit", key=f"add_unit_{module_index}_{section_index}"):
            #     _add_unit(module_index, section_index)
            #     st.rerun()

            for unit_index, unit in enumerate(section["units"]):
                unit.setdefault("unitLevelObjective", "")
                unit.setdefault("keyPoints", [])

                with st.expander(
                    f"Unit {section_index + 1}.{unit_index + 1}: {unit.get('unitTitle', 'Untitled unit') or 'Untitled unit'}",
                    expanded=False,
                ):
                    unit_action_cols = st.columns([8, 1, 1, 1], vertical_alignment="center")
                    with unit_action_cols[1]:
                        if st.button(
                            "⬆️",
                            key=f"add_unit_above_{module_index}_{section_index}_{unit_index}",
                            help="Add unit above",
                        ):
                            _add_unit(module_index, section_index, insert_at=unit_index)
                            st.rerun()
                    with unit_action_cols[2]:
                        if st.button(
                            "⬇️",
                            key=f"add_unit_below_{module_index}_{section_index}_{unit_index}",
                            help="Add unit below",
                        ):
                            _add_unit(module_index, section_index, insert_at=unit_index + 1)
                            st.rerun()
                    with unit_action_cols[3]:
                        if st.button(
                            "🗑️",
                            key=f"delete_unit_{module_index}_{section_index}_{unit_index}",
                            help="Delete unit",
                        ):
                            _delete_unit(module_index, section_index, unit_index)
                            st.rerun()

                    outline_text_field(
                        "Unit title",
                        f"modules.{module_index}.sections.{section_index}.units.{unit_index}.unitTitle",
                        unit.get("unitTitle", ""),
                    )

                    outline_text_field(
                        "Unit objective",
                        f"modules.{module_index}.sections.{section_index}.units.{unit_index}.unitLevelObjective",
                        unit.get("unitLevelObjective", "")
                    )

                    outline_text_field(
                        "Key points (one per line)",
                        f"modules.{module_index}.sections.{section_index}.units.{unit_index}.keyPoints",
                        "\n".join(unit.get("keyPoints", [])),
                        area=True,
                    )

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
