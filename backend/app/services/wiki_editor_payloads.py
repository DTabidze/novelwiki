from flask import request

from app.models import (
    Character,
    CharacterAlias,
    CharacterItem,
    CharacterProgressionEvent,
    CharacterSkill,
    Chapter,
    Item,
    Skill,
    SkillAlias,
    WikiEvidence,
    db,
)

APPROVED_STATUS = "approved"

EVIDENCE_ENTITY_TYPES = {
    "progression_events": "progression",
    "character_items": "character_item",
    "character_skills": "character_skill",
}


def normalize_text(value):
    import re

    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


class PayloadValidationError(ValueError):
    pass


def parse_optional_int(value):
    if value in (None, ""):
        return None

    if isinstance(value, bool):
        raise PayloadValidationError("IDs must be positive integers.")

    try:
        parsed_value = int(value)
    except (TypeError, ValueError) as error:
        raise PayloadValidationError("IDs must be positive integers.") from error

    if parsed_value <= 0:
        raise PayloadValidationError("IDs must be positive integers.")

    return parsed_value


def validate_payload_rows(rows, field_name):
    if not isinstance(rows, list):
        raise PayloadValidationError(f"{field_name} must be an array.")

    if any(not isinstance(row, dict) for row in rows):
        raise PayloadValidationError(f"Every {field_name} entry must be an object.")


def validate_optional_text(value, field_name):
    if value is not None and not isinstance(value, str):
        raise PayloadValidationError(f"{field_name} must be text.")

    return value


def parse_boolean(value, field_name, default=False):
    if value is None:
        return default

    if not isinstance(value, bool):
        raise PayloadValidationError(f"{field_name} must be true or false.")

    return value


def request_json_object():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        raise PayloadValidationError("Request body must be a JSON object.")

    return payload


def validate_chapter_for_novel(chapter_id, novel_id):
    if chapter_id is None:
        return True

    return Chapter.query.filter_by(id=chapter_id, novel_id=novel_id).first() is not None


def apply_character_alias_payload(character, alias_rows):
    validate_payload_rows(alias_rows, "Aliases")
    alias_keys = set()
    primary_count = 0

    for alias_data in alias_rows:
        if parse_boolean(alias_data.get("_deleted"), "Alias deleted flag"):
            continue

        alias_text = normalize_text(validate_optional_text(alias_data.get("alias"), "Alias"))

        if not alias_text:
            return "Alias is required."

        if alias_text in alias_keys:
            return "This character already has this alias."

        alias_keys.add(alias_text)
        primary_count += int(parse_boolean(alias_data.get("is_primary"), "Primary alias flag"))

    if primary_count > 1:
        return "A character can only have one primary alias."

    if any(
        parse_boolean(alias_data.get("is_primary"), "Primary alias flag")
        and not parse_boolean(alias_data.get("_deleted"), "Alias deleted flag")
        for alias_data in alias_rows
    ):
        for alias in character.aliases:
            alias.is_primary = False

    for alias_data in alias_rows or []:
        alias_id = parse_optional_int(alias_data.get("id"))
        should_delete = parse_boolean(alias_data.get("_deleted"), "Alias deleted flag")

        if alias_id:
            alias = CharacterAlias.query.filter_by(
                id=alias_id,
                character_id=character.id,
            ).first()

            if not alias:
                return "Alias does not belong to this character."

            if should_delete:
                db.session.delete(alias)
                continue
        else:
            if should_delete:
                continue
            alias = None

        alias_text = (validate_optional_text(alias_data.get("alias"), "Alias") or "").strip()

        if not alias_text:
            return "Alias is required."

        first_seen_chapter_id = parse_optional_int(alias_data.get("first_seen_chapter_id"))

        if not first_seen_chapter_id:
            return "Alias first mentioned chapter is required."

        if not validate_chapter_for_novel(first_seen_chapter_id, character.novel_id):
            return "Alias chapter reference must belong to this novel."

        with db.session.no_autoflush:
            duplicate_query = CharacterAlias.query.filter(
                CharacterAlias.character_id == character.id,
                db.func.lower(CharacterAlias.alias) == alias_text,
            )

            if alias_id:
                duplicate_query = duplicate_query.filter(CharacterAlias.id != alias_id)

            if duplicate_query.first():
                return "This character already has this alias."

        if alias is None:
            alias = CharacterAlias(character_id=character.id)
            db.session.add(alias)

        alias.alias = alias_text
        alias.first_seen_chapter_id = first_seen_chapter_id
        alias.evidence = validate_optional_text(alias_data.get("evidence"), "Alias evidence") or None
        alias.is_primary = parse_boolean(alias_data.get("is_primary"), "Primary alias flag")

    return None


