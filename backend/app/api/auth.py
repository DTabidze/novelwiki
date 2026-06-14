import hashlib
import secrets
from datetime import timedelta, timezone

from flask import Blueprint, jsonify, request, session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.models import Novel, NovelUserPermission, PasswordSetupToken, User, db, utc_now
from app.services.auth import (
    csrf_token,
    current_user,
    generate_csrf_token,
    login_required,
    superadmin_required,
)


auth_bp = Blueprint("auth", __name__)


def success(data, status=200):
    return jsonify({"data": data}), status


def failure(message, status=400):
    return jsonify({"error": message}), status


def request_payload():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return {}

    return payload


def normalize_text(value):
    if value is None:
        return ""

    return str(value).strip()


def normalize_email(value):
    return normalize_text(value).lower()


def parse_bool(value):
    return bool(value) if isinstance(value, bool) else False


def user_response(user):
    data = user.to_session_dict()
    data["csrf_token"] = csrf_token()
    return data


def validate_role(role):
    return role if role in User.ROLES else None


def hash_setup_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_password_setup_token(user):
    token = secrets.token_urlsafe(32)
    record = PasswordSetupToken(
        user_id=user.id,
        token_hash=hash_setup_token(token),
        expires_at=utc_now() + timedelta(hours=24),
    )
    db.session.add(record)
    return token


def password_setup_response(token):
    return {
        "setup_token": token,
        "setup_path": f"/set-password?token={token}",
        "expires_in_hours": 24,
    }


def find_valid_setup_token(token):
    if not token:
        return None

    record = PasswordSetupToken.query.filter_by(token_hash=hash_setup_token(token)).first()

    if not record or record.used_at:
        return None

    expires_at = record.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < utc_now():
        return None

    if not record.user or not record.user.is_active:
        return None

    return record


@auth_bp.get("/auth/csrf")
def get_csrf():
    return success({"csrf_token": csrf_token()})


@auth_bp.post("/auth/register")
def register():
    payload = request_payload()
    username = normalize_text(payload.get("username"))
    email = normalize_email(payload.get("email"))
    password = payload.get("password") or ""

    if not username:
        return failure("Username is required.")

    if not email:
        return failure("Email is required.")

    if len(password) < 8:
        return failure("Password must be at least 8 characters.")

    user = User(username=username, email=email, role=User.ROLE_USER)
    user.set_password(password)
    db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return failure("A user with this username or email already exists.")

    return success({"user": user.to_session_dict()}, status=201)


@auth_bp.post("/auth/login")
def login():
    payload = request_payload()
    email = normalize_email(payload.get("email"))
    password = payload.get("password") or ""

    if not email or not password:
        return failure("Email and password are required.")

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return failure("Invalid email or password.", status=401)

    if not user.is_active:
        return failure("This user account is inactive.", status=403)

    if user.must_set_password:
        return failure("Password setup is required before signing in.", status=403)

    session.clear()
    session["user_id"] = user.id
    generate_csrf_token()
    user.last_login_at = utc_now()
    db.session.commit()

    return success({"user": user_response(user)})


@auth_bp.post("/auth/logout")
@login_required
def logout():
    session.clear()
    return success({"ok": True})


@auth_bp.get("/auth/me")
def me():
    user = current_user()

    if not user:
        return success({"user": None, "csrf_token": csrf_token()})

    return success({"user": user_response(user)})


@auth_bp.get("/auth/password-setup")
def inspect_password_setup_token():
    token = normalize_text(request.args.get("token"))
    record = find_valid_setup_token(token)

    if not record:
        return failure("This password setup link is invalid or expired.", status=404)

    return success({
        "user": {
            "id": record.user.id,
            "username": record.user.username,
            "email": record.user.email,
        },
        "expires_at": record.expires_at.isoformat(),
    })


@auth_bp.post("/auth/set-password")
def set_password_with_token():
    payload = request_payload()
    token = normalize_text(payload.get("token"))
    password = payload.get("password") or ""
    confirm_password = payload.get("confirm_password") or ""
    record = find_valid_setup_token(token)

    if not record:
        return failure("This password setup link is invalid or expired.", status=404)

    if len(password) < 8:
        return failure("Password must be at least 8 characters.")

    if password != confirm_password:
        return failure("Passwords do not match.")

    record.user.set_password(password)
    record.used_at = utc_now()
    db.session.commit()

    return success({"ok": True})


@auth_bp.patch("/auth/me")
@login_required
def update_profile():
    user = current_user()
    payload = request_payload()

    if "username" in payload:
        username = normalize_text(payload.get("username"))

        if not username:
            return failure("Display name is required.")

        user.username = username

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return failure("A user with this display name already exists.")

    return success({"user": user_response(user)})


@auth_bp.post("/auth/me/password")
@login_required
def change_own_password():
    user = current_user()
    payload = request_payload()
    current_password = payload.get("current_password") or ""
    new_password = payload.get("new_password") or ""
    confirm_password = payload.get("confirm_password") or ""

    if not user.check_password(current_password):
        return failure("Current password is incorrect.", status=403)

    if len(new_password) < 8:
        return failure("New password must be at least 8 characters.")

    if new_password != confirm_password:
        return failure("Passwords do not match.")

    user.set_password(new_password)
    db.session.commit()

    return success({"ok": True})


@auth_bp.get("/admin/users")
@superadmin_required
def list_users():
    search = normalize_text(request.args.get("search")).lower()
    query = User.query

    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(User.username.ilike(pattern), User.email.ilike(pattern)))

    users = query.order_by(User.created_at.desc()).all()
    novels = Novel.query.order_by(Novel.title.asc()).all()

    return success({
        "users": [user.to_admin_dict() for user in users],
        "novels": [novel.to_admin_dict() for novel in novels],
    })


