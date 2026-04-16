import json
from typing import Dict

from anthropic import Anthropic

MODEL = "claude-sonnet-4-20250514"
SIGNOFF = "Tushaar Nair, Advocate, Supreme Court of India, T Nair Chambers"

MESSAGE_PROMPT = f"""Generate three outreach messages in JSON with keys: connection, followup, email.

Constraints:
- Message 1 (connection): under 300 characters total
- Message 2 (followup): maximum 5 lines and asks for a call
- Message 3 (email): two paragraphs
- All messages must open with the target's psychological reality, not their title
- Must reference something specific about their company
- Must never include the word networking
- Must never use em dashes
- Must end exactly with: {SIGNOFF}
- Never mention TBD or The Big Dinner
"""


def _extract_json(raw: str) -> Dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {}


def _normalize_message(text: str) -> str:
    text = (text or "").replace("—", "-").replace("networking", "strategic connection")
    text = text.strip()
    if text.endswith(SIGNOFF):
        return text
    if text:
        return f"{text}\n\n{SIGNOFF}"
    return SIGNOFF


def _enforce_connection_length(connection: str) -> str:
    if len(connection) <= 300:
        return connection
    suffix = f"\n{SIGNOFF}"
    body_max = 300 - len(suffix) - 1
    body = connection.split("\n", 1)[0][:max(body_max, 0)].rstrip(" ,.;")
    return f"{body}\n{SIGNOFF}"


def generate_messages(target: Dict, profile: Dict, api_key: str) -> Dict[str, str]:
    if not api_key:
        base = profile.get("inner_condition") or "You are carrying concentrated legal pressure."
        company = target.get("company") or "your company"
        connection = (
            f"{base} Noticed {company}'s India-linked legal complexity and thought this may help.\n"
            f"{SIGNOFF}"
        )
        followup = (
            f"{base}\n"
            f"Your work at {company} sits at a sensitive cross-border intersection.\n"
            "If useful, may we schedule a short call this week?\n"
            f"{SIGNOFF}"
        )
        email = (
            f"{base} I have been tracking how teams like yours at {company} face difficult India-linked legal inflection points. "
            "Those moments usually demand early strategy before exposure compounds.\n\n"
            "If useful, I can share a concise view on transaction and regulatory risk concentration with practical paths to reduce downside.\n\n"
            f"{SIGNOFF}"
        )
        return {
            "connection": _enforce_connection_length(_normalize_message(connection)),
            "followup": _normalize_message(followup),
            "email": _normalize_message(email),
        }

    client = Anthropic(api_key=api_key)
    prompt = (
        f"Target details:\n{json.dumps(target, ensure_ascii=False)}\n\n"
        f"Psychological profile:\n{json.dumps(profile, ensure_ascii=False)}"
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=1200,
        temperature=0.6,
        system=MESSAGE_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )
    parsed = _extract_json(text)

    connection = _enforce_connection_length(_normalize_message(parsed.get("connection", "")))
    followup = _normalize_message(parsed.get("followup", ""))
    email = _normalize_message(parsed.get("email", ""))
    return {"connection": connection, "followup": followup, "email": email}
