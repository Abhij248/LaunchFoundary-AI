from __future__ import annotations

from behavioral_rulebooks import (
    BEHAVIORAL_ARCHETYPES,
)

from agentic_models import (
    BehavioralContext,
)

def build_behavioral_contexts(
    archetype_keys: list[str],
) -> list[BehavioralContext]:

    contexts = []

    for key in archetype_keys:

        archetype = (
            BEHAVIORAL_ARCHETYPES.get(
                key
            )
        )

        if not archetype:
            continue

        contexts.append(
            BehavioralContext(
                key=archetype.key,

                trust_requirement=(
                    archetype.trust_requirement
                ),

                urgency_level=(
                    archetype.urgency_level
                ),

                conversion_latency=(
                    archetype.conversion_latency
                ),

                visual_dependency=(
                    archetype.visual_dependency
                ),

                operational_complexity=(
                    archetype.operational_complexity
                ),

                preferred_cta_style=(
                    archetype.preferred_cta_style
                ),

                trust_signals=(
                    archetype.trust_signals
                ),

                preferred_sections=(
                    archetype.preferred_sections
                ),

                conversion_risks=(
                    archetype.conversion_risks
                ),
            )
        )

    return contexts


def infer_behavioral_archetypes(
    business_input: str,
    vertical: str,
) -> list[str]:

    text = business_input.lower()

    archetypes = []

    # Restaurant / food ordering behaviour
    if vertical in [
        "restaurant",
        "cafe",
        "bakery",
    ]:
        archetypes.extend([
            "fast_impulse_conversion",
        ])

    # Clinic / trust-driven behaviour
    if vertical in [
        "clinic",
        "consultant",
    ]:
        archetypes.extend([
            "high_trust_consideration",
        ])

    # Urgent local service behaviour
    if vertical in [
        "repair_service",
    ]:
        archetypes.extend([
            "urgent_service_decision",
        ])

    # Additional semantic detection

    if any(
        word in text
        for word in [
            "emergency",
            "urgent",
            "same day",
            "immediate",
        ]
    ):
        if "urgent_service_decision" not in archetypes:
            archetypes.append(
                "urgent_service_decision"
            )

    return archetypes