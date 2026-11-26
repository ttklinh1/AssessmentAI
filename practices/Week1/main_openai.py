import json
import os
import sys
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError
import certifi
import httpx
from openai import OpenAI
 
http_client = httpx.Client(
    verify=certifi.where(),
    timeout=60.0
)
 
# Configuration
BASE_DIR = Path(__file__).resolve().parent.parent.parent
 
GOLD_FILE = BASE_DIR / "data/evaluation/issue_classification_gold.json"
PROMPT_FILE = BASE_DIR / "practices/Week1/prompts.md"
OUTPUT_FILE = BASE_DIR / "practices/Week1/predictions.csv"
 
load_dotenv(BASE_DIR / ".env")
API_KEY = os.getenv("OPENAI_API_KEY")
 
if not API_KEY:
    raise ValueError("OPENAI_API_KEY not found")
 
client = OpenAI(
    http_client=http_client,
    api_key=API_KEY
)
MODEL = os.getenv("OPENAI_MODEL")
 
# Pydantic schema
class Prediction(BaseModel):
    model_config = ConfigDict(extra="forbid")
 
    issue_id: str
 
    category: Literal[
        "Bug",
        "Feature",
        "Question",
        "Risk"
    ]
 
    priority: Literal["P1", "P2", "P3"]
 
    next_action: str = Field(min_length=1)
 
class ClassificationResult(BaseModel):
    results: list[Prediction]
 
# Read prompt from external file
def load_prompt():
    if not PROMPT_FILE.exists():
        raise FileNotFoundError("prompts.md not found")
 
    return PROMPT_FILE.read_text(encoding="utf-8")
 
# Read gold file
def load_gold():
    with open(GOLD_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)
 
    if not isinstance(data, list) or len(data) != 20:
        raise ValueError("Expected exactly 20 test cases")
   
    texts = [
        item["text"].strip()
        for item in data
        if isinstance(item, dict)
        and isinstance(item.get("text"), str)
        and item["text"].strip()
    ]
    return texts
 
def classify_issues(
    prompt,
    texts: list[str]
) -> list[dict]:
    # JSON schema
    response_schema = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "issue_id": {"type": "string"},
                        "category": {"type": "string"},
                        "priority": {"type": "string"},
                        "next_action": {"type": "string"}
                    },
                    "required": [
                        "issue_id",
                        "category",
                        "priority",
                        "next_action"
                    ],
                    "additionalProperties": False
                }
            }
        },
        "required": ["results"],
        "additionalProperties": False
    }
 
    # Prepare input array
    input_data = [
        {
            "text": text
        }
        for text in texts
    ]
 
    # Send request to OpenAI
    response = client.responses.create(
        model=MODEL,
        instructions=prompt,
        input=json.dumps(
            input_data,
            ensure_ascii=False
        ),
        text={
            "format": {
                "type": "json_schema",
                "name": "issue_classification",
                "strict": True,
                "schema": response_schema
            }
        }
    )
    print(response)
 
    #Parse response
    result = json.loads(response.output_text)
 
    return result
 
def validate_json(response_text: str) -> list[dict]:
    """
    Validate OpenAI JSON response using Pydantic.
    Return a list of validated dictionaries.
    """
 
    try:
        data = json.loads(response_text)
 
        # Support JSON array or {"results": [...]}
        if isinstance(data, list):
            payload = {"results": data}
        else:
            payload = data
 
        validated = ClassificationResult.model_validate(payload)
 
        return [
            item.model_dump()
            for item in validated.results
        ]
 
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
 
    except ValidationError as e:
        raise ValueError(f"Pydantic validation failed:\n{e}")
 
def export_csv(results: list[dict]):
    """
    Export classification results to CSV.
    Columns: issue_id, predicted_category, predicted_priority
    """
 
    fieldnames = [
        "issue_id",
        "predicted_category",
        "predicted_priority"
    ]
 
    with open(OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
 
        writer.writeheader()
 
        for item in results:
            writer.writerow({
                "issue_id": item["issue_id"],
                "predicted_category": item["category"],
                "predicted_priority": item["priority"]
            })
 
    print(f"CSV exported successfully: {OUTPUT_FILE}")
 
# Main
def main():
 
    try:
        prompt = load_prompt()
        issues = load_gold()
 
        print(f"Loaded {len(issues)} issues")
        print("Prompt loaded from prompts.md")
 
        results = classify_issues(prompt, issues)
        predictions = validate_json(results)
 
        export_csv(predictions)
 
        print("SUCCESS: All 20 cases validated.")
 
    except Exception as error:
        print(f"FAILED: {error}")
        sys.exit(1)
 
 
if __name__ == "__main__":
    main()