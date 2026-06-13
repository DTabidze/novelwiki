from app.models import (
    CharacterItem,
    CharacterLifeEvent,
    CharacterMetadataProposal,
    CharacterProgressionEvent,
    CharacterSkill,
    Chapter,
    WikiEvidence,
    db,
    serialize_datetime,
)

APPROVED_STATUS = "approved"

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


def chapter_reference(chapter_id):
    if not chapter_id:
        return None

    chapter = db.session.get(Chapter, chapter_id)

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
