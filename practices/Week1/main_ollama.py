import json
import os
import sys
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError
import certifi
import httpx
import requests
import csv

# Configuration
BASE_DIR = Path(__file__).resolve().parent.parent.parent
 
GOLD_FILE = BASE_DIR / "data/evaluation/issue_classification_gold.json"
PROMPT_FILE = BASE_DIR / "practices/Week1/prompts.md"
OUTPUT_FILE = BASE_DIR / "practices/Week1/predictions.csv"
 
load_dotenv(BASE_DIR / ".env")
MODEL = os.getenv("OPENAI_MODEL")
OLLAMA_URL = os.getenv("OLLAMA_URL")
# Pydantic schema
class Prediction(BaseModel):
    model_config = ConfigDict(extra="forbid")
 
    category: Literal[
        "bug",
        "feature",
        "question",
        "risk"
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
    """
    Load all issue_id and text from gold.json.
    Return: list of dictionaries.
    """
    path = Path(GOLD_FILE)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("gold.json must contain a JSON array")

    records = []

    for index, item in enumerate(data):
        issue_id = item.get("issue_id")
        text = item.get("text")

        if not issue_id or not text:
            raise ValueError(f"Invalid record at index {index}")

        records.append({
            "issue_id": issue_id,
            "text": text
        })

    print(f"Loaded {len(records)} records")

    return records

 
def classify_issues(
    prompt,
    text: str
) -> dict:
    
    # JSON schema
    response_schema = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "priority": {"type": "string"},
                        "next_action": {"type": "string"}
                    },
                    "required": [
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
    ]
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": prompt
            },
            {
                "role": "user",
                "content": json.dumps(
                    input_data,
                    ensure_ascii=False
                )
            }
        ],
        "stream": False,
        "format": response_schema,
        "options": {
            "temperature": 0,
            "num_ctx": 8192,
            "num_predict": 4096
        }
    }
    # Send request to OLLAMA
    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=600
    )
    response.raise_for_status()

    result = response.json()
    return result["message"]["content"]
 
def validate_json(response_text: str):
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
 
        return validated.results[0] if validated.results else {}
 
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
 
    except ValidationError as e:
        raise ValueError(f"Pydantic validation failed:\n{e}")
 

def export_csv(results):
    import csv

    fieldnames = [
        "issue_id",
        "predicted_category",
        "predicted_priority"
    ]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"Exported {len(results)} records to {OUTPUT_FILE}")

 
# Main
def main():
 
    try:
        prompt = load_prompt()
        issues = load_gold()
 
        print(f"Loaded {len(issues)} issues")
        print("Prompt loaded from prompts.md")
        # Step 2: Initialize a new results array
        results = []

        # Step 3: Classify each record
        for record in issues:
            issue_id = record["issue_id"]
            text = record["text"]

            print(f"Classifying {issue_id}...")

            classification = classify_issues(prompt, text)
            predictions = validate_json(classification)
            # Step 4: Merge original data and classification result
            result = {
                "issue_id": issue_id,
                "predicted_category": predictions.category,
                "predicted_priority": predictions.priority
            }

            results.append(result)

        # Step 5: Export results
        export_csv(results)

        print(f"Completed: {len(results)} records processed.")
  
    except Exception as error:
        print(f"FAILED: {error}")
        sys.exit(1)
 
 
if __name__ == "__main__":
    main()