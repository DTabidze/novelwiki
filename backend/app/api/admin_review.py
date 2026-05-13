from flask import Blueprint, jsonify, request

from app.models import (
    Character,
    CharacterAlias,
    CharacterLifeEvent,
    CharacterProgressionEvent,
    Chapter,
    Item,
    Skill,
    WikiEvent,
    WikiEvidence,
    db,
)


admin_review_bp = Blueprint("admin_review", __name__)

REVIEW_STATUSES = {"pending", "approved", "rejected"}

ENTITY_CONFIG = {
    "characters": {
        "model": Character,
        "fields": {"name", "description", "review_status", "admin_notes"},
    },
    "skills": {
        "model": Skill,
        "fields": {"name", "category", "description", "review_status", "admin_notes"},
    },
    "items": {
        "model": Item,
        "fields": {"name", "category", "description", "review_status", "admin_notes"},
    },
    "events": {
        "model": WikiEvent,
        "fields": {"event_type", "title", "description", "review_status", "admin_notes"},
    },
    "progression_events": {
        "model": CharacterProgressionEvent,
        "fields": {
            "progression_type",
            "old_value",
            "new_value",
            "description",
            "review_status",
            "admin_notes",
        },
    },
    "life_events": {
        "model": CharacterLifeEvent,
        "fields": {"event_type", "description", "reason", "review_status", "admin_notes"},
    },
}

EVIDENCE_ENTITY_TYPES = {
    "characters": "character",
    "skills": "skill",
    "items": "item",
    "events": "event",
    "progression_events": "progression",
    "life_events": "life_event",
}


def success(data, status=200):
    return jsonify({"data": data, "error": None}), status


def failure(message, status=400):
    return jsonify({"data": None, "error": message}), status


def merge_text(target_text, source_text):
    if not source_text:
        return target_text

    if not target_text:
        return source_text

    if source_text in target_text:
        return target_text

    return f"{target_text}\n\n{source_text}"


def earliest_chapter_id(*chapter_ids):
    valid_ids = [chapter_id for chapter_id in chapter_ids if chapter_id is not None]
    return min(valid_ids) if valid_ids else None


def chapter_reference(chapter_id):
    if not chapter_id:
        return None

    chapter = Chapter.query.get(chapter_id)

    if not chapter:
        return None

    return chapter.to_reference_dict()


def admin_review_response(entity_type, record):
    data = record.to_admin_dict()
    evidence_entity_type = EVIDENCE_ENTITY_TYPES.get(entity_type)

    if evidence_entity_type:
        evidence_rows = (
            WikiEvidence.query.filter_by(
                entity_type=evidence_entity_type,
                entity_id=record.id,
            )
            .order_by(WikiEvidence.id)
            .all()
        )
    else:
        evidence_rows = []

    source_chapter_id = data.get("source_chapter_id")

    if not source_chapter_id and evidence_rows:
        source_chapter_id = evidence_rows[0].chapter_id

    data["source_chapter"] = chapter_reference(source_chapter_id)
    data["first_mentioned_chapter"] = chapter_reference(data.get("first_mentioned_chapter_id"))
    data["first_appeared_chapter"] = chapter_reference(data.get("first_appeared_chapter_id"))
    data["evidence"] = [evidence.to_admin_dict() for evidence in evidence_rows]

    if entity_type == "characters":
        aliases = []

        for alias in record.aliases:
            alias_data = alias.to_admin_dict()
            alias_data["first_seen_chapter"] = chapter_reference(alias.first_seen_chapter_id)
            aliases.append(alias_data)

        data["aliases"] = aliases

    if entity_type == "skills":
        aliases = []

        for alias in record.aliases:
            alias_data = alias.to_admin_dict()
            alias_data["first_seen_chapter"] = chapter_reference(alias.first_seen_chapter_id)
            aliases.append(alias_data)

        data["aliases"] = aliases

    return data


@admin_review_bp.patch("/<entity_type>/<int:entity_id>")
def update_extracted_entity(entity_type, entity_id):
    config = ENTITY_CONFIG.get(entity_type)

    if not config:
        return failure("Unknown review entity type.", status=404)

    payload = request.get_json(silent=True) or {}
    record = config["model"].query.get_or_404(entity_id)

    if "review_status" in payload and payload["review_status"] not in REVIEW_STATUSES:
        return failure("review_status must be pending, approved, or rejected.")

    for field in config["fields"]:
        if field in payload:
            setattr(record, field, payload[field])

    db.session.commit()

    return success(admin_review_response(entity_type, record))


@admin_review_bp.post("/characters/<int:source_id>/merge")
def merge_character(source_id):
    payload = request.get_json(silent=True) or {}
    target_id = payload.get("target_character_id")

    if not target_id:
        return failure("target_character_id is required.")

    if source_id == target_id:
        return failure("Cannot merge a character into itself.")

    source = Character.query.get_or_404(source_id)
    target = Character.query.get_or_404(target_id)

    if source.novel_id != target.novel_id:
        return failure("Characters must belong to the same novel.")

    target.description = merge_text(target.description, source.description)
    target.admin_notes = merge_text(target.admin_notes, source.admin_notes)
    target.first_mentioned_chapter_id = earliest_chapter_id(
        target.first_mentioned_chapter_id,
        source.first_mentioned_chapter_id,
    )
    target.first_appeared_chapter_id = earliest_chapter_id(
        target.first_appeared_chapter_id,
        source.first_appeared_chapter_id,
    )
    target.first_seen_chapter_id = earliest_chapter_id(
        target.first_seen_chapter_id,
        source.first_seen_chapter_id,
    )
    target.current_cultivation_level = (
        target.current_cultivation_level or source.current_cultivation_level
    )
    target.current_position = target.current_position or source.current_position
    target.current_class_rank = target.current_class_rank or source.current_class_rank
    target.current_power_rank = target.current_power_rank or source.current_power_rank

    source_aliases = [
        {
            "alias": alias.alias,
            "first_seen_chapter_id": alias.first_seen_chapter_id,
            "evidence": alias.evidence,
        }
        for alias in source.aliases
    ]

    for alias_data in source_aliases:
        existing_alias = CharacterAlias.query.filter(
            CharacterAlias.character_id == target.id,
            db.func.lower(CharacterAlias.alias) == alias_data["alias"].lower(),
        ).first()

        if not existing_alias:
            db.session.add(
                CharacterAlias(
                    character_id=target.id,
                    alias=alias_data["alias"],
                    first_seen_chapter_id=alias_data["first_seen_chapter_id"],
                    evidence=alias_data["evidence"],
                )
            )

    source_name_alias = CharacterAlias.query.filter(
        CharacterAlias.character_id == target.id,
        db.func.lower(CharacterAlias.alias) == source.name.lower(),
    ).first()

    if not source_name_alias and source.name.lower() != target.name.lower():
        db.session.add(
            CharacterAlias(
                character_id=target.id,
                alias=source.name,
                first_seen_chapter_id=source.first_seen_chapter_id,
                evidence="Merged duplicate character name.",
            )
        )

    WikiEvidence.query.filter_by(entity_type="character", entity_id=source.id).update(
        {"entity_id": target.id}
    )
    CharacterProgressionEvent.query.filter_by(character_id=source.id).update(
        {"character_id": target.id}
    )
    CharacterLifeEvent.query.filter_by(character_id=source.id).update(
        {"character_id": target.id}
    )

    db.session.delete(source)
    db.session.commit()

    return success(admin_review_response("characters", target))
