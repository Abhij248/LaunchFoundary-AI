from __future__ import annotations

from agentic_models import (
    WebsiteAgentState,
)


def evaluate_behavioral_coherence(
    state: WebsiteAgentState,
) -> list[str]:

    issues = []

    contexts = (
        state.behavioral_contexts
        or []
    )

    candidates = (
        state.design_candidates
        or []
    )

    for context in contexts:

        for candidate in candidates:

            sections = []

            for page in candidate.pages:
                for section in page.sections:
                    sections.append(
                        section.type.value
                    )

            primary_action = (
                candidate.primary_action.label
                .lower()
            )

            # ---------------------------------
            # High trust businesses
            # ---------------------------------

            if (
                context.trust_requirement
                == "high"
            ):

                if (
                    "proof_band"
                    not in sections
                ):
                    issues.append(
                        (
                            f"{candidate.candidate_id}: "
                            "missing proof/trust "
                            "sections for "
                            "high-trust behavior"
                        )
                    )

                if any(
                    aggressive in primary_action
                    for aggressive in [
                        "buy now",
                        "instant",
                        "start now",
                    ]
                ):
                    issues.append(
                        (
                            f"{candidate.candidate_id}: "
                            "CTA too aggressive "
                            "for high-trust "
                            "behavior"
                        )
                    )

            # ---------------------------------
            # Fast impulse behavior
            # ---------------------------------

            if (
                context.conversion_latency
                == "short"
            ):

                if (
                    "primary_workflow_form"
                    not in sections
                ):
                    issues.append(
                        (
                            f"{candidate.candidate_id}: "
                            "missing fast-action "
                            "workflow section"
                        )
                    )

            # ---------------------------------
            # Urgent behavior
            # ---------------------------------

            if (
                context.urgency_level
                == "high"
            ):

                if (
                    "service_cards"
                    not in sections
                ):
                    issues.append(
                        (
                            f"{candidate.candidate_id}: "
                            "missing urgent "
                            "service visibility"
                        )
                    )

    return issues