# Meeting Analyzer API Documentation

**Project:** Week 2 – Meeting Analyzer API  
**Version:** 1.0.0  
**Framework:** FastAPI  
**Validation:** Pydantic  
**LLM Provider:** Ollama  
**Model:** qwen2.5:3b  

---

## 1. Overview

Meeting Analyzer API is a REST API that analyzes meeting transcripts and extracts structured information.

The API returns three main sections:

- **Summary:** A brief summary of the meeting.
- **Decisions:** Important decisions made during the meeting.
- **Action Items:** Tasks assigned during the meeting, including owner and due date when available.

The API must not invent information. If the owner or due date is not mentioned in the transcript, the corresponding value must be `null`.

## 2. System Requirements

- Python 3.10 or later.
- FastAPI.
- Ollama installed and running.
- Ollama model `qwen2.5:3b`.

## 3. Installation and Setup

### Step 1: Install the Ollama model

```bash
ollama pull qwen2.5:3b
```

### Step 2: Install Python dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Start the API server

```bash
uvicorn app.main:app --reload
```

The API server will run at:

```text
http://127.0.0.1:8000
```

## 4. OpenAPI Documentation

FastAPI automatically generates API documentation.

| Documentation | URL |
|---|---|
| Swagger UI | http://127.0.0.1:8000/docs |
| ReDoc | http://127.0.0.1:8000/redoc |
| OpenAPI JSON | http://127.0.0.1:8000/openapi.json |

Use Swagger UI to send requests and inspect API responses.

## 5. Example API Request/Response
    1. API Request
        Endpoint POST /analyze-meeting

        Content-Type: application/json

        Request Body:

        **Request body**

        ```json
        {
            "transcript": "The team agreed to complete API testing by November 30. Mai will prepare the test report."
        }
        ```
    2. API Response – Success (200 OK)

        ```json
        {
        "summary": "The team discussed API testing and agreed on the next deliverables.",
        "decisions": [
            {
            "decision": "Complete API testing by November 30."
            }
        ],
        "action_items": [
            {
            "owner": "Mai",
            "action": "Prepare the test report",
            "due_date": null
            }
        ]
        }
        ```
    3. API Response – Validation Error (422)
    Example for miss transcript field
    Request: {}

    Response: 

    ```json {
        "detail": [
            {
            "type": "missing",
            "loc": ["body", "transcript"],
            "msg": "Field required"
            }
        ]
    }
    ```
    4. API Response – Empty Transcript (400)
    Request:

    ```json {
        "transcript": ""
    }
    ```
    Response:

    ```json {
        "detail": "Transcript must not be empty."
    }
    ```
    5. API Response – Internal Server Error (500)
    Example for AI Service not response

    ```json {
        "detail": "Transcript must not be empty."
    }
    ```
    6. List API Test Cases
    TC ID	Scenario	Expected Status
    API-001	Valid transcript	200
    API-002	Missing transcript	422
    API-003	Empty transcript	400
    API-004	Invalid JSON	422
    API-005	AI service unavailable	500
    API-006	Transcript without decisions	200
    API-007	Transcript without action items	200
    API-008	Missing action owner	200 

*Note: This is an illustrative example. Actual output depends on the meeting transcript.*

## 6. Response Schema

### MeetingAnalysis

| Field | Type | Description |
|---|---|---|
| summary | string | Meeting summary |
| decisions | array | List of meeting decisions |
| action_items | array | List of assigned tasks |

### Decision

| Field | Type | Description |
|---|---|---|
| decision | string | A decision explicitly made during the meeting |

### ActionItem

| Field | Type | Description |
|---|---|---|
| owner | string or null | Person responsible for the task |
| action | string | Description of the task |
| due_date | string or null | Due date explicitly mentioned in the transcript |

## 7. Business Rules

1. Extract information only when supported by the transcript.
2. Do not interpret suggestions as confirmed decisions unless the participants agree.
3. Return `null` when an action item has no identifiable owner.
4. Return `null` when no due date is mentioned.
5. Do not calculate, guess, or invent dates.
6. Return empty arrays when no decisions or action items are identified.

## 8. Error Handling

The API handles the following error scenarios:

| HTTP Status | Scenario | Description |
|---|---|---|
| 422 | Invalid payload | Request body is missing or invalid |
| 429 | Rate limit | Upstream LLM service returns a rate-limit error |
| 502 | Upstream error | LLM service returns an unexpected HTTP error |
| 502 | Invalid model response | Model output cannot be parsed or validated |
| 504 | Timeout | LLM request exceeds the configured timeout |

### Example Error Responses

**504 – Timeout**

```json
{
  "detail": "LLM request timed out"
}
```

**429 – Rate Limit**

```json
{
  "detail": "LLM rate limit exceeded"
}
```

**502 – Upstream Service Error**

```json
{
  "detail": "LLM upstream service error"
}
```

**502 – Invalid Model Response**

```json
{
  "detail": "LLM returned an invalid response"
}
```

*Note: Actual error messages should match the implementation in `app/main.py`.*

## 9. Example Request Using PowerShell

```powershell
$body = @{
    transcript = "The team agreed to complete API testing by November 30. Mai will prepare the test report."
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/analyze-meeting" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

## 10. Configuration

The following environment variables can be used:

| Variable | Default Value | Description |
|---|---|---|
| OLLAMA_URL | http://localhost:11434/api/chat | Ollama API endpoint |
| OLLAMA_MODEL | qwen2.5:3b | LLM model name |
| LLM_TIMEOUT_SECONDS | 60 | Request timeout in seconds |

## 11. Security Considerations

- Do not commit API keys, passwords, or other secrets to Git.
- Do not include sensitive meeting information in application logs.
- Keep configuration values outside source code when appropriate.
- The default local Ollama configuration does not require an OpenAI API key.

## 12. Testing

Run the automated test suite:

```bash
pytest -v
```

The test suite covers:

| Test ID | Scenario | Expected Result |
|---|---|---|
| TC01 | Invalid request payload | 422 |
| TC02 | LLM timeout | 504 |
| TC03 | LLM rate limit | 429 |
| TC04 | Upstream HTTP 500 | 502 |
| TC05 | Malformed model response | 502 |
| TC06 | Successful analysis with missing owner/date | 200, missing fields are null |

The tests use mocked LLM responses. Therefore, passing these tests does not by itself prove real-world extraction accuracy.

A separate evaluation dataset containing 20 labeled meeting transcripts should be used to measure fact and action-item accuracy.

## 13. Acceptance Criteria

| ID | Acceptance Criteria |
|---|---|
| AC01 | API starts successfully by following README instructions |
| AC02 | OpenAPI documentation is accessible |
| AC03 | 100% of successful API outputs in the validation set conform to the expected JSON schema |
| AC04 | Fact and action-item accuracy is at least 85% across 20 evaluation cases |
| AC05 | All 5 required error scenarios pass |
| AC06 | No API keys or secrets are exposed in source code, Git history, or logs |

**Important:** These are project acceptance targets. Mark them as passed only after collecting actual test and evaluation evidence.

---

**End of Documentation**