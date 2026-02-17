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

DEFAULT_MODEL = "gpt-5-nano"

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


def _safe_attr(obj: Any, attr: str, default: Any = None) -> Any:
    """Safely fetch a nested attribute from SDK objects."""
    try:
        return getattr(obj, attr, default)
    except Exception:
        return default


def _collect_response_debug(resp: Any) -> Dict[str, Any]:
    """Collect debug metadata from a responses.create payload."""
    error = _safe_attr(resp, "error")
    return {
        "response_id": _safe_attr(resp, "id"),
        "model": _safe_attr(resp, "model"),
        "status": _safe_attr(resp, "status"),
        "incomplete_details": _safe_attr(resp, "incomplete_details"),
        "error": {
            "code": _safe_attr(error, "code") if error else None,
            "message": _safe_attr(error, "message") if error else None,
            "type": _safe_attr(error, "type") if error else None,
        }
        if error
        else None,
        "usage": _safe_attr(resp, "usage"),
    }


def _collect_exception_debug(exc: Exception) -> Dict[str, Any]:
    """Collect structured details from OpenAI/HTTP exceptions when available."""
    debug: Dict[str, Any] = {
        "exception_type": type(exc).__name__,
        "message": str(exc),
    }

    status_code = _safe_attr(exc, "status_code")
    if status_code is not None:
        debug["status_code"] = status_code

    request_id = _safe_attr(exc, "request_id")
    if request_id:
        debug["request_id"] = request_id

    body = _safe_attr(exc, "body")
    if body:
        debug["body"] = body

    response = _safe_attr(exc, "response")
    if response is not None:
        response_text = _safe_attr(response, "text")
        if response_text:
            debug["response_text"] = response_text

    return debug


def _chat_json(system:str, user:str, max_tokens:int, temperature:float)->Dict[str,Any]:
    if _is_mock_mode():
        return {"mock":"on"}
    client = _get_client()
    model = _get_model()
    try:
        resp = client.responses.create( # type: ignore
            model=model,
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
        try:
            return parse_json_strict(_extract_response_text(resp))
        except Exception as parse_or_text_error:
            response_debug = _collect_response_debug(resp)
            raise RuntimeError(
                "API call succeeded but response parsing failed. "
                f"model={model} debug={response_debug}"
            ) from parse_or_text_error
    except Exception as e:
        exception_debug = _collect_exception_debug(e)
        raise RuntimeError(
            f"API call failed. model={model} debug={exception_debug}"
        ) from e

   
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
