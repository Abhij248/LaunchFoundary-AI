from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agentic_graph import run_agent_graph
from agentic_models import AssetExtraction
from agentic_planner import ModelJsonPlanner
from buildspec_planner import generate_build_spec


app = FastAPI(title="LaunchFoundry AMD Inference API")
APP_DIR = Path(__file__).resolve().parent

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pollinations.ai vision model endpoint
POLLINATIONS_VISION_URL = "https://pollinations.ai/api/image-to-text"
json_planner = None

app.mount("/static", StaticFiles(directory=APP_DIR), name="static")


async def process_image_with_pollinations(image_data: bytes, filename: str) -> dict[str, Any]:
    """Process an image using pollinations.ai vision model."""
    try:
        # Prepare the request to pollinations.ai
        # Note: This is a simplified version - you may need to adjust based on the actual API requirements
        async with httpx.AsyncClient() as client:
            # Create a multipart form data request
            files = {
                'image': (filename, image_data, 'image/jpeg')  # Adjust content type as needed
            }
            
            # Send request to pollinations.ai
            response = await client.post(
                POLLINATIONS_VISION_URL,
                files=files,
                timeout=30.0
            )
            
            if response.status_code == 200:
                # Parse the response
                result = response.json()
                return {
                    "image": filename,
                    "parsed": result,
                    "status": "success"
                }
            else:
                return {
                    "image": filename,
                    "error": f"API request failed with status {response.status_code}",
                    "status": "error"
                }
                
    except Exception as e:
        return {
            "image": filename,
            "error": str(e),
            "status": "error"
        }


@app.on_event("startup")
def startup() -> None:

    global json_planner

    json_planner = (
        ModelJsonPlanner(
            "phi3:mini"
        )
    )

    print(
        "Pollinations.ai vision model ready."
    )

@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "vision_model_loaded": True,
    }


@app.get("/")
def frontend() -> FileResponse:
    return FileResponse(APP_DIR / "index.html")


@app.get("/app.js")
def frontend_js() -> FileResponse:
    return FileResponse(APP_DIR / "app.js", media_type="application/javascript")


@app.get("/styles.css")
def frontend_css() -> FileResponse:
    return FileResponse(APP_DIR / "styles.css", media_type="text/css")


@app.get("/jupyter-preview")
def frontend_preview() -> FileResponse:
    return FileResponse(APP_DIR / "jupyter_preview.html")


def normalize_asset_extraction_payload(item: dict[str, Any]) -> dict[str, Any]:
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
    return {
        "image": item.get("image", ""),
        **parsed,
    }


def normalize_string_list(value: Any) -> list[str]:
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
    return normalized


def normalize_prices(value: Any) -> list[str | float | int | list[float | int]]:
    if not isinstance(value, list):
        return []

    normalized: list[str | float | int | list[float | int]] = []
    for entry in value:
        parsed = normalize_price_entry(entry)
        if parsed is None:
            continue
        normalized.append(parsed)
    return normalized


def normalize_price_entry(value: Any) -> str | float | int | list[float | int] | None:
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


def extract_numeric_values(text: str) -> list[float | int]:
    matches = re.findall(r"\d+(?:\.\d+)?", text)
    values: list[float | int] = []
    for match in matches:
        number = float(match) if "." in match else int(match)
        values.append(number)
    return values



@app.post("/generate-buildspec")
async def generate_buildspec(
    payload: dict,
    files: list[UploadFile] = File(default=None)
) -> dict[str, Any]:

    # Handle both direct payload and nested payload structure
    if "payload" in payload:
        profile = payload["payload"].get(
            "business_input",
            {},
        )
    else:
        profile = payload.get(
            "business_input",
            {},
        )

    business_details = (
        profile.get(
            "details",
            "",
        )
    )

    # Process uploaded assets with pollinations.ai vision model
    extractions = []
    asset_signals = ""
    
    # Process uploaded files if any
    if files:
        for file in files:
            try:
                # Read file content
                image_data = await file.read()
                
                # Process with pollinations.ai
                result = await process_image_with_pollinations(image_data, file.filename)
                
                if result["status"] == "success":
                    extractions.append(result)
                    # Add asset signals to the overall signals
                    parsed = result.get("parsed", {})
                    business_signals = parsed.get("business_signals", [])
                    if business_signals:
                        asset_signals += f"File: {file.filename}\n"
                        asset_signals += f"Signals: {', '.join(business_signals[:5])}\n\n"
                        
            except Exception as e:
                print(f"Error processing file {file.filename}: {e}")
                # Continue processing other files even if one fails

    enriched_details = (
        "\n\n".join(
            part
            for part in [
                business_details,
                asset_signals,
            ]
            if part.strip()
        )
    )

    build_spec = generate_build_spec(
        profile,
        enriched_details,
    )

    validated_extractions = []

    agent_state = run_agent_graph(
        {
            "business_input": profile,

            "uploaded_asset_paths": [file.filename for file in files] if files else [],

            "asset_extractions": extractions,
        },

        planner=json_planner,
    )

    return {
        "source":
            "local-qwen-agent-system",

        "assetSignals":
            asset_signals,

        "assetExtractions":
            extractions,

        "buildSpec":
            build_spec,

        "graphExecution":
            agent_state,
    }
