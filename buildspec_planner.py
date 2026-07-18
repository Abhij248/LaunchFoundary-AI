from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FeatureModule:
    key: str
    label: str
    applicable_to: list[str]
    requires: list[str]
    backend: list[str]
    qa: list[str]
    trust: list[str] = field(default_factory=list)
    compliance: list[str] = field(default_factory=list)
    impact: str = "medium"
    complexity: str = "medium"
    # Businesses outside the curated `applicable_to` vertical list still
    # qualify for this feature when their business_shape matches one of these.
    applicable_to_shapes: list[str] = field(default_factory=list)


FEATURE_REGISTRY: dict[str, FeatureModule] = {
    "online_ordering": FeatureModule(
        key="online_ordering",
        label="Online ordering",
        applicable_to=["restaurant", "cafe", "bakery"],
        applicable_to_shapes=["storefront_commerce"],
        requires=["menu_items", "business_hours"],
        backend=["menu_items_table", "orders_table", "cart", "order_status", "admin_orders"],
        qa=["add_to_cart", "submit_order", "admin_order_visible"],
        trust=["clear_prices", "pickup_delivery_info"],
        compliance=["allergen_notice"],
        impact="high",
        complexity="medium",
    ),
    "table_reservation": FeatureModule(
        key="table_reservation",
        label="Table reservation",
        applicable_to=["restaurant", "cafe"],
        requires=["business_hours", "contact_email"],
        backend=["reservations_table", "availability_slots", "admin_reservations"],
        qa=["reservation_submit", "admin_reservation_visible"],
        trust=["opening_hours", "location"],
        impact="high",
        complexity="medium",
    ),
    "appointment_booking": FeatureModule(
        key="appointment_booking",
        label="Appointment booking",
        applicable_to=["clinic", "salon", "tutor", "consultant", "repair_service"],
        requires=["business_hours", "contact_email"],
        backend=["bookings_table", "availability_rules", "admin_schedule"],
        qa=["booking_submit", "admin_booking_visible"],
        trust=["opening_hours", "phone_number"],
        compliance=["appointment_disclaimer"],
        impact="high",
        complexity="medium",
    ),
    "patient_intake": FeatureModule(
        key="patient_intake",
        label="Patient intake form",
        applicable_to=["clinic"],
        requires=["contact_email"],
        backend=["patient_intake_table", "admin_patient_intake"],
        qa=["intake_submit", "admin_intake_visible"],
        trust=["privacy_notice"],
        compliance=["medical_privacy_notice", "no_diagnosis_claims"],
        impact="high",
        complexity="medium",
    ),
    "lead_capture": FeatureModule(
        key="lead_capture",
        label="Lead capture",
        applicable_to=["restaurant", "cafe", "bakery", "clinic", "salon", "tutor", "consultant", "repair_service", "unknown"],
        applicable_to_shapes=["storefront_commerce", "scheduled_booking", "inquiry_lead", "portfolio_showcase", "catalog_reserve"],
        requires=["contact_email"],
        backend=["leads_table", "admin_leads"],
        qa=["lead_form_submit", "admin_lead_visible"],
        trust=["phone_number", "response_time"],
        impact="medium",
        complexity="low",
    ),
    "catalog_reservation": FeatureModule(
        key="catalog_reservation",
        label="Catalog reservation",
        applicable_to=[],
        applicable_to_shapes=["catalog_reserve"],
        requires=[],
        backend=["catalog_items_table", "holds_table", "admin_holds"],
        qa=["hold_submit", "admin_hold_visible"],
        trust=["availability_status"],
        impact="high",
        complexity="medium",
    ),
    "quote_request": FeatureModule(
        key="quote_request",
        label="Quote request",
        applicable_to=[],
        applicable_to_shapes=["inquiry_lead"],
        requires=["contact_email"],
        backend=["quotes_table", "admin_quotes"],
        qa=["quote_submit", "admin_quote_visible"],
        trust=["response_time", "phone_number"],
        impact="high",
        complexity="low",
    ),
    "portfolio_showcase": FeatureModule(
        key="portfolio_showcase",
        label="Portfolio showcase",
        applicable_to=[],
        applicable_to_shapes=["portfolio_showcase"],
        requires=[],
        backend=["portfolio_items_table", "admin_portfolio"],
        qa=["portfolio_item_visible"],
        trust=["case_study_evidence"],
        impact="high",
        complexity="medium",
    ),
}


