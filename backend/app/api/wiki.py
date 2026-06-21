from flask import Blueprint, jsonify, request
from sqlalchemy import func

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
    UserBookmark,
    WikiEditLog,
    WikiEvidence,
    WikiEvent,
    db,
    serialize_datetime,
)
from app.services.auth import current_user, login_required
from app.services.wiki_bookmarks import (
    add_bookmark,
    bookmarked_entity_keys,
    list_bookmarks,
    remove_bookmark,
)


wiki_bp = Blueprint("wiki", __name__)

APPROVED = "approved"


def success(data, status=200):
    return jsonify({"data": data, "error": None}), status


def failure(message, status=400):
    return jsonify({"data": None, "error": message}), status


def chapter_numbers_for_ids(chapter_ids):
    ids = [chapter_id for chapter_id in chapter_ids if chapter_id]

    if not ids:
        return []

    return [
        chapter.chapter_number
        for chapter in Chapter.query.filter(Chapter.id.in_(ids)).all()
        if chapter.chapter_number is not None
    ]


def wiki_coverage_for_novel(novel_id):
    chapter_numbers = []

    approved_characters = Character.query.filter_by(
        novel_id=novel_id,
        review_status=APPROVED,
    ).all()
    for character in approved_characters:
        chapter_numbers.extend(
            chapter_numbers_for_ids(
                [
                    character.first_mentioned_chapter_id,
                    character.first_appeared_chapter_id,
                    character.first_seen_chapter_id,
                ]
            )
        )

    approved_chapter_models = (
        CharacterProgressionEvent,
        CharacterSkill,
        CharacterItem,
        CharacterLifeEvent,
        WikiEvent,
    )
    for model in approved_chapter_models:
        rows = (
            db.session.query(Chapter.chapter_number)
            .join(model, model.chapter_id == Chapter.id)
            .filter(model.novel_id == novel_id, model.review_status == APPROVED)
            .all()
        )
        chapter_numbers.extend(number for (number,) in rows if number is not None)

    evidence_rows = (
        db.session.query(Chapter.chapter_number)
        .join(WikiEvidence, WikiEvidence.chapter_id == Chapter.id)
        .filter(WikiEvidence.novel_id == novel_id)
        .all()
    )
    chapter_numbers.extend(number for (number,) in evidence_rows if number is not None)

    if not chapter_numbers:
        return {
            "start_chapter": None,
            "end_chapter": None,
        }

    return {
        "start_chapter": min(chapter_numbers),
        "end_chapter": max(chapter_numbers),
    }


def last_wiki_update_for_novel(novel):
    edit_log_time = (
        db.session.query(func.max(WikiEditLog.created_at))
        .filter(WikiEditLog.novel_id == novel.id)
        .scalar()
    )

    return edit_log_time or novel.updated_at


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


