import json
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


def utc_now():
    return datetime.now(timezone.utc)


def serialize_datetime(value):
    if not value:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)

    return value.isoformat().replace("+00:00", "Z")


class ReviewMixin:
    review_status = db.Column(db.String(50), nullable=False, default="pending")
    admin_notes = db.Column(db.Text, nullable=True)
    review_version = db.Column(db.Integer, nullable=False, default=0)
    last_reviewed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    last_review_action = db.Column(db.String(50), nullable=True)
    last_reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def review_dict(self):
        last_reviewed_by = None

        if self.last_reviewed_by_user_id:
            user = db.session.get(User, self.last_reviewed_by_user_id)
            last_reviewed_by = user.username if user else None

        return {
            "review_status": self.review_status,
            "admin_notes": self.admin_notes,
            "review_version": self.review_version or 0,
            "last_reviewed_by_user_id": self.last_reviewed_by_user_id,
            "last_reviewed_by": last_reviewed_by,
            "last_review_action": self.last_review_action,
            "last_reviewed_at": serialize_datetime(self.last_reviewed_at),
        }


class Novel(db.Model):
    __tablename__ = "novels"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    cover_image_url = db.Column(db.Text, nullable=True)
    original_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(20), nullable=False, default="txt")
    status = db.Column(db.String(50), nullable=False, default="ready")
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    chapters = db.relationship(
        "Chapter",
        back_populates="novel",
        cascade="all, delete-orphan",
        order_by="Chapter.chapter_number",
    )
    books = db.relationship(
        "Book",
        back_populates="novel",
        cascade="all, delete-orphan",
        order_by="Book.number",
    )

    def to_admin_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "description": self.description,
            "cover_image_url": self.cover_image_url,
            "original_filename": self.original_filename,
            "file_type": self.file_type,
            "status": self.status,
            "error_message": self.error_message,
            "book_count": len(self.books),
            "chapter_count": len(self.chapters),
            "created_at": serialize_datetime(self.created_at),
            "updated_at": serialize_datetime(self.updated_at),
        }


class User(db.Model):
    __tablename__ = "users"

    ROLE_SUPERADMIN = "superadmin"
    ROLE_EDITOR = "editor"
    ROLE_USER = "user"
    ROLES = {ROLE_SUPERADMIN, ROLE_EDITOR, ROLE_USER}

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(50), nullable=False, default=ROLE_USER)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    must_set_password = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    permissions = db.relationship(
        "NovelUserPermission",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="NovelUserPermission.novel_id",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        self.must_set_password = False

    def check_password(self, password):
        if not self.password_hash:
            return False

        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role in {self.ROLE_SUPERADMIN, self.ROLE_EDITOR}

    def to_session_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "must_set_password": self.must_set_password,
            "permissions": [permission.to_admin_dict() for permission in self.permissions],
            "last_login_at": serialize_datetime(self.last_login_at),
        }

    def to_admin_dict(self):
        return {
            **self.to_session_dict(),
            "created_at": serialize_datetime(self.created_at),
            "updated_at": serialize_datetime(self.updated_at),
        }


class NovelUserPermission(db.Model):
    __tablename__ = "novel_user_permissions"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novels.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    can_edit = db.Column(db.Boolean, nullable=False, default=False)
    can_review = db.Column(db.Boolean, nullable=False, default=False)
    can_approve = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    user = db.relationship("User", back_populates="permissions")
    novel = db.relationship("Novel")

    __table_args__ = (
        db.UniqueConstraint("novel_id", "user_id", name="uq_novel_user_permission"),
    )

    def to_admin_dict(self):
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "novel_title": self.novel.title if self.novel else None,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "can_edit": self.can_edit,
            "can_review": self.can_review,
            "can_approve": self.can_approve,
            "created_at": serialize_datetime(self.created_at),
            "updated_at": serialize_datetime(self.updated_at),
        }


class PasswordSetupToken(db.Model):
    __tablename__ = "password_setup_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token_hash = db.Column(db.String(128), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    user = db.relationship("User")


