from __future__ import annotations

from agentic_models import (
    MediaBias,
    PageType,
    RiskLevel,
    SectionType,
    Vertical,
    VisualDensity,
    VisualTone,
    WorkflowType,
)


VERTICAL_RULEBOOKS = {
    Vertical.RESTAURANT: {
        "risk_level": RiskLevel.STANDARD,
        "required_pages": [PageType.HOME, PageType.MENU, PageType.ORDER, PageType.CONTACT],
        "required_workflows": [WorkflowType.ORDER],
        "preferred_tones": [VisualTone.ENERGETIC, VisualTone.MODERN],
        "preferred_density": VisualDensity.HIGH,
        "preferred_media_bias": MediaBias.IMAGE_HEAVY,
        "required_sections": [SectionType.HERO_OFFER_BANNER, SectionType.MENU_SHOWCASE, SectionType.PRIMARY_WORKFLOW_FORM],
        "must_prioritize": ["price visibility", "item visibility", "fast ordering", "offer visibility"],
        "avoid": ["text-heavy hero copy", "hidden pricing", "weak food imagery"],
    },
    Vertical.CLINIC: {
        "risk_level": RiskLevel.REGULATED,
        "required_pages": [PageType.HOME, PageType.SERVICES, PageType.BOOKING, PageType.CONTACT],
        "required_workflows": [WorkflowType.BOOKING],
        "preferred_tones": [VisualTone.CALM, VisualTone.TRUSTWORTHY],
        "preferred_density": VisualDensity.MEDIUM,
        "preferred_media_bias": MediaBias.TRUST_FIRST,
        "required_sections": [SectionType.HERO_TRUST_BANNER, SectionType.DOCTOR_PROFILES, SectionType.PRIMARY_WORKFLOW_FORM],
        "must_prioritize": ["trust", "credentials", "booking clarity", "privacy cues"],
        "avoid": ["aggressive promotional tone", "diagnosis claims", "hidden contact details"],
    },
    Vertical.REPAIR_SERVICE: {
        "risk_level": RiskLevel.STANDARD,
        "required_pages": [PageType.HOME, PageType.SERVICES, PageType.CONTACT],
        "required_workflows": [WorkflowType.LEAD],
        "preferred_tones": [VisualTone.PRACTICAL],
        "preferred_density": VisualDensity.MEDIUM,
        "preferred_media_bias": MediaBias.COPY_FIRST,
        "required_sections": [SectionType.HERO_TRUST_BANNER, SectionType.SERVICE_CARDS, SectionType.PRIMARY_WORKFLOW_FORM],
        "must_prioritize": ["clarity", "speed to quote", "service areas", "phone visibility"],
        "avoid": ["decorative clutter", "unclear service list"],
    },
}

