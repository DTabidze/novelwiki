import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from app.models import Chapter, Novel, db
from app.services.ai_extraction_service import (
    extract_chapter_with_ai,
    progression_stage_decision,
)
from app.services.extraction.ai_client import (
    AIEmptyResponseError,
    AIMalformedResponseError,
    get_ai_timeout_config,
)


class ParallelAIExtractionTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        self.novel = Novel(title="Test Novel", original_filename="", file_type="txt")
        db.session.add(self.novel)
        db.session.flush()
        self.chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=1,
            title="Chapter 1",
            content="Nothing important happened.",
            character_count=0,
        )
        db.session.add(self.chapter)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def empty_result_for_schema(self, schema_model):
        schema_name = schema_model.__name__

        if schema_name == "CharacterExtraction":
            return SimpleNamespace(characters=[])
        if schema_name == "SkillExtraction":
            return SimpleNamespace(skills=[], character_skills=[])
        if schema_name == "ItemExtraction":
            return SimpleNamespace(items=[], character_items=[])
        if schema_name in {
            "ProgressionExtraction",
            "ProgressionAuditExtraction",
            "ProgressionReasoningExtraction",
        }:
            return SimpleNamespace(progression_events=[])
        if schema_name == "LifeEventExtraction":
            return SimpleNamespace(life_events=[])

        raise AssertionError(f"Unexpected schema: {schema_name}")

    def extraction_env(self, parallel, **extra):
        env = {
            "AI_API_KEY": "test-key",
            "AI_MODEL": "test-model",
            "AI_PROVIDER": "openai",
            "AI_EXTRACTION_PIPELINE": "multi_stage",
            "AI_PARALLEL_SAFE_STAGES": "true" if parallel else "false",
            "AI_MAX_CONCURRENT_STAGES": "3",
            "AI_CONDITIONAL_PROGRESSION_STAGES": "false",
            "AI_STAGE_MAX_RETRIES": "1",
        }
        env.update({key: str(value) for key, value in extra.items()})
        return patch.dict(
            "os.environ",
            env,
        )

    def test_parallel_safe_stages_start_before_progression(self):
        started = []
        condition = threading.Condition()
        safe_schema_names = {"CharacterExtraction", "SkillExtraction", "ItemExtraction"}

        def parse_side_effect(*, schema_model, **kwargs):
            schema_name = schema_model.__name__

            with condition:
                started.append(schema_name)

                if schema_name in safe_schema_names:
                    condition.notify_all()
                    condition.wait_for(
                        lambda: len([name for name in started if name in safe_schema_names]) == 3,
                        timeout=2,
                    )

            return self.empty_result_for_schema(schema_model)

        with self.extraction_env(parallel=True), patch("openai.OpenAI"), patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ):
            extract_chapter_with_ai(self.novel, self.chapter)

        self.assertEqual(set(started[:3]), safe_schema_names)
        self.assertIn("ProgressionExtraction", started[3:])

    def test_five_base_stages_never_exceed_three_active_requests(self):
        active = 0
        max_active = 0
        lock = threading.Lock()
        base_schema_names = {
            "CharacterExtraction",
            "SkillExtraction",
            "ItemExtraction",
            "ProgressionExtraction",
            "LifeEventExtraction",
        }

        def parse_side_effect(*, schema_model, **kwargs):
            nonlocal active, max_active

            if schema_model.__name__ in base_schema_names:
                with lock:
                    active += 1
                    max_active = max(max_active, active)
                try:
                    time.sleep(0.03)
                finally:
                    with lock:
                        active -= 1

            return self.empty_result_for_schema(schema_model)

        with self.extraction_env(parallel=True), patch("openai.OpenAI"), patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ):
            extract_chapter_with_ai(self.novel, self.chapter)

        self.assertEqual(max_active, 3)

    def test_every_stage_receives_complete_chapter_text(self):
        content_by_schema = {}

        def parse_side_effect(*, schema_model, user_content, **kwargs):
            content_by_schema[schema_model.__name__] = user_content
            return self.empty_result_for_schema(schema_model)

        with self.extraction_env(parallel=True), patch("openai.OpenAI"), patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ):
            extract_chapter_with_ai(self.novel, self.chapter)

        self.assertEqual(len(content_by_schema), 7)
        self.assertTrue(
            all(
                self.chapter.content in user_content
                for user_content in content_by_schema.values()
            )
        )

    def test_empty_response_retries_only_failed_stage(self):
        calls_by_schema = {}
        lock = threading.Lock()

        def parse_side_effect(*, schema_model, **kwargs):
            schema_name = schema_model.__name__
            with lock:
                calls_by_schema[schema_name] = calls_by_schema.get(schema_name, 0) + 1
                call_count = calls_by_schema[schema_name]

            if schema_name == "SkillExtraction" and call_count == 1:
                raise AIEmptyResponseError("empty")

            return self.empty_result_for_schema(schema_model)

        with self.extraction_env(parallel=True), patch("openai.OpenAI"), patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ):
            extract_chapter_with_ai(self.novel, self.chapter)

        self.assertEqual(calls_by_schema["SkillExtraction"], 2)
        self.assertEqual(calls_by_schema["CharacterExtraction"], 1)
        self.assertEqual(calls_by_schema["ItemExtraction"], 1)
        self.assertEqual(calls_by_schema["ProgressionExtraction"], 1)
        self.assertEqual(calls_by_schema["LifeEventExtraction"], 1)

    def test_malformed_response_retries_only_failed_stage(self):
        calls_by_schema = {}

        def parse_side_effect(*, schema_model, **kwargs):
            schema_name = schema_model.__name__
            calls_by_schema[schema_name] = calls_by_schema.get(schema_name, 0) + 1

            if schema_name == "ItemExtraction" and calls_by_schema[schema_name] == 1:
                raise AIMalformedResponseError("malformed")

            return self.empty_result_for_schema(schema_model)

        with self.extraction_env(parallel=True), patch("openai.OpenAI"), patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ):
            extract_chapter_with_ai(self.novel, self.chapter)

        self.assertEqual(calls_by_schema["ItemExtraction"], 2)
        self.assertEqual(calls_by_schema["CharacterExtraction"], 1)
        self.assertEqual(calls_by_schema["SkillExtraction"], 1)

    def test_persistence_begins_after_all_ai_stages_finish(self):
        active = 0
        finished = []
        lock = threading.Lock()

        def parse_side_effect(*, schema_model, **kwargs):
            nonlocal active
            schema_name = schema_model.__name__

            with lock:
                active += 1
            try:
                time.sleep(0.01)
                return self.empty_result_for_schema(schema_model)
            finally:
                with lock:
                    active -= 1
                    finished.append(schema_name)

        def save_side_effect(*args, **kwargs):
            self.assertEqual(active, 0)
            self.assertEqual(
                set(finished),
                {
                    "CharacterExtraction",
                    "SkillExtraction",
                    "ItemExtraction",
                    "ProgressionExtraction",
                    "ProgressionAuditExtraction",
                    "ProgressionReasoningExtraction",
                    "LifeEventExtraction",
                },
            )
            return {}

        with self.extraction_env(parallel=True), patch("openai.OpenAI"), patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ), patch(
            "app.services.ai_extraction_service.save_chapter_extraction",
            side_effect=save_side_effect,
        ):
            extract_chapter_with_ai(self.novel, self.chapter)

    def test_sequential_mode_preserves_existing_stage_order(self):
        started = []

        def parse_side_effect(*, schema_model, **kwargs):
            started.append(schema_model.__name__)
            return self.empty_result_for_schema(schema_model)

        with self.extraction_env(parallel=False), patch("openai.OpenAI"), patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ):
            extract_chapter_with_ai(self.novel, self.chapter)

        self.assertEqual(
            started,
            [
                "CharacterExtraction",
                "ProgressionExtraction",
                "ProgressionAuditExtraction",
                "ProgressionReasoningExtraction",
                "SkillExtraction",
                "ItemExtraction",
                "LifeEventExtraction",
            ],
        )

    def test_parallel_stage_failure_aborts_without_partial_save(self):
        def parse_side_effect(*, schema_model, **kwargs):
            if schema_model.__name__ == "SkillExtraction":
                raise RuntimeError("skill stage exploded")
            return self.empty_result_for_schema(schema_model)

        with self.extraction_env(parallel=True), patch("openai.OpenAI"), patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ):
            with self.assertRaises(RuntimeError):
                extract_chapter_with_ai(self.novel, self.chapter)

    def test_parallel_failure_does_not_wait_for_running_peer(self):
        peer_sleep = 0.5

        def parse_side_effect(*, schema_model, **kwargs):
            if schema_model.__name__ == "CharacterExtraction":
                time.sleep(peer_sleep)
            if schema_model.__name__ == "SkillExtraction":
                raise RuntimeError("terminal failure")
            return self.empty_result_for_schema(schema_model)

        started_at = time.perf_counter()

        with self.extraction_env(
            parallel=True,
            AI_STAGE_MAX_RETRIES=0,
        ), patch("openai.OpenAI"), patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ):
            with self.assertRaises(RuntimeError):
                extract_chapter_with_ai(self.novel, self.chapter)

        self.assertLess(time.perf_counter() - started_at, peer_sleep / 2)

    def test_sdk_retries_are_disabled_and_request_timeout_is_passed(self):
        request_timeouts = []
        clients = []

        def parse_side_effect(*, client, request_timeout, schema_model, **kwargs):
            clients.append(client)
            request_timeouts.append(request_timeout)
            return self.empty_result_for_schema(schema_model)

        with self.extraction_env(parallel=False, AI_REQUEST_TIMEOUT=3), patch(
            "openai.OpenAI"
        ) as openai_class, patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ):
            extract_chapter_with_ai(self.novel, self.chapter)

        self.assertEqual(openai_class.call_count, 1)
        self.assertEqual(openai_class.call_args.kwargs["max_retries"], 0)
        self.assertTrue(all(client is clients[0] for client in clients))
        self.assertTrue(all(timeout is not None for timeout in request_timeouts))

    def test_progression_audit_receives_resolved_timeout_configuration(self):
        audit_timeout = None

        def parse_side_effect(*, request_timeout, schema_model, **kwargs):
            nonlocal audit_timeout

            if schema_model.__name__ == "ProgressionAuditExtraction":
                audit_timeout = request_timeout

            return self.empty_result_for_schema(schema_model)

        with self.extraction_env(
            parallel=False,
            AI_REQUEST_TIMEOUT=137,
            AI_CONNECT_TIMEOUT=7,
            AI_READ_TIMEOUT=131,
            AI_STAGE_HARD_TIMEOUT=149,
            AI_STAGE_MAX_RETRIES=0,
        ), patch("openai.OpenAI") as openai_class, patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ), self.assertLogs(self.app.logger.name, level="INFO") as logs:
            extract_chapter_with_ai(self.novel, self.chapter)

        self.assertIsNotNone(audit_timeout)
        self.assertEqual(getattr(audit_timeout, "connect", None), 7)
        self.assertEqual(getattr(audit_timeout, "read", None), 131)
        self.assertEqual(openai_class.call_args.kwargs["timeout"], audit_timeout)
        self.assertTrue(
            any(
                "AI stage started: progression_audit" in line
                and "request_timeout=137s" in line
                and "connect_timeout=7s" in line
                and "read_timeout=131s" in line
                and "hard_timeout=149s" in line
                for line in logs.output
            )
        )

    def test_hanging_stage_hits_hard_timeout(self):
        def parse_side_effect(*, schema_model, **kwargs):
            if schema_model.__name__ == "CharacterExtraction":
                time.sleep(0.2)
            return self.empty_result_for_schema(schema_model)

        with self.extraction_env(
            parallel=False,
            AI_STAGE_HARD_TIMEOUT=0.05,
            AI_STAGE_HEARTBEAT_INTERVAL=0.01,
            AI_STAGE_MAX_RETRIES=0,
        ), patch("openai.OpenAI"), patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ):
            with self.assertRaisesRegex(RuntimeError, "hard timeout"):
                extract_chapter_with_ai(self.novel, self.chapter)

    def test_hard_timeout_does_not_wait_for_sleeping_worker_to_finish(self):
        worker_sleep = 1.0
        hard_timeout = 0.05
        calls = []

        def parse_side_effect(*, schema_model, **kwargs):
            calls.append(schema_model.__name__)

            if schema_model.__name__ == "CharacterExtraction":
                time.sleep(worker_sleep)
                return SimpleNamespace(
                    characters=[
                        SimpleNamespace(
                            name="Late Character",
                            aliases=[],
                            appearance_type="appeared",
                            metadata=SimpleNamespace(
                                age_text=None,
                                gender=None,
                                race_or_species=None,
                                origin=None,
                                faction_or_affiliation=None,
                                status=None,
                                titles=[],
                            ),
                            description="Late result that must be ignored.",
                            evidence="Late Character appeared.",
                        )
                    ]
                )

            return self.empty_result_for_schema(schema_model)

        started_at = time.perf_counter()

        with self.extraction_env(
            parallel=False,
            AI_STAGE_HARD_TIMEOUT=hard_timeout,
            AI_STAGE_HEARTBEAT_INTERVAL=0.01,
            AI_STAGE_MAX_RETRIES=0,
        ), patch("openai.OpenAI"), patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ):
            with self.assertRaisesRegex(RuntimeError, "hard timeout"):
                extract_chapter_with_ai(self.novel, self.chapter)

        elapsed = time.perf_counter() - started_at

        self.assertLess(elapsed, worker_sleep / 2)
        self.assertEqual(calls, ["CharacterExtraction"])

    def test_stage_heartbeat_logs_while_waiting(self):
        def parse_side_effect(*, schema_model, **kwargs):
            if schema_model.__name__ == "CharacterExtraction":
                time.sleep(0.08)
            return self.empty_result_for_schema(schema_model)

        with self.extraction_env(
            parallel=False,
            AI_STAGE_HARD_TIMEOUT=0.2,
            AI_STAGE_HEARTBEAT_INTERVAL=0.02,
            AI_STAGE_MAX_RETRIES=0,
        ), patch("openai.OpenAI"), patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ), self.assertLogs(self.app.logger.name, level="INFO") as logs:
            extract_chapter_with_ai(self.novel, self.chapter)

        self.assertTrue(any("AI stage heartbeat: character" in line for line in logs.output))

    def test_transient_timeout_retries_at_most_configured_count(self):
        calls_by_schema = {}

        def parse_side_effect(*, schema_model, **kwargs):
            schema_name = schema_model.__name__
            calls_by_schema[schema_name] = calls_by_schema.get(schema_name, 0) + 1

            if schema_name == "CharacterExtraction" and calls_by_schema[schema_name] == 1:
                raise TimeoutError("temporary timeout")

            return self.empty_result_for_schema(schema_model)

        with self.extraction_env(
            parallel=False,
            AI_STAGE_MAX_RETRIES=1,
        ), patch("openai.OpenAI"), patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ):
            extract_chapter_with_ai(self.novel, self.chapter)

        self.assertEqual(calls_by_schema["CharacterExtraction"], 2)

    def test_invalid_request_is_not_retried(self):
        calls = 0

        class InvalidRequestError(RuntimeError):
            status_code = 400

        def parse_side_effect(*, schema_model, **kwargs):
            nonlocal calls
            calls += 1
            if schema_model.__name__ == "CharacterExtraction":
                raise InvalidRequestError("bad request")
            return self.empty_result_for_schema(schema_model)

        with self.extraction_env(
            parallel=False,
            AI_STAGE_MAX_RETRIES=1,
        ), patch("openai.OpenAI"), patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ):
            with self.assertRaises(RuntimeError):
                extract_chapter_with_ai(self.novel, self.chapter)

        self.assertEqual(calls, 1)

    def test_stage_retry_default_is_one_without_env_override(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(get_ai_timeout_config()["stage_max_retries"], 1)

    def test_conditional_progression_is_disabled_by_default(self):
        calls = []

        def parse_side_effect(*, schema_model, **kwargs):
            calls.append(schema_model.__name__)
            return self.empty_result_for_schema(schema_model)

        with self.extraction_env(parallel=True), patch("openai.OpenAI"), patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ):
            extract_chapter_with_ai(self.novel, self.chapter)

        self.assertIn("ProgressionAuditExtraction", calls)
        self.assertIn("ProgressionReasoningExtraction", calls)

    def test_conditional_progression_skips_followups_without_signals(self):
        calls = []

        def parse_side_effect(*, schema_model, **kwargs):
            calls.append(schema_model.__name__)
            return self.empty_result_for_schema(schema_model)

        with self.extraction_env(
            parallel=True,
            AI_CONDITIONAL_PROGRESSION_STAGES="true",
        ), patch("openai.OpenAI"), patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ):
            extract_chapter_with_ai(self.novel, self.chapter)

        self.assertNotIn("ProgressionAuditExtraction", calls)
        self.assertNotIn("ProgressionReasoningExtraction", calls)
        self.assertEqual(len(calls), 5)

    def test_conditional_progression_runs_followups_for_uncovered_signal(self):
        self.chapter.content = "The warrior was about to advance to Level 9."
        db.session.commit()
        calls = []

        def parse_side_effect(*, schema_model, **kwargs):
            calls.append(schema_model.__name__)
            return self.empty_result_for_schema(schema_model)

        with self.extraction_env(
            parallel=True,
            AI_CONDITIONAL_PROGRESSION_STAGES="true",
        ), patch("openai.OpenAI"), patch(
            "app.services.ai_extraction_service.parse_ai_json_response",
            side_effect=parse_side_effect,
        ):
            extract_chapter_with_ai(self.novel, self.chapter)

        self.assertIn("ProgressionAuditExtraction", calls)
        self.assertIn("ProgressionReasoningExtraction", calls)

    def test_direct_progression_support_does_not_require_followups(self):
        event = SimpleNamespace(
            character_name="Arlen Vale",
            progression_type="power_rank",
            old_value=None,
            new_value="Level 3",
            description="Arlen Vale reached Level 3.",
            evidence="Arlen Vale reached Level 3.",
            source_extractor=None,
        )
        decision = progression_stage_decision(
            "Arlen Vale reached Level 3.",
            [event],
        )

        self.assertFalse(decision["run_audit"])
        self.assertFalse(decision["run_reasoning"])
        self.assertEqual(decision["reasons"], ["direct_progression_support"])
