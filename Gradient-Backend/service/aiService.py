import os
from typing import Any, Dict
from urllib.parse import urlparse

from dotenv import load_dotenv
from openai import OpenAI
from ddgs import DDGS
#from duckduckgo_search import DDGS
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import re

import requests

from service.settingsService import get_reply_settings

load_dotenv()


client = OpenAI()


AI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
COMPANY_SEARCH_ENABLED = os.getenv("COMPANY_SEARCH_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
    "on",
}
COMPANY_SEARCH_MAX_RESULTS = int(os.getenv("COMPANY_SEARCH_MAX_RESULTS", "6"))
COMPANY_SEARCH_TIMEOUT_SECONDS = float(os.getenv("COMPANY_SEARCH_TIMEOUT_SECONDS", "6"))
COMPANY_SEARCH_MAX_TOOL_CALLS = int(os.getenv("COMPANY_SEARCH_MAX_TOOL_CALLS", "2"))
PERSON_SEARCH_MAX_RESULTS = int(os.getenv("PERSON_SEARCH_MAX_RESULTS", "4"))
AI_DEBUG = os.getenv("AI_DEBUG", "false").strip().lower() in {"1", "true", "yes", "y", "on"}

_company_search_cache: Dict[str, str] = {}
_company_search_struct_cache: Dict[str, list[dict[str, str]]] = {}
_person_search_cache: Dict[str, list[dict[str, str]]] = {}

MAX_REPLY_WORDS = 140
REPLY_VARIANTS = ("follow_up", "recap", "quick")


def _to_serializable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_serializable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_to_serializable(item) for item in value]
    if isinstance(value, (str, int, float)) or value is None:
        return value
    if isinstance(value, bool):
        return value
    return str(value)


def _pretty_json(data: dict | list | None) -> str:
    if not data:
        return "{}"
    try:
        return json.dumps(_to_serializable(data), ensure_ascii=False, indent=2)
    except Exception:
        return json.dumps({}, indent=2)


def _enforce_word_limit(text: str, max_words: int = MAX_REPLY_WORDS) -> str:
    words = re.findall(r"\S+", text)
    if len(words) <= max_words:
        return text.strip()
    trimmed = " ".join(words[:max_words]).strip()
    if not trimmed.endswith((".", "!", "?")):
        trimmed += "..."
    return trimmed


