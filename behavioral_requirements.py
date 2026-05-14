from __future__ import annotations

from typing import Any


def derive_behavioral_requirements(
    behavioral_contexts,
) -> dict[str, Any]:

    requirements = {
        "trust_requirements": [],
        "conversion_priorities": [],
        "recommended_sections": [],
        "interaction_patterns": [],
    }

    for context in behavioral_contexts:

        # -----------------------------
        # High trust businesses
        # -----------------------------

        if (
            context.trust_requirement
            == "high"
        ):

            requirements[
                "trust_requirements"
            ].extend([
                "credential_visibility",
                "testimonial_reassurance",
                "privacy_reassurance",
            ])

            requirements[
                "recommended_sections"
            ].extend([
                "credential_band",
                "proof_band",
                "review_band",
            ])

        # -----------------------------
        # Fast conversion businesses
        # -----------------------------

        if (
            context.conversion_latency
            == "short"
        ):

            requirements[
                "conversion_priorities"
            ].extend([
                "minimal_friction",
                "fast_checkout",
                "single_primary_cta",
            ])

            requirements[
                "interaction_patterns"
            ].extend([
                "sticky_cta",
                "quick_action_flow",
            ])

        # -----------------------------
        # Urgent businesses
        # -----------------------------

        if (
            context.urgency_level
            == "high"
        ):

            requirements[
                "conversion_priorities"
            ].extend([
                "rapid_contact",
                "availability_visibility",
            ])

            requirements[
                "recommended_sections"
            ].extend([
                "availability_banner",
                "contact_strip",
            ])

    # deduplicate
    for key in requirements:
        requirements[key] = list(
            dict.fromkeys(
                requirements[key]
            )
        )

    return requirements