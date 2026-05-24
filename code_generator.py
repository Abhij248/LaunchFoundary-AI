"""
Template + AI-Assisted Code Generation System

Generates website code using a hybrid approach:
- Base templates for common verticals (restaurant, clinic, service)
- AI customization based on BuildSpec
- Next.js/React + Tailwind output
"""

from __future__ import annotations
import logging
from typing import Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from agentic_planner import ModelJsonPlanner, PlannerGenerationError

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


def _default_workflows_for_vertical(vertical: str) -> list[str]:
    """Return sensible default workflow keys when the agent provides none."""
    return VERTICAL_DEFAULT_WORKFLOWS.get(vertical, ["lead_capture", "contact_form"])


# Base templates for different verticals
RESTAURANT_TEMPLATE = """
import React from 'react';
import Head from 'next/head';

export default function RestaurantPage({ business, branding }) {
  return (
    <div className="min-h-screen bg-gray-50">
      <Head>
        <title>{business.name} - {business.location}</title>
        <meta name="description" content={business.unique_selling_points} />
      </Head>
      
      {/* Header */}
      <header style={{ backgroundColor: branding.primary_color }} className="text-white py-6">
        <div className="container mx-auto px-4">
          <h1 className="text-4xl font-bold">{business.name}</h1>
          <p className="text-lg opacity-90">{business.location}</p>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-16 bg-gradient-to-br from-gray-100 to-gray-200">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-5xl font-bold mb-4" style={{ color: branding.primary_color }}>
            Welcome to {business.name}
          </h2>
          <p className="text-xl text-gray-700 max-w-2xl mx-auto mb-8">
            {business.unique_selling_points}
          </p>
          <button 
            className="px-8 py-3 rounded-lg text-white font-semibold"
            style={{ backgroundColor: branding.accent_color }}
          >
            Order Now
          </button>
        </div>
      </section>

      {/* Menu Section */}
      <section className="py-16">
        <div className="container mx-auto px-4">
          <h3 className="text-3xl font-bold mb-8 text-center">Our Menu</h3>
          <div className="grid md:grid-cols-3 gap-6">
            {/* Menu items would be dynamically generated */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h4 className="font-bold text-lg mb-2">Signature Dish</h4>
              <p className="text-gray-600">Delicious description here</p>
              <p className="font-bold mt-2" style={{ color: branding.primary_color }}>$12.99</p>
            </div>
          </div>
        </div>
      </section>

      {/* Contact Section */}
      <section className="py-16 bg-gray-800 text-white">
        <div className="container mx-auto px-4">
          <h3 className="text-3xl font-bold mb-8 text-center">Contact Us</h3>
          <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            <div>
              <h4 className="font-bold mb-2">Location</h4>
              <p className="text-gray-300">{business.location}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Hours</h4>
              <p className="text-gray-300">{business.business_hours}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Phone</h4>
              <p className="text-gray-300">{business.phone_number}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Email</h4>
              <p className="text-gray-300">{business.contact_email}</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
"""

