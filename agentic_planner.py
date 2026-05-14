from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

class PlannerGenerationError(Exception):
    pass


SchemaT = TypeVar(
    "SchemaT",
    bound=BaseModel,
)


def load_local_env() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
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


class ModelJsonPlanner:

    def __init__(
        self,
        model_name: str = "openai-large",
    ) -> None:

        self.pollinations_url = (
            "https://gen.pollinations.ai/v1/chat/completions"
        )

        self.api_key = os.getenv(
            "POLLINATIONS_API_KEY",
            os.getenv(
                "pollinations_api_key",
                "",
            ),
        )

        configured_model = os.getenv(
            "POLLINATIONS_TEXT_MODEL",
            os.getenv(
                "pollinations_text_model",
                "",
            ),
        ).strip()

        self.model_name = (
            configured_model
            or model_name
        )

        self.failure_count = 0

        self.request_errors: list[str] = []

    def begin_request(
        self,
    ) -> None:

        self.failure_count = 0

        self.request_errors = []

    def register_failure(
        self,
        stage: str,
        error: Exception | str,
    ) -> None:

        self.failure_count += 1

        message = f"{stage}: {error}"

        self.request_errors.append(
            message
        )

    def get_health_status(
        self,
    ) -> dict[str, Any]:

        return {
            "mode": "external_pollinations",
            "failure_count": (
                self.failure_count
            ),
            "errors": list(
                self.request_errors
            ),
        }

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
        last_error = None
        for _ in range(2):
            try:
                with httpx.Client() as client:
                    headers = {
                        "Content-Type": "application/json",
                    }
                    if self.api_key:
                        headers["Authorization"] = f"Bearer {self.api_key}"
                    response = client.post(
                        self.pollinations_url,
                        headers=headers,
                        json={
                            "model": self.model_name,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": prompt,
                                        }
                                    ],
                                }
                            ],
                            "temperature": 0,
                            "max_tokens": max_new_tokens,
                        },
                        timeout=60.0
                    )
                    response.raise_for_status()
                    result = response.json()
                    if isinstance(result, dict):
                        choices = result.get("choices")
                        if isinstance(choices, list) and choices:
                            message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
                            content = message.get("content") if isinstance(message, dict) else None
                            if isinstance(content, str) and content.strip():
                                return content
                        return result.get("response", result.get("text", "{}")) or "{}"
                    return str(result) if str(result).strip() else "{}"
            except httpx.HTTPStatusError as e:
                response_text = e.response.text if e.response is not None else ""
                last_error = f"{e} | body={response_text[:500]}"
                continue
            except Exception as e:
                last_error = e
                continue
        if last_error is not None:

            self.register_failure(
                "pollinations_generate",
                last_error,
            )

        raise PlannerGenerationError(
            f"Pollinations API error: "
            f"{last_error}"
        )


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

    array_match = re.search(
        r"\[.*\]",
        cleaned,
        flags=re.DOTALL,
    )

    if array_match:
        candidates.append(
            array_match.group(0)
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

    parsed_root = try_parse_json_root(
        cleaned
    )
    if isinstance(parsed_root, list):
        return {
            "items": parsed_root
        }

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


def try_parse_json_root(
    text: str,
) -> Any:

    for candidate in dedupe_strings(
        [
            text,
            repair_json_like_text(text),
            strip_trailing_commas(text),
        ]
    ):

        try:
            return json.loads(
                candidate
            )
        except json.JSONDecodeError:
            pass

        try:
            return ast.literal_eval(
                candidate
            )
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