class Book(db.Model):
    __tablename__ = "books"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novels.id"), nullable=False)
    number = db.Column(db.Integer, nullable=False, default=1)
    title = db.Column(db.String(255), nullable=False)
    source_filename = db.Column(db.String(255), nullable=True)
    parsing_status = db.Column(db.String(50), nullable=False, default="parsed")
    extraction_status = db.Column(db.String(50), nullable=False, default="not_started")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    uploaded_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    novel = db.relationship("Novel", back_populates="books")
    chapters = db.relationship(
        "Chapter",
        back_populates="book",
        cascade="all, delete-orphan",
        order_by="Chapter.chapter_number",
    )

    __table_args__ = (
        db.UniqueConstraint("novel_id", "number", name="uq_book_number"),
    )

    def to_admin_dict(self):
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "number": self.number,
            "title": self.title,
            "source_filename": self.source_filename,
            "parsing_status": self.parsing_status,
            "extraction_status": self.extraction_status,
            "chapter_count": len(self.chapters),
            "created_at": serialize_datetime(self.created_at),
            "uploaded_at": serialize_datetime(self.uploaded_at),
        }


class Chapter(db.Model):
    __tablename__ = "chapters"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novels.id"), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=True)
    chapter_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    character_count = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    novel = db.relationship("Novel", back_populates="chapters")
    book = db.relationship("Book", back_populates="chapters")

    __table_args__ = (
        db.UniqueConstraint("book_id", "chapter_number", name="uq_book_chapter_order"),
    )

    def to_admin_verification_dict(self):
        preview = " ".join(self.content.split())[:200]
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "book_id": self.book_id,
            "book": self.book.to_admin_dict() if self.book else None,
            "chapter_number": self.chapter_number,
            "title": self.title,
            "character_count": self.character_count,
            "preview": preview,
        }

    def to_reference_dict(self):
        return {
            "id": self.id,
            "book_id": self.book_id,
            "chapter_number": self.chapter_number,
            "title": self.title,
        }


class ExtractionRun(db.Model):
    __tablename__ = "extraction_runs"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novels.id"), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=True)
    chapter_start = db.Column(db.Integer, nullable=True)
    chapter_end = db.Column(db.Integer, nullable=True)
    scope_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="queued")
    total_chapters = db.Column(db.Integer, nullable=False, default=0)
    completed_chapters = db.Column(db.Integer, nullable=False, default=0)
    failed_chapters = db.Column(db.Integer, nullable=False, default=0)
    current_chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=True)
    created_records_count = db.Column(db.Integer, nullable=False, default=0)
    warning_count = db.Column(db.Integer, nullable=False, default=0)
    summary_json = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    novel = db.relationship("Novel")
    book = db.relationship("Book")
    current_chapter = db.relationship("Chapter")
    run_chapters = db.relationship(
        "ExtractionRunChapter",
        back_populates="extraction_run",
        cascade="all, delete-orphan",
        order_by="ExtractionRunChapter.id",
    )

    def to_admin_dict(self):
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "book_id": self.book_id,
            "book": self.book.to_admin_dict() if self.book else None,
            "chapter_start": self.chapter_start,
            "chapter_end": self.chapter_end,
            "scope_type": self.scope_type,
            "status": self.status,
            "total_chapters": self.total_chapters,
            "completed_chapters": self.completed_chapters,
            "failed_chapters": self.failed_chapters,
            "current_chapter_id": self.current_chapter_id,
            "current_chapter": self.current_chapter.to_reference_dict() if self.current_chapter else None,
            "created_records_count": self.created_records_count,
            "warning_count": self.warning_count,
            "summary": json.loads(self.summary_json) if self.summary_json else {},
            "run_chapters": [run_chapter.to_admin_dict() for run_chapter in self.run_chapters],
            "error_message": self.error_message,
            "started_at": serialize_datetime(self.started_at),
            "finished_at": serialize_datetime(self.finished_at),
            "created_at": serialize_datetime(self.created_at),
        }


