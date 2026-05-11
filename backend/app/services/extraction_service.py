from app.models import Character, Chapter, Item, Novel, Skill, WikiEvent, WikiEvidence, db


def run_placeholder_extraction(novel):
    first_chapter = (
        Chapter.query.filter_by(novel_id=novel.id).order_by(Chapter.chapter_number).first()
    )

    Character.query.filter_by(novel_id=novel.id).delete()
    Skill.query.filter_by(novel_id=novel.id).delete()
    Item.query.filter_by(novel_id=novel.id).delete()
    WikiEvent.query.filter_by(novel_id=novel.id).delete()
    WikiEvidence.query.filter_by(novel_id=novel.id).delete()

    novel.status = "processing"
    novel.error_message = None
    db.session.flush()

    if not first_chapter:
        novel.status = "failed"
        novel.error_message = "No chapters found for this novel."
        db.session.commit()
        return

    character = Character(
        novel_id=novel.id,
        name="Placeholder Character",
        description="Temporary record proving character extraction storage works.",
        first_seen_chapter_id=first_chapter.id,
    )
    skill = Skill(
        novel_id=novel.id,
        name="Placeholder Skill",
        category="technique",
        description="Temporary record proving skill extraction storage works.",
    )
    item = Item(
        novel_id=novel.id,
        name="Placeholder Item",
        category="artifact",
        description="Temporary record proving item extraction storage works.",
    )
    event = WikiEvent(
        novel_id=novel.id,
        chapter_id=first_chapter.id,
        event_type="placeholder",
        title="Placeholder Processing Event",
        description="Temporary event proving timeline storage works.",
    )

    db.session.add_all([character, skill, item, event])
    db.session.flush()

    db.session.add(
        WikiEvidence(
            novel_id=novel.id,
            chapter_id=first_chapter.id,
            entity_type="event",
            entity_id=event.id,
            evidence_text="Placeholder evidence. Real extraction will save short supporting snippets here.",
        )
    )

    novel.status = "processed"
    db.session.commit()


def get_extracted_data(novel):
    return {
        "novel": novel.to_admin_dict(),
        "characters": [
            character.to_admin_dict()
            for character in Character.query.filter_by(novel_id=novel.id).order_by(Character.name).all()
        ],
        "skills": [
            skill.to_admin_dict()
            for skill in Skill.query.filter_by(novel_id=novel.id).order_by(Skill.name).all()
        ],
        "items": [
            item.to_admin_dict()
            for item in Item.query.filter_by(novel_id=novel.id).order_by(Item.name).all()
        ],
        "events": [
            event.to_admin_dict()
            for event in WikiEvent.query.filter_by(novel_id=novel.id).order_by(WikiEvent.id).all()
        ],
        "evidence": [
            evidence.to_admin_dict()
            for evidence in WikiEvidence.query.filter_by(novel_id=novel.id)
            .order_by(WikiEvidence.id)
            .all()
        ],
    }
