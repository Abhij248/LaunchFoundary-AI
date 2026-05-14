from __future__ import annotations

from typing import Any

from agentic_models import (
    WebsiteAgentState,
)


def business_snapshot_tool(
    state: WebsiteAgentState,
) -> dict[str, Any]:
    if not state.business_profile:
        return {}
    profile = state.business_profile
    identity = state.business_identity
    return {
        "name": profile.name,
        "location": profile.location,
        "goal": profile.goal,
        "vertical": profile.vertical.value,
        "subtype": profile.subtype,
        "risk_level": profile.risk_level.value,
        "audience": profile.audience[:4],
        "confidence": round(profile.confidence, 2),
        "primary_workflow": (
            identity.primary_workflow.value
            if identity
            else "lead"
        ),
        "behavioral_archetypes": list(
            identity.behavioral_archetypes[:4]
        ) if identity else [],
    }


def workflow_constraints_tool(
    state: WebsiteAgentState,
) -> dict[str, Any]:
    if not state.requirements_spec:
        return {}
    requirements = state.requirements_spec
    return {
        "pages": [
            page.value
            for page in requirements.required_pages[:6]
        ],
        "workflows": [
            workflow.value
            for workflow in requirements.required_workflows[:4]
        ],
        "trust_requirements": requirements.trust_requirements[:5],
        "conversion_priorities": requirements.conversion_priorities[:5],
        "compliance_requirements": requirements.compliance_requirements[:4],
        "avoid_patterns": requirements.avoid_patterns[:4],
        "missing_information": requirements.missing_information[:4],
    }


def asset_evidence_tool(
    state: WebsiteAgentState,
) -> dict[str, Any]:
    summary: list[str] = []
    offers: list[str] = []
    services: list[str] = []
    prices: list[str] = []
    visual_cues: list[str] = []
    for extraction in (
        state.asset_extractions or []
    )[:4]:
        if extraction.business_signals:
            summary.extend(
                extraction.business_signals[:4]
            )
        info = extraction.extracted_business_info
        services.extend(
            info.services_or_items[:6]
        )
        offers.extend(
            info.offers[:4]
        )
        prices.extend(
            str(value)
            for value in info.prices[:6]
        )
        visual_cues.extend(
            extraction.visual_brand_cues[:4]
        )
    return {
        "signals": dedupe(summary)[:8],
        "services_or_items": dedupe(services)[:8],
        "offers": dedupe(offers)[:5],
        "prices": dedupe(prices)[:6],
        "visual_cues": dedupe(visual_cues)[:5],
    }


def memory_guidance_tool(
    state: WebsiteAgentState,
) -> dict[str, Any]:
    return {
        "patterns": [
            {
                "title": memory.title,
                "summary": memory.summary,
                "actions": memory.recommended_actions[:3],
                "anti_patterns": memory.anti_patterns[:2],
                "relevance": round(memory.relevance, 2),
            }
            for memory in (
                state.retrieved_memories
                or []
            )[:3]
        ]
    }


def strategy_landscape_tool(
    state: WebsiteAgentState,
) -> dict[str, Any]:
    return {
        "strategies": [
            {
                "id": strategy.strategy_id,
                "name": strategy.name,
                "thesis": strategy.core_thesis,
                "target_behavior": strategy.target_behavior,
                "strengths": strategy.strengths[:3],
                "risks": strategy.risks[:3],
                "confidence": round(strategy.confidence, 2),
            }
            for strategy in (
                state.strategy_hypotheses
                or []
            )[:3]
        ]
    }


def candidate_landscape_tool(
    state: WebsiteAgentState,
) -> dict[str, Any]:
    return {
        "candidates": [
            {
                "id": candidate.candidate_id,
                "rationale": candidate.rationale,
                "primary_action": candidate.primary_action.label,
                "page_types": [
                    page.page_type.value
                    for page in candidate.pages[:4]
                ],
                "section_types": [
                    section.type.value
                    for page in candidate.pages[:3]
                    for section in page.sections[:3]
                ][:8],
                "confidence": round(candidate.confidence, 2),
            }
            for candidate in (
                state.design_candidates
                or []
            )[:3]
        ]
    }


