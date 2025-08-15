
import json
from typing import Any, Dict

def parse_json_strict(s:str)->Dict[str,Any]:
    try:
        return json.loads(s)
    except Exception as e:
        raise ValueError(f"Model returned invalid JSON: {e}")

def validate_alignment_payload(obj:Dict[str,Any])->Dict[str,Any]:
    if obj.get("label") not in {"consistent","ambiguous","inconsistent"}:
        raise ValueError("Bad label")
    if not isinstance(obj.get("reasons"), list):
        raise ValueError("Missing reasons list")
    if "suggested_lo" not in obj:
        raise ValueError("suggested_lo missing")
    return obj

def validate_questions_payload(obj:Dict[str,Any])->Dict[str,Any]:
    qs=obj.get("questions")
    if not isinstance(qs,list) or not qs:
        raise ValueError("questions missing")
    for q in qs:
        if q.get("type")!="MCQ_4": raise ValueError("type must be MCQ_4")
        opts=q.get("options",[])
        if len(opts)!=4: raise ValueError("need 4 options")
        ids=sorted(o.get("id") for o in opts)
        if ids!=["A","B","C","D"]:
            raise ValueError("option ids must be A-D")
        if q.get("correct_option_id") not in {"A","B","C","D"}:
            raise ValueError("correct id bad")
    return obj
