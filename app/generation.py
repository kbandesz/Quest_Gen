# Generate AI responses (including mocks)
import os
from dotenv import load_dotenv
from openai import OpenAI
from typing import Dict, Any
from .prompts import ALIGN_SYSTEM_PROMPT, QUESTGEN_SYSTEM_PROMPT, build_align_user_prompt, build_questgen_user_prompt
from .utils import parse_json_strict, validate_alignment_payload, validate_questions_payload
from . import constants as const

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

def check_alignment(lo_text:str, intended_level:str, module_text:str)->Dict[str,Any]:
    if MOCK_MODE:
        # Return a randomized mock scenario to exercise UI branches
        return const.generate_mock_alignment_result(lo_text, intended_level)
    user_prompt=build_align_user_prompt(intended_level, lo_text, module_text)
    obj=_chat_json(ALIGN_SYSTEM_PROMPT, user_prompt, max_tokens=800, temperature=0.2)
    return validate_alignment_payload(obj)


def generate_questions(final_lo_text:str, bloom_level:str, module_text:str, n_questions:int=1)->Dict[str,Any]:
    if MOCK_MODE:
        return const.generate_mock_questions(n_questions)
    user_prompt=build_questgen_user_prompt(bloom_level, final_lo_text, module_text, n_questions)
    obj=_chat_json(QUESTGEN_SYSTEM_PROMPT, user_prompt, max_tokens=1800, temperature=0.4)
    return validate_questions_payload(obj)