def apply_skill_alias_payload(skill, alias_rows):
    validate_payload_rows(alias_rows, "Skill aliases")
    alias_keys = set()

    for alias_data in alias_rows:
        if parse_boolean(alias_data.get("_deleted"), "Skill alias deleted flag"):
            continue

        alias_text = normalize_text(validate_optional_text(alias_data.get("alias"), "Skill alias"))

        if not alias_text:
            return "Skill alias is required."

        if alias_text in alias_keys:
            return "This skill already has this alias."

        alias_keys.add(alias_text)

    for alias_data in alias_rows:
        alias_id = parse_optional_int(alias_data.get("id"))
        should_delete = parse_boolean(alias_data.get("_deleted"), "Skill alias deleted flag")

        if alias_id:
            alias = SkillAlias.query.filter_by(id=alias_id, skill_id=skill.id).first()

            if not alias:
                return "Skill alias does not belong to this skill."

            if should_delete:
                db.session.delete(alias)
                continue
        elif should_delete:
            continue
        else:
            alias = None

        alias_text = (validate_optional_text(alias_data.get("alias"), "Skill alias") or "").strip()

        if not alias_text:
            return "Skill alias is required."

        first_seen_chapter_id = parse_optional_int(alias_data.get("first_seen_chapter_id"))

        if not first_seen_chapter_id:
            return "Skill alias first mentioned chapter is required."

        if not validate_chapter_for_novel(first_seen_chapter_id, skill.novel_id):
            return "Skill alias chapter reference must belong to this novel."

        with db.session.no_autoflush:
            duplicate_query = SkillAlias.query.filter(
                SkillAlias.skill_id == skill.id,
                db.func.lower(SkillAlias.alias) == normalize_text(alias_text),
            )

            if alias_id:
                duplicate_query = duplicate_query.filter(SkillAlias.id != alias_id)

            if duplicate_query.first():
                return "This skill already has this alias."

        if alias is None:
            alias = SkillAlias(skill_id=skill.id)
            db.session.add(alias)

        alias.alias = alias_text
        alias.first_seen_chapter_id = first_seen_chapter_id
        alias.evidence = validate_optional_text(alias_data.get("evidence"), "Skill alias evidence") or None

    return None


CULTIVATION_PROGRESSION_TYPES = {"cultivation_level", "realm"}