VERTICAL_KEYWORDS: list[tuple[str, list[str]]] = [
    ("restaurant", ["restaurant", "diner", "bistro", "pizzeria", "food", "kitchen", "menu", "reservation", "catering"]),
    ("cafe", ["cafe", "coffee", "espresso", "bakery cafe"]),
    ("bakery", ["bakery", "cakes", "pastry", "bread", "cupcake"]),
    ("clinic", ["clinic", "dental", "doctor", "medical", "health", "patient", "therapy", "dentist"]),
    ("salon", ["salon", "spa", "hair", "beauty", "nails", "barber"]),
    ("tutor", ["tutor", "coaching", "academy", "classes", "lessons"]),
    ("repair_service", ["repair", "plumber", "electrician", "hvac", "mechanic"]),
    ("consultant", ["consultant", "agency", "advisor", "law firm", "accounting"]),
]


PAGE_PRESETS: dict[str, list[str]] = {
    "restaurant": ["Home", "Menu", "Order Online", "Reservations", "About", "Contact"],
    "cafe": ["Home", "Menu", "Order Online", "Events", "About", "Contact"],
    "bakery": ["Home", "Menu", "Custom Orders", "Gallery", "About", "Contact"],
    "clinic": ["Home", "Services", "Doctors", "Book Appointment", "Patient Intake", "Contact"],
    "salon": ["Home", "Services", "Book Appointment", "Gallery", "About", "Contact"],
    "tutor": ["Home", "Courses", "Book Trial Class", "Results", "About", "Contact"],
    "repair_service": ["Home", "Services", "Request Quote", "Service Areas", "Reviews", "Contact"],
    "consultant": ["Home", "Services", "Book Consultation", "Case Studies", "About", "Contact"],
    "unknown": ["Home", "Services", "Contact"],
}


# Curated transactional "shape" a business's backend/admin/checkout needs map
# onto. Kept deliberately small (unlike Vertical, which is an open label) since
# the DB schema, admin UI buckets, and cart/booking/lead-form rendering need a
# finite set of concrete implementations to build against.
VERTICAL_TO_SHAPE: dict[str, str] = {
    "restaurant": "storefront_commerce",
    "cafe": "storefront_commerce",
    "bakery": "storefront_commerce",
    "clinic": "scheduled_booking",
    "salon": "scheduled_booking",
    "tutor": "scheduled_booking",
    "consultant": "scheduled_booking",
    "repair_service": "inquiry_lead",
}


BUSINESS_SHAPE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("storefront_commerce", ["shop", "store", "ecommerce", "e-commerce", "sell", "product", "shipping", "checkout", "retail", "boutique", "merchandise", "movie", "cinema", "theatre", "theater", "showtime", "showtimes", "ticket", "tickets", "screening", "box office"]),
    ("portfolio_showcase", ["portfolio", "photography", "photographer", "gallery", "showcase", "creative", "design studio", "artist"]),
    ("catalog_reserve", ["library", "librarian", "book lending", "borrow", "lending", "loan program", "rental", "equipment rental", "reserve a copy", "hold a copy", "waitlist", "checkout a book"]),
    ("scheduled_booking", ["appointment", "booking", "schedule", "session", "class", "consultation", "visit"]),
    ("inquiry_lead", ["quote", "inquiry", "contact us", "get in touch", "request", "estimate"]),
]


