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

    def to_reference_dict(self):
        return {
            "id": self.id,
            "chapter_number": self.chapter_number,
            "title": self.title,
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
            "relationship_type",
            name="uq_character_skill_relationship",
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
            "relationship_type": self.relationship_type,
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
