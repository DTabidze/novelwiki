from flask import Blueprint, jsonify

from app.models import (
    Character,
    CharacterItem,
    CharacterLifeEvent,
    CharacterProgressionEvent,
    CharacterSkill,
    Chapter,
    Item,
    Novel,
    Skill,
    WikiEvidence,
    WikiEvent,
)


wiki_bp = Blueprint("wiki", __name__)

APPROVED = "approved"


def success(data, status=200):
    return jsonify({"data": data, "error": None}), status


def chapter_reference(chapter_id):
    if not chapter_id:
        return None

    chapter = Chapter.query.get(chapter_id)

    if not chapter:
        return None

    return chapter.to_reference_dict()


def evidence_for(entity_type, entity_id):
    evidence_rows = (
        WikiEvidence.query.filter_by(entity_type=entity_type, entity_id=entity_id)
        .order_by(WikiEvidence.id)
        .all()
    )

    return [
        {
            "id": evidence.id,
            "chapter": chapter_reference(evidence.chapter_id),
            "evidence_text": evidence.evidence_text,
        }
        for evidence in evidence_rows
    ]


def approved_progression_for_character(character_id):
    return (
        CharacterProgressionEvent.query.join(
            Chapter,
            CharacterProgressionEvent.chapter_id == Chapter.id,
        )
        .filter(
            CharacterProgressionEvent.character_id == character_id,
            CharacterProgressionEvent.review_status == APPROVED,
        )
        .order_by(Chapter.chapter_number, CharacterProgressionEvent.id)
        .all()
    )


def current_values_from_progression(character_id):
    current_values = {
        "current_cultivation_level": None,
        "current_position": None,
        "current_class_rank": None,
        "current_power_rank": None,
    }

    field_by_type = {
        "cultivation_level": "current_cultivation_level",
        "position": "current_position",
        "class_rank": "current_class_rank",
        "power_rank": "current_power_rank",
    }

    for progression in approved_progression_for_character(character_id):
        field = field_by_type.get(progression.progression_type)

        if field:
            current_values[field] = progression.new_value

    return current_values


def public_alias(alias):
    return {
        "id": alias.id,
        "alias": alias.alias,
        "first_seen_chapter": chapter_reference(alias.first_seen_chapter_id),
    }


def public_character_summary(character):
    return {
        "id": character.id,
        "novel_id": character.novel_id,
        "name": character.name,
        "description": character.description,
        "aliases": [public_alias(alias) for alias in character.aliases],
        "first_mentioned_chapter": chapter_reference(character.first_mentioned_chapter_id),
        "first_appeared_chapter": chapter_reference(character.first_appeared_chapter_id),
        **current_values_from_progression(character.id),
    }


def public_progression(progression):
    return {
        "id": progression.id,
        "character_id": progression.character_id,
        "character_name": progression.character.name if progression.character else None,
        "chapter": chapter_reference(progression.chapter_id),
        "progression_type": progression.progression_type,
        "old_value": progression.old_value,
        "new_value": progression.new_value,
        "description": progression.description,
        "evidence": evidence_for("progression", progression.id),
    }


def public_life_event(life_event):
    return {
        "id": life_event.id,
        "character_id": life_event.character_id,
        "character_name": life_event.character.name if life_event.character else None,
        "chapter": chapter_reference(life_event.chapter_id),
        "event_type": life_event.event_type,
        "description": life_event.description,
        "reason": life_event.reason,
        "evidence": evidence_for("life_event", life_event.id),
    }


def public_character_skill(relationship):
    return {
        "id": relationship.id,
        "character_id": relationship.character_id,
        "character_name": relationship.character.name if relationship.character else None,
        "skill_id": relationship.skill_id,
        "skill": public_skill(relationship.skill) if relationship.skill else None,
        "chapter": chapter_reference(relationship.chapter_id),
        "relationship_type": relationship.relationship_type,
        "description": relationship.description,
        "evidence": evidence_for("character_skill", relationship.id),
    }


def public_character_item(relationship):
    return {
        "id": relationship.id,
        "character_id": relationship.character_id,
        "character_name": relationship.character.name if relationship.character else None,
        "item_id": relationship.item_id,
        "item": public_item(relationship.item) if relationship.item else None,
        "chapter": chapter_reference(relationship.chapter_id),
        "relationship_type": relationship.relationship_type,
        "description": relationship.description,
        "evidence": evidence_for("character_item", relationship.id),
    }


def public_skill(skill):
    return {
        "id": skill.id,
        "novel_id": skill.novel_id,
        "name": skill.name,
        "category": skill.category,
        "description": skill.description,
        "aliases": [
            {
                "id": alias.id,
                "alias": alias.alias,
                "first_seen_chapter": chapter_reference(alias.first_seen_chapter_id),
            }
            for alias in skill.aliases
        ],
        "evidence": evidence_for("skill", skill.id),
    }


def public_item(item):
    return {
        "id": item.id,
        "novel_id": item.novel_id,
        "name": item.name,
        "category": item.category,
        "description": item.description,
        "evidence": evidence_for("item", item.id),
    }


def review_count(model, novel_id, status):
    return model.query.filter_by(novel_id=novel_id, review_status=status).count()