def _normalize_placeholder_key(key: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", key.upper()).strip("_")


def _flatten_for_placeholders(prefix: str, value: Any) -> dict[str, str]:
    items: dict[str, str] = {}
    if value is None:
        return items
    if isinstance(value, dict):
        for sub_key, sub_val in value.items():
            combined = f"{prefix}_{sub_key}" if prefix else str(sub_key)
            items.update(_flatten_for_placeholders(combined, sub_val))
        return items
    if isinstance(value, list):
        if all(isinstance(item, dict) for item in value):
            for idx, item in enumerate(value, start=1):
                combined = f"{prefix}_{idx}" if prefix else str(idx)
                items.update(_flatten_for_placeholders(combined, item))
        else:
            items[prefix] = ", ".join(str(item) for item in value if str(item).strip())
        return items

    if prefix:
        items[prefix] = str(value)
    return items


def _collect_placeholder_mapping(
    lead: dict[str, Any] | None,
    email: dict[str, Any] | None,
    placeholders: dict[str, Any] | None,
) -> dict[str, str]:
    mapping: dict[str, str] = {}

    def register(key: str, value: Any) -> None:
        if value is None:
            return
        norm = _normalize_placeholder_key(key)
        if not norm:
            return
        text = str(value).strip()
        if not text:
            return
        mapping.setdefault(norm, text)

    for source in (placeholders or {}).items():
        key, value = source
        register(str(key), value)

    for key, value in (email or {}).items():
        register(f"email_{key}", value)

    for key, value in (lead or {}).items():
        register(f"lead_{key}", value)

    for key, value in _flatten_for_placeholders("lead", lead or {}).items():
        register(key, value)

    for key, value in _flatten_for_placeholders("email", email or {}).items():
        register(key, value)

    full_name = (lead or {}).get("full_name") or "".join(
        filter(None, [
            (lead or {}).get("first_name"),
            (lead or {}).get("last_name"),
        ])
    )
    if full_name:
        register("name", full_name)
        register("client_name", full_name)

    subject = (email or {}).get("subject")
    if subject:
        register("subject", subject)
        register("topic_discussed", subject)

    return mapping


def _render_prompt(template: str, mapping: dict[str, str]) -> str:
    if not template:
        return ""

    pattern = re.compile(r"\[([^\[\]]+)\]")

    def replacer(match: re.Match[str]) -> str:
        raw_key = match.group(1)
        norm_key = _normalize_placeholder_key(raw_key)
        replacement = mapping.get(norm_key)
        return replacement if replacement is not None else match.group(0)

    return pattern.sub(replacer, template).strip()


def _compose_reply_context(
    lead: dict[str, Any] | None,
    email: dict[str, Any] | None,
    placeholders: dict[str, Any] | None,
) -> str:
    sections: list[str] = []
    email_section = _pretty_json(email or {})
    lead_section = _pretty_json(lead or {})
    sections.append(f"EMAIL CONTEXT:\n{email_section}")
    sections.append(f"LEAD DATA:\n{lead_section}")
    if placeholders:
        sections.append(f"ADDITIONAL PLACEHOLDERS:\n{_pretty_json(placeholders)}")
    return "\n\n".join(sections)


def _build_reply_messages(rendered_prompt: str, context: str) -> list[dict[str, str]]:
    system_prompt = (
        "You are an experienced sales development representative drafting concise email replies. "
        "Always respond in English. Limit the reply to 140 words. Use only factual information provided in the context. "
        "Do not invent names, dates, or commitments beyond what the context states."
    )

    user_prompt = (
        "Follow this reply blueprint and fill placeholders with the factual details from the context.\n\n"
        f"Reply blueprint:\n{rendered_prompt or '<no prompt provided>'}\n\n"
        f"Context with factual data:\n{context or '<empty>'}\n\n"
        "Output only the email body, without subject lines, notes, or extra commentary."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _apply_reply_blocks(prompt_text: str, top_block: str, bottom_block: str) -> str:
    parts = [part.strip() for part in (top_block, prompt_text, bottom_block) if isinstance(part, str) and part.strip()]
    return "\n\n".join(parts).strip()


def _generate_single_reply_variant(
    variant: str,
    *,
    template: str,
    mapping: dict[str, str],
    context: str,
    style_modifier: str,
    top_block: str,
    bottom_block: str,
) -> tuple[str, str]:
    rendered_prompt = _render_prompt(template, mapping)
    if style_modifier:
        rendered_prompt = _apply_reply_blocks(rendered_prompt, style_modifier, "")
    rendered_prompt = _apply_reply_blocks(rendered_prompt, str(top_block), str(bottom_block))

    if not rendered_prompt:
        return variant, ""

    messages = _build_reply_messages(rendered_prompt, context)

    try:
        completion = client.chat.completions.create(
            model=AI_MODEL,
            messages=messages,
            temperature=0.35,
        )
        choice = completion.choices[0] if completion.choices else None
        content = choice.message.content if choice and choice.message else ""
    except Exception as exc:  # pragma: no cover
        if AI_DEBUG:
            print(f"[AI] generate_email_replies error for {variant}: {exc}")
        content = ""

    max_words = 60 if variant == "quick" else MAX_REPLY_WORDS
    return variant, _enforce_word_limit(content or "", max_words=max_words)


def generate_email_replies(
    *,
    lead: dict[str, Any] | None,
    email: dict[str, Any] | None,
    placeholders: dict[str, Any] | None = None,
    prompt_overrides: dict[str, str] | None = None,
    style: str | None = None,
) -> dict[str, str]:
    settings = get_reply_settings()
    stored_prompts = settings.get("prompts", {}) if isinstance(settings, dict) else {}
    top_block = settings.get("topBlock", "") if isinstance(settings, dict) else ""
    bottom_block = settings.get("bottomBlock", "") if isinstance(settings, dict) else ""
    styles = settings.get("styles", {}) if isinstance(settings, dict) else {}
    style_key = (style or "").strip().lower()
    style_modifier = ""
    if style_key in {"official", "semi_official"} and isinstance(styles, dict):
        style_modifier = str(styles.get(style_key) or "")
    prompts: dict[str, str] = {
        variant: (stored_prompts.get(variant) or "")
        for variant in REPLY_VARIANTS
    }

    if prompt_overrides:
        for key, value in prompt_overrides.items():
            if key in prompts and isinstance(value, str) and value.strip():
                prompts[key] = value

    mapping = _collect_placeholder_mapping(lead, email, placeholders)
    context = _compose_reply_context(lead, email, placeholders)

    replies: dict[str, str] = {variant: "" for variant in REPLY_VARIANTS}
    with ThreadPoolExecutor(max_workers=len(REPLY_VARIANTS)) as executor:
        futures = [
            executor.submit(
                _generate_single_reply_variant,
                variant,
                template=prompts.get(variant, ""),
                mapping=mapping,
                context=context,
                style_modifier=style_modifier,
                top_block=str(top_block),
                bottom_block=str(bottom_block),
            )
            for variant in REPLY_VARIANTS
        ]
        for future in futures:
            variant, content = future.result()
            replies[variant] = content

    return replies


_PERSONAL_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "icloud.com",
    "proton.me",
    "protonmail.com",
    "ukr.net",
    "i.ua",
}


def _company_candidate_from_sender_email(sender_email: str) -> str | None:
    if not sender_email or "@" not in sender_email:
        return None

    domain = sender_email.split("@", 1)[1].strip().lower()
    if not domain or domain in _PERSONAL_EMAIL_DOMAINS:
        return None

    # Get a best-effort "brand" from domain.
    # Examples:
    #   mail.softserve.com -> softserve
    #   nova-poshta.ua -> nova-poshta
    parts = [p for p in domain.split(".") if p]
    if len(parts) < 2:
        return None

    sld = parts[-2]
    if not sld or sld in {"mail", "smtp", "api", "app", "www"}:
        return None

    candidate = sld.replace("-", " ").strip()
    if not candidate:
        return None

    # Title-case words but keep it simple (LLM can normalize further).
    return " ".join([w[:1].upper() + w[1:] for w in candidate.split() if w]) or None


def search_company_tool(company_name: str) -> str:
    if not company_name:
        return "No company provided."

    cached = _company_search_cache.get(company_name)
    if cached is not None:
        return cached

    query_variants = [
        f'"{company_name}" company overview',
        f'"{company_name}" official website',
        f'"{company_name}" about us',
        f'"{company_name}" services',
    ]

    def _format_entry(index: int, title: str, snippet: str, url: str) -> str:
        domain = urlparse(url).netloc if url else ""
        header = f"{index}. {title or 'No title'}"
        if domain:
            header += f" ({domain})"
        details: list[str] = [header]
        if snippet:
            details.append(f"   Snippet: {snippet}")
        if url:
            details.append(f"   URL: {url}")
        return "\n".join(details)

    try:
        aggregated: list[dict] = []
        seen_keys: set[str] = set()

        def _search_once(query: str) -> list[dict]:
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=COMPANY_SEARCH_MAX_RESULTS))

        with ThreadPoolExecutor(max_workers=1) as ex:
            for query in query_variants:
                fut = ex.submit(_search_once, query)
                results = fut.result(timeout=COMPANY_SEARCH_TIMEOUT_SECONDS)

                for result in results:
                    title = (result.get("title") or "").strip()
                    snippet = (result.get("body") or "").strip()
                    url = (result.get("href") or result.get("url") or "").strip()

                    if not title and not snippet and not url:
                        continue

                    dedupe_key = url or f"{title}|{snippet}"
                    if dedupe_key in seen_keys:
                        continue
                    seen_keys.add(dedupe_key)

                    aggregated.append({
                        "title": title,
                        "snippet": snippet,
                        "url": url,
                    })

                    if len(aggregated) >= COMPANY_SEARCH_MAX_RESULTS:
                        break

                if len(aggregated) >= COMPANY_SEARCH_MAX_RESULTS:
                    break

        if not aggregated:
            out = "No info found online."
            _company_search_cache[company_name] = out
            _company_search_struct_cache[company_name] = []
            return out

        context_lines = [
            _format_entry(idx, entry["title"], entry["snippet"], entry["url"])
            for idx, entry in enumerate(aggregated, start=1)
        ]
        context = "\n".join(context_lines)
        _company_search_cache[company_name] = context
        _company_search_struct_cache[company_name] = aggregated
        return context
    except TimeoutError:
        out = "Search timeout."
        _company_search_cache[company_name] = out
        return out
    except Exception as e:
        out = f"Error during search: {e}"
        _company_search_cache[company_name] = out
        return out


