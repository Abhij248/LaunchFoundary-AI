from __future__ import annotations
import logging
logger = logging.getLogger(__name__)


from textwrap import dedent
from typing import Any

from pydantic import ValidationError

from cognitive_state_api import (
    CognitiveStateAPI,
)

from cognitive_runtime import (
    register_node,
)

from behavioral_blending import (
    build_behavioral_blend,
)

from behavioral_requirements import (
    derive_behavioral_requirements,
)

from behavioral_validator import (
    evaluate_behavioral_coherence,
)
from agentic_memory import (
    retrieve_memory_bundle,
)
from agentic_cognition_tools import (
    build_stage_tool_context,
)

from business_archetype_mapper import (
     infer_behavioral_archetypes,
    build_behavioral_contexts,
)

from agentic_models import (
    CognitiveHealthReport,
    AgentDecision,
    SimulationReport,
    WorkflowSimulation,
    DebateOutcome,
    ReflectionReport,
    AssetExtraction,
    BusinessProfile,
    BusinessProfileInference,
    CritiqueReportSet,
    DesignCandidateSet,
    DesignSpec,
    FinalizationDecision,
    PageType,
    RequirementsSpec,
    SectionType,
    StrategyHypothesisSet,
    WebsiteAgentState,
    WorkflowType,
    CanonicalBusinessIdentity,
    CognitiveProvenanceRecord,
    ProvenanceSource,
    ReasoningLineageEntry,
    StateArtifactStatus,
    MemoryRetrievalBundle,
    ToolInvocationRecord,
    Vertical,
    RiskLevel,
    PageType,
)
from agentic_planner import (
    ModelJsonPlanner,
    PlannerGenerationError,
    parse_json_object,
)
from vertical_rulebooks import VERTICAL_RULEBOOKS

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:  # pragma: no cover
    END = "END"
    START = "START"
    StateGraph = None


def infer_vertical_from_business_input(
    state: WebsiteAgentState | None,
) -> str:
    if state is None:
        return "unknown"

    text = " ".join(
        str(
            state.business_input.get(
                key,
                "",
            )
        )
        for key in [
            "name",
            "goal",
            "details",
            "location",
        ]
    ).lower()

    keyword_map = [
        (
            [
                "pizza",
                "pasta",
                "restaurant",
                "reservation",
                "pickup",
                "menu",
                "dine",
            ],
            "restaurant",
        ),
        (
            [
                "cafe",
                "coffee",
                "espresso",
            ],
            "cafe",
        ),
        (
            [
                "bakery",
                "cake",
                "pastry",
                "bake",
            ],
            "bakery",
        ),
        (
            [
                "clinic",
                "doctor",
                "patient",
                "medical",
                "dental",
            ],
            "clinic",
        ),
        (
            [
                "salon",
                "spa",
                "hair",
                "beauty",
            ],
            "salon",
        ),
        (
            [
                "tutor",
                "tuition",
                "student",
                "course",
                "class",
            ],
            "tutor",
        ),
        (
            [
                "repair",
                "service center",
                "fix",
                "appliance",
                "device repair",
            ],
            "repair_service",
        ),
        (
            [
                "consultant",
                "consulting",
                "advisor",
                "agency",
            ],
            "consultant",
        ),
    ]

    for keywords, vertical in keyword_map:
        if any(
            keyword in text
            for keyword in keywords
        ):
            return vertical

    return "unknown"


def infer_risk_level_from_vertical(
    vertical: str,
) -> str:
    if vertical in {
        "clinic",
        "consultant",
    }:
        return "regulated"
    return "standard"


def add_reasoning_note(
    state: WebsiteAgentState,
    message: str,
) -> None:
    state.reasoning_notes.append(
        message
    )


def record_provenance(
    state: WebsiteAgentState,
    artifact_key: str,
    stage: str,
    source_type: ProvenanceSource,
    summary: str,
    confidence: float,
    fallback_used: bool = False,
    supporting_keys: list[str] | None = None,
) -> None:
    state.provenance_log.append(
        CognitiveProvenanceRecord(
            artifact_key=artifact_key,
            stage=stage,
            source_type=source_type,
            summary=summary,
            confidence=max(
                0.0,
                min(1.0, confidence),
            ),
            fallback_used=fallback_used,
            iteration=state.revision_iteration,
            supporting_keys=supporting_keys or [],
        )
    )
    if fallback_used:
        fallback_tag = (
            f"{stage}:{artifact_key}"
        )
        if fallback_tag not in state.active_fallbacks:
            state.active_fallbacks.append(
                fallback_tag
            )


def record_lineage(
    state: WebsiteAgentState,
    stage: str,
    decision: str,
    confidence: float,
    inputs: list[str],
    outputs: list[str],
    summary: str,
    fallback_used: bool = False,
) -> None:
    state.reasoning_lineage.append(
        ReasoningLineageEntry(
            stage=stage,
            decision=decision,
            confidence=max(
                0.0,
                min(1.0, confidence),
            ),
            fallback_used=fallback_used,
            inputs=inputs,
            outputs=outputs,
            summary=summary,
        )
    )


def update_state_artifact(
    state: WebsiteAgentState,
    artifact_key: str,
    stage: str,
    source_type: ProvenanceSource,
    confidence: float,
    summary: str,
    status: str,
) -> None:
    state.state_artifacts[
        artifact_key
    ] = StateArtifactStatus(
        artifact_key=artifact_key,
        status=status,
        source_type=source_type,
        confidence=max(
            0.0,
            min(1.0, confidence),
        ),
        updated_in_stage=stage,
        summary=summary,
        lineage_ref=(
            f"{stage}:{artifact_key}:"
            f"{state.revision_iteration}"
        ),
    )


def artifact_status(
    state: WebsiteAgentState,
    artifact_key: str,
) -> StateArtifactStatus | None:
    return state.state_artifacts.get(
        artifact_key
    )


def artifact_confidence(
    state: WebsiteAgentState,
    artifact_key: str,
    fallback: float = 0.0,
) -> float:
    artifact = artifact_status(
        state,
        artifact_key,
    )
    return (
        artifact.confidence
        if artifact
        else fallback
    )


def artifact_used_fallback(
    state: WebsiteAgentState,
    artifact_key: str,
) -> bool:
    artifact = artifact_status(
        state,
        artifact_key,
    )
    return bool(
        artifact
        and artifact.status == "fallback"
    )


def candidate_decision_scores(
    state: WebsiteAgentState,
) -> list[dict[str, Any]]:
    critique_map = {
        report.candidate_id: average_critique_score(
            report
        )
        for report in (
            state.critique_reports or []
        )
    }
    debate_bonus_id = (
        state.debate_outcome.winning_candidate_id
        if state.debate_outcome
        else ""
    )
    results: list[dict[str, Any]] = []
    for candidate in (
        state.design_candidates
        or []
    ):
        critique_score = critique_map.get(
            candidate.candidate_id,
            0.0,
        )
        confidence = normalize_confidence(
            candidate.confidence
        )
        debate_bonus = (
            0.35
            if debate_bonus_id
            and debate_bonus_id == candidate.candidate_id
            else 0.0
        )
        realism_factor = (
            (
                state.simulation_report.overall_realism_score
                / 10.0
            )
            if state.simulation_report
            else 0.65
        )
        weighted_score = round(
            (
                critique_score * 0.55
                + confidence * 10 * 0.25
                + realism_factor * 10 * 0.15
                + debate_bonus * 10 * 0.05
            ),
            2,
        )
        results.append(
            {
                "candidate_id": candidate.candidate_id,
                "weighted_score": weighted_score,
                "critique_score": round(
                    critique_score,
                    2,
                ),
                "confidence": round(
                    confidence,
                    2,
                ),
                "debate_bonus": round(
                    debate_bonus,
                    2,
                ),
            }
        )
    results.sort(
        key=lambda item: item[
            "weighted_score"
        ],
        reverse=True,
    )
    return results


def set_finalization_decision(
    state: WebsiteAgentState,
    authority: str,
    reason: str,
    supporting_signals: list[str] | None = None,
) -> FinalizationDecision | None:
    if not state.design_candidates:
        return None
    ranked = candidate_decision_scores(
        state
    )
    if not ranked:
        return None
    winner = ranked[0]
    top_score = winner[
        "weighted_score"
    ]
    runner_up = (
        ranked[1][
            "weighted_score"
        ]
        if len(ranked) > 1
        else max(
            top_score - 0.75,
            0.0,
        )
    )
    separation = max(
        top_score - runner_up,
        0.0,
    )
    readiness = round(
        min(
            0.98,
            max(
                0.35,
                top_score / 10.0
                + separation / 12.0
                - min(
                    state.uncertainty_score,
                    0.35,
                ),
            ),
        ),
        2,
    )
    decision = FinalizationDecision(
        finalize_now=True,
        selected_candidate_id=winner[
            "candidate_id"
        ],
        authority=authority,
        reason=reason,
        readiness_score=readiness,
        confidence_weighted_score=top_score,
        supporting_signals=(
            supporting_signals
            or []
        )
        + [
            (
                f"weighted_score="
                f"{top_score}"
            ),
            (
                f"runner_up_gap="
                f"{round(separation, 2)}"
            ),
        ],
    )
    state.finalization_decision = (
        decision
    )
    record_provenance(
        state,
        artifact_key="finalization_decision",
        stage="finalize_authority",
        source_type=ProvenanceSource.GRAPH_ROUTER,
        summary=(
            f"{authority} selected "
            f"{decision.selected_candidate_id} "
            "for finalization."
        ),
        confidence=readiness,
        fallback_used=False,
        supporting_keys=[
            "design_candidates",
            "critique_reports",
            "simulation_report",
            "debate_outcome",
        ],
    )
    update_state_artifact(
        state,
        artifact_key="finalization_decision",
        stage="finalize_authority",
        source_type=ProvenanceSource.GRAPH_ROUTER,
        confidence=readiness,
        summary=(
            f"Best-so-far candidate: "
            f"{decision.selected_candidate_id}"
        ),
        status="finalized",
    )
    record_lineage(
        state,
        stage="finalize_authority",
        decision="authorized_finalization",
        confidence=readiness,
        inputs=[
            "design_candidates",
            "critique_reports",
            "simulation_report",
            "debate_outcome",
        ],
        outputs=[
            "finalization_decision",
        ],
        summary=reason,
        fallback_used=False,
    )
    add_reasoning_note(
        state,
        (
            f"Finalization authority selected "
            f"{decision.selected_candidate_id} "
            f"with readiness {decision.readiness_score} "
            f"and weighted score {decision.confidence_weighted_score}."
        ),
    )
    return decision


def external_planner_unhealthy(
    planner: ModelJsonPlanner,
) -> bool:
    return bool(
        getattr(
            planner,
            "failure_count",
            0,
        )
        or getattr(
            planner,
            "request_errors",
            [],
        )
    )


def invoke_cognition_tools(
    state: WebsiteAgentState,
    stage: str,
) -> dict[str, Any]:
    context = build_stage_tool_context(
        state,
        stage,
    )
    for tool_name, payload in context.items():
        if not isinstance(
            payload,
            dict,
        ):
            continue
        output_keys = list(
            payload.keys()
        )[:8]
        state.tool_invocations.append(
            ToolInvocationRecord(
                stage=stage,
                tool_name=tool_name,
                purpose=(
                    f"Provide structured cognition context for {stage}."
                ),
                output_keys=output_keys,
                summary=(
                    f"{tool_name} returned {len(output_keys)} top-level fields."
                ),
                confidence=max(
                    0.45,
                    1.0 - min(
                        state.uncertainty_score,
                        0.5,
                    ),
                ),
            )
        )
    return context


def build_fallback_strategy_hypotheses(
    state: WebsiteAgentState,
) -> StrategyHypothesisSet:
    vertical = (
        state.business_profile.vertical.value
        if state.business_profile
        else infer_vertical_from_business_input(
            state
        )
    )
    goal = (
        state.business_profile.goal
        if state.business_profile
        else str(
            state.business_input.get(
                "goal",
                "increase conversions",
            )
        )
    )

    if vertical in {
        "restaurant",
        "cafe",
        "bakery",
    }:
        return StrategyHypothesisSet(
            strategies=[
                {
                    "strategy_id": "strategy-conversion-offer",
                    "name": "Offer-Led Conversion",
                    "core_thesis": "Lead with the most compelling offer and reduce friction to ordering or reservation.",
                    "target_behavior": "Get visitors to place an order or reserve a table quickly.",
                    "strengths": [
                        "Clear action path",
                        "Strong promotional focus",
                        "Fast path to revenue",
                    ],
                    "risks": [
                        "Can feel transactional if trust is weak",
                        "May undersell brand story",
                    ],
                    "ideal_for": [
                        "Discount-led campaigns",
                        "Impulse ordering",
                        goal,
                    ],
                    "tradeoffs": [
                        "Less exploration before action",
                        "Heavier emphasis on CTA placement",
                    ],
                    "confidence": 0.74,
                },
                {
                    "strategy_id": "strategy-trust-browse",
                    "name": "Browse-and-Trust Journey",
                    "core_thesis": "Use imagery, menu exploration, and trust cues before presenting the primary action.",
                    "target_behavior": "Help visitors build confidence, explore the menu, and then convert.",
                    "strengths": [
                        "Supports richer browsing",
                        "Improves decision confidence",
                        "Better for unfamiliar customers",
                    ],
                    "risks": [
                        "Action path may feel slower",
                        "Can reduce immediacy of promotional offers",
                    ],
                    "ideal_for": [
                        "Menu-heavy businesses",
                        "Trust-sensitive first visits",
                        goal,
                    ],
                    "tradeoffs": [
                        "More content before CTA",
                        "Slightly softer conversion posture",
                    ],
                    "confidence": 0.7,
                },
            ]
        )

    return StrategyHypothesisSet(
        strategies=[
            {
                "strategy_id": "strategy-direct-conversion",
                "name": "Direct Conversion Flow",
                "core_thesis": "Prioritize the shortest route from intent to action.",
                "target_behavior": "Encourage immediate contact, booking, or purchase.",
                "strengths": [
                    "Simple structure",
                    "High clarity",
                ],
                "risks": [
                    "Less storytelling",
                ],
                "ideal_for": [
                    goal,
                ],
                "tradeoffs": [
                    "Lower exploration depth",
                ],
                "confidence": 0.68,
            },
            {
                "strategy_id": "strategy-credibility-first",
                "name": "Credibility-First Journey",
                "core_thesis": "Build trust and understanding before the main action request.",
                "target_behavior": "Increase confidence before asking users to convert.",
                "strengths": [
                    "Improves trust",
                    "Supports considered decisions",
                ],
                "risks": [
                    "Longer path to action",
                ],
                "ideal_for": [
                    goal,
                ],
                "tradeoffs": [
                    "Requires more supporting content",
                ],
                "confidence": 0.66,
            },
        ]
    )


def build_fallback_reflection_report(
    state: WebsiteAgentState,
) -> ReflectionReport:
    candidate_count = len(
        state.design_candidates
    )
    critique_count = len(
        state.critique_reports
    )
    strategic_diversity = (
        8
        if candidate_count >= 2
        else 5
    )
    critique_depth = (
        7
        if critique_count >= 2
        else 5
    )
    convergence_risk = (
        4
        if strategic_diversity >= 7
        else 7
    )

    return ReflectionReport(
        exploration_quality=7,
        strategic_diversity=strategic_diversity,
        critique_depth=critique_depth,
        reasoning_quality=6,
        convergence_risk=convergence_risk,
        observations=[
            "Used local reflection fallback because the external reasoning model was unavailable.",
            f"Reviewed {candidate_count} candidate directions and {critique_count} critique reports.",
        ],
        improvement_actions=[
            "Preserve structural diversity between candidates.",
            "Tie final rationale more directly to available business evidence.",
        ],
        should_expand_exploration=(
            candidate_count < 2
        ),
    )


def build_fallback_debate_outcome(
    state: WebsiteAgentState,
) -> DebateOutcome:
    candidates = state.design_candidates or []
    winner = candidates[0] if candidates else None
    loser = (
        candidates[1]
        if len(candidates) > 1
        else winner
    )
    winning_candidate_id = (
        winner.candidate_id
        if winner
        else "candidate-1"
    )
    losing_candidate_id = (
        loser.candidate_id
        if loser
        else winning_candidate_id
    )

    return DebateOutcome(
        winning_candidate_id=winning_candidate_id,
        losing_candidate_id=losing_candidate_id,
        winner_reasoning="Selected the strongest available candidate using local fallback debate logic.",
        loser_reasoning="Alternative candidate remains viable but was ranked lower on immediate conversion clarity.",
        tradeoff_analysis=[
            "Fallback debate favored clarity and action hierarchy.",
            "Alternative strategies may still offer stronger trust or exploration benefits.",
        ],
        synthesis_opportunities=[
            "Blend stronger trust cues into the winning candidate.",
            "Retain exploration elements without delaying the primary action too much.",
        ],
        strategic_observations=[
            "Debate fallback preserved forward progress while the external model was unavailable.",
        ],
        confidence=0.62,
    )


