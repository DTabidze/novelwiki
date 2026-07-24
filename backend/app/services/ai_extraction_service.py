import os
import queue
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, is_dataclass
from types import SimpleNamespace

from flask import current_app

from app.models import (
    AIEvidenceAudit,
    Character,
    CharacterItem,
    CharacterSkill,
    CharacterLifeEvent,
    CharacterMetadataProposal,
    CharacterProgressionEvent,
    Chapter,
    Item,
    Novel,
    Skill,
    SkillAlias,
    WikiEvent,
    WikiEvidence,
    db,
)
from app.services.ai_extraction_prompts import (
    BASE_EXTRACTION_SYSTEM_PROMPT,
    CHARACTER_EXTRACTION_PROMPT,
    ITEM_EXTRACTION_PROMPT,
    LIFE_EVENT_EXTRACTION_PROMPT,
    PROGRESSION_AUDIT_PROMPT,
    PROGRESSION_EXTRACTION_PROMPT,
    PROGRESSION_REASONING_PROMPT,
    SKILL_EXTRACTION_PROMPT,
)
from app.services.extraction.ai_client import (
    AIEmptyResponseError,
    AIMalformedResponseError,
    get_ai_config,
    parse_ai_json_response,
)
from app.services.extraction.attribution import (
    attribution_matches_character,
    resolve_character_attribution,
    text_reference_positions,
)
from app.services.extraction.metadata import (
    can_auto_approve_metadata,
    create_character_metadata_proposals,
    metadata_evidence_supports_field,
    metadata_evidence_warnings,
    metadata_result_from_proposal,
    metadata_semantic_warnings,
    revalidate_metadata_proposal,
)
from app.services.extraction.memory import build_extraction_memory
from app.services.extraction.progression import (
    canonicalize_progression_value,
    character_reference_candidates,
    detect_direct_cultivation_progression,
    evidence_mentions_character,
    find_existing_progression,
    is_confirmed_progression,
    is_more_specific_progression_value,
    is_valid_progression_value,
    normalize_progression_type,
    normalized_progression_words,
    progression_compare_key,
    progression_number_from_word,
    progression_review_warnings,
    progression_values_match,
    recalculate_character_current_progression,
)
from app.services.extraction.identity import (
    add_character_alias,
    descriptive_label_key,
    find_existing_character,
    find_existing_character_by_extracted_aliases,
    find_possible_character_spelling_variant,
    find_source_linked_character_variant,
    is_durable_character_update,
    is_trackable_character_name,
    normalize_alias,
    normalize_appearance_type,
    promote_character_canonical_name,
    select_canonical_character_name,
    should_promote_canonical_name,
    supported_title_alias_variants,
)
from app.services.extraction.validation import (
    ENTITY_ORIGIN_EXISTING,
    ENTITY_ORIGIN_NEW,
    ValidationContext,
    automatic_approval_state_needs_repair,
    build_relationship_semantic_analysis,
    canonical_life_event_details,
    classify_character_entity,
    death_text_has_strong_signal,
    find_existing_character_item,
    manually_reviewed_record,
    normalize_character_item_relationship_type,
    record_has_active_serious_blockers,
    set_validation_metadata,
    text_contains_exact_phrase,
    text_contains_value,
    validate_extracted_fact,
    value_has_physical_medium_noun,
    value_looks_like_intangible_skill_concept,
    value_looks_like_physical_item_concept,
    value_looks_like_progression_state,
    value_looks_like_skill_or_technique,
    has_progression_downgrade,
)
from app.services.extraction.evidence import (
    build_evidence_support,
    get_evidence_context,
    get_evidence_discourse_context,
    recover_fact_evidence,
    verify_evidence_text,
)
from app.services.extraction.evidence_audit import record_ai_evidence_audit_for_candidate
from app.services.item_categories import normalize_item_category
from app.services.skill_categories import normalize_skill_category

ALLOWED_EVENT_TYPES = {
    "item_acquired",
    "skill_acquired",
    "location_arrived",
    "major_battle",
}

ALLOWED_LIFE_EVENT_TYPES = {
    "death",
    "fake_death",
    "resurrection",
    "body_destroyed",
    "soul_survived",
    "sealed",
}

AI_EXTRACTION_PIPELINE_LEGACY = "legacy"
AI_EXTRACTION_PIPELINE_MULTI_STAGE = "multi_stage"
AI_PARALLEL_SAFE_STAGES_ENV = "AI_PARALLEL_SAFE_STAGES"
AI_CONDITIONAL_PROGRESSION_STAGES_ENV = "AI_CONDITIONAL_PROGRESSION_STAGES"
AI_MAX_CONCURRENT_STAGES_ENV = "AI_MAX_CONCURRENT_STAGES"
AI_MAX_CONCURRENT_STAGES_LIMIT = 3
AI_PROGRESSION_SOURCES = {
    "legacy_extractor",
    "progression_audit",
    "progression_extractor",
    "progression_reasoning",
}

TRANSIENT_AI_STATUS_CODES = {408, 429, 500, 502, 503, 504}
TRANSIENT_AI_ERROR_NAME_PARTS = (
    "timeout",
    "connection",
    "connect",
    "rate_limit",
    "ratelimit",
    "server",
    "serviceunavailable",
    "temporar",
)


class AIStageTimeout(RuntimeError):
    pass


def attach_ai_telemetry(error, telemetry):
    try:
        error.ai_telemetry = telemetry
    except Exception:
        pass

    return error


def ai_error_status_code(error):
    return getattr(error, "status_code", None) or getattr(
        getattr(error, "response", None),
        "status_code",
        None,
    )


def ai_error_code(error):
    return (
        getattr(error, "code", None)
        or getattr(error, "type", None)
        or getattr(getattr(error, "body", None), "code", None)
    )


def ai_error_request_id(error):
    headers = getattr(getattr(error, "response", None), "headers", {}) or {}
    return (
        getattr(error, "request_id", None)
        or getattr(error, "x_request_id", None)
        or headers.get("x-request-id")
        or headers.get("X-Request-ID")
    )


def ai_timeout_phase(error):
    current = error
    seen = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        error_name = type(current).__name__.lower()

        if "connecttimeout" in error_name:
            return "connect"
        if "readtimeout" in error_name:
            return "read"
        if "writetimeout" in error_name:
            return "write"
        if "pooltimeout" in error_name:
            return "pool"

        current = getattr(current, "__cause__", None) or getattr(
            current,
            "__context__",
            None,
        )

    return None


def ai_error_retry_after_seconds(error):
    headers = getattr(getattr(error, "response", None), "headers", {}) or {}
    retry_after = headers.get("retry-after") or headers.get("Retry-After")

    if retry_after is None:
        return None

    try:
        return max(0.0, float(retry_after))
    except (TypeError, ValueError):
        return None


def is_transient_ai_error(error):
    if isinstance(
        error,
        (
            AIEmptyResponseError,
            AIMalformedResponseError,
            AIStageTimeout,
        ),
    ):
        return True

    status_code = ai_error_status_code(error)
    if status_code in TRANSIENT_AI_STATUS_CODES:
        return True

    combined = f"{type(error).__name__.lower()} {str(ai_error_code(error) or '').lower()}"
    return any(part in combined for part in TRANSIENT_AI_ERROR_NAME_PARTS)


class ExtractionCancelled(RuntimeError):
    pass


def ensure_extraction_can_continue(should_continue):
    if should_continue and not should_continue():
        raise ExtractionCancelled("Extraction was canceled before saving chapter output.")


def get_extraction_pipeline_mode():
    mode = os.getenv("AI_EXTRACTION_PIPELINE", AI_EXTRACTION_PIPELINE_LEGACY).strip().lower()
    if mode not in {AI_EXTRACTION_PIPELINE_LEGACY, AI_EXTRACTION_PIPELINE_MULTI_STAGE}:
        return AI_EXTRACTION_PIPELINE_LEGACY
    return mode


