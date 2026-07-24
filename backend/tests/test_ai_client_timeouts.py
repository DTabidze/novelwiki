import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import BaseModel

from app.services.extraction.ai_client import (
    AIEmptyResponseError,
    AIMalformedResponseError,
    get_ai_config,
    parse_ai_json_response,
)


class TinyResponse(BaseModel):
    value: str


class FakeOpenAIResponses:
    def __init__(self):
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=TinyResponse(value="ok"), output_text='{"value":"ok"}')


class FakeChatCompletions:
    def __init__(
        self,
        fail_strict=False,
        failure_message="strict schema not supported",
        content='{"value":"ok"}',
    ):
        self.fail_strict = fail_strict
        self.failure_message = failure_message
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)

        if self.fail_strict and len(self.calls) == 1:
            error = RuntimeError(self.failure_message)
            error.status_code = 400
            raise error

        return SimpleNamespace(
            id="request-1",
            model="served-model",
            provider="served-provider",
            usage=SimpleNamespace(
                prompt_tokens=120,
                completion_tokens=30,
                total_tokens=150,
                prompt_tokens_details=SimpleNamespace(cached_tokens=40),
                completion_tokens_details=SimpleNamespace(reasoning_tokens=10),
            ),
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content),
                    finish_reason="stop",
                )
            ]
        )


class FakeOpenAIClient:
    def __init__(self, chat_completions=None):
        self.responses = FakeOpenAIResponses()
        self.chat = SimpleNamespace(
            completions=chat_completions or FakeChatCompletions()
        )
        self.timeout_options = []

    def with_options(self, **kwargs):
        self.timeout_options.append(kwargs.get("timeout"))
        return self