def apply_character_cultivation_payload(character, event_rows):
    validate_payload_rows(event_rows, "Cultivation events")

    for event_data in event_rows or []:
        event_id = parse_optional_int(event_data.get("id"))
        should_delete = parse_boolean(event_data.get("_deleted"), "Cultivation deleted flag")

        if event_id:
            event = CharacterProgressionEvent.query.filter_by(
                id=event_id,
                character_id=character.id,
            ).first()

            if not event:
                return "Cultivation record does not belong to this character."

            if should_delete:
                WikiEvidence.query.filter_by(
                    entity_type=EVIDENCE_ENTITY_TYPES["progression_events"],
                    entity_id=event.id,
                ).delete()
                db.session.delete(event)
                continue
        elif should_delete:
            continue
        else:
            event = None

        cultivation_level = (
            validate_optional_text(event_data.get("cultivation_level"), "Cultivation level")
            or validate_optional_text(event_data.get("new_value"), "Cultivation level")
            or ""
        ).strip()

        if not cultivation_level:
            return "Cultivation level is required."

        chapter_id = parse_optional_int(event_data.get("chapter_id"))

        if not chapter_id:
            return "Cultivation chapter is required."

        if not validate_chapter_for_novel(chapter_id, character.novel_id):
            return "Cultivation chapter reference must belong to this novel."

        progression_type = (
            validate_optional_text(event_data.get("progression_type"), "Cultivation progression type")
            or "cultivation_level"
        )

        if progression_type not in CULTIVATION_PROGRESSION_TYPES:
            return "Cultivation progression type is invalid."

        if event is None:
            event = CharacterProgressionEvent(
                novel_id=character.novel_id,
                character_id=character.id,
                chapter_id=chapter_id,
                progression_type=progression_type,
                new_value=cultivation_level,
                review_status=APPROVED_STATUS,
            )
            db.session.add(event)
            db.session.flush()

        event.progression_type = progression_type
        event.chapter_id = chapter_id
        event.old_value = validate_optional_text(event_data.get("old_value"), "Old cultivation value") or event.old_value
        event.new_value = cultivation_level
        event.description = (
            validate_optional_text(event_data.get("notes"), "Cultivation notes")
            or validate_optional_text(event_data.get("description"), "Cultivation description")
            or None
        )
        event.admin_notes = validate_optional_text(event_data.get("admin_notes"), "Cultivation admin notes") or None
        event.review_status = APPROVED_STATUS

        evidence_text = (validate_optional_text(event_data.get("evidence"), "Cultivation evidence") or "").strip()
        evidence = WikiEvidence.query.filter_by(
            entity_type=EVIDENCE_ENTITY_TYPES["progression_events"],
            entity_id=event.id,
        ).first()

        if evidence_text:
            if not evidence:
                evidence = WikiEvidence(
                    novel_id=character.novel_id,
                    entity_type=EVIDENCE_ENTITY_TYPES["progression_events"],
                    entity_id=event.id,
                )
                db.session.add(evidence)

            evidence.chapter_id = chapter_id
            evidence.evidence_text = evidence_text
        elif evidence:
            db.session.delete(evidence)

    return None


def apply_character_skill_payload(character, relationship_rows):
    validate_payload_rows(relationship_rows, "Skill relationships")
    active_skill_ids = set()

    for relationship_data in relationship_rows or []:
        if parse_boolean(relationship_data.get("_deleted"), "Skill relationship deleted flag"):
            continue

        skill_id = parse_optional_int(relationship_data.get("skill_id"))
        if skill_id:
            if skill_id in active_skill_ids:
                return "This skill is already attached to this character."

            active_skill_ids.add(skill_id)

    for relationship_data in relationship_rows or []:
        relationship_id = parse_optional_int(relationship_data.get("id"))
        should_delete = parse_boolean(
            relationship_data.get("_deleted"),
            "Skill relationship deleted flag",
        )

        if relationship_id:
            relationship = CharacterSkill.query.filter_by(
                id=relationship_id,
                character_id=character.id,
            ).first()

            if not relationship:
                return "Skill relationship does not belong to this character."

            if should_delete:
                WikiEvidence.query.filter_by(
                    entity_type=EVIDENCE_ENTITY_TYPES["character_skills"],
                    entity_id=relationship.id,
                ).delete()
                db.session.delete(relationship)
                continue
        else:
            if should_delete:
                continue
            relationship = None

        skill_id = parse_optional_int(relationship_data.get("skill_id"))
        chapter_id = parse_optional_int(relationship_data.get("chapter_id"))
        if not skill_id:
            return "Skill is required."

        skill = Skill.query.filter_by(
            id=skill_id,
            novel_id=character.novel_id,
            review_status=APPROVED_STATUS,
        ).first()

        if not skill:
            return "Skill must be an approved skill from this novel."

        if not chapter_id:
            return "Skill chapter is required."

        if not validate_chapter_for_novel(chapter_id, character.novel_id):
            return "Skill chapter reference must belong to this novel."

        with db.session.no_autoflush:
            duplicate_query = CharacterSkill.query.filter_by(
                character_id=character.id,
                skill_id=skill_id,
            )

            if relationship_id:
                duplicate_query = duplicate_query.filter(CharacterSkill.id != relationship_id)

            if duplicate_query.first():
                return "This skill is already attached to this character."

        if relationship is None:
            relationship = CharacterSkill(
                novel_id=character.novel_id,
                character_id=character.id,
                skill_id=skill_id,
                chapter_id=chapter_id,
                relationship_type="has",
                description=validate_optional_text(
                    relationship_data.get("description"),
                    "Skill relationship description",
                ) or None,
                review_status=APPROVED_STATUS,
            )
            db.session.add(relationship)
            db.session.flush()
        else:
            relationship.skill_id = skill_id
            relationship.chapter_id = chapter_id
            relationship.relationship_type = "has"
            relationship.description = validate_optional_text(
                relationship_data.get("description"),
                "Skill relationship description",
            ) or None

        relationship.admin_notes = validate_optional_text(
            relationship_data.get("admin_notes"),
            "Skill relationship admin notes",
        ) or None
        relationship.review_status = APPROVED_STATUS

        evidence_text = (
            validate_optional_text(relationship_data.get("evidence_text"), "Skill relationship evidence")
            or ""
        ).strip()
        evidence = WikiEvidence.query.filter_by(
            entity_type=EVIDENCE_ENTITY_TYPES["character_skills"],
            entity_id=relationship.id,
        ).first()

        if evidence_text:
            if not evidence:
                evidence = WikiEvidence(
                    novel_id=character.novel_id,
                    entity_type=EVIDENCE_ENTITY_TYPES["character_skills"],
                    entity_id=relationship.id,
                )
                db.session.add(evidence)

            evidence.chapter_id = chapter_id
            evidence.evidence_text = evidence_text
        elif evidence:
            db.session.delete(evidence)

    return None


