
from io import BytesIO
from typing import List, Dict
from docx import Document
from docx.shared import Pt

def build_docx(los:List[dict], questions_by_lo:Dict[str,list])->bytes:
    doc=Document()
    font=doc.styles['Normal'].font
    font.name='Calibri'; font.size=Pt(11)
    doc.add_heading("Assessment Questions (MVP Export)", level=1)
    for lo in los:
        lo_id=lo["id"]
        final=lo.get("final_text") or lo["text"]
        level=lo["intended_level"]
        doc.add_heading(f"Learning Objective: {final}", level=2)
        doc.add_paragraph(f"Bloom level: {level}", style="Normal").italic=True
        qs=questions_by_lo.get(lo_id,[])
        for idx,q in enumerate(qs,1):
            doc.add_paragraph(f"{idx}. {q['stem']}")
            correct=q.get("correct_option_id")
            for opt in q["options"]:
                marker="*" if opt["id"]==correct else ""
                doc.add_paragraph(f"   ({opt['id']}) {opt['text']} {marker}")
            doc.add_paragraph(f"Answer: {correct}")
            if q.get("cognitive_rationale"):
                doc.add_paragraph(f"Rationale: {q['cognitive_rationale']}")
    bio=BytesIO()
    doc.save(bio)
    return bio.getvalue()
