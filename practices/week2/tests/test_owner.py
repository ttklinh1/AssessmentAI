
import json
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:7b"

transcript = """
Meeting Date: 2026-11-26
Attendees: Lan, Hung, Phu

The team decided to deploy version 2.5 to production on November 27, 2026.
Lan will prepare the deployment checklist by November 25.
Hung will execute the deployment.
Phu will verify application health after the deployment.
"""

schema = {
    "type": "object",
    "properties": {
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": ["string", "null"]
                    },
                    "action": {
                        "type": "string"
                    },
                    "due_date": {
                        "type": ["string", "null"]
                    }
                },
                "required": ["owner", "action", "due_date"],
                "additionalProperties": False
            }
        }
    },
    "required": ["actions"],
    "additionalProperties": False
}

payload = {
    "model": MODEL,
    "messages": [
        {
            "role": "system",
            "content": """
Extract only explicitly assigned tasks.

For each task:
- Identify the person explicitly assigned to it.
- Use that person's name as owner.
- Use null only if the owner is genuinely unknown.
- Preserve the deadline in YYYY-MM-DD format.

Return only JSON matching the supplied schema.
"""
        },
        {
            "role": "user",
            "content": transcript
        }
    ],
    "format": schema,
    "options": {
        "temperature": 0,
        "seed": 42
    },
    "stream": False
}

response = requests.post(
    OLLAMA_URL,
    json=payload,
    timeout=300
)

response.raise_for_status()

result = response.json()
content = result["message"]["content"]

print("RAW MODEL OUTPUT:")
print(content)

print("\nPARSED ACTIONS:")
print(json.dumps(
    json.loads(content),
    ensure_ascii=False,
    indent=2
))
