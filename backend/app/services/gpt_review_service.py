import json
import os
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.models import (
    Character,
    CharacterItem,
    CharacterLifeEvent,
    CharacterMetadataProposal,
    CharacterProgressionEvent,
    CharacterSkill,
    Chapter,
    Item,
    Novel,
    Skill,
    WikiEvidence,
    db,
    utc_now,
)
from app.services.extraction.ai_client import (
    get_ai_request_timeout,
    parse_ai_json_response,
)
from app.services.extraction.evidence import get_evidence_context
from app.services.extraction.progression import recalculate_character_current_progression


GPT_REVIEW_PROMPT = """
You are a strict second-stage reviewer in a deterministic backend validation pipeline.
You review candidate fiction-wiki facts that were already produced by another extractor.

Treat the provided input as the complete universe of information.
Use only the supplied candidate fact, evidence, local context, aliases, approved canonical facts,
confidence, and risk flags. Do not use outside knowledge, novel knowledge, genre conventions,
or previous conversation context.

Rules:
- Evaluate only the supplied candidate fact.
- Never create, modify, merge, repair, substitute, or extract facts.
- If the candidate value is wrong but the evidence supports a different value, reject it. Do not correct it.
- Local context may only resolve attribution and nearby references; it must not invent missing facts.
- The backend remains final authority. You only recommend.

Allowed decisions only:
- approve
- reject
- keep_pending

Approve only when the candidate fact is directly supported, attribution is clear, type is correct,
and the fact is not speculative, future, uncertain, contradicted, or wrong.

Reject when the candidate is unsupported, contradicted, wrong type, speculative/future/uncertain,
wrongly attributed, or would need correction.

Keep pending when plausible but unclear, especially when alias resolution, pronouns, attribution,
evidence, or context are ambiguous.

Confidence guidance:
- 0.95-1.00: explicit direct support
- 0.85-0.94: strongly supported, possibly via alias/local context
- 0.60-0.84: plausible but uncertain, usually keep_pending
- below 0.60: usually reject

Return ONLY valid JSON matching the schema. No markdown. No explanation outside JSON.
"""


ALLOWED_FACT_TYPES = {
    "character",
    "skill",
    "item",
    "character_skill",
    "character_item",
    "progression",
    "metadata",
    "life_event",
    "all",
}
ALLOWED_DECISIONS = {"approve", "reject", "keep_pending"}
DEFAULT_MAX_CANDIDATES = 25
DEFAULT_MAX_CONTEXT_CHARS = 1200


class GPTReviewDecision(BaseModel):
    candidate_id: str
    decision: str = Field(description="approve, reject, or keep_pending")
    confidence: float = Field(ge=0, le=1)
    reason: str
    normalized_value: str | None = None
    risk_flags_to_remove: list[str] = Field(default_factory=list)
    risk_flags_to_add: list[str] = Field(default_factory=list)


class GPTReviewResponse(BaseModel):
    decisions: list[GPTReviewDecision]


@dataclass
class GPTReviewConfig:
    enabled: bool
    api_key: str | None
    model: str
    base_url: str | None
    max_candidates: int
    dry_run_default: bool
    request_timeout: float
    temperature: float


def truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def get_gpt_review_config():
    max_candidates = os.getenv("GPT_REVIEW_MAX_CANDIDATES", str(DEFAULT_MAX_CANDIDATES))

    try:
        max_candidates = max(1, int(max_candidates))
    except ValueError as exc:
        raise RuntimeError("GPT_REVIEW_MAX_CANDIDATES must be a positive integer.") from exc

    return GPTReviewConfig(
        enabled=truthy(os.getenv("GPT_REVIEW_ENABLED", "false")),
        api_key=os.getenv("GPT_REVIEW_API_KEY") or os.getenv("OPENAI_API_KEY"),
        model=os.getenv("GPT_REVIEW_MODEL", "gpt-5.5"),
        base_url=os.getenv("GPT_REVIEW_BASE_URL") or None,
        max_candidates=max_candidates,
        dry_run_default=truthy(os.getenv("GPT_REVIEW_DRY_RUN", "true")),
        request_timeout=float(os.getenv("GPT_REVIEW_REQUEST_TIMEOUT") or get_ai_request_timeout()),
        temperature=float(os.getenv("GPT_REVIEW_TEMPERATURE", "0")),
    )


