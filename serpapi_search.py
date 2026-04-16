import logging
from typing import Dict, List, Optional

import requests

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
DEFAULT_QUERIES = [
    '"General Counsel India operations" site:linkedin.com',
    '"VP Legal Indian company UK" site:linkedin.com',
    '"CLO fintech India Dubai" site:linkedin.com',
    '"General Counsel India operations US" site:linkedin.com',
    '"VP Legal India Singapore" site:linkedin.com',
    '"Chief Legal Officer India Australia" site:linkedin.com',
    '"in-house counsel India operations" site:linkedin.com',
    '"General Counsel Indian founder" site:linkedin.com',
]


def _parse_result(result: Dict) -> Dict:
    title = result.get("title", "")
    snippet = result.get("snippet", "")
    parts = [part.strip() for part in title.split("-") if part.strip()]
    name = parts[0] if parts else ""
    company = parts[1] if len(parts) > 1 else ""
    location = ""
    industry = ""
    for token in snippet.split("·"):
        token = token.strip()
        if not token:
            continue
        if not location:
            location = token
        elif not industry:
            industry = token
            break
    return {
        "name": name,
        "company": company,
        "role": "",
        "location": location,
        "industry": industry,
        "linkedin_url": result.get("link", ""),
        "source": "serpapi",
    }


def discover_targets(api_key: str, queries: Optional[List[str]] = None) -> List[Dict]:
    if not api_key:
        return []

    discovered: List[Dict] = []
    for query in (queries or DEFAULT_QUERIES):
        params = {"engine": "google", "q": query, "api_key": api_key}
        try:
            response = requests.get(SERPAPI_ENDPOINT, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logging.warning("SerpAPI query failed for '%s': %s", query, exc)
            continue

        for result in data.get("organic_results", []):
            link = result.get("link", "")
            if "linkedin.com" not in link:
                continue
            parsed = _parse_result(result)
            if parsed["name"] or parsed["company"] or parsed["linkedin_url"]:
                discovered.append(parsed)
    return discovered