def build_fallback_simulation_report(
    state: WebsiteAgentState,
) -> SimulationReport:
    primary_goal = (
        state.business_profile.goal
        if state.business_profile
        else str(
            state.business_input.get(
                "goal",
                "increase conversions",
            )
        )
    )

    simulations = [
        WorkflowSimulation(
            persona="first_time_visitor",
            goal=primary_goal,
            journey_summary="A first-time visitor scans the homepage, evaluates the offer, and looks for a clear path to act.",
            friction_points=[
                "Trust cues may be thin when external reasoning is unavailable.",
            ],
            trust_observations=[
                "Basic trust signals still exist in the generated plan.",
            ],
            confusion_points=[],
            conversion_barriers=[
                "Fallback planning may underspecify supporting content details.",
            ],
            successful=True,
            realism_score=7,
        ),
        WorkflowSimulation(
            persona="returning_customer",
            goal="complete the primary workflow quickly",
            journey_summary="A repeat visitor looks for the shortest path to reorder or reserve without extra browsing.",
            friction_points=[],
            trust_observations=[
                "Action-first structure supports repeat intent well.",
            ],
            confusion_points=[],
            conversion_barriers=[],
            successful=True,
            realism_score=8,
        ),
    ]

    return SimulationReport(
        simulations=simulations,
        overall_realism_score=7,
        systemic_issues=[
            "External model outage reduced the richness of simulated reasoning.",
        ],
        recommended_improvements=[
            "Re-run simulation with the external planner when it recovers.",
            "Keep fallback plans structurally distinct and action clear.",
        ],
    )


def build_fallback_design_candidates(
    state: WebsiteAgentState,
) -> DesignCandidateSet:

    from behavioral_planning import (
        derive_visual_system_from_archetypes,
        derive_primary_action_from_archetypes,
    )

    required_pages = (
        state.requirements_spec.required_pages
        if state.requirements_spec
        else [PageType.HOME]
    )

    workflow_kind = (
        state.business_identity.primary_workflow
        if (
            state.business_identity
            and state.business_identity.primary_workflow
        )
        else (
            state.requirements_spec
            .required_workflows[0]
            if (
                state.requirements_spec
                and state.requirements_spec
                .required_workflows
            )
            else WorkflowType.LEAD
        )
    )

    fallback_candidates = []

    strategies = (
        state.strategy_hypotheses
        or []
    )

    if not strategies:

        strategies = (
            build_fallback_strategy_hypotheses(
                state
            ).strategies
        )

    behavioral_keys = [
        context.key
        for context in (
            state.behavioral_contexts
            or []
        )
    ]

    visual_system = (
        derive_visual_system_from_archetypes(
            behavioral_keys
        )
    )

    primary_action = (
        derive_primary_action_from_archetypes(
            behavioral_keys,

            workflow_kind.value
            if hasattr(
                workflow_kind,
                "value",
            )
            else str(
                workflow_kind
            ),
        )
    )

    for index, strategy in enumerate(
        strategies[:2],
        start=1,
    ):

        candidate_seed = {

            "candidate_id": (
                f"candidate_{index}"
            ),

            "rationale": (
                strategy.core_thesis
                or (
                    f"Fallback candidate "
                    f"{index} aligned to "
                    "the strongest "
                    "available strategy."
                )
            ),

            "confidence": max(
                0.55,
                strategy.confidence - 0.08,
            ),

            "visual_system": (
                visual_system
            ),

            "primary_action": (
                primary_action
            ),

            "pages": [
                {
                    "type": (
                        page_type.value
                        if isinstance(
                            page_type,
                            PageType,
                        )
                        else str(
                            page_type
                        )
                    )
                }
                for page_type in (
                    required_pages
                )
            ],
        }

        fallback_candidates.append(
            normalize_design_candidate(
                candidate_seed,
                index,
                state,
            )
        )

    return DesignCandidateSet(
        candidates=fallback_candidates
    )

def normalize_business_profile_payload(
    payload: dict,
    state: WebsiteAgentState | None = None,
) -> dict:
    if not isinstance(
        payload,
        dict,
    ):
        payload = {}

    if (
        "BusinessProfileInference"
        in payload
        and isinstance(
            payload[
                "BusinessProfileInference"
            ],
            dict,
        )
    ):

        payload = payload[
            "BusinessProfileInference"
        ]

    if (
        "business_profile"
        in payload
        and isinstance(
            payload[
                "business_profile"
            ],
            dict,
        )
    ):
        payload = payload[
            "business_profile"
        ]

    normalized = dict(payload)

    alias_map = {
        "vertical": [
            "vertical",
            "business_vertical",
            "businessVertical",
        ],
        "risk_level": [
            "risk_level",
            "riskLevel",
            "business_risk_level",
            "businessRiskLevel",
        ],
        "subtype": [
            "subtype",
            "business_subtype",
            "businessSubtype",
        ],
        "audience": [
            "audience",
            "target_audience",
            "targetAudience",
        ],
        "evidence_summary": [
            "evidence_summary",
            "evidenceSummary",
        ],
    }

    for canonical, aliases in alias_map.items():
        if normalized.get(canonical):
            continue
        for alias in aliases:
            if alias in normalized and normalized.get(alias) is not None:
                normalized[canonical] = normalized.get(alias)
                break

    for key in [
        "vertical",
        "risk_level",
    ]:

        value = normalized.get(key)

        if isinstance(value, dict):

            normalized[key] = (
                value.get("value")
                or value.get("label")
                or "unknown"
            )

    audience = normalized.get(
        "audience"
    )

    if isinstance(audience, dict):

        audience = (
            audience.get("value")
            or []
        )

    if isinstance(audience, str):

        audience = [audience]

    normalized["audience"] = (
        audience or []
    )

    evidence_summary = normalized.get(
        "evidence_summary"
    )

    if isinstance(
        evidence_summary,
        str,
    ):
        evidence_summary = [
            evidence_summary
        ]
    elif not isinstance(
        evidence_summary,
        list,
    ):
        evidence_summary = []

    normalized[
        "evidence_summary"
    ] = [
        str(item).strip()
        for item in evidence_summary
        if str(item).strip()
    ]

    if not normalized.get(
        "subtype"
    ):
        normalized[
            "subtype"
        ] = "general"

    vertical = normalize_enum(
        normalized.get(
            "vertical"
        )
        or infer_vertical_from_business_input(
            state
        )
    )
    normalized[
        "vertical"
    ] = vertical

    normalized[
        "risk_level"
    ] = normalize_enum(
        normalized.get(
            "risk_level"
        )
        or infer_risk_level_from_vertical(
            vertical
        )
    )

    normalized[
        "behavioral_archetypes"
    ] = infer_behavioral_archetypes(
        business_input=" ".join(
            str(
                state.business_input.get(
                    key,
                    "",
                )
            )
            for key in [
                "name",
                "goal",
                "details",
                "location",
            ]
        ) if state else "",

        vertical=vertical,
    )


    from behavioral_blending import (
        build_behavioral_blend,
    )

    blend = build_behavioral_blend(
        normalized[
            "behavioral_archetypes"
        ]
    )

    normalized[
        "behavioral_blend"
    ] = blend.model_dump()

    normalized[
        "behavioral_contexts"
    ] = [
        context.model_dump()
        for context in build_behavioral_contexts(
            normalized[
                "behavioral_archetypes"
            ]
        )
    ]

    normalized.setdefault(
        "confidence",
        0.8,
    )

    normalized[
        "behavioral_archetypes"
    ] = infer_behavioral_archetypes(
        business_input=" ".join(
            str(
                state.business_input.get(
                    key,
                    "",
                )
            )
            for key in [
                "name",
                "goal",
                "details",
                "location",
            ]
        ) if state else "",

        vertical=vertical,
    )

    normalized.setdefault(
        "behavioral_archetypes",
        []
    )

    return normalized

def remove_forbidden_semantics(
    values: list[str],
    state: WebsiteAgentState,
) -> list[str]:

    if (
        not state.business_identity
        or not state.business_identity
        .forbidden_semantics
    ):
        return values

    forbidden = {
        term.lower()
        for term in (
            state.business_identity
            .forbidden_semantics
        )
    }

    cleaned = []

    for value in values:

        normalized = str(value)

        lowered = normalized.lower()

        blocked = any(
            term in lowered
            for term in forbidden
        )

        if not blocked:
            cleaned.append(
                normalized
            )

    return cleaned