SHAPE_PAGE_PRESETS: dict[str, list[str]] = {
    "storefront_commerce": ["Home", "Shop", "Cart", "About", "Contact"],
    "scheduled_booking": ["Home", "Services", "Book Now", "About", "Contact"],
    "inquiry_lead": ["Home", "Services", "Request a Quote", "About", "Contact"],
    "portfolio_showcase": ["Home", "Portfolio", "About", "Contact"],
    "catalog_reserve": ["Home", "Catalog", "My Holds", "About", "Contact"],
}


REGULATED_VERTICALS = {"clinic", "consultant"}


def classify_business_shape(raw_input: str, vertical_analysis: dict[str, Any]) -> str:
    vertical = vertical_analysis.get("vertical", "unknown")
    if vertical in VERTICAL_TO_SHAPE:
        return VERTICAL_TO_SHAPE[vertical]

    text = raw_input.lower()
    scores: dict[str, int] = {}
    for shape, keywords in BUSINESS_SHAPE_KEYWORDS:
        scores[shape] = sum(1 for keyword in keywords if keyword in text)

    best_shape = max(scores, key=scores.get)
    if scores[best_shape] == 0:
        return "inquiry_lead"

    return best_shape


def classify_vertical(raw_input: str) -> dict[str, Any]:
    text = raw_input.lower()
    scores: dict[str, int] = {}
    for vertical, keywords in VERTICAL_KEYWORDS:
        scores[vertical] = sum(1 for keyword in keywords if keyword in text)

    best_vertical = max(scores, key=scores.get)
    best_score = scores[best_vertical]
    if best_score == 0:
        return {
            "vertical": "unknown",
            "confidence": 0.35,
            "subtype": "general small business",
            "riskLevel": "standard",
        }

    confidence = min(0.95, 0.55 + best_score * 0.12)
    return {
        "vertical": best_vertical,
        "confidence": round(confidence, 2),
        "subtype": best_vertical.replace("_", " "),
        "riskLevel": "regulated" if best_vertical in REGULATED_VERTICALS else "standard",
    }


def detect_available_fields(profile: dict[str, Any], raw_input: str) -> set[str]:
    text = raw_input.lower()
    fields = set(profile.keys())

    if (
        "menu" in text or "pizza" in text or "pasta" in text or "coffee" in text
        or "product" in text or "catalog" in text or "merchandise" in text
        or "sell" in text or "shop" in text or "store" in text
        or "ticket" in text or "show" in text or "snack" in text
    ):
        fields.add("menu_items")
    if "hour" in text or "open" in text or profile.get("business_hours"):
        fields.add("business_hours")
    if "email" in text or "@" in text or profile.get("contact_email"):
        fields.add("contact_email")
    if "phone" in text or profile.get("phone"):
        fields.add("phone_number")
    if "location" in text or "address" in text or profile.get("location"):
        fields.add("location")

    return fields


def select_features(vertical: str, available_fields: set[str], shape: str = "") -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    included: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    missing: set[str] = set()

    for feature in FEATURE_REGISTRY.values():
        applies_by_vertical = vertical in feature.applicable_to or "unknown" in feature.applicable_to
        applies_by_shape = bool(shape) and shape in feature.applicable_to_shapes
        if not applies_by_vertical and not applies_by_shape:
            continue

        unmet = [field for field in feature.requires if field not in available_fields]
        decision = {
            "key": feature.key,
            "label": feature.label,
            "impact": feature.impact,
            "complexity": feature.complexity,
            "backend": feature.backend,
            "qa": feature.qa,
            "trust": feature.trust,
            "compliance": feature.compliance,
        }

        if unmet and feature.key != "lead_capture":
            missing.update(unmet)
            skipped.append({
                **decision,
                "reason": f"Skipped because missing required info: {', '.join(unmet)}",
            })
        else:
            reason_subject = vertical.replace("_", " ") if applies_by_vertical else shape.replace("_", " ")
            included.append({
                **decision,
                "reason": f"Included because it is high-value for {reason_subject} businesses.",
            })

    if not included:
        lead = FEATURE_REGISTRY["lead_capture"]
        included.append({
            "key": lead.key,
            "label": lead.label,
            "impact": lead.impact,
            "complexity": lead.complexity,
            "backend": lead.backend,
            "qa": lead.qa,
            "trust": lead.trust,
            "compliance": lead.compliance,
            "reason": "Fallback module included so the business can capture customer interest immediately.",
        })

    return included, skipped, sorted(missing)


