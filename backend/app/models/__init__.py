from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def utc_now():
    return datetime.now(timezone.utc)


class ReviewMixin:
    review_status = db.Column(db.String(50), nullable=False, default="pending")
    admin_notes = db.Column(db.Text, nullable=True)

    def review_dict(self):
        return {
            "review_status": self.review_status,
            "admin_notes": self.admin_notes,
        }


class Novel(db.Model):
    __tablename__ = "novels"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
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

    def to_admin_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "original_filename": self.original_filename,
            "file_type": self.file_type,
            "status": self.status,
            "error_message": self.error_message,
            "chapter_count": len(self.chapters),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Chapter(db.Model):
    __tablename__ = "chapters"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novels.id"), nullable=False)
    chapter_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    character_count = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    novel = db.relationship("Novel", back_populates="chapters")

    __table_args__ = (
        db.UniqueConstraint("novel_id", "chapter_number", name="uq_chapter_order"),
    )

    def to_admin_verification_dict(self):
        preview = " ".join(self.content.split())[:200]
        return {
            "id": self.id,
            "chapter_number": self.chapter_number,
            "title": self.title,
            "character_count": self.character_count,
            "preview": preview,
        }


class Character(ReviewMixin, db.Model):
    __tablename__ = "characters"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novels.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    first_seen_chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    def to_admin_dict(self):
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "name": self.name,
            "description": self.description,
            "first_seen_chapter_id": self.first_seen_chapter_id,
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

    def to_admin_dict(self):
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            **self.review_dict(),
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