def build_agent_graph(planner: ModelJsonPlanner) -> Any:
    if StateGraph is None:
        raise ImportError("langgraph is not installed yet")
    @register_node("business_profile")
    def business_profile_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:
        fallback_used = False
        source_type = ProvenanceSource.EXTERNAL_MODEL

        prompt = build_business_profile_prompt(
            state
        )

        try:

            raw = planner.generate_text(
                prompt
            )

            parsed = parse_json_object(
                raw
            )

            normalized = (
                normalize_business_profile_payload(
                    parsed,
                    state,
                )
            )

        except PlannerGenerationError as exc:
            fallback_used = True
            source_type = ProvenanceSource.HEURISTIC_FALLBACK

            logger.warning(
                "Business profile fallback triggered: %s",
                exc,
            )

            state.reasoning_notes.append(
                (
                    "Business profile generation "
                    "used deterministic fallback "
                    "because external reasoning "
                    "failed."
                )
            )

            state.uncertainty_score += 0.15

            normalized = (
                normalize_business_profile_payload(
                    {},
                    state,
                )
            )

        try:

            inferred = (
                BusinessProfileInference
                .model_validate(
                    normalized
                )
            )

        except ValidationError:
            fallback_used = True
            source_type = ProvenanceSource.HEURISTIC_FALLBACK

            fallback_profile = (
                normalize_business_profile_payload(
                    {},
                    state,
                )
            )

            state.reasoning_notes.append(
                (
                    "Business profile output "
                    "was incomplete. Used "
                    "heuristic fallback "
                    "classification."
                )
            )

            inferred = (
                BusinessProfileInference
                .model_validate(
                    fallback_profile
                )
            )

        state.business_profile = (
            BusinessProfile(
                name=state.business_input.get(
                    "name",
                    "Unnamed Business",
                ),

                location=state.business_input.get(
                    "location",
                    "Unknown",
                ),

                goal=state.business_input.get(
                    "goal",
                    "increase conversions",
                ),

                vertical=inferred.vertical,

                subtype=inferred.subtype,

                risk_level=inferred.risk_level,

                audience=inferred.audience,

                evidence_summary=normalize_evidence_summary(
                    inferred.evidence_summary
                ),

                confidence=normalize_confidence(
                    inferred.confidence
                ),
            )
        )

        state.behavioral_contexts = (
            build_behavioral_contexts(
                normalized.get(
                    "behavioral_archetypes",
                    [],
                )
            )
        )

        state.behavioral_blend = (
            build_behavioral_blend(
                normalized.get(
                    "behavioral_archetypes",
                    [],
                )
            )
        )

        behavioral_archetypes = (
            normalized.get(
                "behavioral_archetypes",
                [],
            )
        )

        dominant_behavior = (
            state.behavioral_blend
            .dominant_archetype
            if state.behavioral_blend
            else "unknown"
        )

        vertical = (
            state.business_profile.vertical
        )

        primary_workflow = (
            WorkflowType.BOOKING
            if vertical in {
                Vertical.CLINIC,
                Vertical.SALON,
                Vertical.CONSULTANT,
                Vertical.TUTOR,
            }
            else WorkflowType.ORDER
            if vertical in {
                Vertical.RESTAURANT,
                Vertical.CAFE,
                Vertical.BAKERY,
            }
            else WorkflowType.LEAD
        )

        trust_model = (
            "high_assurance"
            if (
                state.business_profile
                .risk_level
                == RiskLevel.REGULATED
            )
            else "standard"
        )

        conversion_model = (
            "trust_accelerated"
            if (
                dominant_behavior
                == "high_trust_consideration"
            )
            else "fast_conversion"
            if (
                dominant_behavior
                == "fast_impulse_conversion"
            )
            else "standard"
        )

        allowed_pages = (
            [
                page.value
                if hasattr(
                    page,
                    "value",
                )
                else str(page)
                for page in (
                    state.requirements_spec.required_pages
                    if (
                        state.requirements_spec
                        and state.requirements_spec.required_pages
                    )
                    else [
                        PageType.HOME,
                        PageType.CONTACT,
                    ]
                )
            ]
        )

        forbidden_semantics = (
            ["medical", "doctor", "patient"]
            if vertical in {
                Vertical.RESTAURANT,
                Vertical.CAFE,
                Vertical.BAKERY,
            }
            else ["menu", "pizza", "reservations"]
            if vertical == Vertical.CLINIC
            else []
        )

        state.business_identity = (
            CanonicalBusinessIdentity(
                vertical=vertical,

                subtype=(
                    state.business_profile
                    .subtype
                ),

                risk_level=(
                    state.business_profile
                    .risk_level
                ),

                confidence=(
                    state.business_profile
                    .confidence
                ),

                behavioral_archetypes=(
                    behavioral_archetypes
                ),

                dominant_behavior_pattern=(
                    dominant_behavior
                ),

                trust_model=trust_model,

                conversion_model=(
                    conversion_model
                ),

                primary_workflow=(
                    primary_workflow
                ),

                allowed_pages=(
                    allowed_pages
                ),

                forbidden_semantics=(
                    forbidden_semantics
                ),
            )
        )

        state.uncertainty_score = max(
            state.uncertainty_score,
            (
                1.0
                - state.business_profile.confidence
            ),
        )

        if state.uncertainty_score > 0.4:

            state.reasoning_notes.append(
                (
                    "Business classification "
                    "confidence is low. "
                    "Expanding planning "
                    "diversity."
                )
            )

        record_provenance(
            state,
            artifact_key="business_profile",
            stage="business_profile",
            source_type=source_type,
            summary=(
                f"Classified business as {state.business_profile.vertical.value} "
                f"with subtype {state.business_profile.subtype}."
            ),
            confidence=state.business_profile.confidence,
            fallback_used=fallback_used,
            supporting_keys=[
                "business_input",
                "asset_extractions",
                "behavioral_archetypes",
            ],
        )
        update_state_artifact(
            state,
            artifact_key="business_profile",
            stage="business_profile",
            source_type=source_type,
            confidence=state.business_profile.confidence,
            summary=(
                f"{state.business_profile.vertical.value} / "
                f"{state.business_profile.subtype}"
            ),
            status="fallback" if fallback_used else "derived",
        )
        record_lineage(
            state,
            stage="business_profile",
            decision="classified_business_identity",
            confidence=state.business_profile.confidence,
            inputs=["business_input", "asset_extractions"],
            outputs=["business_profile", "business_identity", "behavioral_contexts"],
            summary=(
                f"Derived business identity using {source_type.value}."
            ),
            fallback_used=fallback_used,
        )

        return state

    def memory_retrieval_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:
        bundle: MemoryRetrievalBundle = (
            retrieve_memory_bundle(
                state
            )
        )
        state.memory_query = (
            bundle.query
        )
        state.retrieved_memories = list(
            bundle.memories
        )

        memory_confidence = (
            bundle.retrieval_confidence
            if bundle.memories
            else 0.35
        )
        if bundle.memories:
            add_reasoning_note(
                state,
                (
                    "Retrieved local planning memory to guide "
                    "workflow, trust, and offer decisions."
                ),
            )
        else:
            add_reasoning_note(
                state,
                (
                    "No strong memory matches found. Proceeding "
                    "with direct evidence and rulebooks."
                ),
            )

        for note in bundle.notes[:2]:
            add_reasoning_note(
                state,
                f"Memory note: {note}",
            )

        record_provenance(
            state,
            artifact_key="retrieved_memories",
            stage="memory_retrieval",
            source_type=ProvenanceSource.MEMORY_RETRIEVAL,
            summary=(
                f"Retrieved {len(bundle.memories)} reusable planning memories "
                "for this business context."
            ),
            confidence=memory_confidence,
            fallback_used=False,
            supporting_keys=[
                "business_profile",
                "business_identity",
                "asset_extractions",
            ],
        )
        update_state_artifact(
            state,
            artifact_key="retrieved_memories",
            stage="memory_retrieval",
            source_type=ProvenanceSource.MEMORY_RETRIEVAL,
            confidence=memory_confidence,
            summary=(
                "Local memory retrieval populated reusable patterns."
                if bundle.memories
                else "No strong reusable memory patterns matched."
            ),
            status="derived" if bundle.memories else "empty",
        )
        record_lineage(
            state,
            stage="memory_retrieval",
            decision="retrieved_reusable_planning_memory",
            confidence=memory_confidence,
            inputs=["business_profile", "business_identity", "asset_extractions"],
            outputs=["memory_query", "retrieved_memories"],
            summary=(
                "Matched local workflow and trust patterns to the current business."
            ),
            fallback_used=False,
        )

        return state
    @register_node("requirements")
    def requirements_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:
        
        state.execution_trace.append(
            "requirements"
        )

        state.node_visit_counts[
            "requirements"
        ] = (
            state.node_visit_counts.get(
                "requirements",
                0,
            )
            + 1
        )
        fallback_used = False
        source_type = ProvenanceSource.EXTERNAL_MODEL
        tool_context = invoke_cognition_tools(
            state,
            "requirements",
        )

        prompt = build_requirements_prompt(
            state,
            tool_context,
        )

        try:

            raw = planner.generate_text(
                prompt
            )

            parsed = parse_json_object(
                raw
            )

            normalized = (
                normalize_requirements_payload(
                    parsed,
                    state,
                )
            )

        except PlannerGenerationError as exc:
            fallback_used = True
            source_type = ProvenanceSource.HEURISTIC_FALLBACK

            logger.warning(
                "Requirements fallback triggered: %s",
                exc,
            )

            state.reasoning_notes.append(
                (
                    "Requirements generation "
                    "used deterministic fallback "
                    "because external reasoning "
                    "failed."
                )
            )

            state.uncertainty_score += 0.15

            normalized = (
                normalize_requirements_payload(
                    {},
                    state,
                )
            )

        state.requirements_spec = (
            RequirementsSpec.model_validate(
                normalized
            )
        )

        req_confidence = max(
            0.45,
            1.0 - min(state.uncertainty_score, 0.55),
        )
        record_provenance(
            state,
            artifact_key="requirements_spec",
            stage="requirements",
            source_type=source_type,
            summary=(
                f"Planned {len(state.requirements_spec.required_pages)} pages and "
                f"{len(state.requirements_spec.required_workflows)} workflows."
            ),
            confidence=req_confidence,
            fallback_used=fallback_used,
            supporting_keys=[
                "business_profile",
                "business_identity",
                "vertical_rulebook",
                "retrieved_memories",
            ],
        )
        update_state_artifact(
            state,
            artifact_key="requirements_spec",
            stage="requirements",
            source_type=source_type,
            confidence=req_confidence,
            summary="Operational pages and workflows selected.",
            status="fallback" if fallback_used else "derived",
        )
        record_lineage(
            state,
            stage="requirements",
            decision="planned_requirements",
            confidence=req_confidence,
            inputs=["business_profile", "business_identity", "vertical_rulebook", "retrieved_memories"],
            outputs=["requirements_spec"],
            summary="Derived workflow and page requirements.",
            fallback_used=fallback_used,
        )

        return state
    @register_node("strategy")
    def strategy_hypothesis_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:

        state.execution_trace.append(
            "strategy_hypotheses"
        )

        state.node_visit_counts[
            "strategy_hypotheses"
        ] = (
            state.node_visit_counts.get(
                "strategy_hypotheses",
                0,
            )
            + 1
        )
        fallback_used = False
        source_type = ProvenanceSource.EXTERNAL_MODEL
        tool_context = invoke_cognition_tools(
            state,
            "strategy_hypotheses",
        )

        prompt = build_strategy_prompt(
            state,
            tool_context,
        )

        try:

            raw = planner.generate_text(
                prompt
            )

            parsed = parse_json_object(
                raw
            )

            hypotheses = (
                StrategyHypothesisSet
                .model_validate(
                    parsed
                )
            )

        except PlannerGenerationError as exc:
            fallback_used = True
            source_type = ProvenanceSource.HEURISTIC_FALLBACK

            logger.warning(
                "Strategy fallback triggered: %s",
                exc,
            )

            state.reasoning_notes.append(
                (
                    "Strategy generation used "
                    "deterministic fallback "
                    "because external reasoning "
                    "failed."
                )
            )

            state.uncertainty_score += 0.15

            hypotheses = (
                build_fallback_strategy_hypotheses(
                    state
                )
            )

        except (ValidationError, ValueError):
            fallback_used = True
            source_type = ProvenanceSource.LOCAL_FALLBACK

            state.reasoning_notes.append(
                (
                    "Strategy hypothesis "
                    "generation failed. "
                    "Used local fallback "
                    "strategies."
                )
            )

            state.uncertainty_score += 0.1

            hypotheses = (
                build_fallback_strategy_hypotheses(
                    state
                )
            )

        state.strategy_hypotheses = (
            hypotheses.strategies
        )
        strategy_confidence = (
            sum(item.confidence for item in state.strategy_hypotheses) / max(len(state.strategy_hypotheses), 1)
        )
        record_provenance(
            state,
            artifact_key="strategy_hypotheses",
            stage="strategy_hypotheses",
            source_type=source_type,
            summary=(
                f"Generated {len(state.strategy_hypotheses)} strategy hypotheses."
            ),
            confidence=strategy_confidence,
            fallback_used=fallback_used,
            supporting_keys=[
                "business_profile",
                "requirements_spec",
                "behavioral_contexts",
                "retrieved_memories",
            ],
        )
        update_state_artifact(
            state,
            artifact_key="strategy_hypotheses",
            stage="strategy_hypotheses",
            source_type=source_type,
            confidence=strategy_confidence,
            summary="Behavioral strategy set ready for layout planning.",
            status="fallback" if fallback_used else "derived",
        )
        record_lineage(
            state,
            stage="strategy_hypotheses",
            decision="generated_competing_strategies",
            confidence=strategy_confidence,
            inputs=["business_profile", "requirements_spec", "behavioral_contexts", "retrieved_memories"],
            outputs=["strategy_hypotheses"],
            summary="Created competing behavior-led strategies.",
            fallback_used=fallback_used,
        )

        return state
    @register_node("design")
    def design_candidates_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:
        state.revision_iteration += 1
        fallback_used = False
        source_type = ProvenanceSource.EXTERNAL_MODEL
        tool_context = invoke_cognition_tools(
            state,
            "design_candidates",
        )

        prompt = build_design_candidates_prompt(
            state,
            tool_context,
        )

        try:

            raw = planner.generate_text(
                prompt,
                max_new_tokens=700,
            )

            parsed = parse_json_object(
                raw
            )

            normalized = (
                normalize_candidate_set_payload(
                    parsed,
                    state,
                )
            )

            candidates = (
                DesignCandidateSet
                .model_validate(
                    normalized
                )
            )

        except PlannerGenerationError as exc:
            fallback_used = True
            source_type = ProvenanceSource.HEURISTIC_FALLBACK

            logger.warning(
                "Design candidate fallback triggered: %s",
                exc,
            )

            state.reasoning_notes.append(
                (
                    "Design candidate generation "
                    "used deterministic fallback "
                    "because external reasoning "
                    "failed."
                )
            )

            state.uncertainty_score += 0.15

            candidates = (
                build_fallback_design_candidates(
                    state
                )
            )

        except (ValidationError, ValueError):
            fallback_used = True
            source_type = ProvenanceSource.LOCAL_FALLBACK

            state.reasoning_notes.append(
                (
                    "Design candidate generation "
                    "failed validation. Used "
                    "fallback design candidates."
                )
            )

            state.uncertainty_score += 0.1

            candidates = (
                build_fallback_design_candidates(
                    state
                )
            )
        state.design_candidates = (
            candidates.candidates
        )
        state.candidate_history.append(
            {
                "iteration": state.revision_iteration,
                "candidates": [
                    candidate.model_dump()
                    for candidate in candidates.candidates
                ],
            }
        )

        candidate_confidence = (
            sum(item.confidence for item in state.design_candidates) / max(len(state.design_candidates), 1)
        )
        record_provenance(
            state,
            artifact_key="design_candidates",
            stage="design_candidates",
            source_type=source_type,
            summary=(
                f"Prepared {len(state.design_candidates)} design candidates "
                f"for iteration {state.revision_iteration}."
            ),
            confidence=candidate_confidence,
            fallback_used=fallback_used,
            supporting_keys=[
                "strategy_hypotheses",
                "requirements_spec",
                "asset_extractions",
                "retrieved_memories",
            ],
        )
        update_state_artifact(
            state,
            artifact_key="design_candidates",
            stage="design_candidates",
            source_type=source_type,
            confidence=candidate_confidence,
            summary="Candidate layouts available for critique.",
            status="fallback" if fallback_used else "derived",
        )
        record_lineage(
            state,
            stage="design_candidates",
            decision="generated_layout_candidates",
            confidence=candidate_confidence,
            inputs=["strategy_hypotheses", "requirements_spec", "asset_extractions", "retrieved_memories"],
            outputs=["design_candidates", "candidate_history"],
            summary="Expanded strategies into renderable candidate layouts.",
            fallback_used=fallback_used,
        )

        return state
    @register_node("critique")
    def critique_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:
        

        cognition = (
            CognitiveStateAPI(state)
        )

        state.execution_trace.append(
            "critique"
        )

        state.node_visit_counts[
            "critique"
        ] = (
            state.node_visit_counts.get(
                "critique",
                0,
            )
            + 1
        )
        fallback_used = False
        source_type = ProvenanceSource.EXTERNAL_MODEL
        tool_context = invoke_cognition_tools(
            state,
            "critique",
        )
    
        prompt = build_critique_prompt(
            state,
            tool_context,
        )

        try:

            raw = planner.generate_text(
                prompt,
                max_new_tokens=650,
            )

            parsed = parse_json_object(
                raw
            )

            normalized = (
                normalize_critique_set_payload(
                    parsed
                )
            )

            critiques = (
                CritiqueReportSet
                .model_validate(
                    normalized
                )
            )

        except PlannerGenerationError as exc:
            fallback_used = True
            source_type = ProvenanceSource.HEURISTIC_FALLBACK

            logger.warning(
                "Critique fallback triggered: %s",
                exc,
            )

            state.reasoning_notes.append(
                (
                    "Critique generation used "
                    "deterministic fallback "
                    "because external reasoning "
                    "failed."
                )
            )

            state.uncertainty_score += 0.15

            critiques = CritiqueReportSet(
                critiques=[
                    build_fallback_critique(
                        candidate,
                        state,
                    )
                    for candidate in (
                        cognition.get_active_strategy_candidates()
                        or []
                    )
                ]
            )

        except (ValidationError, ValueError):
            fallback_used = True
            source_type = ProvenanceSource.LOCAL_FALLBACK

            state.reasoning_notes.append(
                (
                    "Critique generation failed "
                    "validation. Used fallback "
                    "critique."
                )
            )

            state.uncertainty_score += 0.1

            critiques = CritiqueReportSet(
                critiques=[
                    build_fallback_critique(
                        candidate,
                        state,
                    )
                    for candidate in (
                        cognition.get_active_strategy_candidates()
                        or []
                    )
                ]
            )

        state.critique_reports = (
            ensure_critiques(
                state,
                critiques.critiques,
            )
        )
        state.critique_history.append(
            {
                "iteration": state.revision_iteration,
                "critiques": [
                    critique.model_dump()
                    for critique in state.critique_reports
                ],
            }
        )

        critique_confidence = max(
            0.4,
            1.0 - min(state.uncertainty_score, 0.6),
        )
        record_provenance(
            state,
            artifact_key="critique_reports",
            stage="critique",
            source_type=source_type,
            summary=(
                f"Generated {len(state.critique_reports)} critique reports."
            ),
            confidence=critique_confidence,
            fallback_used=fallback_used,
            supporting_keys=[
                "design_candidates",
                "requirements_spec",
                "asset_extractions",
                "retrieved_memories",
            ],
        )
        update_state_artifact(
            state,
            artifact_key="critique_reports",
            stage="critique",
            source_type=source_type,
            confidence=critique_confidence,
            summary="Candidate critiques ready for evaluation.",
            status="fallback" if fallback_used else "derived",
        )
        record_lineage(
            state,
            stage="critique",
            decision="evaluated_candidates",
            confidence=critique_confidence,
            inputs=["design_candidates", "requirements_spec", "asset_extractions", "retrieved_memories"],
            outputs=["critique_reports", "critique_history"],
            summary="Compared candidate tradeoffs and weaknesses.",
            fallback_used=fallback_used,
        )

        state.agent_decisions[
            "critique"
        ] = AgentDecision(

            confidence=0.68,

            exploration_required=(
                cognition.get_uncertainty_level() > 0.65
            ),

            simulation_required=True,

            recommend_revision=(
                cognition.get_uncertainty_level() > 0.75
            ),

            reasoning=[
                (
                    "Critique agent evaluated "
                    "candidate stability and "
                    "exploration sufficiency."
                )
            ],
        )
        return state
    
    @register_node("reflection")
    def reflection_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:
         
        cognition = (CognitiveStateAPI(state))
        
        state.execution_trace.append(
            "reflection"
        )

        state.node_visit_counts[
            "reflection"
        ] = (
            state.node_visit_counts.get(
                "reflection",
                0,
            )
            + 1
        )
        fallback_used = False
        source_type = ProvenanceSource.EXTERNAL_MODEL
        tool_context = invoke_cognition_tools(
            state,
            "reflection",
        )

        prompt = build_reflection_prompt(
            state,
            tool_context,
        )

        try:

            reflection = (
                planner.generate_model(
                    prompt,
                    ReflectionReport,
                )
            )

        except PlannerGenerationError as exc:
            fallback_used = True
            source_type = ProvenanceSource.HEURISTIC_FALLBACK

            logger.warning(
                "Reflection fallback triggered: %s",
                exc,
            )

            state.reasoning_notes.append(
                (
                    "Reflection generation used "
                    "deterministic fallback "
                    "because external reasoning "
                    "failed."
                )
            )

            state.uncertainty_score += 0.15

            reflection = (
                build_fallback_reflection_report(
                    state
                )
            )

        except (ValidationError, ValueError):
            fallback_used = True
            source_type = ProvenanceSource.LOCAL_FALLBACK

            state.reasoning_notes.append(
                (
                    "Reflection generation failed. "
                    "Used local fallback reflection."
                )
            )

            state.uncertainty_score += 0.1

            reflection = (
                build_fallback_reflection_report(
                    state
                )
            )

        state.reflection_report = (
            reflection
        )

        state.reasoning_notes.append(
            (
                "Reflection agent evaluated "
                "planning process quality."
            )
        )

        state.reasoning_notes.append(
            (
                f"Exploration quality: "
                f"{reflection.exploration_quality}/10 | "
                f"Strategic diversity: "
                f"{reflection.strategic_diversity}/10 | "
                f"Critique depth: "
                f"{reflection.critique_depth}/10"
            )
        )

        state.reasoning_notes.append(
            (
                f"Reasoning quality: "
                f"{reflection.reasoning_quality}/10 | "
                f"Convergence risk: "
                f"{reflection.convergence_risk}/10"
            )
        )

        if reflection.observations:
            state.reasoning_notes.extend(
                [
                    f"Reflection observation: {obs}"
                    for obs in reflection.observations
                ]
            )

        if reflection.improvement_actions:
            state.reasoning_notes.extend(
                [
                    f"Reflection action: {action}"
                    for action in reflection.improvement_actions
                ]
            )

        if (
            reflection.should_expand_exploration
        ):
            state.reasoning_notes.append(
                (
                    "Reflection agent detected "
                    "insufficient exploration depth "
                    "and requested broader "
                    "strategic search."
                )
            )
        else:
            state.reasoning_notes.append(
                (
                    "Reflection agent determined "
                    "strategic exploration depth "
                    "is sufficient."
                )
            )

        reflection_confidence = max(
            0.45,
            1.0 - (reflection.convergence_risk / 12.0),
        )
        record_provenance(
            state,
            artifact_key="reflection_report",
            stage="reflection",
            source_type=source_type,
            summary="Evaluated planning quality and convergence risk.",
            confidence=reflection_confidence,
            fallback_used=fallback_used,
            supporting_keys=["candidate_history", "critique_history", "reasoning_notes"],
        )
        update_state_artifact(
            state,
            artifact_key="reflection_report",
            stage="reflection",
            source_type=source_type,
            confidence=reflection_confidence,
            summary="Reflection report updated.",
            status="fallback" if fallback_used else "derived",
        )
        record_lineage(
            state,
            stage="reflection",
            decision="evaluated_planning_process",
            confidence=reflection_confidence,
            inputs=["candidate_history", "critique_history", "reasoning_notes"],
            outputs=["reflection_report"],
            summary="Reviewed exploration sufficiency and convergence risk.",
            fallback_used=fallback_used,
        )

        state.cognitive_health = (
            CognitiveHealthReport(

                exploration_quality=(
                    cognition
                    .get_reasoning_diversity()
                ),

                reasoning_diversity=(
                    cognition
                    .get_reasoning_diversity()
                ),

                convergence_risk=(
                    cognition
                    .get_convergence_risk()
                ),

                critique_depth=0.74,

                hallucination_risk=(
                    cognition
                    .get_hallucination_risk()
                ),

                cognition_stability=(
                    1.0
                    -
                    cognition
                    .get_convergence_risk()
                ),

                notes=[
                    (
                        "Meta-cognitive evaluation "
                        "computed from runtime state."
                    )
                ],
            )
        )
        return state
    @register_node("debate")
    def debate_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:
        fallback_used = False
        source_type = ProvenanceSource.EXTERNAL_MODEL
        tool_context = invoke_cognition_tools(
            state,
            "debate",
        )

        prompt = build_debate_prompt(
            state,
            tool_context,
        )

        try:

            outcome = (
                planner.generate_model(
                    prompt,
                    DebateOutcome,
                )
            )

        except PlannerGenerationError as exc:
            fallback_used = True
            source_type = ProvenanceSource.HEURISTIC_FALLBACK

            logger.warning(
                "Debate fallback triggered: %s",
                exc,
            )

            state.reasoning_notes.append(
                (
                    "Debate generation used "
                    "deterministic fallback "
                    "because external reasoning "
                    "failed."
                )
            )

            state.uncertainty_score += 0.15

            outcome = (
                build_fallback_debate_outcome(
                    state
                )
            )

        except (ValidationError, ValueError):
            fallback_used = True
            source_type = ProvenanceSource.LOCAL_FALLBACK

            state.reasoning_notes.append(
                (
                    "Debate generation failed. "
                    "Used local fallback debate."
                )
            )

            state.uncertainty_score += 0.1

            outcome = (
                build_fallback_debate_outcome(
                    state
                )
            )

        state.debate_outcome = (
            outcome
        )

        state.reasoning_notes.append(
            (
                "Debate agent compared "
                "candidate strategies directly."
            )
        )

        state.reasoning_notes.append(
            (
                f"Winning candidate: "
                f"{outcome.winning_candidate_id}"
            )
        )

        state.reasoning_notes.extend(
            [
                f"Debate insight: {obs}"
                for obs in (
                    outcome
                    .strategic_observations
                )
            ]
        )

        record_provenance(
            state,
            artifact_key="debate_outcome",
            stage="debate",
            source_type=source_type,
            summary=f"Selected winning candidate {outcome.winning_candidate_id}.",
            confidence=outcome.confidence,
            fallback_used=fallback_used,
            supporting_keys=["strategy_hypotheses", "design_candidates", "critique_reports"],
        )
        update_state_artifact(
            state,
            artifact_key="debate_outcome",
            stage="debate",
            source_type=source_type,
            confidence=outcome.confidence,
            summary="Winning candidate selected through debate.",
            status="fallback" if fallback_used else "derived",
        )
        record_lineage(
            state,
            stage="debate",
            decision="selected_candidate_direction",
            confidence=outcome.confidence,
            inputs=["strategy_hypotheses", "design_candidates", "critique_reports"],
            outputs=["debate_outcome"],
            summary="Compared candidates and chose the strongest direction.",
            fallback_used=fallback_used,
        )

        return state

    @register_node("simulation")
    def simulation_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:

        state.execution_trace.append(
            "simulation"
        )

        state.node_visit_counts[
            "simulation"
        ] = (
            state.node_visit_counts.get(
                "simulation",
                0,
            )
            + 1
        )
        fallback_used = False
        source_type = ProvenanceSource.EXTERNAL_MODEL
        tool_context = invoke_cognition_tools(
            state,
            "simulation",
        )

        prompt = build_simulation_prompt(
            state,
            tool_context,
        )

        try:

            simulation = (
                planner.generate_model(
                    prompt,
                    SimulationReport,
                )
            )

        except PlannerGenerationError as exc:
            fallback_used = True
            source_type = ProvenanceSource.HEURISTIC_FALLBACK

            logger.warning(
                "Simulation fallback triggered: %s",
                exc,
            )

            state.reasoning_notes.append(
                (
                    "Simulation generation used "
                    "deterministic fallback "
                    "because external reasoning "
                    "failed."
                )
            )

            state.uncertainty_score += 0.15

            simulation = (
                build_fallback_simulation_report(
                    state
                )
            )

        except (ValidationError, ValueError):
            fallback_used = True
            source_type = ProvenanceSource.LOCAL_FALLBACK

            state.reasoning_notes.append(
                (
                    "Simulation generation failed. "
                    "Used local fallback simulation."
                )
            )

            state.uncertainty_score += 0.1

            simulation = (
                build_fallback_simulation_report(
                    state
                )
            )

        state.simulation_report = (
            simulation
        )

        state.reasoning_notes.append(
            (
                "Simulation agent executed "
                "behavioral workflow testing."
            )
        )

        state.reasoning_notes.append(
            (
                f"Overall realism score: "
                f"{simulation.overall_realism_score}/10"
            )
        )

        for workflow_simulation in (
            simulation.simulations
        ):

            state.reasoning_notes.append(
                (
                    "Simulation persona: "
                    f"{workflow_simulation.persona}"
                )
            )

            state.reasoning_notes.append(
                (
                    "Simulation goal: "
                    f"{workflow_simulation.goal}"
                )
            )

            state.reasoning_notes.append(
                (
                    "Simulation journey: "
                    f"{workflow_simulation.journey_summary}"
                )
            )

            if (
                workflow_simulation
                .friction_points
            ):

                state.reasoning_notes.extend(
                    [
                        (
                            "Simulation friction: "
                            f"{issue}"
                        )
                        for issue in (
                            workflow_simulation
                            .friction_points
                        )
                    ]
                )

            if (
                workflow_simulation
                .trust_observations
            ):

                state.reasoning_notes.extend(
                    [
                        (
                            "Simulation trust: "
                            f"{obs}"
                        )
                        for obs in (
                            workflow_simulation
                            .trust_observations
                        )
                    ]
                )

            if (
                workflow_simulation
                .confusion_points
            ):

                state.reasoning_notes.extend(
                    [
                        (
                            "Simulation confusion: "
                            f"{issue}"
                        )
                        for issue in (
                            workflow_simulation
                            .confusion_points
                        )
                    ]
                )

            if (
                workflow_simulation
                .conversion_barriers
            ):

                state.reasoning_notes.extend(
                    [
                        (
                            "Simulation barrier: "
                            f"{barrier}"
                        )
                        for barrier in (
                            workflow_simulation
                            .conversion_barriers
                        )
                    ]
                )

            state.reasoning_notes.append(
                (
                    "Simulation success: "
                    f"{workflow_simulation.successful}"
                )
            )

            state.reasoning_notes.append(
                (
                    "Simulation realism: "
                    f"{workflow_simulation.realism_score}/10"
                )
            )

        if simulation.systemic_issues:

            state.reasoning_notes.extend(
                [
                    (
                        "Simulation issue: "
                        f"{issue}"
                    )
                    for issue in (
                        simulation
                        .systemic_issues
                    )
                ]
            )

        if (
            simulation
            .recommended_improvements
        ):

            state.reasoning_notes.extend(
                [
                    (
                        "Simulation improvement: "
                        f"{improvement}"
                    )
                    for improvement in (
                        simulation
                        .recommended_improvements
                    )
                ]
            )

        simulation_confidence = max(
            0.45,
            simulation.overall_realism_score / 10.0,
        )
        record_provenance(
            state,
            artifact_key="simulation_report",
            stage="simulation",
            source_type=source_type,
            summary=f"Simulated user realism score {simulation.overall_realism_score}/10.",
            confidence=simulation_confidence,
            fallback_used=fallback_used,
            supporting_keys=["design_candidates", "debate_outcome", "critique_history"],
        )
        update_state_artifact(
            state,
            artifact_key="simulation_report",
            stage="simulation",
            source_type=source_type,
            confidence=simulation_confidence,
            summary="Workflow simulation completed.",
            status="fallback" if fallback_used else "derived",
        )
        record_lineage(
            state,
            stage="simulation",
            decision="simulated_candidate_realism",
            confidence=simulation_confidence,
            inputs=["design_candidates", "debate_outcome", "critique_history"],
            outputs=["simulation_report"],
            summary="Tested behavioral realism of planned flows.",
            fallback_used=fallback_used,
        )

        return state
    
    @register_node("revise")
    def revise_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:
        fallback_used = False
        source_type = ProvenanceSource.EXTERNAL_MODEL
        tool_context = invoke_cognition_tools(
            state,
            "revision",
        )

        prompt = build_revision_prompt(
            state,
            tool_context,
        )

        raw = planner.generate_text(
            prompt
        )

        try:
            parsed = parse_json_object(
                raw
            )

            normalized = normalize_design_spec_payload(
                parsed,
                state,
            )

            state.design_spec = (
                DesignSpec.model_validate(
                    normalized
                )
            )

            if (
                state.finalization_decision
                and state.finalization_decision.finalize_now
                and state.finalization_decision.readiness_score >= 0.72
                and state.design_spec.chosen_candidate_id
                != state.finalization_decision.selected_candidate_id
            ):
                fallback_used = True
                source_type = ProvenanceSource.GRAPH_ROUTER
                state.reasoning_notes.append(
                    (
                        "Revision output disagreed with the explicit finalization authority. "
                        "Applying authority-selected best-so-far candidate."
                    )
                )
                state.design_spec = (
                    DesignSpec.model_validate(
                        build_fallback_design_spec(
                            state
                        )
                    )
                )

        except Exception:
            fallback_used = True
            source_type = ProvenanceSource.LOCAL_FALLBACK
            state.design_spec = (
                DesignSpec.model_validate(
                    build_fallback_design_spec(
                        state
                    )
                )
            )

        state.reasoning_notes.append(
            (
                f"Final design selected after "
                f"{state.revision_iteration} "
                f"planning iterations."
            )
        )

        state.reasoning_notes.append(
            (
                "Planning completed with "
                f"uncertainty score "
                f"{round(state.uncertainty_score, 2)}."
            )
        )

        final_confidence = max(
            0.45,
            1.0 - min(state.uncertainty_score, 0.55),
        )
        record_provenance(
            state,
            artifact_key="design_spec",
            stage="revise",
            source_type=source_type,
            summary=f"Finalized design spec using candidate {state.design_spec.chosen_candidate_id}.",
            confidence=final_confidence,
            fallback_used=fallback_used,
            supporting_keys=["strategy_hypotheses", "design_candidates", "critique_reports", "simulation_report"],
        )
        update_state_artifact(
            state,
            artifact_key="design_spec",
            stage="revise",
            source_type=source_type,
            confidence=final_confidence,
            summary="Final design specification ready for rendering.",
            status="fallback" if fallback_used else "finalized",
        )
        record_lineage(
            state,
            stage="revise",
            decision="finalized_design_spec",
            confidence=final_confidence,
            inputs=["strategy_hypotheses", "design_candidates", "critique_reports", "simulation_report"],
            outputs=["design_spec"],
            summary="Synthesized final design from the surviving candidate evidence.",
            fallback_used=fallback_used,
        )

        return state

    def critique_router(
        state: WebsiteAgentState,
    ) -> str:
        # Hard revision cap to prevent endless loops if routing keeps requesting regeneration.
        # Note: design_candidates_node increments revision_iteration.
        MAX_REVISION_ITERATIONS = 3
        COMMIT_REVISION_ITERATION = 2
        sim_score = (
            state.simulation_report.overall_realism_score
            if state.simulation_report
            else 0
        )
        debate_conf = (
            state.debate_outcome.confidence
            if state.debate_outcome
            else 0.0
        )
        reflection_expand = bool(
            state.reflection_report
            and state.reflection_report.should_expand_exploration
        )
        if state.revision_iteration >= MAX_REVISION_ITERATIONS:
            state.reasoning_notes.append(
                (
                    "Reached maximum revision iterations "
                    f"({MAX_REVISION_ITERATIONS}). Proceeding to final synthesis."
                )
            )
            set_finalization_decision(
                state,
                authority="revision_cap",
                reason="Reached maximum revision iterations and must finalize best-so-far output.",
                supporting_signals=[
                    f"revision_iteration={state.revision_iteration}",
                ],
            )
            return "revise"

        weak_candidates = 0
        average_scores = []

        for critique in (
            state.critique_reports
        ):
            avg = (
                sum(
                    score.score
                    for score in critique.scores
                )
                / len(critique.scores)
            )
            average_scores.append(avg)

            if avg < 7:
                weak_candidates += 1

        overall_average = (
            sum(average_scores)
            / max(len(average_scores), 1)
        )

        behavioral_issues = (
            evaluate_behavioral_coherence(
                state
            )
        )

        good_enough = (
            overall_average >= 7.0
            and sim_score >= 7
            and debate_conf >= 0.6
        )

        if behavioral_issues:

            state.reasoning_notes.extend(
                [
                    (
                        "Behavioral validation: "
                        + issue
                    )
                    for issue in behavioral_issues
                ]
            )

            if (
                state.revision_iteration < 2
            ):

                state.reasoning_notes.append(
                    (
                        "Behavioral coherence "
                        "validation failed. "
                        "Regenerating candidates."
                    )
                )

                return "design_candidates"

        if good_enough:
            state.reasoning_notes.append(
                (
                    "Convergence threshold met "
                    f"(avg={round(overall_average, 2)}, "
                    f"sim={sim_score}, "
                    f"debate={round(debate_conf, 2)}). "
                    "Finalizing best available plan."
                )
            )
            set_finalization_decision(
                state,
                authority="convergence_threshold",
                reason="Convergence threshold met with sufficiently strong critique, simulation, and debate signals.",
                supporting_signals=[
                    f"overall_average={round(overall_average, 2)}",
                    f"simulation_score={sim_score}",
                    f"debate_confidence={round(debate_conf, 2)}",
                ],
            )
            return "revise"

        if (
            external_planner_unhealthy(
                planner
            )
            and state.revision_iteration >= 1
        ):
            state.reasoning_notes.append(
                (
                    "External planner is degraded. "
                    "Avoiding further regeneration and finalizing best-so-far output."
                )
            )
            set_finalization_decision(
                state,
                authority="planner_health_guard",
                reason="External planner health is degraded after prior exploration, so the system is finalizing the strongest available candidate.",
                supporting_signals=[
                    f"failure_count={getattr(planner, 'failure_count', 0)}",
                    f"revision_iteration={state.revision_iteration}",
                ],
            )
            return "revise"

        if (
            state.revision_iteration >= COMMIT_REVISION_ITERATION
            and overall_average >= 6.6
            and sim_score >= 6
        ):
            state.reasoning_notes.append(
                (
                    "Good-enough threshold reached after repeated exploration "
                    f"(avg={round(overall_average, 2)}, sim={sim_score}). "
                    "Committing best-so-far candidate."
                )
            )
            set_finalization_decision(
                state,
                authority="good_enough_commit",
                reason="Repeated exploration produced a good-enough candidate, so the system is committing best-so-far instead of continuing to search.",
                supporting_signals=[
                    f"overall_average={round(overall_average, 2)}",
                    f"simulation_score={sim_score}",
                    f"revision_iteration={state.revision_iteration}",
                ],
            )
            return "revise"

        if (
            state.simulation_report
            and state.simulation_report.overall_realism_score < 6
            and state.revision_iteration < COMMIT_REVISION_ITERATION
        ):
            state.reasoning_notes.append(
                (
                    "Simulation realism too low. "
                    "Regenerating workflows."
                )
            )
            return "design_candidates"

        if (
            state.debate_outcome
            and state.debate_outcome.confidence < 0.55
            and state.revision_iteration < COMMIT_REVISION_ITERATION
        ):
            state.reasoning_notes.append(
                (
                    "Debate confidence low. "
                    "Expanding strategic search."
                )
            )
            return "design_candidates"

        if (
            reflection_expand
            and state.revision_iteration < COMMIT_REVISION_ITERATION
        ):
            state.reasoning_notes.append(
                (
                    "Reflection agent requested "
                    "expanded strategic exploration."
                )
            )
            return "design_candidates"

        threshold = (
            1
            if state.uncertainty_score > 0.35
            else 0
        )

        if (
            weak_candidates > threshold
        ):
            state.reasoning_notes.append(
                (
                    "Critique quality insufficient "
                    f"(avg={round(overall_average, 2)}). "
                    "Regenerating candidates "
                    "with deeper exploration."
                )
            )
            return "design_candidates"

        state.reasoning_notes.append(
            (
                "Critique quality acceptable "
                f"(avg={round(overall_average, 2)}). "
                "Proceeding to revision "
                "and synthesis."
            )
        )
        set_finalization_decision(
            state,
            authority="synthesis_gate",
            reason="Critique quality is acceptable and no stronger reason to continue exploration remains.",
            supporting_signals=[
                f"overall_average={round(overall_average, 2)}",
                f"weak_candidates={weak_candidates}",
            ],
        )

        return "revise"

    def requirements_router(
        state: WebsiteAgentState,
    ) -> str:

        state.node_visit_counts[
            "requirements"
        ] = (
            state.node_visit_counts.get(
                "requirements",
                0,
            )
            + 1
        )

        if (
            state.node_visit_counts[
                "requirements"
            ]
            >= 3
        ):

            state.reasoning_notes.append(
                (
                    "Requirements routing depth exceeded. "
                    "Proceeding to strategy generation."
                )
            )

            state.execution_trace.append(
                (
                    "requirements -> strategy_hypotheses "
                    "(loop protection)"
                )
            )

            return "strategy_hypotheses"

        if (
            state.uncertainty_score > 0.45
        ):

            state.reasoning_notes.append(
                (
                    "High uncertainty detected. "
                    "Routing to memory retrieval."
                )
            )

            state.execution_trace.append(
                (
                    "requirements -> memory_retrieval"
                )
            )

            return "memory_retrieval"

        state.reasoning_notes.append(
            (
                "Requirements confidence acceptable. "
                "Proceeding to strategy generation."
            )
        )

        state.execution_trace.append(
            (
                "requirements -> strategy_hypotheses"
            )
        )

        return "strategy_hypotheses"

    def strategy_router(
        state: WebsiteAgentState,
    ) -> str:

        state.node_visit_counts[
            "strategy_hypotheses"
        ] = (
            state.node_visit_counts.get(
                "strategy_hypotheses",
                0,
            )
            + 1
        )

        if (
            state.node_visit_counts[
                "strategy_hypotheses"
            ]
            >= 3
        ):

            state.reasoning_notes.append(
                (
                    "Maximum strategy exploration depth reached. "
                    "Proceeding to design generation."
                )
            )

            state.execution_trace.append(
                (
                    "strategy_hypotheses -> design_candidates "
                    "(loop protection)"
                )
            )

            return "design_candidates"

        if (
            state.uncertainty_score > 0.6
        ):

            state.reasoning_notes.append(
                (
                    "Strategy uncertainty remains high. "
                    "Exploring additional strategy hypotheses."
                )
            )

            state.execution_trace.append(
                (
                    "strategy_hypotheses -> strategy_hypotheses"
                )
            )

            return "strategy_hypotheses"

        state.reasoning_notes.append(
            (
                "Strategy confidence acceptable. "
                "Proceeding to design candidates."
            )
        )

        state.execution_trace.append(
            (
                "strategy_hypotheses -> design_candidates"
            )
        )

        return "design_candidates"

    def critique_stage_router(
        state: WebsiteAgentState,
    ) -> str:
        
        decision = (
            state.agent_decisions.get(
                "critique"
            )
        )

        state.node_visit_counts[
            "critique"
        ] = (
            state.node_visit_counts.get(
                "critique",
                0,
            )
            + 1
        )

        critique_count = (
            state.node_visit_counts[
                "critique"
            ]
        )

        if critique_count >= 4:

            state.reasoning_notes.append(
                (
                    "Critique recursion limit reached. "
                    "Proceeding to synthesis."
                )
            )

            state.execution_trace.append(
                "critique -> revise (loop protection)"
            )

            return "revise"

        if (decision and decision.recommend_revision):

            state.reasoning_notes.append(
                (
                    "Critical uncertainty detected during critique. "
                    "Returning to strategy exploration."
                )
            )

            state.execution_trace.append(
                (
                    "critique -> strategy_hypotheses"
                )
            )

            return "strategy_hypotheses"

        state.reasoning_notes.append(
            (
                "Critique completed successfully. "
                "Proceeding to reflection."
            )
        )

        state.execution_trace.append(
            (
                "critique -> reflection"
            )
        )

        return "reflection"

    def reflection_router(
        state: WebsiteAgentState,
    ) -> str:
        if not state.reflection_report:
            return "debate"

        reflection_conf = artifact_confidence(
            state,
            "reflection_report",
            fallback=0.55,
        )

        if (
            state.reflection_report.should_expand_exploration
            and state.revision_iteration < 2
            and reflection_conf >= 0.55
        ):
            add_reasoning_note(
                state,
                "Reflection requested broader exploration with sufficient confidence. Returning to candidate generation.",
            )
            return "design_candidates"

        if (
            reflection_conf < 0.5
            and external_planner_unhealthy(
                planner
            )
        ):
            add_reasoning_note(
                state,
                "Reflection confidence is weak and planner health is poor. Skipping debate and moving directly to simulation.",
            )
            return "simulation"

        return "debate"

    def debate_router(
        state: WebsiteAgentState,
    ) -> str:
        if not state.debate_outcome:
            return "simulation"

        if (
            state.debate_outcome.confidence >= 0.8
            and state.uncertainty_score <= 0.28
        ):
            add_reasoning_note(
                state,
                "Debate produced a strong winner under low uncertainty. Skipping simulation and moving to revision.",
            )
            set_finalization_decision(
                state,
                authority="debate_router",
                reason="Debate produced a strong winner under low uncertainty, so the system is finalizing without additional simulation.",
                supporting_signals=[
                    f"debate_confidence={round(state.debate_outcome.confidence, 2)}",
                    f"winning_candidate={state.debate_outcome.winning_candidate_id}",
                    f"uncertainty={round(state.uncertainty_score, 2)}",
                ],
            )
            return "revise"

        if (
            artifact_used_fallback(
                state,
                "debate_outcome",
            )
            and state.revision_iteration >= 1
        ):
            add_reasoning_note(
                state,
                "Debate relied on fallback reasoning after prior exploration. Running simulation before finalization.",
            )

        return "simulation"

    graph = StateGraph(
        WebsiteAgentState
    )
    graph.add_node(
        "debate",
        debate_node,
    )

    graph.add_node(
        "simulation",
        simulation_node,
    )

    graph.add_node(
        "business_profile",
        business_profile_node,
    )

    graph.add_node(
        "memory_retrieval",
        memory_retrieval_node,
    )

    graph.add_node(
        "requirements",
        requirements_node,
    )

    graph.add_node(
        "strategy_hypotheses",
        strategy_hypothesis_node,
    )

    graph.add_node(
        "design_candidates",
        design_candidates_node,
    )

    graph.add_node(
        "critique",
        critique_node,
    )

    graph.add_node(
        "reflection",
        reflection_node,
    )

    graph.add_node(
        "revise",
        revise_node,
    )

    graph.add_edge(
        START,
        "business_profile",
    )

    graph.add_edge(
        "business_profile",
        "memory_retrieval",
    )

    graph.add_edge(
        "memory_retrieval",
        "requirements",
    )

    graph.add_conditional_edges(
        "requirements",
        requirements_router,
    )

    graph.add_conditional_edges(
        "strategy_hypotheses",
        strategy_router,
    )

    graph.add_edge(
        "design_candidates",
        "critique",
    )

    graph.add_conditional_edges(
        "critique",
        critique_stage_router,
    )

    graph.add_conditional_edges(
        "reflection",
        reflection_router,
    )

    graph.add_conditional_edges(
        "debate",
        debate_router,
    )

    graph.add_conditional_edges(
        "simulation",
        critique_router,
    )

    graph.add_edge(
        "revise",
        END,
    )

    return graph.compile()


