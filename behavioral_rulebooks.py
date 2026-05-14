from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class BehavioralArchetype:
    key: str

    trust_requirement: str
    urgency_level: str
    conversion_latency: str
    visual_dependency: str
    operational_complexity: str

    preferred_cta_style: List[str] = field(default_factory=list)
    trust_signals: List[str] = field(default_factory=list)
    preferred_sections: List[str] = field(default_factory=list)
    conversion_risks: List[str] = field(default_factory=list)


BEHAVIORAL_ARCHETYPES = {

    "fast_impulse_conversion": BehavioralArchetype(
        key="fast_impulse_conversion",

        trust_requirement="medium",
        urgency_level="medium",
        conversion_latency="short",
        visual_dependency="high",
        operational_complexity="low",

        preferred_cta_style=[
            "immediate_action",
            "single_primary_cta",
            "visible_pricing",
        ],

        trust_signals=[
            "reviews",
            "popular_items",
            "clear_prices",
        ],

        preferred_sections=[
            "hero_offer_banner",
            "menu_showcase",
            "quick_checkout",
        ],

        conversion_risks=[
            "hidden_prices",
            "too_much_text",
            "cta_delay",
        ],
    ),

    "high_trust_consideration": BehavioralArchetype(
        key="high_trust_consideration",

        trust_requirement="high",
        urgency_level="low",
        conversion_latency="long",
        visual_dependency="medium",
        operational_complexity="medium",

        preferred_cta_style=[
            "soft_conversion",
            "consultation_first",
            "trust_before_action",
        ],

        trust_signals=[
            "credentials",
            "privacy_notice",
            "testimonials",
            "experience",
        ],

        preferred_sections=[
            "hero_trust_banner",
            "credential_band",
            "proof_band",
        ],

        conversion_risks=[
            "aggressive_cta",
            "missing_credentials",
            "weak_reassurance",
        ],
    ),

    "urgent_service_decision": BehavioralArchetype(
        key="urgent_service_decision",

        trust_requirement="medium",
        urgency_level="high",
        conversion_latency="short",
        visual_dependency="low",
        operational_complexity="medium",

        preferred_cta_style=[
            "fast_contact",
            "phone_first",
            "quote_request",
        ],

        trust_signals=[
            "response_speed",
            "availability",
            "service_areas",
        ],

        preferred_sections=[
            "hero_trust_banner",
            "service_cards",
            "contact_strip",
        ],

        conversion_risks=[
            "hard_to_contact",
            "slow_forms",
            "unclear_service_area",
        ],
    ),
}