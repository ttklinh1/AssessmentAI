Classify the input and return one valid JSON object.
 
**Category** (choose one):
- `bug`: Existing functionality fails.
- `feature`: New or changed functionality.
- `question`: Information request.
- `risk`: Potential future failure, delay, or issue.
 
**Priority** (choose one):
- `P1`: Widespread impact or imminent major incident.
- `P2`: Same-day attention; moderate operational impact.
- `P3`: Informational, non-urgent.
 
**Rules:**
- Determine category and priority from the input.
- Set `next_action` to a brief, actionable next step in English.
- Preserve the input's `issue_id`.
- Return JSON only. No markdown or explanations.
 
**Output schema:**
{
  "category": "<bug|feature|question|risk>",
  "priority": "<P1|P2|P3>",
  "next_action": "<brief next step>"
}
 
**Input:**
{text}