def serialize_graph_event(
    event: dict,
) -> dict:

    serialized = {}

    for key, value in event.items():

        if hasattr(value, "model_dump"):
            serialized[key] = (
                value.model_dump()
            )

        elif isinstance(value, list):

            serialized[key] = [
                item.model_dump()
                if hasattr(item, "model_dump")
                else item
                for item in value
            ]

        else:
            serialized[key] = value

    return serialized


def _state_cycle_signature(state: WebsiteAgentState) -> tuple:
    """
    Lightweight signature to detect obvious cycles where the graph keeps regenerating
    without meaningful progress.
    """
    try:
        vertical = (
            state.business_profile.vertical.value
            if state.business_profile
            else "unknown"
        )
    except Exception:
        vertical = "unknown"

    # Use revision iteration + key confidence/quality signals if present.
    sim_score = (
        state.simulation_report.overall_realism_score
        if state.simulation_report
        else None
    )
    debate_conf = (
        state.debate_outcome.confidence
        if state.debate_outcome
        else None
    )
    expand = (
        state.reflection_report.should_expand_exploration
        if state.reflection_report
        else None
    )
    # Structure proxy: number of candidates and critiques.
    cand_count = len(state.design_candidates or [])
    critique_count = len(state.critique_reports or [])

    return (
        vertical,
        state.revision_iteration,
        sim_score,
        debate_conf,
        expand,
        cand_count,
        critique_count,
    )


