import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}
DEFAULT_AI_REQUEST_TIMEOUT = 180.0
DEFAULT_AI_CONNECT_TIMEOUT = 10.0
DEFAULT_AI_READ_TIMEOUT = 180.0
DEFAULT_AI_STAGE_HARD_TIMEOUT = 210.0
DEFAULT_AI_STAGE_HEARTBEAT_INTERVAL = 30.0
DEFAULT_AI_STAGE_MAX_RETRIES = 1
DEFAULT_OPENROUTER_PROVIDER_ORDER = ("atlas-cloud", "alibaba", "baidu")


class AIEmptyResponseError(RuntimeError):
    code = "empty_ai_response"


class AIMalformedResponseError(RuntimeError):
    code = "malformed_ai_response"


def get_positive_float_env(name, default):
    raw_timeout = os.getenv(name, str(default)).strip()
    try:
        timeout = float(raw_timeout)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive number of seconds.") from exc

    if timeout <= 0:
        raise RuntimeError(f"{name} must be a positive number of seconds.")

    return timeout


def get_non_negative_int_env(name, default):
    raw_value = os.getenv(name, str(default)).strip()

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a non-negative integer.") from exc

    if value < 0:
        raise RuntimeError(f"{name} must be a non-negative integer.")

    return value


def get_boolean_env(name, default):
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    normalized_value = raw_value.strip().lower()

    if normalized_value in TRUTHY_ENV_VALUES:
        return True

    if normalized_value in {"0", "false", "no", "off"}:
        return False

    raise RuntimeError(f"{name} must be a boolean value.")


def get_openrouter_provider_preferences():
    raw_order = os.getenv("OPENROUTER_PROVIDER_ORDER")
    order = (
        list(DEFAULT_OPENROUTER_PROVIDER_ORDER)
        if raw_order is None
        else [provider.strip() for provider in raw_order.split(",") if provider.strip()]
    )

    if not order:
        return None

    return {
        "order": order,
        "allow_fallbacks": get_boolean_env(
            "OPENROUTER_ALLOW_FALLBACKS",
            True,
        ),
    }


def get_ai_request_timeout():
    return get_positive_float_env("AI_REQUEST_TIMEOUT", DEFAULT_AI_REQUEST_TIMEOUT)


def get_ai_timeout_config():
    return {
        "request_timeout": get_ai_request_timeout(),
        "connect_timeout": get_positive_float_env(
            "AI_CONNECT_TIMEOUT",
            DEFAULT_AI_CONNECT_TIMEOUT,
        ),
        "read_timeout": get_positive_float_env(
            "AI_READ_TIMEOUT",
            DEFAULT_AI_READ_TIMEOUT,
        ),
        "stage_hard_timeout": get_positive_float_env(
            "AI_STAGE_HARD_TIMEOUT",
            DEFAULT_AI_STAGE_HARD_TIMEOUT,
        ),
        "stage_heartbeat_interval": get_positive_float_env(
            "AI_STAGE_HEARTBEAT_INTERVAL",
            DEFAULT_AI_STAGE_HEARTBEAT_INTERVAL,
        ),
        "stage_max_retries": get_non_negative_int_env(
            "AI_STAGE_MAX_RETRIES",
            DEFAULT_AI_STAGE_MAX_RETRIES,
        ),
    }


def build_request_timeout(timeout_config):
    try:
        import httpx
    except ImportError:
        return timeout_config["request_timeout"]

    return httpx.Timeout(
        timeout_config["request_timeout"],
        connect=timeout_config["connect_timeout"],
        read=timeout_config["read_timeout"],
        write=min(timeout_config["connect_timeout"], timeout_config["request_timeout"]),
        pool=timeout_config["connect_timeout"],
    )


