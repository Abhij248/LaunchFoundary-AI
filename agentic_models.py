from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from typing import Optional, Any
from datetime import datetime


class CognitiveEvent(BaseModel):
    timestamp: str
    event_type: str

    stage: str
    title: str
    summary: str

    confidence: Optional[float] = None

    candidate_id: Optional[str] = None

    metadata: dict[str, Any] = {}

class Vertical(str, Enum):
    RESTAURANT = "restaurant"
    CAFE = "cafe"
    BAKERY = "bakery"
    CLINIC = "clinic"
    SALON = "salon"
    TUTOR = "tutor"
    REPAIR_SERVICE = "repair_service"
    CONSULTANT = "consultant"
    UNKNOWN = "unknown"

class StrategyHypothesis(BaseModel):
    strategy_id: str

    name: str

    core_thesis: str

    target_behavior: str

    strengths: list[str] = Field(default_factory=list)

    risks: list[str] = Field(default_factory=list)

    ideal_for: list[str] = Field(default_factory=list)

    tradeoffs: list[str] = Field(default_factory=list)

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )




class StrategyHypothesisSet(BaseModel):
    strategies: list[StrategyHypothesis]

class ReflectionReport(BaseModel):
    exploration_quality: int = Field(
        ge=1,
        le=10,
    )

    strategic_diversity: int = Field(
        ge=1,
        le=10,
    )

    critique_depth: int = Field(
        ge=1,
        le=10,
    )

    reasoning_quality: int = Field(
        ge=1,
        le=10,
    )

    convergence_risk: int = Field(
        ge=1,
        le=10,
    )

    observations: list[str] = Field(
        default_factory=list
    )

    improvement_actions: list[str] = Field(
        default_factory=list
    )

    should_expand_exploration: bool = False