def run_agent_graph(
    initial_state: dict[str, Any],
    planner: ModelJsonPlanner,
) -> dict[str, Any]:

    state = WebsiteAgentState(
        **initial_state
    )

    graph = build_agent_graph(
        planner
    )

    events = []

    final_state = None

    # Global termination guards:
    # - Max number of streamed updates
    # - Loop signature consecutive repeat cap, evaluated only at cycle checkpoints
    #   so normal within-pass node updates do not look like a planning loop.
    MAX_STREAM_UPDATES = 60
    MAX_SIGNATURE_REPEATS = 4

    current_state = state

    last_signature: tuple | None = None

    consecutive_signature_repeats = 0

    for idx, event in enumerate(
        graph.stream(
            state,
            stream_mode="updates",
        ),
        start=1,
    ):

        if idx > MAX_STREAM_UPDATES:

            raise RuntimeError(
                f"graph exceeded MAX_STREAM_UPDATES={MAX_STREAM_UPDATES} without terminating"
            )

        serialized = (
            serialize_graph_event(
                event
            )
        )

        events.append(
            serialized
        )

        merged = current_state.model_dump()

        if isinstance(
            serialized,
            dict,
        ):

            for node_update in (
                serialized.values()
            ):

                if isinstance(
                    node_update,
                    dict,
                ):

                    merged.update(
                        node_update
                    )

        current_state = (
            WebsiteAgentState.model_validate(
                merged
            )
        )

        final_state = current_state

        checkpoint_nodes = {
            "simulation",
            "design_candidates",
        }

        event_nodes = {
            key
            for key in serialized.keys()
            if isinstance(
                key,
                str,
            )
        }

        if (
            event_nodes
            & checkpoint_nodes
        ):

            try:

                sig = (
                    _state_cycle_signature(
                        current_state
                    )
                )

            except Exception:

                sig = None

            if sig is not None:

                if sig == last_signature:

                    consecutive_signature_repeats += 1

                else:

                    last_signature = sig

                    consecutive_signature_repeats = 1

                if (
                    consecutive_signature_repeats
                    >= MAX_SIGNATURE_REPEATS
                ):

                    raise RuntimeError(
                        "graph appears to be stuck in a planning loop (cycle signature repeated "
                        f"{MAX_SIGNATURE_REPEATS} times at cycle checkpoints)."
                    )

    try:

        validated = (
            WebsiteAgentState.model_validate(
                final_state
            )
        )

        print(
            "\nEXECUTION TRACE:\n",
            validated.execution_trace,
        )

        print(
            "\nNODE VISIT COUNTS:\n",
            validated.node_visit_counts,
        )

        print(
            "\nDEBUG PAYLOAD:\n",
            {
                "execution_trace":
                    validated.execution_trace,
                "node_visit_counts":
                    validated.node_visit_counts,
            }
        )

        return {
            "final_state":
                validated.model_dump(),

            "events":
                events,

            "debug": {
                "execution_trace":
                    validated.execution_trace,

                "node_visit_counts":
                    validated.node_visit_counts,
            },
        }

    except ValidationError as exc:

        raise RuntimeError(
            f"graph returned invalid state: {exc}"
        ) from exc



def build_business_profile_prompt(state: WebsiteAgentState) -> str:
    return dedent(
        f"""
        You are the Business Understanding Agent for an autonomous AI web agency.

        Build a BusinessProfileInference JSON object only.

        Allowed vertical values: {[key.value for key in VERTICAL_RULEBOOKS.keys()]} plus "unknown".
        Allowed risk levels: ["standard", "regulated"].

        Business input:
        {state.business_input}

        Asset evidence:
        {serialize_asset_extractions(state.asset_extractions)}

        Requirements:
        - infer only: vertical, subtype, risk_level, audience, evidence_summary, confidence
        - do not repeat name, location, or goal
        - evidence_summary must be a list of short strings, not objects
        - confidence must be a numeric value between 0 and 1
        - do not invent facts not supported by input
        """
    ).strip()


def compact_business_profile_context(state: WebsiteAgentState) -> dict[str, Any]:
    if not state.business_profile:
        return {}
    profile = state.business_profile
    return {
        "name": profile.name,
        "location": profile.location,
        "goal": profile.goal,
        "vertical": profile.vertical.value,
        "subtype": profile.subtype,
        "risk_level": profile.risk_level.value,
        "audience": profile.audience[:4],
        "confidence": round(profile.confidence, 2),
    }


def compact_requirements_context(state: WebsiteAgentState) -> dict[str, Any]:
    if not state.requirements_spec:
        return {}
    requirements = state.requirements_spec
    return {
        "pages": [page.value for page in requirements.required_pages[:6]],
        "workflows": [workflow.value for workflow in requirements.required_workflows[:4]],
        "trust": requirements.trust_requirements[:5],
        "conversion": requirements.conversion_priorities[:5],
        "missing_information": requirements.missing_information[:4],
    }

def compact_behavioral_context(
    state: WebsiteAgentState,
) -> list[dict]:

    return [
        context.model_dump()
        for context in (
            state.behavioral_contexts
            or []
        )
    ]

def compact_behavioral_blend(
    state: WebsiteAgentState,
) -> dict:

    if not state.behavioral_blend:
        return {}

    return (
        state.behavioral_blend
        .model_dump()
    )


def compact_strategy_context(state: WebsiteAgentState) -> list[dict[str, Any]]:
    return [
        {
            "id": strategy.strategy_id,
            "name": strategy.name,
            "thesis": strategy.core_thesis,
            "target_behavior": strategy.target_behavior,
            "strengths": strategy.strengths[:3],
            "risks": strategy.risks[:3],
            "confidence": round(strategy.confidence, 2),
        }
        for strategy in (state.strategy_hypotheses or [])[:3]
    ]


def compact_candidate_context(state: WebsiteAgentState) -> list[dict[str, Any]]:
    compacted = []
    for candidate in (state.design_candidates or [])[:3]:
        compacted.append(
            {
                "id": candidate.candidate_id,
                "rationale": candidate.rationale,
                "primary_action": candidate.primary_action.label,
                "pages": [
                    {
                        "page_type": page.page_type.value,
                        "sections": [
                            section.type.value
                            for section in page.sections[:5]
                        ],
                    }
                    for page in candidate.pages[:4]
                ],
                "confidence": round(candidate.confidence, 2),
            }
        )
    return compacted


def compact_critique_context(state: WebsiteAgentState) -> list[dict[str, Any]]:
    compacted = []
    for critique in (state.critique_reports or [])[:3]:
        avg_score = round(
            sum(score.score for score in critique.scores) / max(len(critique.scores), 1),
            2,
        )
        compacted.append(
            {
                "candidate_id": critique.candidate_id,
                "summary": critique.summary,
                "average_score": avg_score,
                "strengths": critique.strengths[:3],
                "weaknesses": critique.weaknesses[:3],
                "revision_instructions": critique.revision_instructions[:4],
            }
        )
    return compacted


def compact_history(history: list[dict[str, Any]], limit: int = 1) -> list[dict[str, Any]]:
    return history[-limit:] if history else []


def compact_reasoning_notes(state: WebsiteAgentState, limit: int = 6) -> list[str]:
    return (state.reasoning_notes or [])[-limit:]


