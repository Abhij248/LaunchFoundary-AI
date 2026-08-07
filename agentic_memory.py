from __future__ import annotations

from typing import Any

from agentic_models import (
    MemoryQuery,
    MemoryRetrievalBundle,
    RetrievedMemory,
    WebsiteAgentState,
)
from learned_memory_store import list_all_memories


# Keyed by behavioral archetype (the same 3 keys infer_behavioral_archetypes()
# always resolves to, via its keyword fallback), not vertical name -- these
# apply to every business that matches the archetype, not just the handful
# of named verticals the old vertical-keyed entries covered. "verticals"
# below is a bonus-match hint for the businesses most commonly associated
# with each archetype, not a requirement: workflow + behavioral_tag +
# evidence_tag overlap alone is enough to surface these for anyone else.
MEMORY_LIBRARY: list[dict[str, Any]] = [
    {
        "memory_id": "fast-impulse-conversion-lane",
        "category": "workflow_pattern",
        "verticals": {"restaurant", "cafe", "bakery"},
        "workflows": {"order"},
        "behavioral_tags": {"fast_impulse_conversion"},
        "evidence_tags": {"menu", "pickup", "delivery", "discount", "combo", "offers", "pricing"},
        "risk_levels": {"standard"},
        "title": "Fast-decision buyers need the shortest path to action, visible immediately",
        "summary": "High-intent impulse buyers convert better when the shortest path to purchase is visible early, top items/offers appear before long storytelling, and browsing a dense catalog stays scannable via grouping rather than a raw list.",
        "applicability": "Best when the business sells priced items visitors browse and buy directly (menu, product catalog, ticket/booking inventory), especially with real offers or a large item count.",
        "recommended_actions": [
            "Expose the primary action (order/buy) in the hero and sticky nav.",
            "Show top-selling or featured items before long brand storytelling.",
            "Turn the strongest real offer into one primary conversion banner tied directly to the action path.",
            "Group a dense catalog into categories/anchors before showing full item detail.",
        ],
        "anti_patterns": [
            "Do not bury the primary action behind About or gallery-first layouts.",
            "Avoid multiple competing offer banners not linked to the action path.",
            "Avoid single-column item walls with no category scaffold.",
        ],
    },
    {
        "memory_id": "high-trust-consideration-lane",
        "category": "trust_pattern",
        "verticals": {"clinic", "consultant", "salon", "tutor"},
        "workflows": {"booking", "lead", "order"},
        "behavioral_tags": {"high_trust_consideration"},
        "evidence_tags": {"hours", "location", "pricing", "offers", "reservations"},
        "risk_levels": {"standard", "regulated"},
        "title": "High-consideration buyers need trust established before commitment friction",
        "summary": "When a decision needs real consideration (a booking, a regulated service, a comparison across venues), visible hours/location, credibility signals, and clear process expectations must arrive before the form or checkout, not after.",
        "applicability": "Useful whenever users compare options, need reassurance, or face a real commitment (booking, regulated service, family/group decision) rather than an instant purchase.",
        "recommended_actions": [
            "Place hours, location, and booking/process expectations near the hero.",
            "Lead with credibility and proof signals before the booking or contact form.",
            "Explain response times or what happens next after a submission.",
            "Make pricing legible early when it materially affects the decision.",
        ],
        "anti_patterns": [
            "Do not open with an aggressive form before explaining the service.",
            "Do not rely on background imagery as the primary trust signal.",
            "Avoid hiding operational facts below the fold.",
        ],
    },
    {
        "memory_id": "urgent-service-decision-lane",
        "category": "workflow_pattern",
        "verticals": {"repair_service"},
        "workflows": {"lead"},
        "behavioral_tags": {"urgent_service_decision"},
        "evidence_tags": {"hours", "location", "pricing"},
        "risk_levels": {"standard"},
        "title": "Urgent-need buyers need a fast contact path, not a lengthy pitch",
        "summary": "When the visitor already knows they need help now (a breakdown, an emergency, a same-day need), speed and certainty of contact matter more than persuasion -- a visible phone number, clear service area, and fast quote/contact path win over long explanatory copy.",
        "applicability": "Best for on-demand or emergency-flavored services where the visitor arrives already needing help, not browsing options.",
        "recommended_actions": [
            "Make the phone number prominent and clickable, not buried in a footer.",
            "State response time or availability expectations plainly.",
            "Show service area/coverage clearly so visitors know they qualify.",
            "Keep the quote/contact form short -- every extra field risks losing an urgent visitor.",
        ],
        "anti_patterns": [
            "Do not hide the phone number behind a contact form only.",
            "Avoid long service explanations before the contact path.",
            "Do not leave service area or coverage unclear.",
        ],
    },
]


def build_memory_query(
    state: WebsiteAgentState,
) -> MemoryQuery:
    vertical = (
        state.business_profile.vertical
        if state.business_profile
        else "unknown"
    )
    subtype = (
        state.business_profile.subtype
        if state.business_profile
        else "general"
    )
    risk_level = (
        state.business_profile.risk_level.value
        if state.business_profile
        else "standard"
    )
    primary_workflow = (
        state.business_identity.primary_workflow.value
        if state.business_identity
        else "lead"
    )
    behavioral_archetypes = list(
        state.business_identity.behavioral_archetypes
        if state.business_identity
        else []
    )
    evidence_tags = sorted(
        infer_evidence_tags(state)
    )
    retrieval_goal = (
        state.business_input.get(
            "goal",
            "",
        )
        or (
            state.business_profile.goal
            if state.business_profile
            else ""
        )
    )
    return MemoryQuery(
        vertical=vertical,
        subtype=subtype,
        risk_level=risk_level,
        primary_workflow=primary_workflow,
        behavioral_archetypes=behavioral_archetypes,
        evidence_tags=evidence_tags,
        retrieval_goal=str(
            retrieval_goal
        ),
    )


