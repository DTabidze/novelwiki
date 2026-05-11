import os

from app.models import Character, Chapter, Item, Novel, Skill, WikiEvent, WikiEvidence, db


SYSTEM_PROMPT = """
You extract wiki-style information from Asian cultivation and LitRPG novel chapters.
Return only facts supported by the provided chapter text.
Use short evidence snippets. Do not include full chapter text.
If a category has no clear entries, return an empty list for that category.
Events are not chapter summaries. Extract only specific, trackable wiki timeline facts.
Allowed event_type values:
- item_acquired
- skill_acquired
- cultivation_level_changed
- rank_changed
- location_arrived
- major_battle
- death

Do not create events for learning, realizing, hearing about, noticing, discussing, wanting,
attempting, understanding, or discovering information unless the character actually gains an
item, skill, rank, cultivation level, joins an organization, arrives at an important location,
fights a major battle, or dies.
Do not create character introduction events; characters are already tracked separately.
For characters, set appearance_type to appeared only when the character is physically present,
speaks, acts, or directly participates in the scene. Use mentioned when the character is only
named, referenced, remembered, or discussed.
Extract named characters and important recurring unnamed characters only. Do not create numbered
placeholder characters such as "Cultivation Monk 1" or "Guard 2" for minor unnamed speakers.
If an unnamed role is not clearly important or recurring, skip it.
Items must be wiki-significant. Extract only artifacts, weapons, cultivation manuals, technique
scrolls, pills, treasures, named quest items, unique equipment, or recurring plot-critical objects.
Do not extract ordinary clothing, uniforms, servant robes, badges, food, furniture, rooms,
buildings, generic tools, or common supplies unless the text clearly makes them magical, named,
unique, recurring, or plot-critical.
Use item_acquired only for important items. Do not create item_acquired timeline facts for
ordinary clothing, badges, uniforms, supplies, or status markers.
Prefer zero to two events per chapter.
"""

ALLOWED_EVENT_TYPES = {
    "item_acquired",
    "skill_acquired",
    "cultivation_level_changed",
    "rank_changed",
    "location_arrived",
    "major_battle",
    "death",
}


def extract_chapter_with_ai(novel, chapter):
    try:
        from openai import OpenAI
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError("Install AI dependencies with: pip install -r requirements.txt") from exc

    class ExtractedCharacter(BaseModel):
        name: str = Field(description="Character name")
        appearance_type: str = Field(description="Either mentioned or appeared")
        description: str = Field(description="Brief wiki-style description")
        evidence: str = Field(description="Short supporting snippet or paraphrase from this chapter")

    class ExtractedSkill(BaseModel):
        name: str = Field(description="Skill, technique, ability, spell, or power name")
        category: str = Field(description="Short category such as technique, ability, spell, or rank")
        description: str = Field(description="Brief wiki-style description")
        evidence: str = Field(description="Short supporting snippet or paraphrase from this chapter")

    class ExtractedItem(BaseModel):
        name: str = Field(description="Item, weapon, artifact, pill, or object name")
        category: str = Field(description="Short category such as manual, weapon, artifact, pill, treasure, or quest_item")
        importance: str = Field(description="Either important or minor")
        description: str = Field(description="Brief wiki-style description")
        evidence: str = Field(description="Short supporting snippet or paraphrase from this chapter")

    class ExtractedEvent(BaseModel):
        event_type: str = Field(
            description=(
                "One of: item_acquired, skill_acquired, "
                "cultivation_level_changed, rank_changed, "
                "location_arrived, major_battle, death"
            )
        )
        title: str = Field(description="Short event title")
        description: str = Field(description="Brief event summary")
        evidence: str = Field(description="Short supporting snippet or paraphrase from this chapter")

    class ChapterExtraction(BaseModel):
        characters: list[ExtractedCharacter]
        skills: list[ExtractedSkill]
        items: list[ExtractedItem]
        events: list[ExtractedEvent]

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing from backend/.env")

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Novel: {novel.title}\n"
                    f"Chapter {chapter.chapter_number}: {chapter.title}\n\n"
                    f"{chapter.content}"
                ),
            },
        ],
        text_format=ChapterExtraction,
    )

    extraction = response.output_parsed
    return save_chapter_extraction(novel, chapter, extraction)


def normalize_evidence_text(evidence_text):
    return (
        " ".join(evidence_text.split())
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("…", "...")
        .strip("\"'")
    )


