from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from requests.exceptions import HTTPError, RequestException, Timeout

from app.schemas import MeetingAnalysis, MeetingRequest
from app.services.llm import InvalidModelResponse, analyze_meeting

app = FastAPI(
    title="Meeting Analyzer API",
    description="Extracts meeting summaries, decisions, and action items.",
    version="1.0.0",
)


@app.post("/analyze-meeting", response_model=MeetingAnalysis)
def analyze_meeting_endpoint(request: MeetingRequest) -> MeetingAnalysis:
    try:
        result = analyze_meeting(request.meeting_text)
        return MeetingAnalysis.model_validate(result)

    except Timeout:
        raise HTTPException(status_code=504, detail="LLM request timed out")

    except HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code == 429:
            raise HTTPException(status_code=429, detail="LLM rate limit exceeded")
        raise HTTPException(status_code=502, detail="LLM upstream service error")

    except (InvalidModelResponse, ValidationError, ValueError, KeyError, TypeError):
        raise HTTPException(status_code=502, detail="LLM returned an invalid response")

    except RequestException:
        raise HTTPException(status_code=502, detail="Unable to connect to LLM service")
