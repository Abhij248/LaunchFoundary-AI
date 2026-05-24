from __future__ import annotations

import html
import os
import re
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx


SEARCH_TIMEOUT_SECONDS = 4.0
FETCH_TIMEOUT_SECONDS = 4.0
MAX_SEARCH_RESULTS = 4
MAX_FETCHED_PAGES = 2


def market_research_tool(
    state: Any,
) -> dict[str, Any]:
    cached = get_cached_tool(
        state,
        "market_research",
    )
    if cached:
        return cached

    profile = getattr(
        state,
        "business_profile",
        None,
    )
    business_input = getattr(
        state,
        "business_input",
        {},
    ) or {}
    vertical = enum_value(
        getattr(
            profile,
            "vertical",
            None,
        ),
        business_input.get(
            "vertical",
            "business",
        ),
    )
    location = str(
        getattr(
            profile,
            "location",
            "",
        )
        or business_input.get(
            "location",
            "",
        )
    ).strip()
    name = str(
        getattr(
            profile,
            "name",
            "",
        )
        or business_input.get(
            "name",
            "",
        )
    ).strip()
    query = " ".join(
        part
        for part in [
            location,
            vertical,
            "competitors services pricing website",
        ]
        if part
    )

    result: dict[str, Any] = {
        "status": "skipped",
        "query": query,
        "business_name": name,
        "search_results": [],
        "evidence": [],
        "errors": [],
    }

    if not live_tools_enabled():
        result["errors"].append(
            "Live web tools disabled by ENABLE_LIVE_WEB_TOOLS."
        )
        return cache_tool(
            state,
            "market_research",
            result,
        )

    if not query.strip():
        result["errors"].append(
            "Insufficient business context for market search."
        )
        return cache_tool(
            state,
            "market_research",
            result,
        )

    try:
        search_results = search_duckduckgo(
            query
        )
        result["status"] = "success" if search_results else "empty"
        result["search_results"] = search_results[:MAX_SEARCH_RESULTS]
        result["evidence"] = [
            compact_result_evidence(
                item
            )
            for item in result["search_results"]
        ][:MAX_SEARCH_RESULTS]
    except Exception as exc:
        result["status"] = "unavailable"
        result["errors"].append(
            str(exc)
        )

    return cache_tool(
        state,
        "market_research",
        result,
    )


def page_reader_tool(
    state: Any,
) -> dict[str, Any]:
    cached = get_cached_tool(
        state,
        "page_reader",
    )
    if cached:
        return cached

    urls = collect_candidate_urls(
        state
    )
    if not urls:
        market = market_research_tool(
            state
        )
        urls = [
            item.get(
                "url",
                "",
            )
            for item in market.get(
                "search_results",
                [],
            )
        ]

    result: dict[str, Any] = {
        "status": "skipped",
        "pages": [],
        "errors": [],
    }

    if not live_tools_enabled():
        result["errors"].append(
            "Live page reader disabled by ENABLE_LIVE_WEB_TOOLS."
        )
        return cache_tool(
            state,
            "page_reader",
            result,
        )

    for url in dedupe(
        urls
    )[:MAX_FETCHED_PAGES]:
        if not is_fetchable_url(
            url
        ):
            continue
        try:
            page = fetch_page_summary(
                url
            )
            if page:
                result["pages"].append(
                    page
                )
        except Exception as exc:
            result["errors"].append(
                f"{url}: {exc}"
            )

    result["status"] = (
        "success"
        if result["pages"]
        else "empty"
    )
    return cache_tool(
        state,
        "page_reader",
        result,
    )


