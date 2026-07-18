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


def parse_temperature(
    value: str | float | int | None,
    fallback: float,
) -> float:
    try:
        if value is None:
            return fallback
        return clamp_temperature(
            float(value)
        )
    except (TypeError, ValueError):
        return fallback


def clamp_temperature(
    value: float,
) -> float:
    return max(
        0.0,
        min(
            1.2,
            float(value),
        ),
    )


PROVIDER_CONFIG = {
    "xai": {
        "url": "https://api.x.ai/v1/chat/completions",
        "key_env": ("XAI_API_KEY", "xai_api_key"),
        "model_env": ("XAI_TEXT_MODEL", "xai_text_model"),
        "default_model": "grok-code-fast-1",
        "best_model_env": ("XAI_BEST_MODEL", "xai_best_model"),
        # grok-4.5 is flagship but reasoning-heavy — it burned its entire
        # completion budget on hidden reasoning tokens and still hit the
        # length cap mid-CSS on a real generation run (finish_reason:
        # "length" at 16000 tokens). grok-4.20-0309-non-reasoning is also
        # flagship-tier, spends 0 tokens on hidden reasoning, and completed
        # the same class of long-form HTML/CSS/JS generation naturally
        # (finish_reason: "stop") well under budget — more reliable for a
        # single large-output generation task like this one.
        "default_best_model": "grok-4.20-0309-non-reasoning",
        "vision_model_env": ("XAI_VISION_MODEL", "xai_vision_model"),
        "default_vision_model": "grok-4.20-0309-non-reasoning",
    },
    "pollinations": {
        "url": "https://gen.pollinations.ai/v1/chat/completions",
        "key_env": ("POLLINATIONS_API_KEY", "pollinations_api_key"),
        "model_env": ("POLLINATIONS_TEXT_MODEL", "pollinations_text_model"),
        "default_model": "openai-large",
        "vision_model_env": ("POLLINATIONS_VISION_MODEL", "pollinations_vision_model"),
        "default_vision_model": "openai-large",
    },
}


def get_active_provider() -> str:
    default_provider = (
        "xai"
        if os.getenv("XAI_API_KEY", os.getenv("xai_api_key", ""))
        else "pollinations"
    )

    provider = os.getenv(
        "LLM_PROVIDER",
        os.getenv("llm_provider", default_provider),
    ).strip().lower()

    if provider not in PROVIDER_CONFIG:
        provider = default_provider

    return provider


def get_vision_config() -> tuple[str, str, str, str]:
    """Return (provider, url, model, api_key) for the active vision backend."""

    provider = get_active_provider()
    config = PROVIDER_CONFIG[provider]

    key_env, legacy_key_env = config["key_env"]
    api_key = os.getenv(key_env, os.getenv(legacy_key_env, ""))

    model_env, legacy_model_env = config["vision_model_env"]
    model = (
        os.getenv(model_env, os.getenv(legacy_model_env, "")).strip()
        or config["default_vision_model"]
    )

    return provider, config["url"], model, api_key


class ModelJsonPlanner:

    def __init__(
        self,
        model_name: str | None = None,
    ) -> None:

        self.provider = get_active_provider()

        config = PROVIDER_CONFIG[self.provider]

        self.pollinations_url = config["url"]

        primary_key_env, legacy_key_env = config["key_env"]
        self.api_key = os.getenv(
            primary_key_env,
            os.getenv(legacy_key_env, ""),
        )

        primary_model_env, legacy_model_env = config["model_env"]
        configured_model = os.getenv(
            primary_model_env,
            os.getenv(legacy_model_env, ""),
        ).strip()

        self.model_name = (
            configured_model
            or model_name
            or config["default_model"]
        )

        self.failure_count = 0

        self.request_errors: list[str] = []

        self.default_temperature = parse_temperature(
            os.getenv(
                "POLLINATIONS_TEXT_TEMPERATURE",
                os.getenv(
                    "pollinations_text_temperature",
                    "0.2",
                ),
            ),
            fallback=0.2,
        )

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
            "mode": f"external_{self.provider}",
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
        temperature: float | None = None,
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
            temperature=temperature,
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
                    temperature=0.1,
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

    def best_model_name(self) -> str:
        config = PROVIDER_CONFIG[self.provider]
        model_env, legacy_model_env = config.get("best_model_env", (None, None))
        configured = (
            os.getenv(model_env, os.getenv(legacy_model_env, ""))
            if model_env
            else ""
        ).strip()
        return configured or config.get("default_best_model") or self.model_name

    def generate_text(
        self,
        prompt: str,
        max_new_tokens: int = 500,
        temperature: float | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> str:
        request_temperature = clamp_temperature(
            self.default_temperature
            if temperature is None
            else temperature
        )
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
                            "model": model or self.model_name,
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
                            "temperature": request_temperature,
                            "max_tokens": max_new_tokens,
                        },
                        timeout=timeout
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
                f"{self.provider}_generate",
                last_error,
            )

        raise PlannerGenerationError(
            f"{self.provider} API error: "
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
