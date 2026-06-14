import re
import secrets
from functools import wraps

from flask import has_request_context, jsonify, request, session

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
    NovelUserPermission,
    Skill,
    SkillAlias,
    User,
    WikiEvent,
    db,
)


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def auth_error(message, status=403):
    return jsonify({"error": message}), status


def current_user():
    if not has_request_context():
        return None

    user_id = session.get("user_id")

    if not user_id:
        return None

    user = db.session.get(User, user_id)

    if not user or not user.is_active:
        session.clear()
        return None

    return user


def generate_csrf_token():
    token = secrets.token_urlsafe(32)
    session["csrf_token"] = token
    return token


def csrf_token():
    return session.get("csrf_token") or generate_csrf_token()


def validate_csrf():
    if request.method in SAFE_METHODS:
        return True

    expected_token = session.get("csrf_token")
    supplied_token = request.headers.get("X-CSRF-Token")

    return bool(expected_token and supplied_token and secrets.compare_digest(expected_token, supplied_token))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return auth_error("Authentication required.", 401)

        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()

        if not user:
            return auth_error("Authentication required.", 401)

        if not user.is_admin():
            return auth_error("Admin access required.", 403)

        return view(*args, **kwargs)

    return wrapped


def superadmin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()

        if not user:
            return auth_error("Authentication required.", 401)

        if user.role != User.ROLE_SUPERADMIN:
            return auth_error("Superadmin access required.", 403)

        return view(*args, **kwargs)

    return wrapped


def user_permission_for_novel(user, novel_id):
    if not user or user.role != User.ROLE_EDITOR:
        return None

    return NovelUserPermission.query.filter_by(user_id=user.id, novel_id=novel_id).first()


def user_can_access_novel(user, novel_id):
    if not user or not user.is_admin():
        return False

    if user.role == User.ROLE_SUPERADMIN:
        return True

    return user_permission_for_novel(user, novel_id) is not None


def user_can_edit_novel(user, novel_id):
    if not user or not user.is_admin():
        return False

    if user.role == User.ROLE_SUPERADMIN:
        return True

    permission = user_permission_for_novel(user, novel_id)
    return bool(permission and permission.can_edit)


def user_can_review_novel(user, novel_id):
    if not user or not user.is_admin():
        return False

    if user.role == User.ROLE_SUPERADMIN:
        return True

    permission = user_permission_for_novel(user, novel_id)
    return bool(permission and permission.can_review)


def user_can_approve_novel(user, novel_id):
    if not user or not user.is_admin():
        return False

    if user.role == User.ROLE_SUPERADMIN:
        return True

    permission = user_permission_for_novel(user, novel_id)
    return bool(permission and permission.can_approve)


def can_access_novel(novel_id):
    return user_can_access_novel(current_user(), novel_id)


def can_edit_novel(novel_id):
    return user_can_edit_novel(current_user(), novel_id)


def can_review_novel(novel_id):
    return user_can_review_novel(current_user(), novel_id)


def can_approve_novel(novel_id):
    return user_can_approve_novel(current_user(), novel_id)


def first_path_int(pattern):
    match = re.search(pattern, request.path)

    if not match:
        return None

    return int(match.group(1))


def review_record_novel_id(entity_type, entity_id):
    models = {
        "characters": Character,
        "skills": Skill,
        "items": Item,
        "events": WikiEvent,
        "progression_events": CharacterProgressionEvent,
        "character_metadata_proposals": CharacterMetadataProposal,
        "character_skills": CharacterSkill,
        "character_items": CharacterItem,
        "life_events": CharacterLifeEvent,
    }
    model = models.get(entity_type)

    if not model:
        return None

    record = model.query.get(entity_id)
    return record.novel_id if record else None