def critique_landscape_tool(
    state: WebsiteAgentState,
) -> dict[str, Any]:
    critiques = []
    for critique in (
        state.critique_reports
        or []
    )[:3]:
        average_score = round(
            sum(
                score.score
                for score in critique.scores
            ) / max(
                len(critique.scores),
                1,
            ),
            2,
        )
        critiques.append(
            {
                "candidate_id": critique.candidate_id,
                "summary": critique.summary,
                "average_score": average_score,
                "strengths": critique.strengths[:3],
                "weaknesses": critique.weaknesses[:3],
                "revision_instructions": critique.revision_instructions[:4],
            }
        )
    return {
        "critiques": critiques
    }


def process_health_tool(
    state: WebsiteAgentState,
) -> dict[str, Any]:
    return {
        "uncertainty_score": round(
            state.uncertainty_score,
            2,
        ),
        "revision_iteration": state.revision_iteration,
        "active_fallbacks": list(
            state.active_fallbacks[-5:]
        ),
        "recent_reasoning_notes": list(
            state.reasoning_notes[-5:]
        ),
        "candidate_history_depth": len(
            state.candidate_history
        ),
        "critique_history_depth": len(
            state.critique_history
        ),
    }


def build_stage_tool_context(
    state: WebsiteAgentState,
    stage: str,
) -> dict[str, Any]:
    stage_map = {
        "requirements": [
            ("business_snapshot", business_snapshot_tool),
            ("asset_evidence", asset_evidence_tool),
            ("memory_guidance", memory_guidance_tool),
            ("process_health", process_health_tool),
        ],
        "strategy_hypotheses": [
            ("business_snapshot", business_snapshot_tool),
            ("workflow_constraints", workflow_constraints_tool),
            ("asset_evidence", asset_evidence_tool),
            ("memory_guidance", memory_guidance_tool),
            ("process_health", process_health_tool),
        ],
        "design_candidates": [
            ("business_snapshot", business_snapshot_tool),
            ("workflow_constraints", workflow_constraints_tool),
            ("strategy_landscape", strategy_landscape_tool),
            ("asset_evidence", asset_evidence_tool),
            ("memory_guidance", memory_guidance_tool),
            ("process_health", process_health_tool),
        ],
        "critique": [
            ("business_snapshot", business_snapshot_tool),
            ("workflow_constraints", workflow_constraints_tool),
            ("candidate_landscape", candidate_landscape_tool),
            ("asset_evidence", asset_evidence_tool),
            ("memory_guidance", memory_guidance_tool),
            ("process_health", process_health_tool),
        ],
        "revision": [
            ("business_snapshot", business_snapshot_tool),
            ("workflow_constraints", workflow_constraints_tool),
            ("strategy_landscape", strategy_landscape_tool),
            ("candidate_landscape", candidate_landscape_tool),
            ("critique_landscape", critique_landscape_tool),
            ("memory_guidance", memory_guidance_tool),
            ("asset_evidence", asset_evidence_tool),
            ("process_health", process_health_tool),
        ],
        "reflection": [
            ("strategy_landscape", strategy_landscape_tool),
            ("candidate_landscape", candidate_landscape_tool),
            ("critique_landscape", critique_landscape_tool),
            ("process_health", process_health_tool),
        ],
        "debate": [
            ("business_snapshot", business_snapshot_tool),
            ("strategy_landscape", strategy_landscape_tool),
            ("candidate_landscape", candidate_landscape_tool),
            ("critique_landscape", critique_landscape_tool),
            ("memory_guidance", memory_guidance_tool),
            ("process_health", process_health_tool),
        ],
        "simulation": [
            ("business_snapshot", business_snapshot_tool),
            ("candidate_landscape", candidate_landscape_tool),
            ("critique_landscape", critique_landscape_tool),
            ("process_health", process_health_tool),
        ],
    }
    tools = stage_map.get(
        stage,
        [],
    )
    context: dict[str, Any] = {}
    for name, tool in tools:
        context[name] = tool(
            state
        )
    return context


def dedupe(
    values: list[str],
) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(
            normalized
        )
    return result
