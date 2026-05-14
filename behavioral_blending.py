from __future__ import annotations

from agentic_models import (
    BehavioralBlend,
    BehavioralArchetypeWeight,
)


ARCHETYPE_PRIORITIES = {
    "urgent_service_decision": 0.9,
    "high_trust_consideration": 0.82,
    "fast_impulse_conversion": 0.7,
}


CONFLICT_MATRIX = {

    (
        "urgent_service_decision",
        "high_trust_consideration",
    ): {
        "synthesis_mode":
            "urgency_with_reassurance",

        "conflict":
            (
                "Urgency pushes rapid CTA "
                "while trust consideration "
                "requires reassurance before action."
            ),
    },

    (
        "fast_impulse_conversion",
        "high_trust_consideration",
    ): {
        "synthesis_mode":
            "trust_accelerated_conversion",

        "conflict":
            (
                "Impulse conversion minimizes "
                "friction while trust-driven "
                "users require validation."
            ),
    },
}


def build_behavioral_blend(
    archetypes: list[str],
) -> BehavioralBlend:

    unique = list(
        dict.fromkeys(archetypes)
    )

    if not unique:
        return BehavioralBlend(
            dominant_archetype="unknown",
        )

    ranked = sorted(
        unique,
        key=lambda item:
        ARCHETYPE_PRIORITIES.get(
            item,
            0.5,
        ),
        reverse=True,
    )

    dominant = ranked[0]

    total = sum(
        ARCHETYPE_PRIORITIES.get(
            item,
            0.5,
        )
        for item in ranked
    )

    weights = []

    for index, item in enumerate(
        ranked,
        start=1,
    ):

        raw = ARCHETYPE_PRIORITIES.get(
            item,
            0.5,
        )

        weights.append(
            BehavioralArchetypeWeight(
                archetype=item,
                weight=round(raw / total, 2),
                dominance_rank=index,
            )
        )

    synthesis_mode = "single_mode"

    conflict_notes = []

    for pair, config in (
        CONFLICT_MATRIX.items()
    ):

        if all(
            item in ranked
            for item in pair
        ):

            synthesis_mode = config[
                "synthesis_mode"
            ]

            conflict_notes.append(
                config["conflict"]
            )

    return BehavioralBlend(
        dominant_archetype=dominant,

        secondary_archetypes=ranked[1:],

        weights=weights,

        synthesis_mode=synthesis_mode,

        conflict_notes=conflict_notes,
    )