def design_quality_tool(
    state: Any,
) -> dict[str, Any]:
    candidates = list(
        getattr(
            state,
            "design_candidates",
            [],
        )
        or []
    )
    design_spec = getattr(
        state,
        "design_spec",
        None,
    )
    asset_count = len(
        getattr(
            state,
            "asset_extractions",
            [],
        )
        or []
    )
    requirements = getattr(
        state,
        "requirements_spec",
        None,
    )
    required_workflows = [
        enum_value(
            workflow,
            "",
        )
        for workflow in (
            getattr(
                requirements,
                "required_workflows",
                [],
            )
            or []
        )
    ]

    issues: list[str] = []
    checks: list[str] = []
    candidate_count = len(
        candidates
    )
    if candidate_count < 2 and not design_spec:
        issues.append(
            "Fewer than two candidate directions."
        )
    else:
        checks.append(
            "Candidate alternatives exist."
        )

    candidate_payloads = [
        candidate_to_dict(
            candidate
        )
        for candidate in candidates[:3]
    ]
    action_labels = [
        str(
            payload.get(
                "primary_action",
                {},
            ).get(
                "label",
                "",
            )
        )
        for payload in candidate_payloads
    ]
    if not any(
        label.strip()
        for label in action_labels
    ):
        issues.append(
            "Primary CTA is missing or unclear."
        )
    else:
        checks.append(
            "Primary CTA is available."
        )

    section_types = [
        section_type
        for payload in candidate_payloads
        for page in payload.get(
            "pages",
            [],
        )
        for section_type in page.get(
            "section_types",
            [],
        )
    ]
    if required_workflows and not workflow_sections_present(
        required_workflows,
        section_types,
    ):
        issues.append(
            "Required workflow is weakly represented in sections."
        )
    else:
        checks.append(
            "Workflow sections match requirements."
        )

    if asset_count and not any_asset_section(
        section_types
    ):
        issues.append(
            "Uploaded asset evidence is not driving visible sections."
        )
    elif asset_count:
        checks.append(
            "Uploaded assets influence section planning."
        )

    if not has_trust_section(
        section_types
    ):
        issues.append(
            "Trust proof or operational assurance is thin."
        )
    else:
        checks.append(
            "Trust cues are represented."
        )

    profile = getattr(
        state,
        "business_profile",
        None,
    )
    vertical = enum_value(
        getattr(
            profile,
            "vertical",
            None,
        ),
        "",
    )
    if vertical in {
        "restaurant",
        "cafe",
        "bakery",
        "food",
        "pizzeria",
    } and not any(
        section in section_types
        for section in [
            "menu_showcase",
            "featured_menu_grid",
            "menu_grid",
        ]
    ):
        issues.append(
            "Food business needs a visual menu section."
        )

    if not any(
        section in section_types
        for section in [
            "hero_offer_banner",
            "hero_trust_banner",
            "immersive_hero",
            "hero",
        ]
    ):
        issues.append(
            "Hero section lacks a clear visual lead."
        )

    score = max(
        1,
        min(
            10,
            10 - len(
                issues
            ) * 2,
        ),
    )
    return {
        "score": score,
        "checks_passed": checks[:5],
        "issues": issues[:5],
        "recommendations": [
            recommendation_for_issue(
                issue
            )
            for issue in issues[:5]
        ],
        "visual_guidance": visual_guidance_for_vertical(
            vertical,
            asset_count,
        ),
    }


def search_duckduckgo(
    query: str,
) -> list[dict[str, str]]:
    url = (
        "https://duckduckgo.com/html/?q="
        + quote_plus(
            query
        )
    )
    with httpx.Client(
        follow_redirects=True,
        timeout=SEARCH_TIMEOUT_SECONDS,
        headers={
            "User-Agent": "Mozilla/5.0 LaunchFoundryAgent/1.0",
        },
    ) as client:
        response = client.get(
            url
        )
        response.raise_for_status()
    return parse_duckduckgo_results(
        response.text
    )