def get_ai_config():
    provider = os.getenv("AI_PROVIDER", "openai").strip().lower()

    if provider == "openai":
        api_key = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY")
        model = os.getenv("AI_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        base_url = os.getenv("AI_BASE_URL") or None
        missing_message = "OPENAI_API_KEY or AI_API_KEY is missing from backend/.env"
    elif provider == "openrouter":
        api_key = os.getenv("AI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        model = os.getenv("AI_MODEL", "deepseek/deepseek-v4-flash")
        base_url = os.getenv("AI_BASE_URL", "https://openrouter.ai/api/v1")
        missing_message = "AI_API_KEY or OPENROUTER_API_KEY is missing from backend/.env"
    elif provider == "deepseek":
        api_key = os.getenv("AI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        model = os.getenv("AI_MODEL", "deepseek-v4-flash")
        base_url = os.getenv("AI_BASE_URL", "https://api.deepseek.com")
        missing_message = "AI_API_KEY or DEEPSEEK_API_KEY is missing from backend/.env"
    else:
        api_key = os.getenv("AI_API_KEY")
        model = os.getenv("AI_MODEL")
        base_url = os.getenv("AI_BASE_URL") or None
        missing_message = "AI_API_KEY is missing from backend/.env"

        if not model:
            raise RuntimeError("AI_MODEL is missing from backend/.env")

    if not api_key:
        raise RuntimeError(missing_message)

    timeout_config = get_ai_timeout_config()

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "provider": provider,
        **timeout_config,
        "sdk_timeout": build_request_timeout(timeout_config),
        "temperature": float(os.getenv("AI_TEMPERATURE", "0.1")),
        "provider_preferences": (
            get_openrouter_provider_preferences()
            if provider == "openrouter"
            else None
        ),
    }


def response_value(value, *names):
    for name in names:
        if isinstance(value, dict) and name in value:
            return value[name]

        attribute = getattr(value, name, None)
        if attribute is not None:
            return attribute

    return None


def response_usage_telemetry(response):
    usage = getattr(response, "usage", None)

    if not usage:
        return {}

    prompt_details = response_value(usage, "prompt_tokens_details", "input_tokens_details")
    completion_details = response_value(
        usage,
        "completion_tokens_details",
        "output_tokens_details",
    )
    return {
        "prompt_tokens": response_value(usage, "prompt_tokens", "input_tokens"),
        "completion_tokens": response_value(
            usage,
            "completion_tokens",
            "output_tokens",
        ),
        "total_tokens": response_value(usage, "total_tokens"),
        "cached_tokens": response_value(prompt_details, "cached_tokens"),
        "reasoning_tokens": response_value(completion_details, "reasoning_tokens"),
    }


def update_response_telemetry(telemetry, response, strict_schema_fallback=False):
    if telemetry is None:
        return

    choices = getattr(response, "choices", None) or []
    first_choice = choices[0] if choices else None
    telemetry.update(
        {
            "request_id": getattr(response, "id", None),
            "response_model": getattr(response, "model", None),
            "upstream_provider": getattr(response, "provider", None),
            "finish_reason": getattr(first_choice, "finish_reason", None),
            "strict_schema_fallback": strict_schema_fallback,
            **response_usage_telemetry(response),
        }
    )


def schema_fallback_is_supported(error):
    if getattr(error, "status_code", None) not in {400, 422}:
        return False

    error_text = " ".join(
        str(value or "")
        for value in (
            error,
            getattr(error, "body", None),
            getattr(getattr(error, "response", None), "text", None),
        )
    ).lower()
    return any(
        marker in error_text
        for marker in (
            "json schema",
            "json_schema",
            "response format",
            "response_format",
            "schema not supported",
            "strict schema",
            "structured output",
        )
    )


def textual_schema_user_content(user_content, schema_model):
    return (
        f"{user_content}\n\n"
        "JSON schema to follow:\n"
        f"{json.dumps(schema_model.model_json_schema(), ensure_ascii=False)}"
    )


def validate_json_content(schema_model, content):
    if not str(content or "").strip():
        raise AIEmptyResponseError("AI provider returned HTTP success with empty content.")

    try:
        return schema_model.model_validate_json(extract_json_content(content))
    except AIEmptyResponseError:
        raise
    except Exception as error:
        raise AIMalformedResponseError(
            f"AI response did not match {schema_model.__name__}: {error}"
        ) from error


def parse_ai_json_response(
    client,
    provider,
    model,
    temperature,
    system_prompt,
    user_content,
    schema_model,
    request_timeout=None,
    telemetry=None,
    provider_preferences=None,
):
    request_client = client.with_options(timeout=request_timeout) if request_timeout is not None else client
    schema_json = json.dumps(schema_model.model_json_schema(), ensure_ascii=False)

    if telemetry is not None:
        telemetry.update(
            {
                "system_prompt_chars": len(system_prompt or ""),
                "user_content_chars": len(user_content or ""),
                "schema_chars": len(schema_json),
                "strict_schema_fallback": False,
            }
        )

    if provider == "openai":
        response = request_client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            text_format=schema_model,
        )
        content = getattr(response, "output_text", "") or ""
        update_response_telemetry(telemetry, response)
        log_ai_response(
            provider,
            model,
            schema_model,
            content,
            telemetry=telemetry,
        )
        parsed = getattr(response, "output_parsed", None)

        if parsed is not None:
            return parsed

        return validate_json_content(schema_model, content)

    messages = [
        {
            "role": "system",
            "content": (
                f"{system_prompt}\n\n"
                "Return only valid JSON matching the requested schema. Do not wrap it in markdown."
            ),
        },
        {
            "role": "user",
            "content": user_content,
        },
    ]
    strict_schema_fallback = False
    provider_routing = (
        {"extra_body": {"provider": provider_preferences}}
        if provider == "openrouter" and provider_preferences
        else {}
    )

    try:
        response = request_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_model.__name__,
                    "schema": schema_model.model_json_schema(),
                    "strict": True,
                },
            },
            **provider_routing,
        )
    except Exception as exc:
        if not schema_fallback_is_supported(exc):
            raise

        strict_schema_fallback = True
        fallback_messages = [
            messages[0],
            {
                "role": "user",
                "content": textual_schema_user_content(user_content, schema_model),
            },
        ]
        response = request_client.chat.completions.create(
            model=model,
            messages=fallback_messages,
            temperature=temperature,
            response_format={"type": "json_object"},
            **provider_routing,
        )

    content = response.choices[0].message.content or ""
    update_response_telemetry(
        telemetry,
        response,
        strict_schema_fallback=strict_schema_fallback,
    )
    log_ai_response(
        provider,
        model,
        schema_model,
        content,
        telemetry=telemetry,
    )
    return validate_json_content(schema_model, content)


def log_ai_response(provider, model, schema_model, content, telemetry=None):
    if os.getenv("AI_LOG_RAW_RESPONSES", "").strip().lower() not in TRUTHY_ENV_VALUES:
        return

    log_dir = Path(os.getenv("AI_LOG_DIR", "backend/instance/ai_logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    schema_name = getattr(schema_model, "__name__", "AIResponse")
    safe_model = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in model
    ).strip("-")
    filename = f"{timestamp}-{provider}-{safe_model}-{schema_name}-{uuid4().hex[:8]}.json"
    payload = {
        "timestamp": timestamp,
        "provider": provider,
        "model": model,
        "schema": schema_name,
        "content": content,
        "telemetry": dict(telemetry or {}),
    }

    (log_dir / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_json_content(content):
    stripped = content.strip()

    if stripped.startswith("```"):
        lines = stripped.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]

        stripped = "\n".join(lines).strip()

    if stripped.startswith("{"):
        return stripped

    start = stripped.find("{")
    end = stripped.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise RuntimeError("AI response did not contain valid JSON")

    return stripped[start : end + 1]