def evidence_match_key(evidence_text):
    return "".join(
        character.lower()
        for character in normalize_evidence_text(evidence_text)
        if character.isalnum() or character.isspace()
    )


def add_evidence(novel, chapter, entity_type, entity_id, evidence_text):
    if not evidence_text:
        return False

    normalized_evidence = normalize_evidence_text(evidence_text)[:500]
    new_evidence_key = evidence_match_key(normalized_evidence)
    existing_evidence_rows = WikiEvidence.query.filter_by(
        novel_id=novel.id,
        chapter_id=chapter.id,
        entity_type=entity_type,
        entity_id=entity_id,
    ).all()

    for existing_evidence in existing_evidence_rows:
        if evidence_match_key(existing_evidence.evidence_text) == new_evidence_key:
            return False

    db.session.add(
        WikiEvidence(
            novel_id=novel.id,
            chapter_id=chapter.id,
            entity_type=entity_type,
            entity_id=entity_id,
            evidence_text=normalized_evidence,
        )
    )
    return True


def find_existing_by_name(model, novel, name):
    return model.query.filter(
        model.novel_id == novel.id,
        db.func.lower(model.name) == name.lower(),
    ).first()


def normalize_appearance_type(appearance_type):
    normalized_type = appearance_type.strip().lower().replace(" ", "_")

    if normalized_type not in {"mentioned", "appeared"}:
        return "appeared"

    return normalized_type


def normalize_importance(importance):
    normalized_importance = importance.strip().lower()

    if normalized_importance not in {"important", "minor"}:
        return "minor"

    return normalized_importance


def is_wiki_significant_item(name, category, description):
    item_text = f"{name} {category} {description}".lower()
    blocked_terms = {
        "robe",
        "servant robe",
        "uniform",
        "badge",
        "hemp robe",
        "clothing",
        "food",
        "furniture",
        "room",
        "bed",
        "common supply",
        "generic tool",
    }

    important_terms = {
        "manual",
        "scripture",
        "technique",
        "artifact",
        "treasure",
        "weapon",
        "sword",
        "pill",
        "elixir",
        "scroll",
        "quest",
        "token",
        "talisman",
    }

    if any(term in item_text for term in blocked_terms):
        return any(term in item_text for term in important_terms)

    return True


def find_existing_event(novel, chapter, event_type, title):
    title_key = event_match_key(title)
    event_rows = WikiEvent.query.filter(
        WikiEvent.novel_id == novel.id,
        WikiEvent.chapter_id == chapter.id,
        db.func.lower(WikiEvent.event_type) == event_type.lower(),
    ).all()

    for event in event_rows:
        if event_match_key(event.title) == title_key:
            return event

    return None


def event_match_key(title):
    normalized_title = title.lower().replace("arrived", "arrival").replace("arrives", "arrival")
    words = [
        word
        for word in "".join(
            character if character.isalnum() or character.isspace() else " "
            for character in normalized_title
        ).split()
        if word not in {"at", "the", "a", "an", "to", "of"}
    ]

    return " ".join(words)


def is_trackable_character_name(name):
    normalized_name = name.strip().lower()

    if any(character.isdigit() for character in normalized_name):
        return False

    blocked_terms = {
        "monk",
        "guard",
        "servant",
        "disciple",
        "man",
        "woman",
        "youth",
        "person",
    }

    words = set(normalized_name.replace("-", " ").split())

    if words & blocked_terms and normalized_name.startswith(("cultivation ", "unknown ", "unnamed ")):
        return False

    return True


def is_significant_rank_event(title, description):
    event_text = f"{title} {description}".lower()
    blocked_terms = {"servant", "worker", "laborer", "chore", "work without pay"}
    progression_terms = {
        "qi condensation",
        "cultivation",
        "level",
        "realm",
        "stage",
        "outer sect",
        "inner sect",
        "disciple",
        "rank",
        "class",
    }

    if any(term in event_text for term in blocked_terms):
        return any(term in event_text for term in progression_terms)

    return True


def merge_description(existing_description, new_description):
    if not existing_description:
        return new_description

    if not new_description or new_description in existing_description:
        return existing_description

    return f"{existing_description}\n\n{new_description}"


