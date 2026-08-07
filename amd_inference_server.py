from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import shutil
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import httpx
from fastapi import Cookie, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agentic_graph import HumanInputRequired, iter_agent_graph_updates, run_agent_graph
from agentic_models import (
    AssetExtraction,
    CognitiveProvenanceRecord,
    ProvenanceSource,
    ReasoningLineageEntry,
    StateArtifactStatus,
)
from agentic_planner import ModelJsonPlanner, get_vision_config
from buildspec_planner import generate_build_spec
from research_agents import ResearchOrchestrator
from code_generator import CodeGenerationOrchestrator, CodeGenerator
from critique_system import CritiqueOrchestrator
from deployment_system import DeploymentOrchestrator
import auth_store
from menu_store import (
    delete_business,
    get_business,
    get_business_build_context,
    get_business_by_slug,
    list_businesses_for_owner,
    list_items,
    replace_items,
    update_business_preview,
)
import submissions_store
from submissions_store import (
    create_submission,
    delete_submissions_for_business,
    list_submissions,
    update_submission_status,
)
from learned_memory_store import record_memory
from custom_entities_store import (
    claim_resource,
    delete_entities_for_business,
    list_claims,
    list_entities,
)

SESSION_COOKIE_NAME = "lf_session"


# Business/asset text routinely contains em-dashes, curly quotes, and other
# non-ASCII characters. On Windows the console's stdout/stderr often use a
# legacy codepage (cp1252/cp437) that can't encode them, so the plain
# StreamHandler below would raise UnicodeEncodeError mid-write; Python's
# logging then falls back to writing the error to stderr, and if THAT write
# also blocks (e.g. a paused/QuickEdit console), the single-threaded server
# deadlocks entirely -- with no exception ever surfacing. Reconfiguring with
# errors="backslashreplace" makes the write always succeed instead.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler("debug.log", maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(title="LaunchFoundry AMD Inference API")
APP_DIR = Path(__file__).resolve().parent


def load_local_env() -> None:
    env_path = APP_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env()

# Set when the frontend is deployed separately from this backend (e.g.
# frontend on Vercel, this backend on Render) -- the exact origin the
# frontend is served from, e.g. "https://launchfoundry.vercel.app". Left
# unset for local dev, where the frontend is served by this same app
# (same-origin, so CORS doesn't come into play at all). A wildcard origin
# can't be combined with allow_credentials=True (browsers reject it), so
# this must be a real origin once the frontend moves elsewhere.
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "").strip()
CROSS_ORIGIN_DEPLOYMENT = bool(FRONTEND_ORIGIN)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN] if CROSS_ORIGIN_DEPLOYMENT else ["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

json_planner = None

app.mount("/static", StaticFiles(directory=APP_DIR), name="static")

# Owner-uploaded product/menu-item photos -- kept outside the repo (like
# menu_items.db) since /static mounts the whole repo root publicly.
UPLOADS_DIR = Path.home() / ".launchfoundry" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


async def process_image_with_pollinations(image_data: bytes, filename: str) -> dict[str, Any]:
    """Process an image using the active provider's chat-completions vision endpoint."""
    provider, vision_url, vision_model, api_key = get_vision_config()
    try:
        logger.debug(f"Processing image via {provider}: {filename}")
        async with httpx.AsyncClient() as client:
            mime_type = (
                mimetypes.guess_type(filename)[0]
                or "image/jpeg"
            )
            encoded = base64.b64encode(image_data).decode("ascii")
            data_url = f"data:{mime_type};base64,{encoded}"
            headers = {
                "Content-Type": "application/json",
            }
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            payload = {
                "model": vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Analyze this business asset image. Return concise JSON with: "
                                    "asset_type, business_signals, extracted_business_info "
                                    "(business_name, phone, email, address, hours, services_or_items, offers, prices), "
                                    "recommended_pages, recommended_features, trust_or_compliance_notes, "
                                    "visual_brand_cues, planner_notes."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": data_url,
                                },
                            },
                        ],
                    }
                ],
            }

            logger.debug(f"Sending request to {provider} vision API for {filename}")
            response = await client.post(
                vision_url,
                headers=headers,
                json=payload,
                timeout=30.0,
            )

            logger.debug(f"Response status for {filename}: {response.status_code}")

            if response.status_code == 200:
                try:
                    result = response.json()
                    logger.debug(f"Successfully parsed JSON response for {filename}")
                except Exception as e:
                    result = {"text_response": response.text}
                    logger.warning(f"JSON parsing failed for {filename}, using text response: {e}")

                parsed_result = extract_pollinations_vision_payload(result)

                return {
                    "image": filename,
                    "parsed": parsed_result,
                    "status": "success",
                }

            error_text = response.text
            logger.error(
                f"{provider} vision API error for {filename}: Status {response.status_code}, Response: {error_text}"
            )
            return {
                "image": filename,
                "error": f"API request failed with status {response.status_code}: {error_text}",
                "status": "error",
                "error_code": f"http_{response.status_code}",
            }

    except Exception as e:
        logger.exception(f"Exception in process_image_with_pollinations for {filename}: {e}")
        return {
            "image": filename,
            "error": str(e),
            "status": "error",
            "error_code": "exception",
        }


def extract_pollinations_vision_payload(result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"text_response": str(result or "")}

    content: str | None = None
    choices = result.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        if isinstance(message, dict):
            raw_content = message.get("content")
            if isinstance(raw_content, str):
                content = raw_content
            elif isinstance(raw_content, list):
                text_parts: list[str] = []
                for item in raw_content:
                    if isinstance(item, dict):
                        text_value = item.get("text")
                        if isinstance(text_value, str):
                            text_parts.append(text_value)
                if text_parts:
                    content = "\n".join(text_parts)

    if not content:
        content = (
            result.get("response")
            if isinstance(result.get("response"), str)
            else result.get("text")
        )

    if not isinstance(content, str) or not content.strip():
        return {"text_response": json.dumps(result)}

    text = content.strip()
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced_match:
        text = fenced_match.group(1)
    else:
        object_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if object_match:
            text = object_match.group(0)

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    return {"text_response": content}