class ExtractionRunChapter(db.Model):
    __tablename__ = "extraction_run_chapters"

    id = db.Column(db.Integer, primary_key=True)
    extraction_run_id = db.Column(db.Integer, db.ForeignKey("extraction_runs.id"), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="pending")
    records_created = db.Column(db.Integer, nullable=False, default=0)
    warning_count = db.Column(db.Integer, nullable=False, default=0)
    summary_json = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    extraction_run = db.relationship("ExtractionRun", back_populates="run_chapters")
    chapter = db.relationship("Chapter")

    __table_args__ = (
        db.UniqueConstraint("extraction_run_id", "chapter_id", name="uq_run_chapter"),
    )

    def to_admin_dict(self):
        return {
            "id": self.id,
            "extraction_run_id": self.extraction_run_id,
            "chapter_id": self.chapter_id,
            "chapter": self.chapter.to_reference_dict() if self.chapter else None,
            "status": self.status,
            "records_created": self.records_created,
            "warning_count": self.warning_count,
            "summary": json.loads(self.summary_json) if self.summary_json else {},
            "error_message": self.error_message,
            "started_at": serialize_datetime(self.started_at),
            "finished_at": serialize_datetime(self.finished_at),
            "created_at": serialize_datetime(self.created_at),
            "updated_at": serialize_datetime(self.updated_at),
        }


class Character(ReviewMixin, db.Model):
    __tablename__ = "characters"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novels.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    first_mentioned_chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=True)
    first_appeared_chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=True)
    first_seen_chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=True)
    age_text = db.Column(db.String(255), nullable=True)
    gender = db.Column(db.String(255), nullable=True)
    race_or_species = db.Column(db.String(255), nullable=True)
    race_or_species_source = db.Column(db.String(50), nullable=True)
    race_or_species_confidence = db.Column(db.String(50), nullable=True)
    origin = db.Column(db.String(255), nullable=True)
    faction_or_affiliation = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(255), nullable=True, default="unknown")
    titles = db.Column(db.Text, nullable=True)
    current_cultivation_level = db.Column(db.String(255), nullable=True)
    current_position = db.Column(db.String(255), nullable=True)
    current_class_rank = db.Column(db.String(255), nullable=True)
    current_power_rank = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    aliases = db.relationship(
        "CharacterAlias",
        back_populates="character",
        cascade="all, delete-orphan",
        order_by="CharacterAlias.alias",
    )

    def to_admin_dict(self):
        source_chapter_id = (
            self.first_appeared_chapter_id
            or self.first_mentioned_chapter_id
            or self.first_seen_chapter_id
        )

        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "name": self.name,
            "description": self.description,
            "first_mentioned_chapter_id": self.first_mentioned_chapter_id,
            "first_appeared_chapter_id": self.first_appeared_chapter_id,
            "first_seen_chapter_id": self.first_seen_chapter_id,
            "age_text": self.age_text,
            "gender": self.gender,
            "race_or_species": self.race_or_species,
            "race_or_species_source": self.race_or_species_source,
            "race_or_species_confidence": self.race_or_species_confidence,
            "origin": self.origin,
            "faction_or_affiliation": self.faction_or_affiliation,
            "status": self.status,
            "titles": self.titles,
            "current_cultivation_level": self.current_cultivation_level,
            "current_position": self.current_position,
            "current_class_rank": self.current_class_rank,
            "current_power_rank": self.current_power_rank,
            "source_chapter_id": source_chapter_id,
            "aliases": [alias.to_admin_dict() for alias in self.aliases],
            **self.review_dict(),
        }


class CharacterAlias(db.Model):
    __tablename__ = "character_aliases"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey("characters.id"), nullable=False)
    alias = db.Column(db.String(255), nullable=False)
    first_seen_chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=True)
    evidence = db.Column(db.Text, nullable=True)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    character = db.relationship("Character", back_populates="aliases")

    __table_args__ = (
        db.UniqueConstraint("character_id", "alias", name="uq_character_alias"),
    )

    def to_admin_dict(self):
        return {
            "id": self.id,
            "character_id": self.character_id,
            "alias": self.alias,
            "first_seen_chapter_id": self.first_seen_chapter_id,
            "evidence": self.evidence,
            "is_primary": self.is_primary,
        }


