import streamlit as st
from typing import Dict, Any

ss = st.session_state

# Helper functions for editable outline rendering
def _get_outline_node(path_parts):
    """Return the container and final key/index for a dotted outline path."""
    if "generated_outline" not in ss:
        raise KeyError("Outline is not available in session state.")

    if not path_parts:
        raise ValueError("Path cannot be empty.")

    node: Any = ss["generated_outline"]
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
    if "generated_outline" not in ss:
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

    st.header("Course Title")
    outline_text_field("Title", "courseTitle", outline.get("courseTitle", ""), label_visibility="collapsed")

    st.markdown("**Course-Level Objectives (one per line)**")
    outline_text_field("Objectives (one per line)", "courseLevelObjectives", 
                        "\n".join(outline.get("courseLevelObjectives", [])),
                        area=True, label_visibility="collapsed", height=150
                        )


    st.divider()

    for module_index, module in enumerate(outline["modules"]):
        module.setdefault("sections", [])
        st.subheader(f"Module {module_index + 1}")
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

        for section_index, section in enumerate(module["sections"]):
            section.setdefault("sectionLevelObjectives", [])
            section.setdefault("units", [])

            st.markdown(f"#### Section {section_index + 1}")
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

            for unit_index, unit in enumerate(section["units"]):
                unit.setdefault("unitLevelObjective", {})
                unit.setdefault("keyPoints", [])

                with st.expander(
                    f"Unit {section_index + 1}.{unit_index + 1}: {unit.get('unitTitle', 'Untitled unit') or 'Untitled unit'}",
                    expanded=False,
                ):
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
        st.header(f"Title: {outline.get('courseTitle', 'N/A')}")

        st.markdown("**Course-Level Objectives**")
        for obj in outline.get("courseLevelObjectives", []):
            st.markdown(f"- {obj}")

        st.markdown("---")

        for i, module in enumerate(outline.get("modules", [])):
            st.subheader(f"Module {i+1}: {module.get('moduleTitle', 'N/A')}")        
            st.markdown(f"**Overview:** {module.get('overview', 'N/A')}")
            
            for j, section in enumerate(module.get("sections", [])):
                st.markdown(f"#### Section {j+1}: {section.get('sectionTitle', 'N/A')}")
                
                for s_obj in section.get("sectionLevelObjectives", []):
                    st.markdown(f"_{s_obj}_")

                for k, unit in enumerate(section.get("units", [])):
                    with st.expander(f"**Unit {j+1}.{k+1}: {unit.get('unitTitle', 'N/A')}**", expanded=False):
                        #unit_obj = unit.get("unitLevelObjective", {})
                        st.markdown(f"_**Objective:** {unit.get("unitLevelObjective", 'N/A')}_")
                        st.markdown("**Key Points:**")
                        for point in unit.get("keyPoints", []):
                            st.markdown(f"  - {point}")