def normalize_review_fact_type(value):
    fact_type = (value or "all").strip().lower()

    if fact_type not in ALLOWED_FACT_TYPES:
        allowed_types = ", ".join(sorted(ALLOWED_FACT_TYPES))
        raise ValueError(f"type must be one of: {allowed_types}")

    return fact_type


def append_admin_note(record, note):
    note = " ".join(str(note or "").split())

    if not note:
        return

    stamped_note = f"[{utc_now().isoformat()}] {note}"
    record.admin_notes = f"{record.admin_notes}\n\n{stamped_note}" if record.admin_notes else stamped_note


def mark_gpt_review_change(record, action):
    record.review_version = (record.review_version or 0) + 1
    record.last_review_action = f"gpt_{action}"
    record.last_reviewed_at = utc_now()
    record.last_reviewed_by_user_id = None


def risk_flags_for_record(record):
    if not hasattr(record, "risk_flags"):
        return []

    try:
        return json.loads(record.risk_flags or "[]")
    except json.JSONDecodeError:
        return []


def set_risk_flags_for_record(record, flags):
    if not hasattr(record, "risk_flags"):
        return

    unique_flags = []
    seen = set()

    for flag in flags:
        flag = str(flag or "").strip()

        if flag and flag not in seen:
            unique_flags.append(flag)
            seen.add(flag)

    record.risk_flags = json.dumps(unique_flags)


def evidence_for_record(entity_type, record):
    if entity_type == "metadata":
        return record.evidence or ""

    filters = {
        "novel_id": record.novel_id,
        "entity_type": entity_type,
        "entity_id": record.id,
    }

    chapter_id = getattr(record, "chapter_id", None)

    if chapter_id:
        filters["chapter_id"] = chapter_id

    evidence = WikiEvidence.query.filter_by(**filters).order_by(WikiEvidence.id).first()
    return evidence.evidence_text if evidence else ""


def local_context_for_candidate(record, evidence_text, max_chars=DEFAULT_MAX_CONTEXT_CHARS):
    chapter_id = candidate_chapter_id(record)

    if not chapter_id:
        return ""

    chapter = db.session.get(Chapter, chapter_id)

    if not chapter or not evidence_text:
        return ""

    context = get_evidence_context(chapter.content, evidence_text)
    return context.combined_context[:max_chars] if context.found else ""


def approved_character_facts(character):
    progression = [
        {
            "type": row.progression_type,
            "value": row.new_value,
            "chapter_id": row.chapter_id,
        }
        for row in CharacterProgressionEvent.query.filter_by(
            character_id=character.id,
            review_status="approved",
        ).order_by(CharacterProgressionEvent.chapter_id, CharacterProgressionEvent.id)
    ]
    life_events = [
        {
            "type": row.event_type,
            "chapter_id": row.chapter_id,
        }
        for row in CharacterLifeEvent.query.filter_by(
            character_id=character.id,
            review_status="approved",
        ).order_by(CharacterLifeEvent.chapter_id, CharacterLifeEvent.id)
    ]
    metadata = {
        field: getattr(character, field)
        for field in (
            "age_text",
            "gender",
            "race_or_species",
            "origin",
            "faction_or_affiliation",
            "status",
            "titles",
        )
        if getattr(character, field, None)
    }

    return {
        "progression": progression,
        "metadata": metadata,
        "life_events": life_events,
    }


def character_context(character):
    if not character:
        return None

    return {
        "id": character.id,
        "canonical_name": character.name,
        "aliases": [alias.alias for alias in character.aliases],
        "approved_facts": approved_character_facts(character),
    }


def chapter_number_for(record):
    chapter_id = candidate_chapter_id(record)

    if not chapter_id:
        return None

    chapter = db.session.get(Chapter, chapter_id)
    return chapter.chapter_number if chapter else None


def candidate_chapter_id(record):
    direct_chapter_id = (
        getattr(record, "chapter_id", None)
        or getattr(record, "first_seen_chapter_id", None)
        or getattr(record, "first_appeared_chapter_id", None)
        or getattr(record, "first_mentioned_chapter_id", None)
    )

    if direct_chapter_id:
        return direct_chapter_id

    entity_type_by_model = {
        Character: "character",
        Skill: "skill",
        Item: "item",
    }
    entity_type = entity_type_by_model.get(type(record))

    if not entity_type:
        return None

    evidence = (
        WikiEvidence.query.filter_by(
            novel_id=record.novel_id,
            entity_type=entity_type,
            entity_id=record.id,
        )
        .order_by(WikiEvidence.id)
        .first()
    )

    return evidence.chapter_id if evidence else None


