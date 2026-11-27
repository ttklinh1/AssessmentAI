
import json
import os
from pathlib import Path
from typing import List
import re
import unicodedata
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

from app.schemas import MeetingAnalysis, ActionItem


# ============================================================
# 1. PROJECT CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent

load_dotenv(BASE_DIR / ".env")

OLLAMA_URL = os.getenv(
    "OLLAMA_URL"
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL"
)

LLM_TIMEOUT_SECONDS = float(
    os.getenv("LLM_TIMEOUT_SECONDS")
)

PROMPT_FILE = BASE_DIR / "practices" / "week2" / "prompt.md"


# ============================================================
# 2. CUSTOM EXCEPTIONS
# ============================================================

class InvalidModelResponse(ValueError):
    """Raised when Ollama returns missing or invalid JSON."""


# ============================================================
# 3. INTERNAL PYDANTIC SCHEMAS
# ============================================================

class DecisionEvidence(BaseModel):
    """One independent decision supported by transcript evidence."""

    model_config = ConfigDict(extra="forbid")

    decision: str = Field(min_length=1)
    evidence: str = Field(min_length=1)


class DecisionAuditResult(BaseModel):
    """Complete, normalized decision list returned by Pass 2."""

    model_config = ConfigDict(extra="forbid")

    decisions: List[DecisionEvidence] = Field(
        default_factory=list
    )

class ActionExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions: List[ActionItem] = Field(default_factory=list)
# ============================================================
# 4. PROMPT LOADING
# ============================================================

def load_prompt() -> str:
    """Load the main meeting extraction prompt."""

    if not PROMPT_FILE.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {PROMPT_FILE}"
        )

    return PROMPT_FILE.read_text(encoding="utf-8")


# ============================================================
# 5. OLLAMA REQUEST HELPER
# ============================================================

def call_ollama(
    system_prompt: str,
    user_message: str,
    response_schema: dict
) -> dict:
    """
    Send a structured-output request to Ollama.

    Returns the parsed JSON object.
    """

    if not OLLAMA_URL or not OLLAMA_MODEL:
        raise ValueError(
            "OLLAMA_URL and OLLAMA_MODEL must be configured."
        )

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        "format": response_schema,
        "options": {
            "temperature": 0,
            "top_p": 0.1,
            "top_k": 10,
            "repeat_penalty": 1.0,
            "seed": 42,
            "num_ctx": 8192,
            "num_predict": 3072
        },
        "stream": False
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=LLM_TIMEOUT_SECONDS
    )

    response.raise_for_status()

    try:
        body = response.json()

        if body.get("done_reason") == "length":
            raise InvalidModelResponse(
                "Ollama response was truncated."
            )

        content = body["message"]["content"]

        parsed = json.loads(content)

        if not isinstance(parsed, dict):
            raise InvalidModelResponse(
                "Model output must be a JSON object."
            )

        return parsed

    except InvalidModelResponse:
        raise

    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidModelResponse(
            "Ollama returned invalid JSON."
        ) from exc