@app.on_event("startup")
def startup() -> None:
    logger.info("Starting up AMD inference server")
    global json_planner

    json_planner = ModelJsonPlanner()

    logger.info(f"{json_planner.provider} model ready.")


@app.get("/health")
def health() -> dict[str, Any]:
    logger.debug("Health check requested")
    return {
        "ok": True,
        "vision_model_loaded": True,
    }


@app.get("/")
def frontend() -> FileResponse:
    logger.debug("Frontend requested")
    return FileResponse(APP_DIR / "index.html")


@app.get("/app.js")
def frontend_js() -> FileResponse:
    logger.debug("App.js requested")
    return FileResponse(APP_DIR / "app.js", media_type="application/javascript")


@app.get("/styles.css")
def frontend_css() -> FileResponse:
    logger.debug("Styles.css requested")
    return FileResponse(APP_DIR / "styles.css", media_type="text/css")


@app.get("/jupyter-preview")
def frontend_preview() -> FileResponse:
    logger.debug("Jupyter preview requested")
    return FileResponse(APP_DIR / "jupyter_preview.html")


def normalize_asset_extraction_payload(item: dict[str, Any]) -> dict[str, Any]:
    logger.debug(f"Normalizing asset extraction payload: {item.get('image', 'unknown')}")
    try:
        status = str(item.get("status") or "unknown")
        if status != "success":
            error_message = str(item.get("error") or "Image extraction failed.")
            result = {
                "image": item.get("image", ""),
                "asset_type": "unprocessed",
                "processing_status": "unavailable",
                "business_signals": [],
                "extracted_business_info": {
                    "services_or_items": [],
                    "offers": [],
                    "prices": [],
                },
                "recommended_pages": [],
                "recommended_features": [],
                "trust_or_compliance_notes": [],
                "visual_brand_cues": [],
                "planner_notes": error_message,
                "external_failure": {
                    "service": f"{get_vision_config()[0]}_vision",
                    "status": status,
                    "error": error_message,
                    "error_code": str(item.get("error_code") or "unknown"),
                },
            }
            logger.debug(f"Normalized failed payload for {item.get('image', 'unknown')}: {result}")
            return result

        parsed = dict((item.get("parsed", {}) or {}))
        info = dict((parsed.get("extracted_business_info", {}) or {}))
        info["services_or_items"] = normalize_string_list(info.get("services_or_items"))
        info["offers"] = normalize_string_list(info.get("offers"))
        info["prices"] = normalize_prices(info.get("prices"))
        parsed["business_signals"] = normalize_string_list(parsed.get("business_signals"))
        parsed["recommended_pages"] = normalize_string_list(parsed.get("recommended_pages"))
        parsed["recommended_features"] = normalize_string_list(parsed.get("recommended_features"))
        parsed["trust_or_compliance_notes"] = normalize_string_list(parsed.get("trust_or_compliance_notes"))
        parsed["visual_brand_cues"] = normalize_string_list(parsed.get("visual_brand_cues"))
        parsed["planner_notes"] = str(parsed.get("planner_notes") or parsed.get("text_response") or "")
        parsed["asset_type"] = str(parsed.get("asset_type") or "image")
        parsed["extracted_business_info"] = info
        result = {
            "image": item.get("image", ""),
            "processing_status": "success",
            **parsed,
        }
        logger.debug(f"Normalized payload for {item.get('image', 'unknown')}: {result}")
        return result
    except Exception as e:
        logger.exception(f"Error normalizing asset extraction payload: {e}")
        return {
            "image": item.get("image", ""),
            "asset_type": "unprocessed",
            "business_signals": [],
            "extracted_business_info": {
                "services_or_items": [],
                "offers": [],
                "prices": [],
            },
            "recommended_pages": [],
            "recommended_features": [],
            "trust_or_compliance_notes": [],
            "visual_brand_cues": [],
            "planner_notes": str(item.get("error") or "Extraction normalization failed."),
            "processing_status": "unavailable",
        }


def normalize_string_list(value: Any) -> list[str]:
    logger.debug(f"Normalizing string list: {value}")
    try:
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for entry in value:
            if isinstance(entry, str):
                text = entry.strip()
                if text:
                    normalized.append(text)
            elif isinstance(entry, (int, float)):
                normalized.append(str(entry))
        logger.debug(f"Normalized string list: {normalized}")
        return normalized
    except Exception as e:
        logger.exception(f"Error normalizing string list: {e}")
        return []


def normalize_prices(value: Any) -> list[str | float | int | list[float | int]]:
    logger.debug(f"Normalizing prices: {value}")
    try:
        if not isinstance(value, list):
            return []

        normalized: list[str | float | int | list[float | int]] = []
        for entry in value:
            parsed = normalize_price_entry(entry)
            if parsed is None:
                continue
            normalized.append(parsed)
        logger.debug(f"Normalized prices: {normalized}")
        return normalized
    except Exception as e:
        logger.exception(f"Error normalizing prices: {e}")
        return []


def normalize_price_entry(value: Any) -> str | float | int | list[float | int] | None:
    logger.debug(f"Normalizing price entry: {value}")
    try:
        if isinstance(value, (int, float)):
            return value

        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            numeric_values = extract_numeric_values(text)
            if not numeric_values:
                return text
            if len(numeric_values) == 1:
                return numeric_values[0]
            return numeric_values

        if isinstance(value, list):
            numeric_values: list[float | int] = []
            for item in value:
                if isinstance(item, (int, float)):
                    numeric_values.append(item)
                elif isinstance(item, str):
                    numeric_values.extend(extract_numeric_values(item))
            if not numeric_values:
                return None
            if len(numeric_values) == 1:
                return numeric_values[0]
            return numeric_values

        return None
    except Exception as e:
        logger.exception(f"Error normalizing price entry: {e}")
        return None