def apply_character_item_payload(character, relationship_rows):
    validate_payload_rows(relationship_rows, "Item relationships")
    active_item_ids = set()

    for relationship_data in relationship_rows or []:
        if parse_boolean(relationship_data.get("_deleted"), "Item relationship deleted flag"):
            continue

        item_id = parse_optional_int(relationship_data.get("item_id"))
        if item_id:
            if item_id in active_item_ids:
                return "This item is already attached to this character."

            active_item_ids.add(item_id)

    for relationship_data in relationship_rows:
        relationship_id = parse_optional_int(relationship_data.get("id"))
        should_delete = parse_boolean(
            relationship_data.get("_deleted"),
            "Item relationship deleted flag",
        )

        if relationship_id:
            relationship = CharacterItem.query.filter_by(
                id=relationship_id,
                character_id=character.id,
            ).first()
            if not relationship:
                return "Item relationship does not belong to this character."

            if should_delete:
                WikiEvidence.query.filter_by(
                    entity_type=EVIDENCE_ENTITY_TYPES["character_items"],
                    entity_id=relationship.id,
                ).delete()
                db.session.delete(relationship)
                continue
        elif should_delete:
            continue
        else:
            relationship = None

        item_id = parse_optional_int(relationship_data.get("item_id"))
        chapter_id = parse_optional_int(relationship_data.get("chapter_id"))

        if not item_id:
            return "Item is required."

        item = Item.query.filter_by(
            id=item_id,
            novel_id=character.novel_id,
            review_status=APPROVED_STATUS,
        ).first()

        if not item:
            return "Item must be an approved item from this novel."

        if not chapter_id:
            return "Item chapter is required."

        if not validate_chapter_for_novel(chapter_id, character.novel_id):
            return "Item chapter reference must belong to this novel."

        duplicate_query = CharacterItem.query.filter_by(
            character_id=character.id,
            item_id=item_id,
        )
        if relationship_id:
            duplicate_query = duplicate_query.filter(CharacterItem.id != relationship_id)

        if duplicate_query.first():
            return "This item is already attached to this character."

        if relationship is None:
            relationship = CharacterItem(
                novel_id=character.novel_id,
                character_id=character.id,
                item_id=item_id,
                chapter_id=chapter_id,
                relationship_type="has",
                description=validate_optional_text(
                    relationship_data.get("description"),
                    "Item relationship description",
                ) or None,
                review_status=APPROVED_STATUS,
            )
            db.session.add(relationship)
            db.session.flush()
        else:
            relationship.item_id = item_id
            relationship.chapter_id = chapter_id
            relationship.relationship_type = "has"
            relationship.description = validate_optional_text(
                relationship_data.get("description"),
                "Item relationship description",
            ) or None

        relationship.admin_notes = validate_optional_text(
            relationship_data.get("admin_notes"),
            "Item relationship admin notes",
        ) or None
        relationship.review_status = APPROVED_STATUS

        evidence_text = (
            validate_optional_text(relationship_data.get("evidence_text"), "Item relationship evidence")
            or ""
        ).strip()
        evidence = WikiEvidence.query.filter_by(
            entity_type=EVIDENCE_ENTITY_TYPES["character_items"],
            entity_id=relationship.id,
        ).first()

        if evidence_text:
            if not evidence:
                evidence = WikiEvidence(
                    novel_id=character.novel_id,
                    entity_type=EVIDENCE_ENTITY_TYPES["character_items"],
                    entity_id=relationship.id,
                )
                db.session.add(evidence)

            evidence.chapter_id = chapter_id
            evidence.evidence_text = evidence_text
        elif evidence:
            db.session.delete(evidence)

    return None


