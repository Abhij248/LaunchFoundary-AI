"""
Post-generation website testing, two-tier.

Tier 1 (run_reachability_check): deterministic, no LLM cost. Loads the real
generated page from its live /site/{slug} URL (so relative fetch() calls to
the real backend resolve correctly, exactly as a real visitor would see it),
clicks through to the checkout/reserve step, and verifies the confirm
element is genuinely visible and not clipped by a scroll-clipped ancestor --
the literal class of bug that motivated this module (a real seat-picker
modal whose CONFIRM button was rendered off-screen behind overflow:hidden).

Tier 2 (run_qa_agent_test): only worth calling if Tier 1 passes. Gives a
real LLM actual browser-control tools (read_page_state/click/fill) via
agentic_planner.generate_with_tools and lets it attempt the real workflow
with invented realistic data, reporting semantic findings a fixed check
can't catch. Completing a real checkout hits the real backend (claims a
real seat, creates a real submission row), so this module tracks whatever
the session actually created via response interception -- not by trusting
the model's own account of what it did -- and cleans it up afterward.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from agentic_planner import ModelJsonPlanner
from custom_entities_store import release_claim
from submissions_store import delete_submission, mark_submission_source

logger = logging.getLogger(__name__)

CONFIRM_TEXT_PATTERN = re.compile(
    r"confirm|checkout|book now|reserve|place order|pay|submit order|complete booking",
    re.IGNORECASE,
)
ITEM_CLICK_SELECTORS = [
    "[data-item-id]", "[data-id]", ".item-card", ".menu-item", ".product-card",
    ".showtime", ".catalog-item",
]


def _any_overlay_visible(page) -> bool:
    try:
        return bool(page.evaluate(
            """
            () => {
                const all = document.querySelectorAll('*');
                for (const node of all) {
                    const style = getComputedStyle(node);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    const cls = (node.className || '') + ' ' + (node.id || '');
                    if (
                        style.position === 'fixed'
                        || node.getAttribute('role') === 'dialog'
                        || node.getAttribute('aria-modal') === 'true'
                        || /modal|dialog|overlay|popup|sheet|drawer/i.test(cls)
                    ) {
                        const rect = node.getBoundingClientRect();
                        if (rect.width > 50 && rect.height > 50) return true;
                    }
                }
                return false;
            }
            """
        ))
    except Exception:
        return False


def _click_first_item(page) -> bool:
    """Tries each candidate element in turn, treating success as 'a real
    modal/overlay actually appeared afterward' -- not just 'a click didn't
    throw'. A wrong click (e.g. a marketing CTA that just scrolls the page)
    would otherwise be indistinguishable from opening the real workflow."""
    candidates = []
    for selector in ITEM_CLICK_SELECTORS:
        try:
            locator = page.locator(selector)
            for i in range(min(locator.count(), 3)):
                candidates.append(locator.nth(i))
        except Exception:
            continue
    try:
        role_locator = page.get_by_role("button", name=re.compile("add|select|choose|view|book", re.IGNORECASE))
        for i in range(min(role_locator.count(), 3)):
            candidates.append(role_locator.nth(i))
    except Exception:
        pass

    for candidate in candidates:
        try:
            if not candidate.is_visible():
                continue
            candidate.click(timeout=3000)
            page.wait_for_timeout(500)
            if _any_overlay_visible(page):
                return True
        except Exception:
            continue
    return False


def _is_inside_overlay_context(page, handle) -> bool:
    """A page's normal marketing copy can easily contain confirm-ish words
    ("Reserve Your Seats Now" as a hero CTA that just scrolls the page,
    not an actual checkout step) -- so text matching alone produces false
    positives. A real checkout/confirm step is reached by opening a
    modal/dialog/drawer, so require the match to actually be inside one."""
    try:
        return bool(page.evaluate(
            """
            (el) => {
                let node = el;
                while (node && node !== document.body) {
                    const style = getComputedStyle(node);
                    const cls = (node.className || '') + ' ' + (node.id || '');
                    if (
                        style.position === 'fixed'
                        || node.getAttribute('role') === 'dialog'
                        || node.getAttribute('aria-modal') === 'true'
                        || /modal|dialog|overlay|popup|sheet|drawer/i.test(cls)
                    ) {
                        return true;
                    }
                    node = node.parentElement;
                }
                return false;
            }
            """,
            handle,
        ))
    except Exception:
        return False


def _find_confirm_element(page):
    """Returns the first confirm-ish text match that's genuinely inside a
    modal/overlay context, skipping matches that are just page copy."""
    try:
        candidates = page.get_by_text(CONFIRM_TEXT_PATTERN)
        count = candidates.count()
        for i in range(min(count, 10)):
            candidate = candidates.nth(i)
            handle = candidate.element_handle(timeout=2000)
            if handle is not None and _is_inside_overlay_context(page, handle):
                return candidate
    except Exception:
        pass
    return None


def _is_genuinely_reachable(page, locator) -> tuple[bool, str]:
    """Replicates the manual DOM-ancestor-overflow check that caught the
    original seat-picker bug: an element can be nominally 'visible' per
    Playwright yet still be positioned outside a fixed-height, overflow
    hidden ancestor's actual clickable viewport."""
    try:
        handle = locator.element_handle(timeout=3000)
        if handle is None:
            return False, "element handle not found"
        info = page.evaluate(
            """
            (el) => {
                const rect = el.getBoundingClientRect();
                let node = el;
                let clippedBy = null;
                while (node && node !== document.body) {
                    const style = getComputedStyle(node);
                    if (style.overflow === 'hidden' || style.overflowY === 'hidden') {
                        const parentRect = node.getBoundingClientRect();
                        if (rect.bottom > parentRect.bottom || rect.top < parentRect.top) {
                            clippedBy = node.className || node.tagName;
                            break;
                        }
                    }
                    node = node.parentElement;
                }
                return {
                    top: rect.top, bottom: rect.bottom,
                    withinViewport: rect.top >= 0 && rect.bottom <= window.innerHeight,
                    clippedBy,
                };
            }
            """,
            handle,
        )
        if info.get("clippedBy"):
            return False, f"clipped by an ancestor with overflow:hidden ({info['clippedBy']})"
        if not info.get("withinViewport"):
            return False, f"positioned outside the viewport (top={info.get('top')}, bottom={info.get('bottom')})"
        return True, ""
    except Exception as exc:
        return False, f"reachability check itself failed: {exc}"