def wiki_data_record_novel_id(path):
    match = re.search(r"/wiki-data/(characters|skills|items)/(\d+)", path)

    if match:
        model = {"characters": Character, "skills": Skill, "items": Item}[match.group(1)]
        record = model.query.get(int(match.group(2)))
        return record.novel_id if record else None

    match = re.search(r"/wiki-data/character-aliases/(\d+)", path)

    if match:
        alias = CharacterAlias.query.get(int(match.group(1)))
        return alias.character.novel_id if alias and alias.character else None

    match = re.search(r"/wiki-data/skill-aliases/(\d+)", path)

    if match:
        alias = SkillAlias.query.get(int(match.group(1)))
        return alias.skill.novel_id if alias and alias.skill else None

    match = re.search(r"/wiki-data/characters/(\d+)/aliases", path)

    if match:
        character = Character.query.get(int(match.group(1)))
        return character.novel_id if character else None

    return None


def novel_id_from_path():
    return first_path_int(r"/novels/(\d+)")


def install_auth_guards(app):
    @app.before_request
    def enforce_authentication():
        if request.method == "OPTIONS":
            return None

        if not request.path.startswith("/api/admin"):
            return None

        user = current_user()

        if not user:
            return auth_error("Authentication required.", 401)

        if not user.is_admin():
            return auth_error("Admin access required.", 403)

        if not app.config.get("TESTING") and request.method not in SAFE_METHODS and not validate_csrf():
            return auth_error("CSRF token is missing or invalid.", 400)

        if request.path.startswith("/api/admin/users"):
            if user.role != User.ROLE_SUPERADMIN:
                return auth_error("Superadmin access required.", 403)
            return None

        if request.path == "/api/admin/novels" and request.method in {"POST", "PATCH", "DELETE"}:
            if user.role != User.ROLE_SUPERADMIN:
                return auth_error("Superadmin access required.", 403)
            return None

        if request.path == "/api/admin/novels/upload":
            if user.role != User.ROLE_SUPERADMIN:
                return auth_error("Superadmin access required.", 403)
            return None

        novel_id = novel_id_from_path()

        if request.path.startswith("/api/admin/review/wiki-data/novels/"):
            novel_id = novel_id_from_path()
            if novel_id and not user_can_access_novel(user, novel_id):
                return auth_error("You do not have access to this novel.", 403)
            return None

        match = re.search(r"/api/admin/review/chapters/(\d+)/context", request.path)

        if match:
            chapter = db.session.get(Chapter, int(match.group(1)))

            if chapter and not user_can_access_novel(user, chapter.novel_id):
                return auth_error("You do not have access to this novel.", 403)

            return None

        if request.path.startswith("/api/admin/review/wiki-data/"):
            novel_id = wiki_data_record_novel_id(request.path)
            if novel_id and not user_can_edit_novel(user, novel_id):
                return auth_error("You do not have edit access to this novel.", 403)
            return None

        match = re.search(r"/api/admin/review/([^/]+)/(\d+)", request.path)

        if match:
            entity_type = match.group(1)
            entity_id = int(match.group(2))
            novel_id = review_record_novel_id(entity_type, entity_id)

            if novel_id:
                if request.path.endswith("/convert") and not user_can_review_novel(user, novel_id):
                    return auth_error("You do not have review access to this novel.", 403)

                if request.method in {"POST", "PATCH", "DELETE"}:
                    payload = request.get_json(silent=True) or {}
                    wants_approval = payload.get("review_status") == "approved"

                    if wants_approval and not user_can_approve_novel(user, novel_id):
                        return auth_error("You do not have approve access to this novel.", 403)

                    if not wants_approval and not user_can_review_novel(user, novel_id):
                        return auth_error("You do not have review access to this novel.", 403)

            return None

        if novel_id:
            if request.method in SAFE_METHODS:
                allowed = user_can_access_novel(user, novel_id)
            else:
                allowed = user_can_edit_novel(user, novel_id) or user_can_review_novel(user, novel_id)

            if not allowed:
                return auth_error("You do not have access to this novel.", 403)

        return None
