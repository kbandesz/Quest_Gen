# Export LOs and Questions to a .docx file
from io import BytesIO
from typing import List, Dict, Optional
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_COLOR_INDEX

def build_questions_docx(los:List[dict], questions_by_lo:Dict[str,list], include:Optional[Dict[str,bool]]=None)->bytes:
    doc = Document()
    # Force Title and Heading styles to use Arial as well
    for style_name in ["Title", "Heading 1", "Heading 2", "Heading 3"]:
        style = doc.styles[style_name].font
        style.name = "Arial"

    # Normal font is Arial 11pt
    font = doc.styles['Normal'].font
    font.name = "Arial"
    font.size = Pt(11)

    # Title line
    doc.add_paragraph("Assessment Questions", style="Title")

    # Default include options (all True)
    if include is None:
        include = {
            "los": True,
            "bloom": True,
            "answer": True,
            "feedback": True,
            "content": True,
            "rationale": True,
        }

    # Go over Learning Objectives
    for lo in los:
        lo_id = lo.get("id")
        final = lo.get("final_text")
        level = lo.get("intended_level")

        # LO heading
        if include.get("los", True):
            doc.add_heading(f"Learning Objective: {final}", level=2)

        # Bloom line is italic
        if include.get("bloom", True):
            para = doc.add_paragraph()
            run = para.add_run(f"Bloom level: {level}")
            run.italic = True

        # Go over questions
        qs = questions_by_lo.get(lo_id, [])
        for idx, q in enumerate(qs, 1):
            # Question stem
            para = doc.add_paragraph()
            run = para.add_run(f"{idx}. {q.get('stem','')}")
            run.bold = True
            run.font.color.rgb = RGBColor(0x5F, 0x49, 0x7A)  # purple-like color

            # Options with yellow highlight for the correct one
            correct = q.get("correct_option_id")
            for opt in q.get("options", []):
                para = doc.add_paragraph()
                run = para.add_run(f"   ({opt.get('id')}) {opt.get('text','')}")
                if opt.get("id") == correct and include.get("answer", True):
                    try:
                        run.font.highlight_color = WD_COLOR_INDEX.YELLOW
                    except Exception:
                        # Some python-docx versions may not support highlight on run.font
                        pass

            # Answer line
            if include.get("answer", True):
                para = doc.add_paragraph()
                run = para.add_run("Answer: ")
                run.bold = True
                para.add_run(str(correct))

            # Feedback block
            if include.get("feedback", True):
                para = doc.add_paragraph()
                run = para.add_run("Feedback:")
                run.bold = True
                for opt in q.get("options", []):
                    doc.add_paragraph(f"   ({opt.get('id')}) {opt.get('option_rationale','')}")

            # Content reference
            if include.get("content", True):
                para = doc.add_paragraph()
                run = para.add_run("Content reference: ")
                run.bold = True
                para.add_run(q.get('contentReference',''))

            # Cognitive rationale
            if include.get("rationale", True):
                para = doc.add_paragraph()
                run = para.add_run("Rationale for Bloom level: ")
                run.bold = True
                para.add_run(q.get('cognitive_rationale',''))

    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