def parse_duckduckgo_results(
    text: str,
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    snippets = re.findall(
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>|<div[^>]+class="result__snippet"[^>]*>(.*?)</div>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    clean_snippets = [
        clean_html(
            left or right
        )
        for left, right in snippets
    ]
    for index, match in enumerate(
        pattern.finditer(
            text
        )
    ):
        raw_url, raw_title = match.groups()
        url = normalize_search_url(
            html.unescape(
                raw_url
            )
        )
        if not is_fetchable_url(
            url
        ):
            continue
        results.append(
            {
                "title": clean_html(
                    raw_title
                )[:90],
                "url": url,
                "snippet": (
                    clean_snippets[index]
                    if index < len(
                        clean_snippets
                    )
                    else ""
                )[:180],
            }
        )
        if len(results) >= MAX_SEARCH_RESULTS:
            break
    return results


def fetch_page_summary(
    url: str,
) -> dict[str, Any]:
    with httpx.Client(
        follow_redirects=True,
        timeout=FETCH_TIMEOUT_SECONDS,
        headers={
            "User-Agent": "Mozilla/5.0 LaunchFoundryAgent/1.0",
        },
    ) as client:
        response = client.get(
            url
        )
        response.raise_for_status()
    text = clean_html(
        response.text
    )
    return {
        "url": url,
        "title": extract_title(
            response.text
        ),
        "signals": extract_page_signals(
            text
        ),
        "summary": text[:600],
    }


def extract_page_signals(
    text: str,
) -> list[str]:
    lowered = text.lower()
    signal_map = {
        "pricing": ["price", "pricing", "$", "rs.", "₹"],
        "booking": ["book", "reservation", "appointment"],
        "ordering": ["order", "delivery", "pickup", "cart"],
        "trust": ["review", "rating", "testimonial", "licensed"],
        "offers": ["offer", "discount", "combo", "deal"],
    }
    signals = []
    for label, needles in signal_map.items():
        if any(
            needle in lowered
            for needle in needles
        ):
            signals.append(
                label
            )
    return signals


def collect_candidate_urls(
    state: Any,
) -> list[str]:
    business_input = getattr(
        state,
        "business_input",
        {},
    ) or {}
    values: list[str] = []
    for key in [
        "website",
        "website_url",
        "competitor_url",
        "competitor_urls",
    ]:
        value = business_input.get(
            key
        )
        if isinstance(
            value,
            list,
        ):
            values.extend(
                str(item)
                for item in value
            )
        elif value:
            values.append(
                str(value)
            )
    details = str(
        business_input.get(
            "details",
            "",
        )
    )
    values.extend(
        re.findall(
            r"https?://[^\s,)]+",
            details,
        )
    )
    return values


def candidate_to_dict(
    candidate: Any,
) -> dict[str, Any]:
    if hasattr(
        candidate,
        "model_dump",
    ):
        data = candidate.model_dump()
    elif isinstance(
        candidate,
        dict,
    ):
        data = candidate
    else:
        return {}

    pages = []
    for page in data.get(
        "pages",
        [],
    ):
        sections = page.get(
            "sections",
            [],
        )
        pages.append(
            {
                "type": enum_value(
                    page.get(
                        "type",
                        page.get(
                            "page_type",
                            "",
                        ),
                    ),
                    "",
                ),
                "section_types": [
                    enum_value(
                        section.get(
                            "type",
                            "",
                        ),
                        "",
                    )
                    for section in sections
                    if isinstance(
                        section,
                        dict,
                    )
                ],
            }
        )
    data["pages"] = pages
    return data


def workflow_sections_present(
    workflows: list[str],
    section_types: list[str],
) -> bool:
    joined = " ".join(
        section_types
    ).lower()
    for workflow in workflows:
        if workflow in {"order", "ordering"} and any(
            word in joined
            for word in ["order", "menu", "cart"]
        ):
            return True
        if workflow in {"booking", "reservation"} and any(
            word in joined
            for word in ["booking", "reservation", "appointment"]
        ):
            return True
        if workflow == "lead" and any(
            word in joined
            for word in ["lead", "contact", "cta"]
        ):
            return True
    return not workflows


def any_asset_section(
    section_types: list[str],
) -> bool:
    joined = " ".join(
        section_types
    ).lower()
    return any(
        word in joined
        for word in ["menu", "gallery", "offer", "product", "media"]
    )


def has_trust_section(
    section_types: list[str],
) -> bool:
    joined = " ".join(
        section_types
    ).lower()
    return any(
        word in joined
        for word in ["testimonial", "trust", "proof", "hours", "location", "faq"]
    )


def recommendation_for_issue(
    issue: str,
) -> str:
    if "CTA" in issue:
        return "Add one explicit primary action above the fold."
    if "workflow" in issue:
        return "Add a section dedicated to the required workflow."
    if "asset" in issue:
        return "Use uploaded menu, offer, or gallery evidence visibly."
    if "Trust" in issue:
        return "Add proof, hours, location, reviews, or process clarity."
    if "Food business" in issue:
        return "Use menu cards with item names, prices, and add actions."
    if "Hero" in issue:
        return "Lead with a distinct hero, image, CTA, and trust cue."
    return "Tighten structure around the business goal."


def visual_guidance_for_vertical(
    vertical: str,
    asset_count: int,
) -> list[str]:
    if vertical in {
        "restaurant",
        "cafe",
        "bakery",
        "food",
        "pizzeria",
    }:
        guidance = [
            "Use a food-led hero with menu/category scanning.",
            "Show prices and add actions directly on menu cards.",
            "Keep cart or order state visible near the menu.",
            "Surface hours, location, and reservation path as trust cues.",
        ]
        if asset_count:
            guidance.insert(
                0,
                "Use uploaded menu/food imagery as primary visual evidence.",
            )
        return guidance
    if vertical in {"clinic", "healthcare", "dental"}:
        return [
            "Use calm spacing, trust proof, and appointment-first hierarchy.",
            "Show services, hours, location, and privacy reassurance.",
            "Avoid aggressive sales styling for clinical pages.",
        ]
    return [
        "Use a clear hero, service cards, trust proof, and one action path.",
        "Avoid generic feature grids without customer benefit copy.",
        "Make the primary workflow visibly reachable from every major section.",
    ]


def normalize_search_url(
    url: str,
) -> str:
    parsed = urlparse(
        url
    )
    if "duckduckgo.com" in parsed.netloc and parsed.query:
        target = parse_qs(
            parsed.query
        ).get(
            "uddg",
            [],
        )
        if target:
            return unquote(
                target[0]
            )
    return url


def is_fetchable_url(
    url: str,
) -> bool:
    try:
        parsed = urlparse(
            url
        )
        if parsed.scheme not in {"http", "https"}:
            return False
        host = (
            parsed.hostname
            or ""
        ).lower()
        if host in {"localhost", "127.0.0.1", "0.0.0.0"}:
            return False
        if host.startswith(
            "10."
        ) or host.startswith(
            "192.168."
        ):
            return False
        if re.match(
            r"172\.(1[6-9]|2\d|3[0-1])\.",
            host,
        ):
            return False
        return bool(
            host
        )
    except Exception:
        return False


def clean_html(
    text: str,
) -> str:
    text = re.sub(
        r"(?is)<script.*?</script>|<style.*?</style>",
        " ",
        text,
    )
    text = re.sub(
        r"(?s)<[^>]+>",
        " ",
        text,
    )
    text = html.unescape(
        text
    )
    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def extract_title(
    text: str,
) -> str:
    match = re.search(
        r"(?is)<title[^>]*>(.*?)</title>",
        text,
    )
    return clean_html(
        match.group(1)
        if match
        else ""
    )[:120]


def compact_result_evidence(
    item: dict[str, str],
) -> str:
    title = item.get(
        "title",
        "",
    )
    snippet = item.get(
        "snippet",
        "",
    )
    return " - ".join(
        part
        for part in [title, snippet]
        if part
    )[:220]


def live_tools_enabled() -> bool:
    value = os.getenv(
        "ENABLE_LIVE_WEB_TOOLS",
        "1",
    ).strip().lower()
    return value not in {
        "0",
        "false",
        "no",
        "off",
    }


def enum_value(
    value: Any,
    fallback: str,
) -> str:
    return str(
        getattr(
            value,
            "value",
            value,
        )
        or fallback
    )


def get_cached_tool(
    state: Any,
    key: str,
) -> dict[str, Any]:
    cache = getattr(
        state,
        "tool_cache",
        {},
    )
    value = cache.get(
        key,
        {},
    )
    return value if isinstance(value, dict) else {}


def cache_tool(
    state: Any,
    key: str,
    value: dict[str, Any],
) -> dict[str, Any]:
    cache = getattr(
        state,
        "tool_cache",
        None,
    )
    if isinstance(
        cache,
        dict,
    ):
        cache[key] = value
    return value


def dedupe(
    values: list[str],
) -> list[str]:
    seen = set()
    result = []
    for value in values:
        normalized = str(
            value
        ).strip()
        lowered = normalized.lower()
        if not normalized or lowered in seen:
            continue
        seen.add(
            lowered
        )
        result.append(
            normalized
        )
    return result