def character_candidate(record, max_context_chars):
    evidence = evidence_for_record("character", record)

    return {
        "candidate_id": f"character:{record.id}",
        "db_id": record.id,
        "type": "character",
        "chapter_id": candidate_chapter_id(record),
        "chapter_number": chapter_number_for(record),
        "character_id": record.id,
        "character_name": record.name,
        "field": "identity",
        "value": record.name,
        "description": record.description,
        "aliases": [alias.alias for alias in record.aliases],
        "evidence": evidence,
        "local_context": local_context_for_candidate(record, evidence, max_context_chars),
        "confidence": record.confidence_score,
        "risk_flags": risk_flags_for_record(record),
        "source": record.source_extractor,
    }


def skill_candidate(record, max_context_chars):
    evidence = evidence_for_record("skill", record)

    return {
        "candidate_id": f"skill:{record.id}",
        "db_id": record.id,
        "type": "skill",
        "chapter_id": candidate_chapter_id(record),
        "chapter_number": chapter_number_for(record),
        "field": "skill",
        "value": record.name,
        "category": record.category,
        "description": record.description,
        "aliases": [alias.alias for alias in record.aliases],
        "evidence": evidence,
        "local_context": local_context_for_candidate(record, evidence, max_context_chars),
        "confidence": record.confidence_score,
        "risk_flags": risk_flags_for_record(record),
        "source": record.source_extractor,
    }


def item_candidate(record, max_context_chars):
    evidence = evidence_for_record("item", record)

    return {
        "candidate_id": f"item:{record.id}",
        "db_id": record.id,
        "type": "item",
        "chapter_id": candidate_chapter_id(record),
        "chapter_number": chapter_number_for(record),
        "field": "item",
        "value": record.name,
        "category": record.category,
        "description": record.description,
        "evidence": evidence,
        "local_context": local_context_for_candidate(record, evidence, max_context_chars),
        "confidence": record.confidence_score,
        "risk_flags": risk_flags_for_record(record),
        "source": record.source_extractor,
    }


def progression_candidate(record, max_context_chars):
    evidence = evidence_for_record("progression", record)

    return {
        "candidate_id": f"progression:{record.id}",
        "db_id": record.id,
        "type": "progression",
        "chapter_id": record.chapter_id,
        "chapter_number": chapter_number_for(record),
        "character_id": record.character_id,
        "character_name": record.character.name if record.character else None,
        "field": record.progression_type,
        "value": record.new_value,
        "old_value": record.old_value,
        "description": record.description,
        "evidence": evidence,
        "local_context": local_context_for_candidate(record, evidence, max_context_chars),
        "confidence": record.confidence_score,
        "risk_flags": risk_flags_for_record(record),
        "source": record.source_extractor,
    }


def metadata_candidate(record, max_context_chars):
    evidence = evidence_for_record("metadata", record)

    return {
        "candidate_id": f"metadata:{record.id}",
        "db_id": record.id,
        "type": "metadata",
        "chapter_id": record.chapter_id,
        "chapter_number": chapter_number_for(record),
        "character_id": record.character_id,
        "character_name": record.character.name if record.character else None,
        "field": record.field_name,
        "value": record.proposed_value,
        "old_value": record.old_value,
        "raw_value": record.raw_proposed_value,
        "normalized_value": record.normalized_value,
        "evidence": evidence,
        "local_context": local_context_for_candidate(record, evidence, max_context_chars),
        "confidence": record.confidence_score,
        "risk_flags": [],
        "source": "metadata",
    }


def life_event_candidate(record, max_context_chars):
    evidence = evidence_for_record("life_event", record)

    return {
        "candidate_id": f"life_event:{record.id}",
        "db_id": record.id,
        "type": "life_event",
        "chapter_id": record.chapter_id,
        "chapter_number": chapter_number_for(record),
        "character_id": record.character_id,
        "character_name": record.character.name if record.character else None,
        "field": "event_type",
        "value": record.event_type,
        "description": record.description,
        "reason": record.reason,
        "evidence": evidence,
        "local_context": local_context_for_candidate(record, evidence, max_context_chars),
        "confidence": record.confidence_score,
        "risk_flags": risk_flags_for_record(record),
        "source": record.source_extractor,
    }