class AIClientTimeoutTest(unittest.TestCase):
    def test_openai_responses_parse_uses_per_request_timeout(self):
        client = FakeOpenAIClient()

        result = parse_ai_json_response(
            client=client,
            provider="openai",
            model="test-model",
            temperature=0.1,
            system_prompt="system",
            user_content="user",
            schema_model=TinyResponse,
            request_timeout=12,
        )

        self.assertEqual(result.value, "ok")
        self.assertEqual(client.timeout_options, [12])
        self.assertEqual(client.responses.calls[0]["model"], "test-model")

    def test_chat_strict_schema_fallback_reuses_per_request_timeout(self):
        chat_completions = FakeChatCompletions(fail_strict=True)
        client = FakeOpenAIClient(chat_completions=chat_completions)

        result = parse_ai_json_response(
            client=client,
            provider="openrouter",
            model="test-model",
            temperature=0.1,
            system_prompt="system",
            user_content="user",
            schema_model=TinyResponse,
            request_timeout=34,
        )

        self.assertEqual(result.value, "ok")
        self.assertEqual(client.timeout_options, [34])
        self.assertEqual(len(chat_completions.calls), 2)
        self.assertEqual(chat_completions.calls[0]["response_format"]["type"], "json_schema")
        self.assertEqual(chat_completions.calls[1]["response_format"]["type"], "json_object")
        self.assertEqual(chat_completions.calls[0]["messages"][1]["content"], "user")
        self.assertIn(
            "JSON schema to follow:",
            chat_completions.calls[1]["messages"][1]["content"],
        )

    def test_openrouter_provider_routing_is_sent_on_strict_and_fallback_requests(self):
        chat_completions = FakeChatCompletions(fail_strict=True)
        client = FakeOpenAIClient(chat_completions=chat_completions)
        provider_preferences = {
            "order": ["atlas-cloud", "alibaba", "baidu"],
            "allow_fallbacks": True,
        }

        parse_ai_json_response(
            client=client,
            provider="openrouter",
            model="test-model",
            temperature=0.1,
            system_prompt="system",
            user_content="user",
            schema_model=TinyResponse,
            provider_preferences=provider_preferences,
        )

        self.assertEqual(len(chat_completions.calls), 2)
        for call in chat_completions.calls:
            self.assertEqual(
                call["extra_body"],
                {"provider": provider_preferences},
            )

    def test_openrouter_provider_routing_defaults_to_stable_providers_with_fallbacks(self):
        with patch.dict(
            "os.environ",
            {
                "AI_PROVIDER": "openrouter",
                "AI_API_KEY": "test-key",
            },
            clear=True,
        ):
            config = get_ai_config()

        self.assertEqual(
            config["provider_preferences"],
            {
                "order": ["atlas-cloud", "alibaba", "baidu"],
                "allow_fallbacks": True,
            },
        )

    def test_strict_schema_request_does_not_duplicate_schema_in_user_content(self):
        chat_completions = FakeChatCompletions()
        client = FakeOpenAIClient(chat_completions=chat_completions)

        parse_ai_json_response(
            client=client,
            provider="openrouter",
            model="test-model",
            temperature=0.1,
            system_prompt="system",
            user_content="complete chapter",
            schema_model=TinyResponse,
        )

        self.assertEqual(
            chat_completions.calls[0]["messages"][1]["content"],
            "complete chapter",
        )
        self.assertEqual(
            chat_completions.calls[0]["response_format"]["type"],
            "json_schema",
        )

    def test_non_schema_bad_request_does_not_fallback(self):
        chat_completions = FakeChatCompletions(
            fail_strict=True,
            failure_message="invalid model name",
        )
        client = FakeOpenAIClient(chat_completions=chat_completions)

        with self.assertRaisesRegex(RuntimeError, "invalid model name"):
            parse_ai_json_response(
                client=client,
                provider="openrouter",
                model="test-model",
                temperature=0.1,
                system_prompt="system",
                user_content="user",
                schema_model=TinyResponse,
            )

        self.assertEqual(len(chat_completions.calls), 1)

    def test_http_success_with_empty_content_is_named_error(self):
        client = FakeOpenAIClient(
            chat_completions=FakeChatCompletions(content="")
        )

        with self.assertRaises(AIEmptyResponseError) as raised:
            parse_ai_json_response(
                client=client,
                provider="openrouter",
                model="test-model",
                temperature=0.1,
                system_prompt="system",
                user_content="user",
                schema_model=TinyResponse,
            )

        self.assertEqual(raised.exception.code, "empty_ai_response")

    def test_malformed_json_is_named_error(self):
        client = FakeOpenAIClient(
            chat_completions=FakeChatCompletions(content="not json")
        )

        with self.assertRaises(AIMalformedResponseError) as raised:
            parse_ai_json_response(
                client=client,
                provider="openrouter",
                model="test-model",
                temperature=0.1,
                system_prompt="system",
                user_content="user",
                schema_model=TinyResponse,
            )

        self.assertEqual(raised.exception.code, "malformed_ai_response")

    def test_response_telemetry_captures_usage_and_provider(self):
        telemetry = {}
        client = FakeOpenAIClient()

        parse_ai_json_response(
            client=client,
            provider="openrouter",
            model="test-model",
            temperature=0.1,
            system_prompt="system",
            user_content="user",
            schema_model=TinyResponse,
            telemetry=telemetry,
        )

        self.assertEqual(telemetry["request_id"], "request-1")
        self.assertEqual(telemetry["response_model"], "served-model")
        self.assertEqual(telemetry["upstream_provider"], "served-provider")
        self.assertEqual(telemetry["finish_reason"], "stop")
        self.assertEqual(telemetry["prompt_tokens"], 120)
        self.assertEqual(telemetry["completion_tokens"], 30)
        self.assertEqual(telemetry["reasoning_tokens"], 10)
        self.assertEqual(telemetry["cached_tokens"], 40)

    def test_raw_response_log_includes_stage_telemetry(self):
        telemetry = {"stage": "item", "attempt": 1, "chapter_number": 7}
        client = FakeOpenAIClient()

        with tempfile.TemporaryDirectory() as log_dir, patch.dict(
            "os.environ",
            {
                "AI_LOG_RAW_RESPONSES": "true",
                "AI_LOG_DIR": log_dir,
            },
        ):
            parse_ai_json_response(
                client=client,
                provider="openrouter",
                model="test-model",
                temperature=0.1,
                system_prompt="system",
                user_content="user",
                schema_model=TinyResponse,
                telemetry=telemetry,
            )
            log_files = list(Path(log_dir).glob("*.json"))
            self.assertEqual(len(log_files), 1)
            payload = json.loads(log_files[0].read_text(encoding="utf-8"))

        self.assertEqual(payload["telemetry"]["stage"], "item")
        self.assertEqual(payload["telemetry"]["chapter_number"], 7)
        self.assertEqual(payload["telemetry"]["prompt_tokens"], 120)


if __name__ == "__main__":
    unittest.main()