def extract_actions(transcript: str) -> ActionExtractionResult:
    """
    Extract explicitly assigned action items independently.
    """

    system_prompt = """
You are an expert meeting action-item extraction assistant.

Extract all explicitly assigned tasks and responsibilities
from the original meeting transcript.

Return only JSON matching the supplied schema.

RULE 1 — EXPLICIT TASKS

- Extract tasks that someone explicitly agrees or is assigned
  to perform.
- Preserve the actual task meaning.
- Do not create tasks from suggestions or unaccepted proposals.
- Do not create actions solely from team-level decisions.
- Do not omit an assigned task because its deadline is missing.

RULE 2 — OWNER IDENTIFICATION

- Identify the person explicitly responsible for each task.
- The grammatical subject of an assignment sentence is
  normally the owner.
- Preserve the person's exact name as written.
- Never use owner=null when the responsible person's name
  is explicitly associated with the task.
- Use owner=null only when an actual task exists but
  its responsible person cannot be identified.
- Never infer an owner from the attendee list.

RULE 3 — SHARED TASKS

If multiple people explicitly share one task,
create one action item per person.

Example:
"Phu and Hung will implement token refresh handling."

Return:
[
  {
    "owner": "Phu",
    "action": "Implement token refresh handling",
    "due_date": "2026-12-04"
  },
  {
    "owner": "Hung",
    "action": "Implement token refresh handling",
    "due_date": "2026-12-04"
  }
]

RULE 4 — ACTION TEXT

- The action field must contain only the task description.
- Do not include deadline phrases in the action field.
- Do not include the owner's name in the action field.
- Keep the action concise and preserve its original meaning.

Example:
Incorrect:
"Implement caching by December 2, 2026"

Correct:
"Implement caching"

The deadline belongs in due_date.

RULE 5 — DEADLINES

- Extract explicitly stated deadlines.
- Convert exact dates to YYYY-MM-DD.
- Use the meeting date to determine the year when
  a month and day are given without a year.
- A deadline explicitly linked to a task may be used
  for that task.
- A clearly stated common deadline may apply to multiple
  assigned tasks.
- Do not invent different deadlines for individual tasks.
- If the deadline is vague and cannot be converted
  into one reliable calendar date, use null.
- Examples of vague deadlines:
  "by the end of December"
  "sometime next month"
  "as soon as possible"
- Use null when no reliable deadline is available.

RULE 6 — FINAL VALIDATION

For every action, verify:

1. The task is explicitly assigned or accepted.
2. The owner is correctly identified, or null if unknown.
3. Shared tasks have one item per responsible person.
4. The action contains no deadline phrase.
5. The deadline is supported by the transcript.
6. No exact date has been invented from a vague deadline.

Return only the required JSON.
"""

    parsed = call_ollama(
        system_prompt=system_prompt,
        user_message=transcript.strip(),
        response_schema=ActionExtractionResult.model_json_schema()
    )

    try:
        return ActionExtractionResult.model_validate(parsed)

    except Exception as exc:
        raise InvalidModelResponse(
            "Action extraction returned invalid data."
        ) from exc


# ============================================================
# 6. PASS 1: MEETING EXTRACTION
# ============================================================

def extract_meeting(transcript: str) -> dict:
    """
    Pass 1:
    Extract summary, decisions, and action items.
    """

    if not transcript or not transcript.strip():
        raise ValueError("Meeting transcript cannot be empty.")

    base_prompt = load_prompt()

    extraction_rules = """

ADDITIONAL EXTRACTION RULES:

DECISIONS:
- Extract every explicit, confirmed team-level decision.
- Include positive and negative decisions.
- Split independent decisions in the same sentence.
- Do not combine separate decisions into one string.
- Remove introductory phrases such as "The team agreed to".
- Preserve negation and temporary conditions such as "for now".
- Do not treat suggestions, opinions, or proposals as decisions
  unless explicitly accepted.
- Do not treat individual task assignments or personal
  commitments as team-level decisions.
- A confirmed agreement remains a decision even when no
  action items are assigned.
- A postponed decision is not an approved decision.
- Do not omit a confirmed decision simply because related
  implementation tasks are also present.


ACTIONS:

Extract every explicitly assigned task and responsibility.

OWNER IDENTIFICATION — HIGHEST PRIORITY:

1. Identify the person responsible for each task using
   the original transcript.

2. The grammatical subject of an assignment sentence
   is normally the task owner.

3. Examples:
   - "Lan will prepare the checklist."
     owner = "Lan"

   - "Hung will execute the deployment."
     owner = "Hung"

   - "Phu will verify application health."
     owner = "Phu"

   - "The checklist will be prepared by Lan."
     owner = "Lan"

4. When a person's name appears immediately before
   "will", "must", "should", "is responsible for",
   "was assigned to", or similar assignment expressions,
   associate that person with the task.

5. If multiple people are explicitly assigned to one task,
   create one action item per person.

6. Never set owner=null when the transcript explicitly
   identifies the responsible person.

7. Do not infer owners from the attendee list.
   Only use names explicitly associated with tasks.

8. Use owner=null only when an actual task exists but
   its responsible person cannot be identified from
   the transcript.

ACTION EXTRACTION:

- Extract explicitly assigned tasks and responsibilities.
- Do not create action items solely from team-level decisions.
- Do not turn an unassigned decision into an action with owner=null.
- Do not convert suggestions into actions unless someone
  explicitly accepts responsibility.
- Preserve the explicitly assigned person's name.
- Preserve explicit deadlines.
- Use null when a deadline is not stated.
- Do not omit an assigned task just because its deadline
  is missing.

MANDATORY SELF-CHECK:

Before returning the JSON, review every action item:

- Find the sentence that describes the task.
- Identify its grammatical subject.
- Check whether that subject is a person's name.
- If a person's name is explicitly linked to the task,
  assign that name to owner.
- Use null only if no responsible person can be identified.

Do not return owner=null for an explicitly named assignment.

DECISION-ACTION SEPARATION:
- Decisions describe confirmed team-level outcomes,
  choices, requirements, or changes to plans.
- Actions describe specific tasks assigned to responsible
  people.
- A decision and a related action may both be extracted
  when both are explicitly supported by the transcript.
- Never duplicate an individual task assignment in decisions.
- Never create an action merely to implement an unassigned
  team-level decision.

SUMMARY:
- Summarize the meeting accurately.
- Include important topics, confirmed decisions, and
  assigned work when relevant.
- Do not invent information.
- Do not describe suggestions as confirmed outcomes.
- Do not describe postponed proposals as approved decisions.

FINAL VALIDATION:
- Verify every decision against explicit supporting evidence.
- Verify every action against an explicit assignment
  or accepted responsibility.
- Check that no individual assignment appears as a decision.
- Check that no unassigned decision becomes an action.
- Check that unknown owners are null only for actual tasks.
- Check that shared tasks contain one entry per owner.
- Return only the JSON structure required by the supplied schema.

"""
    system_prompt = (
        base_prompt
        + "\n\n"
        + extraction_rules
    )
    parsed = call_ollama(
        system_prompt=system_prompt,
        user_message=transcript.strip(),
        response_schema=MeetingAnalysis.model_json_schema()
    )
    try:
        validated = MeetingAnalysis.model_validate(parsed)

        # Extract actions independently to improve owner identification.
        action_result = extract_actions(transcript)

        result = validated.model_dump()

        # Use the independently extracted actions.
        result["actions"] = [
            action.model_dump()
            for action in action_result.actions
        ]

        return MeetingAnalysis.model_validate(result).model_dump()

    except InvalidModelResponse:
        raise

    except Exception as exc:
        raise InvalidModelResponse(
            "Pass 1 returned invalid meeting analysis."
        ) from exc