class DebateOutcome(BaseModel):
    winning_candidate_id: str

    losing_candidate_id: str

    winner_reasoning: str

    loser_reasoning: str

    tradeoff_analysis: list[str] = Field(
        default_factory=list
    )

    synthesis_opportunities: list[str] = Field(
        default_factory=list
    )

    strategic_observations: list[str] = Field(
        default_factory=list
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

class WorkflowSimulation(BaseModel):
    persona: str

    goal: str

    journey_summary: str

    friction_points: list[str] = Field(
        default_factory=list
    )

    trust_observations: list[str] = Field(
        default_factory=list
    )

    confusion_points: list[str] = Field(
        default_factory=list
    )

    conversion_barriers: list[str] = Field(
        default_factory=list
    )

    successful: bool = True

    realism_score: int = Field(
        ge=1,
        le=10,
    )


class SimulationReport(BaseModel):
    simulations: list[WorkflowSimulation]

    overall_realism_score: int = Field(
        ge=1,
        le=10,
    )

    systemic_issues: list[str] = Field(
        default_factory=list
    )

    recommended_improvements: list[str] = Field(
        default_factory=list
    )


class RiskLevel(str, Enum):
    STANDARD = "standard"
    REGULATED = "regulated"


class ProvenanceSource(str, Enum):
    USER_INPUT = "user_input"
    ASSET_EXTRACTION = "asset_extraction"
    EXTERNAL_MODEL = "external_model"
    HEURISTIC_FALLBACK = "heuristic_fallback"
    LOCAL_FALLBACK = "local_fallback"
    MEMORY_RETRIEVAL = "memory_retrieval"
    RULEBOOK = "rulebook"
    GRAPH_ROUTER = "graph_router"
    BEHAVIORAL_SYSTEM = "behavioral_system"


class WorkflowType(str, Enum):
    ORDER = "order"
    BOOKING = "booking"
    LEAD = "lead"


class VisualTone(str, Enum):
    ENERGETIC = "energetic"
    TRUSTWORTHY = "trustworthy"
    CALM = "calm"
    MODERN = "modern"
    PREMIUM = "premium"
    PRACTICAL = "practical"


class VisualDensity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MediaBias(str, Enum):
    IMAGE_HEAVY = "image_heavy"
    BALANCED = "balanced"
    COPY_FIRST = "copy_first"
    TRUST_FIRST = "trust_first"


class PageType(str, Enum):
    HOME = "home"
    MENU = "menu"
    ORDER = "order"
    RESERVATIONS = "reservations"
    SERVICES = "services"
    BOOKING = "booking"
    ABOUT = "about"
    CONTACT = "contact"


class SectionType(str, Enum):
    HERO_OFFER_BANNER = "hero_offer_banner"
    HERO_TRUST_BANNER = "hero_trust_banner"
    PAGE_NAV = "page_nav"
    GALLERY_STRIP = "gallery_strip"
    MENU_SHOWCASE = "menu_showcase"
    FEATURE_GRID = "feature_grid"
    TRUST_BAND = "trust_band"
    REVIEW_BAND = "review_band"
    PROOF_BAND = "proof_band"
    PRIMARY_WORKFLOW_FORM = "primary_workflow_form"
    DOCTOR_PROFILES = "doctor_profiles"
    SERVICE_CARDS = "service_cards"
    CATEGORY_STRIP = "category_strip"


class PrimaryActionSpec(BaseModel):
    label: str = Field(min_length=2, max_length=40)
    kind: WorkflowType
    placements: list[Literal["hero", "sticky", "section_end", "menu_card"]] = Field(default_factory=list)


class AssetExtractionInfo(BaseModel):
    business_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    hours: str | None = None
    services_or_items: list[str] = Field(default_factory=list)
    prices: list[str | float | int | list[float | int]] = Field(default_factory=list)
    offers: list[str] = Field(default_factory=list)


class AssetExtraction(BaseModel):
    image: str
    asset_type: str
    business_signals: list[str] = Field(default_factory=list)
    extracted_business_info: AssetExtractionInfo = Field(default_factory=AssetExtractionInfo)
    recommended_pages: list[str] = Field(default_factory=list)
    recommended_features: list[str] = Field(default_factory=list)
    trust_or_compliance_notes: list[str] = Field(default_factory=list)
    visual_brand_cues: list[str] = Field(default_factory=list)
    planner_notes: str = ""


class BusinessProfile(BaseModel):
    name: str
    location: str
    goal: str
    vertical: Vertical
    subtype: str
    risk_level: RiskLevel
    audience: list[str] = Field(default_factory=list)
    evidence_summary: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class BusinessProfileInference(BaseModel):
    
    vertical: Vertical
    subtype: str
    risk_level: RiskLevel
    audience: list[str] = Field(default_factory=list)
    evidence_summary: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

class CanonicalBusinessIdentity(
    BaseModel
):
    vertical: Vertical

    subtype: str

    risk_level: RiskLevel

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    behavioral_archetypes: list[str] = Field(
        default_factory=list
    )

    dominant_behavior_pattern: str = "unknown"

    trust_model: str = "standard"

    conversion_model: str = "standard"

    primary_workflow: WorkflowType = (
        WorkflowType.LEAD
    )

    allowed_features: list[str] = Field(
        default_factory=list
    )

    allowed_pages: list[str] = Field(
        default_factory=list
    )

    forbidden_semantics: list[str] = Field(
        default_factory=list
    )

class RequirementsSpec(BaseModel):
    required_pages: list[PageType]
    required_workflows: list[WorkflowType]
    trust_requirements: list[str] = Field(default_factory=list)
    compliance_requirements: list[str] = Field(default_factory=list)
    conversion_priorities: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    avoid_patterns: list[str] = Field(default_factory=list)
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list)


class VisualSystemSpec(BaseModel):
    tone: VisualTone
    density: VisualDensity
    media_bias: MediaBias
    trust_emphasis: Literal["low", "medium", "high"]


class SectionSpec(BaseModel):
    type: SectionType
    purpose: str = Field(min_length=8, max_length=240)
    rationale: str = Field(min_length=8, max_length=240)
    priority: int = Field(ge=1, le=10)


class PageSpec(BaseModel):
    page_type: PageType
    title: str = Field(min_length=2, max_length=80)
    sections: list[SectionSpec]

    @field_validator("sections")
    @classmethod
    def sections_must_not_be_empty(cls, value: list[SectionSpec]) -> list[SectionSpec]:
        if not value:
            raise ValueError("page must contain at least one section")
        return value


class DesignCandidate(BaseModel):
    candidate_id: str
    rationale: str = Field(min_length=12, max_length=400)
    confidence: float = Field(ge=0.0, le=1.0)
    visual_system: VisualSystemSpec
    primary_action: PrimaryActionSpec
    pages: list[PageSpec]


