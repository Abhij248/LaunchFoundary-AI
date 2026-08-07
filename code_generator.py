"""
Template + AI-Assisted Code Generation System

Generates website code using a hybrid approach:
- Base templates for common verticals (restaurant, clinic, service)
- AI customization based on BuildSpec
- Next.js/React + Tailwind output
"""

from __future__ import annotations
import json
import logging
import os
import re
from html.parser import HTMLParser
from typing import Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from agentic_planner import ModelJsonPlanner
from custom_entities_store import create_entity


COMMERCE_COPY_BUCKETS: dict[str, Any] = {
    "ticketed_event": {
        "keywords": ["theat", "cinema", "movie", "concert", "showtime", "screening", "box office", "ticket"],
        "items_subtext": "Select your tickets and snacks below",
    },
    "food": {
        "keywords": ["restaurant", "cafe", "bakery", "food", "kitchen", "diner", "pizzeria"],
        "items_subtext": "Tap any item to add it to your order",
    },
    "catalog": {
        "keywords": ["library", "librarian", "book lending", "borrow", "lending", "loan program", "rental", "equipment rental", "reserve a copy", "hold a copy", "waitlist", "checkout a book"],
        "items_subtext": "Reserve an item to pick up or borrow",
    },
    "retail": {
        "keywords": [],
        "items_subtext": "Browse our products and add them to your cart",
    },
}


def _smoke_test_tier1_enabled() -> bool:
    return os.getenv("ENABLE_SMOKE_TEST_TIER1", "1").strip().lower() not in {"0", "false", "no", "off"}


def _smoke_test_tier2_enabled() -> bool:
    # Opt-in, not opt-out -- Tier 2 makes real LLM calls (real cost) on
    # every cart/reserve generation, unlike Tier 1's free deterministic check.
    return os.getenv("ENABLE_SMOKE_TEST_TIER2", "0").strip().lower() in {"1", "true", "yes", "on"}


def commerce_copy(shape: str, *text_fields: str) -> tuple[str, dict[str, str]]:
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
        return "catalog", COMMERCE_COPY_BUCKETS["catalog"]
    v = " ".join(str(f) for f in text_fields if f).lower()
    for key in ("ticketed_event", "catalog", "food"):
        bucket = COMMERCE_COPY_BUCKETS[key]
        # NOTE: keywords is a list of whole phrases (some multi-word, e.g.
        # "reserve a copy") checked as substrings directly — do NOT
        # `.split()` this into individual words, that previously produced a
        # garbage single-letter token ("a") that substring-matched almost
        # any text, making the wrong bucket win by default.
        if any(phrase in v for phrase in bucket["keywords"]):
            return key, bucket
    return "retail", COMMERCE_COPY_BUCKETS["retail"]


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
    generation_failed: bool = Field(
        default=False,
        description="True when the real LLM generation failed -- html_preview is empty (no fallback website is generated), and callers should surface this as a retriable failure with generation_error, not a successful result.",
    )
    generation_error: str = Field(
        default="",
        description="Human-readable reason generation_failed is True, so the owner can be told why instead of just that it failed.",
    )


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


def _inject_catalog_empty_state_guard(html: str, business_id: str) -> str:
    """Guarantee an honest empty-catalog experience at the network layer,
    independent of whether the model's own generated JS chose to invent a
    fake fallback product list or write an honest empty state -- prompt
    instructions alone weren't reliably obeyed run-to-run.

    Wraps window.fetch so any call to this business's items endpoint that
    would return zero real items instead resolves to a single honest
    placeholder item. Since the model always renders "whatever the fetch
    returns" as a real item, its own fallback/sample code path (whatever it
    wrote) simply never executes -- the browser only ever sees a non-empty,
    truthful items array.
    """
    if not business_id:
        return html
    items_url = f"/businesses/{business_id}/items"
    if items_url not in html:
        return html

    guard_script = f"""<script>
(function() {{
  var ITEMS_URL = {json.dumps(items_url)};
  var PLACEHOLDER_RESPONSE = {json.dumps({
        "items": [{
            "id": "__placeholder__",
            "name": "New arrivals coming soon",
            "category": "",
            "description": "The owner hasn't added products yet -- check back soon.",
            "priceLabel": "",
            "priceSortValue": 0,
            "imageUrl": "",
        }]
    })};
  var originalFetch = window.fetch.bind(window);
  function placeholderResponse() {{
    return new Response(JSON.stringify(PLACEHOLDER_RESPONSE), {{
      status: 200,
      headers: {{ "Content-Type": "application/json" }},
    }});
  }}
  window.fetch = function(input, init) {{
    var url = typeof input === "string" ? input : (input && input.url) || "";
    if (url.indexOf(ITEMS_URL) === -1) {{
      return originalFetch(input, init);
    }}
    return originalFetch(input, init).then(function(response) {{
      if (!response.ok) return placeholderResponse();
      return response.clone().json().then(function(data) {{
        if (data && Array.isArray(data.items) && data.items.length > 0) return response;
        return placeholderResponse();
      }}).catch(function() {{ return placeholderResponse(); }});
    }}, function() {{ return placeholderResponse(); }});
  }};
}})();
</script>
"""

    lowered = html.lower()
    head_idx = lowered.find("<head>")
    if head_idx != -1:
        insert_at = head_idx + len("<head>")
        return html[:insert_at] + "\n" + guard_script + html[insert_at:]
    html_idx = lowered.find("<html")
    if html_idx != -1:
        tag_end = html.find(">", html_idx)
        if tag_end != -1:
            insert_at = tag_end + 1
            return html[:insert_at] + "\n" + guard_script + html[insert_at:]
    return guard_script + html


_VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class _TopLevelBodyBlockParser(HTMLParser):
    """Captures each direct child of <body> as an addressable block with its
    exact source span, so a revision can target/replace one block instead of
    the model having to rewrite the entire page. <script>/<style> content is
    handled correctly (not mistaken for nested tags) because HTMLParser
    already treats them as raw CDATA per the HTML spec.
    """

    def __init__(self, html: str):
        super().__init__(convert_charrefs=False)
        self._line_starts = [0]
        for i, ch in enumerate(html):
            if ch == "\n":
                self._line_starts.append(i + 1)
        self.in_body = False
        self.body_depth = 0
        self.blocks: list[dict[str, Any]] = []
        self._current_start: int | None = None
        self._current_tag: str | None = None
        self._current_id: str = ""

    def _offset(self) -> int:
        lineno, col = self.getpos()
        return self._line_starts[lineno - 1] + col

    def _record_leaf(self, tag: str, attrs: list[tuple[str, str | None]], fallback: str) -> None:
        if self.body_depth != 0:
            return
        start = self._offset()
        text = self.get_starttag_text() or fallback
        self.blocks.append({
            "tag": tag,
            "id_attr": dict(attrs).get("id") or "",
            "start": start,
            "end": start + len(text),
        })

    def handle_starttag(self, tag, attrs):
        if tag == "body" and not self.in_body:
            self.in_body = True
            return
        if not self.in_body:
            return
        if tag in _VOID_ELEMENTS:
            self._record_leaf(tag, attrs, f"<{tag}>")
            return
        if self.body_depth == 0:
            self._current_start = self._offset()
            self._current_tag = tag
            self._current_id = dict(attrs).get("id") or ""
        self.body_depth += 1

    def handle_startendtag(self, tag, attrs):
        if not self.in_body:
            return
        self._record_leaf(tag, attrs, f"<{tag}/>")

    def handle_endtag(self, tag):
        if tag == "body":
            self.in_body = False
            return
        if not self.in_body or self.body_depth == 0:
            return
        self.body_depth -= 1
        if self.body_depth == 0 and self._current_start is not None:
            end = self._offset() + len(f"</{tag}>")
            self.blocks.append({
                "tag": self._current_tag or tag,
                "id_attr": self._current_id,
                "start": self._current_start,
                "end": end,
            })
            self._current_start = None
            self._current_tag = None
            self._current_id = ""


