import json
import os
from pathlib import Path
from dotenv import load_dotenv

import requests
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
 
load_dotenv(BASE_DIR / ".env")
OLLAMA_URL = os.getenv("OLLAMA_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
PROMPT_FILE = BASE_DIR / "practices/week2/prompt.md"

LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS"))

class InvalidModelResponse(ValueError):
    """Raised when the model returns missing or invalid JSON content."""

# Read prompt from external file
def load_prompt():
    if not PROMPT_FILE.exists():
        raise FileNotFoundError("prompt.md not found")
 
    return PROMPT_FILE.read_text(encoding="utf-8") 

def analyze_meeting(transcript: str) -> dict:
    """Send a transcript to Ollama and return parsed meeting-analysis JSON."""
    prompt = load_prompt()

    OLLAMA_OPTIONS = {
        "temperature": 0,
        "top_p": 0.1,
        "top_k": 10,
        "repeat_penalty": 1.0,
        "seed": 42,
        "num_ctx": 8192,
        "num_predict": 2048
    }
    
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "format": "json",
        "options" : OLLAMA_OPTIONS,
        "stream": False,
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=LLM_TIMEOUT_SECONDS
    )
    response.raise_for_status()

    try:
        body = response.json()
        content = body["message"]["content"]
        parsed = json.loads(content)
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidModelResponse("Ollama returned an invalid response") from exc

    if not isinstance(parsed, dict):
        raise InvalidModelResponse("Model output must be a JSON object")

    return parsed