# ============================================================
# 7. PASS 2: DECISION COMPLETENESS AUDIT
# ============================================================


def audit_decisions(
    transcript: str,
    initial_decisions: list[str]
) -> DecisionAuditResult:
    print("\nINITIAL DECISIONS:")
    print(json.dumps(initial_decisions))
    
    """
    Pass 2:
    Audit all explicit team-level decisions.

    Exclude individual task assignments and personal commitments.
    """

    
    system_prompt = """
    You are an expert meeting decision extraction auditor.

    Your task is to extract the COMPLETE list of explicit,
    confirmed team-level decisions from the original transcript.

    You will receive:
    1. The original meeting transcript.
    2. Decisions extracted by Pass 1.

    Treat Pass 1 decisions only as reference material.
    Independently verify every decision against the transcript.

    Return only JSON matching the supplied schema.

    RULE 1 — WHAT COUNTS AS A DECISION

    A decision is an explicit, confirmed team-level:
    - Agreement
    - Choice
    - Approval
    - Rejection
    - Requirement
    - Direction
    - Change to an existing plan

    The transcript must indicate that the team accepted
    or confirmed the outcome.

    A decision does not require:
    - An assigned owner
    - An implementation task
    - A deadline

    Explicit consensus is a valid decision.

    Examples:

    "Everyone agreed that refactoring is necessary."
    Decision:
    "Refactoring is necessary."

    "The team agreed to improve API documentation."
    Decision:
    "Improve API documentation."

    "The team decided to deploy version 2.5."
    Decision:
    "Deploy version 2.5."

    RULE 2 — INDIVIDUAL ACTIONS ARE NOT DECISIONS

    Individual assignments and personal commitments are Actions,
    not team-level Decisions.

    Examples:

    "An will investigate high CPU usage."
    No decision.

    "Lan agreed to investigate the feasibility of replacing
    integration tests with unit tests."
    No decision.

    "Phu will update the database configuration."
    No decision.

    Do not infer team approval from an individual's commitment
    to investigate, research, review, evaluate, or implement
    a proposal.

    IMPORTANT:
    A team may assign an investigation task without approving
    the proposal being investigated.

    However:

    "The team agreed to replace integration tests with unit tests."
    This IS a decision.

    RULE 3 — SUGGESTIONS AND UNRESOLVED PROPOSALS

    Do not extract:
    - Suggestions that were not accepted.
    - Personal opinions.
    - Questions.
    - Proposals awaiting further discussion.
    - Unresolved disagreements.
    - Decisions pending customer feedback.
    - Proposals for which no final choice was made.

    Examples:

    "Minh suggested upgrading Rails next quarter."
    No decision.

    "The team discussed the upgrade but made no final decision."
    No decision.

    "Phu suggested dark mode, while Hung recommended waiting
    for customer feedback."
    No decision.

    RULE 4 — POSTPONED DECISIONS

    A statement that a decision was postponed or deferred
    describes an unresolved decision status.

    It is NOT itself a confirmed decision.

    Example:

    "The decision was postponed until the next planning meeting."

    Correct:
    decisions = []

    Incorrect:
    "Postpone the decision until the next planning meeting."

    Do not convert a pending decision into an accepted decision.

    IMPORTANT DISTINCTION:

    "The decision was postponed until the next meeting."
    No decision.

    "The team agreed to delay the already-approved release
    until December 7."
    Decision:
    "Delay the approved release until December 7."

    The second example is a confirmed change to an existing plan.

    RULE 5 — NEGATIVE DECISIONS

    Preserve explicit decisions not to do something.

    Example:

    "The team decided not to migrate to a larger server for now."

    Decision:
    "Do not migrate to a larger server for now."

    Preserve restrictions such as:
    - not
    - for now
    - temporarily
    - until further notice

    Do not confuse a negative decision with an unresolved proposal.

    RULE 6 — ATOMIC DECISIONS

    Extract each independent decision separately.

    Example:

    "The team agreed to increase the connection pool limit
    and add monitoring alerts."

    Correct:
    [
    "Increase the connection pool limit.",
    "Add monitoring alerts."
    ]

    Do not combine independent decisions into one item.

    RULE 7 — NORMALIZATION

    - Remove introductory phrases such as:
    "The team agreed to"
    "The team decided to"
    "The team approved"
    "Everyone agreed that"
    - Preserve the actual decision meaning.
    - Do not add information that is absent from the transcript.
    - Keep each decision concise and self-contained.

    RULE 8 — EVIDENCE

    Every decision must include a short, verbatim excerpt
    from the original transcript.

    Evidence must:
    - Exist in the original transcript.
    - Directly support the decision.
    - Support team-level acceptance or confirmation.
    - Not use an individual task as evidence for a team decision.

    RULE 9 — NO DUPLICATES AND ORDER

    - Each independent decision must appear exactly once.
    - Preserve chronological order from the transcript.

    RULE 10 — FINAL VALIDATION

    Before returning the result, verify every candidate:

    1. Is this an explicit team-level outcome?
    2. Was it accepted, agreed, approved, selected,
    required, or explicitly rejected?
    3. Is it merely an individual task or commitment?
    4. Is it only a suggestion or unresolved proposal?
    5. Was the decision postponed or deferred?
    6. Does the evidence directly support the decision?

    Exclude any candidate that:
    - Is only an individual task.
    - Is only a suggestion.
    - Is still unresolved.
    - Is only a description of a postponed decision.

    Do not omit an explicit team agreement simply because
    no implementation task was assigned.

    Return the COMPLETE decision list, not only missing items.

    Return only JSON matching this schema:

    {
    "decisions": [
        {
        "decision": "A single normalized team-level decision.",
        "evidence": "Verbatim supporting text from the transcript."
        }
    ]
    }
    """

    user_message = f"""
    ORIGINAL MEETING TRANSCRIPT:

    {transcript}

    DECISIONS EXTRACTED BY PASS 1:

    {json.dumps(initial_decisions, ensure_ascii=False, indent=2)}

    Review the entire transcript independently.
    Return the complete list of confirmed team-level decisions.
    Exclude individual task assignments and personal commitments.
    """

    parsed = call_ollama(
            system_prompt=system_prompt,
            user_message=user_message,
            response_schema=DecisionAuditResult.model_json_schema()
        )
    print("\nAUDIT RESULT:")
    print(json.dumps(parsed, ensure_ascii=False, indent=2))
    try:
        return DecisionAuditResult.model_validate(parsed)

    except Exception as exc:
        raise InvalidModelResponse(
            "Pass 2 returned an invalid decision audit."
        ) from exc