def _parse_top_level_body_blocks(html: str) -> list[dict[str, Any]]:
    parser = _TopLevelBodyBlockParser(html)
    try:
        parser.feed(html)
    except Exception:
        return []
    blocks = sorted(parser.blocks, key=lambda b: b["start"])
    result: list[dict[str, Any]] = []
    for block in blocks:
        text = html[block["start"]:block["end"]]
        if not text.strip():
            continue
        result.append({
            "block_id": f"block_{len(result)}",
            "tag": block["tag"],
            "id_attr": block["id_attr"],
            "html": text,
            "preview": re.sub(r"\s+", " ", text).strip()[:160],
        })
    return result


def _revision_tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "list_sections",
                "description": (
                    "List the page's top-level sections (block_id, tag, short preview) so you can "
                    "decide which ones need to change for this revision request."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_section",
                "description": "Read the full current HTML of one section by its block_id.",
                "parameters": {
                    "type": "object",
                    "properties": {"block_id": {"type": "string"}},
                    "required": ["block_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_section",
                "description": (
                    "Replace one existing section's HTML entirely, by its block_id. The new HTML "
                    "replaces that section only -- everything else on the page stays untouched."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "block_id": {"type": "string"},
                        "html": {"type": "string", "description": "The full replacement HTML for this section."},
                    },
                    "required": ["block_id", "html"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "add_section",
                "description": (
                    "Insert a brand new section that has no existing match on the page. "
                    "It is added at the end of the page, right before the closing body tag."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "html": {"type": "string", "description": "The full HTML for the new self-contained section."},
                    },
                    "required": ["html"],
                },
            },
        },
    ]


def _extract_known_risks(
    design_spec: dict[str, Any],
    critique_reports: list[dict[str, Any]],
    simulation_report: dict[str, Any],
    reflection_report: dict[str, Any],
) -> list[str]:
    """Pull the concrete concerns the LangGraph reasoning stage already flagged
    about the chosen design, so generation can address them instead of the
    LLM's earlier critique/simulation/reflection work going unused."""
    risks: list[str] = []

    chosen_candidate_id = design_spec.get("chosen_candidate_id", "")
    matching_critique = next(
        (c for c in critique_reports if c.get("candidate_id") == chosen_candidate_id),
        (critique_reports[0] if critique_reports else None),
    )
    if matching_critique:
        risks.extend(matching_critique.get("weaknesses", [])[:2])
        risks.extend(matching_critique.get("revision_instructions", [])[:2])

    risks.extend(simulation_report.get("systemic_issues", [])[:2])
    risks.extend(simulation_report.get("recommended_improvements", [])[:2])
    risks.extend(reflection_report.get("improvement_actions", [])[:2])

    seen: set[str] = set()
    deduped: list[str] = []
    for risk in risks:
        text = str(risk).strip()
        if text and text not in seen:
            seen.add(text)
            deduped.append(text)
    return deduped[:6]