class CharacterMetadataProposal(ReviewMixin, db.Model):
    __tablename__ = "character_metadata_proposals"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novels.id"), nullable=False)
    character_id = db.Column(db.Integer, db.ForeignKey("characters.id"), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=False)
    field_name = db.Column(db.String(100), nullable=False)
    old_value = db.Column(db.Text, nullable=True)
    raw_proposed_value = db.Column(db.Text, nullable=True)
    proposed_value = db.Column(db.Text, nullable=False)
    normalized_value = db.Column(db.Text, nullable=True)
    confidence_score = db.Column(db.Float, nullable=True)
    extraction_reason = db.Column(db.Text, nullable=True)
    auto_approved = db.Column(db.Boolean, nullable=False, default=False)
    evidence = db.Column(db.Text, nullable=True)
    review_warnings = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    character = db.relationship("Character")

    def to_admin_dict(self):
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "character_id": self.character_id,
            "character_name": self.character.name if self.character else None,
            "chapter_id": self.chapter_id,
            "source_chapter_id": self.chapter_id,
            "field_name": self.field_name,
            "old_value": self.old_value,
            "raw_proposed_value": self.raw_proposed_value,
            "proposed_value": self.proposed_value,
            "normalized_value": self.normalized_value,
            "confidence_score": self.confidence_score,
            "extraction_reason": self.extraction_reason,
            "auto_approved": self.auto_approved,
            "evidence_text": self.evidence,
            "review_warnings": self.review_warnings.splitlines() if self.review_warnings else [],
            **self.review_dict(),
        }


class Skill(ReviewMixin, db.Model):
    __tablename__ = "skills"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novels.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    aliases = db.relationship(
        "SkillAlias",
        back_populates="skill",
        cascade="all, delete-orphan",
        order_by="SkillAlias.alias",
    )

    def to_admin_dict(self):
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "source_chapter_id": None,
            "aliases": [alias.to_admin_dict() for alias in self.aliases],
            **self.review_dict(),
        }


class SkillAlias(db.Model):
    __tablename__ = "skill_aliases"

    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    alias = db.Column(db.String(255), nullable=False)
    first_seen_chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=True)
    evidence = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    skill = db.relationship("Skill", back_populates="aliases")

    __table_args__ = (
        db.UniqueConstraint("skill_id", "alias", name="uq_skill_alias"),
    )

    def to_admin_dict(self):
        return {
            "id": self.id,
            "skill_id": self.skill_id,
            "alias": self.alias,
            "first_seen_chapter_id": self.first_seen_chapter_id,
            "evidence": self.evidence,
        }


class Item(ReviewMixin, db.Model):
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novels.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    def to_admin_dict(self):
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "source_chapter_id": None,
            **self.review_dict(),
        }


class WikiEvent(ReviewMixin, db.Model):
    __tablename__ = "wiki_events"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novels.id"), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=True)
    event_type = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    def to_admin_dict(self):
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "chapter_id": self.chapter_id,
            "source_chapter_id": self.chapter_id,
            "event_type": self.event_type,
            "title": self.title,
            "description": self.description,
            **self.review_dict(),
        }


class WikiEvidence(db.Model):
    __tablename__ = "wiki_evidence"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novels.id"), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=False)
    entity_type = db.Column(db.String(100), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    evidence_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    def to_admin_dict(self):
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "chapter_id": self.chapter_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "evidence_text": self.evidence_text,
        }