def public_novel(novel):
    approved_entry_count = sum(
        review_count(model, novel.id, APPROVED)
        for model in (
            Character,
            Skill,
            Item,
            CharacterProgressionEvent,
            CharacterSkill,
            CharacterItem,
            CharacterLifeEvent,
            WikiEvent,
        )
    )
    pending_review_count = sum(
        review_count(model, novel.id, "pending")
        for model in (
            Character,
            Skill,
            Item,
            CharacterProgressionEvent,
            CharacterSkill,
            CharacterItem,
            CharacterLifeEvent,
            WikiEvent,
        )
    )

    return {
        "id": novel.id,
        "title": novel.title,
        "chapter_count": len(novel.chapters),
        "approved_character_count": Character.query.filter_by(
            novel_id=novel.id,
            review_status=APPROVED,
        ).count(),
        "approved_skill_count": Skill.query.filter_by(
            novel_id=novel.id,
            review_status=APPROVED,
        ).count(),
        "approved_item_count": Item.query.filter_by(
            novel_id=novel.id,
            review_status=APPROVED,
        ).count(),
        "approved_progression_count": CharacterProgressionEvent.query.filter_by(
            novel_id=novel.id,
            review_status=APPROVED,
        ).count(),
        "approved_entry_count": approved_entry_count,
        "pending_review_count": pending_review_count,
        "updated_at": novel.updated_at.isoformat() if novel.updated_at else None,
    }


@wiki_bp.get("/novels")
def list_public_novels():
    novels = Novel.query.order_by(Novel.title).all()
    return success([public_novel(novel) for novel in novels])


@wiki_bp.get("/novels/<int:novel_id>")
def get_public_novel(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    return success(public_novel(novel))


@wiki_bp.get("/novels/<int:novel_id>/characters")
def list_public_characters(novel_id):
    Novel.query.get_or_404(novel_id)
    characters = (
        Character.query.filter_by(novel_id=novel_id, review_status=APPROVED)
        .order_by(Character.name)
        .all()
    )

    return success([public_character_summary(character) for character in characters])


@wiki_bp.get("/characters/<int:character_id>")
def get_public_character(character_id):
    character = Character.query.filter_by(
        id=character_id,
        review_status=APPROVED,
    ).first_or_404()
    progression_rows = approved_progression_for_character(character.id)
    character_skill_rows = (
        CharacterSkill.query.filter_by(
            character_id=character.id,
            review_status=APPROVED,
        )
        .order_by(CharacterSkill.id)
        .all()
    )
    character_item_rows = (
        CharacterItem.query.filter_by(
            character_id=character.id,
            review_status=APPROVED,
        )
        .order_by(CharacterItem.id)
        .all()
    )
    life_event_rows = (
        CharacterLifeEvent.query.filter_by(
            character_id=character.id,
            review_status=APPROVED,
        )
        .order_by(CharacterLifeEvent.id)
        .all()
    )

    data = public_character_summary(character)
    data["evidence"] = evidence_for("character", character.id)
    data["progression_events"] = [
        public_progression(progression) for progression in progression_rows
    ]
    data["skills"] = [
        public_character_skill(relationship) for relationship in character_skill_rows
    ]
    data["items"] = [
        public_character_item(relationship) for relationship in character_item_rows
    ]
    data["life_events"] = [public_life_event(life_event) for life_event in life_event_rows]

    return success(data)


@wiki_bp.get("/novels/<int:novel_id>/skills")
def list_public_skills(novel_id):
    Novel.query.get_or_404(novel_id)
    skills = (
        Skill.query.filter_by(novel_id=novel_id, review_status=APPROVED)
        .order_by(Skill.name)
        .all()
    )

    return success([public_skill(skill) for skill in skills])


@wiki_bp.get("/novels/<int:novel_id>/progression")
def list_public_progression(novel_id):
    Novel.query.get_or_404(novel_id)
    progression_rows = (
        CharacterProgressionEvent.query.join(
            Chapter,
            CharacterProgressionEvent.chapter_id == Chapter.id,
        )
        .filter(
            CharacterProgressionEvent.novel_id == novel_id,
            CharacterProgressionEvent.review_status == APPROVED,
        )
        .order_by(Chapter.chapter_number.desc(), CharacterProgressionEvent.id.desc())
        .all()
    )

    return success([public_progression(progression) for progression in progression_rows])


@wiki_bp.get("/skills/<int:skill_id>")
def get_public_skill(skill_id):
    skill = Skill.query.filter_by(
        id=skill_id,
        review_status=APPROVED,
    ).first_or_404()
    character_skill_rows = (
        CharacterSkill.query.filter_by(
            skill_id=skill.id,
            review_status=APPROVED,
        )
        .order_by(CharacterSkill.id)
        .all()
    )

    data = public_skill(skill)
    data["characters"] = [
        {
            "id": relationship.id,
            "character": public_character_summary(relationship.character)
            if relationship.character
            else None,
            "chapter": chapter_reference(relationship.chapter_id),
            "relationship_type": relationship.relationship_type,
            "description": relationship.description,
            "evidence": evidence_for("character_skill", relationship.id),
        }
        for relationship in character_skill_rows
    ]

    return success(data)


@wiki_bp.get("/novels/<int:novel_id>/items")
def list_public_items(novel_id):
    Novel.query.get_or_404(novel_id)
    items = (
        Item.query.filter_by(novel_id=novel_id, review_status=APPROVED)
        .order_by(Item.name)
        .all()
    )

    return success([public_item(item) for item in items])


@wiki_bp.get("/items/<int:item_id>")
def get_public_item(item_id):
    item = Item.query.filter_by(
        id=item_id,
        review_status=APPROVED,
    ).first_or_404()
    character_item_rows = (
        CharacterItem.query.filter_by(
            item_id=item.id,
            review_status=APPROVED,
        )
        .order_by(CharacterItem.id)
        .all()
    )

    data = public_item(item)
    data["characters"] = [
        {
            "id": relationship.id,
            "character": public_character_summary(relationship.character)
            if relationship.character
            else None,
            "chapter": chapter_reference(relationship.chapter_id),
            "relationship_type": relationship.relationship_type,
            "description": relationship.description,
            "evidence": evidence_for("character_item", relationship.id),
        }
        for relationship in character_item_rows
    ]

    return success(data)