def public_character_summary(character, bookmarked_keys=None):
    bookmarked_keys = bookmarked_keys or set()
    return {
        "id": character.id,
        "novel_id": character.novel_id,
        "name": character.name,
        "description": character.description,
        "aliases": [public_alias(alias) for alias in character.aliases],
        "age_text": character.age_text,
        "gender": character.gender,
        "race_or_species": character.race_or_species,
        "race_or_species_source": character.race_or_species_source,
        "race_or_species_confidence": character.race_or_species_confidence,
        "origin": character.origin,
        "faction_or_affiliation": character.faction_or_affiliation,
        "status": character.status,
        "titles": character.titles,
        "first_mentioned_chapter": chapter_reference(character.first_mentioned_chapter_id),
        "first_appeared_chapter": chapter_reference(character.first_appeared_chapter_id),
        "is_bookmarked": (UserBookmark.ENTITY_CHARACTER, character.id) in bookmarked_keys,
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


def public_character_skill(relationship, bookmarked_keys=None):
    return {
        "id": relationship.id,
        "character_id": relationship.character_id,
        "character_name": relationship.character.name if relationship.character else None,
        "skill_id": relationship.skill_id,
        "skill": public_skill(relationship.skill, bookmarked_keys) if relationship.skill else None,
        "chapter": chapter_reference(relationship.chapter_id),
        "description": relationship.description,
        "evidence": evidence_for("character_skill", relationship.id),
    }


def public_character_item(relationship, bookmarked_keys=None):
    return {
        "id": relationship.id,
        "character_id": relationship.character_id,
        "character_name": relationship.character.name if relationship.character else None,
        "item_id": relationship.item_id,
        "item": public_item(relationship.item, bookmarked_keys) if relationship.item else None,
        "chapter": chapter_reference(relationship.chapter_id),
        "relationship_type": relationship.relationship_type,
        "description": relationship.description,
        "evidence": evidence_for("character_item", relationship.id),
    }


def public_skill(skill, bookmarked_keys=None):
    bookmarked_keys = bookmarked_keys or set()
    character_rows = (
        CharacterSkill.query.filter_by(
            skill_id=skill.id,
            review_status=APPROVED,
        )
        .order_by(CharacterSkill.id)
        .all()
    )

    return {
        "id": skill.id,
        "novel_id": skill.novel_id,
        "name": skill.name,
        "category": skill.category,
        "description": skill.description,
        "is_bookmarked": (UserBookmark.ENTITY_SKILL, skill.id) in bookmarked_keys,
        "aliases": [
            {
                "id": alias.id,
                "alias": alias.alias,
                "first_seen_chapter": chapter_reference(alias.first_seen_chapter_id),
            }
            for alias in skill.aliases
        ],
        "evidence": evidence_for("skill", skill.id),
        "characters": [
            {
                "id": relationship.id,
                "character_id": relationship.character_id,
                "character_name": relationship.character.name if relationship.character else None,
                "chapter": chapter_reference(relationship.chapter_id),
                "description": relationship.description,
            }
            for relationship in character_rows
        ],
    }


def public_item(item, bookmarked_keys=None):
    bookmarked_keys = bookmarked_keys or set()
    character_rows = (
        CharacterItem.query.filter_by(
            item_id=item.id,
            review_status=APPROVED,
        )
        .order_by(CharacterItem.id)
        .all()
    )

    return {
        "id": item.id,
        "novel_id": item.novel_id,
        "name": item.name,
        "category": item.category,
        "description": item.description,
        "is_bookmarked": (UserBookmark.ENTITY_ITEM, item.id) in bookmarked_keys,
        "evidence": evidence_for("item", item.id),
        "characters": [
            {
                "id": relationship.id,
                "character_id": relationship.character_id,
                "character_name": relationship.character.name if relationship.character else None,
                "chapter": chapter_reference(relationship.chapter_id),
                "relationship_type": relationship.relationship_type,
                "description": relationship.description,
            }
            for relationship in character_rows
        ],
    }


def review_count(model, novel_id, status):
    return model.query.filter_by(novel_id=novel_id, review_status=status).count()


def public_novel(novel, bookmarked_keys=None):
    bookmarked_keys = bookmarked_keys or set()
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
    coverage = wiki_coverage_for_novel(novel.id)
    last_wiki_update = last_wiki_update_for_novel(novel)

    return {
        "id": novel.id,
        "title": novel.title,
        "author": novel.author,
        "description": novel.description,
        "cover_image_url": novel.cover_image_url,
        "status": novel.status,
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
        "wiki_coverage_start_chapter": coverage["start_chapter"],
        "wiki_coverage_end_chapter": coverage["end_chapter"],
        "is_bookmarked": (UserBookmark.ENTITY_NOVEL, novel.id) in bookmarked_keys,
        "last_wiki_updated_at": serialize_datetime(last_wiki_update),
        "updated_at": novel.updated_at.isoformat() if novel.updated_at else None,
    }


@wiki_bp.get("/novels")
def list_public_novels():
    novels = Novel.query.order_by(Novel.title).all()
    user = current_user()
    bookmarked_keys = bookmarked_entity_keys(user.id) if user else set()
    return success([public_novel(novel, bookmarked_keys) for novel in novels])


@wiki_bp.get("/novels/<int:novel_id>")
def get_public_novel(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    user = current_user()
    bookmarked_keys = bookmarked_entity_keys(user.id) if user else set()
    return success(public_novel(novel, bookmarked_keys))


def public_bookmark_entity(bookmark, bookmarked_keys):
    if bookmark.entity_type == UserBookmark.ENTITY_NOVEL:
        novel = db.session.get(Novel, bookmark.entity_id)
        return public_novel(novel, bookmarked_keys) if novel else None

    if bookmark.entity_type == UserBookmark.ENTITY_CHARACTER:
        character = Character.query.filter_by(
            id=bookmark.entity_id,
            review_status=APPROVED,
        ).first()
        return public_character_summary(character, bookmarked_keys) if character else None

    if bookmark.entity_type == UserBookmark.ENTITY_SKILL:
        skill = Skill.query.filter_by(
            id=bookmark.entity_id,
            review_status=APPROVED,
        ).first()
        return public_skill(skill, bookmarked_keys) if skill else None

    if bookmark.entity_type == UserBookmark.ENTITY_ITEM:
        item = Item.query.filter_by(
            id=bookmark.entity_id,
            review_status=APPROVED,
        ).first()
        return public_item(item, bookmarked_keys) if item else None

    return None


def public_bookmark_novel(bookmark):
    novel = db.session.get(Novel, bookmark.novel_id)

    if not novel:
        return None

    return {
        "id": novel.id,
        "title": novel.title,
    }


def public_bookmark(bookmark, bookmarked_keys, created=None):
    data = {
        "id": bookmark.id,
        "novel_id": bookmark.novel_id,
        "novel": public_bookmark_novel(bookmark),
        "entity_type": bookmark.entity_type,
        "entity_id": bookmark.entity_id,
        "created_at": serialize_datetime(bookmark.created_at),
        "entity": public_bookmark_entity(bookmark, bookmarked_keys),
    }

    if created is not None:
        data["created"] = created

    return data


@wiki_bp.get("/me/bookmarks")
@login_required
def list_my_bookmarks():
    user = current_user()
    bookmarked_keys = bookmarked_entity_keys(user.id)
    bookmarks = list_bookmarks(user.id)
    return success([public_bookmark(bookmark, bookmarked_keys) for bookmark in bookmarks])


@wiki_bp.post("/me/bookmarks")
@login_required
def create_my_bookmark_from_payload():
    payload = request.get_json(silent=True) or {}
    entity_type = payload.get("entity_type")
    entity_id = payload.get("entity_id")

    try:
        entity_id = int(entity_id)
    except (TypeError, ValueError):
        return failure("Bookmark target is required.", status=400)

    return create_my_bookmark_for_entity(entity_type, entity_id)


@wiki_bp.post("/me/bookmarks/<entity_type>/<int:entity_id>")
@login_required
def create_my_bookmark_for_entity(entity_type, entity_id):
    user = current_user()
    bookmark, created, error = add_bookmark(user.id, entity_type, entity_id)

    if not bookmark:
        status = 400 if error == "Unsupported bookmark type." else 404
        return failure(error, status=status)

    bookmarked_keys = bookmarked_entity_keys(user.id)

    return success(
        public_bookmark(bookmark, bookmarked_keys, created=created),
        status=201 if created else 200,
    )


@wiki_bp.post("/me/bookmarks/<int:novel_id>")
@login_required
def create_my_novel_bookmark(novel_id):
    return create_my_bookmark_for_entity(UserBookmark.ENTITY_NOVEL, novel_id)


@wiki_bp.delete("/me/bookmarks/<entity_type>/<int:entity_id>")
@login_required
def delete_my_bookmark(entity_type, entity_id):
    removed = remove_bookmark(current_user().id, entity_type, entity_id)

    if not removed:
        return failure("Bookmark not found.", status=404)

    return success({"ok": True, "entity_type": entity_type, "entity_id": entity_id})


@wiki_bp.delete("/me/bookmarks/<int:novel_id>")
@login_required
def delete_my_novel_bookmark(novel_id):
    return delete_my_bookmark(UserBookmark.ENTITY_NOVEL, novel_id)


@wiki_bp.get("/novels/<int:novel_id>/characters")
def list_public_characters(novel_id):
    Novel.query.get_or_404(novel_id)
    characters = (
        Character.query.filter_by(novel_id=novel_id, review_status=APPROVED)
        .order_by(Character.name)
        .all()
    )
    user = current_user()
    bookmarked_keys = bookmarked_entity_keys(user.id) if user else set()

    return success([public_character_summary(character, bookmarked_keys) for character in characters])


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

    user = current_user()
    bookmarked_keys = bookmarked_entity_keys(user.id) if user else set()

    data = public_character_summary(character, bookmarked_keys)
    data["evidence"] = evidence_for("character", character.id)
    data["progression_events"] = [
        public_progression(progression) for progression in progression_rows
    ]
    data["skills"] = [
        public_character_skill(relationship, bookmarked_keys) for relationship in character_skill_rows
    ]
    data["items"] = [
        public_character_item(relationship, bookmarked_keys) for relationship in character_item_rows
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
    user = current_user()
    bookmarked_keys = bookmarked_entity_keys(user.id) if user else set()

    return success([public_skill(skill, bookmarked_keys) for skill in skills])


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

    user = current_user()
    bookmarked_keys = bookmarked_entity_keys(user.id) if user else set()

    data = public_skill(skill, bookmarked_keys)
    data["characters"] = [
        {
            "id": relationship.id,
            "character": public_character_summary(relationship.character, bookmarked_keys)
            if relationship.character
            else None,
            "chapter": chapter_reference(relationship.chapter_id),
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
    user = current_user()
    bookmarked_keys = bookmarked_entity_keys(user.id) if user else set()

    return success([public_item(item, bookmarked_keys) for item in items])


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

    user = current_user()
    bookmarked_keys = bookmarked_entity_keys(user.id) if user else set()

    data = public_item(item, bookmarked_keys)
    data["characters"] = [
        {
            "id": relationship.id,
            "character": public_character_summary(relationship.character, bookmarked_keys)
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