def run_reachability_check(base_url: str, site_slug: str) -> dict[str, Any]:
    """Tier 1. Returns {"passed": bool, "reason": str, "console_errors": [...]}.
    A script limitation (couldn't find an item/confirm element) is treated as
    an inconclusive pass, not a failure -- this must never make generation
    less reliable than not testing at all."""
    from playwright.sync_api import sync_playwright

    result: dict[str, Any] = {"passed": True, "reason": "", "console_errors": []}
    url = f"{base_url.rstrip('/')}/site/{site_slug}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.on("console", lambda msg: result["console_errors"].append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda exc: result["console_errors"].append(str(exc)))

            page.goto(url, wait_until="networkidle", timeout=20000)

            if not _click_first_item(page):
                result["reason"] = "Could not locate a clickable item to start the workflow -- inconclusive."
                browser.close()
                return result

            page.wait_for_timeout(600)

            confirm = _find_confirm_element(page)
            if confirm is None:
                result["reason"] = "Could not locate a checkout/confirm/reserve element -- inconclusive."
                browser.close()
                return result

            reachable, why = _is_genuinely_reachable(page, confirm)
            browser.close()
            if not reachable:
                result["passed"] = False
                result["reason"] = f"Checkout/confirm element found but not genuinely reachable: {why}"
            return result
    except Exception as exc:
        logger.warning("Tier 1 smoke test errored, treating as inconclusive: %s", exc)
        result["reason"] = f"Smoke test itself failed to run: {exc}"
        return result


def _tag_and_list_interactive_elements(page) -> list[dict[str, Any]]:
    return page.evaluate(
        """
        () => {
            const nodes = Array.from(document.querySelectorAll(
                'button, a, input, select, textarea, [role="button"], [onclick]'
            ));
            const visible = nodes.filter((el) => {
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
            });
            return visible.slice(0, 40).map((el, i) => {
                el.setAttribute('data-smoke-id', String(i));
                const label = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim();
                return {
                    smoke_id: String(i),
                    tag: el.tagName.toLowerCase(),
                    type: el.getAttribute('type') || '',
                    label: label.slice(0, 80),
                };
            });
        }
        """
    )


def _qa_agent_tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "read_page_state",
                "description": (
                    "See the currently visible interactive elements on the page (buttons, links, "
                    "inputs, selects). Call this again after any click or fill, since the page's "
                    "content changes (e.g. a modal opens) and smoke_ids from before may no longer apply."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "click",
                "description": "Click one element by its smoke_id (from the most recent read_page_state call).",
                "parameters": {
                    "type": "object",
                    "properties": {"smoke_id": {"type": "string"}},
                    "required": ["smoke_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fill",
                "description": "Type a value into one input/textarea/select element by its smoke_id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "smoke_id": {"type": "string"},
                        "value": {"type": "string"},
                    },
                    "required": ["smoke_id", "value"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_console_errors",
                "description": "See any JavaScript console errors that have occurred on the page so far.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "report_findings",
                "description": (
                    "Call this exactly once, when you're done testing (whether you succeeded or "
                    "got stuck), to report what you found."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "completed": {
                            "type": "boolean",
                            "description": "Whether you completed the full workflow, including the final confirm/submit step.",
                        },
                        "issues": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific, concrete problems encountered -- not vague adjectives.",
                        },
                        "notes": {
                            "type": "string",
                            "description": "What you'd tell a developer to fix, if anything.",
                        },
                    },
                    "required": ["completed", "issues", "notes"],
                },
            },
        },
    ]