class WikiEditLog(db.Model):
    __tablename__ = "wiki_edit_logs"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novels.id"), nullable=False)
    entity_type = db.Column(db.String(100), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    entity_label = db.Column(db.String(255), nullable=False)
    parent_entity_type = db.Column(db.String(100), nullable=True)
    parent_entity_id = db.Column(db.Integer, nullable=True)
    change_type = db.Column(db.String(50), nullable=False)
    field_name = db.Column(db.String(100), nullable=True)
    old_value_json = db.Column(db.Text, nullable=True)
    new_value_json = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    edited_by = db.Column(db.String(255), nullable=True, default="Admin")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    novel = db.relationship("Novel")

    def old_value(self):
        return json.loads(self.old_value_json) if self.old_value_json else None

    def new_value(self):
        return json.loads(self.new_value_json) if self.new_value_json else None

    def to_admin_dict(self):
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "entity_label": self.entity_label,
            "parent_entity_type": self.parent_entity_type,
            "parent_entity_id": self.parent_entity_id,
            "change_type": self.change_type,
            "field_name": self.field_name,
            "old_value": self.old_value(),
            "new_value": self.new_value(),
            "summary": self.summary,
            "edited_by": self.edited_by,
            "created_at": serialize_datetime(self.created_at),
        }


class CharacterProgressionEvent(ReviewMixin, db.Model):
    __tablename__ = "character_progression_events"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novels.id"), nullable=False)
    character_id = db.Column(db.Integer, db.ForeignKey("characters.id"), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=False)
    progression_type = db.Column(db.String(100), nullable=False)
    old_value = db.Column(db.String(255), nullable=True)
    new_value = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    review_warnings = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    character = db.relationship("Character")

    def to_admin_dict(self):
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "character_id": self.character_id,
            "character_name": self.character.name if self.character else None,
            "chapter_id": self.chapter_id,
            "source_chapter_id": self.chapter_id,
            "progression_type": self.progression_type,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "description": self.description,
            "review_warnings": self.review_warnings.splitlines() if self.review_warnings else [],
            **self.review_dict(),
        }


class CharacterSkill(ReviewMixin, db.Model):
    __tablename__ = "character_skills"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novels.id"), nullable=False)
    character_id = db.Column(db.Integer, db.ForeignKey("characters.id"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=False)
    relationship_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    character = db.relationship("Character")
    skill = db.relationship("Skill")

    __table_args__ = (
        db.UniqueConstraint(
            "character_id",
            "skill_id",
            name="uq_character_skill_pair",
        ),
    )

    def to_admin_dict(self):
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "character_id": self.character_id,
            "character_name": self.character.name if self.character else None,
            "skill_id": self.skill_id,
            "skill_name": self.skill.name if self.skill else None,
            "chapter_id": self.chapter_id,
            "source_chapter_id": self.chapter_id,
            "description": self.description,
            **self.review_dict(),
        }


class CharacterItem(ReviewMixin, db.Model):
    __tablename__ = "character_items"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novels.id"), nullable=False)
    character_id = db.Column(db.Integer, db.ForeignKey("characters.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=False)
    relationship_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    character = db.relationship("Character")
    item = db.relationship("Item")

    __table_args__ = (
        db.UniqueConstraint(
            "character_id",
            "item_id",
            "relationship_type",
            name="uq_character_item_relationship",
        ),
    )

    def to_admin_dict(self):
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "character_id": self.character_id,
            "character_name": self.character.name if self.character else None,
            "item_id": self.item_id,
            "item_name": self.item.name if self.item else None,
            "chapter_id": self.chapter_id,
            "source_chapter_id": self.chapter_id,
            "relationship_type": self.relationship_type,
            "description": self.description,
            **self.review_dict(),
        }


class CharacterLifeEvent(ReviewMixin, db.Model):
    __tablename__ = "character_life_events"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novels.id"), nullable=False)
    character_id = db.Column(db.Integer, db.ForeignKey("characters.id"), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=False)
    event_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    character = db.relationship("Character")

    def to_admin_dict(self):
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "character_id": self.character_id,
            "character_name": self.character.name if self.character else None,
            "chapter_id": self.chapter_id,
            "source_chapter_id": self.chapter_id,
            "event_type": self.event_type,
            "description": self.description,
            "reason": self.reason,
            **self.review_dict(),
        }
