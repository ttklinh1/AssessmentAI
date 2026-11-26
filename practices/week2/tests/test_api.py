import requests
from fastapi.testclient import TestClient

from app.main import app
import app.main as main_module

client = TestClient(app)

VALID_RESULT = {
    "summary": "The team agreed to improve checkout performance.",
    "decisions": [{"decision": "Prioritize checkout optimization"}],
    "action_items": [
        {"owner": "Mai", "action": "Run load tests", "due_date": "2026-11-30"},
        {"owner": None, "action": "Share the test report", "due_date": None},
    ],
}


def test_invalid_payload_returns_422():
    response = client.post("/analyze-meeting", json={"wrong_field": "hello"})
    assert response.status_code == 422


def test_timeout_returns_504(monkeypatch):
    def fake_analyze(_meeting_text):
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(main_module, "analyze_meeting", fake_analyze)
    response = client.post("/analyze-meeting", json={"transcript": "Meeting notes"})
    assert response.status_code == 504


def test_rate_limit_429_is_preserved(monkeypatch):
    def fake_analyze(_meeting_text):
        error_response = requests.Response()
        error_response.status_code = 429
        raise requests.exceptions.HTTPError(response=error_response)

    monkeypatch.setattr(main_module, "analyze_meeting", fake_analyze)
    response = client.post("/analyze-meeting", json={"transcript": "Meeting notes"})
    assert response.status_code == 429


def test_upstream_500_returns_502(monkeypatch):
    def fake_analyze(_meeting_text):
        error_response = requests.Response()
        error_response.status_code = 500
        raise requests.exceptions.HTTPError(response=error_response)

    monkeypatch.setattr(main_module, "analyze_meeting", fake_analyze)
    response = client.post("/analyze-meeting", json={"transcript": "Meeting notes"})
    assert response.status_code == 502


def test_malformed_model_output_returns_502(monkeypatch):
    def fake_analyze(_meeting_text):
        return {"summary": "Only a summary", "decisions": "not-a-list"}

    monkeypatch.setattr(main_module, "analyze_meeting", fake_analyze)
    response = client.post("/analyze-meeting", json={"transcript": "Meeting notes"})
    assert response.status_code == 502


def test_success_and_missing_fields_are_null(monkeypatch):
    monkeypatch.setattr(main_module, "analyze_meeting", lambda _meeting_text: VALID_RESULT)
    response = client.post("/analyze-meeting", json={"transcript": "Meeting notes"})
    assert response.status_code == 200
    data = response.json()
    assert data["action_items"][1]["owner"] is None
    assert data["action_items"][1]["due_date"] is None