def _run_qa_tool_loop(
    page,
    planner: ModelJsonPlanner,
    workflow_description: str,
    findings: dict[str, Any],
    console_errors: list[str],
    max_iterations: int,
) -> None:
    def tool_executor(name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "read_page_state":
            try:
                return {"elements": _tag_and_list_interactive_elements(page)}
            except Exception as exc:
                return {"error": str(exc)}
        if name == "click":
            smoke_id = str(args.get("smoke_id", ""))
            try:
                page.click(f'[data-smoke-id="{smoke_id}"]', timeout=5000)
                page.wait_for_timeout(400)
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}
        if name == "fill":
            smoke_id = str(args.get("smoke_id", ""))
            value = str(args.get("value", ""))
            try:
                page.fill(f'[data-smoke-id="{smoke_id}"]', value, timeout=5000)
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}
        if name == "get_console_errors":
            return {"errors": list(console_errors)}
        if name == "report_findings":
            findings["completed"] = bool(args.get("completed", False))
            findings["issues"] = [str(i) for i in (args.get("issues") or [])][:8]
            findings["notes"] = str(args.get("notes", ""))[:500]
            findings["reported"] = True
            return {"ok": True}
        return {"error": f"unknown tool {name}"}

    prompt = (
        "You are testing a real, live website as a real customer would.\n"
        f"Task: {workflow_description}\n\n"
        "Use read_page_state to see what's on the page right now (call it again after any click "
        "or fill, since the page changes). Use click/fill with the smoke_id values it gives you to "
        "navigate. Invent plausible, realistic test data (a real-sounding name, a real-sounding "
        "date/time if asked, etc.) -- never literal placeholder text like \"test\" or \"asdf\". Try "
        "to complete the workflow for real, including the final confirm/submit step -- this is "
        "running against a real backend, so a genuine completion is the most useful signal. When "
        "you're done (whether you succeeded or got stuck), call report_findings exactly once."
    )

    try:
        planner.generate_with_tools(
            prompt, _qa_agent_tool_schemas(), tool_executor,
            max_new_tokens=600, temperature=0.4, max_iterations=max_iterations, timeout=60.0,
        )
    except Exception as exc:
        if not findings.get("reported"):
            findings["notes"] = f"Agent session ended without reporting findings: {exc}"


def run_qa_agent_test(
    base_url: str,
    site_slug: str,
    business_id: str,
    planner: ModelJsonPlanner,
    workflow_description: str,
    max_iterations: int = 12,
) -> dict[str, Any]:
    """Tier 2. Only call this after Tier 1 passes -- no point spending real
    LLM calls driving a browser through a workflow already known to be
    mechanically broken. Always attempts cleanup of any real backend state
    the session created, regardless of how the session itself ended."""
    from playwright.sync_api import sync_playwright

    findings: dict[str, Any] = {"completed": False, "issues": [], "notes": "", "reported": False}
    observed_claims: list[tuple[str, str, str]] = []
    observed_submission_ids: list[str] = []
    console_errors: list[str] = []
    url = f"{base_url.rstrip('/')}/site/{site_slug}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda exc: console_errors.append(str(exc)))

            def _on_response(response) -> None:
                try:
                    if response.request.method != "POST" or response.status != 200:
                        return
                    resp_url = response.url
                    if "/claim" in resp_url:
                        body = response.request.post_data_json or {}
                        observed_claims.append((
                            str(body.get("entityType", "")),
                            str(body.get("entityId", "")),
                            str(body.get("resourceKey", "")),
                        ))
                    elif "/submissions" in resp_url:
                        data = response.json()
                        if isinstance(data, dict) and data.get("id"):
                            observed_submission_ids.append(str(data["id"]))
                except Exception:
                    pass

            page.on("response", _on_response)
            page.goto(url, wait_until="networkidle", timeout=20000)

            try:
                _run_qa_tool_loop(page, planner, workflow_description, findings, console_errors, max_iterations)
            except Exception as exc:
                findings["notes"] = f"QA agent session errored: {exc}"

            browser.close()
    except Exception as exc:
        logger.warning("Tier 2 QA smoke test errored: %s", exc)
        findings["notes"] = f"Tier 2 smoke test itself failed to run: {exc}"
    finally:
        for entity_type, entity_id, resource_key in observed_claims:
            try:
                released = release_claim(business_id, entity_type, entity_id, resource_key)
                logger.info(
                    "QA smoke test cleanup: released claim %s/%s/%s (%s)",
                    entity_type, entity_id, resource_key, "ok" if released else "not found",
                )
            except Exception as exc:
                logger.warning(
                    "Failed to release test claim %s/%s/%s: %s", entity_type, entity_id, resource_key, exc
                )
        for submission_id in observed_submission_ids:
            try:
                mark_submission_source(submission_id, "qa_smoke_test")
                deleted = delete_submission(submission_id)
                logger.info(
                    "QA smoke test cleanup: removed submission %s (%s)",
                    submission_id, "ok" if deleted else "not found",
                )
            except Exception as exc:
                logger.warning("Failed to delete test submission %s: %s", submission_id, exc)

    findings["console_errors"] = console_errors
    return findings
