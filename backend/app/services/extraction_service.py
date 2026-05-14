from app.models import (
    Character,
    CharacterAlias,
    CharacterItem,
    CharacterLifeEvent,
    CharacterProgressionEvent,
    CharacterSkill,
    Chapter,
    Item,
    Skill,
    SkillAlias,
    WikiEvent,
    WikiEvidence,
    db,
)


def evidence_match_key(evidence_text):
    normalized_text = (
        " ".join(evidence_text.split())
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("…", "...")
        .strip("\"'")
    )

    return "".join(
        character.lower()
        for character in normalized_text
        if character.isalnum() or character.isspace()
    )


def run_placeholder_extraction(novel):
    first_chapter = (
        Chapter.query.filter_by(novel_id=novel.id).order_by(Chapter.chapter_number).first()
    )

    character_ids = [character.id for character in Character.query.filter_by(novel_id=novel.id).all()]
    skill_ids = [skill.id for skill in Skill.query.filter_by(novel_id=novel.id).all()]

    if character_ids:
        CharacterAlias.query.filter(CharacterAlias.character_id.in_(character_ids)).delete(
            synchronize_session=False
        )

    if skill_ids:
        SkillAlias.query.filter(SkillAlias.skill_id.in_(skill_ids)).delete(
            synchronize_session=False
        )

    CharacterProgressionEvent.query.filter_by(novel_id=novel.id).delete()
    CharacterSkill.query.filter_by(novel_id=novel.id).delete()
    CharacterItem.query.filter_by(novel_id=novel.id).delete()
    CharacterLifeEvent.query.filter_by(novel_id=novel.id).delete()
    WikiEvent.query.filter_by(novel_id=novel.id).delete()
    WikiEvidence.query.filter_by(novel_id=novel.id).delete()
    Character.query.filter_by(novel_id=novel.id).delete()
    Skill.query.filter_by(novel_id=novel.id).delete()
    Item.query.filter_by(novel_id=novel.id).delete()

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
    chapters = {
        chapter.id: chapter.to_reference_dict()
        for chapter in Chapter.query.filter_by(novel_id=novel.id).all()
    }
    evidence_by_entity = {}

    evidence_rows = (
        WikiEvidence.query.filter_by(novel_id=novel.id).order_by(WikiEvidence.id).all()
    )

    for evidence in evidence_rows:
        key = (evidence.entity_type, evidence.entity_id)
        evidence_by_entity.setdefault(key, []).append(evidence.to_admin_dict())

    def with_source_and_evidence(entity_type, record):
        data = record.to_admin_dict()
        record_evidence = evidence_by_entity.get((entity_type, record.id), [])
        unique_evidence = []
        seen_evidence_text = set()

        for evidence in record_evidence:
            normalized_text = evidence_match_key(evidence["evidence_text"])

            if normalized_text in seen_evidence_text:
                continue

            seen_evidence_text.add(normalized_text)
            unique_evidence.append(evidence)

        source_chapter_id = data.get("source_chapter_id")

        if not source_chapter_id and unique_evidence:
            source_chapter_id = unique_evidence[0]["chapter_id"]

        data["source_chapter"] = chapters.get(source_chapter_id)
        data["first_mentioned_chapter"] = chapters.get(data.get("first_mentioned_chapter_id"))
        data["first_appeared_chapter"] = chapters.get(data.get("first_appeared_chapter_id"))
        data["evidence"] = unique_evidence

        if entity_type == "character":
            aliases = []

            for alias in record.aliases:
                alias_data = alias.to_admin_dict()
                alias_data["first_seen_chapter"] = chapters.get(alias.first_seen_chapter_id)
                aliases.append(alias_data)

            data["aliases"] = aliases

        if entity_type == "skill":
            aliases = []

            for alias in record.aliases:
                alias_data = alias.to_admin_dict()
                alias_data["first_seen_chapter"] = chapters.get(alias.first_seen_chapter_id)
                aliases.append(alias_data)

            data["aliases"] = aliases

        return data

    return {
        "novel": novel.to_admin_dict(),
        "characters": [
            with_source_and_evidence("character", character)
            for character in Character.query.filter_by(novel_id=novel.id).order_by(Character.name).all()
        ],
        "skills": [
            with_source_and_evidence("skill", skill)
            for skill in Skill.query.filter_by(novel_id=novel.id).order_by(Skill.name).all()
        ],
        "items": [
            with_source_and_evidence("item", item)
            for item in Item.query.filter_by(novel_id=novel.id).order_by(Item.name).all()
        ],
        "events": [
            with_source_and_evidence("event", event)
            for event in WikiEvent.query.filter_by(novel_id=novel.id).order_by(WikiEvent.id).all()
        ],
        "progression_events": [
            with_source_and_evidence("progression", progression)
            for progression in CharacterProgressionEvent.query.filter_by(novel_id=novel.id)
            .order_by(CharacterProgressionEvent.id)
            .all()
        ],
        "character_skills": [
            with_source_and_evidence("character_skill", relationship)
            for relationship in CharacterSkill.query.filter_by(novel_id=novel.id)
            .order_by(CharacterSkill.id)
            .all()
        ],
        "character_items": [
            with_source_and_evidence("character_item", relationship)
            for relationship in CharacterItem.query.filter_by(novel_id=novel.id)
            .order_by(CharacterItem.id)
            .all()
        ],
        "life_events": [
            with_source_and_evidence("life_event", life_event)
            for life_event in CharacterLifeEvent.query.filter_by(novel_id=novel.id)
            .order_by(CharacterLifeEvent.id)
            .all()
        ],
        "evidence": [evidence.to_admin_dict() for evidence in evidence_rows],
    }