def save_chapter_extraction(novel, chapter, extraction):
    summary = {
        "characters_created": 0,
        "characters_updated": 0,
        "skills_created": 0,
        "skills_updated": 0,
        "items_created": 0,
        "items_updated": 0,
        "events_created": 0,
        "evidence_created": 0,
    }

    for extracted_character in extraction.characters:
        if not is_trackable_character_name(extracted_character.name):
            continue

        appearance_type = normalize_appearance_type(extracted_character.appearance_type)
        character = find_existing_by_name(Character, novel, extracted_character.name)

        if character:
            character.description = merge_description(
                character.description,
                extracted_character.description,
            )
            if not character.first_mentioned_chapter_id:
                character.first_mentioned_chapter_id = chapter.id

            if appearance_type == "appeared" and not character.first_appeared_chapter_id:
                character.first_appeared_chapter_id = chapter.id

            if not character.first_seen_chapter_id:
                character.first_seen_chapter_id = chapter.id

            summary["characters_updated"] += 1
        else:
            first_appeared_chapter_id = chapter.id if appearance_type == "appeared" else None
            character = Character(
                novel_id=novel.id,
                name=extracted_character.name,
                description=extracted_character.description,
                first_mentioned_chapter_id=chapter.id,
                first_appeared_chapter_id=first_appeared_chapter_id,
                first_seen_chapter_id=chapter.id,
                review_status="pending",
            )
            db.session.add(character)
            summary["characters_created"] += 1

        db.session.flush()
        if add_evidence(novel, chapter, "character", character.id, extracted_character.evidence):
            summary["evidence_created"] += 1

    for extracted_skill in extraction.skills:
        skill = find_existing_by_name(Skill, novel, extracted_skill.name)

        if skill:
            skill.category = skill.category or extracted_skill.category
            skill.description = merge_description(skill.description, extracted_skill.description)
            summary["skills_updated"] += 1
        else:
            skill = Skill(
                novel_id=novel.id,
                name=extracted_skill.name,
                category=extracted_skill.category,
                description=extracted_skill.description,
                review_status="pending",
            )
            db.session.add(skill)
            summary["skills_created"] += 1

        db.session.flush()
        if add_evidence(novel, chapter, "skill", skill.id, extracted_skill.evidence):
            summary["evidence_created"] += 1

    for extracted_item in extraction.items:
        if normalize_importance(extracted_item.importance) != "important":
            continue

        if not is_wiki_significant_item(
            extracted_item.name,
            extracted_item.category,
            extracted_item.description,
        ):
            continue

        item = find_existing_by_name(Item, novel, extracted_item.name)

        if item:
            item.category = item.category or extracted_item.category
            item.description = merge_description(item.description, extracted_item.description)
            summary["items_updated"] += 1
        else:
            item = Item(
                novel_id=novel.id,
                name=extracted_item.name,
                category=extracted_item.category,
                description=extracted_item.description,
                review_status="pending",
            )
            db.session.add(item)
            summary["items_created"] += 1

        db.session.flush()
        if add_evidence(novel, chapter, "item", item.id, extracted_item.evidence):
            summary["evidence_created"] += 1

    for extracted_event in extraction.events:
        event_type = extracted_event.event_type.strip().lower().replace(" ", "_")

        if event_type not in ALLOWED_EVENT_TYPES:
            continue

        if event_type == "rank_changed" and not is_significant_rank_event(
            extracted_event.title,
            extracted_event.description,
        ):
            continue

        if event_type == "item_acquired" and not is_important_item_event(
            novel,
            extracted_event.title,
            extracted_event.description,
        ):
            continue

        event = find_existing_event(
            novel,
            chapter,
            event_type,
            extracted_event.title,
        )

        if event:
            event.description = merge_description(event.description, extracted_event.description)
        else:
            event = WikiEvent(
                novel_id=novel.id,
                chapter_id=chapter.id,
                event_type=event_type,
                title=extracted_event.title,
                description=extracted_event.description,
                review_status="pending",
            )
            db.session.add(event)
            summary["events_created"] += 1

        db.session.flush()
        if add_evidence(novel, chapter, "event", event.id, extracted_event.evidence):
            summary["evidence_created"] += 1

    novel.status = "processed"
    novel.error_message = None
    db.session.commit()

    return summary


def is_important_item_event(novel, title, description):
    event_text = f"{title} {description}".lower()
    important_item_names = [
        item.name.lower()
        for item in Item.query.filter_by(novel_id=novel.id).all()
    ]

    return any(item_name in event_text for item_name in important_item_names)
