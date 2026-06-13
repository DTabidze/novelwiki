import json
import re
from datetime import datetime, time, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from app.models import (
    Character,
    CharacterAlias,
    CharacterItem,
    CharacterLifeEvent,
    CharacterMetadataProposal,
    CharacterProgressionEvent,
    CharacterSkill,
    Chapter,
    Item,
    Skill,
    SkillAlias,
    WikiEditLog,
    WikiEvent,
    WikiEvidence,
    db,
    serialize_datetime,
)
from app.services.wiki_editor_payloads import (
    PayloadValidationError,
    apply_character_alias_payload,
    apply_character_cultivation_payload,
    apply_character_item_payload,
    apply_character_skill_payload,
    apply_item_character_payload,
    apply_skill_alias_payload,
    apply_skill_character_payload,
    parse_boolean,
    parse_optional_int,
    request_json_object,
    validate_chapter_for_novel,
    validate_optional_text,
)
from app.services.item_categories import normalize_item_category
from app.services.skill_categories import normalize_skill_category


admin_review_bp = Blueprint("admin_review", __name__)

REVIEW_STATUSES = {"pending", "approved", "rejected"}
APPROVED_STATUS = "approved"

ENTITY_CONFIG = {
    "characters": {
        "model": Character,
        "fields": {
            "name",
            "description",
            "age_text",
            "gender",
            "race_or_species",
            "race_or_species_source",
            "race_or_species_confidence",
            "origin",
            "faction_or_affiliation",
            "status",
            "titles",
            "review_status",
            "admin_notes",
        },
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
    "character_metadata_proposals": {
        "model": CharacterMetadataProposal,
        "fields": {
            "field_name",
            "old_value",
            "proposed_value",
            "evidence",
            "review_status",
            "admin_notes",
        },
    },
    "character_skills": {
        "model": CharacterSkill,
        "fields": {"description", "review_status", "admin_notes"},
    },
    "character_items": {
        "model": CharacterItem,
        "fields": {"relationship_type", "description", "review_status", "admin_notes"},
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
    "character_metadata_proposals": "character_metadata_proposal",
    "character_skills": "character_skill",
    "character_items": "character_item",
    "life_events": "life_event",
}


def success(data, status=200):
    return jsonify({"data": data, "error": None}), status


def failure(message, status=400):
    return jsonify({"data": None, "error": message}), status


@admin_review_bp.errorhandler(PayloadValidationError)
def handle_payload_validation_error(error):
    db.session.rollback()
    return failure(str(error))


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def edit_log_json(value):
    if value in (None, ""):
        return None

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def normalize_log_value(value):
    if value in (None, ""):
        return None

    if isinstance(value, dict):
        return {key: normalize_log_value(item) for key, item in value.items()}

    if isinstance(value, list):
        return [normalize_log_value(item) for item in value]

    return value


def display_log_value(value):
    value = normalize_log_value(value)

    if value in (None, ""):
        return None

    if isinstance(value, dict):
        chapter_number = value.get("chapter_number")
        chapter_title = value.get("title")

        if chapter_number and chapter_title:
            title = re.sub(rf"^chapter\s+{chapter_number}\s*[:\-]\s*", "", str(chapter_title), flags=re.I)
            return f"Chapter {chapter_number} - {title}"

        if chapter_number:
            return f"Chapter {chapter_number}"

        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    if isinstance(value, list):
        return ", ".join(filter(None, [display_log_value(item) for item in value]))

    return str(value)


def values_equal(first, second):
    return normalize_log_value(first) == normalize_log_value(second)


def log_summary(change_type, field_label, old_value=None, new_value=None, context=None):
    old_display = display_log_value(old_value)
    new_display = display_log_value(new_value)

    if change_type == "updated" and old_display is not None and new_display is not None:
        return f'{field_label} changed from "{old_display}" to "{new_display}".'

    if change_type == "added":
        return f"Added {field_label.lower()}{f' to {context}' if context else ''}."

    if change_type == "removed":
        return f"Removed {field_label.lower()}{f' from {context}' if context else ''}."

    return field_label


def add_wiki_edit_log(
    *,
    novel_id,
    entity_type,
    entity_id,
    entity_label,
    change_type,
    field_name=None,
    old_value=None,
    new_value=None,
    parent_entity_type=None,
    parent_entity_id=None,
    summary=None,
):
    db.session.add(
        WikiEditLog(
            novel_id=novel_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_label=entity_label or "Wiki Data",
            parent_entity_type=parent_entity_type,
            parent_entity_id=parent_entity_id,
            change_type=change_type,
            field_name=field_name,
            old_value_json=edit_log_json(normalize_log_value(old_value)),
            new_value_json=edit_log_json(normalize_log_value(new_value)),
            summary=summary,
            edited_by="Admin",
        )
    )


def record_field_logs(novel_id, entity_type, entity_id, entity_label, before, after, fields):
    for field_name, field_label in fields.items():
        old_value = before.get(field_name)
        new_value = after.get(field_name)

        if values_equal(old_value, new_value):
            continue

        add_wiki_edit_log(
            novel_id=novel_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_label=entity_label,
            change_type="updated",
            field_name=field_label,
            old_value=old_value,
            new_value=new_value,
            summary=log_summary("updated", field_label, old_value, new_value),
        )


def first_evidence_text(row):
    evidence_rows = row.get("evidence") or []

    if not evidence_rows:
        return None

    return evidence_rows[0].get("evidence_text")


def row_by_id(rows):
    return {row["id"]: row for row in rows if row.get("id")}


def record_collection_logs(
    *,
    novel_id,
    parent_type,
    parent_id,
    parent_label,
    entity_type,
    before_rows,
    after_rows,
    entity_label_getter,
    field_getters,
    added_field,
    removed_field,
):
    before_by_id = row_by_id(before_rows)
    after_by_id = row_by_id(after_rows)

    for row_id, after_row in after_by_id.items():
        if row_id not in before_by_id:
            label = entity_label_getter(after_row)
            log_entity_label = parent_label or label
            add_wiki_edit_log(
                novel_id=novel_id,
                entity_type=entity_type,
                entity_id=row_id,
                entity_label=log_entity_label,
                parent_entity_type=parent_type,
                parent_entity_id=parent_id,
                change_type="added",
                field_name=added_field,
                new_value=label,
                summary=log_summary("added", added_field, new_value=label, context=parent_label),
            )
            continue

        before_row = before_by_id[row_id]
        label = entity_label_getter(after_row)
        log_entity_label = parent_label or label

        for _field_key, field_label, value_getter in field_getters:
            old_value = value_getter(before_row)
            new_value = value_getter(after_row)

            if values_equal(old_value, new_value):
                continue

            add_wiki_edit_log(
                novel_id=novel_id,
                entity_type=entity_type,
                entity_id=row_id,
                entity_label=log_entity_label,
                parent_entity_type=parent_type,
                parent_entity_id=parent_id,
                change_type="updated",
                field_name=field_label,
                old_value=old_value,
                new_value=new_value,
                summary=log_summary("updated", field_label, old_value, new_value),
            )

    for row_id, before_row in before_by_id.items():
        if row_id in after_by_id:
            continue

        label = entity_label_getter(before_row)
        log_entity_label = parent_label or label
        add_wiki_edit_log(
            novel_id=novel_id,
            entity_type=entity_type,
            entity_id=row_id,
            entity_label=log_entity_label,
            parent_entity_type=parent_type,
            parent_entity_id=parent_id,
            change_type="removed",
            field_name=removed_field,
            old_value=label,
            summary=log_summary("removed", removed_field, old_value=label, context=parent_label),
        )


CHARACTER_LOG_FIELDS = {
    "name": "Canonical Name",
    "description": "Description",
    "first_mentioned_chapter": "First Mentioned Chapter",
    "first_appeared_chapter": "First Appeared Chapter",
    "age_text": "Age",
    "gender": "Gender",
    "race_or_species": "Race / Species",
    "origin": "Origin",
    "faction_or_affiliation": "Affiliation",
    "status": "Status",
    "titles": "Titles",
    "current_position": "Current Position",
    "admin_notes": "Admin Notes",
}

SKILL_LOG_FIELDS = {
    "name": "Canonical Name",
    "category": "Category",
    "description": "Description",
    "admin_notes": "Admin Notes",
}

ITEM_LOG_FIELDS = {
    "name": "Canonical Name",
    "category": "Category",
    "description": "Description",
    "admin_notes": "Admin Notes",
}


def record_character_editor_logs(before, after):
    record_field_logs(after["novel_id"], "character", after["id"], after["name"], before, after, CHARACTER_LOG_FIELDS)
    record_collection_logs(
        novel_id=after["novel_id"],
        parent_type="character",
        parent_id=after["id"],
        parent_label=after["name"],
        entity_type="alias",
        before_rows=before.get("aliases") or [],
        after_rows=after.get("aliases") or [],
        entity_label_getter=lambda row: row.get("alias"),
        field_getters=[
            ("alias", "Alias", lambda row: row.get("alias")),
            ("chapter", "First Mentioned Chapter", lambda row: row.get("first_seen_chapter")),
            ("evidence", "Evidence", lambda row: row.get("evidence")),
            ("is_primary", "Primary Alias", lambda row: row.get("is_primary")),
        ],
        added_field="Alias",
        removed_field="Alias",
    )
    record_collection_logs(
        novel_id=after["novel_id"],
        parent_type="character",
        parent_id=after["id"],
        parent_label=after["name"],
        entity_type="cultivation",
        before_rows=before.get("progression_events") or [],
        after_rows=after.get("progression_events") or [],
        entity_label_getter=lambda row: row.get("new_value") or "Cultivation Breakthrough",
        field_getters=[
            ("new_value", "Cultivation Level", lambda row: row.get("new_value")),
            ("chapter", "Chapter", lambda row: row.get("chapter")),
            ("description", "Notes", lambda row: row.get("description")),
            ("evidence", "Evidence", first_evidence_text),
        ],
        added_field="Cultivation Breakthrough",
        removed_field="Cultivation Breakthrough",
    )
    record_collection_logs(
        novel_id=after["novel_id"],
        parent_type="character",
        parent_id=after["id"],
        parent_label=after["name"],
        entity_type="character_skill",
        before_rows=before.get("skills") or [],
        after_rows=after.get("skills") or [],
        entity_label_getter=lambda row: row.get("skill_name") or "Skill Link",
        field_getters=[
            ("skill", "Skill", lambda row: row.get("skill_name")),
            ("chapter", "First Known Chapter", lambda row: row.get("chapter")),
            ("description", "Description", lambda row: row.get("description")),
            ("evidence", "Evidence", first_evidence_text),
        ],
        added_field="Character Skill Link",
        removed_field="Character Skill Link",
    )
    record_collection_logs(
        novel_id=after["novel_id"],
        parent_type="character",
        parent_id=after["id"],
        parent_label=after["name"],
        entity_type="character_item",
        before_rows=before.get("items") or [],
        after_rows=after.get("items") or [],
        entity_label_getter=lambda row: row.get("item_name") or "Item Link",
        field_getters=[
            ("item", "Item", lambda row: row.get("item_name")),
            ("chapter", "First Known Chapter", lambda row: row.get("chapter")),
            ("description", "Description", lambda row: row.get("description")),
            ("evidence", "Evidence", first_evidence_text),
        ],
        added_field="Character Item Link",
        removed_field="Character Item Link",
    )


def record_skill_editor_logs(before, after):
    record_field_logs(after["novel_id"], "skill", after["id"], after["name"], before, after, SKILL_LOG_FIELDS)
    record_collection_logs(
        novel_id=after["novel_id"],
        parent_type="skill",
        parent_id=after["id"],
        parent_label=after["name"],
        entity_type="skill_alias",
        before_rows=before.get("aliases") or [],
        after_rows=after.get("aliases") or [],
        entity_label_getter=lambda row: row.get("alias"),
        field_getters=[
            ("alias", "Alias", lambda row: row.get("alias")),
            ("chapter", "First Mentioned Chapter", lambda row: row.get("first_seen_chapter")),
            ("evidence", "Evidence", lambda row: row.get("evidence")),
        ],
        added_field="Alias",
        removed_field="Alias",
    )
    record_collection_logs(
        novel_id=after["novel_id"],
        parent_type="skill",
        parent_id=after["id"],
        parent_label=after["name"],
        entity_type="character_skill",
        before_rows=before.get("characters") or [],
        after_rows=after.get("characters") or [],
        entity_label_getter=lambda row: row.get("character_name") or "Character Link",
        field_getters=[
            ("character", "Character", lambda row: row.get("character_name")),
            ("chapter", "First Known Chapter", lambda row: row.get("chapter")),
            ("description", "Description", lambda row: row.get("description")),
            ("evidence", "Evidence", first_evidence_text),
        ],
        added_field="Character Skill Link",
        removed_field="Character Skill Link",
    )


def record_item_editor_logs(before, after):
    record_field_logs(after["novel_id"], "item", after["id"], after["name"], before, after, ITEM_LOG_FIELDS)
    record_collection_logs(
        novel_id=after["novel_id"],
        parent_type="item",
        parent_id=after["id"],
        parent_label=after["name"],
        entity_type="character_item",
        before_rows=before.get("characters") or [],
        after_rows=after.get("characters") or [],
        entity_label_getter=lambda row: row.get("character_name") or "Character Link",
        field_getters=[
            ("character", "Character", lambda row: row.get("character_name")),
            ("chapter", "First Known Chapter", lambda row: row.get("chapter")),
            ("description", "Description", lambda row: row.get("description")),
            ("evidence", "Evidence", first_evidence_text),
        ],
        added_field="Character Item Link",
        removed_field="Character Item Link",
    )


def split_context_paragraphs(content):
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n+", content or "")
        if paragraph.strip()
    ]

    if paragraphs:
        return paragraphs

    fallback = " ".join((content or "").split())
    return [fallback] if fallback else []


def locate_evidence_paragraph(paragraphs, evidence_text):
    normalized_evidence = normalize_text(evidence_text)

    if not normalized_evidence:
        return None

    for index, paragraph in enumerate(paragraphs):
        if normalized_evidence in normalize_text(paragraph):
            return index

    return None


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


@admin_review_bp.get("/chapters/<int:chapter_id>/context")
def chapter_evidence_context(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    evidence_text = request.args.get("evidence", "")
    radius = request.args.get("radius", 1, type=int)
    radius = max(1, min(radius, 2))
    paragraphs = split_context_paragraphs(chapter.content)
    evidence_index = locate_evidence_paragraph(paragraphs, evidence_text)

    if evidence_index is None:
        return success(
            {
                "chapter": chapter.to_reference_dict(),
                "evidence_text": evidence_text,
                "exact_match": False,
                "paragraphs": [],
                "message": "Could not locate exact paragraph in chapter text.",
            }
        )

    start_index = max(0, evidence_index - radius)
    end_index = min(len(paragraphs), evidence_index + radius + 1)

    return success(
        {
            "chapter": chapter.to_reference_dict(),
            "evidence_text": evidence_text,
            "exact_match": True,
            "paragraphs": [
                {
                    "index": index,
                    "text": paragraphs[index],
                    "is_evidence": index == evidence_index,
                }
                for index in range(start_index, end_index)
            ],
        }
    )


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


def evidence_response(entity_type, entity_id):
    return [
        {
            **evidence.to_admin_dict(),
            "chapter": chapter_reference(evidence.chapter_id),
            "created_at": serialize_datetime(evidence.created_at),
        }
        for evidence in WikiEvidence.query.filter_by(
            entity_type=entity_type,
            entity_id=entity_id,
        )
        .order_by(WikiEvidence.id)
        .all()
    ]


CONVERTIBLE_REVIEW_ENTITY_TYPES = {"skills", "items"}


def move_wiki_evidence(source_type, source_id, target_type, target_id):
    evidence_rows = WikiEvidence.query.filter_by(
        entity_type=source_type,
        entity_id=source_id,
    ).all()

    for evidence in evidence_rows:
        db.session.add(WikiEvidence(
            novel_id=evidence.novel_id,
            chapter_id=evidence.chapter_id,
            entity_type=target_type,
            entity_id=target_id,
            evidence_text=evidence.evidence_text,
        ))
        db.session.delete(evidence)


def converted_review_payload(payload, source, target_entity_type):
    allowed_fields = {"target_entity_type", "name", "category", "description", "admin_notes"}
    unexpected_fields = set(payload) - allowed_fields

    if unexpected_fields:
        return None, f"Unsupported conversion field: {sorted(unexpected_fields)[0]}."

    name = validate_optional_text(payload.get("name", source.name), "Name")
    name = (name or "").strip()

    if not name:
        return None, "Name is required."

    category_text = validate_optional_text(payload.get("category", source.category), "Category")

    if target_entity_type == "skills":
        category = normalize_skill_category(category_text)

        if category_text not in (None, "") and not category:
            return None, "Skill category must be one of the supported categories."
    else:
        category = normalize_item_category(category_text)

        if category_text not in (None, "") and not category:
            return None, "Item category must be one of the supported categories."

    return {
        "name": name,
        "category": category,
        "description": validate_optional_text(payload.get("description", source.description), "Description") or None,
        "admin_notes": validate_optional_text(payload.get("admin_notes", source.admin_notes), "Admin notes") or None,
    }, None


def convert_skill_relationships_to_item(skill, item):
    if CharacterSkill.query.filter_by(skill_id=skill.id, review_status=APPROVED_STATUS).first():
        return "Cannot convert a skill with approved character relationships."

    relationships = CharacterSkill.query.filter_by(skill_id=skill.id).all()

    for relationship in relationships:
        converted = CharacterItem(
            novel_id=relationship.novel_id,
            character_id=relationship.character_id,
            item_id=item.id,
            chapter_id=relationship.chapter_id,
            relationship_type="associated",
            description=relationship.description,
            review_status=relationship.review_status,
            admin_notes=relationship.admin_notes,
        )
        db.session.add(converted)
        db.session.flush()
        move_wiki_evidence("character_skill", relationship.id, "character_item", converted.id)
        db.session.delete(relationship)

    return None


def convert_item_relationships_to_skill(item, skill):
    if CharacterItem.query.filter_by(item_id=item.id, review_status=APPROVED_STATUS).first():
        return "Cannot convert an item with approved character relationships."

    relationships = CharacterItem.query.filter_by(item_id=item.id).all()

    for relationship in relationships:
        converted = CharacterSkill(
            novel_id=relationship.novel_id,
            character_id=relationship.character_id,
            skill_id=skill.id,
            chapter_id=relationship.chapter_id,
            relationship_type="has",
            description=relationship.description,
            review_status=relationship.review_status,
            admin_notes=relationship.admin_notes,
        )
        db.session.add(converted)
        db.session.flush()
        move_wiki_evidence("character_item", relationship.id, "character_skill", converted.id)
        db.session.delete(relationship)

    return None


def approved_character_relation_rows(model, character_id):
    rows = (
        model.query.filter_by(
            character_id=character_id,
            review_status=APPROVED_STATUS,
        )
        .order_by(model.id.desc())
        .all()
    )

    enriched_rows = []

    for row in rows:
        row_data = row.to_admin_dict()
        chapter_id = row_data.get("source_chapter_id") or row_data.get("chapter_id")
        row_data["chapter"] = chapter_reference(chapter_id)
        row_data["created_at"] = serialize_datetime(row.created_at)
        row_data["evidence"] = evidence_response(EVIDENCE_ENTITY_TYPES.get(
            {
                CharacterProgressionEvent: "progression_events",
                CharacterSkill: "character_skills",
                CharacterItem: "character_items",
                CharacterLifeEvent: "life_events",
            }[model]
        ), row.id)
        enriched_rows.append(row_data)

    return enriched_rows


def character_editor_response(character):
    data = admin_review_response("characters", character)
    data["created_at"] = serialize_datetime(character.created_at)
    data["evidence"] = evidence_response("character", character.id)

    data["aliases"] = [
        {
            **alias.to_admin_dict(),
            "first_seen_chapter": chapter_reference(alias.first_seen_chapter_id),
            "created_at": serialize_datetime(alias.created_at),
        }
        for alias in character.aliases
    ]
    data["progression_events"] = approved_character_relation_rows(
        CharacterProgressionEvent,
        character.id,
    )
    data["skills"] = approved_character_relation_rows(CharacterSkill, character.id)
    data["items"] = approved_character_relation_rows(CharacterItem, character.id)
    data["life_events"] = approved_character_relation_rows(CharacterLifeEvent, character.id)
    data["metadata_history"] = [
        {
            **proposal.to_admin_dict(),
            "chapter": chapter_reference(proposal.chapter_id),
            "created_at": serialize_datetime(proposal.created_at),
            "updated_at": serialize_datetime(proposal.updated_at),
        }
        for proposal in CharacterMetadataProposal.query.filter_by(
            character_id=character.id,
            review_status=APPROVED_STATUS,
        )
        .order_by(CharacterMetadataProposal.id.desc())
        .all()
    ]
    data["counts"] = {
        "aliases": len(data["aliases"]),
        "progression_events": len(data["progression_events"]),
        "skills": len(data["skills"]),
        "items": len(data["items"]),
        "life_events": len(data["life_events"]),
        "metadata_history": len(data["metadata_history"]),
        "evidence": len(data["evidence"]),
    }

    return data


def skill_editor_response(skill):
    data = admin_review_response("skills", skill)
    data["created_at"] = serialize_datetime(skill.created_at)
    data["evidence"] = evidence_response("skill", skill.id)
    data["aliases"] = [
        {
            **alias.to_admin_dict(),
            "first_seen_chapter": chapter_reference(alias.first_seen_chapter_id),
            "created_at": serialize_datetime(alias.created_at),
        }
        for alias in skill.aliases
    ]
    data["characters"] = [
        {
            **relationship.to_admin_dict(),
            "chapter": chapter_reference(relationship.chapter_id),
            "evidence": evidence_response("character_skill", relationship.id),
            "created_at": serialize_datetime(relationship.created_at),
        }
        for relationship in CharacterSkill.query.filter_by(
            skill_id=skill.id,
            review_status=APPROVED_STATUS,
        )
        .order_by(CharacterSkill.id)
        .all()
    ]
    data["counts"] = {
        "aliases": len(data["aliases"]),
        "characters": len(data["characters"]),
        "evidence": len(data["evidence"]),
    }
    return data


def item_editor_response(item):
    data = admin_review_response("items", item)
    data["created_at"] = serialize_datetime(item.created_at)
    data["evidence"] = evidence_response("item", item.id)
    data["characters"] = [
        {
            **relationship.to_admin_dict(),
            "chapter": chapter_reference(relationship.chapter_id),
            "evidence": evidence_response("character_item", relationship.id),
            "created_at": serialize_datetime(relationship.created_at),
        }
        for relationship in CharacterItem.query.filter_by(
            item_id=item.id,
            review_status=APPROVED_STATUS,
        )
        .order_by(CharacterItem.id)
        .all()
    ]
    data["counts"] = {
        "characters": len(data["characters"]),
        "evidence": len(data["evidence"]),
    }
    return data


@admin_review_bp.get("/wiki-data/novels/<int:novel_id>/characters")
def list_wiki_data_characters(novel_id):
    characters = (
        Character.query.filter_by(
            novel_id=novel_id,
            review_status=APPROVED_STATUS,
        )
        .order_by(Character.name)
        .all()
    )

    return success({"characters": [character_editor_response(character) for character in characters]})


@admin_review_bp.get("/wiki-data/novels/<int:novel_id>/chapters/search")
def search_wiki_data_chapters(novel_id):
    chapter_id = request.args.get("chapter_id", type=int)
    chapter_number = request.args.get("number", type=int)
    query_text = normalize_text(request.args.get("q", ""))
    limit = min(max(request.args.get("limit", 12, type=int), 1), 25)
    query = Chapter.query.filter_by(novel_id=novel_id)

    if chapter_id:
        chapter = query.filter_by(id=chapter_id).first()
        return success({"chapters": [chapter.to_admin_verification_dict()] if chapter else []})

    if chapter_number:
        chapter = query.filter_by(chapter_number=chapter_number).first()
        return success({"chapters": [chapter.to_admin_verification_dict()] if chapter else []})

    if query_text:
        query = query.filter(
            db.or_(
                db.cast(Chapter.chapter_number, db.String).ilike(f"%{query_text}%"),
                Chapter.title.ilike(f"%{query_text}%"),
            )
        )

    chapters = query.order_by(Chapter.chapter_number).limit(limit).all()

    return success({"chapters": [chapter.to_admin_verification_dict() for chapter in chapters]})


@admin_review_bp.get("/wiki-data/novels/<int:novel_id>/skills")
def list_wiki_data_skills(novel_id):
    query_text = normalize_text(request.args.get("q", ""))
    query = Skill.query.filter_by(
        novel_id=novel_id,
        review_status=APPROVED_STATUS,
    )

    if query_text:
        query = query.filter(Skill.name.ilike(f"%{query_text}%"))

    skills = query.order_by(Skill.name).all()
    return success({"skills": [skill_editor_response(skill) for skill in skills]})


@admin_review_bp.get("/wiki-data/novels/<int:novel_id>/items")
def list_wiki_data_items(novel_id):
    query_text = normalize_text(request.args.get("q", ""))
    query = Item.query.filter_by(
        novel_id=novel_id,
        review_status=APPROVED_STATUS,
    )

    if query_text:
        query = query.filter(Item.name.ilike(f"%{query_text}%"))

    items = query.order_by(Item.name).all()
    return success({"items": [item_editor_response(item) for item in items]})


def parse_date_filter(value, end_of_day=False):
    if not value:
        return None

    try:
        parsed_date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed_date = datetime.combine(
                datetime.strptime(value, "%Y-%m-%d").date(),
                time.max if end_of_day else time.min,
                tzinfo=timezone.utc,
            )
        except ValueError as error:
            raise PayloadValidationError("Date filters must be valid dates.") from error

    if parsed_date.tzinfo is None:
        parsed_date = parsed_date.replace(tzinfo=timezone.utc)

    return parsed_date


def parent_label_for_edit_log(log):
    if not log.parent_entity_type or not log.parent_entity_id:
        return None

    model_by_type = {
        "character": Character,
        "skill": Skill,
        "item": Item,
    }
    model = model_by_type.get(log.parent_entity_type)

    if not model:
        return None

    record = model.query.get(log.parent_entity_id)

    return record.name if record else None


def edit_log_response(log):
    data = log.to_admin_dict()
    data["parent_entity_label"] = parent_label_for_edit_log(log)
    return data


@admin_review_bp.get("/wiki-data/novels/<int:novel_id>/edit-log")
def list_wiki_edit_logs(novel_id):
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 10, type=int), 1), 50)
    search = (request.args.get("search") or "").strip()
    entity_type = (request.args.get("entity_type") or "all").strip()
    change_type = (request.args.get("change_type") or "all").strip().lower()
    edited_by = (request.args.get("edited_by") or "all").strip()
    date_from = parse_date_filter(request.args.get("date_from"))
    date_to = parse_date_filter(request.args.get("date_to"), end_of_day=True)

    query = WikiEditLog.query.filter_by(novel_id=novel_id)

    if search:
        like_search = f"%{search}%"
        query = query.filter(
            db.or_(
                WikiEditLog.entity_label.ilike(like_search),
                WikiEditLog.field_name.ilike(like_search),
                WikiEditLog.summary.ilike(like_search),
                WikiEditLog.old_value_json.ilike(like_search),
                WikiEditLog.new_value_json.ilike(like_search),
            )
        )

    if entity_type != "all":
        query = query.filter(WikiEditLog.entity_type == entity_type)

    if change_type != "all":
        query = query.filter(WikiEditLog.change_type == change_type)

    if edited_by != "all":
        query = query.filter(WikiEditLog.edited_by == edited_by)

    if date_from:
        query = query.filter(db.func.date(WikiEditLog.created_at) >= date_from.date().isoformat())

    if date_to:
        query = query.filter(db.func.date(WikiEditLog.created_at) <= date_to.date().isoformat())

    total = query.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    logs = (
        query.order_by(WikiEditLog.created_at.desc(), WikiEditLog.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return success({
        "logs": [edit_log_response(log) for log in logs],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    })


SKILL_EDITOR_FIELDS = {"name", "category", "description", "admin_notes"}
ITEM_EDITOR_FIELDS = {"name", "category", "description", "admin_notes"}


@admin_review_bp.patch("/wiki-data/skills/<int:skill_id>")
def update_wiki_data_skill(skill_id):
    payload = request_json_object()
    skill = Skill.query.filter_by(id=skill_id, review_status=APPROVED_STATUS).first_or_404()
    before = skill_editor_response(skill)

    if "name" in payload:
        skill_name = (validate_optional_text(payload.get("name"), "Skill name") or "").strip()

        if not skill_name:
            return failure("Skill name is required.")

        duplicate_skill = Skill.query.filter(
            Skill.novel_id == skill.novel_id,
            Skill.id != skill.id,
            Skill.review_status == APPROVED_STATUS,
            db.func.lower(Skill.name) == normalize_text(skill_name),
        ).first()

        if duplicate_skill:
            return failure("A canonical skill with this name already exists.")

        skill.name = skill_name

    if "category" in payload:
        category_text = validate_optional_text(payload.get("category"), "Skill category")
        skill_category = normalize_skill_category(category_text)
        if category_text not in (None, "") and not skill_category:
            return failure("Skill category must be one of the supported categories.")
        skill.category = skill_category

    for field in SKILL_EDITOR_FIELDS - {"name", "category"}:
        if field in payload:
            setattr(skill, field, validate_optional_text(payload.get(field), f"Skill {field.replace('_', ' ')}"))

    if "aliases" in payload:
        alias_error = apply_skill_alias_payload(skill, payload.get("aliases"))

        if alias_error:
            db.session.rollback()
            return failure(alias_error)

    if "character_relationships" in payload:
        character_relationship_error = apply_skill_character_payload(
            skill,
            payload.get("character_relationships"),
        )

        if character_relationship_error:
            db.session.rollback()
            return failure(character_relationship_error)

    try:
        db.session.flush()
        db.session.refresh(skill)
        after = skill_editor_response(skill)
        record_skill_editor_logs(before, after)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return failure("This canonical skill or alias already exists.")

    return success(skill_editor_response(skill))


@admin_review_bp.patch("/wiki-data/items/<int:item_id>")
def update_wiki_data_item(item_id):
    payload = request_json_object()
    item = Item.query.filter_by(id=item_id, review_status=APPROVED_STATUS).first_or_404()
    before = item_editor_response(item)

    if "name" in payload:
        item_name = (validate_optional_text(payload.get("name"), "Item name") or "").strip()

        if not item_name:
            return failure("Item name is required.")

        duplicate_item = Item.query.filter(
            Item.novel_id == item.novel_id,
            Item.id != item.id,
            Item.review_status == APPROVED_STATUS,
            db.func.lower(Item.name) == normalize_text(item_name),
        ).first()

        if duplicate_item:
            return failure("A canonical item with this name already exists.")

        item.name = item_name

    if "category" in payload:
        category_text = validate_optional_text(payload.get("category"), "Item category")
        item_category = normalize_item_category(category_text)
        if category_text not in (None, "") and not item_category:
            return failure("Item category must be one of the supported categories.")
        item.category = item_category

    for field in ITEM_EDITOR_FIELDS - {"name", "category"}:
        if field in payload:
            setattr(item, field, validate_optional_text(payload.get(field), f"Item {field.replace('_', ' ')}"))

    if "character_relationships" in payload:
        character_relationship_error = apply_item_character_payload(
            item,
            payload.get("character_relationships"),
        )

        if character_relationship_error:
            db.session.rollback()
            return failure(character_relationship_error)

    try:
        db.session.flush()
        db.session.refresh(item)
        after = item_editor_response(item)
        record_item_editor_logs(before, after)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return failure("This canonical item relationship already exists.")

    return success(item_editor_response(item))


CHARACTER_EDITOR_FIELDS = {
    "name",
    "description",
    "first_mentioned_chapter_id",
    "first_appeared_chapter_id",
    "first_seen_chapter_id",
    "age_text",
    "gender",
    "race_or_species",
    "race_or_species_source",
    "race_or_species_confidence",
    "origin",
    "faction_or_affiliation",
    "status",
    "titles",
    "current_cultivation_level",
    "current_position",
    "current_class_rank",
    "current_power_rank",
    "admin_notes",
}

CHARACTER_CHAPTER_FIELDS = {
    "first_mentioned_chapter_id",
    "first_appeared_chapter_id",
    "first_seen_chapter_id",
}


@admin_review_bp.patch("/wiki-data/characters/<int:character_id>")
def update_wiki_data_character(character_id):
    payload = request_json_object()
    character = Character.query.filter_by(
        id=character_id,
        review_status=APPROVED_STATUS,
    ).first_or_404()
    before = character_editor_response(character)

    if "name" in payload:
        if not isinstance(payload["name"], str) or not payload["name"].strip():
            return failure("Character name is required.")

    for field in CHARACTER_EDITOR_FIELDS:
        if field not in payload:
            continue

        value = payload[field]

        if field in CHARACTER_CHAPTER_FIELDS:
            value = parse_optional_int(value)

            if not validate_chapter_for_novel(value, character.novel_id):
                return failure("Chapter reference must belong to this novel.")
        else:
            value = validate_optional_text(value, f"Character {field.replace('_', ' ')}")

        setattr(character, field, value)

    if "aliases" in payload:
        alias_error = apply_character_alias_payload(character, payload.get("aliases"))

        if alias_error:
            db.session.rollback()
            return failure(alias_error)

    if "cultivation_events" in payload:
        cultivation_error = apply_character_cultivation_payload(
            character,
            payload.get("cultivation_events"),
        )

        if cultivation_error:
            db.session.rollback()
            return failure(cultivation_error)

    if "skill_relationships" in payload:
        skill_error = apply_character_skill_payload(
            character,
            payload.get("skill_relationships"),
        )

        if skill_error:
            db.session.rollback()
            return failure(skill_error)

    if "item_relationships" in payload:
        item_error = apply_character_item_payload(
            character,
            payload.get("item_relationships"),
        )

        if item_error:
            db.session.rollback()
            return failure(item_error)

    try:
        db.session.flush()
        db.session.refresh(character)
        after = character_editor_response(character)
        record_character_editor_logs(before, after)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return failure("This canonical relationship already exists.")

    return success(character_editor_response(character))


@admin_review_bp.post("/wiki-data/characters/<int:character_id>/aliases")
def create_wiki_data_character_alias(character_id):
    payload = request_json_object()
    character = Character.query.filter_by(
        id=character_id,
        review_status=APPROVED_STATUS,
    ).first_or_404()
    before = character_editor_response(character)
    alias_text = (validate_optional_text(payload.get("alias"), "Alias") or "").strip()

    if not alias_text:
        return failure("Alias is required.")

    first_seen_chapter_id = parse_optional_int(payload.get("first_seen_chapter_id"))

    if not first_seen_chapter_id:
        return failure("Alias first mentioned chapter is required.")

    alias = CharacterAlias(
        character_id=character.id,
        alias=alias_text,
        first_seen_chapter_id=first_seen_chapter_id,
        evidence=validate_optional_text(payload.get("evidence"), "Alias evidence") or None,
        is_primary=parse_boolean(payload.get("is_primary"), "Primary alias flag"),
    )

    if not validate_chapter_for_novel(alias.first_seen_chapter_id, character.novel_id):
        return failure("Alias chapter reference must belong to this novel.")

    if CharacterAlias.query.filter(
        CharacterAlias.character_id == character.id,
        db.func.lower(CharacterAlias.alias) == normalize_text(alias_text),
    ).first():
        return failure("This character already has this alias.")

    db.session.add(alias)

    if alias.is_primary:
        for existing_alias in character.aliases:
            existing_alias.is_primary = False

    try:
        db.session.flush()
        db.session.refresh(character)
        after = character_editor_response(character)
        record_character_editor_logs(before, after)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return failure("This alias already exists for the character.")

    return success(character_editor_response(character), status=201)


@admin_review_bp.patch("/wiki-data/character-aliases/<int:alias_id>")
def update_wiki_data_character_alias(alias_id):
    payload = request_json_object()
    alias = CharacterAlias.query.get_or_404(alias_id)
    character = Character.query.filter_by(
        id=alias.character_id,
        review_status=APPROVED_STATUS,
    ).first_or_404()
    before = character_editor_response(character)

    if "alias" in payload:
        alias_text = (validate_optional_text(payload.get("alias"), "Alias") or "").strip()

        if not alias_text:
            return failure("Alias is required.")

        duplicate_alias = CharacterAlias.query.filter(
            CharacterAlias.character_id == character.id,
            CharacterAlias.id != alias.id,
            db.func.lower(CharacterAlias.alias) == normalize_text(alias_text),
        ).first()

        if duplicate_alias:
            return failure("This character already has this alias.")

        alias.alias = alias_text

    if "first_seen_chapter_id" in payload:
        alias.first_seen_chapter_id = parse_optional_int(payload.get("first_seen_chapter_id"))

        if not alias.first_seen_chapter_id:
            return failure("Alias first mentioned chapter is required.")

        if not validate_chapter_for_novel(alias.first_seen_chapter_id, character.novel_id):
            return failure("Alias chapter reference must belong to this novel.")

    if "evidence" in payload:
        alias.evidence = validate_optional_text(payload.get("evidence"), "Alias evidence") or None

    if "is_primary" in payload:
        alias.is_primary = parse_boolean(payload.get("is_primary"), "Primary alias flag")

        if alias.is_primary:
            for existing_alias in character.aliases:
                if existing_alias.id != alias.id:
                    existing_alias.is_primary = False

    try:
        db.session.flush()
        db.session.refresh(character)
        after = character_editor_response(character)
        record_character_editor_logs(before, after)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return failure("This alias already exists for the character.")

    return success(character_editor_response(character))


@admin_review_bp.delete("/wiki-data/character-aliases/<int:alias_id>")
def delete_wiki_data_character_alias(alias_id):
    alias = CharacterAlias.query.get_or_404(alias_id)
    character = Character.query.filter_by(
        id=alias.character_id,
        review_status=APPROVED_STATUS,
    ).first_or_404()
    before = character_editor_response(character)
    db.session.delete(alias)
    db.session.flush()
    db.session.refresh(character)
    after = character_editor_response(character)
    record_character_editor_logs(before, after)
    db.session.commit()

    return success(character_editor_response(character))


METADATA_PROPOSAL_FIELDS = {
    "age_text",
    "gender",
    "race_or_species",
    "origin",
    "faction_or_affiliation",
    "status",
    "titles",
}

LIFE_STATUS_VALUES = {
    "alive",
    "dead",
    "historical",
    "missing",
    "sealed",
    "reincarnated",
    "unknown",
}


def apply_metadata_proposal(proposal):
    if proposal.field_name not in METADATA_PROPOSAL_FIELDS:
        return False

    character = proposal.character

    if not character:
        return False

    if proposal.field_name == "status" and proposal.proposed_value not in LIFE_STATUS_VALUES:
        return False

    if proposal.field_name == "titles":
        character.titles = merge_text(character.titles, proposal.proposed_value)
    else:
        setattr(character, proposal.field_name, proposal.proposed_value)

    if proposal.field_name == "race_or_species":
        character.race_or_species_source = "extracted"
        character.race_or_species_confidence = "confirmed"

    return True


def initialize_alive_status_on_character_approval(character):
    if not character or not character.first_appeared_chapter_id:
        return False

    if character.status and character.status != "unknown":
        return False

    character.status = "alive"
    return True


def initialize_default_species_on_character_approval(character):
    if not character:
        return False

    if character.race_or_species:
        if not character.race_or_species_source:
            character.race_or_species_source = "extracted"
        if not character.race_or_species_confidence:
            character.race_or_species_confidence = "confirmed"
        return False

    character.race_or_species = "Human"
    character.race_or_species_source = "implicit_default"
    character.race_or_species_confidence = "assumed"
    return True


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

    if (
        entity_type == "character_metadata_proposals"
        and payload.get("review_status") == "approved"
    ):
        if not apply_metadata_proposal(record):
            return failure("Metadata proposal could not be applied.")

    if entity_type == "characters" and payload.get("review_status") == "approved":
        initialize_alive_status_on_character_approval(record)
        initialize_default_species_on_character_approval(record)

    db.session.commit()

    return success(admin_review_response(entity_type, record))


@admin_review_bp.post("/<entity_type>/<int:entity_id>/convert")
def convert_extracted_entity(entity_type, entity_id):
    if entity_type not in CONVERTIBLE_REVIEW_ENTITY_TYPES:
        return failure("Only skill and item review proposals can be converted for now.", status=400)

    payload = request_json_object()
    target_entity_type = payload.get("target_entity_type")

    if target_entity_type not in CONVERTIBLE_REVIEW_ENTITY_TYPES:
        return failure("target_entity_type must be skills or items.")

    if target_entity_type == entity_type:
        return failure("target_entity_type must be different from the current review item type.")

    source_model = ENTITY_CONFIG[entity_type]["model"]
    source = source_model.query.get_or_404(entity_id)

    if source.review_status != "pending":
        return failure("Only pending review items can be converted.")

    converted_payload, payload_error = converted_review_payload(payload, source, target_entity_type)

    if payload_error:
        return failure(payload_error)

    target_model = ENTITY_CONFIG[target_entity_type]["model"]
    converted = target_model(
        novel_id=source.novel_id,
        review_status=source.review_status,
        **converted_payload,
    )

    try:
        db.session.add(converted)
        db.session.flush()

        move_wiki_evidence(
            EVIDENCE_ENTITY_TYPES[entity_type],
            source.id,
            EVIDENCE_ENTITY_TYPES[target_entity_type],
            converted.id,
        )

        if entity_type == "skills" and target_entity_type == "items":
            relationship_error = convert_skill_relationships_to_item(source, converted)
        elif entity_type == "items" and target_entity_type == "skills":
            relationship_error = convert_item_relationships_to_skill(source, converted)
        else:
            relationship_error = None

        if relationship_error:
            db.session.rollback()
            return failure(relationship_error)

        db.session.delete(source)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return failure("Converted review item conflicts with existing data.")

    return success(
        {
            "entity_type": target_entity_type,
            "review_item": admin_review_response(target_entity_type, converted),
        },
        status=201,
    )


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
    target.age_text = target.age_text or source.age_text
    target.gender = target.gender or source.gender
    source_species_confirmed = (
        source.race_or_species
        and source.race_or_species_source == "extracted"
        and source.race_or_species_confidence == "confirmed"
    )
    target_species_assumed = (
        target.race_or_species_source == "implicit_default"
        and target.race_or_species_confidence == "assumed"
    )

    if source_species_confirmed and (not target.race_or_species or target_species_assumed):
        target.race_or_species = source.race_or_species
        target.race_or_species_source = source.race_or_species_source
        target.race_or_species_confidence = source.race_or_species_confidence
    else:
        target.race_or_species = target.race_or_species or source.race_or_species
        target.race_or_species_source = (
            target.race_or_species_source or source.race_or_species_source
        )
        target.race_or_species_confidence = (
            target.race_or_species_confidence or source.race_or_species_confidence
        )
    target.origin = target.origin or source.origin
    target.faction_or_affiliation = target.faction_or_affiliation or source.faction_or_affiliation
    target.status = target.status or source.status
    target.titles = merge_text(target.titles, source.titles)

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
    CharacterMetadataProposal.query.filter_by(character_id=source.id).update(
        {"character_id": target.id}
    )
    CharacterSkill.query.filter_by(character_id=source.id).update(
        {"character_id": target.id}
    )
    CharacterItem.query.filter_by(character_id=source.id).update(
        {"character_id": target.id}
    )
    CharacterLifeEvent.query.filter_by(character_id=source.id).update(
        {"character_id": target.id}
    )

    db.session.delete(source)
    db.session.commit()

    return success(admin_review_response("characters", target))
