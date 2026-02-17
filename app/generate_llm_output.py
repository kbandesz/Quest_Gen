# Generate AI responses (including mocks)
import os
#import msal
import streamlit as st
from openai import OpenAI
from typing import Dict, Any
#import json

from . import prompts
from .parse_llm_output import parse_json_strict, validate_alignment_payload, validate_questions_payload
from . import constants as const

# Alias for convenience
ss = st.session_state

DEFAULT_MODEL = "gpt-4.1-nano"


def _is_mock_mode() -> bool:
    """Check if mock mode is enabled from session state."""
    return bool(ss.get("MOCK_MODE", True))


def _get_model() -> str:
    """Get the current OpenAI model from session state."""
    return ss.get("OPENAI_MODEL", DEFAULT_MODEL)


####### MSAL authentication (interactive) ########
# def _acquire_access_token_interactive() -> str:
#     """Acquire an access token interactively using MSAL."""

#     # Read config from environment variables
#     CLIENT_ID = os.getenv("CLIENT_ID")
#     TENANT_ID = os.getenv("TENANT_ID")
#     AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
#     SCOPE = [".default"]

#     app = msal.PublicClientApplication(client_id=CLIENT_ID, authority=AUTHORITY)
#     result = app.acquire_token_interactive(scopes=SCOPE)
#     if not result or "access_token" not in result:
#         print("Failed to acquire access token:")
#         print(json.dumps(result, indent=2))
#         raise RuntimeError("Authentication failed")
#     return result["access_token"]

 
def _get_client() -> OpenAI:
    """Get or create the OpenAI client, cached in session state."""
    cli = ss.get("_openai_client")
    if cli is None:
        cli = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        ss["_openai_client"] = cli
    return cli

# def _get_client() -> OpenAI:
#     """Get or create the OpenAI client, cached in session state."""
#     cli = ss.get("_openai_client")
#     if cli is None:
#         access_token = _acquire_access_token_interactive()
#         cli = OpenAI(
#             api_key="DUMMY",  # OpenAI SDK requires a value; your gateway uses api-key header instead
#             base_url=os.getenv("BASE_URL"),
#             default_headers={
#                 "api-key": os.getenv("API_KEY"),
#                 "Authorization": f"Bearer {access_token}",
#             },
#         )
#         ss["_openai_client"] = cli
#     return cli


def _chat_json(system:str, user:str, max_tokens:int, temperature:float)->Dict[str,Any]:
    if _is_mock_mode():
        return {"mock":"on"}
    client = _get_client()
    try:
        resp = client.chat.completions.create( # type: ignore
            model=_get_model(),
            messages=[
                {"role":"system","content":system},
                {"role":"user","content":user},
            ],
            temperature=temperature,
            response_format={"type":"json_object"},
            max_completion_tokens=max_tokens,
        )
        return parse_json_strict(resp.choices[0].message.content) # type: ignore
    except Exception as e:
        raise Exception(f"API call failed: {e}")

   
def generate_outline(outline_guidance:str, source_material:str)->Dict[str,Any]:
    if _is_mock_mode():
        return const.generate_mock_outline()
    user_prompt=prompts.build_outline_user_prompt(outline_guidance, source_material)
    obj=_chat_json(prompts.OUTLINE_SYSTEM_PROMPT, user_prompt, max_tokens=3000, temperature=0.4)
    return obj


def check_alignment(lo_text:str, intended_level:str, module_text:str)->Dict[str,Any]:
    if _is_mock_mode():
        # Return a randomized mock scenario to exercise UI branches
        return const.generate_mock_alignment_result(lo_text, intended_level)
    user_prompt=prompts.build_align_user_prompt(lo_text, intended_level, module_text)
    obj=_chat_json(prompts.ALIGN_SYSTEM_PROMPT, user_prompt, max_tokens=800, temperature=0.2)
    return validate_alignment_payload(obj)


def generate_questions(final_lo_text:str, bloom_level:str, module_text:str, n_questions:int=1)->Dict[str,Any]:
    if _is_mock_mode():
        return const.generate_mock_questions(n_questions)
    user_prompt=prompts.build_questgen_user_prompt(bloom_level, final_lo_text, module_text, n_questions)
    obj=_chat_json(prompts.QUESTGEN_SYSTEM_PROMPT, user_prompt, max_tokens=1800, temperature=0.4)
    return validate_questions_payload(obj)
