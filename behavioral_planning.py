from __future__ import annotations
from behavioral_rulebooks import BEHAVIORAL_ARCHETYPES




from typing import Any


def derive_visual_system_from_archetypes(
    archetypes: list[str],
) -> dict[str, Any]:

    if "fast_impulse_conversion" in archetypes:
        return {
            "tone": "energetic",
            "density": "high",
            "media_bias": "image_heavy",
            "trust_emphasis": "medium",
        }

    if "high_trust_consideration" in archetypes:
        return {
            "tone": "trustworthy",
            "density": "medium",
            "media_bias": "trust_first",
            "trust_emphasis": "high",
        }

    if "urgent_service_decision" in archetypes:
        return {
            "tone": "practical",
            "density": "medium",
            "media_bias": "copy_first",
            "trust_emphasis": "medium",
        }

    return {
        "tone": "modern",
        "density": "medium",
        "media_bias": "balanced",
        "trust_emphasis": "medium",
    }


def derive_primary_action_from_archetypes(
    archetypes: list[str],
    workflow_kind: str,
) -> dict[str, Any]:

    if "fast_impulse_conversion" in archetypes:
        label = (
            "Order Now"
            if workflow_kind == "order"
            else "Start Now"
        )

        return {
            "label": label,
            "kind": workflow_kind,
            "placements": [
                "hero",
                "menu_card",
                "sticky",
            ],
        }

    if "high_trust_consideration" in archetypes:
        return {
            "label": "Book Consultation",
            "kind": workflow_kind,
            "placements": [
                "section_end",
                "hero",
            ],
        }

    if "urgent_service_decision" in archetypes:
        return {
            "label": "Request Immediate Help",
            "kind": workflow_kind,
            "placements": [
                "hero",
                "sticky",
            ],
        }

    return {
        "label": "Get Started",
        "kind": workflow_kind,
        "placements": ["hero"],
    }

def derive_priority_sections(
    archetypes: list[str],
) -> list[str]:

    sections = []

    if "fast_impulse_conversion" in archetypes:
        sections.extend([
            "hero_offer_banner",
            "menu_showcase",
            "primary_workflow_form",
        ])

    if "high_trust_consideration" in archetypes:
        sections.extend([
            "hero_trust_banner",
            "proof_band",
            "review_band",
        ])

    if "urgent_service_decision" in archetypes:
        sections.extend([
            "service_cards",
            "trust_band",
            "primary_workflow_form",
        ])

    return list(dict.fromkeys(sections))