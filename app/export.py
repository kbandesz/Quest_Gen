
from io import BytesIO
from typing import List, Dict
from docx import Document
from docx.shared import Pt

def build_docx(los:List[dict], questions_by_lo:Dict[str,list])->bytes:
    doc=Document()
    font=doc.styles['Normal'].font
    font.name="Calibri"
    font.size=Pt(11)

    doc.add_heading("Assessment Questions (MVP Export)", level=1)

    for lo in los:
        lo_id=lo["id"]
        final=lo.get("final_text")
        level=lo["intended_level"]

        doc.add_heading(f"Learning Objective: {final}", level=2)

        para = doc.add_paragraph()
        run = para.add_run(f"Bloom level: {level}")
        run.italic = True
        
        qs=questions_by_lo.get(lo_id,[])
        for idx,q in enumerate(qs,1):
            doc.add_paragraph(f"{idx}. {q['stem']}")

            correct=q.get("correct_option_id")
            for opt in q["options"]:
                para = doc.add_paragraph()
                run = para.add_run(f"   ({opt['id']}) {opt['text']}")
                if opt["id"]==correct:
                    run.bold = True
            
            doc.add_paragraph(f"Answer: {correct}")
            doc.add_paragraph(f"Feedback:")
            for opt in q["options"]:
                doc.add_paragraph(f"   ({opt['id']}) {opt['option_rationale']}")
            doc.add_paragraph(f"Content reference: {q['contentReference']}")
            doc.add_paragraph(f"Rationale for Bloom level: {q['cognitive_rationale']}")
    
    bio=BytesIO()
    doc.save(bio)
    return bio.getvalue()