def search_person_insights(full_name: str, company_hint: str | None = None) -> list[dict[str, str]]:
    """Search for person insights using DuckDuckGo to infer role and social links."""

    if not full_name:
        return []

    cache_key = f"{full_name}|{company_hint or ''}"
    if cache_key in _person_search_cache:
        return _person_search_cache[cache_key]

    query = full_name
    if company_hint:
        query = f"{full_name} {company_hint}"

    results: list[dict[str, str]] = []

    try:
        with DDGS() as ddgs:
            matches = ddgs.text(query, max_results=PERSON_SEARCH_MAX_RESULTS)

        for match in matches:
            title = (match.get("title") or "").strip()
            snippet = (match.get("body") or "").strip()
            url = (match.get("href") or match.get("url") or "").strip()

            if not any([title, snippet, url]):
                continue

            results.append({
                "title": title,
                "snippet": snippet,
                "url": url,
            })

            if len(results) >= PERSON_SEARCH_MAX_RESULTS:
                break
    except Exception as exc:  # pragma: no cover - network errors tolerated
        if AI_DEBUG:
            print(f"[AI] person search failed: {exc}")

    _person_search_cache[cache_key] = results
    return results


def fetch_website_tool(url: str) -> str:
    if not url:
        return "No website provided."

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; GradientBot/1.0; +https://example.com)"
        }
        resp = requests.get(url, headers=headers, timeout=COMPANY_SEARCH_TIMEOUT_SECONDS)
        if resp.status_code >= 400:
            return f"Website request failed with status {resp.status_code}."

        html = resp.text or ""

        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""

        desc_match = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
            html,
            flags=re.IGNORECASE,
        )
        desc = re.sub(r"\s+", " ", desc_match.group(1)).strip() if desc_match else ""

        og_desc_match = re.search(
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
            html,
            flags=re.IGNORECASE,
        )
        og_desc = re.sub(r"\s+", " ", og_desc_match.group(1)).strip() if og_desc_match else ""

        summary_parts = []
        if title:
            summary_parts.append(f"Title: {title}")
        if desc:
            summary_parts.append(f"Meta description: {desc}")
        if og_desc and og_desc != desc:
            summary_parts.append(f"OG description: {og_desc}")

        return "\n".join(summary_parts) or "No usable metadata found on website."
    except Exception as e:
        return f"Error fetching website: {e}"


tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "search_company_tool",
            "description": "Use this if you found a company name in the email and need extra details (website, short overview).",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "Company name found in the email (e.g. 'SoftServe' or 'Nova Poshta').",
                    }
                },
                "required": ["company_name"],
            },
        },
    }
    ,
    {
        "type": "function",
        "function": {
            "name": "fetch_website_tool",
            "description": "Use this if the email contains a website URL. Fetch the website to extract title and meta description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "A website URL found in the email (e.g. 'https://thegradient.com').",
                    }
                },
                "required": ["url"],
            },
        },
    }
]


def _website_candidate_from_body(body: str) -> str | None:
    if not body:
        return None
    m = re.search(r"https?://[^\s)\]>\"']+", body, flags=re.IGNORECASE)
    return m.group(0) if m else None


def _first_nonempty(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in {"null", "none", "n/a", "unknown", "—", "-", "невідомо", "no company info"}:
            continue
        return text
    return None


def _dedupe_text(text: str | None) -> str | None:
    if not text:
        return None

    normalized = re.sub(r"[ \t]+", " ", text.strip())
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", normalized) if part.strip()]
    if len(paragraphs) > 1:
        seen: set[str] = set()
        unique: list[str] = []
        for paragraph in paragraphs:
            key = paragraph.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(paragraph)
        if len(unique) < len(paragraphs):
            return "\n\n".join(unique)

    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    seen_sentences: set[str] = set()
    unique_sentences: list[str] = []
    for sentence in sentences:
        key = sentence.strip().lower()
        if not key or key in seen_sentences:
            continue
        seen_sentences.add(key)
        unique_sentences.append(sentence.strip())
    return " ".join(unique_sentences) if unique_sentences else normalized


def _limit_sentences(text: str | None, max_sentences: int = 3) -> str | None:
    if not text:
        return None
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept = [sentence.strip() for sentence in sentences if sentence.strip()][:max_sentences]
    return " ".join(kept) if kept else text.strip()


def _sanitize_summary(text: str | None, max_sentences: int = 3) -> str | None:
    return _limit_sentences(_dedupe_text(text), max_sentences)


def _normalize_links(raw_links: Any, person_insights: list[dict[str, str]]) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()

    candidates = raw_links if isinstance(raw_links, list) else ([raw_links] if raw_links else [])
    for item in candidates:
        if not isinstance(item, str):
            continue
        url = item.strip()
        if url and url not in seen:
            seen.add(url)
            links.append(url)

    for item in person_insights:
        url = (item.get("url") or "").strip()
        if url and url not in seen:
            seen.add(url)
            links.append(url)

    return links[:6]


def _infer_role_from_search(person_insights: list[dict[str, str]]) -> str | None:
    for item in person_insights:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        if " linkedin" in title.lower():
            title = re.sub(r"\s*\|\s*LinkedIn.*$", "", title, flags=re.IGNORECASE).strip()
        lowered = title.lower()
        if " - " in title and " at " in lowered:
            role_part = title.split(" - ", 1)[1]
            return role_part.split(" at ")[0].strip(" -|,")
        if " at " in lowered:
            return title.split(" at ")[0].strip(" -|,")
        if " - " in title:
            return title.split(" - ", 1)[1].strip()
        if len(title.split()) <= 6:
            return title
    return None


def _infer_location_from_search(person_insights: list[dict[str, str]]) -> str | None:
    location_pattern = re.compile(
        r"\b([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+){0,2},\s*[A-Z][a-zA-Z\s\-]{2,})\b"
    )
    for item in person_insights:
        for field in (item.get("snippet") or "", item.get("title") or ""):
            match = location_pattern.search(field)
            if match:
                return match.group(1).strip()
    return None


def _infer_experience_from_search(person_insights: list[dict[str, str]]) -> str | None:
    experience_pattern = re.compile(
        r"(\d+\+?\s*(?:years|year|рок(?:ів|и)?)|senior|lead|head of|director|partner|vp|executive)",
        flags=re.IGNORECASE,
    )
    for item in person_insights:
        snippet = item.get("snippet") or ""
        match = experience_pattern.search(snippet)
        if match:
            return match.group(1).strip()
    return None


def _build_person_summary_fallback(data: dict[str, Any], person_insights: list[dict[str, str]]) -> str | None:
    parts: list[str] = []
    role = data.get("person_role")
    if role:
        parts.append(str(role))
    company = data.get("company")
    if company:
        parts.append(f"у {company}")
    location = data.get("person_location")
    if location:
        parts.append(f"({location})")
    experience = data.get("person_experience")
    if experience:
        parts.append(f"— {experience}")

    if parts:
        return _sanitize_summary(" ".join(parts), max_sentences=2)

    snippet = next((item.get("snippet") for item in person_insights if item.get("snippet")), None)
    return _sanitize_summary(snippet, max_sentences=2)


def _build_company_summary_fallback(
    data: dict[str, Any],
    company_insights: list[dict[str, str]],
) -> str | None:
    snippet = next((item.get("snippet") for item in company_insights if item.get("snippet")), None)
    if snippet:
        return _sanitize_summary(snippet, max_sentences=3)
    company = data.get("company")
    website = data.get("website")
    if company and website:
        return f"{company} — {website}"
    return company


def _finalize_lead_analysis(
    data: dict[str, Any],
    *,
    sender: str,
    company_candidate: str | None,
    person_insights: list[dict[str, str]],
    company_insights: list[dict[str, str]],
) -> dict[str, Any]:
    company = _first_nonempty(data.get("company"), company_candidate)
    website = _normalize_website(_first_nonempty(data.get("website")))

    person_role = _first_nonempty(
        data.get("person_role"),
        _infer_role_from_search(person_insights),
    )
    person_location = _first_nonempty(
        data.get("person_location"),
        _infer_location_from_search(person_insights),
    )
    person_experience = _first_nonempty(
        data.get("person_experience"),
        _infer_experience_from_search(person_insights),
    )

    person_links = _normalize_links(data.get("person_links"), person_insights)

    person_summary = _sanitize_summary(
        _first_nonempty(data.get("person_summary"), _build_person_summary_fallback(data, person_insights)),
        max_sentences=3,
    )
    company_summary = _sanitize_summary(
        _first_nonempty(
            data.get("company_summary"),
            _build_company_summary_fallback(data, company_insights),
        ),
        max_sentences=3,
    )

    full_name = _first_nonempty(data.get("full_name"))
    if not full_name:
        name_parts = [_first_nonempty(data.get("first_name")), _first_nonempty(data.get("last_name"))]
        full_name = " ".join(part for part in name_parts if part) or None

    return {
        "email": _first_nonempty(data.get("email"), sender) or sender,
        "first_name": data.get("first_name"),
        "last_name": data.get("last_name"),
        "full_name": full_name,
        "company": company,
        "company_summary": company_summary,
        "order_number": data.get("order_number"),
        "order_description": data.get("order_description"),
        "amount": data.get("amount"),
        "currency": data.get("currency"),
        "phone_number": data.get("phone_number"),
        "website": website,
        "person_insights": person_insights,
        "person_role": person_role,
        "person_location": person_location,
        "person_experience": person_experience,
        "person_links": person_links,
        "company_insights": company_insights,
        "person_summary": person_summary,
    }


_EXTRACTION_SYSTEM_PROMPT = (
    "You are a B2B lead intelligence assistant. Extract structured facts from inbound sales emails. "
    "Use the sender email domain to infer a company ONLY when it is a corporate domain "
    "(never for gmail.com, outlook.com, yahoo.com, icloud.com, proton.me). "
    "Parse signatures for name, role, phone, company, and location. "
    "Return ONLY valid JSON with keys: "
    "email, first_name, last_name, full_name, company, company_summary, "
    "order_number, order_description, amount, currency, "
    "phone_number, website, person_role, person_location, person_experience, person_links, person_summary. "
    "Use null only when a field is truly absent from the email."
)

_FINAL_SYSTEM_PROMPT = (
    "You are a B2B lead intelligence assistant. Merge extracted email data with enrichment context "
    "into a complete lead profile. "
    "Write person_summary and company_summary in Ukrainian. "
    "Rules:\n"
    "- person_summary: 2-3 concise sentences about WHO the sender is (role, seniority, background, why they wrote). "
    "Do NOT repeat sentences.\n"
    "- company_summary: 2-3 concise sentences about WHAT the company is (industry, offer, scale, relevance). "
    "Do NOT repeat sentences.\n"
    "- person_role: job title; infer from signature, enrichment, or search snippets if missing.\n"
    "- person_location: city/country/region when possible; infer from signature or search if missing.\n"
    "- person_experience: short seniority phrase, e.g. '10+ років у enterprise IT' or 'Senior / Partner level'.\n"
    "- company: canonical company name.\n"
    "- website: normalized https URL when known.\n"
    "- person_links: array of relevant URLs (LinkedIn, company site, profile pages).\n"
    "- Fill every field with the best available evidence. Prefer enrichment over null.\n"
    "Return ONLY valid JSON with the same keys as the extraction step."
)


def _normalize_website(url: str | None) -> str | None:
    if not url:
        return None
    u = url.strip()
    if not u:
        return None
    if u.startswith("http://") or u.startswith("https://"):
        return u
    # Best-effort normalize like "thegradient.com" -> "https://thegradient.com"
    return "https://" + u


def analyze_email(subject: str, body: str, sender: str) -> Dict[str, Any]:
    """Extract and enrich structured lead profile data from an inbound email."""

    company_candidate = _company_candidate_from_sender_email(sender)
    website_candidate = _website_candidate_from_body(body)
    company_for_search: str | None = None
    company_insights_struct: list[dict[str, str]] = []

    if AI_DEBUG:
        sender_domain = sender.split("@", 1)[1] if sender and "@" in sender else None
        print(
            f"[AI] analyze_email model={AI_MODEL} search_enabled={COMPANY_SEARCH_ENABLED} "
            f"sender_domain={sender_domain} company_candidate={company_candidate} website_candidate={website_candidate}"
        )

    user_prompt = (
        "Extract structured lead data from this inbound email.\n\n"
        f"Sender email: {sender}\n"
        f"Sender domain company candidate (may be null): {company_candidate}\n"
        f"Website URL found in body (may be null): {website_candidate}\n"
        f"Subject: {subject}\n\n"
        "Body:\n" + body
    )

    base_response = client.chat.completions.create(
        model=AI_MODEL,
        messages=[
            {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )

    try:
        base_data = json.loads(base_response.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        base_data = {}

    enrichment_parts: list[str] = []
    person_enrichment: list[dict[str, str]] = []
    if COMPANY_SEARCH_ENABLED:
        company_for_search = _first_nonempty(base_data.get("company"), company_candidate)
        website_for_fetch = _normalize_website(
            _first_nonempty(base_data.get("website"), website_candidate)
        )

        if website_for_fetch:
            enrichment_parts.append("[WEBSITE]\n" + fetch_website_tool(website_for_fetch))

        if company_for_search and len(enrichment_parts) < max(COMPANY_SEARCH_MAX_TOOL_CALLS, 0):
            enrichment_parts.append("[DDG_SEARCH]\n" + search_company_tool(company_for_search))
            company_insights_struct = _company_search_struct_cache.get(company_for_search, [])

        person_name = _first_nonempty(base_data.get("full_name"), base_data.get("first_name"))
        if person_name:
            person_enrichment = search_person_insights(person_name, company_for_search)
            if person_enrichment:
                formatted = "\n".join(
                    f"{idx}. {item.get('title', 'Без заголовку')}\n"
                    f"   {item.get('snippet', '')}\n"
                    f"   {item.get('url', '')}"
                    for idx, item in enumerate(person_enrichment, start=1)
                )
                enrichment_parts.append("[PERSON_SEARCH]\n" + formatted)

    enrichment_context = "\n\n".join(enrichment_parts) if enrichment_parts else ""

    final_user_prompt = (
        "Extracted JSON from the email:\n"
        + json.dumps(base_data, ensure_ascii=False)
        + "\n\nEnrichment context (website, company search, person search):\n"
        + (enrichment_context or "<empty>")
        + "\n\nReturn the final complete lead profile JSON."
    )

    final_response = client.chat.completions.create(
        model=AI_MODEL,
        messages=[
            {"role": "system", "content": _FINAL_SYSTEM_PROMPT},
            {"role": "user", "content": final_user_prompt},
        ],
        response_format={"type": "json_object"},
    )

    try:
        data = json.loads(final_response.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        data = {}

    return _finalize_lead_analysis(
        data,
        sender=sender,
        company_candidate=company_candidate,
        person_insights=person_enrichment,
        company_insights=company_insights_struct,
    )