class DesignCandidateSet(BaseModel):
    candidates: list[DesignCandidate]


class CritiqueScore(BaseModel):
    criterion: Literal["conversion", "trust", "usability", "business_fit", "completeness"]
    score: int = Field(ge=1, le=10)
    reasoning: str = Field(min_length=8, max_length=220)


class TradeoffAnalysis(BaseModel):
    advantage: str = Field(min_length=12, max_length=220)
    sacrifice: str = Field(min_length=12, max_length=220)
    ideal_for: str = Field(min_length=12, max_length=220)
    risk: str = Field(min_length=12, max_length=220)


class CritiqueReport(BaseModel):
    candidate_id: str
    summary: str = Field(min_length=12, max_length=300)

    scores: list[CritiqueScore]

    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)

    revision_instructions: list[str] = Field(default_factory=list)

    tradeoffs: list[TradeoffAnalysis] = Field(default_factory=list)

    predicted_effects: list[str] = Field(default_factory=list)

    rejection_reason: str = Field(default="")


class CritiqueReportSet(BaseModel):
    critiques: list[CritiqueReport]


class DesignSpec(BaseModel):
    brief: str = Field(min_length=12, max_length=400)
    chosen_candidate_id: str
    primary_goal: str
    visual_system: VisualSystemSpec
    primary_action: PrimaryActionSpec
    pages: list[PageSpec]
    decision_rationale: list[str] = Field(default_factory=list)


class FinalizationDecision(BaseModel):
    finalize_now: bool = False
    selected_candidate_id: str = ""
    authority: str = "router"
    reason: str = ""
    readiness_score: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
    )
    confidence_weighted_score: float = Field(
        ge=0.0,
        le=10.0,
        default=0.0,
    )
    supporting_signals: list[str] = Field(
        default_factory=list
    )

class ClarificationQuestion(
    BaseModel
):
    question_id: str
    question: str
    options: list[str] = []
    reasoning: str = ""
    priority: int = 1


class BehavioralContext(
    BaseModel
):
    key: str

    trust_requirement: str

    urgency_level: str

    conversion_latency: str

    visual_dependency: str

    operational_complexity: str

    preferred_cta_style: list[str] = Field(
        default_factory=list
    )

    trust_signals: list[str] = Field(
        default_factory=list
    )

    preferred_sections: list[str] = Field(
        default_factory=list
    )

    conversion_risks: list[str] = Field(
        default_factory=list
    )

class AgentDecision(
    BaseModel
):

    confidence: float = 0.5

    exploration_required: bool = False

    critique_required: bool = False

    simulation_required: bool = False

    memory_retrieval_required: bool = False

    recommend_revision: bool = False

    reasoning: list[str] = Field(
        default_factory=list
    )

class CognitiveHealthReport(
    BaseModel
):

    exploration_quality: float

    reasoning_diversity: float

    convergence_risk: float

    critique_depth: float

    hallucination_risk: float

    cognition_stability: float

    notes: list[str] = Field(
        default_factory=list
    )

class AgentDecision(
    BaseModel
):

    confidence: float = 0.5

    exploration_required: bool = False

    critique_required: bool = False

    simulation_required: bool = False

    memory_retrieval_required: bool = False

    recommend_revision: bool = False

    reasoning: list[str] = Field(
        default_factory=list
    )

