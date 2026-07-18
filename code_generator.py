"""
Template + AI-Assisted Code Generation System

Generates website code using a hybrid approach:
- Base templates for common verticals (restaurant, clinic, service)
- AI customization based on BuildSpec
- Next.js/React + Tailwind output
"""

from __future__ import annotations
import logging
import re
from typing import Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from agentic_planner import ModelJsonPlanner, PlannerGenerationError


COMMERCE_COPY_BUCKETS: dict[str, Any] = {
    "ticketed_event": {
        "keywords": ["theat", "cinema", "movie", "concert", "showtime", "screening", "box office", "ticket"],
        "items_heading": "Tickets & Concessions",
        "items_subtext": "Select your tickets and snacks below",
        "cta": "Buy Tickets",
        "overview_heading": "Tickets, Snacks & Showtimes",
        "overview_subtext": "A quick way to pick a showtime, grab tickets, and order snacks ahead.",
        "default_emoji": "🎟️",
        "emoji_map": [
            (["popcorn"], "🍿"), (["soda", "drink", "cola", "juice"], "🥤"),
            (["nacho"], "🧀"), (["candy", "chocolate", "sweet"], "🍬"),
            (["adult", "child", "senior", "matinee", "ticket"], "🎟️"),
        ],
        "description_fallback": "",
        "item_category_map": [
            (["adult", "child", "senior", "matinee", "ticket"], "Tickets"),
        ],
        "default_item_category": "Snacks",
    },
    "food": {
        "keywords": ["restaurant", "cafe", "bakery", "food", "kitchen", "diner", "pizzeria"],
        "items_heading": "Our Menu",
        "items_subtext": "Tap any item to add it to your order",
        "cta": "Order Now",
        "overview_heading": "Order, Reserve, Enjoy",
        "overview_subtext": "A smoother way to browse the menu, place an order, or plan a visit.",
        "default_emoji": "🍴",
        "emoji_map": [
            (["burger", "sandwich"], "🍔"), (["pizza"], "🍕"), (["fries", "chips"], "🍟"),
            (["steak", "meat", "grill"], "🥩"), (["breakfast", "egg", "waffle"], "🍳"),
            (["pasta", "noodle"], "🍝"), (["beverage", "drink", "juice", "coffee", "tea"], "🥤"),
            (["salad", "lunch"], "🥗"), (["soup", "curry", "stew"], "🍲"),
            (["chicken", "wings"], "🍗"), (["fish", "seafood", "shrimp"], "🐟"),
            (["cake", "dessert", "sweet", "ice cream"], "🍰"), (["dinner"], "🍽️"),
            (["wrap", "taco", "burrito"], "🌯"), (["donut", "pancake"], "🥞"),
        ],
        "description_fallback": "Freshly prepared {name}.",
        "item_category_map": [],
        "default_item_category": "Popular",
    },
    "catalog": {
        "keywords": ["library", "librarian", "book lending", "borrow", "lending", "loan program", "rental", "equipment rental", "reserve a copy", "hold a copy", "waitlist", "checkout a book"],
        "items_heading": "Browse Our Catalog",
        "items_subtext": "Reserve an item to pick up or borrow",
        "cta": "Reserve",
        "overview_heading": "Browse, Reserve, Pick Up",
        "overview_subtext": "A simple way to check availability and place a hold.",
        "default_emoji": "📚",
        "emoji_map": [
            (["book", "novel"], "📖"), (["dvd", "movie", "film"], "🎬"),
            (["tool", "equipment"], "🔧"), (["game"], "🎮"),
        ],
        "description_fallback": "",
        "item_category_map": [],
        "default_item_category": "Catalog",
    },
    "retail": {
        "keywords": [],
        "items_heading": "Shop",
        "items_subtext": "Browse our products and add them to your cart",
        "cta": "Shop Now",
        "overview_heading": "Shop With Ease",
        "overview_subtext": "A simple way to browse the catalog and check out.",
        "default_emoji": "🛍️",
        "emoji_map": [],
        "description_fallback": "",
        "item_category_map": [],
        "default_item_category": "Popular",
    },
}


def commerce_copy(shape: str, *text_fields: str) -> dict[str, str]:
    """Copy for the browsable items/cart section AND the services overview
    section, keyed on whatever business text is available (vertical, goal,
    USPs) rather than a binary food/non-food flag — otherwise a theatre, an
    e-commerce store, and a restaurant all get branded identically as "Our
    Menu" just because they share the storefront_commerce shape and the
    online_ordering feature. Checking goal/USP text (not just `vertical`)
    matters because the deterministic classifier only recognizes 8 verticals
    and returns "unknown" for a theatre — the goal text ("sell more tickets")
    is often the only surviving signal at this point in the pipeline.

    `shape` is checked first as a direct shortcut for business_shape values
    that map unambiguously onto one bucket (catalog_reserve -> catalog) —
    business_shape was classified from the FULL raw business description,
    which this function otherwise never sees (only vertical/subtype/goal/usp),
    so it can catch cases the keyword scan below would miss entirely."""
    if shape == "catalog_reserve":
        return COMMERCE_COPY_BUCKETS["catalog"]
    v = " ".join(str(f) for f in text_fields if f).lower()
    for bucket in (COMMERCE_COPY_BUCKETS["ticketed_event"], COMMERCE_COPY_BUCKETS["catalog"], COMMERCE_COPY_BUCKETS["food"]):
        # NOTE: keywords is a list of whole phrases (some multi-word, e.g.
        # "reserve a copy") checked as substrings directly — do NOT
        # `.split()` this into individual words, that previously produced a
        # garbage single-letter token ("a") that substring-matched almost
        # any text, making the wrong bucket win by default.
        if any(phrase in v for phrase in bucket["keywords"]):
            return bucket
    return COMMERCE_COPY_BUCKETS["retail"]


def parse_items_from_human_answers(human_answers: dict[str, Any], currency_sym: str) -> list[dict[str, Any]]:
    """Extract real item/price pairs directly from clarification-question
    answers (e.g. "Popcorn $5, Nachos $6") instead of ever fabricating
    business-specific placeholder content like fake menu items."""
    text = ", ".join(str(v) for v in (human_answers or {}).values())
    if not text.strip():
        return []
    segments = re.split(r",(?![^(]*\))", text)
    items: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        trimmed = segment.strip().lstrip("-→:•").strip()
        if not trimmed:
            continue
        match = re.search(r"[$₹]\s?(\d+(?:\.\d{1,2})?)", trimmed)
        if not match:
            continue
        price_value = float(match.group(1))
        name = trimmed[: match.start()].strip()
        # Drop a dangling unmatched "(" fragment, e.g. "Popcorn (small $5" -> "Popcorn"
        # (the "small"/"large" variant note isn't worth keeping without its price).
        if name.count("(") > name.count(")"):
            name = name[: name.rfind("(")]
        name = name.strip().rstrip(" (:.-").strip()
        if not name or len(name) > 60:
            continue
        items.append({
            "id": f"answer-item-{index}",
            "name": name,
            "category": "Popular",
            "description": "",
            "priceLabel": f"{currency_sym}{price_value:.2f}",
            "priceSortValue": price_value,
        })
    return items

logger = logging.getLogger(__name__)


class GeneratedCode(BaseModel):
    """Generated website code structure"""
    pages: dict[str, str] = Field(default_factory=dict, description="Generated page code by page name")
    components: dict[str, str] = Field(default_factory=dict, description="Generated component code")
    styles: str = Field(default="", description="Custom CSS/Tailwind configuration")
    config: dict[str, Any] = Field(default_factory=dict, description="Configuration files")
    html_preview: str = Field(default="", description="Static HTML preview with real business values")


class TemplateConfig(BaseModel):
    """Template configuration for code generation"""
    vertical: str
    pages: list[str]
    features: list[str]
    branding: dict[str, str]
    business_info: dict[str, Any]