def character_skill_candidate(record, max_context_chars):
    evidence = evidence_for_record("character_skill", record)

    return {
        "candidate_id": f"character_skill:{record.id}",
        "db_id": record.id,
        "type": "character_skill",
        "chapter_id": record.chapter_id,
        "chapter_number": chapter_number_for(record),
        "character_id": record.character_id,
        "character_name": record.character.name if record.character else None,
        "skill_id": record.skill_id,
        "skill_name": record.skill.name if record.skill else None,
        "field": "relationship",
        "value": record.skill.name if record.skill else None,
        "relationship_type": record.relationship_type,
        "description": record.description,
        "evidence": evidence,
        "local_context": local_context_for_candidate(record, evidence, max_context_chars),
        "confidence": record.confidence_score,
        "risk_flags": risk_flags_for_record(record),
        "source": record.source_extractor,
    }


def character_item_candidate(record, max_context_chars):
    evidence = evidence_for_record("character_item", record)

    return {
        "candidate_id": f"character_item:{record.id}",
        "db_id": record.id,
        "type": "character_item",
        "chapter_id": record.chapter_id,
        "chapter_number": chapter_number_for(record),
        "character_id": record.character_id,
        "character_name": record.character.name if record.character else None,
        "item_id": record.item_id,
        "item_name": record.item.name if record.item else None,
        "field": "relationship",
        "value": record.item.name if record.item else None,
        "relationship_type": record.relationship_type,
        "description": record.description,
        "evidence": evidence,
        "local_context": local_context_for_candidate(record, evidence, max_context_chars),
        "confidence": record.confidence_score,
        "risk_flags": risk_flags_for_record(record),
        "source": record.source_extractor,
    }


def pending_candidate_rows(novel_id, fact_type, character_id=None):
    fact_type = normalize_review_fact_type(fact_type)
    queries = []

    if fact_type in {"character", "all"}:
        query = Character.query.filter_by(
            novel_id=novel_id,
            review_status="pending",
        )
        if character_id:
            query = query.filter_by(id=character_id)
        queries.append(("character", query.order_by(Character.id)))

    if fact_type in {"skill", "all"}:
        query = Skill.query.filter_by(
            novel_id=novel_id,
            review_status="pending",
        )
        queries.append(("skill", query.order_by(Skill.id)))

    if fact_type in {"item", "all"}:
        query = Item.query.filter_by(
            novel_id=novel_id,
            review_status="pending",
        )
        queries.append(("item", query.order_by(Item.id)))

    if fact_type in {"progression", "all"}:
        query = CharacterProgressionEvent.query.filter_by(
            novel_id=novel_id,
            review_status="pending",
        )
        if character_id:
            query = query.filter_by(character_id=character_id)
        queries.append(("progression", query.order_by(CharacterProgressionEvent.chapter_id, CharacterProgressionEvent.id)))

    if fact_type in {"metadata", "all"}:
        query = CharacterMetadataProposal.query.filter_by(
            novel_id=novel_id,
            review_status="pending",
        )
        if character_id:
            query = query.filter_by(character_id=character_id)
        queries.append(("metadata", query.order_by(CharacterMetadataProposal.chapter_id, CharacterMetadataProposal.id)))

    if fact_type in {"life_event", "all"}:
        query = CharacterLifeEvent.query.filter_by(
            novel_id=novel_id,
            review_status="pending",
        )
        if character_id:
            query = query.filter_by(character_id=character_id)
        queries.append(("life_event", query.order_by(CharacterLifeEvent.chapter_id, CharacterLifeEvent.id)))

    if fact_type in {"character_skill", "all"}:
        query = CharacterSkill.query.filter_by(
            novel_id=novel_id,
            review_status="pending",
        )
        if character_id:
            query = query.filter_by(character_id=character_id)
        queries.append(("character_skill", query.order_by(CharacterSkill.chapter_id, CharacterSkill.id)))

    if fact_type in {"character_item", "all"}:
        query = CharacterItem.query.filter_by(
            novel_id=novel_id,
            review_status="pending",
        )
        if character_id:
            query = query.filter_by(character_id=character_id)
        queries.append(("character_item", query.order_by(CharacterItem.chapter_id, CharacterItem.id)))

    rows = []

    for row_type, query in queries:
        rows.extend((row_type, row) for row in query.all())

    return sorted(
        rows,
        key=lambda pair: (
            candidate_chapter_id(pair[1]) or 0,
            pair[0],
            pair[1].id,
        ),
    )