def parallel_safe_ai_stages_enabled():
    return os.getenv(AI_PARALLEL_SAFE_STAGES_ENV, "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def conditional_progression_stages_enabled():
    return os.getenv(
        AI_CONDITIONAL_PROGRESSION_STAGES_ENV,
        "false",
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def max_concurrent_ai_stages():
    raw_value = os.getenv(
        AI_MAX_CONCURRENT_STAGES_ENV,
        str(AI_MAX_CONCURRENT_STAGES_LIMIT),
    ).strip()

    try:
        configured_value = int(raw_value)
    except ValueError:
        configured_value = AI_MAX_CONCURRENT_STAGES_LIMIT

    return max(1, min(configured_value, AI_MAX_CONCURRENT_STAGES_LIMIT))


PROGRESSION_SIGNAL_PATTERN = re.compile(
    r"\b(?:"
    r"advance(?:d|ment)?|ascend(?:ed|ing)?|awak(?:en|ened|ening)|"
    r"break(?:through| through)|broke through|class(?:ed)? up|"
    r"cultivation|grade|job|layer|level(?:ed)? up|level\s+\d+|"
    r"position|promot(?:e|ed|ion)|rank(?:ed)? up|realm|stage|tier|"
    r"transcend(?:ed|ence)?|unlock(?:ed)?"
    r")\b",
    re.IGNORECASE,
)
PROGRESSION_INDIRECT_ATTRIBUTION_PATTERN = re.compile(
    r"\b(?:he|her|hers|him|his|it|she|their|theirs|them|they)\b",
    re.IGNORECASE,
)
PROGRESSION_UNCERTAINTY_PATTERN = re.compile(
    r"\b(?:almost|apparently|close to|could|might|near(?:ly)?|not yet|"
    r"on the verge|perhaps|preparing to|seem(?:ed|s)?|soon|would)\b",
    re.IGNORECASE,
)


def progression_stage_decision(chapter_text, progression_events):
    text = str(chapter_text or "")
    events = list(progression_events or [])
    reasons = []
    has_progression_signal = bool(PROGRESSION_SIGNAL_PATTERN.search(text))

    if not has_progression_signal:
        return {
            "run_audit": False,
            "run_reasoning": False,
            "reasons": ["no_progression_signal"],
        }

    if not events:
        return {
            "run_audit": True,
            "run_reasoning": True,
            "reasons": ["progression_signal_without_candidate"],
        }

    run_audit = False
    run_reasoning = False

    for event in events:
        evidence = str(getattr(event, "evidence", "") or "")
        character_name = str(getattr(event, "character_name", "") or "")
        new_value = str(getattr(event, "new_value", "") or "")

        if not evidence or not new_value:
            run_audit = True
            reasons.append("candidate_missing_support")

        if character_name and not text_contains_exact_phrase(evidence, character_name):
            run_reasoning = True
            reasons.append("candidate_indirect_attribution")

        if (
            PROGRESSION_INDIRECT_ATTRIBUTION_PATTERN.search(evidence)
            or evidence.strip().endswith("!")
        ):
            run_reasoning = True
            reasons.append("candidate_pronoun_or_exclamation")

        if PROGRESSION_UNCERTAINTY_PATTERN.search(evidence):
            run_audit = True
            run_reasoning = True
            reasons.append("candidate_uncertain_wording")

    return {
        "run_audit": run_audit,
        "run_reasoning": run_reasoning,
        "reasons": sorted(set(reasons)) or ["direct_progression_support"],
    }


def tag_progression_sources(progression_events, source_extractor):
    for progression_event in progression_events:
        if hasattr(progression_event, "source_extractor"):
            progression_event.source_extractor = source_extractor
    return progression_events


def evidence_supports_character_name_or_alias(character, evidence):
    if text_contains_value(evidence, character.name):
        return True

    for alias in character.aliases:
        if text_contains_value(evidence, alias.alias):
            return True

    return False


def has_duplicate_character_name(novel, character):
    return (
        Character.query.filter(
            Character.novel_id == novel.id,
            Character.id != character.id,
            db.func.lower(Character.name) == character.name.lower(),
        ).first()
        is not None
    )


def character_identity_source_label(source_name):
    return {
        "progression": "identity_supported_by_progression",
        "metadata": "identity_supported_by_metadata",
        "life_event": "identity_supported_by_life_event",
        "character_item": "identity_supported_by_character_item",
        "character_skill": "identity_supported_by_character_skill",
        "character": "character",
    }.get(source_name, f"identity_supported_by_{source_name}")


def character_identity_references(character_or_name):
    name = (
        character_or_name.name
        if isinstance(character_or_name, Character)
        else str(character_or_name or "")
    )
    references = [name]

    if isinstance(character_or_name, Character):
        references.extend(alias.alias for alias in getattr(character_or_name, "aliases", []) or [])

    for alias in supported_title_alias_variants(name, name):
        references.append(alias)

    seen = set()
    unique_references = []

    for reference in references:
        normalized_reference = normalize_alias(reference)
        reference_key = normalized_reference.lower()

        if not normalized_reference or reference_key in seen:
            continue

        unique_references.append(normalized_reference)
        seen.add(reference_key)

    return unique_references


def extraction_character_reference_groups(novel, extraction):
    groups = {}

    for character in Character.query.filter_by(novel_id=novel.id).all():
        groups.setdefault(character.name.lower(), set()).update(
            character_identity_references(character)
        )

    for extracted_character in getattr(extraction, "characters", []) or []:
        extracted_name, extracted_aliases = select_canonical_character_name(
            extracted_character.name,
            extracted_character.aliases,
            extracted_character.evidence,
        )
        references = [extracted_name, *extracted_aliases]
        references.extend(supported_title_alias_variants(extracted_name, extracted_character.evidence))
        groups.setdefault(extracted_name.lower(), set()).update(
            normalize_alias(reference)
            for reference in references
            if normalize_alias(reference)
        )

    return groups


def candidate_character_references(novel, extraction, character_name, explicit_aliases=None):
    character = find_existing_character(novel, character_name)

    if character:
        references = character_identity_references(character)
    else:
        references = [character_name]

    reference_groups = extraction_character_reference_groups(novel, extraction)
    references.extend(reference_groups.get(str(character_name or "").lower(), set()))
    references.extend(explicit_aliases or [])

    seen = set()
    unique_references = []

    for reference in references:
        normalized_reference = normalize_alias(reference)
        reference_key = normalized_reference.lower()

        if not normalized_reference or reference_key in seen:
            continue

        unique_references.append(normalized_reference)
        seen.add(reference_key)

    return unique_references


def competing_character_references(novel, extraction, character_name):
    character_key = str(character_name or "").strip().lower()
    resolved_character = find_existing_character(novel, character_name)
    references = []

    for character in Character.query.filter_by(novel_id=novel.id).all():
        if (
            (resolved_character and character.id == resolved_character.id)
            or character.name.lower() == character_key
        ):
            continue

        references.extend(character_identity_references(character))

    for extracted_character in getattr(extraction, "characters", []) or []:
        extracted_name, extracted_aliases = select_canonical_character_name(
            extracted_character.name,
            extracted_character.aliases,
            extracted_character.evidence,
        )

        if extracted_name.lower() == character_key:
            continue

        references.extend([extracted_name, *extracted_aliases])

    seen = set()
    unique_references = []

    for reference in references:
        normalized_reference = normalize_alias(reference)
        reference_key = normalized_reference.lower()

        if not normalized_reference or reference_key in seen:
            continue

        unique_references.append(normalized_reference)
        seen.add(reference_key)

    return unique_references


def set_candidate_evidence(candidate, evidence_text):
    if candidate is None:
        return False

    try:
        setattr(candidate, "evidence", evidence_text)
        return True
    except Exception:
        try:
            object.__setattr__(candidate, "evidence", evidence_text)
            return True
        except Exception:
            return False


def set_candidate_attr(candidate, name, value):
    if candidate is None:
        return False

    try:
        setattr(candidate, name, value)
        return True
    except Exception:
        try:
            object.__setattr__(candidate, name, value)
            return True
        except Exception:
            return False


def set_candidate_evidence_support(candidate, support):
    if not candidate or not support:
        return False

    set_candidate_attr(candidate, "evidence_source", support.source)
    set_candidate_attr(candidate, "evidence_match_type", support.match_type)
    set_candidate_attr(candidate, "evidence_start_offset", support.start_offset)
    set_candidate_attr(candidate, "evidence_end_offset", support.end_offset)

    if support.recovery_method:
        set_candidate_attr(candidate, "evidence_recovery_method", support.recovery_method)

    return True


def evidence_support_kwargs(candidate):
    return {
        "start_offset": getattr(candidate, "evidence_start_offset", None),
        "end_offset": getattr(candidate, "evidence_end_offset", None),
        "match_type": getattr(candidate, "evidence_match_type", None),
        "evidence_source": getattr(candidate, "evidence_source", None),
    }


def validation_evidence_kwargs(candidate):
    return {
        "evidence_start_offset": getattr(candidate, "evidence_start_offset", None),
        "evidence_end_offset": getattr(candidate, "evidence_end_offset", None),
        "evidence_match_type": getattr(candidate, "evidence_match_type", None),
    }


def entity_validation_support_kwargs(candidate):
    return {
        "start_offset": getattr(candidate, "evidence_start_offset", None),
        "end_offset": getattr(candidate, "evidence_end_offset", None),
        "match_type": getattr(candidate, "evidence_match_type", None),
    }


def copy_evidence_support_attrs(source, target):
    for attr_name in (
        "evidence_source",
        "evidence_match_type",
        "evidence_start_offset",
        "evidence_end_offset",
        "evidence_recovery_method",
    ):
        if hasattr(source, attr_name):
            set_candidate_attr(target, attr_name, getattr(source, attr_name))


def remember_original_evidence(candidate, evidence_text):
    if candidate is None:
        return False

    try:
        setattr(candidate, "original_evidence", evidence_text)
        return True
    except Exception:
        try:
            object.__setattr__(candidate, "original_evidence", evidence_text)
            return True
        except Exception:
            return False


def recover_candidate_evidence_if_needed(
    chapter,
    fact_type,
    candidate,
    aliases=None,
    canonical_facts=None,
    label=None,
):
    chapter_text = chapter.content if chapter else ""
    original_evidence = getattr(candidate, "evidence", None)
    support = build_evidence_support(
        chapter_text,
        fact_type,
        candidate,
        aliases=aliases,
        canonical_facts=canonical_facts,
    )

    if not support.verified:
        if support.ambiguous:
            current_app.logger.debug(
                "Evidence recovery ambiguous: chapter=%s fact_type=%s candidate=%s method=%s",
                getattr(chapter, "chapter_number", None),
                fact_type,
                label or getattr(candidate, "name", None) or getattr(candidate, "character_name", None),
                support.recovery_method,
            )
        return False

    canonical_evidence = support.evidence_text
    evidence_changed = str(original_evidence or "").strip() != canonical_evidence

    if evidence_changed:
        remember_original_evidence(candidate, original_evidence)

    set_candidate_evidence_support(candidate, support)

    if not set_candidate_evidence(candidate, canonical_evidence):
        return False

    if support.source == "backend_recovered":
        current_app.logger.debug(
            "Evidence recovery succeeded: chapter=%s fact_type=%s candidate=%s method=%s",
            getattr(chapter, "chapter_number", None),
            fact_type,
            label or getattr(candidate, "name", None) or getattr(candidate, "character_name", None),
            support.recovery_method,
        )

    return evidence_changed or support.source == "backend_recovered"


def recover_extraction_evidence(novel, chapter, extraction):
    for extracted_character in getattr(extraction, "characters", []) or []:
        extracted_name, extracted_aliases = select_canonical_character_name(
            extracted_character.name,
            extracted_character.aliases,
            extracted_character.evidence,
        )

        character_classification = classify_character_entity(
            extracted_name,
            extracted_character.evidence,
        )

        if character_classification.is_generic:
            continue

        original_evidence = extracted_character.evidence
        proxy = SimpleNamespace(name=extracted_name, evidence=extracted_character.evidence)

        if recover_candidate_evidence_if_needed(
            chapter,
            "character",
            proxy,
            aliases=extracted_aliases,
            label=extracted_name,
        ):
            remember_original_evidence(extracted_character, original_evidence)
            set_candidate_evidence(extracted_character, proxy.evidence)
        copy_evidence_support_attrs(proxy, extracted_character)

    for extracted_skill in getattr(extraction, "skills", []) or []:
        recover_candidate_evidence_if_needed(
            chapter,
            "skill",
            extracted_skill,
            aliases=getattr(extracted_skill, "aliases", []),
            label=extracted_skill.name,
        )

    for extracted_item in getattr(extraction, "items", []) or []:
        recover_candidate_evidence_if_needed(
            chapter,
            "item",
            extracted_item,
            label=extracted_item.name,
        )

    for extracted_progression in getattr(extraction, "progression_events", []) or []:
        character_name = extracted_progression.character_name
        recover_candidate_evidence_if_needed(
            chapter,
            "progression",
            extracted_progression,
            aliases=candidate_character_references(novel, extraction, character_name),
            canonical_facts={
                "competing_character_references": competing_character_references(
                    novel,
                    extraction,
                    character_name,
                ),
            },
            label=f"{character_name}:{extracted_progression.new_value}",
        )

    for extracted_life_event in getattr(extraction, "life_events", []) or []:
        character_name = extracted_life_event.character_name
        recover_candidate_evidence_if_needed(
            chapter,
            "life_event",
            extracted_life_event,
            aliases=candidate_character_references(novel, extraction, character_name),
            canonical_facts={
                "competing_character_references": competing_character_references(
                    novel,
                    extraction,
                    character_name,
                ),
            },
            label=f"{character_name}:{extracted_life_event.event_type}",
        )

    for extracted_relationship in getattr(extraction, "character_skills", []) or []:
        character_name = extracted_relationship.character_name
        recover_candidate_evidence_if_needed(
            chapter,
            "character_skill",
            extracted_relationship,
            aliases=candidate_character_references(novel, extraction, character_name),
            canonical_facts={
                "competing_character_references": competing_character_references(
                    novel,
                    extraction,
                    character_name,
                ),
                "target_name": extracted_relationship.skill_name,
            },
            label=f"{character_name}:{extracted_relationship.skill_name}",
        )

    for extracted_relationship in getattr(extraction, "character_items", []) or []:
        character_name = extracted_relationship.character_name
        recover_candidate_evidence_if_needed(
            chapter,
            "character_item",
            extracted_relationship,
            aliases=candidate_character_references(novel, extraction, character_name),
            canonical_facts={
                "competing_character_references": competing_character_references(
                    novel,
                    extraction,
                    character_name,
                ),
                "target_name": extracted_relationship.item_name,
            },
            label=f"{character_name}:{extracted_relationship.item_name}",
        )


def sentence_supports_character_identity(sentence, character_or_name):
    if not sentence:
        return False

    return any(
        text_contains_exact_phrase(sentence, reference)
        for reference in character_identity_references(character_or_name)
    )


def supporting_identity_evidence(chapter, character_or_name, evidence):
    evidence_text = normalize_evidence_text(evidence)
    chapter_text = chapter.content if chapter else ""
    candidates = []
    verification = verify_evidence_text(chapter_text, evidence_text)

    if verification.verified:
        candidates.append(verification.evidence_text)

    evidence_context = get_evidence_context(
        chapter_text,
        verification.evidence_text if verification.verified else evidence_text,
        start_offset=verification.start_offset,
        end_offset=verification.end_offset,
        match_type=verification.match_type,
    )

    if evidence_context.found:
        candidates.extend(
            candidate
            for candidate in (
                evidence_context.evidence_sentence,
                evidence_context.previous_sentence,
                evidence_context.next_sentence,
            )
            if candidate
        )

    for candidate in candidates:
        if not sentence_supports_character_identity(candidate, character_or_name):
            continue

        if verify_evidence_text(chapter_text, candidate).verified:
            return candidate

    return None


def character_identity_can_be_supported(name, evidence):
    classification = classify_character_entity(name, evidence)

    return (
        is_trackable_character_name(name)
        and not classification.is_generic
        and classification.is_distinctive
        and classification.reason
        in {
            "proper_name",
            "title_style_name",
            "stable_label",
            "stable_recurring_label",
        }
    )


def merged_source_label(existing_source, new_source):
    sources = {
        source.strip()
        for source in str(existing_source or "").split(",")
        if source.strip()
    }
    sources.add(new_source)
    return ",".join(sorted(sources))


def revalidate_character_identity_from_support(
    novel,
    chapter,
    character,
    evidence,
    source_name,
    entity_origin=ENTITY_ORIGIN_EXISTING,
):
    if not character:
        return False

    identity_evidence = supporting_identity_evidence(chapter, character, evidence)

    if not identity_evidence:
        return False

    if not character_identity_can_be_supported(character.name, identity_evidence):
        return False

    validation = validate_extracted_fact(
        ValidationContext(
            novel=novel,
            chapter=chapter,
            fact_type="character",
            entity_name=character.name,
            value=character.name,
            evidence=identity_evidence,
            character=character,
            entity_origin=entity_origin,
            source_extractors={source_name},
        )
    )

    if not validation.auto_approved:
        return False

    support_label = character_identity_source_label(source_name)
    validation.risk_flags = [
        *validation.risk_flags,
        support_label,
    ]
    set_validation_metadata(
        character,
        validation,
        merged_source_label(character.source_extractor, support_label),
    )
    return True


def resolve_or_create_character_from_support(novel, chapter, character_name, evidence, source_name, summary):
    character = find_existing_character(novel, character_name)

    if character:
        return character, False

    identity_evidence = supporting_identity_evidence(chapter, character_name, evidence)

    if not identity_evidence or not character_identity_can_be_supported(character_name, identity_evidence):
        return None, False

    character = Character(
        novel_id=novel.id,
        name=character_name,
        description=None,
        first_mentioned_chapter_id=chapter.id,
        first_appeared_chapter_id=None,
        first_seen_chapter_id=chapter.id,
        status="unknown",
        review_status="pending",
    )
    db.session.add(character)
    db.session.flush()
    summary["characters_created"] += 1
    return character, True


def maybe_approve_promoted_character(
    novel,
    chapter,
    character,
    old_name,
    old_review_status,
    evidence,
):
    if old_review_status != "pending":
        return False

    old_classification = classify_character_entity(old_name, evidence)
    new_classification = classify_character_entity(character.name, evidence)

    if old_classification.reason not in {
        "stable_recurring_label",
        "stable_label",
        "descriptive_role",
    }:
        return False

    if new_classification.reason != "proper_name":
        return False

    if new_classification.is_generic or not new_classification.is_distinctive:
        return False

    if has_duplicate_character_name(novel, character):
        return False

    if not evidence_supports_character_name_or_alias(character, evidence):
        return False

    return revalidate_character_identity_from_support(
        novel,
        chapter,
        character,
        evidence,
        "character,identity_supported_by_canonical_promotion",
        entity_origin=ENTITY_ORIGIN_EXISTING,
    )


def progression_candidate_key(
    novel,
    extracted_progression,
    character=None,
    progression_type=None,
    new_value=None,
):
    progression_type = progression_type or normalize_progression_type(
        extracted_progression.progression_type
    )
    new_value = canonicalize_progression_value(
        progression_type,
        new_value
        if new_value is not None
        else extracted_progression.new_value,
    )

    if character:
        character_key = ("character_id", character.id)
    else:
        existing_character = find_existing_character(novel, extracted_progression.character_name)

        if existing_character:
            character_key = ("character_id", existing_character.id)
        else:
            character_key = (
                "character_name",
                normalize_alias(extracted_progression.character_name).lower(),
            )

    return (
        character_key[0],
        character_key[1],
        progression_type,
        progression_compare_key(progression_type, new_value),
    )


def source_extractors_support_context_attribution(source_extractors):
    ai_sources = set(source_extractors) & AI_PROGRESSION_SOURCES

    return bool(ai_sources)


def _flexible_fragment_pattern(fragment):
    escaped = re.escape(fragment)
    escaped = re.sub(r"\\\s+", r"\\s+", escaped)
    return escaped


def _context_for_match(chapter_text, start, end, window_size):
    return chapter_text[
        max(0, start - window_size): min(len(chapter_text), end + window_size)
    ]


def _context_score(context, fragment, new_value=None, character=None, exact_match=False):
    score = 1000 if exact_match else len(fragment)
    normalized_fragment = normalize_evidence_text(fragment).lower()
    normalized_context = normalize_evidence_text(context).lower()
    normalized_value = normalize_evidence_text(new_value or "").lower()

    if normalized_value:
        compact_fragment = normalized_fragment.replace(" of ", " ")
        compact_value = normalized_value.replace(" of ", " ")

        if normalized_value in normalized_fragment or compact_value in compact_fragment:
            score += 120
        elif " ".join(normalized_value.split()[:2]) in normalized_fragment:
            score += 60

    if "!" in fragment:
        score += 80

    breakthrough_terms = {
        "advanced",
        "advancement",
        "awakening",
        "body",
        "breakthrough",
        "broken through",
        "broke through",
        "cultivat",
        "energy",
        "expelled",
        "filth",
        "level up",
        "rank up",
        "resource",
        "training",
        "transformation",
    }
    current_state_terms = {
        "already",
        "currently",
        "foundation was",
        "is now",
        "now at",
        "now was",
        "was now",
    }
    near_terms = {
        "almost",
        "close to",
        "hair away",
        "just a hair",
        "near",
        "nearly",
        "not yet",
        "on the verge",
        "soon",
    }

    if any(term in normalized_context for term in breakthrough_terms):
        score += 70

    if any(term in normalized_fragment for term in current_state_terms):
        score -= 20

    if any(term in normalized_fragment for term in near_terms):
        score -= 160

    if character and context:
        if reference_positions(context, character_reference_candidates(character)):
            score += 80

    negative_value_patterns = {
        "had not reached",
        "has not reached",
        "not reached",
        "not yet reached",
        "still had not reached",
        "still has not reached",
    }

    if normalized_value and any(pattern in normalized_context for pattern in negative_value_patterns):
        value_index = normalized_context.find(normalized_value)
        if value_index != -1:
            prefix = normalized_context[max(0, value_index - 80): value_index]
            if any(pattern in prefix for pattern in negative_value_patterns):
                score -= 300

    return score


def local_context_for_evidence(
    chapter,
    evidence,
    window_size=520,
    new_value=None,
    character=None,
    start_offset=None,
    end_offset=None,
    match_type=None,
):
    chapter_text = chapter.content or ""
    evidence_text = normalize_evidence_text(evidence)

    reference_groups = (
        [character_reference_candidates(character)]
        if character
        else None
    )
    evidence_context = get_evidence_discourse_context(
        chapter_text,
        evidence,
        start_offset=start_offset,
        end_offset=end_offset,
        match_type=match_type,
        reference_groups=reference_groups,
    )

    if evidence_context.found:
        return evidence_context.combined_context

    if evidence_context.ambiguous:
        return ""

    normalized_chapter_text = (
        chapter_text
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("…", "...")
    )
    candidates = []

    full_evidence = evidence_text.strip()
    if full_evidence:
        exact_pattern = _flexible_fragment_pattern(full_evidence)
        for match in re.finditer(exact_pattern, normalized_chapter_text, re.IGNORECASE):
            context = _context_for_match(chapter_text, match.start(), match.end(), window_size)
            candidates.append(
                (
                    _context_score(
                        context,
                        full_evidence,
                        new_value=new_value,
                        character=character,
                        exact_match=True,
                    ),
                    context,
                )
            )

    fragments = [
        fragment.strip()
        for fragment in re.split(r"\.\.\.|…", evidence_text)
        if len(fragment.strip()) >= 8
    ]

    for fragment in fragments:
        fragment_pattern = _flexible_fragment_pattern(fragment)

        for match in re.finditer(fragment_pattern, normalized_chapter_text, re.IGNORECASE):
            context = _context_for_match(chapter_text, match.start(), match.end(), window_size)
            candidates.append(
                (
                    _context_score(
                        context,
                        fragment,
                        new_value=new_value,
                        character=character,
                    ),
                    context,
                )
            )

        if len(fragment) > 80:
            prefix = fragment[:80].strip()
            prefix_pattern = _flexible_fragment_pattern(prefix)

            for match in re.finditer(prefix_pattern, normalized_chapter_text, re.IGNORECASE):
                context = _context_for_match(chapter_text, match.start(), match.end(), window_size)
                candidates.append(
                    (
                        _context_score(
                            context,
                            prefix,
                            new_value=new_value,
                            character=character,
                        ),
                        context,
                    )
                )

    if new_value:
        normalized_value = normalize_evidence_text(new_value)
        value_pattern = _flexible_fragment_pattern(normalized_value)

        for match in re.finditer(value_pattern, normalized_chapter_text, re.IGNORECASE):
            context = _context_for_match(chapter_text, match.start(), match.end(), window_size)
            candidates.append(
                (
                    _context_score(
                        context,
                        normalized_value,
                        new_value=new_value,
                        character=character,
                    ),
                    context,
                )
            )

        value_words = normalized_value.split()

        if len(value_words) >= 2:
            value_prefix = " ".join(value_words[:2])
            prefix_pattern = _flexible_fragment_pattern(value_prefix)

            for match in re.finditer(prefix_pattern, normalized_chapter_text, re.IGNORECASE):
                context = _context_for_match(chapter_text, match.start(), match.end(), window_size)
                candidates.append(
                    (
                        _context_score(
                            context,
                            value_prefix,
                            new_value=new_value,
                            character=character,
                        ),
                        context,
                    )
                )

    if candidates:
        return max(candidates, key=lambda candidate: candidate[0])[1]

    return ""


def reference_positions(text, references):
    positions = []

    for reference in references:
        reference_text = normalize_evidence_text(reference)

        if not reference_text:
            continue

        positions.extend(text_reference_positions(text, reference_text))

    return positions


def progression_phrase_position(context, new_value):
    context_lower = context.lower()
    value_lower = normalize_evidence_text(new_value).lower()
    index = context_lower.find(value_lower)

    if index != -1:
        return index

    compact_value = value_lower.replace(" of ", " ")
    compact_context = context_lower.replace(" of ", " ")
    index = compact_context.find(compact_value)

    if index != -1:
        return index

    words = value_lower.split()

    if len(words) >= 2:
        index = context_lower.find(" ".join(words[:2]))

        if index != -1:
            return index

    return None


def sentence_fragment_for_position(text, position):
    if position is None:
        return text

    text = str(text or "")
    left_boundary = max(
        text.rfind(".", 0, position),
        text.rfind("!", 0, position),
        text.rfind("?", 0, position),
        text.rfind("\n", 0, position),
    )
    right_candidates = [
        candidate
        for candidate in (
            text.find(".", position),
            text.find("!", position),
            text.find("?", position),
            text.find("\n", position),
        )
        if candidate >= 0
    ]
    right_boundary = min(right_candidates) if right_candidates else len(text) - 1
    return text[left_boundary + 1:right_boundary + 1].strip()


PROGRESSION_PREDICATE_RE = re.compile(
    r"\b(?:"
    r"(?:had\s+|has\s+|have\s+)?reached|"
    r"achieved|advanced|attained|entered|"
    r"broke\s+through|broken\s+through|breaks\s+through|breakthrough|"
    r"became|becomes|"
    r"(?:is|are|was|were)\s+(?:already\s+|now\s+|currently\s+)?at|"
    r"(?:cultivation|realm|foundation|base)(?:\s+\w+){0,4}\s+(?:is|are|was|were|had\s+reached|has\s+reached|have\s+reached)"
    r")\b",
    re.IGNORECASE,
)
PROGRESSION_AMBIGUOUS_COLLECTIVE_RE = re.compile(
    r"\b(?:one|some)\s+of\s+(?:them|whom)\b",
    re.IGNORECASE,
)
PROGRESSION_DISTRIBUTIVE_RE = re.compile(
    r"\b(?:both|each|all\s+(?:of\s+)?(?:three|four|five|six|seven|eight|nine|ten|\d+|them)|the\s+two\s+of\s+them|both\s+of\s+whom)\b",
    re.IGNORECASE,
)
PROGRESSION_RESPECTIVELY_RE = re.compile(r"\brespectively\b", re.IGNORECASE)
PROGRESSION_HELPER_REFERENCE_RE = re.compile(
    r"^\s*(?:'s|’s)\s+(?:help|assistance|aid|support)\b",
    re.IGNORECASE,
)
PROGRESSION_REFERENCE_PREFIX_BLOCK_RE = re.compile(
    r"\b(?:with|unlike|from|by|for|near|beside|against|toward|towards|to|at)\s*$",
    re.IGNORECASE,
)


def normalized_progression_sentence(text):
    return " ".join(str(text or "").split())


def first_progression_predicate_index(text):
    match = PROGRESSION_PREDICATE_RE.search(text or "")
    return match.start() if match else None


def progression_value_ordinal(value):
    for word in normalized_progression_words(value or ""):
        number = progression_number_from_word(word)

        if number is not None:
            return number

    return None


def ordered_progression_ordinals(text):
    ordinals = []

    for word in re.findall(r"[A-Za-z0-9]+", str(text or "").lower().replace("-", " ")):
        number = progression_number_from_word(word)

        if number is not None:
            ordinals.append(number)

    return ordinals


def progression_character_reference_matches(novel, text):
    matches = []
    seen = set()

    for character in Character.query.filter_by(novel_id=novel.id).all():
        for reference in character_reference_candidates(character):
            for position in text_reference_positions(text, reference):
                key = (character.id, reference.lower(), position)

                if key in seen:
                    continue

                matches.append(
                    {
                        "character": character,
                        "reference": reference,
                        "position": position,
                        "end": position + len(reference),
                    }
                )
                seen.add(key)

    return sorted(matches, key=lambda item: (item["position"], -len(item["reference"])))


def target_progression_reference_matches(character, sentence):
    matches = []

    for reference in character_reference_candidates(character):
        for position in text_reference_positions(sentence, reference):
            matches.append(
                {
                    "character": character,
                    "reference": reference,
                    "position": position,
                    "end": position + len(reference),
                }
            )

    return sorted(matches, key=lambda item: (item["position"], -len(item["reference"])))


def unique_ordered_characters_from_matches(matches):
    ordered = []
    seen_ids = set()

    for match in sorted(matches, key=lambda item: item["position"]):
        character_id = match["character"].id

        if character_id in seen_ids:
            continue

        ordered.append(match["character"])
        seen_ids.add(character_id)

    return ordered


def progression_respectively_supports_target(novel, sentence, character, new_value):
    if not PROGRESSION_RESPECTIVELY_RE.search(sentence or ""):
        return None

    normalized_sentence = normalized_progression_sentence(sentence)

    if PROGRESSION_AMBIGUOUS_COLLECTIVE_RE.search(normalized_sentence):
        return False

    all_matches = progression_character_reference_matches(novel, normalized_sentence)
    target_matches = [match for match in all_matches if match["character"].id == character.id]

    if not target_matches:
        return None

    ordered_characters = unique_ordered_characters_from_matches(all_matches)
    ordered_ordinals = ordered_progression_ordinals(normalized_sentence)
    target_ordinal = progression_value_ordinal(new_value)

    if (
        not ordered_characters
        or target_ordinal is None
        or len(ordered_characters) != len(ordered_ordinals)
    ):
        return False

    try:
        target_index = [item.id for item in ordered_characters].index(character.id)
    except ValueError:
        return None

    return ordered_ordinals[target_index] == target_ordinal


def progression_sentence_has_collective_support(novel, sentence, character):
    if PROGRESSION_AMBIGUOUS_COLLECTIVE_RE.search(sentence or ""):
        return False

    if not PROGRESSION_DISTRIBUTIVE_RE.search(sentence or ""):
        return False

    matches = progression_character_reference_matches(novel, sentence)
    character_ids = {match["character"].id for match in matches}

    return len(character_ids) >= 2 and character.id in character_ids


def other_character_before_predicate(novel, sentence, character, reference_end, predicate_index):
    if predicate_index is None:
        return False

    after_reference = sentence[reference_end:]

    for match in progression_character_reference_matches(novel, after_reference):
        if match["character"].id == character.id:
            continue

        if match["position"] < predicate_index:
            return True

    return False


def progression_reference_has_subject_predicate(novel, sentence, character, reference_match, new_value):
    position = reference_match["position"]
    reference_end = reference_match["end"]
    prefix = sentence[:position]
    after_reference = sentence[reference_end:]
    relative_progression_clause = re.match(
        r"^\s*,?\s+(?:who|whose)\b",
        after_reference,
        flags=re.IGNORECASE,
    )

    if not relative_progression_clause and PROGRESSION_REFERENCE_PREFIX_BLOCK_RE.search(prefix):
        return False

    if PROGRESSION_HELPER_REFERENCE_RE.match(after_reference):
        return False

    predicate_index = first_progression_predicate_index(after_reference)

    if predicate_index is None or predicate_index > 180:
        return False

    if other_character_before_predicate(
        novel,
        sentence,
        character,
        reference_end,
        predicate_index,
    ):
        return False

    value_index = progression_phrase_position(after_reference, new_value)

    if value_index is not None and predicate_index > value_index:
        return False

    return True


def direct_progression_subject_status(novel, character, sentence, new_value):
    normalized_sentence = normalized_progression_sentence(sentence)

    if not normalized_sentence or not novel or not character:
        return None

    respectively_supported = progression_respectively_supports_target(
        novel,
        normalized_sentence,
        character,
        new_value,
    )

    if respectively_supported is True:
        return "direct_attribution"

    if respectively_supported is False:
        return "attribution_uncertain"

    if progression_sentence_has_collective_support(novel, normalized_sentence, character):
        return "direct_attribution"

    target_matches = target_progression_reference_matches(character, normalized_sentence)

    if not target_matches:
        return None

    for match in target_matches:
        if progression_reference_has_subject_predicate(
            novel,
            normalized_sentence,
            character,
            match,
            new_value,
        ):
            return "direct_attribution"

    if first_progression_predicate_index(normalized_sentence) is not None:
        return "attribution_uncertain"

    return None


def context_has_unique_progression_character(novel, character, context):
    if not novel or not character or not context:
        return False

    matches = progression_character_reference_matches(novel, context)
    character_ids = {match["character"].id for match in matches}

    return character_ids == {character.id}


def has_competing_progression_claim(novel, character, context, new_value):
    phrase_index = progression_phrase_position(context, new_value)

    if phrase_index is None:
        return False

    assigned_positions = reference_positions(context, character_reference_candidates(character))

    for other_character in Character.query.filter_by(novel_id=novel.id).all():
        if other_character.id == character.id:
            continue

        other_positions = reference_positions(context, character_reference_candidates(other_character))

        for other_position in other_positions:
            if other_position > phrase_index:
                continue

            other_distance = phrase_index - other_position

            if not assigned_positions:
                return True

            assigned_distance = min(abs(phrase_index - position) for position in assigned_positions)

            if other_distance <= assigned_distance:
                return True

    return False


def progression_attribution_status(
    novel,
    chapter,
    character,
    new_value,
    evidence,
    source_extractors,
    extracted_progression,
    start_offset=None,
    end_offset=None,
    match_type=None,
):
    context = local_context_for_evidence(
        chapter,
        evidence,
        new_value=new_value,
        character=character,
        start_offset=start_offset
        if start_offset is not None
        else getattr(extracted_progression, "evidence_start_offset", None),
        end_offset=end_offset
        if end_offset is not None
        else getattr(extracted_progression, "evidence_end_offset", None),
        match_type=match_type
        if match_type is not None
        else getattr(extracted_progression, "evidence_match_type", None),
    )
    phrase_index = progression_phrase_position(evidence, new_value)
    direct_attribution_text = evidence

    if phrase_index is not None:
        direct_attribution_text = sentence_fragment_for_position(evidence, phrase_index)

    subject_status = direct_progression_subject_status(
        novel,
        character,
        direct_attribution_text,
        new_value,
    )

    if subject_status:
        return subject_status

    direct_result = resolve_character_attribution(
        mention=None,
        evidence_text=direct_attribution_text,
        local_context=direct_attribution_text,
        candidate_characters=Character.query.filter_by(novel_id=novel.id).all()
        if novel
        else ([character] if character else []),
        novel=novel,
        target_character=character,
        target_value=new_value,
    )
    context_result = resolve_character_attribution(
        mention=None,
        evidence_text=evidence,
        local_context=context,
        candidate_characters=Character.query.filter_by(novel_id=novel.id).all()
        if novel
        else ([character] if character else []),
        novel=novel,
        target_character=character,
        target_value=new_value,
    )

    if attribution_matches_character(direct_result, character):
        return "direct_attribution"

    if direct_result.ambiguous or context_result.ambiguous:
        return "attribution_uncertain"

    if (
        attribution_matches_character(context_result, character)
        and source_extractors_support_context_attribution(source_extractors)
        and is_confirmed_progression(extracted_progression, local_context=context)
    ):
        return "context_supported_attribution"

    if (
        context_has_unique_progression_character(novel, character, context)
        and source_extractors_support_context_attribution(source_extractors)
        and is_confirmed_progression(extracted_progression, local_context=context)
    ):
        return "context_supported_attribution"

    return "attribution_uncertain"


def progression_source_set(source_extractor_label):
    return {
        source.strip()
        for source in (source_extractor_label or "").split(",")
        if source.strip()
    }


def progression_near_breakthrough_penalty(text):
    normalized_text = normalize_evidence_text(text or "").lower()
    near_terms = {
        "almost",
        "close to",
        "hair away",
        "just a hair",
        "near",
        "nearly",
        "not yet",
        "on the verge",
        "soon",
    }

    return 120 if any(term in normalized_text for term in near_terms) else 0


def progression_breakthrough_score(text):
    normalized_text = normalize_evidence_text(text or "").lower()
    breakthrough_terms = {
        "advanced",
        "advancement",
        "awakening",
        "body",
        "breakthrough",
        "broken through",
        "broke through",
        "cultivat",
        "energy",
        "expelled",
        "filth",
        "level up",
        "rank up",
        "resource",
        "training",
        "transformation",
    }
    score = 0

    if "!" in normalized_text:
        score += 50

    if any(term in normalized_text for term in breakthrough_terms):
        score += 60

    if any(term in normalized_text for term in {"is now", "was now", "currently", "foundation was"}):
        score -= 20

    score -= progression_near_breakthrough_penalty(normalized_text)
    return score


def progression_candidate_quality(chapter, extracted_progression, character=None, new_value=None):
    evidence = extracted_progression.evidence or ""
    value = new_value if new_value is not None else extracted_progression.new_value
    progression_type = normalize_progression_type(extracted_progression.progression_type)
    canonical_value = canonicalize_progression_value(progression_type, value)

    if not is_valid_progression_value(progression_type, canonical_value):
        return -1

    context = local_context_for_evidence(
        chapter,
        evidence,
        new_value=canonical_value,
        character=character,
        start_offset=getattr(extracted_progression, "evidence_start_offset", None),
        end_offset=getattr(extracted_progression, "evidence_end_offset", None),
        match_type=getattr(extracted_progression, "evidence_match_type", None),
    )
    score = 0

    if has_meaningful_progression_evidence(extracted_progression):
        score += 20

    if is_confirmed_progression(extracted_progression, local_context=context):
        score += 40

    if character and evidence_mentions_character(evidence, character):
        score += 50
    elif character and context and reference_positions(context, character_reference_candidates(character)):
        score += 35

    score += progression_breakthrough_score(f"{evidence} {context}")

    if canonical_value and text_contains_progression_value(evidence, canonical_value):
        score += 20

    return score


def text_contains_progression_value(text, value):
    normalized_text = normalize_evidence_text(text or "").lower()
    normalized_value = normalize_evidence_text(value or "").lower()

    if not normalized_text or not normalized_value:
        return False

    if normalized_value in normalized_text:
        return True

    if normalized_value.replace(" of ", " ") in normalized_text.replace(" of ", " "):
        return True

    value_words = normalized_value.split()
    return len(value_words) >= 2 and " ".join(value_words[:2]) in normalized_text


def progression_record_evidence_texts(progression):
    return [
        evidence.evidence_text
        for evidence in WikiEvidence.query.filter_by(
            entity_type="progression",
            entity_id=progression.id,
        ).all()
    ]


def progression_record_source_extractors(progression):
    return progression_source_set(progression.source_extractor)


def progression_proxy(progression, evidence, evidence_row=None):
    character = db.session.get(Character, progression.character_id)

    return SimpleNamespace(
        character_name=character.name if character else None,
        progression_type=progression.progression_type,
        old_value=progression.old_value,
        new_value=progression.new_value,
        description=progression.description,
        evidence=evidence,
        source_extractor=progression.source_extractor,
        evidence_start_offset=getattr(evidence_row, "start_offset", None),
        evidence_end_offset=getattr(evidence_row, "end_offset", None),
        evidence_match_type=getattr(evidence_row, "match_type", None),
    )


def progression_record_evidence_rows(progression):
    return WikiEvidence.query.filter_by(
        entity_type="progression",
        entity_id=progression.id,
    ).all()


def progression_record_best_evidence_support(progression):
    evidence_rows = progression_record_evidence_rows(progression)

    if not evidence_rows:
        return None

    character = db.session.get(Character, progression.character_id)

    def evidence_row_quality(evidence_row):
        evidence_chapter = db.session.get(Chapter, evidence_row.chapter_id)

        if not evidence_chapter:
            return -1

        return progression_candidate_quality(
            evidence_chapter,
            progression_proxy(progression, evidence_row.evidence_text, evidence_row),
            character=character,
            new_value=progression.new_value,
        )

    best_row = max(evidence_rows, key=evidence_row_quality)
    best_chapter = db.session.get(Chapter, best_row.chapter_id)

    return SimpleNamespace(
        evidence_text=best_row.evidence_text,
        chapter=best_chapter,
        start_offset=best_row.start_offset,
        end_offset=best_row.end_offset,
        match_type=best_row.match_type,
    )


def progression_record_best_evidence(progression):
    support = progression_record_best_evidence_support(progression)
    return support.evidence_text if support else None


def find_promotable_pending_progression(character, progression_type, new_value, chapter):
    rows = (
        CharacterProgressionEvent.query.join(
            Chapter,
            CharacterProgressionEvent.chapter_id == Chapter.id,
        )
        .filter(
            CharacterProgressionEvent.character_id == character.id,
            CharacterProgressionEvent.progression_type == progression_type,
            CharacterProgressionEvent.review_status == "pending",
            Chapter.chapter_number < chapter.chapter_number,
        )
        .order_by(Chapter.chapter_number.asc(), CharacterProgressionEvent.id.asc())
        .all()
    )

    for progression in rows:
        if progression_values_match(progression_type, progression.new_value, new_value):
            return progression

    return None


def revalidate_progression_record(
    novel,
    progression,
    evidence,
    source_extractors,
    entity_origin=ENTITY_ORIGIN_EXISTING,
    chapter=None,
    start_offset=None,
    end_offset=None,
    match_type=None,
    conflict=False,
    progression_downgrade=False,
):
    chapter = chapter or db.session.get(Chapter, progression.chapter_id)
    support, validation, validation_context = best_validation_support_for_record(
        novel,
        progression,
        evidence,
        source_extractors,
        chapter=chapter,
        start_offset=start_offset,
        end_offset=end_offset,
        match_type=match_type,
        entity_origin=entity_origin,
    )

    if not validation or not validation_context or not support:
        return None

    character = validation_context.character
    review_warnings = progression_review_warnings(
        novel,
        support.chapter,
        character,
        progression.progression_type,
        progression.new_value,
        support.evidence_text,
    )

    if validation_context.context_supported_attribution:
        review_warnings = [
            warning
            for warning in review_warnings
            if warning != "Evidence may not directly name this character."
        ]

    progression.review_warnings = "\n".join(review_warnings) if review_warnings else None
    apply_revalidation_result(
        progression,
        validation,
        ",".join(sorted(source_extractors)),
    )
    return validation


def extract_chapter_with_ai(novel, chapter, should_continue=None):
    try:
        from openai import OpenAI
        from app.services.ai_extraction_schemas import (
            ChapterExtraction,
            CharacterExtraction,
            ExtractedProgressionEvent,
            ItemExtraction,
            LifeEventExtraction,
            ProgressionExtraction,
            ProgressionAuditExtraction,
            ProgressionReasoningExtraction,
            SkillExtraction,
        )
    except ImportError as exc:
        raise RuntimeError("Install AI dependencies with: pip install -r requirements.txt") from exc

    ai_config = get_ai_config()
    client_kwargs = {
        "api_key": ai_config["api_key"],
        "timeout": ai_config["sdk_timeout"],
        "max_retries": 0,
    }

    if ai_config["base_url"]:
        client_kwargs["base_url"] = ai_config["base_url"]

    if ai_config["provider"] == "openrouter":
        client_kwargs["default_headers"] = {
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:5173"),
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "NovelWiki"),
        }

    ai_client = OpenAI(**client_kwargs)

    model = ai_config["model"]
    pipeline_mode = get_extraction_pipeline_mode()
    parallel_safe_stages = parallel_safe_ai_stages_enabled()
    conditional_progression_stages = conditional_progression_stages_enabled()
    stage_user_content = {}

    def user_content_for_stage(stage_name):
        if stage_name not in stage_user_content:
            memory_context = build_extraction_memory(novel, stage_name=stage_name)
            stage_user_content[stage_name] = (
                f"Novel: {novel.title}\n"
                f"Chapter {chapter.chapter_number}: {chapter.title}\n\n"
                f"{memory_context}\n\n"
                "Current chapter text:\n"
                f"{chapter.content}"
            )

        return stage_user_content[stage_name]

    current_app.logger.info(
        "Extraction chapter %s started: pipeline=%s parallel_safe_stages=%s "
        "max_concurrent_stages=%s conditional_progression_stages=%s "
        "provider=%s model=%s chars=%s",
        chapter.chapter_number,
        pipeline_mode,
        parallel_safe_stages,
        max_concurrent_ai_stages(),
        conditional_progression_stages,
        ai_config["provider"],
        model,
        len(chapter.content or ""),
    )
    logger = current_app.logger

    def extraction_count_summary(result):
        count_fields = (
            "characters",
            "progression_events",
            "skills",
            "items",
            "character_skills",
            "character_items",
            "life_events",
            "events",
        )
        counts = []

        for field_name in count_fields:
            if hasattr(result, field_name):
                counts.append(f"{field_name}={len(getattr(result, field_name) or [])}")

        return " ".join(counts) if counts else "no_count_fields"

    def run_ai_stage_attempt(
        stage_name,
        schema_model,
        system_prompt,
        stage_content,
        attempt,
    ):
        result_queue = queue.Queue(maxsize=1)
        started_at = time.perf_counter()
        telemetry = {
            "stage": stage_name,
            "attempt": attempt,
            "chapter_number": chapter.chapter_number,
            "provider": ai_config["provider"],
            "model": model,
        }

        def invoke_ai_request():
            try:
                result_queue.put(
                    (
                        "result",
                        parse_ai_json_response(
                            client=ai_client,
                            provider=ai_config["provider"],
                            model=model,
                            temperature=ai_config["temperature"],
                            system_prompt=system_prompt,
                            user_content=stage_content,
                            schema_model=schema_model,
                            request_timeout=ai_config["sdk_timeout"],
                            telemetry=telemetry,
                            provider_preferences=ai_config["provider_preferences"],
                        ),
                        telemetry,
                    )
                )
            except BaseException as error:
                result_queue.put(("error", error, telemetry))

        worker = threading.Thread(
            target=invoke_ai_request,
            name=f"ai-stage-{stage_name}-chapter-{chapter.chapter_number}-attempt-{attempt}",
            daemon=True,
        )
        worker.start()
        next_heartbeat_at = min(
            ai_config["stage_heartbeat_interval"],
            ai_config["stage_hard_timeout"],
        )

        while True:
            elapsed = time.perf_counter() - started_at
            remaining = ai_config["stage_hard_timeout"] - elapsed

            if remaining <= 0:
                error = AIStageTimeout(
                    f"AI stage '{stage_name}' attempt {attempt} exceeded "
                    f"hard timeout {ai_config['stage_hard_timeout']:.1f}s"
                )
                raise attach_ai_telemetry(error, telemetry)

            wait_for = min(max(0.05, remaining), max(0.05, next_heartbeat_at - elapsed))

            try:
                result_type, payload, result_telemetry = result_queue.get(
                    timeout=wait_for
                )
                if result_type == "error":
                    raise attach_ai_telemetry(payload, result_telemetry)

                return payload, result_telemetry
            except queue.Empty:
                elapsed = time.perf_counter() - started_at

                if elapsed >= next_heartbeat_at and elapsed < ai_config["stage_hard_timeout"]:
                    logger.info(
                        "Extraction chapter %s AI stage heartbeat: %s attempt=%s elapsed=%.2fs hard_timeout=%.0fs request_timeout=%.0fs",
                        chapter.chapter_number,
                        stage_name,
                        attempt,
                        elapsed,
                        ai_config["stage_hard_timeout"],
                        ai_config["request_timeout"],
                    )
                    next_heartbeat_at += ai_config["stage_heartbeat_interval"]

                continue

    def run_ai_stage(stage_name, schema_model, system_prompt):
        stage_content = user_content_for_stage(stage_name)
        logger.info(
            "Extraction chapter %s AI stage started: %s request_timeout=%.0fs "
            "connect_timeout=%.0fs read_timeout=%.0fs hard_timeout=%.0fs "
            "max_retries=%s input_chars=%s provider=%s model=%s",
            chapter.chapter_number,
            stage_name,
            ai_config["request_timeout"],
            ai_config["connect_timeout"],
            ai_config["read_timeout"],
            ai_config["stage_hard_timeout"],
            ai_config["stage_max_retries"],
            len(stage_content),
            ai_config["provider"],
            model,
        )
        stage_started_at = time.perf_counter()
        max_attempts = ai_config["stage_max_retries"] + 1

        for attempt in range(1, max_attempts + 1):
            attempt_started_at = time.perf_counter()

            try:
                result, telemetry = run_ai_stage_attempt(
                    stage_name,
                    schema_model,
                    system_prompt,
                    stage_content,
                    attempt,
                )
            except Exception as error:
                elapsed = time.perf_counter() - attempt_started_at
                stage_elapsed = time.perf_counter() - stage_started_at
                transient = is_transient_ai_error(error)
                retry_after = ai_error_retry_after_seconds(error)
                will_retry = transient and attempt < max_attempts
                telemetry = getattr(error, "ai_telemetry", {}) or {}
                failure_type = (
                    getattr(error, "code", None)
                    or ("hard_timeout" if isinstance(error, AIStageTimeout) else None)
                    or type(error).__name__
                )

                logger.exception(
                    "Extraction chapter %s AI stage attempt failed: %s "
                    "attempt=%s/%s elapsed=%.2fs stage_elapsed=%.2fs "
                    "provider=%s model=%s failure_type=%s error_class=%s "
                    "timeout_phase=%s status=%s code=%s request_id=%s "
                    "finish_reason=%s prompt_tokens=%s completion_tokens=%s "
                    "reasoning_tokens=%s cached_tokens=%s "
                    "strict_schema_fallback=%s transient=%s will_retry=%s error=%s",
                    chapter.chapter_number,
                    stage_name,
                    attempt,
                    max_attempts,
                    elapsed,
                    stage_elapsed,
                    ai_config["provider"],
                    model,
                    failure_type,
                    type(error).__name__,
                    ai_timeout_phase(error),
                    ai_error_status_code(error),
                    ai_error_code(error),
                    telemetry.get("request_id") or ai_error_request_id(error),
                    telemetry.get("finish_reason"),
                    telemetry.get("prompt_tokens"),
                    telemetry.get("completion_tokens"),
                    telemetry.get("reasoning_tokens"),
                    telemetry.get("cached_tokens"),
                    telemetry.get("strict_schema_fallback"),
                    transient,
                    will_retry,
                    error,
                )

                if will_retry:
                    bounded_retry_after = min(
                        retry_after or 0,
                        ai_config["stage_heartbeat_interval"],
                    )
                    if bounded_retry_after > 0:
                        logger.info(
                            "Extraction chapter %s AI stage retry sleeping: %s attempt=%s retry_after=%.2fs",
                            chapter.chapter_number,
                            stage_name,
                            attempt + 1,
                            bounded_retry_after,
                        )
                        time.sleep(bounded_retry_after)
                    continue

                logger.error(
                    "Extraction chapter %s AI stage failed: %s attempts=%s elapsed=%.2fs provider=%s model=%s",
                    chapter.chapter_number,
                    stage_name,
                    attempt,
                    stage_elapsed,
                    ai_config["provider"],
                    model,
                )
                raise RuntimeError(
                    f"AI stage '{stage_name}' failed after {stage_elapsed:.1f}s "
                    f"(timeout_phase={ai_timeout_phase(error) or 'unknown'}, "
                    f"connect={ai_config['connect_timeout']:.1f}s, "
                    f"read={ai_config['read_timeout']:.1f}s, "
                    f"request={ai_config['request_timeout']:.1f}s, "
                    f"hard={ai_config['stage_hard_timeout']:.1f}s): {error}"
                ) from error

            logger.info(
                "Extraction chapter %s AI stage finished: %s attempt=%s "
                "retries=%s elapsed=%.2fs stage_elapsed=%.2fs provider=%s "
                "model=%s response_model=%s upstream_provider=%s request_id=%s "
                "finish_reason=%s prompt_tokens=%s completion_tokens=%s "
                "total_tokens=%s reasoning_tokens=%s cached_tokens=%s "
                "strict_schema_fallback=%s %s",
                chapter.chapter_number,
                stage_name,
                attempt,
                attempt - 1,
                time.perf_counter() - attempt_started_at,
                time.perf_counter() - stage_started_at,
                ai_config["provider"],
                model,
                telemetry.get("response_model"),
                telemetry.get("upstream_provider"),
                telemetry.get("request_id"),
                telemetry.get("finish_reason"),
                telemetry.get("prompt_tokens"),
                telemetry.get("completion_tokens"),
                telemetry.get("total_tokens"),
                telemetry.get("reasoning_tokens"),
                telemetry.get("cached_tokens"),
                telemetry.get("strict_schema_fallback"),
                extraction_count_summary(result),
            )
            return result

        raise RuntimeError(f"AI stage '{stage_name}' failed without returning a result.")

    def run_parallel_ai_stages(stage_specs):
        worker_count = min(len(stage_specs), max_concurrent_ai_stages())

        # Build DB-backed memory on the Flask request thread before worker threads start.
        for stage_name in stage_specs:
            user_content_for_stage(stage_name)

        logger.info(
            "Extraction chapter %s parallel AI group started: stages=%s max_workers=%s",
            chapter.chapter_number,
            ",".join(stage_specs.keys()),
            worker_count,
        )
        started_at = time.perf_counter()
        results = {}
        executor = ThreadPoolExecutor(max_workers=worker_count)

        try:
            futures = {
                executor.submit(run_ai_stage, stage_name, schema_model, system_prompt): stage_name
                for stage_name, (schema_model, system_prompt) in stage_specs.items()
            }

            for future in as_completed(futures):
                stage_name = futures[future]

                try:
                    results[stage_name] = future.result()
                except Exception:
                    for pending_future in futures:
                        if pending_future is not future:
                            pending_future.cancel()

                    logger.exception(
                        "Extraction chapter %s parallel AI group failed: stage=%s elapsed=%.2fs",
                        chapter.chapter_number,
                        stage_name,
                        time.perf_counter() - started_at,
                    )
                    raise
        except Exception:
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        else:
            executor.shutdown(wait=True)

        logger.info(
            "Extraction chapter %s parallel AI group finished: stages=%s elapsed=%.2fs",
            chapter.chapter_number,
            ",".join(stage_specs.keys()),
            time.perf_counter() - started_at,
        )
        return results

    if pipeline_mode == AI_EXTRACTION_PIPELINE_MULTI_STAGE:
        if parallel_safe_stages:
            ensure_extraction_can_continue(should_continue)
            parallel_results = run_parallel_ai_stages(
                {
                    "character": (CharacterExtraction, CHARACTER_EXTRACTION_PROMPT),
                    "skill": (SkillExtraction, SKILL_EXTRACTION_PROMPT),
                    "item": (ItemExtraction, ITEM_EXTRACTION_PROMPT),
                    "progression": (
                        ProgressionExtraction,
                        PROGRESSION_EXTRACTION_PROMPT,
                    ),
                    "life_event": (
                        LifeEventExtraction,
                        LIFE_EVENT_EXTRACTION_PROMPT,
                    ),
                }
            )
            character_extraction = parallel_results["character"]
            skill_extraction = parallel_results["skill"]
            item_extraction = parallel_results["item"]
            progression_extraction = parallel_results["progression"]
            life_event_extraction = parallel_results["life_event"]
            ensure_extraction_can_continue(should_continue)
        else:
            character_extraction = run_ai_stage(
                "character",
                CharacterExtraction,
                CHARACTER_EXTRACTION_PROMPT,
            )
            ensure_extraction_can_continue(should_continue)

            progression_extraction = run_ai_stage(
                "progression",
                ProgressionExtraction,
                PROGRESSION_EXTRACTION_PROMPT,
            )
            ensure_extraction_can_continue(should_continue)

        tag_progression_sources(progression_extraction.progression_events, "progression_extractor")
        progression_stage_plan = {
            "run_audit": True,
            "run_reasoning": True,
            "reasons": ["conditional_progression_disabled"],
        }

        if conditional_progression_stages:
            progression_stage_plan = progression_stage_decision(
                chapter.content,
                progression_extraction.progression_events,
            )

        logger.info(
            "Extraction chapter %s progression follow-up plan: "
            "conditional=%s run_audit=%s run_reasoning=%s reasons=%s",
            chapter.chapter_number,
            conditional_progression_stages,
            progression_stage_plan["run_audit"],
            progression_stage_plan["run_reasoning"],
            ",".join(progression_stage_plan["reasons"]),
        )

        if progression_stage_plan["run_audit"]:
            progression_audit = run_ai_stage(
                "progression_audit",
                ProgressionAuditExtraction,
                PROGRESSION_AUDIT_PROMPT,
            )
            tag_progression_sources(
                progression_audit.progression_events,
                "progression_audit",
            )
            ensure_extraction_can_continue(should_continue)
        else:
            progression_audit = ProgressionAuditExtraction(progression_events=[])

        if progression_stage_plan["run_reasoning"]:
            progression_reasoning = run_ai_stage(
                "progression_reasoning",
                ProgressionReasoningExtraction,
                PROGRESSION_REASONING_PROMPT,
            )
            tag_progression_sources(
                progression_reasoning.progression_events,
                "progression_reasoning",
            )
            ensure_extraction_can_continue(should_continue)
        else:
            progression_reasoning = ProgressionReasoningExtraction(
                progression_events=[]
            )

        if not parallel_safe_stages:
            skill_extraction = run_ai_stage(
                "skill",
                SkillExtraction,
                SKILL_EXTRACTION_PROMPT,
            )
            ensure_extraction_can_continue(should_continue)

            item_extraction = run_ai_stage(
                "item",
                ItemExtraction,
                ITEM_EXTRACTION_PROMPT,
            )
            ensure_extraction_can_continue(should_continue)

            life_event_extraction = run_ai_stage(
                "life_event",
                LifeEventExtraction,
                LIFE_EVENT_EXTRACTION_PROMPT,
            )
            ensure_extraction_can_continue(should_continue)

        extraction = ChapterExtraction(
            characters=character_extraction.characters,
            skills=skill_extraction.skills,
            items=item_extraction.items,
            events=[],
            progression_events=[
                *progression_extraction.progression_events,
                *progression_audit.progression_events,
                *progression_reasoning.progression_events,
            ],
            life_events=life_event_extraction.life_events,
            character_skills=skill_extraction.character_skills,
            character_items=item_extraction.character_items,
        )
    else:
        extraction = run_ai_stage(
            "legacy_chapter",
            ChapterExtraction,
            BASE_EXTRACTION_SYSTEM_PROMPT,
        )
        tag_progression_sources(extraction.progression_events, "legacy_extractor")
        ensure_extraction_can_continue(should_continue)

        progression_audit = run_ai_stage(
            "progression_audit",
            ProgressionAuditExtraction,
            PROGRESSION_AUDIT_PROMPT,
        )
        tag_progression_sources(progression_audit.progression_events, "progression_audit")
        extraction.progression_events.extend(progression_audit.progression_events)

    current_app.logger.info(
        "Extraction chapter %s deterministic progression stage started",
        chapter.chapter_number,
    )
    regex_progression_events = detect_direct_cultivation_progression(
        novel,
        chapter,
        extraction,
        ExtractedProgressionEvent,
    )
    tag_progression_sources(regex_progression_events, "regex_detector")
    extraction.progression_events.extend(regex_progression_events)
    current_app.logger.info(
        "Extraction chapter %s deterministic progression stage finished: regex_progression_events=%s",
        chapter.chapter_number,
        len(regex_progression_events),
    )

    ensure_extraction_can_continue(should_continue)
    current_app.logger.info(
        "Extraction chapter %s save stage started: %s",
        chapter.chapter_number,
        extraction_count_summary(extraction),
    )
    started_at = time.perf_counter()
    summary = save_chapter_extraction(novel, chapter, extraction)
    current_app.logger.info(
        "Extraction chapter %s save stage finished: elapsed=%.2fs summary=%s",
        chapter.chapter_number,
        time.perf_counter() - started_at,
        summary,
    )
    return summary


def normalize_evidence_text(evidence_text):
    return (
        " ".join(evidence_text.split())
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("…", "...")
        .strip("\"'")
    )


def evidence_match_key(evidence_text):
    return "".join(
        character.lower()
        for character in normalize_evidence_text(evidence_text)
        if character.isalnum() or character.isspace()
    )


def add_evidence(
    novel,
    chapter,
    entity_type,
    entity_id,
    evidence_text,
    start_offset=None,
    end_offset=None,
    match_type=None,
    evidence_source=None,
):
    if not has_meaningful_evidence(evidence_text) and not (
        entity_type == "life_event" and death_text_has_strong_signal(evidence_text)
    ):
        return False

    verification = verify_evidence_text(
        chapter.content if chapter else "",
        evidence_text,
        start_offset=start_offset,
        end_offset=end_offset,
        match_type=match_type,
    )

    if not verification.verified:
        return False

    normalized_evidence = verification.evidence_text[:500]
    new_evidence_key = evidence_match_key(normalized_evidence)
    existing_evidence_rows = WikiEvidence.query.filter_by(
        novel_id=novel.id,
        chapter_id=chapter.id,
        entity_type=entity_type,
        entity_id=entity_id,
    ).all()

    for existing_evidence in existing_evidence_rows:
        if (
            verification.start_offset is not None
            and verification.end_offset is not None
            and existing_evidence.start_offset == verification.start_offset
            and existing_evidence.end_offset == verification.end_offset
        ):
            return False

        if (
            verification.start_offset is not None
            and verification.end_offset is not None
            and (
                existing_evidence.start_offset is not None
                or existing_evidence.end_offset is not None
            )
        ):
            continue

        if evidence_match_key(existing_evidence.evidence_text) == new_evidence_key:
            return False

    db.session.add(
        WikiEvidence(
            novel_id=novel.id,
            chapter_id=chapter.id,
            entity_type=entity_type,
            entity_id=entity_id,
            evidence_text=normalized_evidence,
            start_offset=verification.start_offset,
            end_offset=verification.end_offset,
            match_type=verification.match_type,
            evidence_source=evidence_source or "ai_verified",
        )
    )
    return True


def add_ai_evidence_audit(novel, chapter, entity_type, entity_id, candidate, source_extractor, summary=None):
    created = record_ai_evidence_audit_for_candidate(
        novel,
        chapter,
        entity_type,
        entity_id,
        candidate,
        source_extractor=source_extractor,
    )

    if created and summary is not None:
        summary["ai_evidence_audits_created"] = summary.get("ai_evidence_audits_created", 0) + 1

    return created


def source_extractor_set(source_extractor):
    return {
        source.strip()
        for source in str(source_extractor or "").split(",")
        if source.strip()
    }


def merge_source_extractors(record, *sources):
    merged_sources = source_extractor_set(getattr(record, "source_extractor", None))

    if (
        getattr(record, "review_status", None) == "approved"
        and not getattr(record, "auto_approved", False)
    ):
        return merged_sources

    for source in sources:
        if isinstance(source, set):
            merged_sources.update(source)
        elif isinstance(source, (list, tuple)):
            merged_sources.update(
                source_part
                for source_value in source
                for source_part in source_extractor_set(source_value)
            )
        else:
            merged_sources.update(source_extractor_set(source))

    if hasattr(record, "source_extractor") and merged_sources:
        record.source_extractor = ",".join(sorted(merged_sources))

    return merged_sources


def apply_revalidation_result(record, validation, source_extractor):
    return set_validation_metadata(record, validation, source_extractor)


def log_fact_revalidation(record, fact_type, reason, old_state, validation):
    current_app.logger.debug(
        "Fact revalidation: fact_type=%s id=%s reason=%s status=%s->%s confidence=%s->%s flags=%s->%s",
        fact_type,
        getattr(record, "id", None),
        reason,
        old_state.get("review_status"),
        getattr(record, "review_status", None),
        old_state.get("confidence_score"),
        validation.confidence_score if validation else None,
        old_state.get("risk_flags"),
        validation.risk_flags if validation else None,
    )


def record_validation_state(record):
    risk_flags = []
    raw_flags = getattr(record, "risk_flags", None)

    if raw_flags:
        try:
            import json

            risk_flags = json.loads(raw_flags)
        except (TypeError, ValueError):
            risk_flags = []

    return {
        "review_status": getattr(record, "review_status", None),
        "confidence_score": getattr(record, "confidence_score", None),
        "risk_flags": risk_flags,
    }


def wiki_evidence_type_for_record(record):
    if isinstance(record, Character):
        return "character"
    if isinstance(record, Skill):
        return "skill"
    if isinstance(record, Item):
        return "item"
    if isinstance(record, CharacterSkill):
        return "character_skill"
    if isinstance(record, CharacterItem):
        return "character_item"
    if isinstance(record, CharacterLifeEvent):
        return "life_event"
    if isinstance(record, CharacterProgressionEvent):
        return "progression"
    if isinstance(record, WikiEvent):
        return "event"

    return None


def verified_support_from_evidence(chapter, evidence, start_offset=None, end_offset=None, match_type=None):
    verification = verify_evidence_text(
        chapter.content if chapter else "",
        evidence,
        start_offset=start_offset,
        end_offset=end_offset,
        match_type=match_type,
    )

    if not verification.verified:
        return None

    return SimpleNamespace(
        chapter=chapter,
        evidence_text=verification.evidence_text,
        start_offset=verification.start_offset,
        end_offset=verification.end_offset,
        match_type=verification.match_type,
    )


def stored_evidence_supports_for_record(record):
    entity_type = wiki_evidence_type_for_record(record)

    if not entity_type or not getattr(record, "id", None):
        return []

    supports = []

    for evidence_row in WikiEvidence.query.filter_by(
        entity_type=entity_type,
        entity_id=record.id,
    ).all():
        evidence_chapter = db.session.get(Chapter, evidence_row.chapter_id)
        support = verified_support_from_evidence(
            evidence_chapter,
            evidence_row.evidence_text,
            start_offset=evidence_row.start_offset,
            end_offset=evidence_row.end_offset,
            match_type=evidence_row.match_type,
        )

        if support:
            supports.append(support)

    return supports


def revalidate_character_identity_from_record_support(novel, record, character, source_name):
    if not character or not record:
        return False

    if getattr(record, "review_status", None) != "approved":
        return False

    if record_has_active_serious_blockers(record):
        return False

    for support in stored_evidence_supports_for_record(record):
        if revalidate_character_identity_from_support(
            novel,
            support.chapter,
            character,
            support.evidence_text,
            source_name,
            entity_origin=ENTITY_ORIGIN_EXISTING,
        ):
            return True

    return False


def validation_context_for_record(
    novel,
    record,
    chapter,
    evidence,
    source_extractors,
    support,
    entity_origin=ENTITY_ORIGIN_EXISTING,
):
    offsets = {
        "evidence_start_offset": getattr(support, "start_offset", None),
        "evidence_end_offset": getattr(support, "end_offset", None),
        "evidence_match_type": getattr(support, "match_type", None),
    }

    if isinstance(record, Skill):
        return ValidationContext(
            novel=novel,
            chapter=chapter,
            fact_type="skill",
            entity_name=record.name,
            value=record.name,
            evidence=evidence,
            skill=record,
            entity_origin=ENTITY_ORIGIN_EXISTING,
            source_extractors=source_extractors,
            **offsets,
        )

    if isinstance(record, Item):
        return ValidationContext(
            novel=novel,
            chapter=chapter,
            fact_type="item",
            entity_name=record.name,
            value=record.name,
            evidence=evidence,
            item=record,
            entity_origin=ENTITY_ORIGIN_EXISTING,
            source_extractors=source_extractors,
            **offsets,
        )

    if isinstance(record, CharacterProgressionEvent):
        character = record.character or db.session.get(Character, record.character_id)
        progression_downgrade = (
            has_progression_downgrade(
                character,
                record.progression_type,
                record.new_value,
            )
            if character
            else False
        )
        attribution_status = progression_attribution_status(
            novel,
            chapter,
            character,
            record.new_value,
            evidence,
            source_extractors,
            progression_proxy(record, evidence, support),
            start_offset=offsets["evidence_start_offset"],
            end_offset=offsets["evidence_end_offset"],
            match_type=offsets["evidence_match_type"],
        )
        return ValidationContext(
            novel=novel,
            chapter=chapter,
            fact_type="progression",
            entity_name=character.name if character else None,
            value=record.new_value,
            evidence=evidence,
            character=character,
            entity_origin=entity_origin,
            source_extractors=source_extractors,
            conflict=progression_downgrade,
            progression_downgrade=progression_downgrade,
            attribution_uncertain=attribution_status == "attribution_uncertain",
            context_supported_attribution=(
                attribution_status == "context_supported_attribution"
            ),
            **offsets,
        )

    if isinstance(record, CharacterSkill):
        character = record.character or db.session.get(Character, record.character_id)
        skill = record.skill or db.session.get(Skill, record.skill_id)
        return ValidationContext(
            novel=novel,
            chapter=chapter,
            fact_type="character_skill",
            entity_name=f"{character.name} - {skill.name}",
            value=skill.name,
            evidence=evidence,
            character=character,
            skill=skill,
            relationship_type=record.relationship_type,
            entity_origin=ENTITY_ORIGIN_EXISTING,
            source_extractors=source_extractors,
            **offsets,
        )

    if isinstance(record, CharacterItem):
        character = record.character or db.session.get(Character, record.character_id)
        item = record.item or db.session.get(Item, record.item_id)
        return ValidationContext(
            novel=novel,
            chapter=chapter,
            fact_type="character_item",
            entity_name=f"{character.name} - {item.name}",
            value=item.name,
            evidence=evidence,
            character=character,
            item=item,
            relationship_type=record.relationship_type,
            entity_origin=ENTITY_ORIGIN_EXISTING,
            source_extractors=source_extractors,
            **offsets,
        )

    if isinstance(record, CharacterLifeEvent):
        character = record.character or db.session.get(Character, record.character_id)
        return ValidationContext(
            novel=novel,
            chapter=chapter,
            fact_type="life_event",
            entity_name=character.name,
            value=record.event_type,
            evidence=evidence,
            character=character,
            entity_origin=ENTITY_ORIGIN_EXISTING,
            source_extractors=source_extractors,
            description=record.description,
            reason=record.reason,
            **offsets,
        )

    return None


def best_validation_support_for_record(
    novel,
    record,
    incoming_evidence,
    source_extractors,
    chapter=None,
    start_offset=None,
    end_offset=None,
    match_type=None,
    entity_origin=ENTITY_ORIGIN_EXISTING,
):
    supports = []
    incoming_support = verified_support_from_evidence(
        chapter,
        incoming_evidence,
        start_offset=start_offset,
        end_offset=end_offset,
        match_type=match_type,
    )

    if incoming_support:
        supports.append(incoming_support)

    supports.extend(stored_evidence_supports_for_record(record))

    unique_supports = []
    seen = set()

    for support in supports:
        key = (
            getattr(support.chapter, "id", None),
            support.start_offset,
            support.end_offset,
            evidence_match_key(support.evidence_text),
        )

        if key in seen:
            continue

        unique_supports.append(support)
        seen.add(key)

    scored_supports = []

    for support in unique_supports:
        support_chapter = support.chapter

        if not support_chapter:
            continue

        validation_context = validation_context_for_record(
            novel,
            record,
            support_chapter,
            support.evidence_text,
            source_extractors,
            support,
            entity_origin=entity_origin,
        )

        if not validation_context:
            continue

        validation = validate_extracted_fact(validation_context)
        semantic_quality = 0

        if isinstance(record, CharacterProgressionEvent):
            semantic_quality = progression_candidate_quality(
                support_chapter,
                progression_proxy(record, support.evidence_text, support),
                character=validation_context.character,
                new_value=record.new_value,
            )

        scored_supports.append(
            (
                semantic_quality,
                1 if validation.auto_approved else 0,
                validation.confidence_score,
                -len(validation.risk_flags),
                support,
                validation,
                validation_context,
            )
        )

    if not scored_supports:
        return None, None, None

    _, _, _, _, support, validation, validation_context = max(
        scored_supports,
        key=lambda row: row[:4],
    )
    return support, validation, validation_context


def trace_record_for_fact_type(fact_type, record_id):
    model_by_fact_type = {
        "character": Character,
        "skill": Skill,
        "item": Item,
        "character_skill": CharacterSkill,
        "character_item": CharacterItem,
        "progression": CharacterProgressionEvent,
        "life_event": CharacterLifeEvent,
        "metadata": CharacterMetadataProposal,
        "event": WikiEvent,
    }
    model = model_by_fact_type.get(str(fact_type or "").strip().lower())

    if not model:
        return None

    return db.session.get(model, record_id)


def trace_chapter_for_record(record):
    chapter_id = getattr(record, "chapter_id", None)
    return db.session.get(Chapter, chapter_id) if chapter_id else None


def trace_support_payload(support):
    if not support:
        return None

    context = get_evidence_context(
        getattr(support.chapter, "content", "") if support.chapter else "",
        support.evidence_text,
        start_offset=support.start_offset,
        end_offset=support.end_offset,
        match_type=support.match_type,
    )
    verification = verify_evidence_text(
        getattr(support.chapter, "content", "") if support.chapter else "",
        support.evidence_text,
        start_offset=support.start_offset,
        end_offset=support.end_offset,
        match_type=support.match_type,
    )
    return {
        "chapter_id": getattr(support.chapter, "id", None),
        "chapter_number": getattr(support.chapter, "chapter_number", None),
        "evidence": support.evidence_text,
        "source": getattr(support, "source", None),
        "match_type": support.match_type,
        "start_offset": support.start_offset,
        "end_offset": support.end_offset,
        "verified": verification.verified,
        "context_found": context.found,
        "context": context.combined_context,
    }


def trace_ai_evidence_audits(record):
    entity_type = wiki_evidence_type_for_record(record)

    if isinstance(record, CharacterMetadataProposal):
        entity_type = "character_metadata_proposal"

    if not entity_type or not getattr(record, "id", None):
        return []

    return [
        audit.to_admin_dict()
        for audit in AIEvidenceAudit.query.filter_by(
            entity_type=entity_type,
            entity_id=record.id,
        ).order_by(AIEvidenceAudit.id.asc()).all()
    ]


def trace_stored_evidence_rows(record):
    entity_type = wiki_evidence_type_for_record(record)

    if not entity_type or not getattr(record, "id", None):
        return []

    rows = []
    for evidence_row in WikiEvidence.query.filter_by(
        entity_type=entity_type,
        entity_id=record.id,
    ).order_by(WikiEvidence.id.asc()).all():
        chapter = db.session.get(Chapter, evidence_row.chapter_id)
        support = verified_support_from_evidence(
            chapter,
            evidence_row.evidence_text,
            start_offset=evidence_row.start_offset,
            end_offset=evidence_row.end_offset,
            match_type=evidence_row.match_type,
        )
        rows.append(
            {
                **evidence_row.to_admin_dict(),
                "verified": bool(support),
                "context": trace_support_payload(support) if support else None,
            }
        )

    return rows


def trace_fact_validation(novel_id, fact_type, record_id, incoming_evidence=None):
    record = trace_record_for_fact_type(fact_type, record_id)

    if not record:
        return {
            "found": False,
            "fact_type": fact_type,
            "record_id": record_id,
        }

    novel = db.session.get(Novel, novel_id) or getattr(record, "novel", None)
    chapter = trace_chapter_for_record(record)
    source_extractors = source_extractor_set(getattr(record, "source_extractor", None))
    evidence = incoming_evidence if incoming_evidence is not None else getattr(record, "evidence", None)

    if not evidence:
        evidence_rows = trace_stored_evidence_rows(record)
        evidence = evidence_rows[0]["evidence_text"] if evidence_rows else None

    trace = {
        "found": True,
        "fact_type": fact_type,
        "record_id": record_id,
        "record_state": record_validation_state(record),
        "source_extractors": sorted(source_extractors),
        "ai_evidence_audits": trace_ai_evidence_audits(record),
        "stored_evidence": trace_stored_evidence_rows(record),
        "selected_support": None,
        "attribution": None,
        "relationship_semantic_analysis": None,
        "validator": None,
        "finalizer_state": record_validation_state(record),
    }

    if isinstance(record, CharacterMetadataProposal):
        character = record.character or db.session.get(Character, record.character_id)
        proposed_metadata = metadata_result_from_proposal(record)
        verification = verify_evidence_text(
            getattr(chapter, "content", "") if chapter else "",
            evidence,
        )
        evidence_context = get_evidence_context(
            getattr(chapter, "content", "") if chapter else "",
            verification.evidence_text if verification.verified else evidence,
            start_offset=verification.start_offset,
            end_offset=verification.end_offset,
            match_type=verification.match_type,
        )
        warnings = [
            *metadata_evidence_warnings(chapter, evidence),
            *metadata_semantic_warnings(
                character,
                record.field_name,
                proposed_metadata,
                verification.evidence_text if verification.verified else evidence,
                chapter,
            ),
        ] if character and proposed_metadata else []
        field_supported = (
            metadata_evidence_supports_field(
                character,
                record.field_name,
                proposed_metadata,
                verification.evidence_text if verification.verified else evidence,
                chapter,
            )
            if character and proposed_metadata
            else False
        )
        auto_approved = (
            can_auto_approve_metadata(
                character,
                record.field_name,
                proposed_metadata,
                warnings,
                verification.evidence_text if verification.verified else evidence,
                chapter,
            )
            if character and proposed_metadata
            else False
        )
        trace["selected_support"] = {
            "evidence": verification.evidence_text if verification.verified else evidence,
            "verified": verification.verified,
            "match_type": verification.match_type,
            "start_offset": verification.start_offset,
            "end_offset": verification.end_offset,
            "context_found": evidence_context.found,
            "context": evidence_context.combined_context,
        }
        trace["validator"] = {
            "field_supported": field_supported,
            "warnings": list(dict.fromkeys(warnings)),
            "auto_approved": auto_approved,
        }
        return trace

    support, validation, validation_context = best_validation_support_for_record(
        novel,
        record,
        evidence,
        source_extractors,
        chapter=chapter,
    )
    trace["selected_support"] = trace_support_payload(support)

    if validation_context:
        if validation_context.character:
            attribution = resolve_character_attribution(
                evidence_text=validation_context.evidence,
                local_context=get_evidence_context(
                    getattr(validation_context.chapter, "content", "")
                    if validation_context.chapter
                    else "",
                    validation_context.evidence,
                    start_offset=validation_context.evidence_start_offset,
                    end_offset=validation_context.evidence_end_offset,
                    match_type=validation_context.evidence_match_type,
                ).combined_context,
                candidate_characters=[validation_context.character],
                novel=novel,
                target_character=validation_context.character,
            )
            trace["attribution"] = asdict(attribution) if is_dataclass(attribution) else None

        if validation_context.fact_type in {"character_item", "character_skill"}:
            semantic_analysis = build_relationship_semantic_analysis(validation_context)
            trace["relationship_semantic_analysis"] = asdict(semantic_analysis)

    if validation:
        trace["validator"] = {
            "confidence_score": validation.confidence_score,
            "risk_flags": validation.risk_flags,
            "auto_approved": validation.auto_approved,
        }

    return trace


def revalidate_fact(
    novel,
    record,
    evidence,
    reason,
    source_extractors=None,
    chapter=None,
    start_offset=None,
    end_offset=None,
    match_type=None,
    evidence_source=None,
):
    if not record:
        return None

    if not has_meaningful_evidence(evidence):
        verification = verify_evidence_text(
            chapter.content if chapter else "",
            evidence,
            start_offset=start_offset,
            end_offset=end_offset,
            match_type=match_type,
        )

        if not verification.verified:
            return None

    old_state = record_validation_state(record)
    source_extractors = source_extractors or source_extractor_set(
        getattr(record, "source_extractor", None)
    )
    source_extractor_label = ",".join(sorted(source_extractors))

    if isinstance(record, Character):
        revalidate_character_identity_from_support(
            novel,
            chapter,
            record,
            evidence,
            source_extractor_label or "character",
            entity_origin=ENTITY_ORIGIN_EXISTING,
        )
        return None

    support, validation, validation_context = best_validation_support_for_record(
        novel,
        record,
        evidence,
        source_extractors,
        chapter=chapter,
        start_offset=start_offset,
        end_offset=end_offset,
        match_type=match_type,
    )

    if not validation:
        return None

    if isinstance(record, CharacterLifeEvent):
        prior_detail_flags = [
            flag
            for flag in old_state.get("risk_flags", [])
            if flag
            in {
                "life_event_cause_unsupported",
                "life_event_detail_speculative",
                "life_event_detail_unsupported",
            }
        ]
        record.description, record.reason, detail_flags = canonical_life_event_details(
            validation_context,
            record.description,
            record.reason,
        )
        combined_flags = []

        for flag in [
            *validation.risk_flags,
            *detail_flags,
            *prior_detail_flags,
        ]:
            if flag and flag not in combined_flags:
                combined_flags.append(flag)

        validation.risk_flags = combined_flags

    if isinstance(record, CharacterProgressionEvent):
        review_warnings = progression_review_warnings(
            novel,
            support.chapter,
            validation_context.character,
            record.progression_type,
            record.new_value,
            support.evidence_text,
        )

        if validation_context.context_supported_attribution:
            review_warnings = [
                warning
                for warning in review_warnings
                if warning != "Evidence may not directly name this character."
            ]

        record.review_warnings = "\n".join(review_warnings) if review_warnings else None

    apply_revalidation_result(record, validation, source_extractor_label)
    log_fact_revalidation(
        record,
        wiki_evidence_type_for_record(record) or record.__class__.__name__,
        reason,
        old_state,
        validation,
    )

    if isinstance(record, CharacterProgressionEvent) and validation_context.character:
        recalculate_character_current_progression(
            validation_context.character,
            record.progression_type,
        )

    return validation

    return None


def find_existing_by_name(model, novel, name):
    return model.query.filter(
        model.novel_id == novel.id,
        db.func.lower(model.name) == name.lower(),
    ).first()



def find_existing_skill(novel, name):
    skill = find_existing_by_name(Skill, novel, name)

    if skill:
        return skill

    alias = (
        SkillAlias.query.join(Skill)
        .filter(
            Skill.novel_id == novel.id,
            db.func.lower(SkillAlias.alias) == name.lower(),
        )
        .first()
    )

    return alias.skill if alias else None



def add_skill_alias(skill, alias, chapter, evidence):
    normalized_alias = normalize_alias(alias)

    if not normalized_alias or normalized_alias.lower() == skill.name.lower():
        return False

    existing_alias = SkillAlias.query.filter(
        SkillAlias.skill_id == skill.id,
        db.func.lower(SkillAlias.alias) == normalized_alias.lower(),
    ).first()

    if existing_alias:
        return False

    evidence_verification = verify_evidence_text(chapter.content if chapter else "", evidence)
    db.session.add(
        SkillAlias(
            skill_id=skill.id,
            alias=normalized_alias,
            first_seen_chapter_id=chapter.id,
            evidence=evidence_verification.evidence_text[:500]
            if evidence_verification.verified
            else None,
        )
    )
    return True


def normalize_importance(importance):
    normalized_importance = importance.strip().lower()

    if normalized_importance not in {"important", "minor"}:
        return "minor"

    return normalized_importance


SKILL_LIKE_NAME_TERMS = {
    "ability",
    "art",
    "chant",
    "curse",
    "hex",
    "mantra",
    "method",
    "skill",
    "spell",
    "technique",
}

PHYSICAL_TECHNIQUE_MEDIUM_TERMS = {
    "book",
    "jade slip",
    "manual",
    "physical record",
    "record",
    "scroll",
    "scripture",
    "tome",
    "written technique",
}

SKILL_USAGE_TERMS = {
    "activate",
    "activated",
    "cast",
    "casts",
    "cultivated",
    "learned",
    "performed",
    "practiced",
    "unleashed",
    "used",
}


def looks_like_skill_name(name):
    words = set(re.findall(r"[a-z0-9]+", (name or "").lower().replace("-", " ")))
    return bool(words & SKILL_LIKE_NAME_TERMS)


def evidence_describes_physical_skill_medium(evidence, category="", description=""):
    text = f"{evidence} {category} {description}".lower()
    return any(term in text for term in PHYSICAL_TECHNIQUE_MEDIUM_TERMS)


def evidence_describes_skill_usage(evidence, description=""):
    text = f"{evidence} {description}".lower()
    return any(term in text for term in SKILL_USAGE_TERMS)


def should_skip_item_as_skill_like(name, category, description, evidence):
    if not looks_like_skill_name(name):
        return False

    if value_has_physical_medium_noun(name):
        return False

    return True


def infer_item_category(name, category=None, evidence="", description=""):
    normalized_category = normalize_item_category(category)
    name_category = infer_item_category_from_name(name)

    if name_category and name_category not in {"Other", "Resource"}:
        return name_category

    evidence_category = infer_item_category_from_direct_evidence(name, evidence)

    if evidence_category:
        return evidence_category

    if name_category:
        return name_category

    if normalized_category and normalized_category != "Other":
        return normalized_category

    return "Other"


def infer_item_category_from_name(name):
    normalized_name = (name or "").lower().replace("-", " ")
    words = set(re.findall(r"[a-z0-9]+", normalized_name))

    if not words:
        return None

    if words & {"banner", "sign", "outlet", "workshop", "building", "fragment", "shard", "piece"}:
        return "Other"

    if words & {"pill", "pellet"}:
        return "Pill"

    if words & {"medicine", "drug"}:
        return "Medicine"

    if words & {"elixir"}:
        return "Medicine"

    if (
        words
        & {
            "book",
            "manual",
            "record",
            "scroll",
            "scripture",
            "slip",
            "text",
            "tome",
        }
        or "jade slip" in normalized_name
    ):
        return "Manual"

    if words & {"stone", "crystal", "ore", "rock", "gem", "essence", "resource"}:
        return "Resource"

    if words & {"sword", "blade", "dagger", "saber", "sabre", "spear", "bow", "axe", "weapon"}:
        return "Weapon"

    if words & {"mirror", "pendant", "ring", "talisman", "pennant", "seal"}:
        return "Artifact"

    if words & {"treasure"}:
        return "Treasure"

    if words & {"bottle", "gourd"}:
        return "Artifact"

    return None


def infer_item_category_from_direct_evidence(name, evidence):
    evidence_text = (evidence or "").lower().replace("-", " ")
    words = set(re.findall(r"[a-z0-9]+", evidence_text))
    name_words = set(re.findall(r"[a-z0-9]+", (name or "").lower().replace("-", " ")))

    if not words:
        return None

    instructional_text_terms = {
        "art",
        "cultivation",
        "formula",
        "instruction",
        "instructions",
        "manual",
        "method",
        "record",
        "scripture",
        "spell",
        "sutra",
        "technique",
    }

    if name_words & {"fragment", "inscription", "piece", "shard", "tablet"}:
        if words & instructional_text_terms:
            return "Manual"

        return "Other"

    if "magical item" in evidence_text and name_words & {
        "bottle",
        "gourd",
        "mirror",
        "pendant",
        "ring",
        "talisman",
    }:
        return "Artifact"

    return None


def is_wiki_significant_skill(name, category, description, evidence=""):
    if value_looks_like_progression_state(name, evidence):
        return False

    if value_looks_like_physical_item_concept(name):
        return False

    if evidence_describes_physical_skill_medium(evidence) and not evidence_describes_skill_usage(
        evidence,
        description,
    ):
        return False

    skill_text = f"{name} {category} {description} {evidence}".lower()
    name_text = f"{name} {category}".lower()
    blocked_terms = {
        "artifact",
        "bag",
        "bottle",
        "elixir",
        "essence",
        "gourd",
        "jade slip",
        "manual",
        "medicine",
        "mirror",
        "pendant",
        "pill",
        "robe",
        "scroll",
        "spirit stone",
        "stone",
        "tablet",
        "treasure",
        "weapon",
    }

    if any(term in name_text for term in blocked_terms):
        return False

    skill_terms = {
        "ability",
        "art",
        "breathing",
        "cultivation method",
        "form",
        "magic",
        "method",
        "power",
        "skill",
        "spell",
        "technique",
    }

    return any(term in skill_text for term in skill_terms)


def evidence_describes_separate_skill_with_item_name(name, evidence, description=""):
    if not looks_like_skill_name(name):
        return False

    return evidence_describes_skill_usage(evidence, description)


def existing_item_blocks_skill_link(novel, skill_name, evidence, description=""):
    item = find_existing_by_name(Item, novel, skill_name)

    if not item:
        return False

    return not evidence_describes_separate_skill_with_item_name(
        skill_name,
        evidence,
        description,
    )


def is_wiki_significant_item(name, category, description, evidence=""):
    if value_looks_like_intangible_skill_concept(name):
        return False

    if should_skip_item_as_skill_like(name, category, description, evidence):
        return False

    item_text = f"{name} {category} {description} {evidence}".lower()
    blocked_terms = {
        "robe",
        "servant robe",
        "uniform",
        "badge",
        "hemp robe",
        "clothing",
        "food",
        "furniture",
        "room",
        "bed",
        "common supply",
        "generic tool",
        "jade slip",
        "direction slip",
        "entry token",
        "pass",
        "paperwork",
    }

    important_terms = {
        "manual",
        "scripture",
        "technique",
        "artifact",
        "treasure",
        "weapon",
        "sword",
        "banner",
        "book",
        "crystal",
        "fragment",
        "gem",
        "inscribed",
        "inscription",
        "inscriptions",
        "jade slip",
        "ore",
        "pill",
        "record",
        "readable",
        "rock",
        "sign",
        "stone",
        "elixir",
        "resource",
        "scroll",
        "tablet",
        "talisman",
        "teeth",
        "text",
        "treasures",
        "writing",
        "written",
    }

    blocked_item_exceptions = {
        "magic",
        "magical",
        "artifact",
        "rank",
        "rank-signifying",
        "recurring",
        "named",
        "manual",
        "jade slip",
        "scripture",
        "technique",
        "talisman",
        "spirit tablet",
    }
    clothing_significance_terms = {
        "magical",
        "artifact",
        "rank",
        "rank-signifying",
        "recurring",
        "named",
    }

    if term_in_text(item_text, "robe") and not any(
        term_in_text(item_text, term) for term in clothing_significance_terms
    ):
        return False

    if any(term_in_text(item_text, term) for term in blocked_terms):
        return any(term_in_text(item_text, term) for term in blocked_item_exceptions)

    return any(term_in_text(item_text, term) for term in important_terms)


def term_in_text(text, term):
    normalized_text = " ".join((text or "").lower().replace("-", " ").split())
    normalized_term = " ".join((term or "").lower().replace("-", " ").split())

    if not normalized_text or not normalized_term:
        return False

    if re.search(rf"(?<!\w){re.escape(normalized_term)}(?!\w)", normalized_text):
        return True

    if not normalized_term.endswith("s"):
        plural_term = f"{normalized_term}s"
        return bool(re.search(rf"(?<!\w){re.escape(plural_term)}(?!\w)", normalized_text))

    return False


def find_existing_event(novel, chapter, event_type, title, description):
    title_key = event_match_key(title)
    event_rows = WikiEvent.query.filter(
        WikiEvent.novel_id == novel.id,
        WikiEvent.chapter_id == chapter.id,
        db.func.lower(WikiEvent.event_type) == event_type.lower(),
    ).all()

    for event in event_rows:
        if event_match_key(event.title) == title_key:
            return event

        if event_type == "item_acquired" and same_item_acquisition_event(
            title,
            description,
            event.title,
            event.description or "",
        ):
            return event

    return None


def same_item_acquisition_event(title, description, existing_title, existing_description):
    current_text = f"{title} {description}".lower()
    existing_text = f"{existing_title} {existing_description}".lower()

    return any(
        item_term in current_text and item_term in existing_text
        for item_term in {
            "dry spirit pill",
            "spirit condensation pill",
            "qi condensation manual",
            "copper mirror",
            "bag of holding",
            "demonic essence",
            "spirit stone",
        }
    )


def event_match_key(title):
    normalized_title = title.lower().replace("arrived", "arrival").replace("arrives", "arrival")
    words = [
        word
        for word in "".join(
            character if character.isalnum() or character.isspace() else " "
            for character in normalized_title
        ).split()
        if word not in {"at", "the", "a", "an", "to", "of"}
    ]

    return " ".join(words)


def is_major_location_event(title, description):
    event_text = f"{title} {description}".lower()
    major_terms = {
        "sect",
        "realm",
        "city",
        "continent",
        "mountain",
        "secret realm",
        "forbidden zone",
        "trial ground",
        "cave",
        "valley",
        "battlefield",
        "long-term base",
    }
    minor_terms = {
        "room",
        "quarter",
        "quarters",
        "pavilion",
        "courtyard",
        "shop",
        "hall",
        "treasure pavilion",
        "servants",
        "outer sect",
        "inner sect",
    }

    if any(term in event_text for term in minor_terms):
        return False

    return any(term in event_text for term in major_terms)


def has_specific_location_evidence(evidence):
    evidence_words = evidence.split()

    if len(evidence_words) < 5:
        return False

    evidence_text = evidence.lower()
    action_terms = {
        "arrived",
        "landed",
        "entered",
        "reached",
        "taken",
        "brought",
        "followed",
        "appeared",
        "transported",
        "flew",
    }

    return any(term in evidence_text for term in action_terms)


def is_disallowed_progression_like_event(title, description):
    event_text = f"{title} {description}".lower()
    progression_terms = {
        "promoted",
        "promotion",
        "breakthrough",
        "broke through",
        "outer sect",
        "inner sect",
        "disciple",
        "qi condensation",
        "cultivation level",
        "rank",
        "realm",
    }

    return any(term in event_text for term in progression_terms)



def has_meaningful_evidence(evidence):
    if not evidence:
        return False

    normalized_evidence = normalize_evidence_text(evidence)

    if len(normalized_evidence.split()) < 4:
        return False

    vague_phrases = {
        "discussion about",
        "remarks about",
        "murmurs in the crowd",
        "murmurs in crowd",
        "tagging along",
        "mentioned by others",
        "people talk about",
        "the chapter says",
    }

    return not any(phrase in normalized_evidence.lower() for phrase in vague_phrases)


def has_meaningful_progression_evidence(extracted_progression):
    if has_meaningful_evidence(extracted_progression.evidence):
        return True

    evidence = normalize_evidence_text(extracted_progression.evidence or "").lower()
    new_value = normalize_evidence_text(extracted_progression.new_value or "").lower()

    if not evidence or not new_value:
        return False

    value_supported = new_value in evidence or new_value.replace(" of ", " ") in evidence.replace(
        " of ", " "
    )

    return value_supported and evidence.endswith("!")


def record_skipped_progression(summary, extracted_progression, reason):
    summary["skipped_extractions"].append(
        {
            "type": "progression",
            "reason": reason,
            "character_name": getattr(extracted_progression, "character_name", None),
            "progression_type": getattr(extracted_progression, "progression_type", None),
            "new_value": getattr(extracted_progression, "new_value", None),
            "source_extractor": getattr(extracted_progression, "source_extractor", None),
        }
    )


def is_significant_rank_event(title, description):
    event_text = f"{title} {description}".lower()
    blocked_terms = {"servant", "worker", "laborer", "chore", "work without pay"}
    progression_terms = {
        "qi condensation",
        "cultivation",
        "level",
        "realm",
        "stage",
        "outer sect",
        "inner sect",
        "disciple",
        "rank",
        "class",
    }

    if any(term in event_text for term in blocked_terms):
        return any(term in event_text for term in progression_terms)

    return True



def normalize_life_event_type(event_type):
    normalized_type = event_type.strip().lower().replace(" ", "_")

    if normalized_type not in ALLOWED_LIFE_EVENT_TYPES:
        return None

    return normalized_type


def revalidate_pending_dead_status_metadata(character, chapter):
    if not character or not chapter:
        return 0

    revalidated = 0

    for proposal in CharacterMetadataProposal.query.filter_by(
        character_id=character.id,
        field_name="status",
        normalized_value="dead",
        review_status="pending",
    ).all():
        if revalidate_metadata_proposal(proposal, chapter):
            revalidated += 1

    return revalidated


def find_existing_life_event(character, chapter, event_type):
    return CharacterLifeEvent.query.filter_by(
        character_id=character.id,
        chapter_id=chapter.id,
        event_type=event_type,
    ).first()


def find_existing_character_skill_pair(character, skill):
    return CharacterSkill.query.filter_by(
        character_id=character.id,
        skill_id=skill.id,
    ).first()


def validate_skill_entity_from_relationship(
    novel,
    chapter,
    character,
    skill,
    evidence,
    created,
    start_offset=None,
    end_offset=None,
    match_type=None,
):
    if manually_reviewed_record(skill):
        return None

    if skill.review_status == "approved" and not automatic_approval_state_needs_repair(skill):
        return None

    validation = validate_extracted_fact(
        ValidationContext(
            novel=novel,
            chapter=chapter,
            fact_type="skill",
            entity_name=skill.name,
            value=skill.name,
            evidence=evidence,
            character=character,
            skill=skill,
            entity_origin=ENTITY_ORIGIN_NEW if created else ENTITY_ORIGIN_EXISTING,
            source_extractors={"skill", "character_skill"},
            evidence_start_offset=start_offset,
            evidence_end_offset=end_offset,
            evidence_match_type=match_type,
        )
    )
    set_validation_metadata(skill, validation, "skill,character_skill")
    return validation


def validate_item_entity_from_relationship(
    novel,
    chapter,
    character,
    item,
    evidence,
    created,
    start_offset=None,
    end_offset=None,
    match_type=None,
):
    if manually_reviewed_record(item):
        return None

    if item.review_status == "approved" and not automatic_approval_state_needs_repair(item):
        return None

    validation = validate_extracted_fact(
        ValidationContext(
            novel=novel,
            chapter=chapter,
            fact_type="item",
            entity_name=item.name,
            value=item.name,
            evidence=evidence,
            character=character,
            item=item,
            entity_origin=ENTITY_ORIGIN_NEW if created else ENTITY_ORIGIN_EXISTING,
            source_extractors={"item", "character_item"},
            evidence_start_offset=start_offset,
            evidence_end_offset=end_offset,
            evidence_match_type=match_type,
        )
    )
    set_validation_metadata(item, validation, "item,character_item")
    return validation


def merge_description(existing_description, new_description):
    if not existing_description:
        return new_description

    if not new_description or new_description in existing_description:
        return existing_description

    return f"{existing_description}\n\n{new_description}"



def save_chapter_extraction(novel, chapter, extraction):
    summary = {
        "characters_created": 0,
        "characters_updated": 0,
        "skills_created": 0,
        "skills_updated": 0,
        "items_created": 0,
        "items_updated": 0,
        "events_created": 0,
        "progression_events_created": 0,
        "metadata_proposals_created": 0,
        "character_skills_created": 0,
        "character_items_created": 0,
        "life_events_created": 0,
        "evidence_created": 0,
        "ai_evidence_audits_created": 0,
        "skipped_extractions": [],
    }

    recover_extraction_evidence(novel, chapter, extraction)

    progression_sources_by_key = {}
    progression_events_for_processing = sorted(
        extraction.progression_events,
        key=lambda extracted_progression: progression_candidate_quality(
            chapter,
            extracted_progression,
        ),
        reverse=True,
    )

    for extracted_progression in progression_events_for_processing:
        if not has_meaningful_progression_evidence(extracted_progression):
            continue

        progression_type = normalize_progression_type(extracted_progression.progression_type)
        new_value = canonicalize_progression_value(
            progression_type,
            extracted_progression.new_value,
        )

        if not is_valid_progression_value(progression_type, new_value):
            continue

        local_context = local_context_for_evidence(
            chapter,
            extracted_progression.evidence,
            new_value=new_value,
            start_offset=getattr(extracted_progression, "evidence_start_offset", None),
            end_offset=getattr(extracted_progression, "evidence_end_offset", None),
            match_type=getattr(extracted_progression, "evidence_match_type", None),
        )

        if not is_confirmed_progression(extracted_progression, local_context=local_context):
            continue

        if not is_valid_progression_value(progression_type, new_value):
            continue

        progression_key = progression_candidate_key(
            novel,
            extracted_progression,
            progression_type=progression_type,
            new_value=new_value,
        )
        source_extractor = getattr(extracted_progression, "source_extractor", None) or "unknown"
        progression_sources_by_key.setdefault(progression_key, set()).add(source_extractor)

    for extracted_character in extraction.characters:
        if not has_meaningful_evidence(extracted_character.evidence):
            continue

        extracted_name, extracted_aliases = select_canonical_character_name(
            extracted_character.name,
            extracted_character.aliases,
            extracted_character.evidence,
        )

        if not is_trackable_character_name(extracted_name):
            continue

        appearance_type = normalize_appearance_type(extracted_character.appearance_type)
        character = find_existing_character(novel, extracted_name)
        source_linked_variant = None

        if not character:
            character = find_existing_character_by_extracted_aliases(
                novel,
                [extracted_name, *extracted_aliases],
            )

        if not character:
            source_linked_variant = find_source_linked_character_variant(
                novel,
                extracted_name,
                extracted_character.evidence,
            )
            character = source_linked_variant

        possible_spelling_variant = (
            find_possible_character_spelling_variant(novel, extracted_name)
            if not character
            else None
        )
        character_created = False
        canonical_name_promoted = False
        promotion_old_name = None
        promotion_old_review_status = None

        if character:
            if should_promote_canonical_name(character.name, extracted_name):
                promotion_old_name = character.name
                promotion_old_review_status = character.review_status
                canonical_name_promoted = promote_character_canonical_name(
                    character,
                    extracted_name,
                    chapter,
                    extracted_character.evidence,
                )

            if not character.first_mentioned_chapter_id:
                character.first_mentioned_chapter_id = chapter.id

            if appearance_type == "appeared" and not character.first_appeared_chapter_id:
                character.first_appeared_chapter_id = chapter.id

            if not character.first_seen_chapter_id:
                character.first_seen_chapter_id = chapter.id

            summary["characters_updated"] += 1
        else:
            first_appeared_chapter_id = chapter.id if appearance_type == "appeared" else None
            character = Character(
                novel_id=novel.id,
                name=extracted_name,
                description=extracted_character.description,
                first_mentioned_chapter_id=chapter.id,
                first_appeared_chapter_id=first_appeared_chapter_id,
                first_seen_chapter_id=chapter.id,
                status="unknown",
                review_status="pending",
            )
            db.session.add(character)
            summary["characters_created"] += 1
            character_created = True

        db.session.flush()
        aliases_added = False

        alias_candidates = []
        seen_alias_candidates = set()

        for alias in [
            *extracted_aliases,
            *supported_title_alias_variants(extracted_name, extracted_character.evidence),
            *(
                [extracted_name]
                if source_linked_variant
                and extracted_name.lower() != character.name.lower()
                else []
            ),
        ]:
            normalized_candidate = normalize_alias(alias)
            candidate_key = normalized_candidate.lower()

            if (
                not normalized_candidate
                or candidate_key == character.name.lower()
                or candidate_key in seen_alias_candidates
            ):
                continue

            alias_candidates.append(normalized_candidate)
            seen_alias_candidates.add(candidate_key)

        for alias in alias_candidates:
            if add_character_alias(
                character,
                alias,
                chapter,
                extracted_character.evidence,
            ):
                aliases_added = True

        metadata_evidence = getattr(
            extracted_character,
            "original_evidence",
            extracted_character.evidence,
        )

        summary["metadata_proposals_created"] += create_character_metadata_proposals(
            novel,
            chapter,
            character,
            extracted_character.metadata,
            metadata_evidence,
        )

        if not character_created:
            revalidate_character_identity_from_support(
                novel,
                chapter,
                character,
                extracted_character.evidence,
                "metadata",
                entity_origin=ENTITY_ORIGIN_EXISTING,
            )

        durable_update = character_created or is_durable_character_update(
            character,
            extracted_character,
            appearance_type,
            aliases_added or canonical_name_promoted,
        )

        if durable_update:
            character.description = merge_description(
                character.description,
                extracted_character.description,
            )

        if durable_update and add_evidence(
            novel,
            chapter,
            "character",
            character.id,
            extracted_character.evidence,
            **evidence_support_kwargs(extracted_character),
        ):
            summary["evidence_created"] += 1

        validation = validate_extracted_fact(
            ValidationContext(
                novel=novel,
                chapter=chapter,
                fact_type="character",
                entity_name=character.name,
                value=character.name,
                evidence=extracted_character.evidence,
                character=character,
                entity_origin=(
                    ENTITY_ORIGIN_NEW if character_created else ENTITY_ORIGIN_EXISTING
                ),
                source_extractors={"character"},
                existing_record=possible_spelling_variant,
                **validation_evidence_kwargs(extracted_character),
            )
        )
        set_validation_metadata(character, validation, "character")
        add_ai_evidence_audit(
            novel,
            chapter,
            "character",
            character.id,
            extracted_character,
            "character",
            summary,
        )

        if canonical_name_promoted and promotion_old_name:
            maybe_approve_promoted_character(
                novel,
                chapter,
                character,
                promotion_old_name,
                promotion_old_review_status,
                extracted_character.evidence,
            )
            revalidate_character_identity_from_support(
                novel,
                chapter,
                character,
                extracted_character.evidence,
                "character",
                entity_origin=ENTITY_ORIGIN_EXISTING,
            )

    for extracted_skill in extraction.skills:
        if not has_meaningful_evidence(extracted_skill.evidence):
            continue

        if not is_wiki_significant_skill(
            extracted_skill.name,
            extracted_skill.category,
            extracted_skill.description,
            extracted_skill.evidence,
        ):
            continue

        skill_category = normalize_skill_category(extracted_skill.category) or "Other"
        skill = find_existing_skill(novel, extracted_skill.name)
        skill_created = False

        if skill:
            skill.category = skill.category or skill_category
            skill.description = merge_description(skill.description, extracted_skill.description)
            summary["skills_updated"] += 1
        else:
            skill = Skill(
                novel_id=novel.id,
                name=extracted_skill.name,
                category=skill_category,
                description=extracted_skill.description,
                review_status="pending",
            )
            db.session.add(skill)
            summary["skills_created"] += 1
            skill_created = True

        db.session.flush()
        validation = validate_extracted_fact(
            ValidationContext(
                novel=novel,
                chapter=chapter,
                fact_type="skill",
                entity_name=skill.name,
                value=skill.name,
                evidence=extracted_skill.evidence,
                skill=skill,
                entity_origin=ENTITY_ORIGIN_NEW if skill_created else ENTITY_ORIGIN_EXISTING,
                source_extractors={"skill"},
                **validation_evidence_kwargs(extracted_skill),
            )
        )
        set_validation_metadata(skill, validation, "skill")
        add_ai_evidence_audit(
            novel,
            chapter,
            "skill",
            skill.id,
            extracted_skill,
            "skill",
            summary,
        )

        for alias in extracted_skill.aliases:
            add_skill_alias(skill, alias, chapter, extracted_skill.evidence)

        if add_evidence(
            novel,
            chapter,
            "skill",
            skill.id,
            extracted_skill.evidence,
            **evidence_support_kwargs(extracted_skill),
        ):
            summary["evidence_created"] += 1

    for extracted_item in extraction.items:
        if not has_meaningful_evidence(extracted_item.evidence):
            continue

        if normalize_importance(extracted_item.importance) != "important":
            continue

        if not is_wiki_significant_item(
            extracted_item.name,
            extracted_item.category,
            extracted_item.description,
            extracted_item.evidence,
        ):
            continue

        item_category = infer_item_category(
            extracted_item.name,
            extracted_item.category,
            extracted_item.evidence,
            extracted_item.description,
        )
        item = find_existing_by_name(Item, novel, extracted_item.name)
        item_created = False

        if item:
            item.category = item.category or item_category
            item.description = merge_description(item.description, extracted_item.description)
            summary["items_updated"] += 1
        else:
            item = Item(
                novel_id=novel.id,
                name=extracted_item.name,
                category=item_category,
                description=extracted_item.description,
                review_status="pending",
            )
            db.session.add(item)
            summary["items_created"] += 1
            item_created = True

        db.session.flush()
        validation = validate_extracted_fact(
            ValidationContext(
                novel=novel,
                chapter=chapter,
                fact_type="item",
                entity_name=item.name,
                value=item.name,
                evidence=extracted_item.evidence,
                item=item,
                entity_origin=ENTITY_ORIGIN_NEW if item_created else ENTITY_ORIGIN_EXISTING,
                source_extractors={"item"},
                **validation_evidence_kwargs(extracted_item),
            )
        )
        set_validation_metadata(item, validation, "item")
        add_ai_evidence_audit(
            novel,
            chapter,
            "item",
            item.id,
            extracted_item,
            "item",
            summary,
        )

        if add_evidence(
            novel,
            chapter,
            "item",
            item.id,
            extracted_item.evidence,
            **evidence_support_kwargs(extracted_item),
        ):
            summary["evidence_created"] += 1

    for extracted_relationship in extraction.character_skills:
        if not has_meaningful_evidence(extracted_relationship.evidence):
            continue

        character = find_existing_character(novel, extracted_relationship.character_name)
        skill = find_existing_skill(novel, extracted_relationship.skill_name)
        skill_created = False

        if not character:
            character, _ = resolve_or_create_character_from_support(
                novel,
                chapter,
                extracted_relationship.character_name,
                extracted_relationship.evidence,
                "character_skill",
                summary,
            )

            if not character:
                continue

        if not is_wiki_significant_skill(
            extracted_relationship.skill_name,
            "technique",
            extracted_relationship.description,
            extracted_relationship.evidence,
        ):
            continue

        if existing_item_blocks_skill_link(
            novel,
            extracted_relationship.skill_name,
            extracted_relationship.evidence,
            extracted_relationship.description,
        ):
            continue

        if not skill:
            skill = Skill(
                novel_id=novel.id,
                name=extracted_relationship.skill_name,
                category="technique",
                description=extracted_relationship.description,
                review_status="pending",
            )
            db.session.add(skill)
            db.session.flush()
            summary["skills_created"] += 1
            skill_created = True

            if add_evidence(
                novel,
                chapter,
                "skill",
                skill.id,
                extracted_relationship.evidence,
                **evidence_support_kwargs(extracted_relationship),
            ):
                summary["evidence_created"] += 1
            add_ai_evidence_audit(
                novel,
                chapter,
                "skill",
                skill.id,
                extracted_relationship,
                "character_skill",
                summary,
            )

            validate_skill_entity_from_relationship(
                novel,
                chapter,
                character,
                skill,
                extracted_relationship.evidence,
                created=True,
                **entity_validation_support_kwargs(extracted_relationship),
            )

        existing_skill_pair = find_existing_character_skill_pair(character, skill)

        if existing_skill_pair:
            old_sources = source_extractor_set(existing_skill_pair.source_extractor)
            existing_skill_pair.relationship_type = "has"
            existing_skill_pair.description = merge_description(
                existing_skill_pair.description,
                extracted_relationship.description,
            )
            existing_chapter = db.session.get(Chapter, existing_skill_pair.chapter_id)

            if (
                not existing_chapter
                or chapter.chapter_number < existing_chapter.chapter_number
            ):
                existing_skill_pair.chapter_id = chapter.id

            evidence_changed = add_evidence(
                novel,
                chapter,
                "character_skill",
                existing_skill_pair.id,
                extracted_relationship.evidence,
                **evidence_support_kwargs(extracted_relationship),
            )

            if evidence_changed:
                summary["evidence_created"] += 1
            add_ai_evidence_audit(
                novel,
                chapter,
                "character_skill",
                existing_skill_pair.id,
                extracted_relationship,
                "character_skill",
                summary,
            )

            merged_sources = merge_source_extractors(
                existing_skill_pair,
                "character_skill",
            )
            source_changed = merged_sources != old_sources

            if evidence_changed or source_changed:
                validation = revalidate_fact(
                    novel,
                    existing_skill_pair,
                    extracted_relationship.evidence,
                    "evidence_merged",
                    source_extractors=merged_sources,
                    chapter=chapter,
                    **evidence_support_kwargs(extracted_relationship),
                )

                if validation and validation.auto_approved:
                    revalidate_character_identity_from_record_support(
                        novel,
                        existing_skill_pair,
                        character,
                        "character_skill",
                    )
                    validate_skill_entity_from_relationship(
                        novel,
                        chapter,
                        character,
                        skill,
                        extracted_relationship.evidence,
                        created=skill_created,
                        **entity_validation_support_kwargs(extracted_relationship),
                    )
            continue

        relationship = CharacterSkill(
            novel_id=novel.id,
            character_id=character.id,
            skill_id=skill.id,
            chapter_id=chapter.id,
            relationship_type="has",
            description=extracted_relationship.description,
            review_status="pending",
        )
        db.session.add(relationship)
        db.session.flush()

        validation = validate_extracted_fact(
            ValidationContext(
                novel=novel,
                chapter=chapter,
                fact_type="character_skill",
                entity_name=f"{character.name} - {skill.name}",
                value=skill.name,
                evidence=extracted_relationship.evidence,
                character=character,
                skill=skill,
                entity_origin=(
                    ENTITY_ORIGIN_NEW if skill_created else ENTITY_ORIGIN_EXISTING
                ),
                source_extractors={"character_skill"},
                **validation_evidence_kwargs(extracted_relationship),
            )
        )
        set_validation_metadata(relationship, validation, "character_skill")
        add_ai_evidence_audit(
            novel,
            chapter,
            "character_skill",
            relationship.id,
            extracted_relationship,
            "character_skill",
            summary,
        )

        if add_evidence(
            novel,
            chapter,
            "character_skill",
            relationship.id,
            extracted_relationship.evidence,
            **evidence_support_kwargs(extracted_relationship),
        ):
            summary["evidence_created"] += 1

        revalidated_relationship = revalidate_fact(
            novel,
            relationship,
            extracted_relationship.evidence,
            "initial_evidence_attached",
            source_extractors={"character_skill"},
            chapter=chapter,
            **evidence_support_kwargs(extracted_relationship),
        )

        if revalidated_relationship:
            validation = revalidated_relationship

        if validation.auto_approved:
            revalidate_character_identity_from_record_support(
                novel,
                relationship,
                character,
                "character_skill",
            )
            validate_skill_entity_from_relationship(
                novel,
                chapter,
                character,
                skill,
                extracted_relationship.evidence,
                created=skill_created,
                **entity_validation_support_kwargs(extracted_relationship),
            )

        summary["character_skills_created"] += 1

    for extracted_relationship in getattr(extraction, "character_items", []):
        if not has_meaningful_evidence(extracted_relationship.evidence):
            continue

        character = find_existing_character(novel, extracted_relationship.character_name)
        item = find_existing_by_name(Item, novel, extracted_relationship.item_name)
        relationship_type = normalize_character_item_relationship_type(
            extracted_relationship.relationship_type
        )

        if not character:
            character, _ = resolve_or_create_character_from_support(
                novel,
                chapter,
                extracted_relationship.character_name,
                extracted_relationship.evidence,
                "character_item",
                summary,
            )

        if not character:
            summary["skipped_extractions"].append(
                {
                    "source_extractor": "character_item",
                    "reason": "ambiguous_owner",
                    "character_name": extracted_relationship.character_name,
                    "item_name": extracted_relationship.item_name,
                    "relationship_type": relationship_type,
                    "evidence": normalize_evidence_text(extracted_relationship.evidence)[:500],
                }
            )
            continue

        item_created = False

        if not item:
            if not is_wiki_significant_item(
                extracted_relationship.item_name,
                "Other",
                extracted_relationship.description,
                extracted_relationship.evidence,
            ):
                continue

            item = Item(
                novel_id=novel.id,
                name=extracted_relationship.item_name,
                    category=infer_item_category(
                        extracted_relationship.item_name,
                        "Other",
                        extracted_relationship.evidence,
                        extracted_relationship.description,
                    ),
                description=extracted_relationship.description,
                review_status="pending",
            )
            db.session.add(item)
            db.session.flush()
            summary["items_created"] += 1
            item_created = True

            validation = validate_extracted_fact(
                ValidationContext(
                    novel=novel,
                    chapter=chapter,
                    fact_type="item",
                    entity_name=item.name,
                    value=item.name,
                    evidence=extracted_relationship.evidence,
                    item=item,
                    entity_origin=ENTITY_ORIGIN_NEW,
                    source_extractors={"item", "character_item"},
                    **validation_evidence_kwargs(extracted_relationship),
                )
            )
            set_validation_metadata(item, validation, "item")
            add_ai_evidence_audit(
                novel,
                chapter,
                "item",
                item.id,
                extracted_relationship,
                "character_item",
                summary,
            )

            if add_evidence(
                novel,
                chapter,
                "item",
                item.id,
                extracted_relationship.evidence,
                **evidence_support_kwargs(extracted_relationship),
            ):
                summary["evidence_created"] += 1

        existing_item_relationship = find_existing_character_item(
            character,
            item,
            relationship_type,
        )

        if existing_item_relationship:
            old_sources = source_extractor_set(existing_item_relationship.source_extractor)
            existing_item_relationship.description = merge_description(
                existing_item_relationship.description,
                extracted_relationship.description,
            )
            existing_chapter = db.session.get(Chapter, existing_item_relationship.chapter_id)

            if (
                not existing_chapter
                or chapter.chapter_number < existing_chapter.chapter_number
            ):
                existing_item_relationship.chapter_id = chapter.id

            evidence_changed = add_evidence(
                novel,
                chapter,
                "character_item",
                existing_item_relationship.id,
                extracted_relationship.evidence,
                **evidence_support_kwargs(extracted_relationship),
            )

            if evidence_changed:
                summary["evidence_created"] += 1
            add_ai_evidence_audit(
                novel,
                chapter,
                "character_item",
                existing_item_relationship.id,
                extracted_relationship,
                "character_item",
                summary,
            )

            merged_sources = merge_source_extractors(
                existing_item_relationship,
                "character_item",
                "item",
            )
            source_changed = merged_sources != old_sources

            if evidence_changed or source_changed:
                validation = revalidate_fact(
                    novel,
                    existing_item_relationship,
                    extracted_relationship.evidence,
                    "evidence_merged",
                    source_extractors=merged_sources,
                    chapter=chapter,
                    **evidence_support_kwargs(extracted_relationship),
                )

                if validation and validation.auto_approved:
                    revalidate_character_identity_from_record_support(
                        novel,
                        existing_item_relationship,
                        character,
                        "character_item",
                    )
                    validate_item_entity_from_relationship(
                        novel,
                        chapter,
                        character,
                        item,
                        extracted_relationship.evidence,
                        created=item_created,
                        **entity_validation_support_kwargs(extracted_relationship),
                    )
            continue

        relationship = CharacterItem(
            novel_id=novel.id,
            character_id=character.id,
            item_id=item.id,
            chapter_id=chapter.id,
            relationship_type=relationship_type,
            description=extracted_relationship.description,
            review_status="pending",
        )
        db.session.add(relationship)
        db.session.flush()

        validation = validate_extracted_fact(
            ValidationContext(
                novel=novel,
                chapter=chapter,
                fact_type="character_item",
                entity_name=f"{character.name} - {item.name}",
                value=item.name,
                evidence=extracted_relationship.evidence,
                character=character,
                item=item,
                relationship_type=relationship_type,
                entity_origin=(
                    ENTITY_ORIGIN_NEW if item_created else ENTITY_ORIGIN_EXISTING
                ),
                source_extractors={"character_item", "item"},
                ambiguous_owner=not character,
                **validation_evidence_kwargs(extracted_relationship),
            )
        )
        set_validation_metadata(relationship, validation, "character_item")
        add_ai_evidence_audit(
            novel,
            chapter,
            "character_item",
            relationship.id,
            extracted_relationship,
            "character_item",
            summary,
        )

        if add_evidence(
            novel,
            chapter,
            "character_item",
            relationship.id,
            extracted_relationship.evidence,
            **evidence_support_kwargs(extracted_relationship),
        ):
            summary["evidence_created"] += 1

        revalidated_relationship = revalidate_fact(
            novel,
            relationship,
            extracted_relationship.evidence,
            "initial_evidence_attached",
            source_extractors={"character_item", "item"},
            chapter=chapter,
            **evidence_support_kwargs(extracted_relationship),
        )

        if revalidated_relationship:
            validation = revalidated_relationship

        if validation.auto_approved:
            revalidate_character_identity_from_record_support(
                novel,
                relationship,
                character,
                "character_item",
            )
            validate_item_entity_from_relationship(
                novel,
                chapter,
                character,
                item,
                extracted_relationship.evidence,
                created=item_created,
                **entity_validation_support_kwargs(extracted_relationship),
            )

        summary["character_items_created"] += 1

    for extracted_event in extraction.events:
        # Timeline events are intentionally disabled for this MVP phase.
        # Keep the table/API in place so we can re-enable them later.
        continue

        if not has_meaningful_evidence(extracted_event.evidence):
            continue

        event_type = extracted_event.event_type.strip().lower().replace(" ", "_")

        if event_type not in ALLOWED_EVENT_TYPES:
            continue

        if is_disallowed_progression_like_event(
            extracted_event.title,
            extracted_event.description,
        ):
            continue

        if event_type == "location_arrived" and not is_major_location_event(
            extracted_event.title,
            extracted_event.description,
        ):
            continue

        if event_type == "location_arrived" and not has_specific_location_evidence(
            extracted_event.evidence,
        ):
            continue

        if event_type == "rank_changed" and not is_significant_rank_event(
            extracted_event.title,
            extracted_event.description,
        ):
            continue

        if event_type == "item_acquired" and not is_important_item_event(
            novel,
            extracted_event.title,
            extracted_event.description,
        ):
            continue

        event = find_existing_event(
            novel,
            chapter,
            event_type,
            extracted_event.title,
            extracted_event.description,
        )

        if event:
            event.description = merge_description(event.description, extracted_event.description)
        else:
            event = WikiEvent(
                novel_id=novel.id,
                chapter_id=chapter.id,
                event_type=event_type,
                title=extracted_event.title,
                description=extracted_event.description,
                review_status="pending",
            )
            db.session.add(event)
            summary["events_created"] += 1

        db.session.flush()
        if add_evidence(novel, chapter, "event", event.id, extracted_event.evidence):
            summary["evidence_created"] += 1

    saved_progression_by_key = {}

    for extracted_progression in progression_events_for_processing:
        if not has_meaningful_progression_evidence(extracted_progression):
            continue

        progression_type = normalize_progression_type(extracted_progression.progression_type)
        new_value = canonicalize_progression_value(
            progression_type,
            extracted_progression.new_value,
        )
        old_value = canonicalize_progression_value(
            progression_type,
            extracted_progression.old_value,
        )

        if not is_valid_progression_value(progression_type, new_value):
            record_skipped_progression(
                summary,
                extracted_progression,
                "invalid_progression_placeholder",
            )
            continue

        character = find_existing_character(novel, extracted_progression.character_name)
        character_created_from_progression = False

        if not character:
            character, character_created_from_progression = resolve_or_create_character_from_support(
                novel,
                chapter,
                extracted_progression.character_name,
                extracted_progression.evidence,
                "progression",
                summary,
            )

        local_context = local_context_for_evidence(
            chapter,
            extracted_progression.evidence,
            new_value=new_value,
            character=character,
            start_offset=getattr(extracted_progression, "evidence_start_offset", None),
            end_offset=getattr(extracted_progression, "evidence_end_offset", None),
            match_type=getattr(extracted_progression, "evidence_match_type", None),
        )

        if not is_confirmed_progression(extracted_progression, local_context=local_context):
            continue

        if not character:
            if not is_trackable_character_name(extracted_progression.character_name):
                continue

            character = Character(
                novel_id=novel.id,
                name=extracted_progression.character_name,
                description=None,
                first_mentioned_chapter_id=chapter.id,
                first_appeared_chapter_id=None,
                first_seen_chapter_id=chapter.id,
                status="unknown",
                review_status="pending",
            )
            db.session.add(character)
            db.session.flush()
            summary["characters_created"] += 1
            character_created_from_progression = True

        if value_looks_like_skill_or_technique(new_value):
            continue

        if progression_values_match(
            progression_type,
            old_value,
            new_value,
        ):
            continue

        progression_key = progression_candidate_key(
            novel,
            extracted_progression,
            character=character,
            progression_type=progression_type,
            new_value=new_value,
        )
        fallback_progression_key = progression_candidate_key(
            novel,
            extracted_progression,
            progression_type=progression_type,
            new_value=new_value,
        )
        source_extractor = getattr(extracted_progression, "source_extractor", None) or "unknown"
        source_extractors = set()
        source_extractors.update(progression_sources_by_key.get(progression_key, set()))
        source_extractors.update(progression_sources_by_key.get(fallback_progression_key, set()))

        if not source_extractors:
            source_extractors.add(source_extractor)

        if progression_key in saved_progression_by_key:
            existing_same_run_progression = saved_progression_by_key[progression_key]
            old_sources = source_extractor_set(existing_same_run_progression.source_extractor)
            existing_sources = merge_source_extractors(
                existing_same_run_progression,
                source_extractors,
            )

            evidence_changed = add_evidence(
                novel,
                chapter,
                "progression",
                existing_same_run_progression.id,
                extracted_progression.evidence,
                **evidence_support_kwargs(extracted_progression),
            )

            if evidence_changed:
                summary["evidence_created"] += 1
            add_ai_evidence_audit(
                novel,
                chapter,
                "progression",
                existing_same_run_progression.id,
                extracted_progression,
                source_extractor,
                summary,
            )

            if evidence_changed or existing_sources != old_sources:
                best_support = progression_record_best_evidence_support(
                    existing_same_run_progression
                )
                best_evidence = (
                    best_support.evidence_text if best_support else extracted_progression.evidence
                )
                revalidate_progression_record(
                    novel,
                    existing_same_run_progression,
                    best_evidence,
                    existing_sources,
                    chapter=best_support.chapter if best_support else chapter,
                    start_offset=best_support.start_offset if best_support else None,
                    end_offset=best_support.end_offset if best_support else None,
                    match_type=best_support.match_type if best_support else None,
                )
                if existing_same_run_progression.review_status == "approved":
                    revalidate_character_identity_from_record_support(
                        novel,
                        existing_same_run_progression,
                        character,
                        "progression",
                    )
                recalculate_character_current_progression(character, progression_type)

            continue

        existing_progression = find_existing_progression(
            character,
            progression_type,
            new_value,
        )

        if existing_progression:
            old_sources = source_extractor_set(existing_progression.source_extractor)
            merged_sources = merge_source_extractors(existing_progression, source_extractors)
            source_changed = merged_sources != old_sources
            value_changed = False

            if is_more_specific_progression_value(
                progression_type,
                existing_progression.new_value,
                new_value,
            ):
                existing_progression.new_value = new_value
                value_changed = True
                existing_progression.description = merge_description(
                    existing_progression.description,
                    extracted_progression.description,
                )
                recalculate_character_current_progression(character, progression_type)

            evidence_changed = add_evidence(
                novel,
                chapter,
                "progression",
                existing_progression.id,
                extracted_progression.evidence,
                **evidence_support_kwargs(extracted_progression),
            )

            if evidence_changed:
                summary["evidence_created"] += 1
            add_ai_evidence_audit(
                novel,
                chapter,
                "progression",
                existing_progression.id,
                extracted_progression,
                source_extractor,
                summary,
            )

            if evidence_changed or source_changed or value_changed:
                best_support = progression_record_best_evidence_support(
                    existing_progression
                )
                validation = revalidate_progression_record(
                    novel,
                    existing_progression,
                    best_support.evidence_text
                    if best_support
                    else extracted_progression.evidence,
                    merged_sources,
                    chapter=best_support.chapter if best_support else chapter,
                    start_offset=best_support.start_offset
                    if best_support
                    else getattr(extracted_progression, "evidence_start_offset", None),
                    end_offset=best_support.end_offset
                    if best_support
                    else getattr(extracted_progression, "evidence_end_offset", None),
                    match_type=best_support.match_type
                    if best_support
                    else getattr(extracted_progression, "evidence_match_type", None),
                )
                if validation and validation.auto_approved:
                    revalidate_character_identity_from_record_support(
                        novel,
                        existing_progression,
                        character,
                        "progression",
                    )

            recalculate_character_current_progression(character, progression_type)
            continue

        promotable_progression = find_promotable_pending_progression(
            character,
            progression_type,
            new_value,
            chapter,
        )

        if promotable_progression:
            pending_support = progression_record_best_evidence_support(promotable_progression)
            pending_evidence = pending_support.evidence_text if pending_support else None
            pending_quality = (
                progression_candidate_quality(
                    pending_support.chapter,
                    progression_proxy(promotable_progression, pending_evidence, pending_support),
                    character=character,
                    new_value=promotable_progression.new_value,
                )
                if pending_evidence and pending_support and pending_support.chapter
                else -1
            )
            incoming_quality = progression_candidate_quality(
                chapter,
                extracted_progression,
                character=character,
                new_value=new_value,
            )

            if pending_evidence and pending_quality >= incoming_quality:
                merged_sources = progression_record_source_extractors(promotable_progression)
                merged_sources.update(source_extractors)

                if add_evidence(
                    novel,
                    chapter,
                    "progression",
                    promotable_progression.id,
                    extracted_progression.evidence,
                    **evidence_support_kwargs(extracted_progression),
                ):
                    summary["evidence_created"] += 1
                add_ai_evidence_audit(
                    novel,
                    chapter,
                    "progression",
                    promotable_progression.id,
                    extracted_progression,
                    source_extractor,
                    summary,
                )

                validation = revalidate_progression_record(
                    novel,
                    promotable_progression,
                    pending_evidence,
                    merged_sources,
                    chapter=pending_support.chapter,
                    start_offset=pending_support.start_offset,
                    end_offset=pending_support.end_offset,
                    match_type=pending_support.match_type,
                )
                if validation and validation.auto_approved:
                    revalidate_character_identity_from_record_support(
                        novel,
                        promotable_progression,
                        character,
                        "progression",
                    )
                recalculate_character_current_progression(character, progression_type)
                saved_progression_by_key[progression_key] = promotable_progression
                continue

        attribution_status = progression_attribution_status(
            novel,
            chapter,
            character,
            new_value,
            extracted_progression.evidence,
            source_extractors,
            extracted_progression,
            start_offset=getattr(extracted_progression, "evidence_start_offset", None),
            end_offset=getattr(extracted_progression, "evidence_end_offset", None),
            match_type=getattr(extracted_progression, "evidence_match_type", None),
        )
        review_warnings = progression_review_warnings(
            novel,
            chapter,
            character,
            progression_type,
            new_value,
            extracted_progression.evidence,
        )

        if attribution_status == "context_supported_attribution":
            review_warnings = [
                warning
                for warning in review_warnings
                if warning != "Evidence may not directly name this character."
            ]

        progression_downgrade = has_progression_downgrade(character, progression_type, new_value)
        progression = CharacterProgressionEvent(
            novel_id=novel.id,
            character_id=character.id,
            chapter_id=chapter.id,
            progression_type=progression_type,
            old_value=old_value,
            new_value=new_value,
            description=extracted_progression.description,
            review_warnings="\n".join(review_warnings) if review_warnings else None,
            review_status="pending",
        )
        db.session.add(progression)
        db.session.flush()

        source_extractor_label = ",".join(sorted(source_extractors))

        validation = validate_extracted_fact(
            ValidationContext(
                novel=novel,
                chapter=chapter,
                fact_type="progression",
                entity_name=character.name,
                value=new_value,
                evidence=extracted_progression.evidence,
                character=character,
                entity_origin=(
                    ENTITY_ORIGIN_NEW
                    if character_created_from_progression
                    else ENTITY_ORIGIN_EXISTING
                ),
                source_extractors=source_extractors,
                conflict=progression_downgrade,
                progression_downgrade=progression_downgrade,
                attribution_uncertain=attribution_status == "attribution_uncertain",
                context_supported_attribution=(
                    attribution_status == "context_supported_attribution"
                ),
                **validation_evidence_kwargs(extracted_progression),
            )
        )
        set_validation_metadata(
            progression,
            validation,
            source_extractor_label,
        )
        add_ai_evidence_audit(
            novel,
            chapter,
            "progression",
            progression.id,
            extracted_progression,
            source_extractor,
            summary,
        )

        if progression_downgrade:
            progression.review_warnings = "\n".join(
                warning
                for warning in [
                    progression.review_warnings,
                    "Potential progression downgrade.",
                ]
                if warning
            )

        recalculate_character_current_progression(character, progression_type)
        saved_progression_by_key[progression_key] = progression

        if add_evidence(
            novel,
            chapter,
            "progression",
            progression.id,
            extracted_progression.evidence,
            **evidence_support_kwargs(extracted_progression),
        ):
            summary["evidence_created"] += 1

        best_support = progression_record_best_evidence_support(progression)

        if best_support:
            validation = revalidate_progression_record(
                novel,
                progression,
                best_support.evidence_text,
                source_extractors,
                entity_origin=(
                    ENTITY_ORIGIN_NEW
                    if character_created_from_progression
                    else ENTITY_ORIGIN_EXISTING
                ),
                chapter=best_support.chapter,
                start_offset=best_support.start_offset,
                end_offset=best_support.end_offset,
                match_type=best_support.match_type,
                conflict=progression_downgrade,
                progression_downgrade=progression_downgrade,
            )

        if validation.auto_approved:
            revalidate_character_identity_from_record_support(
                novel,
                progression,
                character,
                "progression",
            )

        summary["progression_events_created"] += 1

    for extracted_life_event in extraction.life_events:
        if not has_meaningful_evidence(extracted_life_event.evidence) and not death_text_has_strong_signal(
            extracted_life_event.evidence
        ):
            continue

        life_event_type = normalize_life_event_type(extracted_life_event.event_type)

        if not life_event_type:
            continue

        character = find_existing_character(novel, extracted_life_event.character_name)

        if not character:
            character, _ = resolve_or_create_character_from_support(
                novel,
                chapter,
                extracted_life_event.character_name,
                extracted_life_event.evidence,
                "life_event",
                summary,
            )

            if not character:
                continue

        existing_life_event = find_existing_life_event(character, chapter, life_event_type)

        if existing_life_event:
            old_sources = source_extractor_set(existing_life_event.source_extractor)
            merged_sources = merge_source_extractors(existing_life_event, "life_event")
            source_changed = merged_sources != old_sources
            evidence_changed = add_evidence(
                novel,
                chapter,
                "life_event",
                existing_life_event.id,
                extracted_life_event.evidence,
                **evidence_support_kwargs(extracted_life_event),
            )

            if evidence_changed:
                summary["evidence_created"] += 1
            add_ai_evidence_audit(
                novel,
                chapter,
                "life_event",
                existing_life_event.id,
                extracted_life_event,
                "life_event",
                summary,
            )

            evidence_verified = verify_evidence_text(
                chapter.content if chapter else "",
                extracted_life_event.evidence,
                start_offset=getattr(extracted_life_event, "evidence_start_offset", None),
                end_offset=getattr(extracted_life_event, "evidence_end_offset", None),
                match_type=getattr(extracted_life_event, "evidence_match_type", None),
            ).verified

            validation = None

            if evidence_changed or source_changed or evidence_verified:
                validation = revalidate_fact(
                    novel,
                    existing_life_event,
                    extracted_life_event.evidence,
                    "evidence_merged",
                    source_extractors=merged_sources,
                    chapter=chapter,
                    **evidence_support_kwargs(extracted_life_event),
                )

            if validation and validation.auto_approved:
                revalidate_character_identity_from_record_support(
                    novel,
                    existing_life_event,
                    character,
                    "life_event",
                )

            if (
                life_event_type == "death"
                and existing_life_event.review_status == "approved"
            ):
                revalidated_metadata = revalidate_pending_dead_status_metadata(
                    character,
                    chapter,
                )
                summary["metadata_proposals_updated"] = (
                    summary.get("metadata_proposals_updated", 0) + revalidated_metadata
                )
            continue

        validation_context = ValidationContext(
            novel=novel,
            chapter=chapter,
            fact_type="life_event",
            entity_name=character.name,
            value=life_event_type,
            evidence=extracted_life_event.evidence,
            character=character,
            entity_origin=ENTITY_ORIGIN_EXISTING,
            source_extractors={"life_event"},
            description=extracted_life_event.description,
            reason=extracted_life_event.reason,
            **validation_evidence_kwargs(extracted_life_event),
        )
        life_event_description, life_event_reason, _ = canonical_life_event_details(
            validation_context,
            extracted_life_event.description,
            extracted_life_event.reason,
        )

        life_event = CharacterLifeEvent(
            novel_id=novel.id,
            character_id=character.id,
            chapter_id=chapter.id,
            event_type=life_event_type,
            description=life_event_description,
            reason=life_event_reason,
            review_status="pending",
        )
        db.session.add(life_event)
        db.session.flush()

        validation = validate_extracted_fact(validation_context)
        set_validation_metadata(life_event, validation, "life_event")
        add_ai_evidence_audit(
            novel,
            chapter,
            "life_event",
            life_event.id,
            extracted_life_event,
            "life_event",
            summary,
        )

        if add_evidence(
            novel,
            chapter,
            "life_event",
            life_event.id,
            extracted_life_event.evidence,
            **evidence_support_kwargs(extracted_life_event),
        ):
            summary["evidence_created"] += 1

        revalidated_life_event = revalidate_fact(
            novel,
            life_event,
            extracted_life_event.evidence,
            "initial_evidence_attached",
            source_extractors={"life_event"},
            chapter=chapter,
            **evidence_support_kwargs(extracted_life_event),
        )

        if revalidated_life_event:
            validation = revalidated_life_event

        if validation.auto_approved:
            revalidate_character_identity_from_record_support(
                novel,
                life_event,
                character,
                "life_event",
            )

        if life_event_type == "death" and life_event.review_status == "approved":
            revalidated_metadata = revalidate_pending_dead_status_metadata(
                character,
                chapter,
            )
            summary["metadata_proposals_updated"] = (
                summary.get("metadata_proposals_updated", 0) + revalidated_metadata
            )

        summary["life_events_created"] += 1

    novel.status = "processed"
    novel.error_message = None
    db.session.commit()

    return summary


def is_important_item_event(novel, title, description):
    event_text = f"{title} {description}".lower()
    blocked_terms = {
        "discovers",
        "discovered",
        "discovery",
        "tests",
        "tested",
        "uses",
        "used",
        "power",
        "property",
        "ability",
        "learns",
        "realizes",
    }

    if any(term in event_text for term in blocked_terms):
        return False

    important_item_names = [
        item.name.lower()
        for item in Item.query.filter_by(novel_id=novel.id).all()
    ]

    return any(item_name in event_text for item_name in important_item_names)
