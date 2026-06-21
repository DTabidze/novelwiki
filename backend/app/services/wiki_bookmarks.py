from sqlalchemy.exc import IntegrityError

from app.models import Character, Item, Novel, Skill, UserBookmark, db


APPROVED = "approved"


ENTITY_MODELS = {
    UserBookmark.ENTITY_NOVEL: Novel,
    UserBookmark.ENTITY_CHARACTER: Character,
    UserBookmark.ENTITY_SKILL: Skill,
    UserBookmark.ENTITY_ITEM: Item,
}


def normalize_entity_type(entity_type):
    return (entity_type or "").strip().lower()


def resolve_bookmark_target(entity_type, entity_id):
    entity_type = normalize_entity_type(entity_type)
    model = ENTITY_MODELS.get(entity_type)

    if not model:
        return entity_type, None

    query = model.query.filter_by(id=entity_id)

    if entity_type != UserBookmark.ENTITY_NOVEL:
        query = query.filter_by(review_status=APPROVED)

    return entity_type, query.first()


def bookmark_novel_id(entity_type, target):
    if entity_type == UserBookmark.ENTITY_NOVEL:
        return target.id

    return target.novel_id


def bookmarked_entity_keys(user_id):
    if not user_id:
        return set()

    rows = UserBookmark.query.with_entities(
        UserBookmark.entity_type,
        UserBookmark.entity_id,
    ).filter_by(user_id=user_id)
    return {(entity_type, entity_id) for entity_type, entity_id in rows}


def list_bookmarks(user_id):
    return (
        UserBookmark.query.filter_by(user_id=user_id)
        .order_by(UserBookmark.created_at.desc())
        .all()
    )


def get_bookmark(user_id, entity_type, entity_id):
    return UserBookmark.query.filter_by(
        user_id=user_id,
        entity_type=normalize_entity_type(entity_type),
        entity_id=entity_id,
    ).first()


def add_bookmark(user_id, entity_type, entity_id):
    entity_type, target = resolve_bookmark_target(entity_type, entity_id)

    if entity_type not in UserBookmark.ENTITY_TYPES:
        return None, False, "Unsupported bookmark type."

    if not target:
        return None, False, "Bookmark target not found."

    bookmark = get_bookmark(user_id, entity_type, entity_id)

    if bookmark:
        return bookmark, False, None

    bookmark = UserBookmark(
        user_id=user_id,
        novel_id=bookmark_novel_id(entity_type, target),
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.session.add(bookmark)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        bookmark = get_bookmark(user_id, entity_type, entity_id)
        return bookmark, False, None

    return bookmark, True, None


def remove_bookmark(user_id, entity_type, entity_id):
    bookmark = get_bookmark(user_id, entity_type, entity_id)

    if not bookmark:
        return False

    db.session.delete(bookmark)
    db.session.commit()
    return True