def apply_skill_character_payload(skill, relationship_rows):
    validate_payload_rows(relationship_rows, "Skill character relationships")
    active_character_ids = set()

    for relationship_data in relationship_rows or []:
        if parse_boolean(relationship_data.get("_deleted"), "Skill character relationship deleted flag"):
            continue

        character_id = parse_optional_int(relationship_data.get("character_id"))
        if character_id:
            if character_id in active_character_ids:
                return "This character is already attached to this skill."

            active_character_ids.add(character_id)

    for relationship_data in relationship_rows or []:
        relationship_id = parse_optional_int(relationship_data.get("id"))
        should_delete = parse_boolean(
            relationship_data.get("_deleted"),
            "Skill character relationship deleted flag",
        )

        if relationship_id:
            relationship = CharacterSkill.query.filter_by(
                id=relationship_id,
                skill_id=skill.id,
            ).first()

            if not relationship:
                return "Character skill relationship does not belong to this skill."

            if should_delete:
                WikiEvidence.query.filter_by(
                    entity_type=EVIDENCE_ENTITY_TYPES["character_skills"],
                    entity_id=relationship.id,
                ).delete()
                db.session.delete(relationship)
                continue
        else:
            if should_delete:
                continue
            relationship = None

        character_id = parse_optional_int(relationship_data.get("character_id"))
        chapter_id = parse_optional_int(relationship_data.get("chapter_id"))

        if not character_id:
            return "Character is required."

        character = Character.query.filter_by(
            id=character_id,
            novel_id=skill.novel_id,
            review_status=APPROVED_STATUS,
        ).first()

        if not character:
            return "Character must be an approved character from this novel."

        if not chapter_id:
            return "Skill chapter is required."

        if not validate_chapter_for_novel(chapter_id, skill.novel_id):
            return "Skill chapter reference must belong to this novel."

        with db.session.no_autoflush:
            duplicate_query = CharacterSkill.query.filter_by(
                character_id=character_id,
                skill_id=skill.id,
            )

            if relationship_id:
                duplicate_query = duplicate_query.filter(CharacterSkill.id != relationship_id)

            if duplicate_query.first():
                return "This character is already attached to this skill."

        if relationship is None:
            relationship = CharacterSkill(
                novel_id=skill.novel_id,
                character_id=character_id,
                skill_id=skill.id,
                chapter_id=chapter_id,
                relationship_type="has",
                review_status=APPROVED_STATUS,
            )
            db.session.add(relationship)
            db.session.flush()

        relationship.character_id = character_id
        relationship.skill_id = skill.id
        relationship.chapter_id = chapter_id
        relationship.relationship_type = "has"
        relationship.description = validate_optional_text(
            relationship_data.get("description"),
            "Skill relationship description",
        ) or None
        relationship.admin_notes = validate_optional_text(
            relationship_data.get("admin_notes"),
            "Skill relationship admin notes",
        ) or None
        relationship.review_status = APPROVED_STATUS

        evidence_text = (
            validate_optional_text(relationship_data.get("evidence_text"), "Skill relationship evidence")
            or ""
        ).strip()
        evidence = WikiEvidence.query.filter_by(
            entity_type=EVIDENCE_ENTITY_TYPES["character_skills"],
            entity_id=relationship.id,
        ).first()

        if evidence_text:
            if not evidence:
                evidence = WikiEvidence(
                    novel_id=skill.novel_id,
                    entity_type=EVIDENCE_ENTITY_TYPES["character_skills"],
                    entity_id=relationship.id,
                )
                db.session.add(evidence)

            evidence.chapter_id = chapter_id
            evidence.evidence_text = evidence_text
        elif evidence:
            db.session.delete(evidence)

    return None