def retrieve_memory_bundle(
    state: WebsiteAgentState,
) -> MemoryRetrievalBundle:
    query = build_memory_query(
        state
    )
    scored_memories: list[RetrievedMemory] = []
    # MEMORY_LIBRARY is a static, hand-written seed; list_all_memories()
    # is the real, accumulating record of what critique/simulation/
    # reflection actually found wrong and what owners actually asked to
    # fix, so retrieval draws from both instead of only the fixed 5 cards.
    for item in MEMORY_LIBRARY + list_all_memories():
        score = score_memory_item(
            item,
            query,
        )
        if score < 0.35:
            continue
        scored_memories.append(
            RetrievedMemory(
                memory_id=item["memory_id"],
                category=item["category"],
                title=item["title"],
                summary=item["summary"],
                applicability=item.get(
                    "applicability",
                    "",
                ),
                recommended_actions=list(
                    item.get(
                        "recommended_actions",
                        [],
                    )
                )[:4],
                anti_patterns=list(
                    item.get(
                        "anti_patterns",
                        [],
                    )
                )[:3],
                evidence_tags=sorted(
                    set(
                        item.get(
                            "evidence_tags",
                            set(),
                        )
                    )
                ),
                relevance=round(
                    min(score, 0.95),
                    2,
                ),
            )
        )
    scored_memories.sort(
        key=lambda memory: memory.relevance,
        reverse=True,
    )
    notes: list[str] = []
    if not scored_memories:
        notes.append(
            "No strong local memory matches were found. Continue with direct evidence and rulebooks."
        )
    elif any(
        memory.category == "offer_pattern"
        for memory in scored_memories
    ):
        notes.append(
            "Offer-heavy asset evidence matched conversion memory patterns."
        )
    retrieval_confidence = round(
        min(
            sum(
                memory.relevance
                for memory in scored_memories[:3]
            )
            / max(
                len(
                    scored_memories[:3]
                ),
                1,
            ),
            0.95,
        ),
        2,
    ) if scored_memories else 0.0
    return MemoryRetrievalBundle(
        query=query,
        memories=scored_memories[:4],
        retrieval_confidence=retrieval_confidence,
        notes=notes,
    )


def infer_evidence_tags(
    state: WebsiteAgentState,
) -> set[str]:
    text_parts: list[str] = []
    for key in [
        "name",
        "goal",
        "details",
        "location",
        "unique_selling_points",
    ]:
        value = state.business_input.get(
            key,
            "",
        )
        text_parts.append(
            str(value).lower()
        )
    for extraction in (
        state.asset_extractions or []
    )[:4]:
        text_parts.extend(
            value.lower()
            for value in extraction.business_signals[:6]
        )
        info = extraction.extracted_business_info
        text_parts.extend(
            value.lower()
            for value in info.offers[:4]
        )
        text_parts.extend(
            value.lower()
            for value in info.services_or_items[:8]
        )
    text = " ".join(text_parts)
    tags: set[str] = set()
    keyword_map = {
        "menu": ["menu", "pizza", "pasta", "dessert", "burger", "coffee"],
        "pickup": ["pickup", "takeaway", "take away"],
        "delivery": ["delivery", "deliver"],
        "discount": ["discount", "off", "%", "deal"],
        "combo": ["combo", "bundle", "pack"],
        "offers": ["offer", "deal", "special"],
        "pricing": ["rupee", "rs", "price", "$", "cost"],
        "reservations": ["reservation", "reserve", "table"],
        "hours": ["hours", "11am", "10pm", "open"],
        "location": ["location", "address", "san francisco"],
    }
    for tag, keywords in keyword_map.items():
        if any(
            keyword in text
            for keyword in keywords
        ):
            tags.add(tag)
    # A populated business_hours field is itself real evidence of "hours"
    # information, regardless of whether its exact wording (e.g. "9am-9pm")
    # happens to contain one of the keyword_map's literal substrings.
    if str(state.business_input.get("business_hours", "")).strip():
        tags.add("hours")
    return tags


def score_memory_item(
    item: dict[str, Any],
    query: MemoryQuery,
) -> float:
    score = 0.0
    if query.vertical in item.get(
        "verticals",
        set(),
    ):
        score += 0.35
    if query.primary_workflow in item.get(
        "workflows",
        set(),
    ):
        score += 0.2
    if query.risk_level in item.get(
        "risk_levels",
        set(),
    ):
        score += 0.1
    behavioral_overlap = len(
        set(
            query.behavioral_archetypes
        )
        & set(
            item.get(
                "behavioral_tags",
                set(),
            )
        )
    )
    score += min(
        behavioral_overlap * 0.1,
        0.2,
    )
    evidence_overlap = len(
        set(
            query.evidence_tags
        )
        & set(
            item.get(
                "evidence_tags",
                set(),
            )
        )
    )
    score += min(
        evidence_overlap * 0.05,
        0.15,
    )
    if query.retrieval_goal and any(
        keyword in query.retrieval_goal.lower()
        for keyword in [
            "order",
            "reservation",
            "booking",
        ]
    ):
        score += 0.05
    return score
