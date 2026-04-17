import json
from typing import Dict

from anthropic import Anthropic

MODEL = "claude-3-5-sonnet-20241022"
SIGNOFF = "Tushaar Nair, Advocate, Supreme Court of India, T Nair Chambers"

BIG_DINNER_CITIES = {"mumbai", "bombay", "delhi", "new delhi"}

BIG_DINNER_POSTSCRIPT = (
    "Also -- I host a small dinner in the city every few weeks, "
    "just a handful of people thinking seriously about law, business, and India. "
    "No agenda, no decks. If that sounds like something you'd enjoy, happy to put you on the list."
)

MESSAGE_PROMPT_BASE = """Generate three outreach messages in JSON with keys: connection, followup, email.

Voice and tone -- this is non-negotiable:
- Write as one peer to another. No hierarchy, no selling, no asking for anything in message 1.
- Never open with what Tushaar does or offers. Open inside the target's world -- a tension they live with, a shift they are navigating, a reality they feel daily.
- Never pitch, never position, never hint at a service. The messages are a genuine observation or thought, not a door-opener to a sale.
- Warmth is fine. Curiosity is fine. Directness is fine. Salesperson energy is not.
- Treat the reader as someone who is smart, busy, and will instantly delete anything that feels like outreach.
- The goal of message 1 is only to feel human. The goal of message 2 is only to open a conversation. The goal of message 3 is to give something of value with zero strings attached.

Hard constraints:
- Message 1 (connection): under 300 characters total
- Message 2 (followup): maximum 5 lines, ends with a low-pressure invite to talk -- not a sales call, just a conversation
- Message 3 (email): two paragraphs -- first paragraph is an observation or insight that is genuinely useful to them, second paragraph is a soft, optional invite
- All messages must open with the target's psychological reality, not their title
- Must reference something specific about their company or situation
- Must never include the word networking
- Must never use em dashes
- Must never sound like legal marketing or BD copy
- Must end exactly with: {signoff}
- Never mention TBD or The Big Dinner
"""


def _is_big_dinner_city(location: str) -> bool:
    if not location:
        return False
    return any(city in location.lower() for city in BIG_DINNER_CITIES)


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
    text = (text or "").replace("\u2014", "-").replace("networking", "connecting")
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


def _append_big_dinner(email: str) -> str:
    if SIGNOFF in email:
        return email.replace(
            f"\n\n{SIGNOFF}",
            f"\n\n{BIG_DINNER_POSTSCRIPT}\n\n{SIGNOFF}",
            1,
        )
    return f"{email}\n\n{BIG_DINNER_POSTSCRIPT}\n\n{SIGNOFF}"


def generate_messages(target: Dict, profile: Dict, api_key: str) -> Dict[str, str]:
    location = target.get("location", "")
    big_dinner = _is_big_dinner_city(location)
    company = target.get("company") or "your company"

    if not api_key:
        base = profile.get("inner_condition") or "Running cross-border legal work is rarely just legal work."
        connection = (
            f"{base} The India side of that tends to move fast and quietly.\n"
            f"{SIGNOFF}"
        )
        followup = (
            f"Still thinking about what teams like yours at {company} tend to run into at the India inflection point.\n"
            "Not a pitch -- just found it worth a short conversation if the timing is right for you.\n"
            f"{SIGNOFF}"
        )
        email_body = (
            f"The India-linked legal layer for companies at {company}'s stage tends to concentrate quietly -- "
            "transaction exposure, regulatory timing, cross-border enforcement gaps -- "
            "usually showing up fully formed at the worst possible moment.\n\n"
            "Happy to share a few honest observations on where that tends to sit for teams in your position, "
            "no agenda attached. Only worth it if it is actually useful to you."
        )
        email = f"{email_body}\n\n{SIGNOFF}"
        if big_dinner:
            email = _append_big_dinner(email_body)
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
    system_prompt = MESSAGE_PROMPT_BASE.format(signoff=SIGNOFF)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1200,
            temperature=0.7,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        return generate_messages(target, profile, "")
    text = "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )
    parsed = _extract_json(text)

    connection = _enforce_connection_length(_normalize_message(parsed.get("connection", "")))
    followup = _normalize_message(parsed.get("followup", ""))
    raw_email = parsed.get("email", "")

    if big_dinner:
        raw_email = raw_email.replace(f"\n\n{SIGNOFF}", "").replace(SIGNOFF, "").strip()
        email = _append_big_dinner(raw_email)
    else:
        email = _normalize_message(raw_email)

    return {"connection": connection, "followup": followup, "email": email}
