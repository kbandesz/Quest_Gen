
import os
from dotenv import load_dotenv
from openai import OpenAI
from typing import Dict, Any
import random
from .prompts import SYSTEM_PROMPT, build_alignment_prompt, build_generation_prompt
from .utils import parse_json_strict, validate_alignment_payload, validate_questions_payload

# Load OPENAI_API_KEY from .env
load_dotenv() 

MOCK_MODE = True
OPENAI_MODEL = "gpt-4.1-nano"
client = None  # type: ignore

# To override mock flag and model at runtime.
def set_runtime_config(mock_mode: bool, model: str) -> None:
    """Allow the app to override mock flag and model at runtime."""
    global MOCK_MODE, OPENAI_MODEL, client
    MOCK_MODE = bool(mock_mode)
    OPENAI_MODEL = model or OPENAI_MODEL
    if not MOCK_MODE:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    else:
        # entering mock mode: drop the client reference
        client = None

# Mock alignment scenarios (used only when MOCK_MODE is enabled)
_MOCK_ALIGNMENT_SCENARIOS = [
    # 1) Consistent — no rewrite needed
    lambda lo_text, intended_level: {
        "label": "consistent",
        "reasons": [f"Primary verb and cognitive demand match '{intended_level}'.", "LO is measurable and specific."],
        "suggested_lo": None,
    },
    # 2) Ambiguous — suggest sharper rewrite
    lambda lo_text, intended_level: {
        "label": "ambiguous",
        "reasons": ["LO mixes multiple actions or vague phrasing (e.g., 'understand', 'know')."],
        "suggested_lo": f"Revise to a single measurable verb at {intended_level}: Replace vague phrasing in \"{lo_text}\" with a concrete outcome (e.g., 'analyze X by comparing Y and Z using criteria A').",
    },
    # 3) Inconsistent — suggest rewrite aligned to intended level
    lambda lo_text, intended_level: {
        "label": "inconsistent",
        "reasons": [f"Stated verb implies a different Bloom level than '{intended_level}'.", "Assessment would not evidence the intended level."],
        "suggested_lo": f"Rewrite for {intended_level}: Start with a strong {intended_level.lower()}-level verb and specify observable criteria relevant to the module.",
    },
    # 4) Ambiguous due to content coverage — needs context-constrained rewrite
    lambda lo_text, intended_level: {
        "label": "ambiguous",
        "reasons": ["Module content only partially covers the constructs referenced in the LO."],
        "suggested_lo": f"Constrain scope to topics covered in the module and keep the {intended_level.lower()} cognitive demand.",
    },
]

def _mock_alignment_choice(lo_text: str, intended_level: str) -> Dict[str, Any]:
    """Pick one mock alignment outcome at random."""
    scenario_fn = random.choice(_MOCK_ALIGNMENT_SCENARIOS)
    return scenario_fn(lo_text, intended_level)

def _chat_json(prompt:str, max_tokens:int, temperature:float)->Dict[str,Any]:
    if MOCK_MODE:
        return {"mock":"on"}
    if client is None:
        set_runtime_config(MOCK_MODE, OPENAI_MODEL)
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role":"system","content":SYSTEM_PROMPT},
                {"role":"user","content":prompt},
            ],
            temperature=temperature,
            response_format={"type":"json_object"},
            max_completion_tokens=max_tokens,
        )
        return parse_json_strict(resp.choices[0].message.content)
    except Exception as e:
        raise Exception(f"API call failed: {e}")

def check_alignment(lo_text:str, intended_level:str, module_text:str)->Dict[str,Any]:
    if MOCK_MODE:
        # Return a randomized mock scenario to exercise UI branches
        return _mock_alignment_choice(lo_text, intended_level)
    prompt=build_alignment_prompt(intended_level, lo_text, module_text)
    obj=_chat_json(prompt, max_tokens=800, temperature=0.2)
    return validate_alignment_payload(obj)

def _mock_questions(n:int=2)->Dict[str,Any]:
    qs=[]
    for i in range(n):
        qs.append({
            "type":"MCQ_4",
            "stem":f"Mock question {i+1}: What is 2 + 2?",
            "options":[
                {"id":"A","text":"3","option_rationale":"Off-by-one"},
                {"id":"B","text":"4","option_rationale":"Correct"},
                {"id":"C","text":"5","option_rationale":"Common error"},
                {"id":"D","text":"22","option_rationale":"concat digits"},
            ],
            "correct_option_id":"B",
            "cognitive_rationale":"Remember-level math fact",
            "contentReference":""
        })
    return {"questions":qs}

def generate_questions(final_lo_text:str, bloom_level:str, module_text:str, n_questions:int=1)->Dict[str,Any]:
    n=min(2,int(n_questions))
    if MOCK_MODE:
        return _mock_questions(n)
    prompt=build_generation_prompt(bloom_level, final_lo_text, module_text, n)
    obj=_chat_json(prompt, max_tokens=1800, temperature=0.4)
    return validate_questions_payload(obj)