@auth_bp.post("/admin/users")
@superadmin_required
def create_user():
    payload = request_payload()
    username = normalize_text(payload.get("username"))
    email = normalize_email(payload.get("email"))
    role = validate_role(payload.get("role")) or User.ROLE_USER

    if not username:
        return failure("Username is required.")

    if not email:
        return failure("Email is required.")

    if role == User.ROLE_SUPERADMIN:
        return failure("Superadmins must be created with the bootstrap CLI.")

    user = User(
        username=username,
        email=email,
        role=role,
        is_active=parse_bool(payload.get("is_active", True)),
        must_set_password=True,
    )
    db.session.add(user)

    try:
        db.session.flush()
        setup_token = create_password_setup_token(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return failure("A user with this username or email already exists.")

    return success({
        "user": user.to_admin_dict(),
        "password_setup": password_setup_response(setup_token),
    }, status=201)


@auth_bp.patch("/admin/users/<int:user_id>")
@superadmin_required
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    actor = current_user()
    payload = request_payload()

    if "username" in payload:
        username = normalize_text(payload.get("username"))

        if not username:
            return failure("Username is required.")

        user.username = username

    if "email" in payload:
        email = normalize_email(payload.get("email"))

        if not email:
            return failure("Email is required.")

        user.email = email

    if "role" in payload:
        role = validate_role(payload.get("role"))

        if not role:
            return failure("Role must be superadmin, editor, or user.")

        if role == User.ROLE_SUPERADMIN and user.role != User.ROLE_SUPERADMIN:
            return failure("Superadmin promotion is not available from user management.")

        if actor and actor.id == user.id and role != User.ROLE_SUPERADMIN:
            return failure("You cannot remove your own superadmin role.", status=400)

        user.role = role

    if "is_active" in payload:
        if not isinstance(payload.get("is_active"), bool):
            return failure("Active status must be true or false.")

        if actor and actor.id == user.id and not payload["is_active"]:
            return failure("You cannot deactivate your own account.", status=400)

        user.is_active = payload["is_active"]

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return failure("A user with this username or email already exists.")

    return success({"user": user.to_admin_dict()})


@auth_bp.delete("/admin/users/<int:user_id>")
@superadmin_required
def deactivate_user(user_id):
    user = User.query.get_or_404(user_id)

    if current_user() and current_user().id == user.id:
        return failure("You cannot deactivate your own account.", status=400)

    user.is_active = False
    db.session.commit()
    return success({"user": user.to_admin_dict()})


@auth_bp.post("/admin/users/<int:user_id>/password-reset")
@superadmin_required
def generate_password_reset(user_id):
    user = User.query.get_or_404(user_id)

    if not user.is_active:
        return failure("Cannot generate a password reset link for an inactive user.", status=400)

    token = create_password_setup_token(user)
    user.must_set_password = True
    db.session.commit()

    return success({
        "user": user.to_admin_dict(),
        "password_setup": password_setup_response(token),
    })


@auth_bp.get("/admin/novels/<int:novel_id>/permissions")
@superadmin_required
def list_novel_permissions(novel_id):
    Novel.query.get_or_404(novel_id)
    permissions = NovelUserPermission.query.filter_by(novel_id=novel_id).order_by(
        NovelUserPermission.created_at.desc()
    ).all()
    return success({"permissions": [permission.to_admin_dict() for permission in permissions]})


@auth_bp.post("/admin/novels/<int:novel_id>/permissions")
@superadmin_required
def create_novel_permission(novel_id):
    Novel.query.get_or_404(novel_id)
    payload = request_payload()
    user_id = payload.get("user_id")
    user = User.query.get(user_id)

    if not user:
        return failure("User is required.")

    if user.role != User.ROLE_EDITOR:
        return failure("Only editors can receive novel-specific permissions.")

    permission = NovelUserPermission(
        novel_id=novel_id,
        user_id=user.id,
        can_edit=parse_bool(payload.get("can_edit")),
        can_review=parse_bool(payload.get("can_review")),
        can_approve=parse_bool(payload.get("can_approve")),
    )
    db.session.add(permission)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return failure("This user already has permissions for this novel.")

    return success({"permission": permission.to_admin_dict()}, status=201)


@auth_bp.patch("/admin/novels/<int:novel_id>/permissions/<int:permission_id>")
@superadmin_required
def update_novel_permission(novel_id, permission_id):
    permission = NovelUserPermission.query.filter_by(
        id=permission_id,
        novel_id=novel_id,
    ).first_or_404()
    payload = request_payload()

    if permission.user and permission.user.role != User.ROLE_EDITOR:
        return failure("Only editor permissions can be modified.")

    for field in ("can_edit", "can_review", "can_approve"):
        if field in payload:
            if not isinstance(payload.get(field), bool):
                return failure(f"{field} must be true or false.")

            setattr(permission, field, payload[field])

    db.session.commit()
    return success({"permission": permission.to_admin_dict()})


@auth_bp.delete("/admin/novels/<int:novel_id>/permissions/<int:permission_id>")
@superadmin_required
def delete_novel_permission(novel_id, permission_id):
    permission = NovelUserPermission.query.filter_by(
        id=permission_id,
        novel_id=novel_id,
    ).first_or_404()
    deleted_id = permission.id
    db.session.delete(permission)
    db.session.commit()
    return success({"deleted_permission_id": deleted_id})