WORKFLOW_FIELD_GUIDE: dict[str, dict[str, Any]] = {
    # ── Scheduling / Booking ──────────────────────────────────────────────
    "appointment_booking": {
        "default":      ["Your name", "Phone number", "Email", "Preferred date", "Preferred time", "Notes (optional)"],
        "clinic":       ["Patient name", "Contact number", "Email", "Appointment type (New Patient / Follow-up / Consultation)", "Preferred date", "Preferred time", "Brief reason for visit"],
        "salon":        ["Your name", "Phone number", "Service (Haircut / Colour / Treatment)", "Stylist preference (optional)", "Date", "Time"],
        "spa":          ["Your name", "Phone number", "Service type", "Date", "Time"],
        "gym":          ["Your name", "Phone", "Email", "Training goal", "Preferred session time"],
        "consultant":   ["Your name", "Company (optional)", "Phone", "Email", "Service of interest", "Brief description"],
        "tutor":        ["Student name", "Parent / Guardian name", "Contact number", "Subject", "Grade level", "Preferred schedule"],
        "legal":        ["Your name", "Phone", "Email", "Type of legal matter", "Brief description"],
        "real_estate":  ["Your name", "Phone", "Email", "Property of interest", "Viewing date preference"],
        "photography":  ["Your name", "Phone", "Email", "Event / shoot type", "Date", "Location"],
        "veterinary":   ["Pet owner name", "Phone", "Email", "Pet name & species", "Reason for visit", "Preferred date"],
        "dental":       ["Patient name", "Phone", "Email", "Appointment type", "Preferred date", "Any concerns"],
        "hotel":        ["Your name", "Email", "Phone", "Check-in date", "Check-out date", "Number of guests", "Room type preference"],
        "event":        ["Your name", "Phone", "Email", "Event type", "Preferred date", "Expected attendance"],
    },
    "table_reservation": {
        "default":      ["Your name", "Email address", "Date", "Time (e.g. 7:00 PM)", "Party size", "Special requests (optional)"],
        "restaurant":   ["Your name", "Email", "Phone", "Date", "Time", "Party size", "Dietary requirements (optional)"],
        "cafe":         ["Your name", "Phone", "Date", "Time", "Number of guests"],
    },
    # ── Lead / Enquiry capture ────────────────────────────────────────────
    "lead_capture": {
        "default":      ["Your name", "Phone number", "Email", "How can we help you?"],
        "clinic":       ["Your name", "Phone number", "Insurance provider (optional)", "What brings you in?"],
        "consultant":   ["Your name", "Company", "Phone", "Email", "Area of interest"],
        "tutor":        ["Parent name", "Phone", "Subject of interest", "Student grade level"],
        "legal":        ["Your name", "Phone", "Type of legal matter", "Brief description"],
        "real_estate":  ["Your name", "Phone", "Email", "Buying or selling?", "Budget range"],
        "gym":          ["Your name", "Phone", "Email", "Fitness goal", "Preferred membership type"],
        "hotel":        ["Your name", "Email", "Phone", "Dates of interest", "Number of guests", "Special requests"],
        "agency":       ["Your name", "Company", "Phone", "Email", "Project type", "Budget range", "Timeline"],
        "photography":  ["Your name", "Phone", "Email", "Event / shoot type", "Date", "Location"],
        "ecommerce":    ["Your name", "Email", "Phone", "Product interest", "How did you hear about us?"],
        "nonprofit":    ["Your name", "Email", "Phone", "How would you like to get involved?"],
    },
    "contact_form": {
        "default":      ["Your name", "Email", "Phone (optional)", "Message"],
    },
    # ── Health / Medical ──────────────────────────────────────────────────
    "patient_intake": {
        "default":      ["Full name", "Date of birth", "Contact number", "Email", "Emergency contact name & phone", "Current medications (if any)", "Reason for visit"],
        "veterinary":   ["Owner name", "Phone", "Email", "Pet name", "Species / Breed", "Age", "Vaccination history", "Reason for visit"],
        "dental":       ["Full name", "Date of birth", "Phone", "Email", "Last dental visit", "Current concerns", "Insurance provider (optional)"],
    },
    # ── Commerce ──────────────────────────────────────────────────────────
    "online_ordering": {
        "default":      ["Your name", "Phone number", "Delivery address"],
        "restaurant":   ["Your name", "Phone", "Delivery address", "Special instructions (optional)"],
        "bakery":       ["Your name", "Phone", "Order details", "Pickup or delivery?", "Preferred date"],
        "florist":      ["Your name", "Phone", "Email", "Order details", "Delivery address", "Delivery date", "Message for card (optional)"],
    },
    "quote_request": {
        "default":      ["Your name", "Phone", "Email", "Service required", "Project description", "Timeline", "Budget (optional)"],
        "contractor":   ["Your name", "Phone", "Email", "Type of work", "Property address", "Project description", "Start date preference"],
        "agency":       ["Your name", "Company", "Phone", "Email", "Project type", "Goals", "Budget range", "Deadline"],
        "photography":  ["Your name", "Phone", "Email", "Event type", "Date", "Location", "Hours required", "Additional services"],
    },
    # ── Education ─────────────────────────────────────────────────────────
    "course_enrollment": {
        "default":      ["Your name", "Phone", "Email", "Course of interest", "Experience level", "Preferred start date"],
        "tutor":        ["Student name", "Parent name", "Phone", "Email", "Subject", "Grade level", "Learning goals", "Preferred schedule"],
        "gym":          ["Your name", "Phone", "Email", "Class type", "Experience level", "Preferred schedule"],
    },
    # ── Real-estate / Property ────────────────────────────────────────────
    "property_enquiry": {
        "default":      ["Your name", "Phone", "Email", "Property of interest", "Buying / Renting / Selling", "Budget range", "Timeline"],
    },
    # ── Hospitality ───────────────────────────────────────────────────────
    "room_booking": {
        "default":      ["Your name", "Email", "Phone", "Check-in date", "Check-out date", "Number of guests", "Room type", "Special requests"],
    },
    # ── Events ────────────────────────────────────────────────────────────
    "event_registration": {
        "default":      ["Your name", "Email", "Phone", "Company / Organisation (optional)", "Event name", "Number of attendees", "Dietary / accessibility requirements (optional)"],
    },
    # ── Feedback / Misc ───────────────────────────────────────────────────
    "feedback_form": {
        "default":      ["Your name (optional)", "Email (optional)", "How was your experience? (1–5)", "What did you love?", "What could be improved?"],
    },
    "newsletter_signup": {
        "default":      ["Your name", "Email address"],
    },
    "job_application": {
        "default":      ["Full name", "Phone", "Email", "Position applying for", "Years of experience", "LinkedIn / Portfolio URL (optional)", "Why do you want to join us?"],
    },
}


# Default workflows per vertical — used when the agent returns no workflows.
VERTICAL_DEFAULT_WORKFLOWS: dict[str, list[str]] = {
    "restaurant":   ["table_reservation", "online_ordering", "lead_capture"],
    "cafe":         ["table_reservation", "lead_capture"],
    "bakery":       ["online_ordering", "lead_capture"],
    "clinic":       ["appointment_booking", "patient_intake", "lead_capture"],
    "dental":       ["appointment_booking", "patient_intake", "lead_capture"],
    "veterinary":   ["appointment_booking", "patient_intake", "lead_capture"],
    "salon":        ["appointment_booking", "lead_capture"],
    "spa":          ["appointment_booking", "lead_capture"],
    "gym":          ["appointment_booking", "lead_capture", "course_enrollment"],
    "tutor":        ["course_enrollment", "lead_capture"],
    "legal":        ["appointment_booking", "lead_capture"],
    "real_estate":  ["property_enquiry", "appointment_booking", "lead_capture"],
    "consultant":   ["appointment_booking", "quote_request", "lead_capture"],
    "agency":       ["quote_request", "lead_capture"],
    "contractor":   ["quote_request", "lead_capture"],
    "photography":  ["appointment_booking", "quote_request", "lead_capture"],
    "hotel":        ["room_booking", "lead_capture"],
    "event":        ["event_registration", "lead_capture"],
    "ecommerce":    ["online_ordering", "lead_capture"],
    "nonprofit":    ["lead_capture", "newsletter_signup"],
    "florist":      ["online_ordering", "lead_capture"],
}


def _workflow_fields(workflow_key: str, vertical: str) -> list[str]:
    guide = WORKFLOW_FIELD_GUIDE.get(workflow_key, {})
    return guide.get(vertical, guide.get("default", ["Name", "Phone", "Email", "Message"]))


SHAPE_DEFAULT_WORKFLOWS: dict[str, list[str]] = {
    "storefront_commerce": ["online_ordering", "lead_capture"],
    "scheduled_booking": ["appointment_booking", "lead_capture"],
    "inquiry_lead": ["lead_capture", "quote_request"],
    "portfolio_showcase": ["portfolio_showcase", "lead_capture"],
    "catalog_reserve": ["catalog_reservation", "lead_capture"],
}


def _default_workflows_for_vertical(vertical: str, shape: str = "") -> list[str]:
    """Return sensible default workflow keys when the agent provides none."""
    if vertical in VERTICAL_DEFAULT_WORKFLOWS:
        return VERTICAL_DEFAULT_WORKFLOWS[vertical]
    return SHAPE_DEFAULT_WORKFLOWS.get(shape, ["lead_capture", "contact_form"])



