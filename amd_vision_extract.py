from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import torch
from qwen_vl_utils import process_vision_info
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration


MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"


EXTRACTION_PROMPT = """
You are the multimodal intake agent for an autonomous AI web agency.

Analyze the uploaded business image. It may be a restaurant menu, flyer, brochure,
storefront photo, service list, clinic leaflet, price list, business card, or other
business asset.

Return only valid JSON with this exact shape:
{
  "asset_type": "menu | brochure | flyer | storefront | service_list | business_card | clinic_document | unknown",
  "business_signals": ["short signal"],
  "extracted_business_info": {
    "business_name": null,
    "phone": null,
    "email": null,
    "address": null,
    "hours": null,
    "services_or_items": [],
    "prices": [],
    "offers": []
  },
  "recommended_pages": [],
  "recommended_features": [],
  "trust_or_compliance_notes": [],
  "visual_brand_cues": [],
  "planner_notes": "one concise paragraph explaining how this asset should influence the website and backend"
}

Do not invent details that are not visible. Use null or empty arrays when uncertain.
"""


def load_model(model_id: str = MODEL_ID) -> tuple[Qwen2_5_VLForConditionalGeneration, AutoProcessor]:
    if not torch.cuda.is_available():
        raise RuntimeError("PyTorch cannot see the AMD GPU. On ROCm, torch.cuda.is_available() should be True.")

    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_id,
        torch_dtype="auto",
        device_map="auto",
    )
    processor = AutoProcessor.from_pretrained(
        model_id,
        min_pixels=256 * 28 * 28,
        max_pixels=1280 * 28 * 28,
    )
    return model, processor


def extract_asset_info(
    image_path: str | Path,
    model: Qwen2_5_VLForConditionalGeneration,
    processor: AutoProcessor,
    model_id: str = MODEL_ID,
    max_new_tokens: int = 700,
) -> dict[str, Any]:
    path = Path(image_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": path.as_uri()},
                {"type": "text", "text": EXTRACTION_PROMPT},
            ],
        }
    ]

    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to("cuda")

    with torch.inference_mode():
        generated_ids = model.generate(**inputs, max_new_tokens=max_new_tokens)

    generated_ids_trimmed = [
        out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output_text = processor.batch_decode(
        generated_ids_trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0]

    return {
        "image": str(path),
        "model": model_id,
        "raw_output": output_text,
        "parsed": parse_json_object(output_text),
    }


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return {
                "asset_type": "unknown",
                "business_signals": ["model returned non-json output"],
                "extracted_business_info": {},
                "recommended_pages": [],
                "recommended_features": [],
                "trust_or_compliance_notes": [],
                "visual_brand_cues": [],
                "planner_notes": cleaned[:1000],
            }
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            salvage = salvage_partial_fields(cleaned)
            salvage["business_signals"] = salvage.get("business_signals") or ["partial structured output recovered"]
            salvage["planner_notes"] = salvage.get("planner_notes") or cleaned[:1000]
            return salvage


def salvage_partial_fields(text: str) -> dict[str, Any]:
    def capture_string(field: str) -> str | None:
        match = re.search(rf'"{field}"\s*:\s*"([^"]*)"', text)
        return match.group(1).strip() if match else None

    def capture_string_array(field: str, limit: int = 12) -> list[str]:
        match = re.search(rf'"{field}"\s*:\s*\[(.*?)\]', text, flags=re.DOTALL)
        if not match:
            return []
        items = re.findall(r'"([^"]+)"', match.group(1))
        return [item.strip() for item in items[:limit] if item.strip()]

    def capture_price_array(limit: int = 12) -> list[float]:
        match = re.search(r'"prices"\s*:\s*\[(.*?)\]', text, flags=re.DOTALL)
        if not match:
            return []
        values = re.findall(r"-?\d+(?:\.\d+)?", match.group(1))
        return [float(value) for value in values[:limit]]

    extracted_info = {
        "business_name": capture_string("business_name"),
        "phone": capture_string("phone"),
        "email": capture_string("email"),
        "address": capture_string("address"),
        "hours": capture_string("hours"),
        "services_or_items": capture_string_array("services_or_items"),
        "prices": capture_price_array(),
        "offers": capture_string_array("offers"),
    }

    return {
        "asset_type": capture_string("asset_type") or "unknown",
        "business_signals": capture_string_array("business_signals"),
        "extracted_business_info": extracted_info,
        "recommended_pages": capture_string_array("recommended_pages"),
        "recommended_features": capture_string_array("recommended_features"),
        "trust_or_compliance_notes": capture_string_array("trust_or_compliance_notes"),
        "visual_brand_cues": capture_string_array("visual_brand_cues"),
        "planner_notes": capture_string("planner_notes") or "",
    }


def summarize_for_buildspec(extractions: list[dict[str, Any]]) -> str:
    lines = ["Extracted asset signals:"]
    for item in extractions:
        parsed = item.get("parsed", {})
        lines.append(f"File: {Path(item['image']).name}")
        lines.append(f"Asset type: {parsed.get('asset_type', 'unknown')}")
        for signal in parsed.get("business_signals", []):
            lines.append(f"- Signal: {signal}")
        info = parsed.get("extracted_business_info", {})
        services = info.get("services_or_items") if isinstance(info, dict) else []
        prices = info.get("prices") if isinstance(info, dict) else []
        if services:
            lines.append(f"- Services/items visible: {', '.join(map(str, dedupe_keep_order(services)[:12]))}")
        if prices:
            lines.append(f"- Prices visible: {', '.join(format_prices(prices[:12]))}")
        for feature in parsed.get("recommended_features", []):
            lines.append(f"- Recommended feature: {feature}")
        for note in parsed.get("trust_or_compliance_notes", []):
            lines.append(f"- Trust/compliance: {note}")
        if parsed.get("planner_notes"):
            lines.append(f"- Planner note: {parsed['planner_notes']}")
    return "\n".join(lines)


def dedupe_keep_order(values: list[Any]) -> list[Any]:
    seen = set()
    output = []
    for value in values:
        key = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def format_prices(values: list[Any]) -> list[str]:
    formatted = []
    for value in values:
        if isinstance(value, list):
            numbers = [str(item) for item in value[:4]]
            formatted.append("[" + ", ".join(numbers) + "]")
        else:
            formatted.append(str(value))
    return formatted


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract business signals from images with Qwen2.5-VL on AMD GPU.")
    parser.add_argument("images", nargs="+", help="Image paths to analyze.")
    parser.add_argument("--output", default="asset-extractions.json", help="JSON output file.")
    args = parser.parse_args()

    model, processor = load_model()
    results = [extract_asset_info(path, model, processor) for path in args.images]
    Path(args.output).write_text(json.dumps(results, indent=2), encoding="utf-8")
    Path("asset-signals.txt").write_text(summarize_for_buildspec(results), encoding="utf-8")
    print(f"Wrote {args.output}")
    print("Wrote asset-signals.txt")
