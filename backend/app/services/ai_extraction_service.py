import os

from app.models import Character, Chapter, Item, Novel, Skill, WikiEvent, WikiEvidence, db


SYSTEM_PROMPT = """
You extract wiki-style information from Asian cultivation and LitRPG novel chapters.
Return only facts supported by the provided chapter text.
Use short evidence snippets. Do not include full chapter text.
If a category has no clear entries, return an empty list for that category.
"""


def extract_chapter_with_ai(novel, chapter):
    try:
        from openai import OpenAI
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError("Install AI dependencies with: pip install -r requirements.txt") from exc

    class ExtractedCharacter(BaseModel):
        name: str = Field(description="Character name")
        description: str = Field(description="Brief wiki-style description")
        evidence: str = Field(description="Short supporting snippet or paraphrase from this chapter")

    class ExtractedSkill(BaseModel):
        name: str = Field(description="Skill, technique, ability, spell, or power name")
        category: str = Field(description="Short category such as technique, ability, spell, or rank")
        description: str = Field(description="Brief wiki-style description")
        evidence: str = Field(description="Short supporting snippet or paraphrase from this chapter")

    class ExtractedItem(BaseModel):
        name: str = Field(description="Item, weapon, artifact, pill, or object name")
        category: str = Field(description="Short category such as weapon, artifact, pill, or object")
        description: str = Field(description="Brief wiki-style description")
        evidence: str = Field(description="Short supporting snippet or paraphrase from this chapter")

    class ExtractedEvent(BaseModel):
        event_type: str = Field(description="Short type such as introduction, level_up, item_gain, battle, discovery")
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
    save_chapter_extraction(novel, chapter, extraction)
    return extraction


def add_evidence(novel, chapter, entity_type, entity_id, evidence_text):
    if not evidence_text:
        return

    db.session.add(
        WikiEvidence(
            novel_id=novel.id,
            chapter_id=chapter.id,
            entity_type=entity_type,
            entity_id=entity_id,
            evidence_text=evidence_text[:500],
        )
    )


def save_chapter_extraction(novel, chapter, extraction):
    for extracted_character in extraction.characters:
        character = Character(
            novel_id=novel.id,
            name=extracted_character.name,
            description=extracted_character.description,
            first_seen_chapter_id=chapter.id,
            review_status="pending",
        )
        db.session.add(character)
        db.session.flush()
        add_evidence(novel, chapter, "character", character.id, extracted_character.evidence)

    for extracted_skill in extraction.skills:
        skill = Skill(
            novel_id=novel.id,
            name=extracted_skill.name,
            category=extracted_skill.category,
            description=extracted_skill.description,
            review_status="pending",
        )
        db.session.add(skill)
        db.session.flush()
        add_evidence(novel, chapter, "skill", skill.id, extracted_skill.evidence)

    for extracted_item in extraction.items:
        item = Item(
            novel_id=novel.id,
            name=extracted_item.name,
            category=extracted_item.category,
            description=extracted_item.description,
            review_status="pending",
        )
        db.session.add(item)
        db.session.flush()
        add_evidence(novel, chapter, "item", item.id, extracted_item.evidence)

    for extracted_event in extraction.events:
        event = WikiEvent(
            novel_id=novel.id,
            chapter_id=chapter.id,
            event_type=extracted_event.event_type,
            title=extracted_event.title,
            description=extracted_event.description,
            review_status="pending",
        )
        db.session.add(event)
        db.session.flush()
        add_evidence(novel, chapter, "event", event.id, extracted_event.evidence)

    novel.status = "processed"
    novel.error_message = None
    db.session.commit()
