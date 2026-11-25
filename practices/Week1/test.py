from openai import OpenAI
import os
from dotenv import load_dotenv
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL")
client = OpenAI(
    api_key=API_KEY,
    timeout=30,
    max_retries=2
)

def classify_issues(text):
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "Classify the issue and return JSON."
            },
            {
                "role": "user",
                "content": text
            }
        ],
        temperature=0
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    result = classify_issues(
        "Login button does not work after entering valid credentials."
    )

    print("Classification result:")
    print(result)