def compact_memory_context(
    state: WebsiteAgentState,
) -> list[dict[str, Any]]:
    return [
        {
            "id": memory.memory_id,
            "category": memory.category,
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


def build_requirements_prompt(
    state: WebsiteAgentState,
    tool_context: dict[str, Any] | None = None,
) -> str:
    assert state.business_profile is not None
    rulebook = VERTICAL_RULEBOOKS.get(state.business_profile.vertical)
    tool_context = tool_context or {}
    return dedent(
        f"""
        You are the Requirements Agent.

        Build a RequirementsSpec JSON object only.

        Current uncertainty score:
        {state.uncertainty_score}

        Business snapshot tool:
        {tool_context.get("business_snapshot", {})}

        Vertical rulebook guidance:
        {rulebook}

        Asset evidence tool:
        {tool_context.get("asset_evidence", {})}

        Memory guidance tool:
        {tool_context.get("memory_guidance", {})}

        Process health tool:
        {tool_context.get("process_health", {})}

        Requirements:
        - choose required pages from the allowed enum values
        - choose required workflows from the allowed enum values
        - include trust requirements and conversion priorities
        - only add missing_information when truly needed
        Generate clarification_questions only when:
        - the answer materially affects workflows
        - business logic changes
        - trust/compliance changes
        - operational behavior changes

        Avoid aesthetic-only questions.
        - if uncertainty is high:
        - ask clarification questions earlier
        - prioritize operational ambiguity
        - reduce assumptions
        - avoid committing too early
        ONLY RETURN:
        - required_pages
        - required_workflows
        - trust_requirements
        - conversion_priorities
        """
    ).strip()


def build_strategy_prompt(
    state: WebsiteAgentState,
    tool_context: dict[str, Any] | None = None,
) -> str:

    assert (
        state.business_profile
        is not None
    )

    assert (
        state.requirements_spec
        is not None
    )

    tool_context = tool_context or {}
    return dedent(
        f"""
        You are the Strategy Agent
        for an autonomous AI
        web agency.

        Generate a
        StrategyHypothesisSet
        JSON object only.

        Business snapshot tool:
        {tool_context.get("business_snapshot", {})}

        Workflow constraints tool:
        {tool_context.get("workflow_constraints", {})}

        Asset evidence tool:
        {tool_context.get("asset_evidence", {})}

        Memory guidance tool:
        {tool_context.get("memory_guidance", {})}

        Process health tool:
        {tool_context.get("process_health", {})}

        Requirements:

        - generate 2 genuinely
          distinct website
          strategies

        - each strategy must
          optimize for different
          user behavior

        - strategies must involve
          real tradeoffs

        - avoid generic labels like:
          "good UX"
          "clean design"

        - strategies should differ in:
          - urgency
          - trust depth
          - browsing friction
          - CTA aggressiveness
          - educational depth
          - exploration behavior
          - workflow prioritization

        - explain:
          - what this strategy optimizes
          - what it sacrifices
          - which users it benefits
          - what business risks it creates

        - confidence should reflect
          how strongly the strategy
          matches the business evidence

        - if uncertainty is high:
          - generate more strategically
            diverse hypotheses
          - explore alternative business
            interpretations
          - avoid premature convergence
          - challenge initial assumptions
          - increase exploration breadth

        - strategies should emerge from:
          - operational signals
          - visual evidence
          - business goals
          - user psychology
          - workflow constraints
          - trust requirements
          - browsing behavior

        - think in terms of:
          - behavioral economics
          - friction reduction
          - trust sequencing
          - intent acceleration
          - exploratory browsing
          - cognitive load
          - decision confidence

        - strategies must contain:
          - real behavioral hypotheses
          - meaningful tradeoffs
          - operational implications
          - conversion assumptions
        """
    ).strip()



def build_design_candidates_prompt(
    state: WebsiteAgentState,
    tool_context: dict[str, Any] | None = None,
) -> str:

    assert (
        state.business_profile
        is not None
    )

    assert (
        state.requirements_spec
        is not None
    )

    rulebook = VERTICAL_RULEBOOKS.get(
        state.business_profile.vertical
    )

    tool_context = tool_context or {}

    return dedent(
        f"""
        You are the Layout Planner Agent
        for an autonomous AI web agency.

        Build a DesignCandidateSet
        JSON object only.

        Business snapshot tool:
        {tool_context.get("business_snapshot", {})}

        Workflow constraints tool:
        {tool_context.get("workflow_constraints", {})}

        Strategy landscape tool:
        {tool_context.get("strategy_landscape", {})}

        Memory guidance tool:
        {tool_context.get("memory_guidance", {})}

        Previous critique history:
        {compact_history(state.critique_history)}

        Asset evidence tool:
        {tool_context.get("asset_evidence", {})}

        Process health tool:
        {tool_context.get("process_health", {})}

        Rulebook:
        {rulebook}

        Requirements:

        - produce one candidate per
          strategy hypothesis

        - each candidate must strongly
          embody its assigned strategy

        - candidates must differ
          substantially in:
          - information hierarchy
          - CTA behavior
          - browsing flow
          - trust progression
          - workflow sequencing
          - content density
          - educational depth
          - urgency level
          - exploration behavior

        - section ordering must emerge
          naturally from the strategy itself

        - do NOT use generic homepage
          structures

        - think in terms of:
          - user psychology
          - hesitation reduction
          - scanning behavior
          - urgency
          - trust progression
          - decision support
          - workflow friction

        - section sequencing must be
          strategically justified,
          not aesthetically justified

        - keep copy concise
        - every section must include:
          - purpose
          - short rationale

        - rationale should be brief
          and tie to:
          - business goals
          - workflow behavior
          - user intent
          - asset evidence when relevant

        - avoid repeating weaknesses
          identified in previous
          critique rounds

        - evolve candidate structures
          across iterations instead
          of repeating similar layouts

        - improve strategic differentiation
          between candidates

        - candidates should optimize for
          genuinely different user behavior
          models

        - return compact JSON only
        - keep section count modest
        - do not add optional prose

        - use only allowed:
          - section types
          - page types
          - workflow kinds
          - tones
          - density values
          - media bias values

        - do not invent unsupported
          workflows or operational systems
        """
    ).strip()


def build_critique_prompt(
    state: WebsiteAgentState,
    tool_context: dict[str, Any] | None = None,
) -> str:
    assert state.business_profile is not None
    assert state.requirements_spec is not None
    rulebook = VERTICAL_RULEBOOKS.get(state.business_profile.vertical)
    tool_context = tool_context or {}
    return dedent(
        f"""
        You are the Design Critic Agent.

        Build a CritiqueReportSet JSON object only.

        Current uncertainty score:
        {state.uncertainty_score}

        Business snapshot tool:
        {tool_context.get("business_snapshot", {})}

        Workflow constraints tool:
        {tool_context.get("workflow_constraints", {})}

        Candidate landscape tool:
        {tool_context.get("candidate_landscape", {})}

        Memory guidance tool:
        {tool_context.get("memory_guidance", {})}

        Asset evidence tool:
        {tool_context.get("asset_evidence", {})}

        Process health tool:
        {tool_context.get("process_health", {})}
        Vertical rulebook:
        {rulebook}

        Requirements:
        - critique every candidate comparatively, not independently
        - evaluate how each candidate supports the business goal, workflow clarity, trust-building, and conversion behavior
        - score conversion, trust, usability, business_fit, and completeness from 1 to 10

        - NEVER use vague statements like:
        "better UX"
        "strong trust"
        "clean design"

        - ALWAYS reference:
        - specific sections
        - section ordering
        - CTA placement
        - workflow placement
        - browsing friction
        - user hesitation
        - scanning behavior
        - trust-building strategy
        - extracted asset evidence

        - explain WHY a candidate would outperform the competing candidate under specific business conditions

        - explicitly analyze tradeoffs:
        - what this strategy improves
        - what it sacrifices
        - what type of user behavior it optimizes for
        - what business risk it introduces

        - critique should feel like business strategy analysis, not aesthetic commentary

        - every critique must include:
        - strengths
        - weaknesses
        - revision instructions
        - tradeoffs
        - predicted business effects
        - rejection reasoning if the candidate loses

        - predicted_effects should describe likely user or business outcomes

        - rejection_reason must clearly explain why this candidate lost against the alternative

        - keep critique grounded in:
        - business goals
        - workflow friction
        - user psychology
        - extracted asset evidence
        - rulebook priorities

        - reference concrete extracted offers, items, prices, visual cues, or business signals whenever possible
        - when uncertainty is high:
        - critique assumptions more aggressively
        - identify hidden business risks
        - challenge weak strategic assumptions
        - question workflow prioritization
        """
    ).strip()


def build_revision_prompt(
    state: WebsiteAgentState,
    tool_context: dict[str, Any] | None = None,
) -> str:

    assert (
        state.business_profile
        is not None
    )

    assert (
        state.requirements_spec
        is not None
    )

    tool_context = tool_context or {}

    return dedent(
        f"""
        You are the Revision Agent
        for an autonomous AI web agency.

        Build a final DesignSpec
        JSON object only.

        Business snapshot tool:
        {tool_context.get("business_snapshot", {})}

        Workflow constraints tool:
        {tool_context.get("workflow_constraints", {})}

        Strategy landscape tool:
        {tool_context.get("strategy_landscape", {})}

        Candidate landscape tool:
        {tool_context.get("candidate_landscape", {})}

        Critique landscape tool:
        {tool_context.get("critique_landscape", {})}

        Memory guidance tool:
        {tool_context.get("memory_guidance", {})}

        Finalization authority:
        {state.finalization_decision.model_dump() if state.finalization_decision else None}

        Previous critique iterations:
        {compact_history(state.critique_history)}

        Asset evidence tool:
        {tool_context.get("asset_evidence", {})}

        Process health tool:
        {tool_context.get("process_health", {})}

        Requirements:

        - choose the strongest candidate
          based on:
          - business goals
          - workflow clarity
          - critique quality
          - strategic coherence
          - behavioral optimization
          - finalization authority if provided

        - revise the winning candidate
          WITHOUT collapsing its
          strategic identity

        - preserve the strategy's:
          - interaction philosophy
          - browsing model
          - trust progression
          - workflow behavior
          - conversion logic

        - only fix weaknesses identified
          in critique reports

        - preserve meaningful
          differentiation from rejected
          strategies

        - avoid collapsing all candidates
          into generic middle-ground layouts

        - explicitly address weaknesses
          identified during previous
          critique iterations

        - explain why the selected strategy
          survived critique rounds

        - preserve strengths while
          improving:
          - workflow clarity
          - CTA placement
          - trust sequencing
          - browsing progression
          - section ordering
          - decision support
          - evidence grounding

        - section sequencing must remain
          strategically justified

        - reasoning must reference:
          - user psychology
          - workflow friction
          - scanning behavior
          - hesitation reduction
          - trust-building behavior
          - operational priorities

        - mention concrete extracted:
          - offers
          - items
          - prices
          - visual cues
          - operational signals

        - provide:
          - a strong brief
          - decision_rationale
          - strategic reasoning

        - keep the structure:
          - renderable
          - operationally believable
          - practically deployable

        - preserve only allowed enum values
        """
    ).strip()


def build_reflection_prompt(
    state: WebsiteAgentState,
    tool_context: dict[str, Any] | None = None,
) -> str:
    tool_context = tool_context or {}
    return dedent(
        f"""
        You are the Reflection Agent
        for an autonomous AI
        planning system.

        Analyze the reasoning quality
        of the planning process itself.

        Generate a ReflectionReport
        JSON object only.

        Strategy landscape tool:
        {tool_context.get("strategy_landscape", {})}

        Candidate landscape tool:
        {tool_context.get("candidate_landscape", {})}

        Critique landscape tool:
        {tool_context.get("critique_landscape", {})}

        Process health tool:
        {tool_context.get("process_health", {})}

        Candidate history:
        {compact_history(state.candidate_history)}

        Critique history:
        {compact_history(state.critique_history)}

        Reasoning notes:
        {compact_reasoning_notes(state)}

        Requirements:

        - evaluate:
          - exploration depth
          - strategic diversity
          - critique quality
          - reasoning quality
          - convergence risk

        - detect:
          - repetitive reasoning
          - shallow exploration
          - strategy collapse
          - generic convergence
          - weak differentiation
          - insufficient challenge

        - determine whether the
          planner explored enough
          strategic space

        - determine whether
          candidates became
          too similar

        - identify whether the
          critique process became
          repetitive or weak

        - recommend concrete
          improvement actions

        - if planning quality is weak:
          set should_expand_exploration=true
        """
    ).strip()


def build_debate_prompt(
    state: WebsiteAgentState,
    tool_context: dict[str, Any] | None = None,
) -> str:
    tool_context = tool_context or {}
    return dedent(
        f"""
        You are the Debate Agent
        for an autonomous AI
        planning system.

        Generate a DebateOutcome
        JSON object only.

        Business snapshot tool:
        {tool_context.get("business_snapshot", {})}

        Strategy landscape tool:
        {tool_context.get("strategy_landscape", {})}

        Candidate landscape tool:
        {tool_context.get("candidate_landscape", {})}

        Critique landscape tool:
        {tool_context.get("critique_landscape", {})}

        Memory guidance tool:
        {tool_context.get("memory_guidance", {})}

        Process health tool:
        {tool_context.get("process_health", {})}

        Reflection report:
        {state.reflection_report.model_dump() if state.reflection_report else None}

        Requirements:

        - compare candidates directly

        - identify:
          - strategic strengths
          - strategic weaknesses
          - behavioral tradeoffs
          - workflow implications
          - trust implications
          - conversion implications

        - determine which candidate
          better matches:
          - business goals
          - user behavior
          - operational realism
          - workflow effectiveness

        - explain WHY one strategy
          should dominate

        - identify opportunities
          to synthesize strengths
          from the losing strategy

        - avoid generic statements

        - reason explicitly about:
          - user psychology
          - friction
          - trust progression
          - exploration depth
          - urgency
          - scanning behavior
          - operational usability
        """
    ).strip()


def build_simulation_prompt(
    state: WebsiteAgentState,
    tool_context: dict[str, Any] | None = None,
) -> str:
    tool_context = tool_context or {}
    return dedent(
        f"""
        You are the Simulation Agent
        for an autonomous AI
        planning system.

        Generate a SimulationReport
        JSON object only.

        Business snapshot tool:
        {tool_context.get("business_snapshot", {})}

        Candidate landscape tool:
        {tool_context.get("candidate_landscape", {})}

        Critique landscape tool:
        {tool_context.get("critique_landscape", {})}

        Process health tool:
        {tool_context.get("process_health", {})}

        Debate outcome:
        {state.debate_outcome.model_dump() if state.debate_outcome else None}

        Critique history:
        {compact_history(state.critique_history)}

        Requirements:

        - simulate realistic users
          interacting with the
          generated experiences

        - simulate:
          - first-time visitors
          - hesitant users
          - high-intent users
          - mobile users
          - information-seeking users

        - identify:
          - friction points
          - confusion
          - trust failures
          - conversion blockers
          - workflow inefficiencies
          - unrealistic assumptions

        - evaluate:
          - operational realism
          - usability realism
          - behavioral realism
          - workflow coherence

        - roleplay step-by-step
          journeys through the site

        - detect:
          - premature CTAs
          - excessive cognitive load
          - missing information
          - navigation confusion
          - workflow dead ends

        - provide:
          - realism scores
          - systemic issues
          - recommended improvements

        - reason from actual
          simulated user behavior,
          not generic UX principles
        """
    ).strip()


def serialize_asset_extractions(extractions: list[AssetExtraction]) -> list[dict[str, Any]]:
    return [extraction.model_dump() for extraction in extractions]


def summarize_asset_evidence(extractions: list[AssetExtraction]) -> list[str]:
    summary: list[str] = []
    for extraction in extractions[:5]:
        parts: list[str] = []
        if extraction.asset_type:
            parts.append(f"type={extraction.asset_type}")
        if extraction.business_signals:
            parts.append(f"signals={', '.join(extraction.business_signals[:3])}")
        info = extraction.extracted_business_info
        if info.offers:
            parts.append(f"offers={', '.join(info.offers[:2])}")
        if info.services_or_items:
            parts.append(f"items={', '.join(info.services_or_items[:4])}")
        if info.prices:
            parts.append(f"prices={', '.join(format_price_hint(price) for price in info.prices[:3])}")
        if extraction.visual_brand_cues:
            parts.append(f"visuals={', '.join(extraction.visual_brand_cues[:2])}")
        if parts:
            summary.append(" | ".join(parts))
    return summary


def normalize_confidence(value: Any) -> float:
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    if isinstance(value, str):
        lookup = {
            "low": 0.35,
            "medium": 0.65,
            "high": 0.85,
            "very high": 0.92,
            "realistic": 0.7,
        }
        mapped = lookup.get(value.strip().lower())
        if mapped is not None:
            return mapped
        try:
            return max(0.0, min(1.0, float(value)))
        except ValueError:
            return 0.6
    return 0.6


def normalize_evidence_summary(values: list[Any]) -> list[str]:
    output: list[str] = []
    for value in values:
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                output.append(cleaned)
            continue
        if isinstance(value, dict):
            asset_type = value.get("asset_type")
            signals = value.get("business_signals") or []
            note = value.get("planner_notes")
            parts = [str(asset_type)] if asset_type else []
            if signals:
                parts.append(str(signals[0]))
            if note:
                parts.append(str(note)[:80])
            cleaned = " | ".join(part for part in parts if part)
            if cleaned:
                output.append(cleaned)
    return output[:8]


def normalize_enum(
    value,
):

    if isinstance(
        value,
        str,
    ):

        return (
            value
            .strip()
            .lower()
        )

    return value

PAGE_ROLE_SECTION_RULES = {

    PageType.HOME: {
        SectionType.HERO_OFFER_BANNER,
        SectionType.HERO_TRUST_BANNER,
        SectionType.FEATURE_GRID,
        SectionType.TRUST_BAND,
        SectionType.REVIEW_BAND,
        SectionType.PROOF_BAND,
    },

    PageType.MENU: {
        SectionType.MENU_SHOWCASE,
        SectionType.CATEGORY_STRIP,
        SectionType.GALLERY_STRIP,
    },

    PageType.ORDER: {
        SectionType.PRIMARY_WORKFLOW_FORM,
        SectionType.TRUST_BAND,
        SectionType.PROOF_BAND,
    },

    PageType.CONTACT: {
        SectionType.TRUST_BAND,
        SectionType.PROOF_BAND,
    },

    PageType.RESERVATIONS: {
        SectionType.PRIMARY_WORKFLOW_FORM,
        SectionType.TRUST_BAND,
    },

    PageType.SERVICES: {
        SectionType.SERVICE_CARDS,
        SectionType.FEATURE_GRID,
        SectionType.TRUST_BAND,
    },

    PageType.ABOUT: {
        SectionType.FEATURE_GRID,
        SectionType.PROOF_BAND,
    },
}

def normalize_requirements_payload(
    payload: dict[str, Any],
    state: WebsiteAgentState,
) -> dict[str, Any]:

    candidate = payload

    for key in (
        "RequirementsSpec",
        "requirements_spec",
        "requirements",
        "result",
    ):

        nested = payload.get(key)

        if isinstance(
            nested,
            dict,
        ):

            candidate = nested
            break

    business_profile = (
        candidate.get(
            "business_profile",
            {},
        )
    )

    if isinstance(
        business_profile,
        dict,
    ):
        business_profile[
            "vertical"
        ] = normalize_enum(
            business_profile.get(
                "vertical"
            )
        )

        business_profile[
            "risk_level"
        ] = normalize_enum(
            business_profile.get(
                "risk_level"
            )
        )

    rulebook = (
        VERTICAL_RULEBOOKS.get(
            state.business_profile.vertical
        )
        if state.business_profile
        else {}
    )

    behavioral_requirements = (
        derive_behavioral_requirements(
            state.behavioral_contexts
        )
    )


    MINIMUM_REQUIRED_PAGES = [
        PageType.HOME,
        PageType.SERVICES,
        PageType.CONTACT,
    ]

    MINIMUM_REQUIRED_WORKFLOWS = [
        WorkflowType.LEAD,
    ]

    required_pages = (
        candidate.get(
            "required_pages"
        )
        or rulebook.get(
            "required_pages"
        )
        or MINIMUM_REQUIRED_PAGES
    )

    required_pages = (
        remove_forbidden_semantics(
            [
                (
                    page.value
                    if hasattr(
                        page,
                        "value",
                    )
                    else str(page)
                )
                for page in required_pages
            ],
            state,
        )
    )

    required_workflows = (
        candidate.get(
            "required_workflows"
        )
        or rulebook.get(
            "required_workflows"
        )
        or MINIMUM_REQUIRED_WORKFLOWS
    )

    return {

        "required_pages":
            required_pages,

        "required_workflows":
            required_workflows,

        "trust_requirements":
            remove_forbidden_semantics(
                (
                    normalize_string_list(
                        candidate.get(
                            "trust_requirements"
                        )
                        or rulebook.get(
                            "must_prioritize",
                            [],
                        )
                    )
                    +
                    normalize_string_list(
                        behavioral_requirements.get(
                            "trust_requirements",
                            [],
                        )
                    )
                ),
                state,
            ),

        "compliance_requirements":
            normalize_string_list(
                candidate.get(
                    "compliance_requirements"
                )
                or []
            ),

        "conversion_priorities":
            remove_forbidden_semantics(
                (
                    normalize_string_list(
                        candidate.get(
                            "conversion_priorities"
                        )
                        or rulebook.get(
                            "must_prioritize",
                            [],
                        )
                    )
                    +
                    normalize_string_list(
                        behavioral_requirements.get(
                            "conversion_priorities",
                            [],
                        )
                    )
                ),
                state,
            ),

        "missing_information":
            normalize_string_list(
                candidate.get(
                    "missing_information"
                )
                or []
            ),

        "avoid_patterns":
            normalize_string_list(
                candidate.get(
                    "avoid_patterns"
                )
                or rulebook.get(
                    "avoid",
                    [],
                )
            ),
    }


def normalize_string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    output: list[str] = []
    for value in values:
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                output.append(cleaned)
    return output[:12]


def normalize_candidate_set_payload(payload: dict[str, Any], state: WebsiteAgentState) -> dict[str, Any]:
    candidate = payload
    for key in ("DesignCandidateSet", "design_candidate_set", "result"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            candidate = nested
            break
    raw_candidates = []
    if isinstance(payload.get("items"), list):
        raw_candidates = payload["items"]
    elif isinstance(candidate.get("candidates"), list):
        raw_candidates = candidate["candidates"]
    elif isinstance(candidate.get("DesignCandidateSet"), list):
        raw_candidates = candidate["DesignCandidateSet"]
    elif isinstance(payload.get("DesignCandidateSet"), list):
        raw_candidates = payload["DesignCandidateSet"]
    return {"candidates": [normalize_design_candidate(item, index, state) for index, item in enumerate(raw_candidates, start=1)]}


def normalize_strategy_hypothesis_set_payload(payload: dict[str, Any], state: WebsiteAgentState) -> dict[str, Any]:
    candidate = payload
    for key in ("StrategyHypothesisSet", "strategy_hypothesis_set", "strategyHypothesisSet", "result"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            candidate = nested
            break

    raw_strategies = []
    for key in ("strategies", "StrategyHypothesisSet", "strategyHypothesisSet"):
        value = candidate.get(key) if isinstance(candidate, dict) else None
        if isinstance(value, list):
            raw_strategies = value
            break
    if not raw_strategies and isinstance(payload.get("strategyHypothesisSet"), list):
        raw_strategies = payload["strategyHypothesisSet"]
    if not raw_strategies and isinstance(payload.get("StrategyHypothesisSet"), list):
        raw_strategies = payload["StrategyHypothesisSet"]

    return {
        "strategies": [
            normalize_strategy_hypothesis(item, index, state)
            for index, item in enumerate(raw_strategies, start=1)
        ]
    }


def normalize_strategy_hypothesis(item: dict[str, Any], index: int, state: WebsiteAgentState) -> dict[str, Any]:
    if not isinstance(item, dict):
        item = {}

    optimize_values = normalize_string_list(
        item.get("what_it_optimizes")
        or item.get("optimizes")
        or item.get("strengths")
        or []
    )
    sacrifice_values = normalize_string_list(
        item.get("what_it_sacrifices")
        or item.get("sacrifices")
        or item.get("risks")
        or []
    )
    user_values = normalize_string_list(
        item.get("which_users_it_benefits")
        or item.get("users_it_benefits")
        or item.get("ideal_for")
        or []
    )
    risk_values = normalize_string_list(
        item.get("what_business_risks_it_creates")
        or item.get("business_risks")
        or item.get("risks")
        or []
    )

    name = (
        item.get("name")
        or item.get("label")
        or item.get("title")
        or item.get("id")
        or f"strategy-{index}"
    )

    core_thesis = (
        item.get("core_thesis")
        or item.get("coreThesis")
        or item.get("summary")
        or item.get("thesis")
        or (optimize_values[0] if optimize_values else f"Strategy {index} prioritizes a distinct conversion path.")
    )

    target_behavior = (
        item.get("target_behavior")
        or item.get("targetBehavior")
        or item.get("primary_user_behavior")
        or item.get("primaryUserBehavior")
        or "Guide visitors toward the primary business goal."
    )

    tradeoffs = normalize_string_list(
        item.get("tradeoffs")
        or item.get("trade_offs")
        or item.get("tradeOffs")
        or sacrifice_values
    )

    confidence = normalize_confidence(
        item.get("confidence", 0.68)
    )

    return {
        "strategy_id": item.get("strategy_id") or item.get("strategyId") or item.get("id") or f"strategy-{index}",
        "name": str(name),
        "core_thesis": str(core_thesis),
        "target_behavior": str(target_behavior),
        "strengths": optimize_values[:6],
        "risks": risk_values[:6],
        "ideal_for": user_values[:6],
        "tradeoffs": tradeoffs[:6],
        "confidence": confidence,
    }


def normalize_critique_set_payload(payload: dict[str, Any]) -> dict[str, Any]:
    candidate = payload
    for key in ("CritiqueReportSet", "critique_report_set", "result"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            candidate = nested
            break
    if isinstance(payload.get("items"), list):
        return {"critiques": payload["items"]}
    if isinstance(candidate.get("critiques"), list):
        return {"critiques": candidate["critiques"]}
    if isinstance(candidate.get("CritiqueReportSet"), list):
        return {"critiques": candidate["CritiqueReportSet"]}
    if isinstance(payload.get("CritiqueReportSet"), list):
        return {"critiques": payload["CritiqueReportSet"]}
    return {"critiques": []}


def normalize_design_spec_payload(payload: dict[str, Any], state: WebsiteAgentState | None = None) -> dict[str, Any]:
    for key in ("DesignSpec", "design_spec", "result"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            return normalize_design_spec(nested, state)
    return normalize_design_spec(payload, state)

def deduplicate_sections(
    sections,
):
    seen = set()

    cleaned = []

    for section in sections:

        section_type = (
            getattr(
                section,
                "type",
                None,
            )
            or section.get(
                "type"
            )
        )

        if hasattr(
            section_type,
            "value",
        ):
            section_key = (
                section_type.value
            )
        else:
            section_key = str(
                section_type
            )

        section_key = (
            section_key
            .strip()
            .lower()
        )

        if (
            not section_key
            or section_key in seen
        ):
            continue

        seen.add(
            section_key
        )

        cleaned.append(
            section
        )

    return cleaned




def normalize_design_candidate(
    candidate: dict[str, Any],
    index: int,
    state: WebsiteAgentState,
) -> dict[str, Any]:

    mode = determine_candidate_mode(
        candidate
    )

    strategy = (
        state.strategy_hypotheses[
            min(
                index - 1,
                len(
                    state.strategy_hypotheses
                ) - 1,
            )
        ]
        if state.strategy_hypotheses
        else None
    )

    behavioral_requirements = (
        derive_behavioral_requirements(
            state.behavioral_contexts
        )
    )

    behavioral_sections = (
        behavioral_requirements[
            "recommended_sections"
        ]
    )

    pages = (
        candidate.get("pages")
        or candidate.get("page_specs")
        or candidate.get("page_plan")
        or []
    )

    if (
        not isinstance(
            pages,
            list,
        )
        or not pages
    ):

        pages = [
            {
                "type": (
                    page_type.value
                    if isinstance(
                        page_type,
                        PageType,
                    )
                    else str(
                        page_type
                    )
                )
            }
            for page_type in (
                state.requirements_spec.required_pages
                if state.requirements_spec
                else [PageType.HOME]
            )
        ]

    enriched_pages = []

    for page in pages:

        if not isinstance(
            page,
            dict,
        ):

            page = {
                "type": str(page)
            }

        raw_page_type = str(
            page.get(
                "type",
                "home",
            )
        ).lower()

        try:

            page_type = (
                PageType(
                    raw_page_type
                )
            )

        except ValueError:

            page_type = (
                PageType.HOME
            )

        allowed_sections = (
            PAGE_ROLE_SECTION_RULES.get(
                page_type,
                set(),
            )
        )

        existing_sections = (
            page.get("sections")
            or []
        )

        if not isinstance(
            existing_sections,
            list,
        ):
            existing_sections = []

        existing_section_types = set()

        normalized_existing_sections = []

        for section in existing_sections:

            if isinstance(
                section,
                dict,
            ):

                section_type = str(
                    section.get(
                        "type",
                        ""
                    )
                ).strip()

            else:

                section_type = str(
                    section
                ).strip()

                section = {
                    "type": section_type
                }

            try:

                section_enum = (
                    SectionType(
                        section_type
                    )
                )

            except ValueError:
                continue

            if (
                section_enum
                not in allowed_sections
            ):
                continue

            existing_section_types.add(
                section_type
            )

            normalized_existing_sections.append(
                section
            )

        for behavioral_section in (
            behavioral_sections
        ):

            try:

                section_enum = (
                    SectionType(
                        behavioral_section
                    )
                )

            except ValueError:
                continue

            if (
                section_enum
                not in allowed_sections
            ):
                continue

            if (
                behavioral_section
                not in existing_section_types
            ):

                normalized_existing_sections.append(
                    {
                        "type": behavioral_section
                    }
                )

        normalized_existing_sections = (
            deduplicate_sections(
                normalized_existing_sections
            )
        )

        page["sections"] = (
            normalized_existing_sections
        )

        enriched_pages.append(
            page
        )

    return {

        "candidate_id": (
            candidate.get(
                "candidate_id"
            )
            or candidate.get("id")
            or f"candidate_{index}"
        ),

        "rationale": (
            candidate.get(
                "rationale"
            )
            or candidate.get(
                "summary"
            )
            or (
                strategy.core_thesis
                if strategy
                else None
            )
            or candidate.get(
                "description"
            )
            or candidate.get("name")
            or (
                "Model-generated "
                "candidate selected "
                "for business fit."
            )
        ),

        "confidence": (
            normalize_confidence(
                candidate.get(
                    "confidence",
                    0.72,
                )
            )
        ),

        "visual_system": (
            normalize_visual_system(
                (
                    candidate.get(
                        "visual_system"
                    )
                    or candidate.get(
                        "visual"
                    )
                    or candidate.get(
                        "style"
                    )
                    or {}
                ),
                state,
                mode,
            )
        ),

        "primary_action": (
            normalize_primary_action(
                (
                    candidate.get(
                        "primary_action"
                    )
                    or candidate.get(
                        "cta"
                    )
                    or candidate.get(
                        "call_to_action"
                    )
                    or {}
                ),
                state,
                mode,
            )
        ),

        "pages": [
            normalize_page_spec(
                page,
                page_index,
                state,
                mode,
            )
            for (
                page_index,
                page,
            ) in enumerate(
                enriched_pages,
                start=1,
            )
        ],
    }



def normalize_page_spec(page: dict[str, Any], index: int, state: WebsiteAgentState, mode: str = "conversion") -> dict[str, Any]:
    normalized_page_type = normalize_page_type(page.get("page_type") or page.get("type") or page.get("name"))
    raw_sections = page.get("sections") or page.get("content_sections") or []
    if raw_sections and isinstance(raw_sections[0], str):
        raw_sections = [{"type": section, "purpose": "Model-selected section", "rationale": "Supports page goal"} for section in raw_sections]
    if not raw_sections:
        raw_sections = infer_default_sections_for_page(normalized_page_type, state, page, mode)
    return {
        "page_type": normalized_page_type,
        "title": page.get("title") or page.get("name") or page_title_for_type(normalized_page_type, index),
        "sections": [normalize_section_spec(section, section_index, normalized_page_type, state) for section_index, section in enumerate(raw_sections, start=1)],
    }


def normalize_section_spec(section: dict[str, Any], index: int, page_type: str, state: WebsiteAgentState) -> dict[str, Any]:
    section_type = section.get("type") or section.get("section_type") or "feature_grid"
    if section_type not in {
        "hero_offer_banner",
        "hero_trust_banner",
        "page_nav",
        "gallery_strip",
        "menu_showcase",
        "feature_grid",
        "trust_band",
        "review_band",
        "proof_band",
        "primary_workflow_form",
        "doctor_profiles",
        "service_cards",
        "category_strip",
    }:
        section_type = infer_section_type(section_type, page_type, state)
    return {
        "type": section_type,
        "purpose": section.get("purpose") or section.get("goal") or default_section_purpose(section_type, page_type),
        "rationale": section.get("rationale") or section.get("why") or "Chosen by the planner as part of the page structure.",
        "priority": int(section.get("priority") or index),
    }


def normalize_visual_system(value: dict[str, Any], state: WebsiteAgentState | None = None, mode: str = "conversion") -> dict[str, Any]:
    rulebook = get_rulebook_for_state(state)
    default_tone = first_rulebook_value(rulebook.get("preferred_tones"), "practical")
    default_density = enumish_value(rulebook.get("preferred_density"), "medium")
    default_media_bias = enumish_value(rulebook.get("preferred_media_bias"), "copy_first")
    if mode == "trust_browsing":
        if default_density == "high":
            default_density = "medium"
        if default_media_bias == "image_heavy":
            default_media_bias = "balanced"
    tone = str(value.get("tone") or value.get("style") or default_tone).lower().replace(" ", "_")
    density = str(value.get("density") or default_density).lower()
    media_bias = str(value.get("media_bias") or value.get("mediaBias") or default_media_bias).lower()
    trust_emphasis = str(value.get("trust_emphasis") or value.get("trustEmphasis") or ("high" if mode == "trust_browsing" else "medium")).lower()

    if tone not in {"energetic", "trustworthy", "calm", "modern", "premium", "practical"}:
        tone = default_tone
    if density not in {"low", "medium", "high"}:
        density = default_density
    if media_bias not in {"image_heavy", "balanced", "copy_first", "trust_first"}:
        media_bias = default_media_bias
    if trust_emphasis not in {"low", "medium", "high"}:
        trust_emphasis = "medium"

    return {
        "tone": tone,
        "density": density,
        "media_bias": media_bias,
        "trust_emphasis": trust_emphasis,
    }


def normalize_primary_action(value: dict[str, Any], state: WebsiteAgentState | None = None, mode: str = "conversion") -> dict[str, Any]:
    default_kind = infer_primary_action_kind(state)
    kind = str(value.get("kind") or value.get("type") or default_kind).lower()
    if kind not in {"order", "booking", "lead"}:
        kind = default_kind
    default_placements = ["hero", "section_end"] if mode == "conversion" else ["section_end", "menu_card"]
    placements = value.get("placements") or value.get("placement") or default_placements
    if isinstance(placements, str):
        placements = [placements]
    clean_placements = [item for item in placements if item in {"hero", "sticky", "section_end", "menu_card"}]
    if not clean_placements:
        clean_placements = default_placements
    return {
        "label": value.get("label") or value.get("text") or default_action_label(kind, mode),
        "kind": kind,
        "placements": clean_placements,
    }


def normalize_design_spec(value: dict[str, Any], state: WebsiteAgentState | None = None) -> dict[str, Any]:
    pages = value.get("pages") or []
    chosen_candidate_id = value.get("chosen_candidate_id") or value.get("candidate_id") or value.get("id") or "candidate_1"
    return {
        "brief": value.get("brief") or value.get("rationale") or "Model-selected design specification.",
        "chosen_candidate_id": chosen_candidate_id,
        "primary_goal": value.get("primary_goal") or value.get("goal") or "increase conversions",
        "visual_system": normalize_visual_system(value.get("visual_system") or value.get("visual") or {}, state),
        "primary_action": normalize_primary_action(value.get("primary_action") or value.get("cta") or {}, state),
        "pages": [normalize_page_spec(page, index, state or WebsiteAgentState(business_input={})) for index, page in enumerate(pages, start=1)],
        "decision_rationale": normalize_string_list(value.get("decision_rationale") or value.get("rationales") or []),
    }


def build_fallback_design_spec(state: WebsiteAgentState) -> dict[str, Any]:
    candidate = choose_best_candidate(state)
    critique = next((item for item in state.critique_reports if item.candidate_id == candidate.candidate_id), None)
    rationale = [f"Selected {candidate.candidate_id} as the strongest renderable candidate."]
    if critique:
        rationale.extend(critique.strengths[:2])
        rationale.extend(critique.revision_instructions[:2])
    if not rationale:
        rationale = ["Selected the strongest candidate using rulebook-guided defaults."]
    return {
        "brief": build_fallback_brief(state, candidate, critique),
        "chosen_candidate_id": candidate.candidate_id,
        "primary_goal": state.business_profile.goal if state.business_profile else "increase conversions",
        "visual_system": candidate.visual_system.model_dump(),
        "primary_action": candidate.primary_action.model_dump(),
        "pages": [page.model_dump() for page in candidate.pages],
        "decision_rationale": dedupe_strings(rationale)[:5],
    }


def choose_best_candidate(state: WebsiteAgentState):
    if not state.design_candidates:
        raise ValueError("cannot build fallback design spec without candidates")
    if (
        state.finalization_decision
        and state.finalization_decision.selected_candidate_id
    ):
        selected_id = (
            state.finalization_decision
            .selected_candidate_id
        )
        for candidate in (
            state.design_candidates
        ):
            if (
                candidate.candidate_id
                == selected_id
            ):
                return candidate
    ranked = candidate_decision_scores(
        state
    )
    if ranked:
        selected_id = ranked[0][
            "candidate_id"
        ]
        for candidate in (
            state.design_candidates
        ):
            if (
                candidate.candidate_id
                == selected_id
            ):
                return candidate
    return max(
        state.design_candidates,
        key=lambda candidate: candidate.confidence,
    )


def average_critique_score(report: Any) -> float:
    if not getattr(report, "scores", None):
        return 0.0
    return sum(score.score for score in report.scores) / len(report.scores)


def ensure_critiques(state: WebsiteAgentState, critiques: list[Any]) -> list[Any]:
    if critiques:
        critique_ids = {critique.candidate_id for critique in critiques}
        completed = list(critiques)
        for candidate in state.design_candidates:
            if candidate.candidate_id not in critique_ids:
                completed.append(build_fallback_critique(candidate, state))
        return completed
    return [build_fallback_critique(candidate, state) for candidate in state.design_candidates]


def build_fallback_critique(candidate: Any, state: WebsiteAgentState) -> Any:
    mode = infer_candidate_mode(candidate)

    similarity_penalty = calculate_similarity_penalty(
        candidate,
        state.design_candidates,
    )

    conversion = (
        9
        if mode == "conversion"
        else 7
        if candidate.primary_action.kind.value == infer_primary_action_kind(state)
        else 6
    )

    trust = (
        8
        if mode == "trust_browsing"
        or candidate.visual_system.trust_emphasis in {"medium", "high"}
        else 5
    )

    usability = 8 if len(candidate.pages) >= 1 else 5

    business_fit = (
        (
            8
            if state.business_profile
            and state.business_profile.vertical.value
            in candidate.rationale.lower()
            else 7
        )
        - similarity_penalty
    )

    completeness = (8 if candidate.pages else 4) - similarity_penalty

    evidence = summarize_asset_evidence(state.asset_extractions)

    evidence_hint = (
        truncate_text(evidence[0], 90)
        if evidence
        else "No asset evidence summary available."
    )

    winner_phrase = (
        "This candidate is likely the winner because it aligns more directly with the primary workflow and minimizes interaction friction."
        if mode == "conversion"
        else "This candidate is valuable because it prioritizes exploration, reassurance, and trust-building before conversion."
    )

    report = {
        "candidate_id": candidate.candidate_id,

        "summary": truncate_text(
            (
                f"{candidate.candidate_id} is a {mode}-leaning strategy "
                f"optimized around a distinct user behavior model. "
                f"{winner_phrase}"
            ),
            300,
        ),

        "scores": [
            {
                "criterion": "conversion",
                "score": conversion,
                "reasoning": truncate_text(
                    (
                        f"The workflow placement and section ordering support a "
                        f"{mode}-oriented user journey. "
                        f"The structure reflects extracted business evidence: "
                        f"{evidence_hint}"
                    ),
                    220,
                ),
            },

            {
                "criterion": "trust",
                "score": trust,
                "reasoning": truncate_text(
                    (
                        "Trust-building sections and visual emphasis help reduce "
                        "hesitation before the primary action. "
                        "The candidate uses layout sequencing to support visitor confidence."
                    ),
                    220,
                ),
            },

            {
                "criterion": "usability",
                "score": usability,
                "reasoning": truncate_text(
                    (
                        "The page structure remains renderable and reasonably scannable "
                        "without excessive interaction friction or navigation complexity."
                    ),
                    220,
                ),
            },

            {
                "criterion": "business_fit",
                "score": business_fit,
                "reasoning": truncate_text(
                    (
                        "The candidate aligns with the stated business goals, "
                        "workflow expectations, and extracted operational signals."
                    ),
                    220,
                ),
            },

            {
                "criterion": "completeness",
                "score": completeness,
                "reasoning": truncate_text(
                    (
                        "The structure includes enough operational and informational "
                        "components to support a believable storefront experience."
                    ),
                    220,
                ),
            },
        ],

        "strengths": [
            truncate_text(
                "Primary workflow placement is strategically aligned with the intended user journey.",
                120,
            ),

            truncate_text(
                f"The candidate maintains a clearly differentiated {mode}-leaning interaction philosophy.",
                120,
            ),

            truncate_text(
                "Section sequencing supports a coherent conversion or exploration flow.",
                120,
            ),
        ],

        "weaknesses": [
            truncate_text(
                "The strategic tradeoffs between browsing depth and conversion speed could be expressed more explicitly.",
                120,
            ),

            truncate_text(
                "Some rationale still relies too heavily on generic planning language instead of concrete asset evidence.",
                120,
            ),
        ],

        "revision_instructions": [
            truncate_text(
                "Strengthen section-level rationale using extracted offers, catalog signals, visual cues, or operational evidence.",
                140,
            ),

            truncate_text(
                "Improve differentiation from the competing candidate through more distinct CTA sequencing and browsing behavior.",
                140,
            ),

            truncate_text(
                "Clarify how this structure optimizes for a specific user intent or business outcome.",
                140,
            ),
        ],

        "tradeoffs": [
            {
                "advantage": truncate_text(
                    (
                        "This strategy improves clarity around the primary workflow "
                        "and reduces uncertainty during the action path."
                    ),
                    220,
                ),

                "sacrifice": truncate_text(
                    (
                        "The structure may reduce exploratory depth or informational richness "
                        "for users still evaluating the business."
                    ),
                    220,
                ),

                "ideal_for": truncate_text(
                    (
                        "Best suited for users already close to taking action "
                        "or seeking a fast, low-friction path."
                    ),
                    220,
                ),

                "risk": truncate_text(
                    (
                        "Over-optimizing for workflow efficiency may reduce perceived trust, "
                        "premium quality, or educational depth."
                    ),
                    220,
                ),
            }
        ],

        "predicted_effects": [
            truncate_text(
                "Likely improves completion rate for the primary workflow.",
                140,
            ),

            truncate_text(
                "May accelerate user transition from browsing into action.",
                140,
            ),

            truncate_text(
                "Could influence trust perception depending on visitor intent and familiarity.",
                140,
            ),
        ],

        "rejection_reason": truncate_text(
            (
                "This candidate loses when the competing strategy better aligns "
                "with the primary business objective, trust expectations, "
                "or browsing behavior of the target audience."
            ),
            220,
        ),
    }

    if similarity_penalty > 0:
        report["weaknesses"].append(
            truncate_text(
                "Current section sequencing is too similar to the competing candidate strategy.",
                120,
            )
        )

        report["revision_instructions"].append(
            truncate_text(
                "Rework homepage and workflow section ordering to create a genuinely distinct behavioral strategy.",
                140,
            )
        )

    return CritiqueReportSet.model_validate(
        {"critiques": [report]}
    ).critiques[0]


def build_fallback_brief(state: WebsiteAgentState, candidate: Any, critique: Any | None) -> str:
    goal = state.business_profile.goal if state.business_profile else "increase conversions"
    page_count = len(candidate.pages)
    evidence = summarize_asset_evidence(state.asset_extractions)
    evidence_suffix = f" Grounded in extracted evidence: {truncate_text(evidence[0], 90)}." if evidence else ""
    base = f"Design optimized for {goal} with a {page_count}-page structure centered on {candidate.primary_action.label.lower()}.{evidence_suffix}"
    if critique and critique.summary:
        return truncate_text(f"{base} {critique.summary}", 400)
    return truncate_text(base, 400)


def dedupe_strings(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            output.append(cleaned)
    return output


def get_rulebook_for_state(state: WebsiteAgentState | None) -> dict[str, Any]:
    if state is None or state.business_profile is None:
        return {}
    return VERTICAL_RULEBOOKS.get(state.business_profile.vertical, {})


def enumish_value(value: Any, fallback: str) -> str:
    return getattr(value, "value", value) or fallback


def first_rulebook_value(values: Any, fallback: str) -> str:
    if isinstance(values, list) and values:
        return enumish_value(values[0], fallback)
    return fallback


def infer_primary_action_kind(state: WebsiteAgentState | None) -> str:
    if state and state.requirements_spec and state.requirements_spec.required_workflows:
        workflow = state.requirements_spec.required_workflows[0]
        return getattr(workflow, "value", workflow)
    return "lead"


def infer_candidate_mode(candidate: Any) -> str:
    rationale = (candidate.rationale or "").lower()
    if any(token in rationale for token in ("trust", "clarity", "browse", "browsing", "exploration", "confidence")):
        return "trust_browsing"
    return "conversion"


def format_price_hint(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(str(item) for item in value[:3]) + "]"
    return str(value)


def truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def determine_candidate_mode(candidate: dict[str, Any], index: int = 1) -> str:
    rationale = str(candidate.get("rationale") or candidate.get("summary") or candidate.get("description") or "").lower()
    if any(token in rationale for token in ("trust", "browse", "browsing", "clarity", "exploration")):
        return "trust_browsing"
    return "conversion"


def calculate_similarity_penalty(candidate: Any, candidates: list[Any]) -> int:
    current_signature = candidate_structure_signature(candidate)
    for other in candidates:
        if other.candidate_id == candidate.candidate_id:
            continue
        if candidate_structure_signature(other) == current_signature:
            return 2
    return 0


def candidate_structure_signature(candidate: Any) -> tuple[tuple[str, tuple[str, ...]], ...]:
    signature: list[tuple[str, tuple[str, ...]]] = []
    for page in candidate.pages:
        signature.append((page.page_type.value, tuple(section.type.value for section in page.sections)))
    return tuple(signature)


def default_action_label(kind: str, mode: str = "conversion") -> str:
    if mode == "trust_browsing" and kind == "order":
        return "Explore Menu"
    if kind == "order":
        return "Order Now"
    if kind == "booking":
        return "Book Now"
    return "Get Started"


def normalize_page_type(value: Any) -> str:
    raw = str(value or "home").strip().lower().replace(" ", "_")
    aliases = {
        "homepage": "home",
        "landing": "home",
        "landing_page": "home",
        "order_online": "order",
        "online_order": "order",
        "ordering": "order",
        "book": "booking",
        "appointment": "booking",
        "reservations_page": "reservations",
        "reservation": "reservations",
        "service": "services",
    }
    normalized = aliases.get(raw, raw)
    allowed = {page_type.value for page_type in PageType}
    return normalized if normalized in allowed else "home"


def page_title_for_type(page_type: str, index: int) -> str:
    titles = {
        "home": "Home",
        "menu": "Menu",
        "order": "Order Online",
        "reservations": "Reservations",
        "services": "Services",
        "booking": "Booking",
        "about": "About",
        "contact": "Contact",
    }
    return titles.get(page_type, f"Page {index}")


def infer_default_sections_for_page(page_type: str, state: WebsiteAgentState, page: dict[str, Any], mode: str = "conversion") -> list[dict[str, Any]]:
    purpose = page.get("purpose") or "Support the main business journey."
    if page_type == "home":
        if mode == "trust_browsing":
            return [
                {"type": "hero_trust_banner", "purpose": "Set context and reduce hesitation before browsing.", "rationale": "Trust-first journeys should establish credibility before asking for action."},
                {"type": "gallery_strip", "purpose": "Use visual cues from the business assets to build appetite and recognition.", "rationale": "Visual evidence supports browsing confidence."},
                {"type": "menu_showcase", "purpose": "Help visitors explore the catalog before committing.", "rationale": "Browsing-first journeys should expand exploration before conversion."},
                {"type": "review_band", "purpose": "Reinforce trust and quality before the action step.", "rationale": "Social proof should appear before the final action ask."},
                {"type": "page_nav", "purpose": "Help visitors orient quickly.", "rationale": "Supports scanning across a richer storefront."},
            ]
        return [
            {"type": infer_home_hero_type(state), "purpose": purpose, "rationale": "Lead with the most important conversion or trust signal."},
            {"type": "primary_workflow_form", "purpose": "Capture ordering intent as early as possible.", "rationale": "Conversion-first journeys should reduce friction quickly."},
            {"type": "feature_grid", "purpose": "Show the main offer or catalog.", "rationale": "This is the core browsing surface."},
            {"type": "proof_band", "purpose": "Reinforce legitimacy and conversion confidence.", "rationale": "Adds credibility before action."},
            {"type": "page_nav", "purpose": "Help visitors orient quickly.", "rationale": "Supports fast scanning."},
        ]
    if page_type == "menu":
        if mode == "trust_browsing":
            return [
                {"type": "category_strip", "purpose": "Help browsing by category.", "rationale": "Makes a large catalog easier to scan."},
                {"type": "menu_showcase", "purpose": purpose or "Display items, prices, and choices.", "rationale": "This page should prioritize discovery and information depth."},
                {"type": "review_band", "purpose": "Add confidence around item quality and popularity.", "rationale": "Trust-first browsing benefits from proof near the catalog."},
                {"type": "primary_workflow_form", "purpose": "Offer a low-pressure action path after exploration.", "rationale": "Action should follow exploration, not interrupt it."},
            ]
        return [
            {"type": "category_strip", "purpose": "Help browsing by category.", "rationale": "Makes a large catalog easier to scan."},
            {"type": "menu_showcase", "purpose": purpose or "Display items, prices, and choices.", "rationale": "This page should prioritize item discovery and pricing."},
            {"type": "primary_workflow_form", "purpose": "Convert browsing into action.", "rationale": "Keep ordering friction low."},
        ]
    if page_type in {"order", "booking", "reservations"}:
        if mode == "trust_browsing":
            return [
                {"type": "trust_band", "purpose": "Reduce hesitation before submission.", "rationale": "Support confidence before the final transaction."},
                {"type": "primary_workflow_form", "purpose": purpose or "Capture the main transaction.", "rationale": "Action should follow reassurance in a trust-first flow."},
            ]
        return [
            {"type": "primary_workflow_form", "purpose": purpose or "Capture the main transaction.", "rationale": "This page exists to complete the primary workflow."},
            {"type": "trust_band", "purpose": "Reduce hesitation before submission.", "rationale": "Supports final-step confidence."},
        ]
    if page_type == "services":
        return [
            {"type": "service_cards", "purpose": purpose or "Explain the available services clearly.", "rationale": "Service comparisons need structure."},
            {"type": "primary_workflow_form", "purpose": "Turn interest into inquiry or booking.", "rationale": "Pair service understanding with action."},
        ]
    if page_type == "contact":
        return [
            {"type": "trust_band", "purpose": "Make support and response expectations clear.", "rationale": "Contact pages need credibility and clarity."},
            {"type": "primary_workflow_form", "purpose": "Capture contact requests cleanly.", "rationale": "Provide a direct conversion path."},
        ]
    if page_type == "about":
        return [
            {"type": "gallery_strip", "purpose": purpose or "Show the business visually.", "rationale": "Adds personality and context."},
            {"type": "proof_band", "purpose": "Summarize trust and differentiation.", "rationale": "About pages should support credibility."},
        ]
    return [
        {"type": "feature_grid", "purpose": purpose, "rationale": page.get("rationale") or "Supports the primary user journey."}
    ]


def infer_home_hero_type(state: WebsiteAgentState) -> str:
    rulebook = get_rulebook_for_state(state)
    required_sections = {enumish_value(item, "") for item in rulebook.get("required_sections", [])}
    if "hero_offer_banner" in required_sections:
        return "hero_offer_banner"
    return "hero_trust_banner"


def infer_primary_content_section(state: WebsiteAgentState) -> str:
    vertical = state.business_profile.vertical.value if state.business_profile else ""
    if vertical in {"restaurant", "cafe", "bakery"}:
        return "menu_showcase"
    if vertical == "clinic":
        return "doctor_profiles"
    if vertical == "repair_service":
        return "service_cards"
    return "feature_grid"


def infer_section_type(value: Any, page_type: str, state: WebsiteAgentState) -> str:
    raw = str(value or "").strip().lower().replace(" ", "_")
    aliases = {
        "hero": infer_home_hero_type(state) if page_type == "home" else "hero_trust_banner",
        "nav": "page_nav",
        "navigation": "page_nav",
        "gallery": "gallery_strip",
        "menu": "menu_showcase",
        "menu_grid": "menu_showcase",
        "features": "feature_grid",
        "cards": "feature_grid",
        "trust": "trust_band",
        "reviews": "review_band",
        "proof": "proof_band",
        "form": "primary_workflow_form",
        "workflow_form": "primary_workflow_form",
        "doctors": "doctor_profiles",
        "services": "service_cards",
        "categories": "category_strip",
    }
    return aliases.get(raw, "feature_grid")


def default_section_purpose(section_type: str, page_type: str) -> str:
    purposes = {
        "hero_offer_banner": "Surface the strongest commercial hook immediately.",
        "hero_trust_banner": "Introduce the business with confidence-building information.",
        "page_nav": "Help visitors move quickly to important content.",
        "gallery_strip": "Use visual evidence to strengthen interest and clarity.",
        "menu_showcase": "Display the catalog with pricing and item clarity.",
        "feature_grid": "Organize key information into scannable blocks.",
        "trust_band": "Reduce hesitation with trust and clarity signals.",
        "review_band": "Show customer proof that supports conversion.",
        "proof_band": "Summarize evidence that the business is credible and ready.",
        "primary_workflow_form": "Turn visitor intent into the main business action.",
        "doctor_profiles": "Present practitioners in a trust-building format.",
        "service_cards": "Explain the available services clearly and quickly.",
        "category_strip": "Improve browsing across multiple content groups.",
    }
    return purposes.get(section_type, f"Support the main goal of the {page_type} page.")
