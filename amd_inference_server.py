from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import re
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agentic_graph import iter_agent_graph_updates, run_agent_graph
from agentic_models import (
    AssetExtraction,
    CognitiveProvenanceRecord,
    ProvenanceSource,
    ReasoningLineageEntry,
    StateArtifactStatus,
)
from agentic_planner import ModelJsonPlanner
from buildspec_planner import generate_build_spec
from research_agents import ResearchOrchestrator
from code_generator import CodeGenerationOrchestrator
from critique_system import CritiqueOrchestrator
from deployment_system import DeploymentOrchestrator


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler(),
    ],
)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

POLLINATIONS_VISION_URL = "https://gen.pollinations.ai/v1/chat/completions"
POLLINATIONS_VISION_MODEL = os.getenv("POLLINATIONS_VISION_MODEL", os.getenv("pollinations_vision_model", "openai-large"))
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY", os.getenv("pollinations_api_key", ""))
json_planner = None

app.mount("/static", StaticFiles(directory=APP_DIR), name="static")


async def process_image_with_pollinations(image_data: bytes, filename: str) -> dict[str, Any]:
    """Process an image using Pollinations chat-completions vision."""
    try:
        logger.debug(f"Processing image: {filename}")
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
            if POLLINATIONS_API_KEY:
                headers["Authorization"] = f"Bearer {POLLINATIONS_API_KEY}"

            payload = {
                "model": POLLINATIONS_VISION_MODEL,
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

            logger.debug(f"Sending request to pollinations API for {filename}")
            response = await client.post(
                POLLINATIONS_VISION_URL,
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
                f"Pollinations API error for {filename}: Status {response.status_code}, Response: {error_text}"
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

    logger.info("Pollinations.ai vision model ready.")


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
                    "service": "pollinations_vision",
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
            "debate_outcome": None,
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
    vision_mode = (
        "unavailable"
        if any(item.get("processing_status") != "success" for item in normalized_extractions)
        else ("unused" if not normalized_extractions else "pollinations_vision")
    )
    return {
        "source": "pollinations-agent-system",
        "assetSignals": asset_signals,
        "assetExtractions": normalized_extractions,
        "buildSpec": build_spec,
        "graphExecution": agent_state,
        "graphStatus": {
            "status": agent_state.get("status", "completed"),
            "error": agent_state.get("graph_error", ""),
        },
        "plannerMode": planner_status.get("mode", "external_pollinations"),
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
    for error in planner_status.get("errors", []):
        failures.append(
            {
                "service": "pollinations_generate",
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
        initial_graph_state = {
            "business_input": profile,
            "uploaded_asset_paths": [item.get("image", "") for item in normalized_extractions],
            "asset_extractions": [
                AssetExtraction.model_validate(item)
                for item in normalized_extractions
            ],
        }

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

        # Initialize planner if not already done
        global json_planner
        if json_planner is None:
            json_planner = ModelJsonPlanner()

        # Initialize code generation orchestrator
        code_orchestrator = CodeGenerationOrchestrator(json_planner)

        # Generate website code
        generated_code = code_orchestrator.generate_website(build_spec, agent_context=agent_context)

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
    except Exception as e:
        logger.exception(f"Error in generate_code: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


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
    vision_mode = (
        "unavailable"
        if any(item.get("processing_status") != "success" for item in normalized_extractions)
        else ("unused" if not normalized_extractions else "pollinations_vision")
    )

    return {
        "source": "pollinations-vision-extraction",
        "assetSignals": asset_signals,
        "assetExtractions": normalized_extractions,
        "visionMode": vision_mode,
        "externalFailures": external_failures,
    }
