# Generate AI responses (including mocks)
import os
from openai import OpenAI
from typing import Dict, Any

from . import prompts
from .parse_llm_output import parse_json_strict, validate_alignment_payload, validate_questions_payload
from . import constants as const


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


def _chat_json(system:str, user:str, max_tokens:int, temperature:float)->Dict[str,Any]:
    if MOCK_MODE:
        return {"mock":"on"}
    if client is None:
        set_runtime_config(MOCK_MODE, OPENAI_MODEL)
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role":"system","content":system},
                {"role":"user","content":user},
            ],
            temperature=temperature,
            response_format={"type":"json_object"},
            max_completion_tokens=max_tokens,
        )
        return parse_json_strict(resp.choices[0].message.content)
    except Exception as e:
        raise Exception(f"API call failed: {e}")

def _clean_objectives(d):
    # Remove Bloom levels from LLM response (may want to use later)
    if isinstance(d, dict):
        # If this is a unitLevelObjective, replace dict with its "objectiveText"
        if set(d.keys()) == {"bloomsLevel", "objectiveText"} or set(d.keys()) == {"objectiveText"}:
            return d.get("objectiveText")

        # Recurse into dictionary values
        for k, v in list(d.items()):
            if k == "unitLevelObjective":
                d[k] = _clean_objectives(v)  # convert to string
            elif k == "sectionLevelObjectives" and isinstance(v, list):
                d[k] = [_clean_objectives(obj) for obj in v if isinstance(obj, dict)]
            else:
                d[k] = _clean_objectives(v)
        return d

    elif isinstance(d, list):
        return [_clean_objectives(item) for item in d]

    return d
    
def generate_outline(outline_guidance:str, source_material:str)->Dict[str,Any]:
    if MOCK_MODE:
        return _clean_objectives(const.generate_mock_llm_response())
    user_prompt=prompts.build_outline_user_prompt(outline_guidance, source_material)
    obj=_chat_json(prompts.OUTLINE_SYSTEM_PROMPT, user_prompt, max_tokens=1800, temperature=0.4)
    return _clean_objectives(obj)


def check_alignment(lo_text:str, intended_level:str, module_text:str)->Dict[str,Any]:
    if MOCK_MODE:
        # Return a randomized mock scenario to exercise UI branches
        return const.generate_mock_alignment_result(lo_text, intended_level)
    user_prompt=prompts.build_align_user_prompt(lo_text, intended_level, module_text)
    obj=_chat_json(prompts.ALIGN_SYSTEM_PROMPT, user_prompt, max_tokens=800, temperature=0.2)
    return validate_alignment_payload(obj)


def generate_questions(final_lo_text:str, bloom_level:str, module_text:str, n_questions:int=1)->Dict[str,Any]:
    if MOCK_MODE:
        return const.generate_mock_questions(n_questions)
    user_prompt=prompts.build_questgen_user_prompt(bloom_level, final_lo_text, module_text, n_questions)
    obj=_chat_json(prompts.QUESTGEN_SYSTEM_PROMPT, user_prompt, max_tokens=1800, temperature=0.4)
    return validate_questions_payload(obj)
