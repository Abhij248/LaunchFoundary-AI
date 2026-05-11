from __future__ import annotations

import ast
import json
import re
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError


SchemaT = TypeVar(
    "SchemaT",
    bound=BaseModel,
)


class ModelJsonPlanner:

    def __init__(
        self,
        model_name: str = "phi3:mini",
    ) -> None:

        self.model_name = (
            model_name
        )
        self.pollinations_url = "https://pollinations.ai/api/generate"

    def generate_model(
        self,
        prompt: str,
        schema_model: type[SchemaT],
        max_new_tokens: int = 180,
    ) -> SchemaT:
        
        prompt += """

                CRITICAL OUTPUT RULES:
                - Keep outputs concise
                - Avoid deeply nested structures
                - Avoid verbose evidence summaries
                - Return ONLY raw JSON
                - No markdown
                - No explanations
                - No comments
                - No confidence narratives
                - No prose outside JSON
                - Do not explain fields
                - Do not justify assumptions
                - Do not add text after JSON
                - All property values must be valid JSON values only

                """


        raw = self.generate_text(
            prompt,
            max_new_tokens=max_new_tokens,
        )

        parsed = parse_json_object(
            raw
        )

        try:

            return schema_model.model_validate(
                parsed
            )

        except ValidationError as exc:

            retry_prompt = (
                prompt
                + "\n\n"
                + "Your previous response "
                + "did not validate.\n"
                + "Return ONLY valid JSON.\n"
                + "Do not include explanations.\n"
                + f"Validation error: {exc}"
            )

            retry_raw = (
                self.generate_text(
                    retry_prompt,
                    max_new_tokens=max_new_tokens,
                )
            )

            retry_parsed = (
                parse_json_object(
                    retry_raw
                )
            )

            return schema_model.model_validate(
                retry_parsed
            )

    def generate_text(
        self,
        prompt: str,
        max_new_tokens: int = 500,
    ) -> str:
        try:
            with httpx.Client() as client:
                response = client.post(
                    self.pollinations_url,
                    json={
                        "prompt": prompt,
                        "model": self.model_name,
                        "max_new_tokens": max_new_tokens,
                        "temperature": 0,
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                result = response.json()
                if isinstance(result, dict):
                    return result.get("response", result.get("text", "{}")) or "{}"
                return str(result) if str(result).strip() else "{}"
        except Exception as e:
            print(f"Pollinations API error: {e}")
            return "{}"


def parse_json_object(
    text: str,
) -> dict[str, Any]:

    cleaned = text.strip()

    cleaned = re.sub(
        r"^```(?:json)?",
        "",
        cleaned,
    ).strip()

    cleaned = re.sub(
        r"```$",
        "",
        cleaned,
    ).strip()

    candidates = [cleaned]

    match = re.search(
        r"\{.*\}",
        cleaned,
        flags=re.DOTALL,
    )

    if match:
        candidates.append(
            match.group(0)
        )

    for candidate in dedupe_strings(
        candidates
    ):

        parsed = (
            try_parse_json_candidate(
                candidate
            )
        )

        if parsed is not None:
            return parsed

    raise ValueError(
        f"model did not return parseable JSON: "
        f"{cleaned[:500]}"
    )


def try_parse_json_candidate(
    text: str,
) -> dict[str, Any] | None:

    for candidate in dedupe_strings(
        [
            text,
            repair_json_like_text(text),
            strip_trailing_commas(text),
        ]
    ):

        try:

            parsed = json.loads(
                candidate
            )

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            pass

        try:

            literal = ast.literal_eval(
                candidate
            )

            if isinstance(literal, dict):
                return literal

        except (
            ValueError,
            SyntaxError,
        ):
            pass

    return None


def repair_json_like_text(
    text: str,
) -> str:

    repaired = text.strip()

    repaired = re.sub(
        r"//.*",
        "",
        repaired,
    )

    repaired = strip_trailing_commas(
        repaired
    )

    repaired = re.sub(
        r"\bTrue\b",
        "true",
        repaired,
    )

    repaired = re.sub(
        r"\bFalse\b",
        "false",
        repaired,
    )

    repaired = re.sub(
        r"\bNone\b",
        "null",
        repaired,
    )

    repaired = re.sub(
        r'(?<=\{|,)\s*([A-Za-z_][A-Za-z0-9_]*)\s*:',
        r' "\1":',
        repaired,
    )

    return repaired

def strip_trailing_commas(
    text: str,
) -> str:

    return re.sub(
        r",(\s*[\]}])",
        r"\1",
        text,
    )


def dedupe_strings(
    values: list[str],
) -> list[str]:

    seen: set[str] = set()

    unique: list[str] = []

    for value in values:

        if value in seen:
            continue

        seen.add(value)

        unique.append(value)

    return unique