# ============================================================
# 8. MERGE AND VALIDATE DECISIONS
# ============================================================





def normalize_evidence(text: str) -> str:
    """
    Normalize evidence before matching against transcript.

    Removes surrounding quotation marks and normalizes whitespace.
    """

    text = text.strip()

    # Remove surrounding quotation marks.
    text = text.strip("\"'“”‘’`")

    # Normalize multiple spaces and line breaks.
    text = re.sub(r"\s+", " ", text)

    return text.strip()

def normalize_for_matching(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.casefold()

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    # Ignore punctuation differences
    text = re.sub(r"[^\w\s]", "", text)

    return text.strip()


def find_evidence_position(transcript: str, evidence: str):
    normalized_transcript = normalize_for_matching(transcript)
    normalized_evidence = normalize_for_matching(evidence)

    if not normalized_evidence:
        return -1

    return normalized_transcript.find(normalized_evidence)
def merge_missing_decisions(
    transcript: str,
    initial_decisions: list[str],
    audit_result: DecisionAuditResult
) -> list[str]:
    """
    Merge the complete audited decision list.

    Accept decisions only when their evidence can be found
    in the original transcript.

    Fall back to Pass 1 if no audited evidence is valid.
    """

    verified_decisions = []

    for item in audit_result.decisions:

        decision = item.decision.strip()
        evidence = item.evidence.strip()

        if not decision or not evidence:
            continue

        position = find_evidence_position(
            transcript,
            evidence
        )

        if position is None:
            print(
                "[WARNING] Evidence not found:",
                evidence
            )
            continue

        verified_decisions.append({
            "decision": decision,
            "position": position
        })

    # Fallback if Pass 2 returns no verifiable decisions.
    if not verified_decisions:
        print(
            "[WARNING] No valid audited decisions. "
            "Using Pass 1 decisions."
        )

        return deduplicate_decisions(initial_decisions)

    # Sort by original transcript position.
    verified_decisions.sort(
        key=lambda item: item["position"]
    )

    merged = [
        item["decision"]
        for item in verified_decisions
    ]

    return deduplicate_decisions(merged)

def deduplicate_decisions(
    decisions: list[str]
) -> list[str]:
    """Remove exact normalized duplicate decisions."""

    result = []
    seen = set()

    for decision in decisions:
        if not isinstance(decision, str):
            continue

        decision = decision.strip()

        if not decision:
            continue

        key = " ".join(decision.casefold().split())

        if key not in seen:
            seen.add(key)
            result.append(decision)

    return result

def remove_decision_only_actions(
    decisions: list[str],
    actions: list
) -> list:
    """
    Remove actions that only repeat team-level decisions.

    Keep actions with an explicit owner.
    Keep owner=None actions unless they clearly duplicate
    a decision without describing a separate task.
    """

    cleaned_actions = []

    normalized_decisions = [
        normalize_evidence(decision).casefold().rstrip(".")
        for decision in decisions
    ]
    print("[INFO] actions filtering:")
    print(json.dumps(actions, ensure_ascii=False, indent=2))
    for action in actions:
        action_text = (
            normalize_evidence(action["action"])
            .casefold()
            .rstrip(".")
        )

        if action["owner"] is None and action_text in normalized_decisions:
            print(
                "[INFO] Removed decision-only action:",
                action["action"]
            )
            continue

        cleaned_actions.append(action)

    return cleaned_actions
# ============================================================
# 9. COMPLETE MEETING ANALYSIS
# ============================================================

def analyze_meeting(meeting_text: str) -> dict:
    """
    Execute the complete meeting analysis workflow.

    Pass 1: Extract meeting analysis.
    Pass 2: Audit and normalize all decisions.
    Final: Merge audited decisions into the original result.
    """

    if not meeting_text or not meeting_text.strip():
        raise ValueError("Meeting transcript cannot be empty.")

    transcript = meeting_text.strip()

    # --------------------------------------------------------
    # PASS 1
    # --------------------------------------------------------

    result = extract_meeting(transcript)
    print("\n[DEBUG] PASS 1 ACTIONS:")
    print(json.dumps(
    result["actions"],
    ensure_ascii=False,
    indent=2
))
    # --------------------------------------------------------
    # PASS 2
    # --------------------------------------------------------

    audit_result = audit_decisions(
        transcript,
        result["decisions"]
    )

    # --------------------------------------------------------
    # MERGE
    # --------------------------------------------------------

    result["decisions"] = merge_missing_decisions(
        transcript,
        result["decisions"],
        audit_result
    )
    result["actions"] = remove_decision_only_actions(
        result["decisions"],
        result["actions"]
    )
    # --------------------------------------------------------
    # FINAL VALIDATION
    # --------------------------------------------------------

    try:
        final_result = MeetingAnalysis.model_validate(result)
    except Exception as exc:
        raise InvalidModelResponse(
            "Final meeting analysis failed schema validation."
        ) from exc

    final_output = final_result.model_dump()

    print(json.dumps(
        final_output,
        ensure_ascii=False,
        indent=2
    ))

    return final_output