def apply_item_character_payload(item, relationship_rows):
    validate_payload_rows(relationship_rows, "Item character relationships")
    active_character_ids = set()

    for relationship_data in relationship_rows or []:
        if parse_boolean(relationship_data.get("_deleted"), "Item character relationship deleted flag"):
            continue

        character_id = parse_optional_int(relationship_data.get("character_id"))
        if character_id:
            if character_id in active_character_ids:
                return "This character is already attached to this item."

            active_character_ids.add(character_id)

    for relationship_data in relationship_rows or []:
        relationship_id = parse_optional_int(relationship_data.get("id"))
        should_delete = parse_boolean(
            relationship_data.get("_deleted"),
            "Item character relationship deleted flag",
        )

        if relationship_id:
            relationship = CharacterItem.query.filter_by(
                id=relationship_id,
                item_id=item.id,
            ).first()

            if not relationship:
                return "Character item relationship does not belong to this item."

            if should_delete:
                WikiEvidence.query.filter_by(
                    entity_type=EVIDENCE_ENTITY_TYPES["character_items"],
                    entity_id=relationship.id,
                ).delete()
                db.session.delete(relationship)
                continue
        else:
            if should_delete:
                continue
            relationship = None

        character_id = parse_optional_int(relationship_data.get("character_id"))
        chapter_id = parse_optional_int(relationship_data.get("chapter_id"))

        if not character_id:
            return "Character is required."

        character = Character.query.filter_by(
            id=character_id,
            novel_id=item.novel_id,
            review_status=APPROVED_STATUS,
        ).first()

        if not character:
            return "Character must be an approved character from this novel."

        if not chapter_id:
            return "Item chapter is required."

        if not validate_chapter_for_novel(chapter_id, item.novel_id):
            return "Item chapter reference must belong to this novel."

        with db.session.no_autoflush:
            duplicate_query = CharacterItem.query.filter_by(
                character_id=character_id,
                item_id=item.id,
            )

            if relationship_id:
                duplicate_query = duplicate_query.filter(CharacterItem.id != relationship_id)

            if duplicate_query.first():
                return "This character is already attached to this item."

        if relationship is None:
            relationship = CharacterItem(
                novel_id=item.novel_id,
                character_id=character_id,
                item_id=item.id,
                chapter_id=chapter_id,
                relationship_type="has",
                review_status=APPROVED_STATUS,
            )
            db.session.add(relationship)
            db.session.flush()

        relationship.character_id = character_id
        relationship.item_id = item.id
        relationship.chapter_id = chapter_id
        relationship.relationship_type = "has"
        relationship.description = validate_optional_text(
            relationship_data.get("description"),
            "Item relationship description",
        ) or None
        relationship.admin_notes = validate_optional_text(
            relationship_data.get("admin_notes"),
            "Item relationship admin notes",
        ) or None
        relationship.review_status = APPROVED_STATUS

        evidence_text = (
            validate_optional_text(relationship_data.get("evidence_text"), "Item relationship evidence")
            or ""
        ).strip()
        evidence = WikiEvidence.query.filter_by(
            entity_type=EVIDENCE_ENTITY_TYPES["character_items"],
            entity_id=relationship.id,
        ).first()

        if evidence_text:
            if not evidence:
                evidence = WikiEvidence(
                    novel_id=item.novel_id,
                    entity_type=EVIDENCE_ENTITY_TYPES["character_items"],
                    entity_id=relationship.id,
                )
                db.session.add(evidence)

            evidence.chapter_id = chapter_id
            evidence.evidence_text = evidence_text
        elif evidence:
            db.session.delete(evidence)

    return None