def extract_numeric_values(text: str) -> list[float | int]:
    logger.debug(f"Extracting numeric values from: {text}")
    try:
        matches = re.findall(r"\d+(?:\.\d+)?", text)
        values: list[float | int] = []
        for match in matches:
            number = float(match) if "." in match else int(match)
            values.append(number)
        logger.debug(f"Extracted numeric values: {values}")
        return values
    except Exception as e:
        logger.exception(f"Error extracting numeric values: {e}")
        return []


def build_fallback_graph_execution(
    profile: dict[str, Any],
    asset_extractions: list[dict[str, Any]],
    planner_status: dict[str, Any] | None = None,
    graph_error: str = "",
) -> dict[str, Any]:
    planner_status = planner_status or {}
    reasoning_notes = [
        "Agent graph fallback mode was used because the external planning model failed.",
    ]
    if graph_error:
        reasoning_notes.append(
            f"Graph execution fallback reason: {graph_error}"
        )
    if planner_status.get("degraded"):
        reasoning_notes.append(
            f"Planner entered degraded mode: {planner_status.get('reason') or 'external planner unavailable.'}"
        )
    return {
        "status": "fallback",
        "graph_error": graph_error,
        "final_state": {
            "business_input": profile,
            "uploaded_asset_paths": [item.get("image", "") for item in asset_extractions],
            "asset_extractions": asset_extractions,
            "business_profile": None,
            "requirements_spec": None,
            "strategy_hypotheses": [],
            "revision_iteration": 0,
            "candidate_history": [],
            "critique_history": [],
            "design_candidates": [],
            "critique_reports": [],
            "design_spec": None,
            "finalization_decision": None,
            "qa_notes": [],
            "reasoning_notes": reasoning_notes,
            "provenance_log": [
                CognitiveProvenanceRecord(
                    artifact_key="graph_execution",
                    stage="fallback",
                    source_type=ProvenanceSource.LOCAL_FALLBACK,
                    summary="Graph execution fell back to deterministic response packaging.",
                    confidence=0.35,
                    fallback_used=True,
                    iteration=0,
                    supporting_keys=["business_input", "asset_extractions"],
                ).model_dump()
            ],
            "reasoning_lineage": [
                ReasoningLineageEntry(
                    stage="fallback",
                    decision="returned_fallback_graph_execution",
                    confidence=0.35,
                    fallback_used=True,
                    inputs=["business_input", "asset_extractions"],
                    outputs=["graph_execution"],
                    summary=graph_error or "Graph did not complete normally.",
                ).model_dump()
            ],
            "state_artifacts": {
                "graph_execution": StateArtifactStatus(
                    artifact_key="graph_execution",
                    status="fallback",
                    source_type=ProvenanceSource.LOCAL_FALLBACK,
                    confidence=0.35,
                    updated_in_stage="fallback",
                    summary="Fallback graph execution returned.",
                    lineage_ref="fallback:graph_execution:0",
                ).model_dump()
            },
            "active_fallbacks": ["fallback:graph_execution"],
            "memory_query": None,
            "retrieved_memories": [],
            "tool_invocations": [],
            "reflection_report": None,
            "uncertainty_score": 0.0,
            "simulation_report": None,
        },
        "events": [],
    }


def build_generate_response_payload(
    *,
    asset_signals: str,
    normalized_extractions: list[dict[str, Any]],
    build_spec: dict[str, Any],
    agent_state: dict[str, Any],
    planner_status: dict[str, Any],
) -> dict[str, Any]:
    external_failures = collect_external_failures(
        normalized_extractions,
        planner_status,
    )
    active_provider = get_vision_config()[0]
    vision_mode = (
        "unavailable"
        if any(item.get("processing_status") != "success" for item in normalized_extractions)
        else ("unused" if not normalized_extractions else f"{active_provider}_vision")
    )
    return {
        "source": f"{active_provider}-agent-system",
        "assetSignals": asset_signals,
        "assetExtractions": normalized_extractions,
        "buildSpec": build_spec,
        "graphExecution": agent_state,
        "graphStatus": {
            "status": agent_state.get("status", "completed"),
            "error": agent_state.get("graph_error", ""),
        },
        "plannerMode": planner_status.get("mode", f"external_{active_provider}"),
        "visionMode": vision_mode,
        "externalFailures": external_failures,
        "cognitive_events": [
            (
                event.model_dump()
                if hasattr(event, "model_dump")
                else event
            )
            for event in agent_state.get(
                "cognitive_events",
                [],
            )
        ],
    }


def sse_event(
    event_name: str,
    payload: dict[str, Any],
) -> str:
    return (
        f"event: {event_name}\n"
        f"data: {json.dumps(payload, default=str)}\n\n"
    )


def asset_signals_from_extractions(extractions: list[dict[str, Any]]) -> str:
    if not extractions:
        return ""

    lines = ["Extracted asset signals:"]
    for item in extractions:
        lines.append(f"File: {item.get('image', 'uploaded-image')}")
        lines.append(f"Asset type: {item.get('asset_type', 'image')}")
        processing_status = str(item.get("processing_status") or "unknown")
        if processing_status != "success":
            lines.append(f"- Extraction status: {processing_status}")
            planner_notes = str(item.get("planner_notes") or "").strip()
            if planner_notes:
                lines.append(f"- Extraction failure: {planner_notes[:240]}")
            continue
        for signal in item.get("business_signals", [])[:6]:
            lines.append(f"- Signal: {signal}")

        info = item.get("extracted_business_info", {}) or {}
        services = info.get("services_or_items", []) or []
        offers = info.get("offers", []) or []
        prices = info.get("prices", []) or []

        if services:
            lines.append(f"- Services/items visible: {', '.join(str(value) for value in services[:12])}")
        if offers:
            lines.append(f"- Offers visible: {', '.join(str(value) for value in offers[:8])}")
        if prices:
            lines.append(f"- Prices visible: {', '.join(str(value) for value in prices[:8])}")

        for feature in item.get("recommended_features", [])[:6]:
            lines.append(f"- Recommended feature: {feature}")

        planner_notes = str(item.get("planner_notes") or "").strip()
        if planner_notes:
            lines.append(f"- Planner note: {planner_notes[:240]}")

    return "\n".join(lines)


