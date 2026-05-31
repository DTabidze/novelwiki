import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


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

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "provider": provider,
        "temperature": float(os.getenv("AI_TEMPERATURE", "0.1")),
    }


def parse_ai_json_response(client, provider, model, temperature, system_prompt, user_content, schema_model):
    if provider == "openai":
        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            text_format=schema_model,
        )
        log_ai_response(provider, model, schema_model, getattr(response, "output_text", ""))
        return response.output_parsed

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
            "content": (
                f"{user_content}\n\n"
                "JSON schema to follow:\n"
                f"{json.dumps(schema_model.model_json_schema(), ensure_ascii=False)}"
            ),
        },
    ]

    try:
        response = client.chat.completions.create(
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
        )
    except Exception as exc:
        if getattr(exc, "status_code", None) not in {400, 422}:
            raise

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )

    content = response.choices[0].message.content or ""
    log_ai_response(provider, model, schema_model, content)
    return schema_model.model_validate_json(extract_json_content(content))


def log_ai_response(provider, model, schema_model, content):
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
