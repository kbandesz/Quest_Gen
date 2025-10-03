### Quick orientation

This repository contains a Streamlit app (entry: `mainapp.py`) called ALTO-Design that helps instructional designers create learning objectives and AI-generated multiple-choice questions. The app is intentionally split between a Streamlit UI and a small `app/` library with clear responsibilities:

- `mainapp.py` — Streamlit UI and the single-page multi-step router (steps 1..5). Widgets drive state via `st.session_state`.
- `app/generate_llm_output.py` — LLM interaction layer. Honors a runtime `MOCK_MODE` and exposes `set_runtime_config`, `generate_outline`, `check_alignment`, `generate_questions`.
- `app/prompts.py` — All system & user prompts (careful: production prompts are strict JSON-contracts). Changes here must preserve the exact JSON schema expected by `app/parse_llm_output.py`.
- `app/parse_input_files.py` — File parsing & token estimation for uploaded PDFs, DOCX, PPTX, and TXT.
- `app/parse_llm_output.py` — Strict JSON validators used to fail fast on malformed LLM responses.
- `app/export_docx.py` — Builds the downloaded Word file from LO + question data.
- `app/save_load_progress.py` — Snapshotting and restoring durable session state; used by the sidebar save/load UI.

### Big picture / architecture notes

- UI (mainapp.py) holds all UI state in `st.session_state`. Durable keys are defined in `app/save_load_progress.py::DOMAIN_STATE_KEYS`. Widget-only state (temporary keys used to bind to inputs) intentionally lives only in session state during a run.
- LLM calls are centralized in `app/generate_llm_output.py`. The app toggles between `MOCK_MODE` (no network) and real OpenAI client via `set_runtime_config`. When `MOCK_MODE` is True the app uses canned responses in `app/constants.py`.
- Prompt contracts are strict: `app/prompts.py` defines system/user prompts and precise JSON output schemas. `app/parse_llm_output.py` validates responses and will raise on mismatch. Do not change prompt schemas without updating validators.
- File parsing and tokenization for content-size checks live in `app/parse_input_files.py`; token limits are enforced in `mainapp.py` using `app/constants.MODULE_TOKEN_LIMIT`.

### Developer workflows & important commands

- Run locally: `streamlit run mainapp.py` (project root). The app defaults to MOCK_MODE so it runs offline.
- Install deps: `pip install -r requirements.txt` (package list includes streamlit, openai, python-docx, pypdf, python-pptx, mammoth, tiktoken).
- To test real LLM flows: set `OPENAI_API_KEY` in environment (or .env) and toggle Mock mode in the sidebar. The runtime model key `OPENAI_MODEL` is exposed in the sidebar and passed to `set_runtime_config`.

### Project-specific conventions and patterns

- Storing UI state: everything user-facing is kept in `st.session_state` (alias `ss` in many modules). Durable vs ephemeral keys: consult `DOMAIN_STATE_KEYS` in `app/save_load_progress.py` before persisting.
- Signatures: the app computes SHA1 signatures (`_sig_module`, `_sig_alignment`, `_sig_generation`, `_sig_questions`) in `mainapp.py` to detect when upstream content changed and to invalidate derived artifacts (alignment results, generated questions, DOCX). Prefer computing or using these existing signatures for cache invalidation.
- Mock Mode: `constants.generate_mock_*` helpers produce plausible shapes used throughout the UI — modify them only for testing/demos, not to change production data shapes.
- Prompt-to-JSON contract: prompts request strict JSON objects. `app/parse_llm_output.py` validates formats and will raise ValueError on unexpected structures. When editing prompts or validators, update both sides.

### Integration points & failure modes to watch

- LLM network failures: `app/generate_llm_output._chat_json` wraps OpenAI calls and raises on failure. UI surfaces exceptions with `st.error` and uses mock mode during demos. When enabling real mode ensure `client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))` is reachable.
- File parsing edge cases: `parse_input_files._extract_single` wraps file-type readers and raises ValueError on corrupt or unsupported files; `mainapp.py` catches and shows errors to the user.
- Token estimation: `parse_input_files.extract_text_and_tokens` uses `tiktoken.get_encoding("o200k_base")`. If you change models or encodings, update the encoder selection and the module token limit in `app/constants.py`.

### Safe change checklist for AI agents

1. When changing a prompt in `app/prompts.py`, update the corresponding validator in `app/parse_llm_output.py` and any tests. Example: if you add a new field to the question schema, add validation in `validate_questions_payload`.
2. When adding or removing durable state keys, update `DOMAIN_STATE_KEYS` in `app/save_load_progress.py` so save/load continues to work.
3. If altering the LLM client code or model settings, prefer adding feature flags and expose them via `set_runtime_config` to keep `MOCK_MODE` working for offline development.
4. When touching exports (`app/export_docx.py`), ensure `ss['include_opts']` options map to the fields the function expects (see `mainapp.py` step 5 where checkboxes are named `exp_inc_*`).

### Examples (copyable snippets)

- Invalidate questions when the module content changes: mainapp computes a new module sig via `_sig_module(text)` and calls `clear_module_dependent_outputs()` if changed. Reuse this pattern when adding derived artifacts.
- Prompt + validator coupling: `app/generate_llm_output.check_alignment` calls `prompts.build_align_user_prompt()` and then `validate_alignment_payload()`; both sides expect the pair: {label,reasons,suggested_lo}.

### Where to run tests and what to run manually

- There are no automated unit tests in the repo. Quick manual checks:
  - `streamlit run mainapp.py` to exercise the UI end-to-end (MOCK_MODE on by default).
  - Toggle Mock mode in the sidebar to validate offline vs online flows.

### If you're the coding agent: concrete first tasks

1. Small docs or linting chores: update `README.md` to include the `streamlit` command and mention Mock mode (already present but confirm accuracy).
2. Non-invasive improvements: add unit tests for `app/parse_llm_output.py` validators and `app/parse_input_files.extract_text_and_tokens` token counting.

