import json
from typing import Dict

from anthropic import Anthropic

MODEL = "claude-3-5-sonnet-20241022"

PROFILE_PROMPT = """You are an elite intelligence analyst and psychological profiler. Given a legal professional's details, produce:

1. INNER CONDITION: A 1-sentence description of their current psychological state - what keeps them up at night, what pressure they are under, what they are quietly trying to prove.

2. DECISION DRIVER: The core emotional or professional driver behind their decisions (e.g., "fear of regulatory exposure", "desire to be seen as globally sophisticated", "pressure to reduce outside counsel spend").

3. INTELLIGENCE HOOK: One specific, verifiable fact or observation about their company or industry that creates a genuine, non-generic reason to reach out. This should feel like you did actual research.

4. FIT SCORE: A number from 0-100 representing how strong a fit this person is as a legal advisory retainer client for an Indian Supreme Court advocate specialising in cross-border legal strategy, India-linked transactions, and regulatory matters. Score above 60 = qualified.

Return JSON with keys: inner_condition, decision_driver, intelligence_hook, fit_score
"""


def _extract_json(raw: str) -> Dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    cleaned = raw.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "inner_condition": "Under constant pressure to prevent cross-border legal surprises while demonstrating strategic control.",
            "decision_driver": "Need to reduce execution risk in India-linked legal exposure.",
            "intelligence_hook": "Their sector has active India-facing regulatory and transaction complexity that needs jurisdiction-aware strategy.",
            "fit_score": 0,
        }


def profile_target(target: Dict, api_key: str) -> Dict:
    if not api_key:
        return {
            "inner_condition": "Balancing legal risk containment with pressure to move business quickly.",
            "decision_driver": "Pressure to avoid avoidable regulatory risk.",
            "intelligence_hook": "Their company likely faces India-linked legal complexity that benefits from specialized counsel.",
            "fit_score": 0,
        }

    client = Anthropic(api_key=api_key)
    user_content = (
        f"Name: {target.get('name', '')}\n"
        f"Company: {target.get('company', '')}\n"
        f"Role: {target.get('role', '')}\n"
        f"Location: {target.get('location', '')}\n"
        f"Industry: {target.get('industry', '')}\n"
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=800,
            temperature=0.4,
            system=PROFILE_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
    except Exception:
        return _extract_json("")
    text = "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )
    parsed = _extract_json(text)
    try:
        parsed["fit_score"] = int(parsed.get("fit_score", 0))
    except (TypeError, ValueError):
        parsed["fit_score"] = 0
    return parsed
