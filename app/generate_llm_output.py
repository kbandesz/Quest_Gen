# Generate AI responses (including mocks)
import os
import streamlit as st
from openai import OpenAI
from typing import Dict, Any

from . import prompts
from .parse_llm_output import parse_json_strict, validate_alignment_payload, validate_questions_payload
from . import constants as const

# Alias for convenience
ss = st.session_state

DEFAULT_MODEL = "gpt-5-nano"

def _is_mock_mode() -> bool:
    """Check if mock mode is enabled from session state."""
    return bool(ss.get("MOCK_MODE", True))


def _get_model() -> str:
    """Get the current OpenAI model from session state."""
    return ss.get("OPENAI_MODEL", DEFAULT_MODEL)


def _get_client() -> OpenAI:
    """Get or create the OpenAI client, cached in session state."""
    cli = ss.get("_openai_client")
    if cli is None:
        cli = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        ss["_openai_client"] = cli
    return cli


def _extract_response_text(resp: Any) -> str:
    """Extract plain text from a Responses API result."""
    text = getattr(resp, "output_text", "")
    if text:
        return text

    output = getattr(resp, "output", []) or []
    for item in output:
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", []) or []:
            chunk_type = getattr(content, "type", None)
            if chunk_type in {"output_text", "text"}:
                value = getattr(content, "text", None)
                if value:
                    return value
    raise ValueError("No response text returned by model.")


def _chat_json(system:str, user:str, max_tokens:int, temperature:float)->Dict[str,Any]:
    if _is_mock_mode():
        return {"mock":"on"}
    client = _get_client()
    try:
        resp = client.responses.create( # type: ignore
            model=_get_model(),
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user}],
                },
            ],
            temperature=temperature,
            text={"format": {"type": "json_object"}},
            max_output_tokens=max_tokens,
        )
        return parse_json_strict(_extract_response_text(resp))
    except Exception as e:
        raise Exception(f"API call failed: {e}")

   
def generate_outline(outline_guidance:str, source_material:str)->Dict[str,Any]:
    if _is_mock_mode():
        return const.generate_mock_outline()
    user_prompt=prompts.build_outline_user_prompt(outline_guidance, source_material)
    obj=_chat_json(prompts.OUTLINE_SYSTEM_PROMPT, user_prompt, max_tokens=6000, temperature=0.4)
    return obj


def check_alignment(lo_text:str, intended_level:str, module_text:str)->Dict[str,Any]:
    if _is_mock_mode():
        # Return a randomized mock scenario to exercise UI branches
        return const.generate_mock_alignment_result(lo_text, intended_level)
    user_prompt=prompts.build_align_user_prompt(lo_text, intended_level, module_text)
    obj=_chat_json(prompts.ALIGN_SYSTEM_PROMPT, user_prompt, max_tokens=2000, temperature=0.2)
    return validate_alignment_payload(obj)


def generate_questions(final_lo_text:str, bloom_level:str, module_text:str, n_questions:int=1)->Dict[str,Any]:
    if _is_mock_mode():
        return const.generate_mock_questions(n_questions)
    user_prompt=prompts.build_questgen_user_prompt(bloom_level, final_lo_text, module_text, n_questions)
    obj=_chat_json(prompts.QUESTGEN_SYSTEM_PROMPT, user_prompt, max_tokens=4000, temperature=0.4)
    return validate_questions_payload(obj)
