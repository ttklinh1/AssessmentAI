
import csv
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field
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

# client = OpenAI(
#     base_url="https://openrouter.ai",
#     api_key=API_KEY,
#     timeout=60.0,
#     max_retries=2
# )
client = OpenAI(
    http_client=http_client,
    api_key=API_KEY,

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

    # Only send issue_id and text
    return [
        {
            "issue_id": f"CASE-{index:02d}",
            "text": item["text"]
        }
        for index, item in enumerate(data, start=1)
    ]


# Call OpenAI API
def classify_issues(prompt, issues):
    print("vo day ne========")
    try:
        response = client.responses.create(
        model=MODEL,
        input=[
            {
                "role": "system",
                "content": prompt
            },
            {
                "role": "user",
                "content": json.dumps(
                    issues,
                    ensure_ascii=False
                )
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "issue_classification",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "results": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "issue_id": {
                                        "type": "string"
                                    },
                                    "category": {
                                        "type": "string",
                                        "enum": [
                                            "Bug",
                                            "Feature",
                                            "Question",
                                            "Risk"
                                        ]
                                    },
                                    "priority": {
                                        "type": "string",
                                        "enum": [
                                            "P1", "P2", "P3"
                                        ]
                                    },
                                    "next_action": {
                                        "type": "string"
                                    }
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
            }
        }
    )
        print("vo day ne========111111111111111111111111111111")
        if not response.output_text:
            raise ValueError("Empty API response")

        data = json.loads(response.output_text)

        if set(data.keys()) != {"results"}:
            raise ValueError("Unexpected JSON structure")

        if len(data["results"]) != 20:
            raise ValueError("Expected 20 predictions")

        return data["results"]
    
    except Exception as e:
        print(f"Exception type: {type(e).__name__}")
        print(f"Exception message: {str(e)}")
        traceback.print_exc()
        raise


# Validate with Pydantic
def validate_results(results, issues):
    print("vo day ne 2=============")
    predictions = [
        Prediction.model_validate(item)
        for item in results
    ]

    expected_ids = [item["issue_id"] for item in issues]
    actual_ids = [item.issue_id for item in predictions]

    if actual_ids != expected_ids:
        raise ValueError("Missing, duplicated or reordered issue IDs")

    return predictions


# Export CSV


def export_csv(predictions):
    print("vo day ne 3=============")
    fieldnames = [
        "issue_id",
        "predicted_category",
        "predicted_priority"
    ]

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for item in predictions:
            writer.writerow({
                "issue_id": item.issue_id,
                "predicted_category": item.category,
                "predicted_priority": item.priority
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

        predictions = validate_results(results, issues)

        export_csv(predictions)

        print("SUCCESS: All 20 cases validated.")

    except Exception as error:
        print(f"FAILED: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
