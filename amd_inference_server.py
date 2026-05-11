from __future__ import annotations

import json
import logging
import re
import tempfile
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agentic_graph import run_agent_graph
from agentic_models import AssetExtraction
from agentic_planner import ModelJsonPlanner
from buildspec_planner import generate_build_spec


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

POLLINATIONS_VISION_URL = "https://pollinations.ai/api/image-to-text"
json_planner = None

app.mount("/static", StaticFiles(directory=APP_DIR), name="static")


async def process_image_with_pollinations(image_data: bytes, filename: str) -> dict[str, Any]:
    """Process an image using pollinations.ai vision model."""
    try:
        logger.debug(f"Processing image: {filename}")
        async with httpx.AsyncClient() as client:
            files = {
                "image": (filename, image_data, "image/jpeg")
            }

            logger.debug(f"Sending request to pollinations API for {filename}")
            response = await client.post(
                POLLINATIONS_VISION_URL,
                files=files,
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

                return {
                    "image": filename,
                    "parsed": result,
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
            }

    except Exception as e:
        logger.exception(f"Exception in process_image_with_pollinations for {filename}: {e}")
        return {
            "image": filename,
            "error": str(e),
            "status": "error",
        }


@app.on_event("startup")
def startup() -> None:
    logger.info("Starting up AMD inference server")
    global json_planner

    json_planner = ModelJsonPlanner("phi3:mini")

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
        parsed["extracted_business_info"] = info
        result = {
            "image": item.get("image", ""),
            **parsed,
        }
        logger.debug(f"Normalized payload for {item.get('image', 'unknown')}: {result}")
        return result
    except Exception as e:
        logger.exception(f"Error normalizing asset extraction payload: {e}")
        return item


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


def build_fallback_graph_execution(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "final_state": {
            "business_input": profile,
            "uploaded_asset_paths": [],
            "asset_extractions": [],
            "business_profile": None,
            "requirements_spec": None,
            "strategy_hypotheses": [],
            "revision_iteration": 0,
            "candidate_history": [],
            "critique_history": [],
            "design_candidates": [],
            "critique_reports": [],
            "design_spec": None,
            "qa_notes": [],
            "reasoning_notes": [
                "Agent graph fallback mode was used because the external planning model failed.",
            ],
            "reflection_report": None,
            "uncertainty_score": 0.0,
            "debate_outcome": None,
            "simulation_report": None,
        },
        "events": [],
    }


@app.post("/generate-buildspec")
async def generate_buildspec(payload: dict[str, Any]) -> dict[str, Any]:
    logger.info("Received generate_buildspec request")
    logger.debug(f"Request payload: {payload}")

    try:
        profile = payload.get("business_input", {})

        if not profile:
            if "payload" in payload and isinstance(payload["payload"], dict):
                profile = payload["payload"].get("business_input", {})
            elif "business_input" in payload and isinstance(payload["business_input"], dict):
                profile = payload["business_input"]
            elif isinstance(payload, dict):
                profile = payload

        if not profile:
            if isinstance(payload, dict) and "name" in payload and "location" in payload:
                profile = payload
            elif isinstance(payload, dict):
                for key in ["business_input", "payload", "data"]:
                    if key in payload and isinstance(payload[key], dict):
                        profile = payload[key]
                        break

        logger.debug(f"Extracted business profile: {profile}")

        business_details = profile.get("details", "")
        extractions: list[dict[str, Any]] = []
        asset_signals = ""

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
                    "uploaded_asset_paths": [],
                    "asset_extractions": [],
                },
                planner=json_planner,
            )
        except Exception as graph_error:
            logger.exception(f"Agent graph failed, using fallback graph execution: {graph_error}")
            agent_state = build_fallback_graph_execution(profile)

        logger.info("Successfully processed generate_buildspec request")
        return {
            "source": "local-qwen-agent-system",
            "assetSignals": asset_signals,
            "assetExtractions": extractions,
            "buildSpec": build_spec,
            "graphExecution": agent_state,
        }
    except Exception as e:
        logger.exception(f"Error in generate_buildspec: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
