# Week 2 - Meeting Analyzer API

FastAPI `POST /analyze-meeting` backed by Ollama. Extracts a summary, decisions,
and action items (`owner`, `action`, `due_date`). Missing owners and dates are
represented as JSON `null`; the prompt explicitly prohibits inventing dates.

## Requirements

- Python 3.10+
- Ollama installed and running
- A text model, e.g. `qwen2.5:3b`

## Setup (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
ollama pull qwen2.5:3b
```

In another terminal, ensure Ollama is running. Then start the API:

```powershell
uvicorn app.main:app --reload
```

Swagger UI: http://127.0.0.1:8000/docs

## Example request

```json
{
  "transcript": "Linh: We agree to release the update next week. Mai will run load tests by November 30, 2026. Someone should share the report."
}
```

The model should return `owner: null` and `due_date: null` for the report action
because neither is explicitly assigned. Model output is validated against the
Pydantic response schema before being returned.

## Tests

The five required failure scenarios are covered:

1. Invalid request payload -> 422
2. LLM timeout -> 504
3. Upstream HTTP 429 -> 429
4. Upstream HTTP 500 -> 502
5. Malformed/schema-invalid model response -> 502

An additional success test checks that missing owner and due date remain null.

Run:

```powershell
pytest -v
```

Tests mock the LLM call, so Ollama does not need to be running for the test suite.
