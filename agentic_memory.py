from __future__ import annotations

from typing import Any

from agentic_models import (
    MemoryQuery,
    MemoryRetrievalBundle,
    RetrievedMemory,
    WebsiteAgentState,
)


MEMORY_LIBRARY: list[dict[str, Any]] = [
    {
        "memory_id": "restaurant-fast-order-lane",
        "category": "workflow_pattern",
        "verticals": {"restaurant", "cafe", "bakery"},
        "workflows": {"order"},
        "behavioral_tags": {"fast_impulse_conversion", "high_intent_repeat_ordering"},
        "evidence_tags": {"menu", "pickup", "delivery", "combos"},
        "risk_levels": {"standard"},
        "title": "Fast order lane wins repeat and high-intent demand",
        "summary": "High-intent food buyers convert better when the shortest ordering path is visible early and category browsing stays lightweight.",
        "applicability": "Best when the business already has menu density, pickup intent, or repeat ordering behavior.",
        "recommended_actions": [
            "Expose order CTA in the hero and sticky nav.",
            "Show top-selling categories before long brand storytelling.",
            "Keep cart entry visible across menu-heavy pages.",
        ],
        "anti_patterns": [
            "Do not bury ordering behind About or gallery-first layouts.",
            "Avoid long introductory copy before showing menu structure.",
        ],
    },
    {
        "memory_id": "restaurant-trust-before-order",
        "category": "trust_pattern",
        "verticals": {"restaurant", "cafe", "bakery"},
        "workflows": {"order", "booking"},
        "behavioral_tags": {"high_trust_consideration", "family_group_decision"},
        "evidence_tags": {"hours", "location", "pricing", "offers"},
        "risk_levels": {"standard"},
        "title": "Trust cues should arrive before decision friction spikes",
        "summary": "For diners comparing options, visible hours, location, price anchoring, and proof bands reduce hesitation before menu commitment.",
        "applicability": "Useful when users may compare across venues, make family decisions, or need assurance before ordering or reserving.",
        "recommended_actions": [
            "Place hours, location, and reservation/order expectations near the hero.",
            "Use proof bands and concise trust signals before deep menu scrolling.",
            "Make pricing legible early when combos or offers matter.",
        ],
        "anti_patterns": [
            "Do not rely on background imagery as the primary trust signal.",
            "Avoid hiding operational facts below the fold.",
        ],
    },
    {
        "memory_id": "restaurant-offer-anchoring",
        "category": "offer_pattern",
        "verticals": {"restaurant", "cafe", "bakery"},
        "workflows": {"order"},
        "behavioral_tags": {"fast_impulse_conversion", "deal_seeking"},
        "evidence_tags": {"discount", "combo", "offers", "pricing"},
        "risk_levels": {"standard"},
        "title": "Offers work best when anchored to a clear primary action",
        "summary": "Discounts and combos help only when they point directly into the ordering path instead of becoming decorative noise.",
        "applicability": "Use when uploaded flyers or menu assets show explicit combos, bundles, or discount language.",
        "recommended_actions": [
            "Turn the strongest offer into one primary conversion banner.",
            "Tie offers to category entry or preset cart paths.",
            "Summarize bundle logic in one line instead of listing OCR-heavy details.",
        ],
        "anti_patterns": [
            "Do not surface every extracted offer verbatim in the hero.",
            "Avoid multiple competing discount banners in the same viewport.",
        ],
    },
    {
        "memory_id": "booking-assurance-lane",
        "category": "workflow_pattern",
        "verticals": {"clinic", "salon", "consultant", "tutor"},
        "workflows": {"booking", "lead"},
        "behavioral_tags": {"high_trust_consideration"},
        "evidence_tags": {"hours", "address", "phone"},
        "risk_levels": {"regulated", "standard"},
        "title": "Booking workflows need assurance before commitment",
        "summary": "Service businesses convert better when provider credibility and booking expectations are established before form friction.",
        "applicability": "Useful for booked services where users need trust, availability, and process clarity first.",
        "recommended_actions": [
            "Lead with trust proof and process clarity before the booking form.",
            "Explain response times, appointment flow, or what happens next.",
            "Use the booking CTA after credibility and logistics appear.",
        ],
        "anti_patterns": [
            "Do not open with an aggressive form before explaining the service.",
        ],
    },
    {
        "memory_id": "menu-density-scannability",
        "category": "vertical_pattern",
        "verticals": {"restaurant", "cafe", "bakery"},
        "workflows": {"order"},
        "behavioral_tags": {"exploratory_browser", "family_group_decision"},
        "evidence_tags": {"menu", "pricing"},
        "risk_levels": {"standard"},
        "title": "Dense menus need scannable grouping before detail",
        "summary": "Users handle large food menus better when categories and anchors appear before long lists of individual items.",
        "applicability": "Best when asset extraction reveals many menu items or pricing rows.",
        "recommended_actions": [
            "Use category strips and grouped sections before full item detail.",
            "Highlight signature or popular items instead of dumping everything at once.",
            "Keep the first viewport focused on action plus menu orientation.",
        ],
        "anti_patterns": [
            "Do not paste raw OCR item strings into the hero or badges.",
            "Avoid single-column item walls with no category scaffold.",
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
    for item in MEMORY_LIBRARY:
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