async def extract_request_payload(request: Request, payload_form: str | None) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "").lower()

    if "multipart/form-data" in content_type:
        if not payload_form:
            return {}
        try:
            parsed = json.loads(payload_form)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            logger.warning("Failed to decode multipart payload JSON")
            return {}

    try:
        body = await request.json()
        return body if isinstance(body, dict) else {}
    except Exception:
        logger.warning("Failed to decode JSON body")
        return {}


def collect_external_failures(
    normalized_extractions: list[dict[str, Any]],
    planner_status: dict[str, Any],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for item in normalized_extractions:
        failure = item.get("external_failure")
        if isinstance(failure, dict):
            failures.append(
                {
                    "image": item.get("image", ""),
                    **failure,
                }
            )
    planner_provider = str(planner_status.get("mode", "external_unknown")).replace("external_", "")
    for error in planner_status.get("errors", []):
        failures.append(
            {
                "service": f"{planner_provider}_generate",
                "status": "error",
                "error": error,
            }
        )
    return failures


async def process_uploaded_files(
    files: list[UploadFile] | None,
) -> list[dict[str, Any]]:
    normalized_extractions: list[dict[str, Any]] = []
    if not files:
        return normalized_extractions

    for upload in files:
        if upload is None:
            continue
        file_bytes = await upload.read()
        if not file_bytes:
            continue
        extraction = await process_image_with_pollinations(
            file_bytes,
            upload.filename or "uploaded-image",
        )
        normalized_extractions.append(
            normalize_asset_extraction_payload(
                extraction
            )
        )

    return normalized_extractions


def normalize_supplied_extractions(
    raw_extractions: Any,
) -> list[dict[str, Any]]:
    if not isinstance(raw_extractions, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in raw_extractions:
        if isinstance(item, dict):
            normalized.append(
                normalize_asset_extraction_payload(
                    {
                        "image": item.get("image", ""),
                        "parsed": item,
                        "status": "success",
                    }
                )
            )
    return normalized


@app.post("/generate-buildspec")
async def generate_buildspec(
    request: Request,
    payload: str | None = Form(default=None),
    files: list[UploadFile] | None = File(default=None),
) -> dict[str, Any]:
    parsed_payload = await extract_request_payload(request, payload)
    planner = ModelJsonPlanner()
    planner.begin_request()

    logger.info("Received generate_buildspec request")
    logger.debug(f"Request payload: {parsed_payload}")

    try:
        profile = parsed_payload.get("business_input", {})

        if not profile:
            if "payload" in parsed_payload and isinstance(parsed_payload["payload"], dict):
                profile = parsed_payload["payload"].get("business_input", {})
            elif "business_input" in parsed_payload and isinstance(parsed_payload["business_input"], dict):
                profile = parsed_payload["business_input"]
            elif isinstance(parsed_payload, dict):
                profile = parsed_payload

        if not profile:
            if isinstance(parsed_payload, dict) and "name" in parsed_payload and "location" in parsed_payload:
                profile = parsed_payload
            elif isinstance(parsed_payload, dict):
                for key in ["business_input", "payload", "data"]:
                    if key in parsed_payload and isinstance(parsed_payload[key], dict):
                        profile = parsed_payload[key]
                        break

        logger.debug(f"Extracted business profile: {profile}")

        business_details = profile.get("details", "")
        normalized_extractions = normalize_supplied_extractions(
            parsed_payload.get("asset_extractions")
        )
        if not normalized_extractions:
            normalized_extractions = await process_uploaded_files(
                files
            )

        asset_signals = asset_signals_from_extractions(normalized_extractions)

        enriched_details = "\n\n".join(
            part
            for part in [
                business_details,
                asset_signals,
            ]
            if str(part).strip()
        )

        logger.debug(f"Enriched details: {enriched_details[:200]}...")

        build_spec = generate_build_spec(
            profile,
            enriched_details,
        )

        logger.debug(f"Generated build spec: {build_spec}")

        logger.debug("Running agent graph...")
        try:
            agent_state = run_agent_graph(
                {
                    "business_input": profile,
                    "human_answers": parsed_payload.get("human_answers") or {},
                    "uploaded_asset_paths": [item.get("image", "") for item in normalized_extractions],
                    "asset_extractions": [
                        AssetExtraction.model_validate(item)
                        for item in normalized_extractions
                    ],
                },
                planner=planner,
            )
        except Exception as graph_error:
            logger.exception(f"Agent graph failed, using fallback graph execution: {graph_error}")
            planner_status = planner.get_health_status()
            agent_state = build_fallback_graph_execution(
                profile,
                normalized_extractions,
                planner_status,
                str(graph_error),
            )

        logger.info("Successfully processed generate_buildspec request")
        return build_generate_response_payload(
            asset_signals=asset_signals,
            normalized_extractions=normalized_extractions,
            build_spec=build_spec,
            agent_state=agent_state,
            planner_status=planner.get_health_status(),
        )
    except Exception as e:
        logger.exception(f"Error in generate_buildspec: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/generate-buildspec-stream")
async def generate_buildspec_stream(
    request: Request,
    payload: str | None = Form(default=None),
    files: list[UploadFile] | None = File(default=None),
) -> StreamingResponse:
    parsed_payload = await extract_request_payload(request, payload)
    planner = ModelJsonPlanner()
    planner.begin_request()

    logger.info("Received generate_buildspec_stream request")
    logger.debug(f"Streaming request payload: {parsed_payload}")

    try:
        profile = parsed_payload.get("business_input", {})

        if not profile:
            if "payload" in parsed_payload and isinstance(parsed_payload["payload"], dict):
                profile = parsed_payload["payload"].get("business_input", {})
            elif "business_input" in parsed_payload and isinstance(parsed_payload["business_input"], dict):
                profile = parsed_payload["business_input"]
            elif isinstance(parsed_payload, dict):
                profile = parsed_payload

        if not profile:
            if isinstance(parsed_payload, dict) and "name" in parsed_payload and "location" in parsed_payload:
                profile = parsed_payload
            elif isinstance(parsed_payload, dict):
                for key in ["business_input", "payload", "data"]:
                    if key in parsed_payload and isinstance(parsed_payload[key], dict):
                        profile = parsed_payload[key]
                        break

        business_details = profile.get("details", "")
        normalized_extractions = normalize_supplied_extractions(
            parsed_payload.get("asset_extractions")
        )
        if not normalized_extractions:
            normalized_extractions = await process_uploaded_files(
                files
            )

        asset_signals = asset_signals_from_extractions(normalized_extractions)
        enriched_details = "\n\n".join(
            part
            for part in [
                business_details,
                asset_signals,
            ]
            if str(part).strip()
        )
        build_spec = generate_build_spec(
            profile,
            enriched_details,
        )
        resume_state = parsed_payload.get("resume_state")
        initial_graph_state = (
            resume_state
            if isinstance(resume_state, dict)
            else {}
        )
        initial_graph_state.update({
            "business_input": profile,
            "human_answers": parsed_payload.get("human_answers") or {},
            "uploaded_asset_paths": [item.get("image", "") for item in normalized_extractions],
            "asset_extractions": [
                AssetExtraction.model_validate(item)
                for item in normalized_extractions
            ],
        })

    except Exception as setup_error:
        logger.exception(f"Error preparing generate_buildspec_stream: {setup_error}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(setup_error)}")

    def event_stream():
        yield sse_event(
            "status",
            {
                "message": "Build spec ready. Starting live LangGraph execution.",
            },
        )
        yield sse_event(
            "buildspec",
            {
                "assetSignals": asset_signals,
                "assetExtractions": normalized_extractions,
                "buildSpec": build_spec,
            },
        )

        try:
            agent_state = None
            for update in iter_agent_graph_updates(
                initial_graph_state,
                planner,
            ):
                if update.get("type") == "graph_event":
                    yield sse_event(
                        "graph_update",
                        {
                            "event": update.get("event", {}),
                        },
                    )
                elif update.get("type") == "complete":
                    agent_state = update.get("graph_execution")

            if agent_state is None:
                raise RuntimeError("graph completed without a final state")

        except HumanInputRequired as human_pause:
            resume_state = (
                human_pause.state.model_dump()
                if human_pause.state is not None
                else None
            )
            yield sse_event(
                "human_input_required",
                {
                    "questions": [
                        question.model_dump()
                        for question in human_pause.questions
                    ],
                    "resume_state": resume_state,
                    "message": "The planner needs clarification before continuing.",
                },
            )
            return

        except Exception as graph_error:
            logger.exception(f"Streaming agent graph failed, using fallback graph execution: {graph_error}")
            planner_status = planner.get_health_status()
            agent_state = build_fallback_graph_execution(
                profile,
                normalized_extractions,
                planner_status,
                str(graph_error),
            )
            yield sse_event(
                "graph_error",
                {
                    "error": str(graph_error),
                },
            )

        planner_status = planner.get_health_status()
        yield sse_event(
            "complete",
            build_generate_response_payload(
                asset_signals=asset_signals,
                normalized_extractions=normalized_extractions,
                build_spec=build_spec,
                agent_state=agent_state,
                planner_status=planner_status,
            ),
        )
        logger.info("Successfully streamed generate_buildspec request")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/run-research")
async def run_research(
    request: Request,
    payload: str | None = Form(default=None),
) -> dict[str, Any]:
    """Run deep research agents for competitor analysis, local SEO, and menu/service extraction"""
    parsed_payload = await extract_request_payload(request, payload)
    logger.info("Received run_research request")
    logger.debug(f"Research payload: {parsed_payload}")

    try:
        profile = parsed_payload.get("business_input", {})
        if not profile:
            profile = parsed_payload

        # Initialize planner if not already done
        global json_planner
        if json_planner is None:
            json_planner = ModelJsonPlanner()

        # Initialize research orchestrator
        orchestrator = ResearchOrchestrator(json_planner)

        # Extract vertical from profile
        from buildspec_planner import classify_vertical
        vertical_analysis = classify_vertical(profile.get("details", ""))
        profile["vertical"] = vertical_analysis["vertical"]

        # Run research agents
        assets = parsed_payload.get("assets", [])
        research_results = await orchestrator.run_research(
            business_profile=profile,
            assets=assets,
            run_competitor=True,
            run_seo=True,
            run_extraction=len(assets) > 0
        )

        logger.info("Successfully completed research agents")
        return {
            "source": "research_agents",
            "research_results": {
                "competitor_analysis": research_results.get("competitor_analysis").model_dump() if research_results.get("competitor_analysis") else {},
                "local_seo": research_results.get("local_seo").model_dump() if research_results.get("local_seo") else {},
                "menu_extraction": research_results.get("menu_extraction").model_dump() if research_results.get("menu_extraction") else {},
            },
            "vertical": profile.get("vertical", "unknown"),
        }
    except Exception as e:
        logger.exception(f"Error in run_research: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/generate-code")
async def generate_code(
    request: Request,
    payload: str | None = Form(default=None),
    lf_session: str | None = Cookie(default=None),
) -> dict[str, Any]:
    """Generate website code from BuildSpec using template + AI-assisted approach"""
    parsed_payload = await extract_request_payload(request, payload)
    logger.info("Received generate_code request")
    logger.debug(f"Code generation payload: {parsed_payload}")

    try:
        build_spec = parsed_payload.get("buildSpec", {})
        if not build_spec:
            raise HTTPException(status_code=400, detail="buildSpec is required")

        agent_context = parsed_payload.get("agentContext") or {}
        # Anonymous generation is still allowed (unchanged from before auth
        # existed) -- if logged in, the business gets linked to this owner;
        # if not, it stays unowned, same as every business created so far.
        owner = auth_store.get_owner_for_session(lf_session)
        if owner:
            agent_context = {**agent_context, "owner_id": owner["ownerId"]}

        # Initialize planner if not already done
        global json_planner
        if json_planner is None:
            json_planner = ModelJsonPlanner()

        # Initialize code generation orchestrator
        code_orchestrator = CodeGenerationOrchestrator(json_planner)

        # Generate website code
        generated_code = code_orchestrator.generate_website(build_spec, agent_context=agent_context)

        if generated_code.generation_failed:
            logger.warning(
                "Website generation failed for business %s: %s",
                build_spec.get("business", {}).get("id", ""),
                generated_code.generation_error,
            )
            reason = generated_code.generation_error or "an unknown server-side issue"
            raise HTTPException(
                status_code=503,
                detail=(
                    f"We couldn't generate your website: {reason} This is usually a brief "
                    "server or model hiccup, not a problem with your business details. Please try again."
                ),
            )

        logger.info("Successfully generated website code")
        return {
            "source": "template_ai_code_generator",
            "generated_code": {
                "pages": generated_code.pages,
                "components": generated_code.components,
                "styles": generated_code.styles,
                "config": generated_code.config,
                "html_preview": generated_code.html_preview,
            },
            "vertical": build_spec.get("business", {}).get("vertical", "unknown"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in generate_code: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/businesses/{business_id}/items")
def get_business_items(business_id: str) -> dict[str, Any]:
    """Owner-facing + generated-page read of the current live item list (MVP CMS)."""
    return {"items": list_items(business_id)}


@app.put("/businesses/{business_id}/items")
async def put_business_items(business_id: str, request: Request) -> dict[str, Any]:
    """Whole-list replace -- the owner's menu editor saves the entire array at once."""
    payload = await request.json()
    items = payload.get("items", [])
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="items must be a list")
    return {"items": replace_items(business_id, items)}


@app.delete("/businesses/{business_id}")
def delete_business_route(
    business_id: str,
    lf_session: str | None = Cookie(default=None),
) -> dict[str, Any]:
    """Permanently deletes a business: the record itself, its menu items,
    submissions, and any uploaded product photos. Only the owner who created
    it can delete it -- an unowned or someone-else's business 404s rather
    than revealing whether the id exists."""
    owner = auth_store.get_owner_for_session(lf_session)
    if not owner:
        raise HTTPException(status_code=401, detail="Not logged in")
    deleted = delete_business(business_id, owner["ownerId"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Business not found, or you don't own it")
    delete_submissions_for_business(business_id)
    delete_entities_for_business(business_id)
    uploads_dir = UPLOADS_DIR / business_id
    if uploads_dir.exists():
        shutil.rmtree(uploads_dir, ignore_errors=True)
    return {"deleted": True}


# Generic, schemaless per-business entities -- for businesses whose real
# backend need doesn't fit the fixed items/submissions schema (e.g. a
# theatre's showtimes with per-seat availability). Entities themselves are
# only ever created server-side (during generation, via real tool-calling in
# code_generator.py's _provision_custom_backend) -- these public routes are
# read + atomic-claim only, matching how a real customer interacts with them.
@app.get("/businesses/{business_id}/entities/{entity_type}")
def get_entities(business_id: str, entity_type: str) -> dict[str, Any]:
    return {"entities": list_entities(business_id, entity_type)}


@app.get("/businesses/{business_id}/entities/{entity_type}/{entity_id}/claims")
def get_entity_claims(business_id: str, entity_type: str, entity_id: str) -> dict[str, Any]:
    return {"claimedResourceKeys": list_claims(business_id, entity_type, entity_id)}


@app.post("/businesses/{business_id}/claim")
async def claim_entity_resource(business_id: str, request: Request) -> dict[str, Any]:
    """Atomically claim one resource (e.g. one seat) within one entity (e.g.
    one showtime). This is the real backend guarantee behind seat selection
    -- returns 409, not a silent success, if someone already claimed it."""
    payload = await request.json()
    entity_type = str(payload.get("entityType") or "")
    entity_id = str(payload.get("entityId") or "")
    resource_key = str(payload.get("resourceKey") or "")
    if not (entity_type and entity_id and resource_key):
        raise HTTPException(status_code=400, detail="entityType, entityId, and resourceKey are required")
    claimed = claim_resource(business_id, entity_type, entity_id, resource_key)
    if not claimed:
        raise HTTPException(status_code=409, detail=f'"{resource_key}" was already claimed by someone else')
    return {"claimed": True, "resourceKey": resource_key}


_ITEM_IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
_ITEM_IMAGE_MAX_BYTES = 8 * 1024 * 1024


def _safe_path_component(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", value or "")[:80]
    return cleaned or fallback


@app.post("/businesses/{business_id}/items/image")
async def upload_item_image(business_id: str, item_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    """Owner uploads a real photo for one catalog/menu item -- this is an
    admin-dashboard capability, distinct from anything the LLM generates for
    the public site. The generated page just renders whatever imageUrl this
    produces, same as it already does for name/price/description.

    item_id is a query param, not a path segment: item ids are opaque
    strings that can contain slashes/spaces/punctuation (same reason the
    generated pages are told to pass them via data-id, never splice them
    into a URL path directly)."""
    content_type = (file.content_type or "").lower()
    ext = _ITEM_IMAGE_CONTENT_TYPES.get(content_type)
    if not ext:
        raise HTTPException(status_code=400, detail="Unsupported image type -- use JPEG, PNG, WEBP, or GIF.")
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(file_bytes) > _ITEM_IMAGE_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Image too large (max 8MB)")

    safe_business_id = _safe_path_component(business_id, "business")
    safe_item_id = _safe_path_component(item_id, "item")
    business_dir = UPLOADS_DIR / safe_business_id
    business_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{safe_item_id}{ext}"
    (business_dir / filename).write_bytes(file_bytes)

    return {"imageUrl": f"/uploads/{safe_business_id}/{filename}"}


@app.get("/site/{slug}")
def get_public_site(slug: str) -> HTMLResponse:
    """Serves a business's generated site to real customers at its own URL --
    step 2 of turning this from a builder-tool-only preview into a real
    customer-facing product."""
    business = get_business_by_slug(slug)
    if not business or not business.get("htmlPreview"):
        raise HTTPException(status_code=404, detail="Site not found")
    return HTMLResponse(content=business["htmlPreview"])


@app.get("/businesses/{business_id}/admin")
def get_business_admin_page(
    business_id: str,
    lf_session: str | None = Cookie(default=None),
) -> HTMLResponse:
    """The LLM-generated owner dashboard -- unlike /site/{slug}, this is
    deliberately NOT public: it shows real customer data (names, contact
    info, submission history), so ownership is checked before anything is
    returned, not just before an action is taken."""
    owner = auth_store.get_owner_for_session(lf_session)
    if not owner:
        raise HTTPException(status_code=401, detail="Not logged in")
    business = get_business(business_id)
    if not business or business.get("ownerId") != owner["ownerId"]:
        raise HTTPException(status_code=404, detail="Business not found, or you don't own it")
    if not business.get("adminHtmlPreview"):
        raise HTTPException(status_code=404, detail="No generated admin dashboard yet for this business")
    return HTMLResponse(content=business["adminHtmlPreview"])


@app.post("/businesses/{business_id}/revise")
async def revise_business_site(business_id: str, request: Request) -> dict[str, Any]:
    """Lets an owner describe something wrong or missing and get a targeted
    fix applied to their already-live page, rather than starting over. A
    single generation attempt is a probabilistic LLM call and won't always
    get everything right (missing integration hooks, mixed-up sections,
    etc.) -- this is the correction mechanism for that, triggered by the
    owner instead of guessed at automatically."""
    payload = await request.json()
    revision_request = (payload.get("revisionRequest") or "").strip()
    if not revision_request:
        raise HTTPException(status_code=400, detail="revisionRequest is required")

    context = get_business_build_context(business_id)
    if not context or not context.get("buildSpec"):
        raise HTTPException(
            status_code=404,
            detail="No generation history found for this business -- generate a site before requesting a fix.",
        )

    build_spec = {**context["buildSpec"], "menuItems": list_items(business_id)}
    current_html = context.get("htmlPreview") or ""

    global json_planner
    if json_planner is None:
        json_planner = ModelJsonPlanner()
    generator = CodeGenerator(json_planner)

    feature_keys = {str(f.get("key", "")).lower() for f in build_spec.get("includedFeatures", [])}
    needs_reserve = "catalog_reservation" in feature_keys
    needs_cart = (not needs_reserve) and ("online_ordering" in feature_keys or bool(build_spec.get("menuItems")))

    def _passes_gate(html: str) -> bool:
        return bool(html) and CodeGenerator._html_has_working_commerce_ui(
            html, needs_cart, needs_reserve, business_id
        )

    # Try a targeted edit first -- sends the model only the page section(s)
    # that plausibly need to change instead of the entire page, so most
    # revisions are cheaper, faster, and leave everything else byte-for-byte
    # untouched. Falls back to a full-page rewrite if the targeted approach
    # doesn't produce a usable result (still gated the same way either way),
    # and keeps the old live page if neither passes -- this only adds a
    # cheaper first attempt, it never makes a revision less likely to work.
    revised_html = generator.revise_html_with_targeted_edit(
        build_spec, current_html, revision_request
    )
    used_targeted_edit = bool(revised_html)
    if not _passes_gate(revised_html):
        revised_html = generator.generate_html_with_llm(
            build_spec, {}, revision_request=revision_request, current_html=current_html
        )
        used_targeted_edit = False

    if _passes_gate(revised_html):
        update_business_preview(business_id, revised_html)
        logger.info(
            "Revision accepted for business %s (targeted_edit=%s)",
            business_id, used_targeted_edit,
        )
        # Real owner feedback about what the original generation missed --
        # the highest-value learned-memory signal there is, since it's not
        # an AI's own self-critique but an actual person asking for a fix.
        business_meta = build_spec.get("business", {})
        try:
            record_memory(
                business_id=business_id,
                vertical=str(business_meta.get("vertical", "")),
                subtype=str(business_meta.get("subtype", "")),
                risk_level=str(business_meta.get("riskLevel", "standard")).lower(),
                source="revision_request",
                title=f"Owner requested a fix for {business_meta.get('vertical', 'a')} business",
                summary=revision_request,
            )
        except Exception:
            logger.warning("Failed to record learned memory for revision request", exc_info=True)
        return {"accepted": True, "htmlPreview": revised_html}

    return {
        "accepted": False,
        "htmlPreview": current_html,
        "message": (
            "The revision didn't pass validation, so your live site is unchanged. "
            "Try rephrasing the request or being more specific."
        ),
    }


@app.post("/businesses/{business_id}/submissions")
async def post_submission(business_id: str, request: Request) -> dict[str, Any]:
    """Called directly by the generated customer-facing page (same-origin
    fetch, no auth) whenever a visitor places an order/reservation/completes
    a lead form -- works whether that page is standalone at /site/{slug} or
    embedded in the builder's preview iframe, unlike the old postMessage
    approach which only ever worked in the iframe case."""
    payload = await request.json()
    submission_type = payload.get("type", "")
    if submission_type not in {"order", "reservation", "lead"}:
        raise HTTPException(status_code=400, detail="type must be one of order, reservation, lead")
    record = create_submission(
        business_id, submission_type,
        customer=payload.get("customer", ""), summary=payload.get("summary", ""), contact=payload.get("contact", ""),
    )
    if record is None:
        raise HTTPException(status_code=400, detail="business_id is required")
    return record


@app.get("/businesses/{business_id}/submissions")
def get_submissions(business_id: str) -> dict[str, Any]:
    return {"submissions": list_submissions(business_id)}


@app.patch("/businesses/{business_id}/submissions/{submission_id}")
async def patch_submission_status(business_id: str, submission_id: str, request: Request) -> dict[str, Any]:
    """Owner-facing: mark an order/booking/lead as in progress, completed, or
    cancelled from the admin dashboard -- this is admin-dashboard code (this
    app's own app.js), not something a 'Request a Fix' on the generated site
    could ever reach."""
    payload = await request.json()
    status = payload.get("status", "")
    if status not in submissions_store.VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(submissions_store.VALID_STATUSES)}",
        )
    record = update_submission_status(business_id, submission_id, status)
    if record is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return record


@app.post("/auth/signup")
async def auth_signup(request: Request, response: Response) -> dict[str, Any]:
    payload = await request.json()
    try:
        owner = auth_store.signup(payload.get("email", ""), payload.get("password", ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    token = auth_store.create_session(owner["ownerId"])
    response.set_cookie(
        SESSION_COOKIE_NAME, token, httponly=True,
        samesite="none" if CROSS_ORIGIN_DEPLOYMENT else "lax",
        secure=CROSS_ORIGIN_DEPLOYMENT,
        max_age=int(auth_store.SESSION_TTL.total_seconds()),
    )
    return owner


@app.post("/auth/login")
async def auth_login(request: Request, response: Response) -> dict[str, Any]:
    payload = await request.json()
    try:
        owner = auth_store.login(payload.get("email", ""), payload.get("password", ""))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    token = auth_store.create_session(owner["ownerId"])
    response.set_cookie(
        SESSION_COOKIE_NAME, token, httponly=True,
        samesite="none" if CROSS_ORIGIN_DEPLOYMENT else "lax",
        secure=CROSS_ORIGIN_DEPLOYMENT,
        max_age=int(auth_store.SESSION_TTL.total_seconds()),
    )
    return owner


@app.post("/auth/logout")
def auth_logout(response: Response, lf_session: str | None = Cookie(default=None)) -> dict[str, Any]:
    auth_store.destroy_session(lf_session)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"ok": True}


@app.get("/auth/me")
def auth_me(lf_session: str | None = Cookie(default=None)) -> dict[str, Any]:
    owner = auth_store.get_owner_for_session(lf_session)
    if not owner:
        raise HTTPException(status_code=401, detail="Not logged in")
    return owner


@app.get("/auth/my-businesses")
def auth_my_businesses(lf_session: str | None = Cookie(default=None)) -> dict[str, Any]:
    owner = auth_store.get_owner_for_session(lf_session)
    if not owner:
        raise HTTPException(status_code=401, detail="Not logged in")
    return {"businesses": list_businesses_for_owner(owner["ownerId"])}


@app.post("/run-critique")
async def run_critique(
    request: Request,
    payload: str | None = Form(default=None),
) -> dict[str, Any]:
    """Run critique agents on generated code"""
    parsed_payload = await extract_request_payload(request, payload)
    logger.info("Received run_critique request")
    logger.debug(f"Critique payload: {parsed_payload}")

    try:
        code = parsed_payload.get("code", "")
        build_spec = parsed_payload.get("buildSpec", {})
        agents = parsed_payload.get("agents", ["ux", "accessibility", "conversion", "security", "performance"])

        if not code:
            raise HTTPException(status_code=400, detail="code is required")

        # Initialize planner if not already done
        global json_planner
        if json_planner is None:
            json_planner = ModelJsonPlanner()

        # Initialize critique orchestrator
        critique_orchestrator = CritiqueOrchestrator(json_planner)

        # Run critique agents
        critique_reports = await critique_orchestrator.run_critique(code, build_spec, agents)

        # Run debate/consensus
        debate_outcome = await critique_orchestrator.run_debate(critique_reports, build_spec)

        logger.info("Successfully completed critique and debate")
        return {
            "source": "critique_debate_system",
            "critique_reports": {
                agent_name: report.model_dump() if hasattr(report, "model_dump") else report
                for agent_name, report in critique_reports.items()
            },
            "debate_outcome": debate_outcome.model_dump() if hasattr(debate_outcome, "model_dump") else debate_outcome,
        }
    except Exception as e:
        logger.exception(f"Error in run_critique: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/generate-deployment")
async def generate_deployment(
    request: Request,
    payload: str | None = Form(default=None),
) -> dict[str, Any]:
    """Generate deployment package from BuildSpec"""
    parsed_payload = await extract_request_payload(request, payload)
    logger.info("Received generate_deployment request")
    logger.debug(f"Deployment payload: {parsed_payload}")

    try:
        build_spec = parsed_payload.get("buildSpec", {})
        if not build_spec:
            raise HTTPException(status_code=400, detail="buildSpec is required")

        # Initialize deployment orchestrator
        deployment_orchestrator = DeploymentOrchestrator()

        # Generate deployment package
        deployment_package = deployment_orchestrator.generate_deployment_package(build_spec)

        logger.info("Successfully generated deployment package")
        return {
            "source": "deployment_system",
            "deployment_package": {
                "database_schema": deployment_package.database_schema.model_dump(),
                "auth_config": deployment_package.auth_config.model_dump(),
                "payment_config": deployment_package.payment_config.model_dump() if deployment_package.payment_config else None,
                "deployment_config": deployment_package.deployment_config.model_dump(),
                "readme": deployment_package.readme,
                "docker_compose": deployment_package.docker_compose,
                "env_file": deployment_package.env_file,
            },
            "vertical": build_spec.get("business", {}).get("vertical", "unknown"),
        }
    except Exception as e:
        logger.exception(f"Error in generate_deployment: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/extract-assets")
async def extract_assets(
    request: Request,
    payload: str | None = Form(default=None),
    files: list[UploadFile] | None = File(default=None),
) -> dict[str, Any]:
    parsed_payload = await extract_request_payload(request, payload)
    logger.info("Received extract_assets request")
    logger.debug(f"Extract assets payload: {parsed_payload}")

    normalized_extractions = await process_uploaded_files(
        files
    )
    asset_signals = asset_signals_from_extractions(
        normalized_extractions
    )
    planner_status = {
        "mode": "vision_only",
        "degraded": False,
        "reason": "",
        "failure_count": 0,
        "errors": [],
    }
    external_failures = collect_external_failures(
        normalized_extractions,
        planner_status,
    )
    active_provider = get_vision_config()[0]
    vision_mode = (
        "unavailable"
        if any(item.get("processing_status") != "success" for item in normalized_extractions)
        else ("unused" if not normalized_extractions else f"{active_provider}_vision")
    )

    return {
        "source": f"{active_provider}-vision-extraction",
        "assetSignals": asset_signals,
        "assetExtractions": normalized_extractions,
        "visionMode": vision_mode,
        "externalFailures": external_failures,
    }
