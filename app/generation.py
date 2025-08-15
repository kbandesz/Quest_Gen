
import os
from typing import Dict, Any
from .prompts import SYSTEM_PROMPT, build_alignment_prompt, build_generation_prompt
from .utils import parse_json_strict, validate_alignment_payload, validate_questions_payload

MOCK_MODE = os.getenv("MOCK_MODE","false").lower() in {"1","true","yes"}

if not MOCK_MODE:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    OPENAI_MODEL = os.getenv("OPENAI_MODEL","gpt-4o-mini")

def _chat_json(prompt:str, max_tokens:int, temperature:float)->Dict[str,Any]:
    if MOCK_MODE:
        return {"mock":"on"}
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role":"system","content":SYSTEM_PROMPT},
            {"role":"user","content":prompt},
        ],
        temperature=temperature,
        response_format={"type":"json_object"},
        max_tokens=max_tokens,
    )
    return parse_json_strict(resp.choices[0].message.content)

def check_alignment(intended_level:str, lo_text:str, module_text:str)->Dict[str,Any]:
    if MOCK_MODE:
        return {
            "label":"consistent",
            "reasons":["mock mode – not evaluated"],
            "flags":["none"],
            "suggested_lo":None
        }
    prompt=build_alignment_prompt(intended_level, lo_text, module_text)
    obj=_chat_json(prompt, max_tokens=800, temperature=0.2)
    return validate_alignment_payload(obj)

def _mock_questions(n:int=3)->Dict[str,Any]:
    qs=[]
    for i in range(n):
        qs.append({
            "type":"MCQ_4",
            "stem":f"Mock question {i+1}: What is 2 + 2?",
            "options":[
                {"id":"A","text":"3","distractor_rationale":"Off-by-one"},
                {"id":"B","text":"4","distractor_rationale":"Correct"},
                {"id":"C","text":"5","distractor_rationale":"Common error"},
                {"id":"D","text":"22","distractor_rationale":"concat digits"},
            ],
            "correct_option_id":"B",
            "cognitive_rationale":"Remember-level math fact",
            "contentReference":""
        })
    return {"questions":qs}

def generate_questions(final_lo_text:str, bloom_level:str, module_text:str, n_questions:int=3)->Dict[str,Any]:
    n=max(2,min(3,int(n_questions)))
    if MOCK_MODE:
        return _mock_questions(n)
    prompt=build_generation_prompt(bloom_level, final_lo_text, module_text, n)
    obj=_chat_json(prompt, max_tokens=1800, temperature=0.4)
    return validate_questions_payload(obj)