class WebsiteAgentState(BaseModel):


    cognitive_events: list[CognitiveEvent] = Field(default_factory=list)
    cognitive_health: CognitiveHealthReport | None = None

    agent_decisions: dict[
        str,
        AgentDecision
    ] = Field(
        default_factory=dict
    )
    execution_trace: list[str] = Field(default_factory=list)
    node_visit_counts: dict[str, int] = Field(default_factory=dict)
    behavioral_blend: BehavioralBlend | None = None
    behavioral_contexts: list[BehavioralContext] = Field(default_factory=list)
    simulation_report: SimulationReport | None = None
    debate_outcome: DebateOutcome | None = None
    uncertainty_score: float = 0.0
    reflection_report: ReflectionReport | None = None
    reasoning_notes: list[str] = Field(default_factory=list)
    business_input: dict
    uploaded_asset_paths: list[str] = Field(default_factory=list)
    asset_extractions: list[AssetExtraction] = Field(default_factory=list)
    business_profile: BusinessProfile | None = None
    business_identity: (CanonicalBusinessIdentity| None) = None
    requirements_spec: RequirementsSpec | None = None
    strategy_hypotheses: list[StrategyHypothesis] = Field(default_factory=list)
    revision_iteration: int = 0
    candidate_history: list[dict] = Field(default_factory=list)
    critique_history: list[dict] = Field(default_factory=list)
    design_candidates: list[DesignCandidate] = Field(default_factory=list)
    critique_reports: list[CritiqueReport] = Field(default_factory=list)
    design_spec: DesignSpec | None = None
    finalization_decision: FinalizationDecision | None = None
    qa_notes: list[str] = Field(default_factory=list)
    provenance_log: list["CognitiveProvenanceRecord"] = Field(default_factory=list)
    reasoning_lineage: list["ReasoningLineageEntry"] = Field(default_factory=list)
    state_artifacts: dict[str, "StateArtifactStatus"] = Field(default_factory=dict)
    active_fallbacks: list[str] = Field(default_factory=list)
    memory_query: MemoryQuery | None = None
    retrieved_memories: list[RetrievedMemory] = Field(default_factory=list)
    tool_invocations: list["ToolInvocationRecord"] = Field(default_factory=list)

class BehavioralArchetypeWeight(
    BaseModel
):
    archetype: str

    weight: float = Field(
        ge=0.0,
        le=1.0,
    )

    dominance_rank: int = Field(
        ge=1,
    )


class BehavioralBlend(
    BaseModel
):
    dominant_archetype: str

    secondary_archetypes: list[str] = Field(
        default_factory=list
    )

    weights: list[
        BehavioralArchetypeWeight
    ] = Field(
        default_factory=list
    )

    synthesis_mode: str = ""

    conflict_notes: list[str] = Field(
        default_factory=list
    )


class CognitiveProvenanceRecord(
    BaseModel
):
    artifact_key: str
    stage: str
    source_type: ProvenanceSource
    summary: str
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
    fallback_used: bool = False
    iteration: int = 0
    supporting_keys: list[str] = Field(
        default_factory=list
    )


class ReasoningLineageEntry(
    BaseModel
):
    stage: str
    decision: str
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
    fallback_used: bool = False
    inputs: list[str] = Field(
        default_factory=list
    )
    outputs: list[str] = Field(
        default_factory=list
    )
    summary: str = ""


class StateArtifactStatus(
    BaseModel
):
    artifact_key: str
    status: Literal[
        "empty",
        "derived",
        "fallback",
        "finalized",
    ] = "derived"
    source_type: ProvenanceSource
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
    updated_in_stage: str
    summary: str = ""
    lineage_ref: str = ""


class MemoryQuery(
    BaseModel
):
    vertical: str = "unknown"
    subtype: str = "general"
    risk_level: str = "standard"
    primary_workflow: str = "lead"
    behavioral_archetypes: list[str] = Field(
        default_factory=list
    )
    evidence_tags: list[str] = Field(
        default_factory=list
    )
    retrieval_goal: str = ""


class RetrievedMemory(
    BaseModel
):
    memory_id: str
    category: Literal[
        "vertical_pattern",
        "workflow_pattern",
        "behavioral_pattern",
        "trust_pattern",
        "offer_pattern",
    ]
    title: str
    summary: str
    applicability: str = ""
    recommended_actions: list[str] = Field(
        default_factory=list
    )
    anti_patterns: list[str] = Field(
        default_factory=list
    )
    evidence_tags: list[str] = Field(
        default_factory=list
    )
    relevance: float = Field(
        ge=0.0,
        le=1.0,
    )


class MemoryRetrievalBundle(
    BaseModel
):
    query: MemoryQuery
    memories: list[RetrievedMemory] = Field(
        default_factory=list
    )
    retrieval_confidence: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
    )
    notes: list[str] = Field(
        default_factory=list
    )


class ToolInvocationRecord(
    BaseModel
):
    stage: str
    tool_name: str
    purpose: str
    output_keys: list[str] = Field(
        default_factory=list
    )
    summary: str = ""
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
    )


WebsiteAgentState.model_rebuild()