def readiness_scores(vertical: str, included_features: list[dict[str, Any]], missing_info: list[str]) -> dict[str, int]:
    feature_bonus = min(12, len(included_features) * 4)
    missing_penalty = min(16, len(missing_info) * 4)
    compliance_bonus = 6 if vertical in REGULATED_VERTICALS else 2

    return {
        "seo": max(70, 84 + feature_bonus // 2 - missing_penalty),
        "ux": max(70, 86 + feature_bonus // 2 - missing_penalty // 2),
        "trust": max(65, 80 + feature_bonus - missing_penalty),
        "conversion": max(65, 82 + feature_bonus - missing_penalty),
        "compliance": max(70, 84 + compliance_bonus - missing_penalty // 2),
    }


def generate_build_spec(profile: dict[str, Any], raw_input: str) -> dict[str, Any]:
    vertical_analysis = classify_vertical(raw_input)
    vertical = vertical_analysis["vertical"]
    shape = classify_business_shape(raw_input, vertical_analysis)
    if vertical == "unknown":
        vertical_analysis["subtype"] = f"{shape.replace('_', ' ')} business"
    available_fields = detect_available_fields(profile, raw_input)
    included, skipped, missing = select_features(vertical, available_fields, shape)

    trust = sorted({item for feature in included for item in feature["trust"]})
    compliance = sorted({item for feature in included for item in feature["compliance"]})
    qa = sorted({item for feature in included for item in feature["qa"]})
    backend = sorted({item for feature in included for item in feature["backend"]})
    scores = readiness_scores(vertical, included, missing)
    business_readiness = round(sum(scores.values()) / len(scores))

    return {
        "business": {
            "name": profile.get("name", "Unnamed Business"),
            "location": profile.get("location", "Unknown"),
            "goal": profile.get("goal", "increase customer conversions"),
            **vertical_analysis,
            "target_audience": profile.get("target_audience", ""),
            "unique_selling_points": profile.get("unique_selling_points", ""),
            "business_hours": profile.get("business_hours", ""),
            "phone_number": profile.get("phone_number", ""),
            "social_media": {
                "facebook": profile.get("facebook_url", ""),
                "instagram": profile.get("instagram_url", ""),
                "existing_website": profile.get("existing_website", ""),
            },
            "branding": {
                "primary_color": profile.get("primary_color", "#3b82f6"),
                "secondary_color": profile.get("secondary_color", "#1e40af"),
                "accent_color": profile.get("accent_color", "#f59e0b"),
            },
        },
        "pages": (
            (PAGE_PRESETS.get(vertical) if vertical != "unknown" else None)
            or SHAPE_PAGE_PRESETS.get(shape)
            or PAGE_PRESETS["unknown"]
        ),
        "businessShape": shape,
        "includedFeatures": included,
        "skippedFeatures": skipped,
        "missingInfo": missing,
        "backend": backend,
        "trust": trust,
        "compliance": compliance,
        "qa": ["functional", "visual", "business", "conversion", "compliance", *qa],
        "scores": {
            **scores,
            "businessReadiness": business_readiness,
        },
    }


if __name__ == "__main__":
    import json

    sample_profile = {
        "name": "Bella Napoli",
        "location": "San Francisco",
        "goal": "increase online orders and table reservations",
        "contact_email": "hello@bellanapoli.example",
    }
    sample_input = """
    Bella Napoli is a family Italian restaurant in San Francisco.
    It serves pizza, pasta, desserts, and has a menu for pickup orders.
    Business hours are 11am to 10pm daily.
    """
    print(json.dumps(generate_build_spec(sample_profile, sample_input), indent=2))