def build_gpt_review_batch(
    novel,
    limit=DEFAULT_MAX_CANDIDATES,
    fact_type="all",
    character_id=None,
    max_context_chars=DEFAULT_MAX_CONTEXT_CHARS,
):
    limit = max(1, int(limit or DEFAULT_MAX_CANDIDATES))
    selected_rows = pending_candidate_rows(novel.id, fact_type, character_id=character_id)[:limit]
    candidates = []
    characters_by_id = {}

    for row_type, record in selected_rows:
        character = getattr(record, "character", None)

        if character:
            characters_by_id[character.id] = character

        if row_type == "progression":
            candidates.append(progression_candidate(record, max_context_chars))
        elif row_type == "metadata":
            candidates.append(metadata_candidate(record, max_context_chars))
        elif row_type == "life_event":
            candidates.append(life_event_candidate(record, max_context_chars))
        elif row_type == "character":
            candidates.append(character_candidate(record, max_context_chars))
        elif row_type == "skill":
            candidates.append(skill_candidate(record, max_context_chars))
        elif row_type == "item":
            candidates.append(item_candidate(record, max_context_chars))
        elif row_type == "character_skill":
            candidates.append(character_skill_candidate(record, max_context_chars))
        elif row_type == "character_item":
            candidates.append(character_item_candidate(record, max_context_chars))

    return {
        "novel": {
            "id": novel.id,
            "title": novel.title,
        },
        "review_context": {
            "characters": [
                character_context(character)
                for character in sorted(characters_by_id.values(), key=lambda item: item.name)
            ],
            "known_entities": {
                "items": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "category": item.category,
                    }
                    for item in Item.query.filter_by(
                        novel_id=novel.id,
                        review_status="approved",
                    ).order_by(Item.name)
                ],
                "skills": [
                    {
                        "id": skill.id,
                        "name": skill.name,
                        "category": skill.category,
                        "aliases": [alias.alias for alias in skill.aliases],
                    }
                    for skill in Skill.query.filter_by(
                        novel_id=novel.id,
                        review_status="approved",
                    ).order_by(Skill.name)
                ],
                "progression_values": sorted(
                    {
                        row.new_value
                        for row in CharacterProgressionEvent.query.filter_by(
                            novel_id=novel.id,
                            review_status="approved",
                        ).all()
                    }
                ),
            },
        },
        "candidates": candidates,
    }


def estimate_payload_chars(batch):
    return len(json.dumps(batch, ensure_ascii=False))


def review_pending_with_gpt(batch, config=None):
    config = config or get_gpt_review_config()

    if not config.enabled:
        raise RuntimeError("GPT review is disabled. Set GPT_REVIEW_ENABLED=true to use it.")

    if not config.api_key:
        raise RuntimeError("GPT_REVIEW_API_KEY or OPENAI_API_KEY is required for GPT review.")

    from openai import OpenAI

    client_kwargs = {
        "api_key": config.api_key,
        "timeout": config.request_timeout,
    }

    if config.base_url:
        client_kwargs["base_url"] = config.base_url

    client = OpenAI(**client_kwargs)

    return parse_ai_json_response(
        client=client,
        provider="openai",
        model=config.model,
        temperature=config.temperature,
        system_prompt=GPT_REVIEW_PROMPT,
        user_content=json.dumps(batch, ensure_ascii=False),
        schema_model=GPTReviewResponse,
    )


def record_for_candidate(candidate_id):
    try:
        candidate_type, raw_id = candidate_id.split(":", 1)
        record_id = int(raw_id)
    except (ValueError, TypeError):
        return None, None

    model_by_type = {
        "character": Character,
        "skill": Skill,
        "item": Item,
        "progression": CharacterProgressionEvent,
        "metadata": CharacterMetadataProposal,
        "life_event": CharacterLifeEvent,
        "character_skill": CharacterSkill,
        "character_item": CharacterItem,
    }
    model = model_by_type.get(candidate_type)

    if not model:
        return None, None

    return candidate_type, db.session.get(model, record_id)


def merge_text(target_text, source_text):
    if not source_text:
        return target_text

    if not target_text:
        return source_text

    if source_text in target_text:
        return target_text

    return f"{target_text}\n\n{source_text}"