CLINIC_TEMPLATE = """
import React from 'react';
import Head from 'next/head';

export default function ClinicPage({ business, branding }) {
  return (
    <div className="min-h-screen bg-blue-50">
      <Head>
        <title>{business.name} - {business.location}</title>
        <meta name="description" content={business.unique_selling_points} />
      </Head>
      
      {/* Header */}
      <header style={{ backgroundColor: branding.primary_color }} className="text-white py-6">
        <div className="container mx-auto px-4">
          <h1 className="text-4xl font-bold">{business.name}</h1>
          <p className="text-lg opacity-90">{business.location}</p>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-16 bg-gradient-to-br from-blue-100 to-blue-200">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-5xl font-bold mb-4" style={{ color: branding.primary_color }}>
            Your Health, Our Priority
          </h2>
          <p className="text-xl text-gray-700 max-w-2xl mx-auto mb-8">
            {business.unique_selling_points}
          </p>
          <button 
            className="px-8 py-3 rounded-lg text-white font-semibold"
            style={{ backgroundColor: branding.accent_color }}
          >
            Book Appointment
          </button>
        </div>
      </section>

      {/* Services Section */}
      <section className="py-16">
        <div className="container mx-auto px-4">
          <h3 className="text-3xl font-bold mb-8 text-center">Our Services</h3>
          <div className="grid md:grid-cols-3 gap-6">
            <div className="bg-white rounded-lg shadow-md p-6">
              <h4 className="font-bold text-lg mb-2">General Checkup</h4>
              <p className="text-gray-600">Comprehensive health assessments</p>
            </div>
            <div className="bg-white rounded-lg shadow-md p-6">
              <h4 className="font-bold text-lg mb-2">Specialist Care</h4>
              <p className="text-gray-600">Expert medical specialists</p>
            </div>
            <div className="bg-white rounded-lg shadow-md p-6">
              <h4 className="font-bold text-lg mb-2">Emergency Care</h4>
              <p className="text-gray-600">24/7 emergency services</p>
            </div>
          </div>
        </div>
      </section>

      {/* Contact Section */}
      <section className="py-16 bg-gray-800 text-white">
        <div className="container mx-auto px-4">
          <h3 className="text-3xl font-bold mb-8 text-center">Contact Us</h3>
          <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            <div>
              <h4 className="font-bold mb-2">Location</h4>
              <p className="text-gray-300">{business.location}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Hours</h4>
              <p className="text-gray-300">{business.business_hours}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Phone</h4>
              <p className="text-gray-300">{business.phone_number}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Email</h4>
              <p className="text-gray-300">{business.contact_email}</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
"""

SERVICE_TEMPLATE = """
import React from 'react';
import Head from 'next/head';

export default function ServicePage({ business, branding }) {
  return (
    <div className="min-h-screen bg-gray-50">
      <Head>
        <title>{business.name} - {business.location}</title>
        <meta name="description" content={business.unique_selling_points} />
      </Head>
      
      {/* Header */}
      <header style={{ backgroundColor: branding.primary_color }} className="text-white py-6">
        <div className="container mx-auto px-4">
          <h1 className="text-4xl font-bold">{business.name}</h1>
          <p className="text-lg opacity-90">{business.location}</p>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-16 bg-gradient-to-br from-orange-100 to-orange-200">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-5xl font-bold mb-4" style={{ color: branding.primary_color }}>
            Expert Services You Can Trust
          </h2>
          <p className="text-xl text-gray-700 max-w-2xl mx-auto mb-8">
            {business.unique_selling_points}
          </p>
          <button 
            className="px-8 py-3 rounded-lg text-white font-semibold"
            style={{ backgroundColor: branding.accent_color }}
          >
            Get a Quote
          </button>
        </div>
      </section>

      {/* Services Section */}
      <section className="py-16">
        <div className="container mx-auto px-4">
          <h3 className="text-3xl font-bold mb-8 text-center">Our Services</h3>
          <div className="grid md:grid-cols-3 gap-6">
            <div className="bg-white rounded-lg shadow-md p-6">
              <h4 className="font-bold text-lg mb-2">Repair Services</h4>
              <p className="text-gray-600">Fast and reliable repairs</p>
            </div>
            <div className="bg-white rounded-lg shadow-md p-6">
              <h4 className="font-bold text-lg mb-2">Maintenance</h4>
              <p className="text-gray-600">Preventive maintenance plans</p>
            </div>
            <div className="bg-white rounded-lg shadow-md p-6">
              <h4 className="font-bold text-lg mb-2">Emergency Service</h4>
              <p className="text-gray-600">24/7 emergency support</p>
            </div>
          </div>
        </div>
      </section>

      {/* Contact Section */}
      <section className="py-16 bg-gray-800 text-white">
        <div className="container mx-auto px-4">
          <h3 className="text-3xl font-bold mb-8 text-center">Contact Us</h3>
          <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            <div>
              <h4 className="font-bold mb-2">Service Area</h4>
              <p className="text-gray-300">{business.location}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Hours</h4>
              <p className="text-gray-300">{business.business_hours}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Phone</h4>
              <p className="text-gray-300">{business.phone_number}</p>
            </div>
            <div>
              <h4 className="font-bold mb-2">Email</h4>
              <p className="text-gray-300">{business.contact_email}</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
"""


