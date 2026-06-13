from app.models import CharacterItem, CharacterSkill, WikiEvidence, db
from app.services.item_categories import normalize_item_category
from app.services.skill_categories import normalize_skill_category
from app.services.wiki_editor_payloads import validate_optional_text

APPROVED_STATUS = "approved"
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