class CodeGenerator:
    """Template + AI-assisted code generator"""

    def __init__(self, planner: Optional[ModelJsonPlanner] = None):
        self.planner = planner

    def generate_html_preview(self, build_spec: dict[str, Any]) -> str:
        """Generate a functional HTML preview with working forms and real business values"""
        business = build_spec.get("business", {})
        branding = business.get("branding") or {}
        name = business.get("name", "Our Business")
        location = business.get("location", "")
        vertical = business.get("vertical", "restaurant")
        vertical_label = str(vertical or "").replace("_", " ").strip()
        if not vertical_label or vertical_label.lower() == "unknown":
            vertical_label = "business"
        location_phrase = f" in {location}" if location else ""
        usp = (business.get("unique_selling_points")
               or f"Your premier {vertical_label}{location_phrase}")
        hours = business.get("business_hours") or "Call us for our hours"
        phone = business.get("phone_number") or "Contact us online"
        email = business.get("contact_email") or business.get("email") or ""
        human_answers = business.get("human_answers") or {}
        primary = (branding.get("primary_color")
                   or business.get("primary_color") or "#dc2626")
        accent = (branding.get("accent_color")
                  or business.get("accent_color") or "#f59e0b")
        font_family = business.get("font_family") or "Inter"

        # Visual mood, keyed off business_shape, so the deterministic fallback
        # doesn't render the same "bold gradient" look for every business type
        # either — mirrors the mood system used by generate_html_with_llm.
        mood = self.SHAPE_TO_MOOD.get(build_spec.get("businessShape", ""), "bold")
        mood_vars = self.PREVIEW_MOOD_VARS.get(mood, self.PREVIEW_MOOD_VARS["bold"])
        radius = mood_vars["radius"]
        btn_radius = mood_vars["btn_radius"]
        hero_bg = mood_vars["hero_bg"].format(primary=primary, accent=accent)
        hero_align = mood_vars["hero_align"]
        heading_font = mood_vars["heading_font"] or f"'{font_family}'"

        features = build_spec.get("includedFeatures", [])
        menu_items = build_spec.get("menuItems", [])
        has_ordering = any(f.get("key") == "online_ordering" for f in features)
        is_food_business = has_ordering or bool(menu_items)
        has_reservation = any(f.get("key") == "table_reservation" for f in features)
        has_booking = any(f.get("key") == "appointment_booking" for f in features)
        has_booking = has_booking or str(vertical).lower() in {"clinic", "dental"}

        commerce = commerce_copy(build_spec.get("businessShape", ""), vertical, business.get("subtype", ""), business.get("goal", ""), usp)
        cta_primary = commerce["cta"] if has_ordering else ("Book Appointment" if has_booking else "Get in Touch")
        cta_secondary = "Reserve a Table" if has_reservation else ""

        pages = build_spec.get("pages", ["Home", "Menu", "Contact"])
        # Map page names to section anchors within this document
        _anchor_map = {
            "home": "hero", "menu": "menu", "order online": "menu",
            "order": "menu", "reservations": "reserve", "reservation": "reserve",
            "book": "reserve", "appointments": "reserve", "appointment": "reserve",
            "booking": "reserve", "services": "services", "service": "services",
            "providers": "providers", "provider": "providers", "team": "providers",
            "doctors": "providers", "dentists": "providers",
            "about": "services",
            "contact": "contact", "find us": "contact", "gallery": "contact",
            "locations": "contact", "offers": "menu", "specials": "menu",
        }
        def _nav_href(page_label: str) -> str:
            key = page_label.lower().strip()
            return "#" + _anchor_map.get(key, key.replace(" ", "-"))
        nav_links = "".join(
            f'<a href="{_nav_href(p)}" onclick="event.preventDefault();var t=document.getElementById(this.getAttribute(\'href\').slice(1));if(t)t.scrollIntoView({{behavior:\'smooth\'}})">{p}</a>'
            for p in pages[:6]
        )

        def _feature_copy(feature: dict[str, Any]) -> tuple[str, str]:
            key = str(feature.get("key", "")).lower()
            label = feature.get("label") or key.replace("_", " ").title()
            if key == "online_ordering":
                return "Order Online", "Choose your favourites, add them to the cart, and send the order in minutes."
            if key == "table_reservation":
                return "Table Reservations", "Pick a date, time, and party size so the team can prepare your visit."
            if key == "appointment_booking":
                return "Easy Booking", "Request a convenient appointment time without waiting on a phone call."
            if key == "lead_capture":
                return "Quick Enquiries", "Ask a question, request help, or share details for a fast follow-up."
            if key == "service_catalog":
                return "Services At A Glance", "Browse the main services and find the right next step quickly."
            if key == "menu_showcase":
                return "Menu Highlights", "Browse popular items, prices, and offers before ordering."
            return label, f"Everything visitors need to take the next step with {name}."

        feat_cards = "".join(
            f'<div class="fc"><h4>{title}</h4><p>{body}</p></div>'
            for title, body in (_feature_copy(f) for f in features[:4])
        )
        if not feat_cards:
            feat_cards = (
                f'<div class="fc"><h4>Fresh Menu</h4><p>Explore popular choices and seasonal favourites from {name}.</p></div>'
                f'<div class="fc"><h4>Fast Contact</h4><p>Reach the team quickly for orders, bookings, or questions.</p></div>'
            )

        order_section = ""  # Ordering handled by cart drawer checkout flow

        reserve_section = ""
        if has_reservation or has_booking:
            label = "Reserve a Table" if has_reservation else "Book an Appointment"
            response_timing = str(human_answers.get("simulation_response_timing") or "").strip()
            privacy_note = str(human_answers.get("simulation_privacy_reassurance") or "").strip()
            reassurance = ""
            if response_timing or privacy_note:
                reassurance = (
                    '<div class="reassurance-row">'
                    f'{f"<span>{response_timing}</span>" if response_timing else ""}'
                    f'{f"<span>{privacy_note}</span>" if privacy_note else ""}'
                    '</div>'
                )
            reserve_section = (
                f'<section id="reserve" class="sec"><div class="wrap">'
                f'<h2>{label}</h2><p class="sub">Secure your spot at {name}</p>'
                f'{reassurance}'
                f'<form class="frm" id="reserveForm">'
                f'<input type="text" name="cname" placeholder="Your name" required>'
                f'<input type="email" name="email" placeholder="Email address" required>'
                f'<input type="date" name="date" required>'
                f'<input type="number" name="guests" placeholder="Number of guests" min="1" max="20" required>'
                f'<button type="submit">{label}</button></form>'
                f'</div></section>'
            )

        provider_profiles = ""
        provider_answer = str(human_answers.get("simulation_provider_credentials") or "").strip()
        if provider_answer and str(vertical).lower() in {"clinic", "dental"}:
            profile_cards = ""
            for idx, item in enumerate([p.strip() for p in provider_answer.replace("\n", ";").split(";") if p.strip()][:3], start=1):
                parts = [p.strip() for p in item.replace(" - ", ", ").split(",") if p.strip()]
                profile_name = parts[0] if parts else f"Provider {idx}"
                profile_detail = " · ".join(parts[1:]) if len(parts) > 1 else "Clinical care team"
                profile_cards += (
                    f'<div class="fc provider-card"><div class="avatar">{profile_name[:1]}</div>'
                    f'<h4>{profile_name}</h4><p>{profile_detail}</p></div>'
                )
            provider_profiles = (
                f'<section id="providers" class="sec alt"><div class="wrap">'
                f'<h2>Meet Your Care Team</h2>'
                f'<p class="sub">Provider details are shown before booking so patients can choose with confidence.</p>'
                f'<div class="fgrid">{profile_cards}</div></div></section>'
            )

        email_row = f'<div class="ci"><h4>Email</h4><p>{email}</p></div>' if email else ""
        _scroll_js = "event.preventDefault();var t=document.getElementById(this.getAttribute('href').slice(1));if(t)t.scrollIntoView({behavior:'smooth'})"
        reserve_btn = f'<a href="#reserve" class="btn-s" onclick="{_scroll_js}">{cta_secondary}</a>' if cta_secondary else ""
        contact_cls = "sec" if (has_ordering or has_reservation or has_booking) else "sec alt"

        # --- Currency ---
        loc_low = location.lower()
        india_cities = ["india","bangalore","bengaluru","mumbai","delhi","chennai","hyderabad","pune","kolkata"]
        currency_sym = "\u20b9" if any(c in loc_low for c in india_cities) else "$"
        price_default: float = 199.0 if currency_sym == "\u20b9" else 9.99

        # --- Menu items from BuildSpec (loaded earlier, alongside is_food_business) ---
        if is_food_business and not menu_items:
            menu_items = parse_items_from_human_answers(human_answers, currency_sym)
            if not menu_items:
                # No uploaded menu photo AND no usable clarification-answer
                # data \u2014 don't guess with food-specific placeholder content
                # (a restaurant menu is wrong for a theatre, salon, retailer,
                # etc.); show an honest "not yet provided" placeholder instead.
                menu_items = [
                    {
                        "id": "fallback-generic",
                        "name": "Item pricing not yet provided",
                        "category": "Popular",
                        "description": "Add real items and prices to replace this placeholder.",
                        "priceLabel": "--",
                        "priceSortValue": 0,
                    },
                ]
        has_ordering = has_ordering or bool(menu_items and is_food_business)
        cta_primary = commerce["cta"] if has_ordering else cta_primary
        contact_cls = "sec" if (has_ordering or has_reservation or has_booking) else "sec alt"

        def _emoji(n: str) -> str:
            nl = n.lower()
            for kws, em in commerce.get("emoji_map", []):
                if any(k in nl for k in kws):
                    return em
            return commerce.get("default_emoji", "🍴")

        def _item_category(item: dict) -> str:
            raw_cat = item.get("category")
            # Trust a real extracted category (e.g. "Veg"/"Non-Veg" from a
            # menu photo) — only re-derive it for the generic placeholder
            # categories our own answer-text parser assigns ("Menu"/"Popular"),
            # since that parser can't tell a ticket tier from a snack on its own.
            if raw_cat and raw_cat not in ("Menu", "Popular"):
                return raw_cat
            nl = str(item.get("name", "")).lower()
            for kws, cat_name in commerce.get("item_category_map", []):
                if any(k in nl for k in kws):
                    return cat_name
            return commerce.get("default_item_category", raw_cat or "Popular")

        def _card(item: dict) -> str:
            iid = str(item.get("id", "")).replace("'", "").replace('"', "")
            nm  = item.get("name", "Item")
            cat = _item_category(item)
            desc_fallback = commerce.get("description_fallback", "").format(name=nm.lower()) if commerce.get("description_fallback") else ""
            dsc = (item.get("description") or desc_fallback)
            dsc = dsc[:65] + ("..." if len(dsc) > 65 else "")
            pl  = item.get("priceLabel") or f"{currency_sym}{price_default:.2f}"
            pn  = float(item.get("priceSortValue") or price_default)
            em  = _emoji(nm)
            snm = nm.replace("'", "\\'").replace('"', '\\"')
            spl = pl.replace("'", "\\'")
            return (
                f'<div class="mi-card" data-id="{iid}" data-cat="{cat}">'
                f'<div class="mi-info"><span class="vdot"></span>'
                f'<div class="mi-nm">{nm}</div>'
                f'<div class="mi-ds">{dsc}</div>'
                f'<div class="mi-pr">{pl}</div></div>'
                f'<div class="mi-rt"><div class="mi-em">{em}</div>'
                f'<button class="add-btn" id="ab-{iid}" onclick="addItem(\'{iid}\',\'{snm}\',\'{spl}\',{pn})">ADD</button>'
                f'<div class="qty-ctrl" id="qc-{iid}">'
                f'<button onclick="rmItem(\'{iid}\')">&#8722;</button>'
                f'<span id="qn-{iid}">0</span>'
                f'<button onclick="addItem(\'{iid}\',\'{snm}\',\'{spl}\',{pn})">&#43;</button>'
                f'</div></div></div>'
            )

        cats = list(dict.fromkeys(_item_category(i) for i in menu_items)) if menu_items else []
        cat_tabs_html = (
            '<button class="ctab active" onclick="filterCat(\'all\',this)">All</button>'
            + "".join(f'<button class="ctab" onclick="filterCat(\'{c}\',this)">{c}</button>' for c in cats)
        )
        items_html = "".join(_card(i) for i in menu_items)

        menu_section = ""
        if menu_items:
            menu_section = (
                f'<section id="menu" class="sec alt"><div class="wrap">'
                f'<h2>{commerce["items_heading"]}</h2><p class="sub">{commerce["items_subtext"]}</p>'
                f'<div class="cat-row">{cat_tabs_html}</div>'
                f'<div class="mi-list" id="miList">{items_html}</div>'
                f'</div></section>'
            )

        # --- Cart HTML (overlay + drawer + bottom bar) ---
        hero_cta_href = "menu" if menu_items else ("order" if has_ordering else ("reserve" if (has_reservation or has_booking) else "contact"))

        cart_html = (
            '<div id="cOverlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:200" onclick="closeCart()"></div>'
            '<div class="cart-drawer" id="cDrawer">'
              '<div id="cView">'
                '<div class="c-head"><span style="font-weight:700;font-size:1.05rem">Your Order</span>'
                '<button onclick="closeCart()" style="background:none;border:none;font-size:1.2rem;cursor:pointer">&#10005;</button></div>'
                '<div id="cItems"><p class="empty-cart">Add items from the menu above</p></div>'
                '<div id="cBill"></div>'
                '<button class="co-btn" id="cProceed" onclick="showCo()" style="display:none">Proceed to Checkout &#8594;</button>'
              '</div>'
              '<div id="coView" style="display:none">'
                '<div class="c-head"><button onclick="backCart()" style="background:none;border:none;font-size:1rem;cursor:pointer">&#8592; Back</button>'
                '<span style="font-weight:700">Checkout</span><span></span></div>'
                '<form id="coForm" style="display:flex;flex-direction:column;gap:.65rem;margin-top:.75rem">'
                  '<input name="cname" placeholder="Your name" required class="co-inp">'
                  '<input name="phone" type="tel" placeholder="Phone number" required class="co-inp">'
                  '<input name="address" placeholder="Delivery address" required class="co-inp">'
                  '<div style="display:flex;gap:.5rem;margin:.25rem 0">'
                    '<button type="button" class="py-btn active" onclick="selPay(this)">Cash on Delivery</button>'
                    '<button type="button" class="py-btn" onclick="selPay(this)">Pay Online</button>'
                  '</div>'
                  '<button type="submit" class="co-btn">Place Order</button>'
                '</form>'
              '</div>'
            '</div>'
            f'<div id="cBar" style="display:none" class="c-bar" onclick="openCart()">'
              f'<div>&#128722; <span id="cCnt">0</span> item(s)</div>'
              f'<div>View Cart &middot; <strong id="cTot">{currency_sym}0.00</strong> &#8594;</div>'
            '</div>'
        )

        # --- CSS (core + menu + cart) ---
        css = (
            "*{box-sizing:border-box;margin:0;padding:0}"
            f"body{{font-family:'{font_family}',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#1f2937;padding-bottom:70px;background:#f8faf9}}"
            f"nav{{background:{primary};color:#fff;padding:.8rem 2rem;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:99}}"
            "nav strong{font-size:1.05rem;font-weight:700}"
            "nav a{color:#fff;text-decoration:none;margin-left:1rem;font-size:.88rem;opacity:.9}"
            f".hero{{background:{hero_bg};color:#fff;padding:5.5rem 2rem 4.5rem;text-align:{hero_align};position:relative;overflow:hidden}}"
            + (".hero::after{content:'';position:absolute;right:-120px;bottom:-160px;width:420px;height:420px;border-radius:50%;background:rgba(255,255,255,.11)}" if mood == "bold" else "")
            + f".hero h1{{font-family:{heading_font},sans-serif;font-size:clamp(2.4rem,6vw,4.4rem);line-height:1.05;font-weight:800;margin:0 auto .9rem;max-width:860px;letter-spacing:0}}"
            ".hero p{font-size:1.13rem;line-height:1.65;max-width:720px;margin:.5rem auto 2rem;opacity:.93}"
            f".ctas{{display:flex;gap:.75rem;justify-content:{'center' if hero_align == 'center' else 'flex-start'};flex-wrap:wrap;max-width:860px;margin:0 auto}}"
            f".btn-p{{background:{accent};color:#fff;border:none;padding:.8rem 1.75rem;border-radius:{btn_radius};font-size:1rem;font-weight:700;cursor:pointer;text-decoration:none}}"
            f".btn-s{{background:transparent;color:#fff;border:2px solid rgba(255,255,255,.8);padding:.8rem 1.75rem;border-radius:{btn_radius};font-size:1rem;font-weight:600;cursor:pointer;text-decoration:none}}"
            ".sec{padding:3.5rem 2rem}.sec.alt{background:#f9fafb}"
            ".wrap{max-width:860px;margin:0 auto}"
            f"h2{{font-family:{heading_font},sans-serif;font-size:1.75rem;font-weight:700;color:{primary};margin-bottom:.4rem}}"
            ".sub{color:#6b7280;margin-bottom:1.5rem;font-size:.97rem}"
            ".fgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:1rem}"
            f".fc{{background:linear-gradient(180deg,#fff,#fbfdfb);border:1px solid #e5e7eb;border-radius:{radius};padding:1.35rem;box-shadow:0 14px 32px rgba(15,23,42,.07)}}"
            f".fc h4{{color:{primary};font-weight:700;margin-bottom:.4rem;font-size:.95rem}}"
            ".fc p{font-size:.85rem;color:#6b7280}"
            ".frm{display:flex;flex-direction:column;gap:.7rem;max-width:460px}"
            ".reassurance-row{display:flex;flex-wrap:wrap;gap:.5rem;margin:0 0 1rem}.reassurance-row span{background:#fff;border:1px solid #d1d5db;border-radius:999px;padding:.45rem .75rem;font-size:.82rem;font-weight:700;color:#4b5563}"
            f".avatar{{width:42px;height:42px;border-radius:999px;background:{primary};color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800;margin-bottom:.75rem}}"
            "input,textarea{padding:.75rem 1rem;border:1px solid #d1d5db;border-radius:.5rem;font-size:.95rem;font-family:inherit}"
            f".frm button{{padding:.85rem;background:{primary};color:#fff;border:none;border-radius:.5rem;font-size:1rem;font-weight:700;cursor:pointer}}"
            ".ok{color:#16a34a;font-weight:600;padding:1rem 0;font-size:1.05rem}"
            ".cgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:1.25rem;margin-top:1.5rem}"
            f".ci{{background:#f9fafb;border-radius:.75rem;padding:1.25rem;border:1px solid #e5e7eb}}"
            f".ci h4{{font-weight:700;color:{primary};margin-bottom:.35rem;font-size:.8rem;text-transform:uppercase;letter-spacing:.05em}}"
            ".ci p{font-size:.9rem;color:#374151}"
            f"footer{{background:{primary};color:#fff;text-align:center;padding:1.25rem;font-size:.85rem}}"
            ".cat-row{display:flex;gap:.5rem;overflow-x:auto;padding-bottom:.75rem;margin-bottom:1.25rem}"
            f".ctab{{background:#fff;border:1.5px solid #e5e7eb;border-radius:20px;padding:.35rem 1rem;font-size:.85rem;cursor:pointer;white-space:nowrap;font-family:inherit}}"
            f".ctab.active{{background:{primary};color:#fff;border-color:{primary}}}"
            ".mi-list{display:flex;flex-direction:column;gap:.75rem}"
            ".mi-card{background:linear-gradient(180deg,#fff,#fbfdfb);border:1px solid #edf2ef;border-radius:1.15rem;padding:1.05rem 1.25rem;display:flex;gap:1rem;box-shadow:0 12px 30px rgba(15,23,42,.08);align-items:center;transition:transform .2s,box-shadow .2s}"
            ".mi-card:hover{transform:translateY(-2px);box-shadow:0 18px 42px rgba(15,23,42,.13)}"
            ".mi-info{flex:1}"
            ".vdot{display:inline-block;width:12px;height:12px;border:2px solid #16a34a;border-radius:2px;position:relative;margin-bottom:.3rem}"
            ".vdot::after{content:'';position:absolute;top:2px;left:2px;width:6px;height:6px;background:#16a34a;border-radius:50%}"
            ".mi-nm{font-weight:700;font-size:.95rem;color:#111827;margin:.15rem 0}"
            ".mi-ds{font-size:.8rem;color:#6b7280;margin-bottom:.4rem;line-height:1.4}"
            ".mi-pr{font-weight:700;color:#111827;font-size:.95rem}"
            ".mi-rt{display:flex;flex-direction:column;align-items:center;gap:.4rem;min-width:80px}"
            ".mi-em{font-size:2.2rem;line-height:1}"
            f".add-btn{{background:#fff;border:1.5px solid {primary};color:{primary};border-radius:.4rem;padding:.3rem .9rem;font-weight:700;font-size:.85rem;cursor:pointer;font-family:inherit}}"
            f".qty-ctrl{{display:none;align-items:center;gap:.3rem;background:{primary};border-radius:.4rem;padding:.25rem .4rem}}"
            ".qty-ctrl button{background:none;border:none;color:#fff;font-size:1rem;font-weight:700;cursor:pointer;padding:0 .15rem;line-height:1}"
            ".qty-ctrl span{color:#fff;font-weight:700;font-size:.9rem;min-width:18px;text-align:center}"
            f".c-bar{{position:fixed;bottom:0;left:0;right:0;background:{primary};color:#fff;display:flex;align-items:center;justify-content:space-between;padding:.9rem 1.5rem;z-index:150;cursor:pointer;box-shadow:0 -4px 12px rgba(0,0,0,.15);font-size:.95rem;font-weight:600}}"
            ".cart-drawer{position:fixed;bottom:0;left:0;right:0;background:#fff;border-radius:1.25rem 1.25rem 0 0;padding:1.25rem 1.5rem;max-height:85vh;overflow-y:auto;z-index:250;transform:translateY(100%);transition:transform .3s ease}"
            ".cart-drawer.open{transform:translateY(0)}"
            ".c-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:.75rem;padding-bottom:.75rem;border-bottom:1px solid #f3f4f6}"
            ".cart-row{display:flex;align-items:center;gap:.75rem;padding:.65rem 0;border-bottom:1px solid #f9fafb}"
            ".cr-nm{flex:1;font-size:.9rem;font-weight:500}"
            f".cr-qty{{display:flex;align-items:center;gap:.35rem;background:{primary};border-radius:.35rem;padding:.2rem .45rem}}"
            ".cr-qty button{background:none;border:none;color:#fff;font-weight:700;cursor:pointer;font-size:.9rem;padding:0 .1rem}"
            ".cr-qty span{color:#fff;font-weight:700;font-size:.85rem;min-width:16px;text-align:center}"
            ".cr-pr{font-weight:600;font-size:.9rem;min-width:55px;text-align:right}"
            ".bill-det{margin:.75rem 0;background:#f9fafb;border-radius:.75rem;padding:.85rem}"
            ".bill-row{display:flex;justify-content:space-between;font-size:.9rem;padding:.2rem 0}"
            ".total-row{font-weight:700;padding-top:.5rem;margin-top:.5rem;border-top:1px solid #e5e7eb}"
            f".co-btn{{width:100%;background:{primary};color:#fff;border:none;border-radius:.5rem;padding:.9rem;font-size:1rem;font-weight:700;cursor:pointer;margin-top:.75rem;font-family:inherit}}"
            ".empty-cart{color:#9ca3af;text-align:center;padding:1.5rem;font-size:.9rem}"
            ".co-inp{padding:.75rem 1rem;border:1px solid #d1d5db;border-radius:.5rem;font-size:.9rem;font-family:inherit;width:100%}"
            f".py-btn{{flex:1;padding:.55rem;border:1.5px solid #d1d5db;border-radius:.5rem;background:#fff;font-size:.85rem;cursor:pointer;font-family:inherit}}"
            f".py-btn.active{{border-color:{primary};color:{primary};font-weight:700}}"
            ".ok-icon{width:56px;height:56px;background:#dcfce7;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.5rem;color:#16a34a;margin:0 auto .75rem}"
        )

        # --- Consolidated JS (cart + form handlers + postMessage) ---
        _js_tpl = (
            "<script>"
            "var cart={};"
            "var CURR='__CUR__';"
            "function addItem(id,nm,pl,pn){if(!cart[id])cart[id]={id:id,nm:nm,pl:pl,pn:pn,qty:0};cart[id].qty++;updateUI();}"
            "function rmItem(id){if(cart[id]){cart[id].qty--;if(cart[id].qty<=0)delete cart[id];}updateUI();}"
            "function updateUI(){"
              "var es=Object.values(cart);"
              "var tq=es.reduce(function(s,i){return s+i.qty;},0);"
              "var tp=es.reduce(function(s,i){return s+i.pn*i.qty;},0);"
              "var bar=document.getElementById('cBar');"
              "bar.style.display=tq>0?'flex':'none';"
              "document.getElementById('cCnt').textContent=tq;"
              "document.getElementById('cTot').textContent=CURR+tp.toFixed(2);"
              "document.querySelectorAll('.mi-card').forEach(function(c){"
                "var id=c.dataset.id,qty=cart[id]?cart[id].qty:0;"
                "var ab=document.getElementById('ab-'+id),qc=document.getElementById('qc-'+id);"
                "if(ab&&qc){if(qty>0){ab.style.display='none';qc.style.display='flex';document.getElementById('qn-'+id).textContent=qty;}else{ab.style.display='block';qc.style.display='none';}}"
              "});"
              "window.parent.postMessage({type:'cart_update',count:tq,total:tp.toFixed(2)},'*');}"
            "function openCart(){document.getElementById('cDrawer').classList.add('open');document.getElementById('cOverlay').style.display='block';renderCart();}"
            "function closeCart(){document.getElementById('cDrawer').classList.remove('open');document.getElementById('cOverlay').style.display='none';}"
            "function backCart(){document.getElementById('coView').style.display='none';document.getElementById('cView').style.display='block';}"
            "function showCo(){document.getElementById('cView').style.display='none';document.getElementById('coView').style.display='block';}"
            "function selPay(btn){document.querySelectorAll('.py-btn').forEach(function(b){b.classList.remove('active')});btn.classList.add('active');}"
            "function filterCat(cat,btn){"
              "document.querySelectorAll('.ctab').forEach(function(b){b.classList.remove('active')});btn.classList.add('active');"
              "document.querySelectorAll('.mi-card').forEach(function(c){c.style.display=(cat==='all'||c.dataset.cat===cat)?'flex':'none';});}"
            "function renderCart(){"
              "var es=Object.values(cart);"
              "var sub=es.reduce(function(s,i){return s+i.pn*i.qty;},0);"
              "var del=CURR==='$'?2.99:49;"
              "var tot=sub+del;"
              "if(!es.length){document.getElementById('cItems').innerHTML='<p class=empty-cart>Your cart is empty</p>';document.getElementById('cBill').innerHTML='';document.getElementById('cProceed').style.display='none';return;}"
              "document.getElementById('cItems').innerHTML=es.map(function(i){"
                "return '<div class=cart-row><div class=cr-nm>'+i.nm+'</div><div class=cr-qty><button onclick=\"rmItem(\\''+i.id+'\\');renderCart()\">&#8722;</button><span>'+i.qty+'</span><button onclick=\"addItem(\\''+i.id+'\\',\\''+i.nm+'\\',\\''+i.pl+'\\','+i.pn+');renderCart()\">&#43;</button></div><div class=cr-pr>'+CURR+(i.pn*i.qty).toFixed(2)+'</div></div>';"
              "}).join('');"
              "document.getElementById('cBill').innerHTML='<div class=bill-det><div class=bill-row><span>Subtotal</span><span>'+CURR+sub.toFixed(2)+'</span></div><div class=bill-row><span>Delivery</span><span>'+CURR+del.toFixed(2)+'</span></div><div class=\"bill-row total-row\"><span><strong>Total</strong></span><span><strong>'+CURR+tot.toFixed(2)+'</strong></span></div></div>';"
              "document.getElementById('cProceed').style.display='block';}"
            "document.addEventListener('DOMContentLoaded',function(){"
              "var cf=document.getElementById('coForm');"
              "if(cf){cf.addEventListener('submit',function(e){"
                "e.preventDefault();var f=e.target;"
                "var es=Object.values(cart);"
                "var tot=es.reduce(function(s,i){return s+i.pn*i.qty;},0)+(CURR==='$'?2.99:49);"
                "window.parent.postMessage({type:'order',customer:f.cname.value,phone:f.phone.value,order:es.map(function(i){return i.nm+' x'+i.qty;}).join(', '),contact:f.phone.value,total:CURR+tot.toFixed(2)},'*');"
                "document.getElementById('coView').innerHTML='<div style=\"text-align:center;padding:2rem 1rem\"><div class=ok-icon>&#10003;</div><h3 style=\"margin-bottom:.5rem\">Order Placed!</h3><p style=\"color:#6b7280;margin-bottom:1.5rem\">Estimated delivery: 30-45 min.</p><button onclick=\"closeCart();Object.keys(cart).forEach(function(k){delete cart[k]});updateUI()\" class=co-btn>Done</button></div>';});};"
              "var of=document.getElementById('orderForm');"
              "if(of){of.addEventListener('submit',function(e){e.preventDefault();var f=e.target;window.parent.postMessage({type:'order',customer:f.cname.value,phone:f.phone.value,order:f.order.value,contact:f.phone.value},'*');f.innerHTML='<p class=ok>&#10003; Order received!</p>';});}"
              "var rf=document.getElementById('reserveForm');"
              "if(rf){rf.addEventListener('submit',function(e){e.preventDefault();var f=e.target;window.parent.postMessage({type:'reservation',customer:f.cname.value,email:f.email.value,date:f.date.value,guests:f.guests.value},'*');f.innerHTML='<p class=ok>&#10003; Confirmed! See you soon.</p>';});}"
            "});"
            "</script>"
        )
        cart_js = _js_tpl.replace("__CUR__", currency_sym)

        return (
            f'<!DOCTYPE html><html lang="en"><head>'
            f'<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">'
            f'<title>{name}</title><style>{css}</style></head><body>'
            f'{cart_js}'
            f'<nav><strong>{name}</strong><div>{nav_links}</div></nav>'
            f'<section class="hero"><h1>{name}</h1><p>{usp}</p>'
            f'<div class="ctas"><a href="#{hero_cta_href}" class="btn-p" onclick="{_scroll_js}">{cta_primary}</a>{reserve_btn}</div>'
            f'</section>'
            f'<section id="services" class="sec"><div class="wrap">'
            f'<h2>{commerce["overview_heading"] if has_ordering else "How We Help"}</h2>'
            f'<p class="sub">{commerce["overview_subtext"] if has_ordering else f"Simple ways to connect with {name}."}</p>'
            f'<div class="fgrid">{feat_cards}</div></div></section>'
            f'{menu_section}'
            f'{order_section}'
            f'{provider_profiles}'
            f'{reserve_section}'
            f'<section id="contact" class="{contact_cls}">'
            f'<div class="wrap"><h2>Find Us</h2><p class="sub">Get in touch with {name}</p>'
            f'<div class="cgrid"><div class="ci"><h4>Location</h4><p>{location}</p></div>'
            f'<div class="ci"><h4>Hours</h4><p>{hours}</p></div>'
            f'<div class="ci"><h4>Phone</h4><p>{phone}</p></div>'
            f'{email_row}</div></div></section>'
            f'<footer>&copy; {name} &middot; {location}</footer>'
            f'{cart_html}'
            f'</body></html>'
        )
    
    SHAPE_TO_MOOD: dict[str, str] = {
        "storefront_commerce": "bold",
        "scheduled_booking": "trust",
        "inquiry_lead": "structured",
        "portfolio_showcase": "editorial",
        "catalog_reserve": "trust",
    }

    # Mood knobs for the deterministic generate_html_preview fallback, which
    # has cart/menu JS-bound classes that must keep their exact names/structure
    # — so only the hero/radius/heading personality varies here.
    PREVIEW_MOOD_VARS: dict[str, dict[str, Any]] = {
        "bold": {
            "radius": "1rem", "btn_radius": ".5rem", "hero_align": "left",
            "hero_bg": "radial-gradient(circle at 85% 12%,{accent}55,transparent 28%),linear-gradient(135deg,{primary},{primary}cc)",
            "heading_font": None,
        },
        "trust": {
            "radius": ".65rem", "btn_radius": ".65rem", "hero_align": "center",
            "hero_bg": "{primary}",
            "heading_font": "'Source Serif 4',serif",
        },
        "structured": {
            "radius": ".2rem", "btn_radius": ".2rem", "hero_align": "left",
            "hero_bg": "{primary}",
            "heading_font": None,
        },
        "editorial": {
            "radius": "0", "btn_radius": "0", "hero_align": "center",
            "hero_bg": "#0a0a0a",
            "heading_font": "'Playfair Display',serif",
        },
    }

    # Describes each mood in words for the free-form LLM brief (generate_html_with_llm) —
    # PREVIEW_MOOD_VARS above remains the literal CSS knobs used only by the deterministic
    # fallback renderer (generate_html_preview).
    MOOD_TONE_DESCRIPTIONS: dict[str, str] = {
        "bold": "fast-moving, energetic, impulse-driven — confident color, big decisive type, low friction to act now",
        "trust": "calm, credible, reassuring — generous whitespace, a refined muted palette, credentials and proof placed where decisions happen",
        "structured": "organized, efficient, no-nonsense — clear grids, utilitarian layout, easy to scan and compare quickly",
        "editorial": "sophisticated, story-led, considered — elegant typography, magazine-like pacing, curated imagery over busy UI chrome",
    }

    # Guide-key categories that represent scheduling a slot on a calendar
    # (appointment/table) — these report their submissions to the admin
    # dashboard as postMessage type "reservation"; everything else (general
    # enquiries, quotes, intake) reports as "lead". This is the ONLY structural
    # contract handed to the free-form HTML generation prompt below — the
    # dashboard listener (app.js) buckets purely on this `type` field.
    _RESERVATION_GUIDE_KEYS = {"appointment_booking", "table_reservation"}

    def generate_html_with_llm(
        self,
        build_spec: dict[str, Any],
        agent_context: dict[str, Any] | None = None,
    ) -> str:
        """Use LLM to generate a complete HTML site driven by agent-identified workflows."""
        if not self.planner:
            return ""

        business = build_spec.get("business", {})
        branding = business.get("branding") or {}
        name = business.get("name", "Our Business")
        location = business.get("location", "")
        vertical = business.get("vertical", "general")
        usp = business.get("unique_selling_points", "")
        hours = business.get("business_hours", "")
        phone = business.get("phone_number", "")
        goal = business.get("goal", "")
        ctx = agent_context or {}
        requirements_spec = ctx.get("requirements_spec") or {}
        design_spec = ctx.get("design_spec") or {}
        visual_system = design_spec.get("visual_system") or {}
        reasoning_notes = ctx.get("reasoning_notes") or []
        retrieved_memories = ctx.get("retrieved_memories") or []
        human_answers = ctx.get("human_answers") or {}
        research_results = ctx.get("research_results") or {}
        primary = visual_system.get("primary_color") or branding.get("primary_color") or business.get("primary_color") or "#2563eb"
        accent = visual_system.get("accent_color") or branding.get("accent_color") or business.get("accent_color") or "#f59e0b"
        font_family = visual_system.get("font_family") or business.get("font_family") or "Inter"

        raw_workflows: list[Any] = (
            requirements_spec.get("required_workflows")
            or [f.get("key", "") for f in build_spec.get("includedFeatures", []) if f.get("key")]
            or _default_workflows_for_vertical(vertical, build_spec.get("businessShape", ""))
        )
        trust_requirements: list[str] = requirements_spec.get("trust_requirements") or []
        menu_items: list[dict] = build_spec.get("menuItems", [])

        # Which interaction pattern does this business actually need? A cart
        # (browse multiple priced items, add several, checkout) is completely
        # different from a one-click reserve (library/rental: no price, no
        # running total) or a plain contact form (booking/lead/quote) — using
        # the same cart UI for all of them is exactly what made every
        # generated site feel like the same restaurant template regardless
        # of business type.
        feature_keys = {str(f.get("key", "")).lower() for f in build_spec.get("includedFeatures", [])}
        # Check reserve FIRST: `menuItems` is reused generically as "the list
        # of real items" for both purchasable products AND catalog/library
        # items, so a non-empty list alone can't be trusted to mean "needs a
        # cart" — an explicit catalog_reservation feature must win over that.
        needs_reserve = "catalog_reservation" in feature_keys
        needs_cart = (not needs_reserve) and ("online_ordering" in feature_keys or bool(menu_items))
        commerce = commerce_copy(build_spec.get("businessShape", ""), vertical, business.get("subtype", ""), goal, usp)
        loc_low = location.lower()
        india_cities = ["india", "bangalore", "bengaluru", "mumbai", "delhi", "chennai", "hyderabad", "pune", "kolkata"]
        currency_sym = "₹" if any(c in loc_low for c in india_cities) else "$"

        # These workflow keys are handled by the dedicated cart/reserve
        # section below instead of a generic contact form.
        skip_workflow_keys: set[str] = set()
        if needs_cart:
            skip_workflow_keys.update({"order", "online_ordering"})
        if needs_reserve:
            skip_workflow_keys.add("catalog_reservation")

        # Each remaining workflow (booking/lead/quote/etc.) becomes a plain-English
        # requirement rather than a prescribed <form id=...> markup — the model
        # decides the actual HTML/JS, it just has to fire the integration hook
        # (see prompt below) with the right `type` when the visitor submits.
        workflow_specs: list[dict] = []
        for wf in raw_workflows:
            wf_key = str(wf).lower().replace(" ", "_")
            if wf_key in skip_workflow_keys:
                continue
            matched = next((k for k in WORKFLOW_FIELD_GUIDE if k in wf_key or wf_key in k), None)
            fields = _workflow_fields(matched, vertical) if matched else ["Name", "Phone", "Email", "Message"]
            guide_key = matched or wf_key
            title = guide_key.replace("_", " ").title()
            canonical_type = "reservation" if guide_key in self._RESERVATION_GUIDE_KEYS else "lead"
            workflow_specs.append({"guide_key": guide_key, "title": title, "fields": fields, "type": canonical_type})

        wf_lines = [
            f'- "{ws["title"]}" — let visitors submit: {", ".join(ws["fields"])}. Write intro copy specific to '
            f'this {vertical} business explaining why they would use it. On submit, fire the integration hook '
            f'below with type="{ws["type"]}", then show a friendly confirmation in place of the form.'
            for ws in workflow_specs
        ]
        wf_block = ("\n" + "\n".join(wf_lines)) if wf_lines else ""

        items_block = ""
        if needs_cart:
            item_lines = "\n".join(
                f'  - {item.get("name", "Item")} — {currency_sym}{item.get("priceSortValue", 0)}'
                for item in menu_items[:20]
            ) if menu_items else "  (no real items were provided — invent 3-4 plausible items with realistic prices for this specific business)"
            items_block = (
                f'\n═══ WORKFLOW: BROWSE & BUY ═══\n'
                f'{commerce["items_subtext"]} Let visitors browse the real items below, add any of them to a '
                f'running cart, see a live count/total, and check out. Design the browsing layout, the cart UI '
                f'(drawer, sidebar, floating bar — your call) and the checkout step yourself; write a short, '
                f'item-specific description for each card rather than a generic phrase like "Freshly prepared X".\n'
                f'Real items to feature (use these exact names and prices, do not invent different ones):\n{item_lines}\n'
                f'When checkout completes, fire the integration hook below with type="order", summary listing '
                f'what was ordered, and the formatted total.'
            )
        elif needs_reserve:
            item_lines = "\n".join(
                f'  - {item.get("name", "Item")}'
                for item in menu_items[:20]
            ) if menu_items else "  (no real catalog items were provided — invent 3-4 plausible items for this business's catalog)"
            items_block = (
                f'\n═══ WORKFLOW: BROWSE & RESERVE ═══\n'
                f'{commerce["items_subtext"]} Let visitors browse the real catalog items below and place a '
                f'one-click hold on any of them — this is a reservation, not a purchase, so there is no price, '
                f'cart, or checkout step. Design the catalog layout and reserve interaction yourself.\n'
                f'Real items to feature:\n{item_lines}\n'
                f'When a visitor reserves an item, fire the integration hook below with type="reservation" and '
                f'a summary naming the item held.'
            )

        trust_str = "; ".join(trust_requirements[:4]) if trust_requirements else \
            f"Show phone ({phone}), business hours, and location prominently to build trust."
        note_lines = [str(n) for n in reasoning_notes[-3:] if n]
        memory_lines = [m.get("summary", str(m)) if isinstance(m, dict) else str(m) for m in retrieved_memories[:2] if m]
        menu_sample = ", ".join(i.get("name", "") for i in menu_items[:6]) if menu_items else ""

        extras = ""
        if note_lines:
            extras += "\nAGENT INSIGHTS (use to write better copy):\n" + "\n".join(f"  - {n}" for n in note_lines)
        if memory_lines:
            extras += "\nPATTERNS FROM MEMORY:\n" + "\n".join(f"  - {m}" for m in memory_lines)
        if menu_sample:
            extras += f"\nMENU ITEMS (show as visual cards in a dedicated menu section between hero and workflows): {menu_sample}"
        if human_answers:
            extras += f"\nHUMAN CLARIFICATIONS (must be reflected in the page): {human_answers}"

        competitor = research_results.get("competitor_analysis") or {}
        local_seo = research_results.get("local_seo") or {}
        menu_research = research_results.get("menu_extraction") or {}
        research_lines: list[str] = []
        if competitor.get("market_gaps"):
            research_lines.append("Market gaps to exploit in the hero/positioning copy: " + "; ".join(competitor["market_gaps"][:3]))
        if competitor.get("differentiation_opportunities"):
            research_lines.append("Differentiation angles to emphasize: " + "; ".join(competitor["differentiation_opportunities"][:3]))
        if competitor.get("competitor_weaknesses"):
            research_lines.append("Competitor weaknesses this business should visibly do better on: " + "; ".join(competitor["competitor_weaknesses"][:3]))
        if local_seo.get("target_keywords"):
            research_lines.append("Work these SEO keywords naturally into headings/copy: " + ", ".join(local_seo["target_keywords"][:6]))
        if local_seo.get("local_search_terms"):
            research_lines.append("Local search terms to reflect in copy: " + ", ".join(local_seo["local_search_terms"][:4]))
        if menu_research.get("business_highlights"):
            research_lines.append("Highlights to call out: " + "; ".join(menu_research["business_highlights"][:3]))
        if menu_research.get("special_offers"):
            research_lines.append("Special offers to feature: " + "; ".join(menu_research["special_offers"][:2]))
        if research_lines:
            extras += "\nRESEARCH FINDINGS (this is real research on competitors and local SEO — the copy must reflect it, not generic filler):\n" + "\n".join(f"  - {line}" for line in research_lines)

        shape = build_spec.get("businessShape", "")
        mood = self.SHAPE_TO_MOOD.get(shape, "bold")
        mood_desc = self.MOOD_TONE_DESCRIPTIONS.get(mood, "")

        prompt = f"""You are a senior web designer/engineer building a single-file HTML website for a real business.

The result must look and feel like a premium, bespoke, modern website — the kind a top design studio, or a
flagship AI model asked directly to "design me a beautiful, authentic website for my business", would produce.
It must NOT look like a generic template, a spec sheet, or an admin form. That bar applies here regardless of
how ordinary this business type sounds — an "ordinary" business still deserves a genuinely well-designed site.

═══ BUSINESS ═══
Name: {name} | Type: {vertical} | Location: {location}
Goal: {goal}
USP: {usp}
Hours: {hours} | Phone: {phone}
{extras}

═══ CREATIVE FREEDOM — YOU DECIDE ═══
Layout, section order, structure, typography, color use, CSS techniques, animations/transitions, and navigation
style are entirely up to you. The brand colors below are a starting point, not a cage — introduce complementary
colors if the design calls for it. Use real photographic imagery wherever it strengthens the page:
https://picsum.photos/seed/<a-descriptive-seed>/<width>/<height> returns real, working placeholder photos with
no signup or API key needed — use a different seed per image so nothing repeats. Google Fonts via <link> tags,
inline SVG icons, gradients, and background patterns are all fair game.
Brand starting point: primary {primary}, accent {accent}, font {font_family}.
Design mood for this business: "{mood}" — {mood_desc}.

═══ WHAT THIS PAGE MUST LET VISITORS DO (build it however you like) ═══
- Immediately understand what {name} is and why they should care — a real hero moment, not a placeholder banner.
- Reach everything you build on the page — give it some form of navigation, whatever style suits your design.
{items_block}{wf_block}
- See real trust signals: {trust_str}
- Find hours ({hours}), phone ({phone}), and location ({location}) easily.

═══ THE ONLY INTEGRATION REQUIREMENT ═══
This page runs inside the business owner's dashboard as an iframe. Whenever a visitor completes one of the
actions above (places an order, reserves an item, submits a form), your JavaScript must call:
    window.parent.postMessage({{type:"order"|"reservation"|"lead", summary:"<short human-readable summary of
    what they did/ordered/requested>", customer:"<their name if collected, else empty string>",
    contact:"<their phone or email if collected, else empty string>"}}, "*")
Use the exact type given for each action above (specified next to each workflow). Beyond firing this one call
at the right moment, how you build the UI/JS to get there is entirely your choice — no prescribed markup,
function names, or class names to follow.

═══ OUTPUT FORMAT ═══
- Output ONLY raw HTML starting with <!DOCTYPE html>, with your own <style> and <script> inline. No markdown,
  no code fences, no explanation before or after.
- Every interactive control must actually do something — no href="#" or dead buttons.
- Write only customer-facing website copy. Never mention BuildSpec, agents, planner reasoning, backend modules,
  implementation details, or phrases like "included because"."""

        try:
            best_model = self.planner.best_model_name()
            html = self.planner.generate_text(
                prompt, max_new_tokens=16000, temperature=0.6, model=best_model, timeout=180.0,
            )
            html = html.strip()
            if html.startswith("```"):
                lines = html.split("\n")
                end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
                html = "\n".join(lines[1:end])
            start = html.find("<!DOCTYPE html>")
            if start == -1:
                start = html.find("<html")
            if start != -1:
                html = html[start:]
                logger.info("LLM HTML generation succeeded (%d chars)", len(html))
                return html
            logger.warning("LLM returned output without valid HTML root; falling back")
            return ""
        except Exception as exc:
            logger.warning("LLM HTML generation failed: %s", exc)
            return ""
    
    def generate_code(
        self,
        build_spec: dict[str, Any],
        agent_context: dict[str, Any] | None = None,
    ) -> GeneratedCode:
        """Generate website code from BuildSpec, using LLM when available."""
        business = build_spec.get("business", {})
        vertical = business.get("vertical", "restaurant")
        context_design_spec = (
            (agent_context or {}).get("design_spec")
            or {}
        )
        visual_system = (
            context_design_spec.get("visual_system")
            or {}
        )
        if visual_system:
            if visual_system.get("primary_color"):
                business["primary_color"] = visual_system.get("primary_color")
            if visual_system.get("accent_color"):
                business["accent_color"] = visual_system.get("accent_color")
            if visual_system.get("font_family"):
                business["font_family"] = visual_system.get("font_family")
        if agent_context and agent_context.get("human_answers"):
            business["human_answers"] = agent_context.get("human_answers") or {}
        feature_keys = {
            str(feature.get("key", "")).lower()
            for feature in build_spec.get("includedFeatures", [])
        }
        # Same reserve-first priority as generate_html_with_llm: a
        # catalog_reservation feature means "one-click hold" (no cart), even
        # though menuItems is reused generically to carry the real item list.
        needs_reserve = "catalog_reservation" in feature_keys
        needs_cart = (not needs_reserve) and ("online_ordering" in feature_keys or bool(build_spec.get("menuItems")))

        html_preview = self.generate_html_with_llm(build_spec, agent_context)
        if not self._html_has_working_commerce_ui(html_preview, needs_cart, needs_reserve):
            logger.info(
                "LLM preview omitted the required cart/reserve mechanism; using deterministic commerce preview"
            )
            html_preview = ""
        if not self._html_reflects_human_clarifications(
            html_preview,
            business.get("human_answers") or {},
        ):
            logger.info(
                "LLM preview omitted human clarification content; using deterministic preview"
            )
            html_preview = ""
        if not html_preview:
            logger.info("LLM generation unavailable or failed; using static HTML preview")
            html_preview = self.generate_html_preview(build_spec)

        # No static per-vertical template here: html_preview above is the real,
        # business-aware output. A hardcoded placeholder page previously shown
        # here (e.g. "Repair Services / Fast and reliable repairs") had nothing
        # to do with the actual business.
        pages: dict[str, str] = {}
        components: dict[str, str] = {}

        branding = business.get("branding", {})
        styles = (
            "module.exports = {\n"
            "  theme: {\n"
            "    extend: {\n"
            "      colors: {\n"
            f"        primary: '{branding.get('primary_color', '#3b82f6')}',\n"
            f"        secondary: '{branding.get('secondary_color', '#1e40af')}',\n"
            f"        accent: '{branding.get('accent_color', '#f59e0b')}',\n"
            "      },\n"
            "    },\n"
            "  },\n"
            "}\n"
        )
        config = {
            "business": business,
            "vertical": vertical,
            "features": build_spec.get("includedFeatures", []),
        }

        return GeneratedCode(
            pages=pages,
            components=components,
            styles=styles,
            config=config,
            html_preview=html_preview,
        )

    @staticmethod
    def _html_has_working_commerce_ui(html: str, needs_cart: bool, needs_reserve: bool) -> bool:
        # generate_html_with_llm's prompt no longer prescribes any specific
        # markup/function/class names — the model designs the cart or reserve
        # UI freely. The only thing it's required to produce is the
        # postMessage integration hook with the matching `type`, so that's
        # the only thing checked here. Whitespace is stripped before matching
        # since generated JS formatting (spacing, quote style) varies freely.
        if not needs_cart and not needs_reserve:
            return True
        lower = re.sub(r"\s+", "", (html or "").lower())
        if "postmessage" not in lower:
            return False
        needle = "type:'order'" if needs_cart else "type:'reservation'"
        needle_dq = needle.replace("'", '"')
        return needle in lower or needle_dq in lower

    @staticmethod
    def _html_reflects_human_clarifications(
        html: str,
        human_answers: dict[str, Any],
    ) -> bool:
        if not human_answers:
            return True
        lower = (html or "").lower()
        provider_answer = str(
            human_answers.get("simulation_provider_credentials")
            or ""
        ).strip()
        if provider_answer:
            first_provider = provider_answer.replace("\n", ";").split(";")[0]
            provider_name = first_provider.split(",")[0].strip().lower()
            if provider_name and provider_name not in lower:
                return False
        for key in (
            "simulation_response_timing",
            "simulation_privacy_reassurance",
        ):
            answer = str(human_answers.get(key) or "").strip().lower()
            if answer and answer not in lower:
                return False
        return True