class CodeGenerator:
    """Template + AI-assisted code generator"""
    
    def __init__(self, planner: Optional[ModelJsonPlanner] = None):
        self.planner = planner
        self.templates = {
            "restaurant": RESTAURANT_TEMPLATE,
            "clinic": CLINIC_TEMPLATE,
            "repair_service": SERVICE_TEMPLATE,
            "service": SERVICE_TEMPLATE,
        }
    
    def get_template_for_vertical(self, vertical: str) -> str:
        """Get base template for a given vertical"""
        return self.templates.get(vertical, self.templates["restaurant"])

    def generate_html_preview(self, build_spec: dict[str, Any]) -> str:
        """Generate a functional HTML preview with working forms and real business values"""
        business = build_spec.get("business", {})
        branding = business.get("branding") or {}
        name = business.get("name", "Our Business")
        location = business.get("location", "")
        vertical = business.get("vertical", "restaurant")
        usp = (business.get("unique_selling_points")
               or f"Your premier {vertical.replace('_', ' ')} in {location}")
        hours = business.get("business_hours") or "Call us for our hours"
        phone = business.get("phone_number") or "Contact us online"
        email = business.get("contact_email") or business.get("email") or ""
        primary = (branding.get("primary_color")
                   or business.get("primary_color") or "#dc2626")
        accent = (branding.get("accent_color")
                  or business.get("accent_color") or "#f59e0b")

        features = build_spec.get("includedFeatures", [])
        food_verticals = {"restaurant", "cafe", "bakery", "food", "pizzeria"}
        is_food_business = str(vertical).lower() in food_verticals
        has_ordering = any(f.get("key") == "online_ordering" for f in features)
        has_reservation = any(f.get("key") == "table_reservation" for f in features)
        has_booking = any(f.get("key") == "appointment_booking" for f in features)

        cta_primary = "Order Now" if has_ordering else ("Book Appointment" if has_booking else "Get in Touch")
        cta_secondary = "Reserve a Table" if has_reservation else ""

        pages = build_spec.get("pages", ["Home", "Menu", "Contact"])
        # Map page names to section anchors within this document
        _anchor_map = {
            "home": "hero", "menu": "menu", "order online": "menu",
            "order": "menu", "reservations": "reserve", "reservation": "reserve",
            "book": "reserve", "appointments": "reserve", "about": "contact",
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
            reserve_section = (
                f'<section id="reserve" class="sec"><div class="wrap">'
                f'<h2>{label}</h2><p class="sub">Secure your spot at {name}</p>'
                f'<form class="frm" id="reserveForm">'
                f'<input type="text" name="cname" placeholder="Your name" required>'
                f'<input type="email" name="email" placeholder="Email address" required>'
                f'<input type="date" name="date" required>'
                f'<input type="number" name="guests" placeholder="Number of guests" min="1" max="20" required>'
                f'<button type="submit">{label}</button></form>'
                f'</div></section>'
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

        # --- Menu items from BuildSpec ---
        menu_items = build_spec.get("menuItems", [])
        if is_food_business and not menu_items:
            menu_items = [
                {
                    "id": "fallback-margherita",
                    "name": "Margherita Pizza",
                    "category": "Popular",
                    "description": "Classic house pizza ready for online ordering.",
                    "priceLabel": f"{currency_sym}{price_default:.2f}",
                    "priceSortValue": price_default,
                },
                {
                    "id": "fallback-pasta",
                    "name": "White Sauce Pasta",
                    "category": "Popular",
                    "description": "Creamy pasta option surfaced from restaurant intent.",
                    "priceLabel": f"{currency_sym}{price_default + (50 if currency_sym == '\u20b9' else 3):.2f}",
                    "priceSortValue": price_default + (50 if currency_sym == "\u20b9" else 3),
                },
            ]
        has_ordering = has_ordering or bool(menu_items and is_food_business)
        cta_primary = "Order Now" if has_ordering else cta_primary
        contact_cls = "sec" if (has_ordering or has_reservation or has_booking) else "sec alt"

        _emap = [
            (["burger","sandwich"],"🍔"),(["pizza"],"🍕"),(["fries","chips"],"🍟"),
            (["steak","meat","grill"],"🥩"),(["breakfast","egg","waffle"],"🍳"),
            (["pasta","noodle"],"🍝"),(["beverage","drink","juice","coffee","tea"],"🥤"),
            (["salad","lunch"],"🥗"),(["soup","curry","stew"],"🍲"),
            (["chicken","wings"],"🍗"),(["fish","seafood","shrimp"],"🐟"),
            (["cake","dessert","sweet","ice cream"],"🍰"),(["dinner"],"🍽️"),
            (["wrap","taco","burrito"],"🌯"),(["donut","pancake"],"🥞"),
        ]

        def _emoji(n: str) -> str:
            nl = n.lower()
            for kws, em in _emap:
                if any(k in nl for k in kws):
                    return em
            return "🍴"

        def _card(item: dict) -> str:
            iid = str(item.get("id", "")).replace("'", "").replace('"', "")
            nm  = item.get("name", "Item")
            cat = item.get("category", "Popular")
            dsc = (item.get("description") or f"Freshly prepared {nm.lower()}.")
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

        cats = list(dict.fromkeys(i.get("category", "Popular") for i in menu_items)) if menu_items else []
        cat_tabs_html = (
            '<button class="ctab active" onclick="filterCat(\'all\',this)">All</button>'
            + "".join(f'<button class="ctab" onclick="filterCat(\'{c}\',this)">{c}</button>' for c in cats)
        )
        items_html = "".join(_card(i) for i in menu_items)

        menu_section = ""
        if menu_items:
            menu_section = (
                f'<section id="menu" class="sec alt"><div class="wrap">'
                f'<h2>Our Menu</h2><p class="sub">Tap any item to add it to your order</p>'
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
            "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#1f2937;padding-bottom:70px;background:#f8faf9}"
            f"nav{{background:{primary};color:#fff;padding:.8rem 2rem;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:99}}"
            "nav strong{font-size:1.05rem;font-weight:700}"
            "nav a{color:#fff;text-decoration:none;margin-left:1rem;font-size:.88rem;opacity:.9}"
            f".hero{{background:radial-gradient(circle at 85% 12%,{accent}55,transparent 28%),linear-gradient(135deg,{primary},{primary}cc);color:#fff;padding:5.5rem 2rem 4.5rem;text-align:left;position:relative;overflow:hidden}}"
            ".hero::after{content:'';position:absolute;right:-120px;bottom:-160px;width:420px;height:420px;border-radius:50%;background:rgba(255,255,255,.11)}"
            ".hero h1{font-size:clamp(2.4rem,6vw,4.4rem);line-height:1;font-weight:850;margin:0 auto .9rem;max-width:860px;letter-spacing:0}"
            ".hero p{font-size:1.13rem;line-height:1.65;max-width:720px;margin:.5rem auto 2rem;opacity:.93}"
            ".ctas{display:flex;gap:.75rem;justify-content:flex-start;flex-wrap:wrap;max-width:860px;margin:0 auto}"
            f".btn-p{{background:{accent};color:#fff;border:none;padding:.8rem 1.75rem;border-radius:.5rem;font-size:1rem;font-weight:700;cursor:pointer;text-decoration:none}}"
            ".btn-s{background:transparent;color:#fff;border:2px solid rgba(255,255,255,.8);padding:.8rem 1.75rem;border-radius:.5rem;font-size:1rem;font-weight:600;cursor:pointer;text-decoration:none}"
            ".sec{padding:3.5rem 2rem}.sec.alt{background:#f9fafb}"
            ".wrap{max-width:860px;margin:0 auto}"
            f"h2{{font-size:1.75rem;font-weight:700;color:{primary};margin-bottom:.4rem}}"
            ".sub{color:#6b7280;margin-bottom:1.5rem;font-size:.97rem}"
            ".fgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:1rem}"
            f".fc{{background:linear-gradient(180deg,#fff,#fbfdfb);border:1px solid #e5e7eb;border-radius:1rem;padding:1.35rem;box-shadow:0 14px 32px rgba(15,23,42,.07)}}"
            f".fc h4{{color:{primary};font-weight:700;margin-bottom:.4rem;font-size:.95rem}}"
            ".fc p{font-size:.85rem;color:#6b7280}"
            ".frm{display:flex;flex-direction:column;gap:.7rem;max-width:460px}"
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
            f'<section class="sec"><div class="wrap">'
            f'<h2>{"Order, Reserve, Enjoy" if is_food_business else "How We Help"}</h2>'
            f'<p class="sub">{"A smoother way to browse the menu, place an order, or plan a visit." if is_food_business else f"Simple ways to connect with {name}."}</p>'
            f'<div class="fgrid">{feat_cards}</div></div></section>'
            f'{menu_section}'
            f'{order_section}'
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
    
    # ------------------------------------------------------------------
    # Modern design-system CSS injected verbatim into every LLM page.
    # Anchored to CSS custom properties so brand colours work without
    # the LLM having to re-derive them.
    # ------------------------------------------------------------------
    _BASE_CSS_TPL = (
        "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');"
        "*{{box-sizing:border-box;margin:0;padding:0}}"
        ":root{{--p:{primary};--a:{accent};--bg:#f8fafc;--text:#0f172a;--muted:#64748b;--border:#e2e8f0;--r:12px;--sh:0 4px 6px -1px rgba(0,0,0,.07),0 2px 4px rgba(0,0,0,.05)}}"
        "body{{font-family:'Inter',system-ui,sans-serif;color:var(--text);background:var(--bg)}}"
        "nav{{background:var(--p);position:sticky;top:0;z-index:100;padding:.9rem 2rem;display:flex;align-items:center;justify-content:space-between;box-shadow:0 1px 3px rgba(0,0,0,.15)}}"
        ".nav-logo{{font-size:1.05rem;font-weight:800;color:#fff;letter-spacing:0;text-decoration:none}}"
        ".nav-links{{display:flex;gap:1.75rem}}"
        ".nav-links a{{color:rgba(255,255,255,.82);text-decoration:none;font-size:.875rem;font-weight:500;transition:color .15s;cursor:pointer}}"
        ".nav-links a:hover{{color:#fff}}"
        ".hero{{padding:6rem 2rem 5rem;text-align:left;background:radial-gradient(circle at 85% 12%,var(--a) 0,transparent 28%),linear-gradient(135deg,var(--p) 0%,color-mix(in srgb,var(--p) 72%,#000) 100%);position:relative;overflow:hidden}}"
        ".hero h1{{font-size:clamp(2.25rem,6vw,4.5rem);font-weight:850;color:#fff;letter-spacing:0;line-height:1;margin:0 auto 1rem;max-width:920px}}"
        ".hero p{{font-size:1.1rem;color:rgba(255,255,255,.86);max-width:720px;margin:.5rem auto 2.5rem;line-height:1.65}}"
        ".cta-row{{display:flex;gap:.875rem;justify-content:flex-start;max-width:920px;margin:0 auto;flex-wrap:wrap}}"
        ".btn{{display:inline-block;padding:.85rem 2rem;border-radius:var(--r);font-size:.95rem;font-weight:700;text-decoration:none;cursor:pointer;border:none;transition:all .2s;font-family:inherit}}"
        ".btn-accent{{background:var(--a);color:#fff;box-shadow:0 4px 14px rgba(0,0,0,.18)}}"
        ".btn-accent:hover{{transform:translateY(-2px);box-shadow:0 8px 22px rgba(0,0,0,.22)}}"
        ".btn-ghost{{background:transparent;color:#fff;border:2px solid rgba(255,255,255,.55)}}"
        ".btn-ghost:hover{{background:rgba(255,255,255,.12)}}"
        ".trust-bar{{background:#fff;border-bottom:1px solid var(--border);padding:.875rem 2rem;display:flex;gap:2rem;justify-content:center;flex-wrap:wrap}}"
        ".trust-item{{font-size:.8rem;font-weight:600;color:var(--muted);display:flex;align-items:center;gap:.35rem}}"
        "section.sec{{padding:5rem 2rem}}"
        "section.sec.alt{{background:#fff}}"
        ".container{{max-width:960px;margin:0 auto}}"
        ".sec-tag{{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--p);margin-bottom:.6rem}}"
        ".sec-title{{font-size:1.875rem;font-weight:800;letter-spacing:0;margin-bottom:.4rem}}"
        ".sec-sub{{color:var(--muted);font-size:.975rem;margin-bottom:2.25rem;line-height:1.65}}"
        ".card{{background:linear-gradient(180deg,#fff,#fbfdfb);border:1px solid var(--border);border-radius:var(--r);padding:1.75rem;box-shadow:0 14px 32px rgba(15,23,42,.08);transition:box-shadow .2s,transform .2s}}"
        ".card:hover{{transform:translateY(-2px);box-shadow:0 18px 42px rgba(15,23,42,.12)}}"
        ".card-icon{{font-size:1.75rem;margin-bottom:.875rem}}"
        ".card h3{{font-size:1rem;font-weight:700;margin-bottom:.4rem}}"
        ".card p{{font-size:.875rem;color:var(--muted);line-height:1.55}}"
        ".grid-3{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1.25rem}}"
        ".grid-2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:1.5rem}}"
        "form.wf-form{{display:flex;flex-direction:column;gap:.875rem;max-width:500px}}"
        "form.wf-form label{{font-size:.8rem;font-weight:600;color:var(--text);margin-bottom:.15rem;display:block}}"
        "form.wf-form input,form.wf-form textarea,form.wf-form select{{padding:.75rem 1rem;border:1.5px solid var(--border);border-radius:8px;font-size:.9rem;font-family:inherit;color:var(--text);background:#fff;transition:border-color .2s;width:100%}}"
        "form.wf-form input:focus,form.wf-form textarea:focus,form.wf-form select:focus{{outline:none;border-color:var(--p);box-shadow:0 0 0 3px color-mix(in srgb,var(--p) 15%,transparent)}}"
        ".wf-submit{{padding:.875rem;background:var(--p);color:#fff;border:none;border-radius:8px;font-size:1rem;font-weight:700;cursor:pointer;font-family:inherit;transition:background .2s;width:100%}}"
        ".wf-submit:hover{{background:color-mix(in srgb,var(--p) 83%,#000)}}"
        ".success-card{{background:#f0fdf4;border:1.5px solid #86efac;border-radius:var(--r);padding:2rem;text-align:center;color:#166534}}"
        ".success-card h3{{font-size:1.1rem;font-weight:700;margin-bottom:.4rem}}"
        ".success-card p{{font-size:.9rem;opacity:.85}}"
        ".info-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1rem;margin-top:1.5rem}}"
        ".info-card{{background:#fff;border:1px solid var(--border);border-radius:var(--r);padding:1.25rem;text-align:center}}"
        ".info-card h4{{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--p);margin-bottom:.4rem}}"
        ".info-card p{{font-size:.9rem;color:var(--text);font-weight:500}}"
        "footer{{background:var(--p);color:rgba(255,255,255,.7);text-align:center;padding:2.5rem 2rem;font-size:.875rem;line-height:1.7}}"
        "footer strong{{color:#fff;font-weight:700}}"
        "@media(max-width:640px){{.nav-links{{display:none}}.hero{{padding:4rem 1.25rem 3rem}}section.sec{{padding:3rem 1.25rem}}}}"
    )

    _BASE_JS = (
        "<script>"
        "function navTo(id){var el=document.getElementById(id);if(el)el.scrollIntoView({behavior:'smooth',block:'start'});}"
        "function wfForm(formId,type){var f=document.getElementById(formId);if(!f)return;f.addEventListener('submit',function(e){e.preventDefault();var d={};new FormData(f).forEach(function(v,k){d[k]=v;});window.parent.postMessage(Object.assign({type:type},d),'*');var p=f.parentElement;p.innerHTML='<div class=\"success-card\"><h3>&#10003; Got it!</h3><p>We\\'ll be in touch shortly.</p></div>';});}"
        "</script>"
    )

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
        primary = branding.get("primary_color") or business.get("primary_color") or "#2563eb"
        accent = branding.get("accent_color") or business.get("accent_color") or "#f59e0b"

        ctx = agent_context or {}
        requirements_spec = ctx.get("requirements_spec") or {}
        reasoning_notes = ctx.get("reasoning_notes") or []
        retrieved_memories = ctx.get("retrieved_memories") or []

        raw_workflows: list[Any] = (
            requirements_spec.get("required_workflows")
            or [f.get("key", "") for f in build_spec.get("includedFeatures", []) if f.get("key")]
            or _default_workflows_for_vertical(vertical)
        )
        trust_requirements: list[str] = requirements_spec.get("trust_requirements") or []
        menu_items: list[dict] = build_spec.get("menuItems", [])

        # Pre-assign deterministic anchor IDs so nav links always match sections.
        workflow_specs: list[dict] = []
        for wf in raw_workflows:
            wf_key = str(wf).lower().replace(" ", "_")
            matched = next((k for k in WORKFLOW_FIELD_GUIDE if k in wf_key or wf_key in k), None)
            fields = _workflow_fields(matched, vertical) if matched else ["Name", "Phone", "Email", "Message"]
            guide_key = matched or wf_key
            section_id = f"sec-{guide_key.replace('_', '-')[:22]}"
            title = guide_key.replace("_", " ").title()
            form_id = f"form-{guide_key[:18]}"
            workflow_specs.append({
                "wf": wf, "guide_key": guide_key, "section_id": section_id,
                "title": title, "form_id": form_id, "fields": fields,
            })

        # Build nav items: always include hero + each workflow + contact
        nav_items = [("Home", "sec-hero")] + [(ws["title"], ws["section_id"]) for ws in workflow_specs] + [("Contact", "sec-contact")]
        nav_links_html = "".join(
            f'<a onclick="navTo(\'{sid}\')">{lbl}</a>'
            for lbl, sid in nav_items
        )
        first_cta_id = workflow_specs[0]["section_id"] if workflow_specs else "sec-contact"

        # Workflow section specifications for the prompt
        wf_spec_lines: list[str] = []
        form_init_calls: list[str] = []
        for ws in workflow_specs:
            fields_str = "; ".join(ws["fields"])
            wf_spec_lines.append(
                f'SECTION id="{ws["section_id"]}" title="{ws["title"]}":\n'
                f'  Write compelling intro copy for a {vertical} business.\n'
                f'  Include a <form id="{ws["form_id"]}" class="wf-form"> with these fields: {fields_str}.\n'
                f'  End form with <button type="submit" class="wf-submit">Submit</button>.\n'
                f'  Do NOT add any form onsubmit attribute — JS wires it up separately.'
            )
            form_init_calls.append(f'wfForm("{ws["form_id"]}","{ws["guide_key"]}")')

        wf_spec_block = "\n\n".join(wf_spec_lines)
        form_init_js = (
            "<script>document.addEventListener('DOMContentLoaded',function(){"
            + "".join(f"{c};" for c in form_init_calls)
            + "});</script>"
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

        base_css = self._BASE_CSS_TPL.format(primary=primary, accent=accent)

        prompt = f"""You are generating a single-file HTML website. Follow these instructions EXACTLY.

═══ BUSINESS ═══
Name: {name} | Type: {vertical} | Location: {location}
Goal: {goal}
USP: {usp}
Hours: {hours} | Phone: {phone}
{extras}

═══ PAGE STRUCTURE (use these exact section IDs) ═══
1. <nav> — sticky navigation with logo "{name}" and these links: {", ".join(f"{lbl}→#{sid}" for lbl,sid in nav_items)}
2. <section id="sec-hero" class="hero"> — full-width hero with h1, tagline, CTA button pointing to #{first_cta_id}
3. Trust bar — one row showing: phone, hours, location as trust-item spans
4. Features overview — 3-card grid highlighting the business's key strengths
{wf_spec_block}
5. <section id="sec-contact" class="sec alt"> — contact info cards (hours, phone, location)
6. <footer> — business name, location, copyright

═══ ACTION ROUTING ═══
- Every non-submit CTA/button must include onclick="navTo('target-section-id')".
- Primary action buttons must point to "{first_cta_id}".
- Contact/support buttons must point to "sec-contact".
- Do not create href="#" links or inert buttons.
- Form submit buttons must remain type="submit" and stay inside their matching form.

═══ VISUAL QUALITY ═══
- Make the page feel like a polished customer website, not an admin/spec view.
- Use a strong first viewport, clear hierarchy, generous spacing, and benefit-led copy.
- Prefer concrete menu/service cards, trust proof, hours/location, and action modules over generic feature explanations.
- Do not write explanatory copy about why sections were included.

═══ TRUST REQUIREMENTS ═══
{trust_str}

═══ CSS — EMBED THIS VERBATIM inside <style> ═══
{base_css}

═══ JS — EMBED THESE TWO BLOCKS VERBATIM ═══
Block 1 (smooth scroll + form wiring helper):
{self._BASE_JS}

Block 2 (wire up all forms after DOM loads):
{form_init_js}

═══ RULES ═══
- Output ONLY raw HTML starting with <!DOCTYPE html>. No markdown, no code fences, no explanation.
- Every nav link must use onclick="navTo('section-id')" with the exact IDs listed above.
- Hero CTA button must use onclick="navTo('{first_cta_id}')".
- Do NOT add any inline onsubmit to forms — the JS block handles it.
- Write only customer-facing website copy. Never mention BuildSpec, agents, planner reasoning, backend modules, implementation details, or phrases like "included because".
- Use class names from the CSS above (sec, alt, container, card, grid-3, btn, btn-accent, etc.)."""

        try:
            html = self.planner.generate_text(prompt, max_new_tokens=4000, temperature=0.3)
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
        food_verticals = {"restaurant", "cafe", "bakery", "food", "pizzeria"}
        is_food_business = str(vertical).lower() in food_verticals
        feature_keys = {
            str(feature.get("key", "")).lower()
            for feature in build_spec.get("includedFeatures", [])
        }
        requires_commerce_preview = is_food_business

        html_preview = self.generate_html_with_llm(build_spec, agent_context)
        if requires_commerce_preview and not self._html_has_menu_cart(html_preview):
            logger.info(
                "LLM preview omitted restaurant menu/cart; using deterministic commerce preview"
            )
            html_preview = ""
        if not html_preview:
            logger.info("LLM generation unavailable or failed; using static HTML preview")
            html_preview = self.generate_html_preview(build_spec)

        template = self.get_template_for_vertical(vertical)
        pages = {"index": template}
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
    def _html_has_menu_cart(html: str) -> bool:
        lower = (html or "").lower()
        has_menu = 'id="menu"' in lower or "id='menu'" in lower or "our menu" in lower
        has_cart = (
            "cart" in lower
            and (
                "additem" in lower
                or "add item" in lower
                or "add to cart" in lower
                or "your order" in lower
            )
        )
        return has_menu and has_cart


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