class CodeGenerator:
    """Template + AI-assisted code generator"""

    def __init__(self, planner: Optional[ModelJsonPlanner] = None):
        self.planner = planner
        # Reason the most recent generate_html_with_llm() call failed, if it
        # did -- so a caller can tell the owner *why* generation failed
        # instead of silently substituting a generic fallback page.
        self.last_generation_error = ""

    SHAPE_TO_MOOD: dict[str, str] = {
        "storefront_commerce": "bold",
        "scheduled_booking": "trust",
        "inquiry_lead": "structured",
        "portfolio_showcase": "editorial",
        "catalog_reserve": "trust",
    }

    # Describes each mood in words for the free-form LLM brief (generate_html_with_llm).
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

    def _provision_custom_backend(
        self,
        business_id: str,
        business_name: str,
        vertical: str,
        menu_items: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Uses real tool-calling to let the model define and seed a bespoke
        data entity for businesses whose needs don't fit the fixed
        items/submissions schema (e.g. theatre showtimes with per-seat
        availability). Returns None if tool-calling isn't available or fails
        -- the caller falls back to a purely presentational seat picker with
        no real backend."""
        if not self.planner or not business_id:
            return None

        created: dict[str, Any] = {"entity_type": "", "entities": [], "tool_calls": 0}

        def tool_executor(name: str, args: dict[str, Any]) -> dict[str, Any]:
            created["tool_calls"] += 1
            if name == "create_entity_type":
                created["entity_type"] = str(args.get("name", "")).strip().lower().replace(" ", "_")
                return {"ok": True, "entity_type": created["entity_type"]}
            if name == "create_entity":
                entity_type = created["entity_type"] or "showtime"
                data = args.get("data") or {}
                entity = create_entity(business_id, entity_type, data)
                if entity:
                    created["entities"].append(entity)
                    return {"ok": True, "entity": entity}
                return {"ok": False, "error": "failed to create entity"}
            return {"error": f"unknown tool {name}"}

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "create_entity_type",
                    "description": "Register the name of the custom data entity this business needs (e.g. 'showtime').",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_entity",
                    "description": "Create one real instance of the entity (e.g. one showtime) with whatever fields make sense.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "data": {
                                "type": "object",
                                "description": (
                                    'The fields for this instance, e.g. {"movie": ..., "time": ..., '
                                    '"pricePerSeat": ..., "totalSeats": ...}'
                                ),
                            },
                        },
                        "required": ["data"],
                    },
                },
            },
        ]

        item_names = ", ".join(str(i.get("name", "")) for i in menu_items[:6] if i.get("name")) or "no specific items given"
        prompt = (
            f"You're setting up the real backend data for {business_name}, a {vertical} business that sells "
            f"tickets/seats to showings or events.\n"
            f"Real items/products already on file: {item_names}.\n"
            f"First call create_entity_type to name the kind of bookable thing this business has (e.g. 'showtime'). "
            f"Then call create_entity 2-4 times to create real example instances of it, using the real items above as "
            f"the basis (e.g. one showtime per real movie/item, with a sensible showtime and per-seat price). Each "
            f"instance's data should include enough fields for a booking page to work (name/title, a time or date if "
            f"relevant, price per seat, and total seat count -- keep seat counts realistic, e.g. 20-60, not thousands). "
            f"Stop once you've created a few real instances -- don't call any more tools after that."
        )

        try:
            self.planner.generate_with_tools(
                prompt, tools, tool_executor,
                max_new_tokens=400, temperature=0.4, max_iterations=8, timeout=60.0,
            )
        except Exception as exc:
            logger.warning("Custom backend provisioning failed, falling back to presentational seat picker: %s", exc)
            return None

        if not created["entity_type"] or not created["entities"]:
            return None
        logger.info(
            "Custom backend provisioned (%d tool call(s), entity_type=%s, %d entities, business_id=%s)",
            created["tool_calls"], created["entity_type"], len(created["entities"]), business_id,
        )
        return created

    def generate_admin_html_with_llm(
        self,
        build_spec: dict[str, Any],
        business_id: str,
    ) -> str:
        """Generates the owner-facing operational dashboard as its own real
        page, tailored to what this specific business actually has -- not
        the generic fixed Orders/Bookings/Leads/Menu template. Returns "" on
        any failure; the caller keeps the existing hand-coded generic panel
        as a permanent fallback (unlike the customer page, losing the
        ability to see/act on real submissions is worse than a generic
        layout, so this one is allowed to fail soft).

        Same fixed-contract principle as the customer page: the model
        decides layout/labels/actions freely, but the only things it's
        allowed to call are the real, already-existing, already-ownership-
        checked endpoints described below. No new endpoints, no ability for
        generated JS to touch anything outside this business_id.
        """
        if not self.planner or not business_id:
            return ""

        business = build_spec.get("business", {})
        name = business.get("name", "Our Business")
        vertical = business.get("vertical", "business")
        goal = business.get("goal", "")

        raw_workflows: list[Any] = (
            [f.get("key", "") for f in build_spec.get("includedFeatures", []) if f.get("key")]
            or _default_workflows_for_vertical(vertical, build_spec.get("businessShape", ""))
        )
        workflow_keys = {str(w).lower() for w in raw_workflows}
        has_commerce = bool(build_spec.get("menuItems")) or "online_ordering" in workflow_keys
        has_reserve = "catalog_reservation" in workflow_keys

        menu_items: list[dict] = build_spec.get("menuItems", [])[:5]

        # A real sample of this business's custom backend data, if any exists
        # (e.g. a theatre's showtimes) -- schemaless by design, so the model
        # can only build a sensible view of it by seeing a REAL instance,
        # never by guessing a shape.
        custom_entity_sample = ""
        try:
            from custom_entities_store import list_entities as _list_custom_entities
            for entity_type in {"showtime"}:  # extend as more entity types get provisioned
                entities = _list_custom_entities(business_id, entity_type)
                if entities:
                    custom_entity_sample = (
                        f'Entity type "{entity_type}", {len(entities)} real instance(s), example: '
                        f'{json.dumps(entities[0]["data"])}'
                    )
                    break
        except Exception:
            custom_entity_sample = ""

        endpoints_block = (
            f'- GET "/businesses/{business_id}/submissions" returns JSON shaped {{"submissions":[{{"id","type",'
            f'"customer","summary","contact","createdAt","status","source"}}, ...]}}. "type" is one of '
            f'"order"/"reservation"/"lead". "status" is one of "new"/"in_progress"/"completed"/"cancelled" -- '
            f'stick to exactly these 4 values, but pick whatever LABEL text makes sense to show for each, '
            f'fitting this specific business (e.g. a clinic booking might label "in_progress" as "Patient '
            f'Arrived"; a restaurant order might label it "Preparing").\n'
            f'- PATCH "/businesses/{business_id}/submissions/{{submissionId}}" with JSON body {{"status": '
            f'"<one of the 4 values above>"}} updates one record\'s status -- wire this to whatever status '
            f'controls you design.\n'
        )
        if custom_entity_sample:
            endpoints_block += (
                f'- GET "/businesses/{business_id}/entities/showtime" returns {{"entities":[{{"id","entityType",'
                f'"data"}}, ...]}}. Example entity: {custom_entity_sample}\n'
                f'- GET "/businesses/{business_id}/entities/showtime/{{entityId}}/claims" returns '
                f'{{"claimedResourceKeys":[...]}} -- which specific resources (e.g. seats) are taken for one entity.\n'
            )
        if has_commerce or has_reserve:
            endpoints_block += (
                f'- GET "/businesses/{business_id}/items" returns {{"items":[{{"id","name","category",'
                f'"description","priceLabel","priceSortValue","imageUrl"}}, ...]}}\n'
                f'- PUT "/businesses/{business_id}/items" with JSON body {{"items":[...]}} (same shape) replaces '
                f'the whole list -- wire this to an add/edit/remove item UI.\n'
            )

        item_lines = "\n".join(f'  - {i.get("name","")} - {i.get("priceLabel","")}' for i in menu_items)

        prompt = f"""You are building one page of our own website-builder platform: the back-office admin
screen for a business that already has a live site on our platform, {name} (a {vertical} business, goal:
{goal or 'no stated goal'}). This platform already runs a backend that stores this business's orders,
bookings, and leads -- the endpoints below are that same backend, part of the same application as the page
you're writing, not a third-party or external system. Every fetch() call you write is a same-origin relative
URL (never prefix any of them with a domain) -- exactly like any normal single-page admin panel calling its
own platform's own API for one seller/tenant's own data, the same pattern e-commerce and booking platforms
use for their seller dashboards every day. These endpoints are live and already responding right now -- the
fetch() calls below will succeed when this page loads in a browser, the same as they already do on this
business's live customer-facing site today.

Build a page that covers exactly what this business actually has -- skip any section for something not
described below (e.g. no items section if none are listed).

Note on the data involved: every submission is just basic contact-request metadata the visitor typed into a
web form themselves (a name, a phone number, a one-line reason for the request, a status label) -- the same
kind of record a Calendly/Squarespace/Shopify seller dashboard shows. It is never clinical, diagnostic, or
otherwise regulated record content, regardless of what vertical the business is in.

═══ THIS BUSINESS'S DATA ═══
Workflows in use: {sorted(workflow_keys) or ["lead"]}
{f"Items on file:{chr(10)}{item_lines}" if item_lines else "No catalog/menu items -- skip an items section."}
{f"Custom data on file: {custom_entity_sample}" if custom_entity_sample else ""}

═══ THIS PLATFORM'S OWN DATA ENDPOINTS FOR THIS BUSINESS ═══
{endpoints_block}

═══ REQUIREMENTS ═══
- Fetch real data on load; never invent example records.
- For each submission type this business actually has, show the list with the business-appropriate status
  labels and let the owner change status via the PATCH call.
- If a custom entity sample was given, show a real view of it (and its claims, if relevant) -- your call on
  the exact layout, but it must reflect the real fields shown above, not invented ones.
- If items were given, let the owner see and edit them via the GET/PUT items endpoints.
- Keep it functional and clean -- this is a working tool, not a marketing page. No fake data, no filler
  copy about the business itself.
- Every interactive control must actually work -- no dead buttons.

═══ OUTPUT FORMAT ═══
Output ONLY raw HTML starting with <!DOCTYPE html>, with your own <style> and <script> inline. No markdown,
no code fences, no explanation before or after."""

        best_model = self.planner.best_model_name()
        reasoning_effort = self.planner.best_model_reasoning_effort()
        # Observed non-deterministic false-positive safety refusals on this
        # prompt shape (a model occasionally reads "real fetch() calls to a
        # UUID-scoped endpoint" as an unauthorized-access request, even
        # though it's this same app's own backend) -- the same prompt
        # succeeds on a retry often enough that one extra attempt is worth
        # it before falling back to the hand-coded panel.
        for attempt in range(2):
            try:
                html = self.planner.generate_text(
                    prompt, max_new_tokens=8000, temperature=0.5, model=best_model, timeout=120.0,
                    reasoning_effort=reasoning_effort,
                )
                html = html.strip()
                if html.startswith("```"):
                    lines = html.split("\n")
                    end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
                    html = "\n".join(lines[1:end])
                start = html.find("<!DOCTYPE html>")
                if start == -1:
                    start = html.find("<html")
                if start == -1:
                    logger.warning(
                        "Admin dashboard generation attempt %d returned no valid HTML root (business_id=%s)",
                        attempt + 1, business_id,
                    )
                    continue
                html = html[start:]
                logger.info(
                    "Admin dashboard generation succeeded on attempt %d (%d chars, business_id=%s)",
                    attempt + 1, len(html), business_id,
                )
                return html
            except Exception as exc:
                logger.warning("Admin dashboard generation attempt %d failed: %s", attempt + 1, exc)
        logger.warning("Admin dashboard generation exhausted retries, keeping fallback panel (business_id=%s)", business_id)
        return ""

    def generate_html_with_llm(
        self,
        build_spec: dict[str, Any],
        agent_context: dict[str, Any] | None = None,
        revision_request: str = "",
        current_html: str = "",
    ) -> str:
        """Use LLM to generate a complete HTML site driven by agent-identified workflows.

        When revision_request is set, this is a targeted fix/change to an
        already-live page (current_html) rather than a from-scratch build --
        the prompt tells the model what already exists and what specifically
        to change, instead of designing a page from zero every time.
        """
        self.last_generation_error = ""
        if not self.planner:
            self.last_generation_error = "No AI model is currently configured on the server."
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
        business_id = business.get("id", "")
        ctx = agent_context or {}
        requirements_spec = ctx.get("requirements_spec") or {}
        design_spec = ctx.get("design_spec") or {}
        visual_system = design_spec.get("visual_system") or {}
        reasoning_notes = ctx.get("reasoning_notes") or []
        retrieved_memories = ctx.get("retrieved_memories") or []
        human_answers = ctx.get("human_answers") or {}
        research_results = ctx.get("research_results") or {}
        known_risks = _extract_known_risks(
            design_spec,
            ctx.get("critique_reports") or [],
            ctx.get("simulation_report") or {},
            ctx.get("reflection_report") or {},
        )
        planned_content_areas: list[str] = [
            str(p) for p in (requirements_spec.get("required_pages") or []) if str(p).strip()
        ]
        compliance_requirements: list[str] = requirements_spec.get("compliance_requirements") or []
        conversion_priorities: list[str] = requirements_spec.get("conversion_priorities") or []
        primary_action = design_spec.get("primary_action") or {}
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
        commerce_key, commerce = commerce_copy(build_spec.get("businessShape", ""), vertical, business.get("subtype", ""), goal, usp)
        # A theatre/cinema isn't "browse many independent products, add
        # several to a cart" -- it's "pick one showing, then pick specific
        # seats for that one showing." Treating it like generic e-commerce
        # (which is all that happened before this flag existed) is why a
        # movie ticket flow came out looking like a t-shirt store.
        needs_seat_selection = needs_cart and commerce_key == "ticketed_event"
        custom_backend = (
            self._provision_custom_backend(business_id, name, vertical, menu_items)
            if needs_seat_selection and business_id else None
        )
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
            title = wf_key.replace("_", " ").title()
            is_reservation = any(k in wf_key or wf_key in k for k in self._RESERVATION_GUIDE_KEYS)
            canonical_type = "reservation" if is_reservation else "lead"
            workflow_specs.append({"title": title, "type": canonical_type})

        wf_lines = [
            f'- "{ws["title"]}" — decide which fields visitors need to submit for this specific request type on '
            f'this {vertical} business (not a generic name/phone/email form) — think about what information you\'d '
            f'actually need to act on it. Write intro copy specific to this business explaining why they would use '
            f'it. On submit, fire the integration hook below with type="{ws["type"]}", then show a friendly '
            f'confirmation in place of the form.'
            for ws in workflow_specs
        ]
        wf_block = ("\n" + "\n".join(wf_lines)) if wf_lines else ""

        empty_catalog_guidance = (
            f'If the fetch fails, or succeeds but returns zero items (a brand-new business the owner '
            f'hasn\'t added anything to yet -- this is the normal starting state, not an error), do NOT '
            f'invent specific products, brand names, model numbers, or prices to fill the space -- that '
            f'would show visitors fake inventory that was never confirmed by the business. Instead render '
            f'a clean, on-brand empty state in the same layout: a short friendly message (e.g. "New arrivals '
            f'are on their way -- check back soon") and/or a couple of muted, clearly-generic placeholder '
            f'cards. It must be obvious this is a placeholder, not real inventory. As soon as the owner adds '
            f'real items from their dashboard, this same fetch will return them and they replace the '
            f'placeholder automatically.\n'
        )
        items_block = ""
        if needs_cart:
            item_lines = "\n".join(
                f'  - {item.get("name", "Item")} — {currency_sym}{item.get("priceSortValue", 0)}'
                for item in menu_items[:20]
            )
            if needs_seat_selection:
                if custom_backend:
                    entity_type = custom_backend["entity_type"]
                    showtime_lines = "\n".join(
                        f'  - id "{e["id"]}": {json.dumps(e["data"])}'
                        for e in custom_backend["entities"][:20]
                    )
                    items_block = (
                        f'\n═══ WORKFLOW: BROWSE SHOWINGS, PICK SEATS, CHECKOUT (real backend) ═══\n'
                        f'This is a ticketed/seated event business (movie showtimes, concert, screening, etc.) -- '
                        f'do NOT build a generic "add to cart" product list. A real backend has already been '
                        f'provisioned for this: fetch the live list of showings from this relative URL (same-origin, '
                        f'plain GET, no auth needed): "/businesses/{business_id}/entities/{entity_type}". It responds '
                        f'{{"entities":[{{"id","entityType","data": {{...fields you see below...}}}}, ...]}}. Example '
                        f'entities currently live:\n{showtime_lines}\n'
                        f'Build the real flow: (1) visitor picks a showing/event from the fetched list, (2) fetch '
                        f'"/businesses/{business_id}/entities/{entity_type}/{{id}}/claims" (GET) for that showing\'s id '
                        f'to see which seat keys are already taken ({{"claimedResourceKeys":[...]}}), and render a '
                        f'visual grid of individually clickable seats (rows x columns) with taken seats disabled, '
                        f'(3) when the visitor picks one or more free seats and checks out, POST to '
                        f'"/businesses/{business_id}/claim" with JSON body {{"entityType":"{entity_type}","entityId":'
                        f'"<the showing\'s id>","resourceKey":"<a seat label like \'Row C Seat 4\'>"}} once per seat '
                        f'chosen. A 200 response means that seat is now really claimed for them; a 409 response means '
                        f'someone else grabbed that exact seat first -- if you get a 409, tell the visitor that seat '
                        f'was just taken and let them pick a different one (refetch claims to update the grid), do '
                        f'not treat it as a generic error. This is real shared inventory, not a presentational mockup '
                        f'-- two visitors genuinely cannot both end up with the same seat.\n'
                    )
                else:
                    items_block = (
                        f'\n═══ WORKFLOW: BROWSE SHOWINGS, PICK SEATS, CHECKOUT ═══\n'
                        f'This is a ticketed/seated event business (movie showtimes, concert, screening, etc.) -- '
                        f'do NOT build a generic "add to cart" product list. Each item below is one showing/event; the '
                        f'"priceLabel" is the per-seat/per-ticket price. Build the real flow: (1) visitor picks a '
                        f'showing/event from the list, (2) that reveals a seat picker -- a visual grid of individually '
                        f'clickable seats (e.g. rows x columns of seat buttons) they select one or more of, with a '
                        f'running total priced per seat selected, (3) checkout confirms the showing, the specific '
                        f'seats chosen (e.g. "Row C, Seats 4-5"), and the total. Design the seat grid, layout, and '
                        f'checkout step yourself -- it just has to be real seat-by-seat selection, not a quantity '
                        f'stepper. Note: this seat grid is a presentational UI for a good booking experience, not a '
                        f'live shared inventory -- there is no backend tracking of which specific seats other visitors '
                        f'already chose, so do not claim seats are "sold out" from real data you don\'t have.\n'
                    )
            else:
                items_block = (
                    f'\n═══ WORKFLOW: BROWSE & BUY ═══\n'
                    f'{commerce["items_subtext"]} Let visitors browse items, add any of them to a '
                    f'running cart, see a live count/total, and check out. Design the browsing layout, the cart UI '
                    f'(drawer, sidebar, floating bar — your call) and the checkout step yourself; write a short, '
                    f'item-specific description for each card rather than a generic phrase like "Freshly prepared X".\n'
                )
            if business_id and not custom_backend:
                items_block += (
                    f'On page load, fetch the current item list from this relative URL (same-origin, plain '
                    f'GET, no auth needed — do not prefix it with a domain): "/businesses/{business_id}/items". '
                    f'It responds with JSON shaped {{"items":[{{"id","name","category","description",'
                    f'"priceLabel","priceSortValue","imageUrl"}}, ...]}}. Render whatever this call returns — the owner '
                    f'can add, edit, or remove items, change prices, and upload a real photo at any time from '
                    f'their own dashboard, so the page must always reflect the live result of this fetch, never '
                    f'a fixed list baked in at build time. Each item\'s "id" is an opaque string that can '
                    f'contain spaces, slashes, or punctuation — never splice it unquoted into an inline HTML '
                    f'attribute (e.g. onclick="addToCart(${{item.id}})" breaks the moment an id isn\'t a plain '
                    f'number); store it in a data-id attribute and read it back via .dataset in an event '
                    f'listener, or JSON-escape it properly if you do build the handler as a string.\n'
                    f'"imageUrl" is a relative path (e.g. "/uploads/...") when the owner has uploaded a real '
                    f'photo for that item — use <img src="that exact value"> as-is (it\'s already a working URL, '
                    f'don\'t rewrite or prefix it). Only when imageUrl is empty/missing should you fall back to '
                    f'a generic, clearly-neutral placeholder graphic (a flat color block, icon, or pattern) — '
                    f'never a stock photo standing in for a specific real product, since it has no photo yet.\n'
                    f'{empty_catalog_guidance}'
                )
                if item_lines:
                    items_block += f'Real items to feature right now:\n{item_lines}\n'
            elif not custom_backend:
                items_block += (
                    f'Real items to feature (use these exact names and prices, do not invent different ones):\n'
                    f'{item_lines}\n' if item_lines else
                    f'No items were provided -- build a clean empty-state placeholder instead of inventing products.\n'
                )
            items_block += (
                f'When checkout completes, fire the integration hook below with type="order", summary listing '
                f'what was ordered, and the formatted total.'
            )
        elif needs_reserve:
            item_lines = "\n".join(
                f'  - {item.get("name", "Item")}'
                for item in menu_items[:20]
            )
            items_block = (
                f'\n═══ WORKFLOW: BROWSE & RESERVE ═══\n'
                f'{commerce["items_subtext"]} Let visitors browse catalog items and place a '
                f'one-click hold on any of them — this is a reservation, not a purchase, so there is no price, '
                f'cart, or checkout step. Design the catalog layout and reserve interaction yourself.\n'
            )
            if business_id:
                items_block += (
                    f'On page load, fetch the current item list from this relative URL (same-origin, plain '
                    f'GET, no auth needed — do not prefix it with a domain): "/businesses/{business_id}/items". '
                    f'It responds with JSON shaped {{"items":[{{"id","name","category","description","imageUrl"}}, ...]}} '
                    f'(ignore any price fields — these are catalog holds, not purchases). Render whatever this '
                    f'call returns — the owner can add, edit, or remove items and upload a real photo at any '
                    f'time from their own dashboard, so the page must always reflect the live result '
                    f'of this fetch, never a fixed list baked in at build time. Each item\'s "id" is an opaque '
                    f'string that can contain spaces, slashes, or punctuation — never splice it unquoted into '
                    f'an inline HTML attribute (e.g. onclick="reserveItem(${{item.id}})" breaks the moment an '
                    f'id isn\'t a plain number); store it in a data-id attribute and read it back via .dataset '
                    f'in an event listener, or JSON-escape it properly if you do build the handler as a string.\n'
                    f'"imageUrl" is a relative path (e.g. "/uploads/...") when the owner has uploaded a real '
                    f'photo for that item — use <img src="that exact value"> as-is. Only when imageUrl is '
                    f'empty/missing should you fall back to a generic, clearly-neutral placeholder graphic (a '
                    f'flat color block, icon, or pattern) — never a stock photo standing in for a specific real '
                    f'item, since it has no photo yet.\n'
                    f'{empty_catalog_guidance}'
                )
                if item_lines:
                    items_block += f'Real items to feature right now:\n{item_lines}\n'
            else:
                items_block += (
                    f'Real items to feature:\n{item_lines}\n' if item_lines else
                    f'No items were provided -- build a clean empty-state placeholder instead of inventing products.\n'
                )
            items_block += (
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
        if known_risks:
            extras += "\nKNOWN RISKS (an earlier automated review of this plan flagged these -- make sure the page you write actually addresses them):\n" + "\n".join(f"  - {r}" for r in known_risks)
        if planned_content_areas:
            extras += (
                "\nPLANNED CONTENT AREAS (an earlier planning pass identified these as the content this "
                "business needs -- treat them as a checklist to cover somewhere on the page, in whatever "
                "structure/section layout you think best, not a literal list of separate pages): "
                + ", ".join(planned_content_areas)
            )
        if conversion_priorities:
            extras += (
                "\nCONVERSION PRIORITIES (shape the primary action/CTA flow around these):\n"
                + "\n".join(f"  - {c}" for c in conversion_priorities[:4])
            )
        if primary_action.get("label"):
            extras += (
                f"\nPLANNED PRIMARY ACTION: theme the main call-to-action around "
                f"\"{primary_action.get('label')}\" (a {primary_action.get('kind', 'lead')}-type action)."
            )
        if menu_sample:
            extras += f"\nMENU ITEMS (show as visual cards in a dedicated menu section between hero and workflows): {menu_sample}"
        if human_answers:
            extras += f"\nHUMAN CLARIFICATIONS (must be reflected in the page): {human_answers}"

        compliance_block = ""
        if compliance_requirements:
            compliance_block = (
                "\n═══ COMPLIANCE GUARDRAILS ═══\n"
                "This business was flagged as needing extra care -- never include any of the following in "
                "the copy, no matter how natural it might otherwise feel to write:\n"
                + "\n".join(f"- {c}" for c in compliance_requirements)
                + "\n"
            )

        competitor = research_results.get("competitor_analysis") or {}
        local_seo = research_results.get("local_seo") or {}
        menu_research = research_results.get("menu_extraction") or {}
        # Split by whether the source actually used real web_search/read_page data
        # (competitor/local_seo research_agents.py can decide to skip the tools and
        # just brainstorm) -- only genuinely grounded findings get labeled as real
        # research; everything else is framed honestly as unverified ideas, so the
        # generation model doesn't state fabricated specifics as fact.
        grounded_lines: list[str] = []
        speculative_lines: list[str] = []

        competitor_bucket = grounded_lines if competitor.get("grounded") else speculative_lines
        if competitor.get("market_gaps"):
            competitor_bucket.append("Market gaps to exploit in the hero/positioning copy: " + "; ".join(competitor["market_gaps"][:3]))
        if competitor.get("differentiation_opportunities"):
            competitor_bucket.append("Differentiation angles to emphasize: " + "; ".join(competitor["differentiation_opportunities"][:3]))
        if competitor.get("competitor_weaknesses"):
            competitor_bucket.append("Competitor weaknesses this business should visibly do better on: " + "; ".join(competitor["competitor_weaknesses"][:3]))

        local_seo_bucket = grounded_lines if local_seo.get("grounded") else speculative_lines
        if local_seo.get("target_keywords"):
            local_seo_bucket.append("Work these SEO keywords naturally into headings/copy: " + ", ".join(local_seo["target_keywords"][:6]))
        if local_seo.get("local_search_terms"):
            local_seo_bucket.append("Local search terms to reflect in copy: " + ", ".join(local_seo["local_search_terms"][:4]))

        # Menu/service extraction is always grounded in the business's own uploaded assets.
        if menu_research.get("business_highlights"):
            grounded_lines.append("Highlights to call out: " + "; ".join(menu_research["business_highlights"][:3]))
        if menu_research.get("special_offers"):
            grounded_lines.append("Special offers to feature: " + "; ".join(menu_research["special_offers"][:2]))

        if grounded_lines:
            extras += "\nRESEARCH FINDINGS (real data from web search/page reads or this business's own uploaded assets — the copy should reflect it):\n" + "\n".join(f"  - {line}" for line in grounded_lines)
        if speculative_lines:
            extras += "\nSTRATEGIC IDEAS (brainstormed positioning angles, NOT verified facts about real competitors — use for tone/direction only, never state as specific claims about named competitors):\n" + "\n".join(f"  - {line}" for line in speculative_lines)

        shape = build_spec.get("businessShape", "")
        mood = self.SHAPE_TO_MOOD.get(shape, "bold")
        mood_desc = self.MOOD_TONE_DESCRIPTIONS.get(mood, "")

        if business_id:
            integration_block = (
                'This page is a real, standalone website a customer can visit directly — it is not just a '
                'preview inside something else. Whenever a visitor completes one of the actions above (places '
                'an order, reserves an item, submits a form), your JavaScript must report it to the business\'s '
                'own backend with a same-origin fetch call (a relative URL — never prefix it with a domain):\n'
                f'    fetch("/businesses/{business_id}/submissions", {{\n'
                '      method: "POST",\n'
                '      headers: {"Content-Type": "application/json"},\n'
                '      body: JSON.stringify({type:"order"|"reservation"|"lead", summary:"<short human-readable '
                'summary of what they did/ordered/requested>", customer:"<their name if collected, else empty '
                'string>", contact:"<their phone or email if collected, else empty string>"})\n'
                '    })\n'
                'Use the exact type given for each action above (specified next to each workflow). Beyond '
                'making this one call at the right moment, how you build the UI/JS to get there is entirely '
                'your choice — no prescribed markup, function names, or class names to follow.'
            )
        else:
            integration_block = (
                'Whenever a visitor completes one of the actions above (places an order, reserves an item, '
                'submits a form), your JavaScript must call:\n'
                '    window.parent.postMessage({type:"order"|"reservation"|"lead", summary:"<short '
                'human-readable summary of what they did/ordered/requested>", customer:"<their name if '
                'collected, else empty string>", contact:"<their phone or email if collected, else empty '
                'string>"}, "*")\n'
                'Use the exact type given for each action above (specified next to each workflow).'
            )

        revision_block = ""
        if revision_request and current_html:
            revision_block = f"""
═══ THIS IS A REVISION OF AN ALREADY-LIVE PAGE, NOT A FRESH BUILD ═══
This business already has a live page (shown in full below) and its owner has asked for this specific change:
"{revision_request}"

Produce a complete, revised version of the ENTIRE page that addresses this request. Preserve everything that
already works well — do not redesign, restyle, or rewrite parts the owner didn't ask you to change. Still
follow every rule above (creative freedom elsewhere, the integration requirement, output format).

Current live page:
{current_html}
"""

        prompt = f"""You are a senior web designer/engineer building a single-file HTML website for a real business.

The result must look and feel like a premium,aesthetic, bespoke, modern website — the kind a top design studio, or a
flagship AI model asked directly to "design me a beautiful, authentic website for my business", would produce.
It must NOT look like a generic template, a spec sheet, or an admin form. That bar applies here regardless of
how ordinary this business type sounds — an "ordinary" business still deserves a genuinely well-designed site.

═══ BUSINESS ═══
Name: {name} | Type: {vertical} | Location: {location}
Goal: {goal}
USP: {usp}
Hours: {hours} | Phone: {phone}
{extras}

═══ FACTS ONLY — NO INVENTED STATISTICS ═══
Only state facts given above (or in the research/human-clarification notes if present). Never invent specific
numbers, dates, or names that weren't provided — no fabricated ratings (e.g. "4.98 stars"), customer/follower
counts (e.g. "12,400+ members"), founding years (e.g. "Since 2018"), or brand/product names the business never
mentioned. If you want to convey trust or popularity, use honest qualitative language instead ("a neighborhood
favorite", "loved by regulars") rather than making up a statistic to back it.
{compliance_block}
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
{integration_block}
{revision_block}
═══ OUTPUT FORMAT ═══
- Output ONLY raw HTML starting with <!DOCTYPE html>, with your own <style> and <script> inline. No markdown,
  no code fences, no explanation before or after.
- Every interactive control must actually do something — no href="#" or dead buttons.
- Write only customer-facing website copy. Never mention BuildSpec, agents, planner reasoning, backend modules,
  implementation details, or phrases like "included because"."""

        try:
            best_model = self.planner.best_model_name()
            reasoning_effort = self.planner.best_model_reasoning_effort()
            html = self.planner.generate_text(
                prompt, max_new_tokens=16000, temperature=0.6, model=best_model, timeout=180.0,
                reasoning_effort=reasoning_effort,
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
                html = _inject_catalog_empty_state_guard(html, business_id)
                logger.info("LLM HTML generation succeeded (%d chars)", len(html))
                return html
            self.last_generation_error = "The AI model's response didn't contain a valid HTML page."
            logger.warning("LLM returned output without valid HTML root; falling back")
            return ""
        except Exception as exc:
            self.last_generation_error = f"The AI model request failed: {exc}"
            logger.warning("LLM HTML generation failed: %s", exc)
            return ""

    def revise_html_with_targeted_edit(
        self,
        build_spec: dict[str, Any],
        current_html: str,
        revision_request: str,
    ) -> str:
        """Attempt a revision via real tool-calling: the model gets
        list_sections/read_section to look around the already-live page and
        write_section/add_section to make the actual edit, deciding for
        itself how many sections to inspect and change -- instead of the
        old fixed two-call pipeline (pick blocks, then blind-write them).
        Cheaper and safer than a full rewrite since untouched sections are
        never sent to or regenerated by the model at all. Returns "" if
        anything doesn't pan out (parsing failed, tool-calling unsupported/
        failed, no edits were ever made), so the caller falls back to the
        existing full-page rewrite path -- this never has to be the only
        way a revision works.
        """
        if not self.planner or not current_html or not revision_request:
            return ""
        blocks = _parse_top_level_body_blocks(current_html)
        # Too few blocks (parsing likely failed to find real structure) or
        # implausibly many (probably mis-parsed some inline markup as
        # top-level) -- not confident enough to attempt a targeted splice.
        if not (1 <= len(blocks) <= 40):
            return ""

        business_name = build_spec.get("business", {}).get("name", "this business")
        # Tracks each block's CURRENT html (not the frozen original) so that
        # read_section reflects the tool's own prior writes, and a block can
        # be written to more than once in the same session -- matching
        # against the frozen original would make a second write_section
        # call on an already-edited block fail with "no longer present".
        live_html = {b["block_id"]: b["html"] for b in blocks}
        working = {"html": current_html, "edited": False, "tool_calls": 0}

        def tool_executor(name: str, args: dict[str, Any]) -> dict[str, Any]:
            working["tool_calls"] += 1
            if name == "list_sections":
                return {
                    "sections": [
                        {"block_id": b["block_id"], "tag": b["tag"], "preview": b["preview"]}
                        for b in blocks
                    ]
                }
            if name == "read_section":
                block_id = str(args.get("block_id", ""))
                if block_id not in live_html:
                    return {"error": "unknown block_id"}
                return {"block_id": block_id, "html": live_html[block_id]}
            if name == "write_section":
                block_id = str(args.get("block_id", ""))
                new_html = str(args.get("html", "")).strip()
                current_block_html = live_html.get(block_id)
                if current_block_html is None or not new_html:
                    return {"ok": False, "error": "unknown block_id or empty html"}
                if current_block_html not in working["html"]:
                    return {"ok": False, "error": "this section is no longer present on the page"}
                working["html"] = working["html"].replace(current_block_html, new_html, 1)
                live_html[block_id] = new_html
                working["edited"] = True
                return {"ok": True}
            if name == "add_section":
                new_html = str(args.get("html", "")).strip()
                if not new_html or "</body>" not in working["html"]:
                    return {"ok": False, "error": "no html provided, or no closing body tag to insert before"}
                working["html"] = working["html"].replace("</body>", f"{new_html}\n</body>", 1)
                working["edited"] = True
                return {"ok": True}
            return {"error": f"unknown tool {name}"}

        prompt = (
            f"You are making a small, targeted edit to {business_name}'s live website, not rewriting it.\n"
            f'The owner asked: "{revision_request}"\n\n'
            "Use list_sections to see what's on the page, read_section on any you need the full current content "
            "of before changing, then write_section to replace an existing section that needs to change, or "
            "add_section if the request needs something genuinely new that no existing section covers. Make as "
            "many calls as you actually need -- read a section before rewriting it if you're not already sure "
            "what it contains. Stop calling tools once the edit is done.\n\n"
            "IMPORTANT constraint on this page's own backend calls: any fetch() on this page that POSTs to "
            '"/businesses/<id>/submissions" sends a JSON body with a `type` field, and the backend only accepts '
            'exactly one of these three literal values: "order" (a purchase/checkout), "reservation" (booking a '
            'specific slot/table/appointment/seat), or "lead" (a general enquiry/contact/intake with no specific '
            "slot). Any other value (e.g. \"appointment\", \"booking\", \"intake\") is silently rejected by the "
            "backend -- the submission is lost even though the page shows a success message. If fixing this "
            "request involves changing what a form submits, only ever use one of those three exact values, "
            "picking whichever one actually matches what the visitor is doing -- never invent a new one."
        )

        try:
            self.planner.generate_with_tools(
                prompt, _revision_tool_schemas(), tool_executor,
                max_new_tokens=4000, temperature=0.4, max_iterations=8, timeout=90.0,
            )
        except Exception as exc:
            logger.warning("Tool-calling revision failed: %s", exc)
            return ""

        if not working["edited"]:
            return ""
        logger.info(
            "Tool-calling revision applied (%d tool call(s), business_id=%s)",
            working["tool_calls"], build_spec.get("business", {}).get("id", ""),
        )
        return working["html"]

    def _run_post_generation_smoke_tests(
        self,
        html: str,
        build_spec: dict[str, Any],
        business_id: str,
        site_slug: str,
        needs_reserve: bool,
    ) -> str:
        """Tier 1 (deterministic, free) then Tier 2 (LLM-driven QA agent,
        opt-in real cost) against the real live page -- see
        browser_smoke_test.py for what each actually checks. Auto-repairs
        once via the existing tool-calling revision path on either tier's
        failure, then ships regardless of the second outcome -- this can
        only ever leave a generation unchanged or make it better, never
        worse, matching every other layered fallback in this codebase.
        """
        if not _smoke_test_tier1_enabled():
            return html

        import browser_smoke_test

        base_url = os.getenv("SMOKE_TEST_BASE_URL", "http://127.0.0.1:8000")
        business_name = build_spec.get("business", {}).get("name", "this business")

        tier1 = browser_smoke_test.run_reachability_check(base_url, site_slug)
        if not tier1["passed"]:
            logger.warning(
                "Smoke test Tier 1 failed for business_id=%s: %s", business_id, tier1["reason"]
            )
            repaired = self.revise_html_with_targeted_edit(
                build_spec, html,
                f"Automated testing found: {tier1['reason']}. Fix this so the checkout/confirm "
                f"step is fully visible and clickable, without changing anything else.",
            )
            if repaired:
                from menu_store import update_business_preview
                update_business_preview(business_id, repaired)
                html = repaired
                tier1 = browser_smoke_test.run_reachability_check(base_url, site_slug)
                logger.info(
                    "Smoke test Tier 1 after repair (business_id=%s): %s",
                    business_id, "passed" if tier1["passed"] else "still failing",
                )

        if tier1["passed"] and _smoke_test_tier2_enabled() and self.planner:
            workflow = (
                "reserve an item" if needs_reserve
                else "browse items, add one or more to the cart, and complete checkout"
            )
            tier2 = browser_smoke_test.run_qa_agent_test(
                base_url, site_slug, business_id, self.planner,
                f"As a real customer of {business_name}, {workflow}.",
            )
            if tier2.get("issues") or not tier2.get("completed"):
                issues_text = "; ".join(tier2.get("issues", [])) or tier2.get(
                    "notes", "the agent could not complete the workflow"
                )
                logger.warning(
                    "Smoke test Tier 2 found issues for business_id=%s: %s", business_id, issues_text
                )
                repaired = self.revise_html_with_targeted_edit(
                    build_spec, html,
                    f"Automated real-user testing found: {issues_text}. Fix these issues without "
                    f"changing anything else.",
                )
                if repaired:
                    from menu_store import update_business_preview
                    update_business_preview(business_id, repaired)
                    html = repaired

        return html

    def generate_code(
        self,
        build_spec: dict[str, Any],
        agent_context: dict[str, Any] | None = None,
    ) -> GeneratedCode:
        """Generate website code from BuildSpec, using LLM when available."""
        business_id = build_spec.get("business", {}).get("id") or ""
        site_slug = ""
        if business_id:
            # First generation for this business seeds the DB from the
            # parsed/extracted menuItems; a later regeneration is a no-op on
            # the seed and always reads back whatever the owner currently has
            # live (including edits/deletions made via the menu CMS since the
            # last generation) instead of the stale data captured this time.
            from menu_store import seed_if_new, list_items as _list_menu_items, ensure_business
            seed_if_new(business_id, build_spec.get("menuItems", []))
            build_spec = {**build_spec, "menuItems": _list_menu_items(business_id)}
            owner_id = (agent_context or {}).get("owner_id")
            business_record = ensure_business(
                business_id, build_spec.get("business", {}).get("name", "Business"), owner_id
            )
            site_slug = business_record["slug"] if business_record else ""

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
        if html_preview:
            self._persist_raw_llm_output(html_preview, business.get("name", "business"))
        # These two checks are advisory only, not gates: the model now writes
        # its own free-form JS/copy, so string-matching for an exact contract
        # phrase or verbatim clarification text is inherently unreliable (it
        # can legitimately express the same thing via a variable, template
        # literal, or paraphrase) and was previously discarding real,
        # successfully-generated pages in favor of the generic deterministic
        # template on false negatives. A missing postMessage hook or an
        # unreflected clarification is a much smaller problem than throwing
        # away a whole working, bespoke page, so we only log a warning here.
        if html_preview and not self._html_has_working_commerce_ui(html_preview, needs_cart, needs_reserve, business_id):
            logger.warning(
                "LLM preview may be missing the submissions integration hook "
                "(dashboard might not receive this order/reservation) "
                "-- keeping the generated page anyway"
            )
        if html_preview and not self._html_reflects_human_clarifications(
            html_preview,
            business.get("human_answers") or {},
        ):
            logger.warning(
                "LLM preview may not explicitly restate a human clarification "
                "answer -- keeping the generated page anyway"
            )
        # A blank/broken LLM call is not something a generic deterministic
        # template can meaningfully paper over -- it looks nothing like the
        # actual business, and silently showing it as if generation
        # succeeded just hides a real failure from the owner. No fallback
        # website is generated here; generation_failed + generation_error
        # tell the caller exactly what to show instead (a retriable failure
        # with a real reason, not a fake success).
        generation_failed = not html_preview
        generation_error = self.last_generation_error if generation_failed else ""
        if generation_failed:
            logger.warning(
                "LLM generation failed for business_id=%s: %s", business_id, generation_error
            )

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
            "siteSlug": site_slug,
        }

        if business_id and site_slug and not generation_failed:
            from menu_store import update_business_build_spec, update_business_preview
            # Only touch the live site on a real success -- a failed attempt
            # leaves whatever was already live (or nothing, for a business's
            # first-ever attempt) completely untouched.
            update_business_preview(business_id, html_preview)
            # Persisted so a later "request a fix" revision has the same
            # business context this generation used, not just the raw HTML.
            update_business_build_spec(business_id, build_spec)

            if needs_cart or needs_reserve:
                html_preview = self._run_post_generation_smoke_tests(
                    html_preview, build_spec, business_id, site_slug, needs_reserve
                )

            # Best-effort: on failure this just leaves admin_html_preview
            # empty and the frontend keeps showing the hand-coded generic
            # panel -- never blocks or degrades the customer-facing result.
            from menu_store import update_business_admin_preview
            admin_html = self.generate_admin_html_with_llm(build_spec, business_id)
            if admin_html:
                update_business_admin_preview(business_id, admin_html)

        return GeneratedCode(
            pages=pages,
            components=components,
            styles=styles,
            config=config,
            html_preview=html_preview,
            generation_failed=generation_failed,
            generation_error=generation_error,
        )

    @staticmethod
    def _persist_raw_llm_output(html: str, business_name: str) -> None:
        # Written BEFORE the advisory gate checks below run, so a raw copy of
        # every real LLM generation survives on disk regardless of what those
        # checks decide -- lets us recover/inspect a specific generation even
        # if a future gate (or a bug in one) produces a false negative.
        try:
            import datetime
            import re as _re

            out_dir = Path(__file__).parent / "generated_previews"
            out_dir.mkdir(exist_ok=True)

            slug = _re.sub(r"[^a-z0-9]+", "-", business_name.lower()).strip("-") or "business"
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            (out_dir / f"{timestamp}_{slug}.html").write_text(html, encoding="utf-8")
            (out_dir / "latest.html").write_text(html, encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to persist raw LLM HTML output: %s", exc)

    @staticmethod
    def _html_has_working_commerce_ui(html: str, needs_cart: bool, needs_reserve: bool, business_id: str = "") -> bool:
        # generate_html_with_llm's prompt no longer prescribes any specific
        # markup/function/class names — the model designs the cart or reserve
        # UI freely. The only thing it's required to produce is the
        # integration hook with the matching `type`, so that's the only thing
        # checked here. Whitespace is stripped before matching since
        # generated JS formatting (spacing, quote style) varies freely.
        # When business_id is set the prompt asks for a real POST to
        # /businesses/{id}/submissions instead of the legacy postMessage hook
        # (postMessage never reached anywhere for a standalone /site/{slug}
        # page with no parent frame to receive it) -- check for whichever
        # contract was actually requested.
        if not needs_cart and not needs_reserve:
            return True
        lower = re.sub(r"\s+", "", (html or "").lower())
        if business_id:
            if "/submissions" not in lower:
                return False
        elif "postmessage" not in lower:
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