class CodeGenerationOrchestrator:
    """Orchestrates code generation process"""
    
    def __init__(self, planner: Optional[ModelJsonPlanner] = None):
        self.generator = CodeGenerator(planner)
    
    def generate_website(
        self,
        build_spec: dict[str, Any],
        output_dir: Optional[Path] = None,
        agent_context: dict[str, Any] | None = None,
    ) -> GeneratedCode:
        """Generate complete website from BuildSpec."""
        logger.info("Generating website for vertical: %s", build_spec.get("business", {}).get("vertical", "unknown"))
        generated_code = self.generator.generate_code(build_spec, agent_context=agent_context)
        if output_dir:
            self.write_code_to_disk(generated_code, output_dir)
        return generated_code
    
    def write_code_to_disk(self, code: GeneratedCode, output_dir: Path) -> None:
        """Write generated code to disk"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Write pages
        pages_dir = output_dir / "pages"
        pages_dir.mkdir(exist_ok=True)
        for page_name, page_code in code.pages.items():
            (pages_dir / f"{page_name}.js").write_text(page_code)
        
        # Write components
        components_dir = output_dir / "components"
        components_dir.mkdir(exist_ok=True)
        for component_name, component_code in code.components.items():
            (components_dir / f"{component_name}.js").write_text(component_code)
        
        # Write styles
        (output_dir / "tailwind.config.js").write_text(code.styles)
        
        # Write config
        import json
        (output_dir / "config.json").write_text(json.dumps(code.config, indent=2))
        
        logger.info(f"Code written to {output_dir}")


if __name__ == "__main__":
    # Test code generation
    test_build_spec = {
        "business": {
            "name": "Bella Napoli",
            "location": "San Francisco",
            "goal": "increase online orders and table reservations",
            "unique_selling_points": "Family recipes passed down 3 generations, wood-fired pizza",
            "target_audience": "Families and young professionals",
            "business_hours": "11am-10pm daily",
            "phone_number": "+1 (415) 555-0123",
            "contact_email": "hello@bellanapoli.example",
            "vertical": "restaurant",
            "branding": {
                "primary_color": "#dc2626",
                "secondary_color": "#1e3a8a",
                "accent_color": "#f59e0b",
            },
        },
        "includedFeatures": [
            {"label": "Online ordering"},
            {"label": "Menu display"},
            {"label": "Contact form"},
        ],
    }
    
    orchestrator = CodeGenerationOrchestrator()
    generated = orchestrator.generate_website(test_build_spec)
    
    print("Generated Code:")
    print(f"Pages: {list(generated.pages.keys())}")
    print(f"Components: {list(generated.components.keys())}")
    print(f"Styles length: {len(generated.styles)}")