def apply_metadata_proposal_for_gpt(proposal):
    character = proposal.character

    if not character:
        return False

    if proposal.field_name == "titles":
        character.titles = merge_text(character.titles, proposal.proposed_value)
    else:
        setattr(character, proposal.field_name, proposal.proposed_value)

    if proposal.field_name == "race_or_species":
        character.race_or_species_source = "extracted"
        character.race_or_species_confidence = "confirmed"

    return True


def apply_gpt_review_decisions(decisions, dry_run=True, model_name=None):
    results = []

    for decision in decisions:
        candidate_type, record = record_for_candidate(decision.candidate_id)

        if not record:
            results.append(
                {
                    "candidate_id": decision.candidate_id,
                    "applied": False,
                    "reason": "candidate_not_found",
                }
            )
            continue

        if record.review_status != "pending":
            results.append(
                {
                    "candidate_id": decision.candidate_id,
                    "applied": False,
                    "reason": "candidate_not_pending",
                }
            )
            continue

        if decision.decision not in ALLOWED_DECISIONS:
            results.append(
                {
                    "candidate_id": decision.candidate_id,
                    "applied": False,
                    "reason": "invalid_decision",
                }
            )
            continue

        if dry_run:
            results.append(
                {
                    "candidate_id": decision.candidate_id,
                    "decision": decision.decision,
                    "applied": False,
                    "reason": "dry_run",
                }
            )
            continue

        note = (
            f"GPT reviewer ({model_name or 'unknown model'}) decision={decision.decision} "
            f"confidence={decision.confidence:.2f}: {decision.reason}"
        )
        append_admin_note(record, note)

        if hasattr(record, "confidence_score"):
            record.confidence_score = max(record.confidence_score or 0, decision.confidence * 100)

        if decision.decision == "approve":
            if candidate_type == "metadata" and not apply_metadata_proposal_for_gpt(record):
                results.append(
                    {
                        "candidate_id": decision.candidate_id,
                        "applied": False,
                        "reason": "metadata_apply_failed",
                    }
                )
                continue

            flags = risk_flags_for_record(record)
            flags = [
                flag
                for flag in flags
                if flag not in set(decision.risk_flags_to_remove or [])
            ]
            flags.extend(decision.risk_flags_to_add or [])
            set_risk_flags_for_record(record, flags)
            record.review_status = "approved"
            record.auto_approved = True
            mark_gpt_review_change(record, "approve")

            if candidate_type == "progression":
                recalculate_character_current_progression(record.character, record.progression_type)

        elif decision.decision == "reject":
            flags = risk_flags_for_record(record)
            flags.extend(decision.risk_flags_to_add or [])
            set_risk_flags_for_record(record, flags)
            record.review_status = "rejected"
            mark_gpt_review_change(record, "reject")

        else:
            mark_gpt_review_change(record, "keep_pending")

        results.append(
            {
                "candidate_id": decision.candidate_id,
                "decision": decision.decision,
                "applied": True,
                "record_status": record.review_status,
            }
        )

    db.session.commit()
    return results


def run_gpt_review(
    novel_id,
    limit=None,
    fact_type="all",
    character_id=None,
    dry_run=None,
    reviewer=None,
):
    novel = db.session.get(Novel, novel_id)

    if not novel:
        raise RuntimeError(f"Novel {novel_id} was not found.")

    config = get_gpt_review_config()
    limit = min(int(limit or config.max_candidates), config.max_candidates)
    dry_run = config.dry_run_default if dry_run is None else bool(dry_run)
    batch = build_gpt_review_batch(
        novel,
        limit=limit,
        fact_type=fact_type,
        character_id=character_id,
    )

    if not batch["candidates"]:
        return {
            "batch": batch,
            "decisions": [],
            "results": [],
            "dry_run": dry_run,
            "model": config.model,
            "payload_chars": estimate_payload_chars(batch),
        }

    response = reviewer(batch, config) if reviewer else review_pending_with_gpt(batch, config)
    results = apply_gpt_review_decisions(
        response.decisions,
        dry_run=dry_run,
        model_name=config.model,
    )

    return {
        "batch": batch,
        "decisions": [decision.model_dump() for decision in response.decisions],
        "results": results,
        "dry_run": dry_run,
        "model": config.model,
        "payload_chars": estimate_payload_chars(batch),
    }
