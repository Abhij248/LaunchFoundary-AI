from __future__ import annotations

from textwrap import dedent
from typing import Any

from pydantic import ValidationError

from agentic_models import (
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
    PageType,
    RequirementsSpec,
    SectionType,
    StrategyHypothesisSet,
    WebsiteAgentState,
    WorkflowType,
)
from agentic_planner import ModelJsonPlanner, parse_json_object
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

    normalized.setdefault(
        "confidence",
        0.8,
    )

    return normalized


def build_agent_graph(planner: ModelJsonPlanner) -> Any:
    if StateGraph is None:
        raise ImportError("langgraph is not installed yet")

    def business_profile_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:

        prompt = build_business_profile_prompt(
            state
        )

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

        try:
            inferred = (
                BusinessProfileInference
                .model_validate(
                    normalized
                )
            )
        except ValidationError:
            fallback_profile = (
                normalize_business_profile_payload(
                    {},
                    state,
                )
            )
            state.reasoning_notes.append(
                "Business profile output was incomplete. Used heuristic fallback classification."
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
        state.uncertainty_score = (
            1.0 - state.business_profile.confidence
        )

        if state.uncertainty_score > 0.4:
            state.reasoning_notes.append(
                "Business classification confidence is low. Expanding planning diversity."
            )

        return state

    def requirements_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:

        prompt = build_requirements_prompt(
            state
        )

        raw = planner.generate_text(
            prompt
        )

        parsed = parse_json_object(
            raw
        )

        normalized = normalize_requirements_payload(
            parsed,
            state,
        )

        state.requirements_spec = (
            RequirementsSpec.model_validate(
                normalized
            )
        )

        return state

    def strategy_hypothesis_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:

        prompt = build_strategy_prompt(
            state
        )

        try:
            hypotheses = planner.generate_model(
                prompt,
                StrategyHypothesisSet,
            )
        except ValidationError:
            state.reasoning_notes.append(
                "Strategy hypothesis generation failed. Used local fallback strategies."
            )
            hypotheses = (
                build_fallback_strategy_hypotheses(
                    state
                )
            )

        state.strategy_hypotheses = (
            hypotheses.strategies
        )

        return state

    def design_candidates_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:
        state.revision_iteration += 1

        prompt = build_design_candidates_prompt(
            state
        )

        raw = planner.generate_text(
            prompt
        )

        parsed = parse_json_object(
            raw
        )

        normalized = normalize_candidate_set_payload(
            parsed,
            state,
        )

        candidates = (
            DesignCandidateSet.model_validate(
                normalized
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

        return state

    def critique_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:

        prompt = build_critique_prompt(
            state
        )

        raw = planner.generate_text(
            prompt
        )

        parsed = parse_json_object(
            raw
        )

        normalized = normalize_critique_set_payload(
            parsed
        )

        critiques = (
            CritiqueReportSet.model_validate(
                normalized
            )
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

        return state

    def reflection_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:

        prompt = build_reflection_prompt(
            state
        )

        try:
            reflection = planner.generate_model(
                prompt,
                ReflectionReport,
            )
        except ValidationError:
            state.reasoning_notes.append(
                "Reflection generation failed. Used local fallback reflection."
            )
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

        return state

    def debate_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:

        try:
            outcome = planner.generate_model(
                build_debate_prompt(state),
                DebateOutcome,
            )
        except ValidationError:
            state.reasoning_notes.append(
                "Debate generation failed. Used local fallback debate."
            )
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
                for obs in outcome.strategic_observations
            ]
        )

        return state

    def simulation_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:

        try:
            simulation = planner.generate_model(
                build_simulation_prompt(state),
                SimulationReport,
            )
        except ValidationError:
            state.reasoning_notes.append(
                "Simulation generation failed. Used local fallback simulation."
            )
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

        for issue in (
            simulation.systemic_issues
        ):
            state.reasoning_notes.append(
                f"Simulation issue: {issue}"
            )

        return state

    def revise_node(
        state: WebsiteAgentState,
    ) -> WebsiteAgentState:

        prompt = build_revision_prompt(
            state
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

        except Exception:
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

        return state

    def critique_router(
        state: WebsiteAgentState,
    ) -> str:
        # Hard revision cap to prevent endless loops if routing keeps requesting regeneration.
        # Note: design_candidates_node increments revision_iteration.
        MAX_REVISION_ITERATIONS = 4
        if state.revision_iteration >= MAX_REVISION_ITERATIONS:
            state.reasoning_notes.append(
                (
                    "Reached maximum revision iterations "
                    f"({MAX_REVISION_ITERATIONS}). Proceeding to final synthesis."
                )
            )
            return "revise"

        if (
            state.simulation_report
            and state.simulation_report.overall_realism_score < 6
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
        ):
            state.reasoning_notes.append(
                (
                    "Debate confidence low. "
                    "Expanding strategic search."
                )
            )
            return "design_candidates"

        if (
            state.reflection_report
            and state.reflection_report.should_expand_exploration
        ):
            state.reasoning_notes.append(
                (
                    "Reflection agent requested "
                    "expanded strategic exploration."
                )
            )
            return "design_candidates"

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

        return "revise"

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
        "requirements",
    )

    graph.add_edge(
        "requirements",
        "strategy_hypotheses",
    )

    graph.add_edge(
        "strategy_hypotheses",
        "design_candidates",
    )

    graph.add_edge(
        "design_candidates",
        "critique",
    )

    graph.add_edge(
        "critique",
        "reflection",
    )

    graph.add_edge(
        "reflection",
        "debate",
    )

    graph.add_edge(
        "debate",
        "simulation",
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
    # - Loop signature repeat cap
    MAX_STREAM_UPDATES = 60
    MAX_SIGNATURE_REPEATS = 6
    signature_repeat_count: dict[tuple, int] = {}

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
        final_state = event

        # cycle detection using latest state (graph emits partial updates but final_state will accumulate)
        try:
            if hasattr(final_state, "get"):
                # if event is dict-like, we can't reliably reconstruct state; use state object
                sig = _state_cycle_signature(state)
            else:
                sig = _state_cycle_signature(state)
        except Exception:
            sig = None

        if sig is not None:
            signature_repeat_count[sig] = signature_repeat_count.get(sig, 0) + 1
            if signature_repeat_count[sig] >= MAX_SIGNATURE_REPEATS:
                raise RuntimeError(
                    "graph appears to be stuck in a planning loop (cycle signature repeated "
                    f"{MAX_SIGNATURE_REPEATS} times)."
                )

    try:
        validated = (
            WebsiteAgentState.model_validate(
                final_state
            )
        )

        return {
            "final_state": validated.model_dump(),
            "events": events,
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


def build_requirements_prompt(state: WebsiteAgentState) -> str:
    assert state.business_profile is not None
    rulebook = VERTICAL_RULEBOOKS.get(state.business_profile.vertical)
    return dedent(
        f"""
        You are the Requirements Agent.

        Build a RequirementsSpec JSON object only.

        Current uncertainty score:
        {state.uncertainty_score}

        Business profile:
        {state.business_profile.model_dump()}

        Vertical rulebook guidance:
        {rulebook}

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
) -> str:

    assert (
        state.business_profile
        is not None
    )

    assert (
        state.requirements_spec
        is not None
    )

    return dedent(
        f"""
        You are the Strategy Agent
        for an autonomous AI
        web agency.

        Generate a
        StrategyHypothesisSet
        JSON object only.

        Business profile:
        {state.business_profile.model_dump()}

        Requirements:
        {state.requirements_spec.model_dump()}

        Current uncertainty score:
        {state.uncertainty_score}

        Asset evidence:
        {serialize_asset_extractions(state.asset_extractions)}

        Reasoning notes:
        {state.reasoning_notes}

        Requirements:

        - generate 3 genuinely
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

    asset_digest = summarize_asset_evidence(
        state.asset_extractions
    )

    return dedent(
        f"""
        You are the Layout Planner Agent
        for an autonomous AI web agency.

        Build a DesignCandidateSet
        JSON object only.

        Business profile:
        {state.business_profile.model_dump()}

        Requirements:
        {state.requirements_spec.model_dump()}

        Strategy hypotheses:
        {[strategy.model_dump() for strategy in state.strategy_hypotheses]}

        Previous critique history:
        {state.critique_history}

        Asset evidence:
        {serialize_asset_extractions(state.asset_extractions)}

        Asset evidence summary:
        {asset_digest}

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

        - every section must include:
          - purpose
          - rationale

        - every rationale must reference:
          - business goals
          - workflow behavior
          - user intent
          - extracted asset evidence
          - visual cues
          - operational signals

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


def build_critique_prompt(state: WebsiteAgentState) -> str:
    assert state.business_profile is not None
    assert state.requirements_spec is not None
    asset_digest = summarize_asset_evidence(state.asset_extractions)
    rulebook = VERTICAL_RULEBOOKS.get(state.business_profile.vertical)
    return dedent(
        f"""
        You are the Design Critic Agent.

        Build a CritiqueReportSet JSON object only.

        Current uncertainty score:
        {state.uncertainty_score}

        Business profile:
        {state.business_profile.model_dump()}

        Requirements:
        {state.requirements_spec.model_dump()}

        Candidates:
        {[candidate.model_dump() for candidate in state.design_candidates]}

        Asset evidence summary:
        {asset_digest}
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
) -> str:

    assert (
        state.business_profile
        is not None
    )

    assert (
        state.requirements_spec
        is not None
    )

    asset_digest = summarize_asset_evidence(
        state.asset_extractions
    )

    return dedent(
        f"""
        You are the Revision Agent
        for an autonomous AI web agency.

        Build a final DesignSpec
        JSON object only.

        Business profile:
        {state.business_profile.model_dump()}

        Requirements:
        {state.requirements_spec.model_dump()}

        Strategy hypotheses:
        {[strategy.model_dump() for strategy in state.strategy_hypotheses]}

        Candidates:
        {[candidate.model_dump() for candidate in state.design_candidates]}

        Critiques:
        {[critique.model_dump() for critique in state.critique_reports]}

        Previous critique iterations:
        {state.critique_history}

        Asset evidence summary:
        {asset_digest}

        Requirements:

        - choose the strongest candidate
          based on:
          - business goals
          - workflow clarity
          - critique quality
          - strategic coherence
          - behavioral optimization

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
) -> str:

    return dedent(
        f"""
        You are the Reflection Agent
        for an autonomous AI
        planning system.

        Analyze the reasoning quality
        of the planning process itself.

        Generate a ReflectionReport
        JSON object only.

        Business profile:
        {state.business_profile.model_dump() if state.business_profile else None}

        Strategy hypotheses:
        {[strategy.model_dump() for strategy in state.strategy_hypotheses]}

        Candidate history:
        {state.candidate_history}

        Critique history:
        {state.critique_history}

        Reasoning notes:
        {state.reasoning_notes}

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
) -> str:

    return dedent(
        f"""
        You are the Debate Agent
        for an autonomous AI
        planning system.

        Generate a DebateOutcome
        JSON object only.

        Business profile:
        {state.business_profile.model_dump() if state.business_profile else None}

        Strategy hypotheses:
        {[strategy.model_dump() for strategy in state.strategy_hypotheses]}

        Design candidates:
        {[candidate.model_dump() for candidate in state.design_candidates]}

        Critiques:
        {[critique.model_dump() for critique in state.critique_reports]}

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
) -> str:

    return dedent(
        f"""
        You are the Simulation Agent
        for an autonomous AI
        planning system.

        Generate a SimulationReport
        JSON object only.

        Business profile:
        {state.business_profile.model_dump() if state.business_profile else None}

        Final candidates:
        {[candidate.model_dump() for candidate in state.design_candidates]}

        Debate outcome:
        {state.debate_outcome.model_dump() if state.debate_outcome else None}

        Critique history:
        {state.critique_history}

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

    required_pages = (
        candidate.get(
            "required_pages"
        )
        or rulebook.get(
            "required_pages",
            [],
        )
    )

    required_workflows = (
        candidate.get(
            "required_workflows"
        )
        or rulebook.get(
            "required_workflows",
            [WorkflowType.LEAD],
        )
    )

    return {

        "required_pages":
            required_pages,

        "required_workflows":
            required_workflows,

        "trust_requirements":
            normalize_string_list(
                candidate.get(
                    "trust_requirements"
                )
                or rulebook.get(
                    "must_prioritize",
                    [],
                )
            ),

        "compliance_requirements":
            normalize_string_list(
                candidate.get(
                    "compliance_requirements"
                )
                or []
            ),

        "conversion_priorities":
            normalize_string_list(
                candidate.get(
                    "conversion_priorities"
                )
                or rulebook.get(
                    "must_prioritize",
                    [],
                )
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
    if isinstance(candidate.get("candidates"), list):
        raw_candidates = candidate["candidates"]
    elif isinstance(candidate.get("DesignCandidateSet"), list):
        raw_candidates = candidate["DesignCandidateSet"]
    elif isinstance(payload.get("DesignCandidateSet"), list):
        raw_candidates = payload["DesignCandidateSet"]
    return {"candidates": [normalize_design_candidate(item, index, state) for index, item in enumerate(raw_candidates, start=1)]}


def normalize_critique_set_payload(payload: dict[str, Any]) -> dict[str, Any]:
    candidate = payload
    for key in ("CritiqueReportSet", "critique_report_set", "result"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            candidate = nested
            break
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


def normalize_design_candidate(candidate: dict[str, Any], index: int, state: WebsiteAgentState) -> dict[str, Any]:
    mode = determine_candidate_mode(candidate)

    strategy = (
        state.strategy_hypotheses[
            min(
                index - 1,
                len(state.strategy_hypotheses) - 1,
            )
        ]
        if state.strategy_hypotheses
        else None
    )

    pages = candidate.get("pages") or candidate.get("page_specs") or candidate.get("page_plan") or []
    if not isinstance(pages, list) or not pages:
        pages = [
            {"type": page_type.value if isinstance(page_type, PageType) else str(page_type)}
            for page_type in (state.requirements_spec.required_pages if state.requirements_spec else [PageType.HOME])
        ]
    return {
        "candidate_id": candidate.get("candidate_id") or candidate.get("id") or f"candidate_{index}",

        "rationale": (
            candidate.get("rationale")
            or candidate.get("summary")
            or (
                strategy.core_thesis
                if strategy
                else None
            )
            or candidate.get("description")
            or candidate.get("name")
            or "Model-generated candidate selected for business fit."
        ),
        "confidence": normalize_confidence(candidate.get("confidence", 0.72)),
        "visual_system": normalize_visual_system(
            candidate.get("visual_system") or candidate.get("visual") or candidate.get("style") or {},
            state,
            mode,
        ),
        "primary_action": normalize_primary_action(
            candidate.get("primary_action") or candidate.get("cta") or candidate.get("call_to_action") or {},
            state,
            mode,
        ),
        "pages": [
            normalize_page_spec(
                page,
                page_index,
                state,
                mode,
            )
            for page_index, page in enumerate(
                pages,
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
    critique_map = {report.candidate_id: average_critique_score(report) for report in state.critique_reports}
    return max(
        state.design_candidates,
        key=lambda candidate: (critique_map.get(candidate.candidate_id, 0.0), candidate.confidence),
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
