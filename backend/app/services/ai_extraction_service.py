import os

from app.models import (
    Character,
    CharacterAlias,
    CharacterLifeEvent,
    CharacterProgressionEvent,
    Chapter,
    Item,
    Novel,
    Skill,
    SkillAlias,
    WikiEvent,
    WikiEvidence,
    db,
)


SYSTEM_PROMPT = """
You extract wiki-style information from Asian cultivation and LitRPG novel chapters.
Return only facts supported by the provided chapter text.
Use short evidence snippets. Do not include full chapter text.
If a category has no clear entries, return an empty list for that category.
Primary goal for this MVP: character identity and confirmed character progression.
Timeline events are disabled for now. Always return an empty list for events.
Do not put cultivation breakthroughs, rank changes, deaths, fake deaths, resurrections,
or body/soul status changes in events. Use progression_events and life_events for those.
Life events are only for hard status changes: death, fake death, resurrection, body destroyed,
soul survived, or sealed. Do not create life_events for being scared, trapped, captured, lost,
hopeful, injured, rescued, confused, or having an uncertain future.
Any breakthrough, promotion, position change, disciple status change, class/rank change, or
cultivation level change must be extracted as progression_events.
Before returning JSON, perform this workflow:
1. Identify important characters in this chapter and resolve aliases inside the chapter.
2. Choose the best canonical name for each person from this chapter context and known memory.
3. Scan the chapter again only for confirmed cultivation levels, power levels, ranks, positions,
classes, jobs, titles, and promotions.
4. Attach every confirmed progression fact to the canonical character name from step 2.
5. Extract important skills and important items only after characters/progression are handled.
Progression extraction is mandatory. For every important character, extract confirmed current or
changed cultivation/power/status facts. Use the chapter's exact terminology.
Save a progression_event when the chapter confirms:
- a breakthrough, advancement, promotion, rank-up, class/job change, or position change happened
- a current cultivation/power level, realm, stage, rank, layer, grade, position, class, job, title,
or status is stated for the first time
- a level/rank is stated as a standalone realization or exclamation after training, meditation,
resource use, battle, recovery, or breakthrough context
Extract every confirmed progression fact in the chapter. Do not stop after finding one person's
level if another important character's level or breakthrough is also confirmed.
Before returning JSON, perform a consistency check: if any character description mentions a
confirmed cultivation level, power level, realm, rank, stage, position, class, job, title, or
promotion, there must be a matching progression_event for that same character. Do not leave
confirmed power/status facts only inside character descriptions.
Do not save:
- almost/near/close to a breakthrough
- plans, hopes, requirements, guesses, instructions, or future possibilities
- repeated known values from memory
Examples of confirmed progression wording include, but are not limited to:
- "broke through into the second level"
- "has reached the seventh level"
- "his cultivation base was at the third level"
- "The third level!" after a clear breakthrough/training context
- "became an Outer Sect disciple"
- "advanced to Foundation Establishment"
These examples are only examples. Always preserve the chapter's exact power-system terms.
Do not create character introduction events; characters are already tracked separately.
For characters, set appearance_type to appeared only when the character is physically present,
speaks, acts, or directly participates in the scene. Use mentioned when the character is only
named, referenced, remembered, or discussed.
Extract named characters and distinctive recurring unnamed characters only. Distinctive unnamed
characters can be extracted when they have a stable label and meaningful story presence, such as
"Fat Teenager", "Horse-faced Young Man", "Shrewd-looking Man", or "Green-robed Man".
They should have dialogue, recurring presence, conflict role, mentor role, useful information, or
a relationship to a major character. Skip generic unnamed background people such as "a servant",
"one disciple", "a monk", "a guard", "the young man", "the woman", or "one of the crowd".
Do not create numbered or ordinal placeholder characters such as "Cultivation Monk 1",
"First Cultivation Monk", "Second Cultivation Monk", "First Guard", or "Guard 2".
Do not create group characters such as "Cultivation monks", "guards", "disciples", or "servants".
Extract individuals only. If an unnamed group is not a single stable recurring character, skip it.
Important titled or role-named characters who act with power or drive the scene must be extracted,
even if their personal name is not yet known. Examples: "Elder Sister Xu", "Cultivator Shangguan",
"Master Uncle Shangguan", "Brother Chen".
In early chapters, do not omit active scene-driving titled characters such as captors, rescuers,
teachers, attackers, sect representatives, or resource distributors just because their full real
name is not yet revealed.
For character aliases, include alternate labels used in this chapter such as titles, nicknames,
descriptive labels, or partial names. Do not include the canonical name as an alias.
When a real personal name is revealed for a character previously known by a title or descriptive
label, use the real personal name as the canonical name and put the old title/label in aliases.
For example, if "Fat Teenager" is revealed as "Li Furui", use name "Li Furui" and alias
"Fat Teenager". If "Elder Sister Xu" is revealed as "Xu Qing", use name "Xu Qing" and alias
"Elder Sister Xu".
Only add an alias when the chapter clearly uses that alias for the same character. Do not infer
that two people are the same. Do not attach labels like "fat teenager", "young man", "servant",
or "disciple" to a named character unless the text explicitly identifies them as that same person.
Items must be wiki-significant. Extract only artifacts, weapons, cultivation manuals, technique
scrolls, pills, treasures, named quest items, unique equipment, or recurring plot-critical objects.
Do not extract ordinary clothing, uniforms, servant robes, badges, food, furniture, rooms,
buildings, generic tools, or common supplies unless the text clearly makes them magical, named,
unique, recurring, or plot-critical.
Do not extract administrative slips, ordinary jade slips, direction slips, entry tokens, badges,
passes, or paperwork unless they contain a named technique/manual, are magical artifacts, or recur
as plot-critical objects.
Do not extract places, resources, locations, springs, sects, mountains, caves, pavilions, manuals,
or items as characters.
Do not create item_acquired, skill_acquired, location_arrived, or major_battle events right now.
Evidence must directly support the exact entity or fact being extracted. Do not attach evidence
about one character/item/fact to a different character/item/fact.
Use the known wiki memory provided by the user message:
- Use canonical names from memory when a chapter uses a known alias.
- Do not create new entities for known aliases.
- Do not output known characters, skills, or items when they are merely mentioned or used again.
- Only output a known character if this chapter adds durable new wiki information such as real
name, alias/title, cultivation/power change, faction/rank change, major relationship, death,
resurrection, sealing, or another long-term status change.
- Character descriptions do not update current levels/ranks by themselves. Any confirmed current
level, rank, position, class, or power value must be output as a progression_event.
- Do not output a known skill/item when it is merely used again. Output it only if it gains a new
durable property, name, owner, or significance.
- Do not repeat progression values already listed in memory.
"""

ALLOWED_EVENT_TYPES = {
    "item_acquired",
    "skill_acquired",
    "location_arrived",
    "major_battle",
}

GENERIC_PERSON_LABELS = {
    "fat teenager",
    "the fat teenager",
    "fatty",
    "young man",
    "the young man",
    "young woman",
    "the young woman",
    "servant",
    "disciple",
    "monk",
    "cultivator",
}

ALLOWED_LIFE_EVENT_TYPES = {
    "death",
    "fake_death",
    "resurrection",
    "body_destroyed",
    "soul_survived",
    "sealed",
}


def extract_chapter_with_ai(novel, chapter):
    try:
        from openai import OpenAI
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError("Install AI dependencies with: pip install -r requirements.txt") from exc

    class ExtractedCharacter(BaseModel):
        name: str = Field(description="Character name")
        aliases: list[str] = Field(description="Alternate names, titles, or descriptive labels used in this chapter")
        appearance_type: str = Field(description="Either mentioned or appeared")
        description: str = Field(description="Brief wiki-style description")
        evidence: str = Field(description="Short supporting snippet or paraphrase from this chapter")

    class ExtractedSkill(BaseModel):
        name: str = Field(description="Skill, technique, ability, spell, or power name")
        aliases: list[str] = Field(description="Alternate names or shortened labels used for this skill")
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
                "One of: item_acquired, skill_acquired, location_arrived, major_battle"
            )
        )
        title: str = Field(description="Short event title")
        description: str = Field(description="Brief event summary")
        evidence: str = Field(description="Short supporting snippet or paraphrase from this chapter")

    class ExtractedProgressionEvent(BaseModel):
        character_name: str = Field(description="Character whose progression changed")
        progression_type: str = Field(description="cultivation_level, position, class_rank, or power_rank")
        old_value: str | None = Field(description="Previous value if explicitly known")
        new_value: str = Field(description="New confirmed rank, level, realm, or title")
        description: str = Field(description="Brief description of the confirmed change")
        evidence: str = Field(description="Short supporting snippet proving the change happened here")

    class ExtractedLifeEvent(BaseModel):
        character_name: str = Field(description="Character affected by the life-status event")
        event_type: str = Field(
            description="death, fake_death, resurrection, body_destroyed, soul_survived, or sealed"
        )
        description: str = Field(description="Brief description of what happened")
        reason: str = Field(description="Cause or reason if known")
        evidence: str = Field(description="Short supporting snippet proving the event happened here")

    class ChapterExtraction(BaseModel):
        characters: list[ExtractedCharacter]
        skills: list[ExtractedSkill]
        items: list[ExtractedItem]
        events: list[ExtractedEvent]
        progression_events: list[ExtractedProgressionEvent]
        life_events: list[ExtractedLifeEvent]

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing from backend/.env")

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    memory_context = build_extraction_memory(novel)

    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Novel: {novel.title}\n"
                    f"Chapter {chapter.chapter_number}: {chapter.title}\n\n"
                    f"{memory_context}\n\n"
                    "Current chapter text:\n"
                    f"{chapter.content}"
                ),
            },
        ],
        text_format=ChapterExtraction,
    )

    extraction = response.output_parsed
    return save_chapter_extraction(novel, chapter, extraction)


def build_extraction_memory(novel):
    lines = [
        "Known wiki memory for this novel.",
        "Use this memory to avoid duplicates and prefer canonical names.",
        "",
        "Known characters:",
    ]

    characters = Character.query.filter_by(novel_id=novel.id).order_by(Character.name).limit(80).all()

    if characters:
        for character in characters:
            aliases = ", ".join(alias.alias for alias in character.aliases[:8])
            alias_text = f" | aliases: {aliases}" if aliases else ""
            current_facts = []

            if character.current_cultivation_level:
                current_facts.append(f"cultivation: {character.current_cultivation_level}")

            if character.current_position:
                current_facts.append(f"position: {character.current_position}")

            if character.current_class_rank:
                current_facts.append(f"class rank: {character.current_class_rank}")

            if character.current_power_rank:
                current_facts.append(f"power rank: {character.current_power_rank}")

            current_text = f" | current: {', '.join(current_facts)}" if current_facts else ""
            lines.append(f"- {character.name}{alias_text}{current_text}")
    else:
        lines.append("- None yet")

    lines.extend(["", "Known skills:"])
    skills = Skill.query.filter_by(novel_id=novel.id).order_by(Skill.name).limit(80).all()

    if skills:
        for skill in skills:
            aliases = ", ".join(alias.alias for alias in skill.aliases[:8])
            alias_text = f" | aliases: {aliases}" if aliases else ""
            lines.append(f"- {skill.name}{alias_text}")
    else:
        lines.append("- None yet")

    lines.extend(["", "Known items:"])
    items = Item.query.filter_by(novel_id=novel.id).order_by(Item.name).limit(80).all()

    if items:
        for item in items:
            lines.append(f"- {item.name}")
    else:
        lines.append("- None yet")

    lines.extend(["", "Known progression values:"])
    progression_rows = (
        CharacterProgressionEvent.query.filter_by(novel_id=novel.id)
        .order_by(CharacterProgressionEvent.id.desc())
        .limit(120)
        .all()
    )

    if progression_rows:
        for progression in progression_rows:
            character_name = progression.character.name if progression.character else "Unknown"
            lines.append(
                f"- {character_name}: {progression.progression_type} = {progression.new_value}"
            )
    else:
        lines.append("- None yet")

    lines.extend(
        [
            "",
            "Memory rules:",
            "- If current text uses a known alias, output the canonical known name.",
            "- If a known character/skill/item is merely mentioned or used again, do not output it.",
            "- If a known skill reveals a new durable property, output the canonical skill name with the new detail.",
            "- If a known progression value is repeated, do not output it.",
            "- Only output new facts from the current chapter.",
        ]
    )

    return "\n".join(lines)


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
    if not has_meaningful_evidence(evidence_text):
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


def title_variant_key(name):
    title_words = {
        "elder",
        "junior",
        "senior",
        "brother",
        "sister",
        "master",
        "uncle",
        "aunt",
        "cultivator",
        "lord",
        "lady",
        "young",
    }
    words = [
        word
        for word in normalize_alias(name).lower().replace("-", " ").split()
        if word not in title_words
    ]

    return " ".join(words)


def descriptive_label_key(name):
    normalized_name = normalize_alias(name).lower().replace("-", " ")

    if normalized_name in {"fatty", "fat teenager", "the fat teenager", "chubby boy"}:
        return "fat_companion"

    return None


def find_existing_character_by_title_variant(novel, name):
    name_key = title_variant_key(name)
    label_key = descriptive_label_key(name)

    if not name_key and not label_key:
        return None

    characters = Character.query.filter_by(novel_id=novel.id).all()

    for character in characters:
        if name_key and title_variant_key(character.name) == name_key:
            return character

        if label_key and descriptive_label_key(character.name) == label_key:
            return character

        for alias in character.aliases:
            if name_key and title_variant_key(alias.alias) == name_key:
                return character

            if label_key and descriptive_label_key(alias.alias) == label_key:
                return character

    return None


def find_existing_character_by_extracted_aliases(novel, aliases):
    for alias in aliases:
        character = find_existing_character(novel, alias)

        if character:
            return character

    return None


def find_existing_character(novel, name):
    character = find_existing_by_name(Character, novel, name)

    if character:
        return character

    alias = (
        CharacterAlias.query.join(Character)
        .filter(
            Character.novel_id == novel.id,
            db.func.lower(CharacterAlias.alias) == name.lower(),
        )
        .first()
    )

    if alias:
        return alias.character

    return find_existing_character_by_title_variant(novel, name)


def find_existing_skill(novel, name):
    skill = find_existing_by_name(Skill, novel, name)

    if skill:
        return skill

    alias = (
        SkillAlias.query.join(Skill)
        .filter(
            Skill.novel_id == novel.id,
            db.func.lower(SkillAlias.alias) == name.lower(),
        )
        .first()
    )

    return alias.skill if alias else None


def normalize_appearance_type(appearance_type):
    normalized_type = appearance_type.strip().lower().replace(" ", "_")

    if normalized_type not in {"mentioned", "appeared"}:
        return "appeared"

    return normalized_type


def normalize_alias(alias):
    return " ".join(alias.split()).strip()


def strip_leading_title_from_personal_name(name):
    normalized_name = normalize_alias(name)
    title_prefixes = {
        "Brother",
        "Sister",
        "Elder",
        "Junior",
        "Senior",
        "Master",
        "Uncle",
        "Aunt",
    }
    words = normalized_name.split()

    if len(words) < 3 or words[0] not in title_prefixes:
        return normalized_name

    possible_personal_name = " ".join(words[1:])

    if is_probable_personal_name(possible_personal_name):
        return possible_personal_name

    return normalized_name


def personal_name_from_aliases(aliases):
    for alias in aliases:
        normalized_alias = strip_leading_title_from_personal_name(alias)

        if is_probable_personal_name(normalized_alias):
            return normalized_alias

    return None


def add_character_alias(character, alias, chapter, evidence, allow_generic=False):
    normalized_alias = normalize_alias(alias)

    if not normalized_alias or normalized_alias.lower() == character.name.lower():
        return False

    if not allow_generic and normalized_alias.lower() in GENERIC_PERSON_LABELS:
        return False

    existing_alias = CharacterAlias.query.filter(
        CharacterAlias.character_id == character.id,
        db.func.lower(CharacterAlias.alias) == normalized_alias.lower(),
    ).first()

    if existing_alias:
        return False

    db.session.add(
        CharacterAlias(
            character_id=character.id,
            alias=normalized_alias,
            first_seen_chapter_id=chapter.id,
            evidence=normalize_evidence_text(evidence)[:500] if evidence else None,
        )
    )
    return True


def is_probable_personal_name(name):
    normalized_name = normalize_alias(name)
    words = normalized_name.replace("-", " ").split()
    non_personal_words = {
        "elder",
        "junior",
        "senior",
        "brother",
        "sister",
        "master",
        "uncle",
        "aunt",
        "cultivator",
        "lord",
        "lady",
        "young",
        "fat",
        "chubby",
        "horse",
        "faced",
        "shrewd",
        "looking",
        "green",
        "robed",
        "teenager",
        "man",
        "woman",
        "monk",
        "disciple",
        "servant",
        "guard",
    }

    if len(words) < 2 or len(words) > 4:
        return False

    if any(word.lower() in non_personal_words for word in words):
        return False

    return all(word[:1].isupper() for word in words)


def is_descriptive_or_title_name(name):
    normalized_name = normalize_alias(name).lower()
    descriptive_terms = {
        "elder",
        "junior",
        "senior",
        "brother",
        "sister",
        "master",
        "uncle",
        "aunt",
        "cultivator",
        "fat",
        "chubby",
        "horse-faced",
        "horse faced",
        "shrewd-looking",
        "shrewd looking",
        "green-robed",
        "green robed",
        "teenager",
        "young man",
        "young woman",
        "man",
        "woman",
    }

    return any(term in normalized_name for term in descriptive_terms)


def should_promote_canonical_name(current_name, new_name):
    return is_probable_personal_name(new_name) and is_descriptive_or_title_name(current_name)


def promote_character_canonical_name(character, new_name, chapter, evidence):
    normalized_new_name = normalize_alias(new_name)

    if not normalized_new_name or normalized_new_name.lower() == character.name.lower():
        return False

    old_name = character.name
    character.name = normalized_new_name
    add_character_alias(character, old_name, chapter, evidence, allow_generic=True)
    return True


def is_durable_character_update(character, extracted_character, appearance_type, aliases_added):
    if not character.description:
        return True

    if aliases_added:
        return True

    if appearance_type == "appeared" and not character.first_appeared_chapter_id:
        return True

    update_text = f"{extracted_character.description} {extracted_character.evidence}".lower()
    durable_terms = {
        "real name",
        "revealed",
        "alias",
        "also known",
        "cultivation",
        "qi condensation",
        "foundation establishment",
        "core formation",
        "nascent soul",
        "level",
        "rank",
        "realm",
        "outer sect",
        "inner sect",
        "disciple",
        "elder",
        "patriarch",
        "sect",
        "clan",
        "faction",
        "friend",
        "enemy",
        "rival",
        "master",
        "teacher",
        "father",
        "mother",
        "brother",
        "sister",
        "dies",
        "death",
        "killed",
        "resurrected",
        "sealed",
    }

    return any(term in update_text for term in durable_terms)


def add_skill_alias(skill, alias, chapter, evidence):
    normalized_alias = normalize_alias(alias)

    if not normalized_alias or normalized_alias.lower() == skill.name.lower():
        return False

    existing_alias = SkillAlias.query.filter(
        SkillAlias.skill_id == skill.id,
        db.func.lower(SkillAlias.alias) == normalized_alias.lower(),
    ).first()

    if existing_alias:
        return False

    db.session.add(
        SkillAlias(
            skill_id=skill.id,
            alias=normalized_alias,
            first_seen_chapter_id=chapter.id,
            evidence=normalize_evidence_text(evidence)[:500] if evidence else None,
        )
    )
    return True


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
        "jade slip",
        "direction slip",
        "entry token",
        "pass",
        "paperwork",
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
        "talisman",
    }

    blocked_item_exceptions = {
        "magic",
        "magical",
        "artifact",
        "manual",
        "scripture",
        "technique",
        "talisman",
        "immortal's cave",
        "immortal cave",
        "spirit tablet",
    }

    if any(term in item_text for term in blocked_terms):
        return any(term in item_text for term in blocked_item_exceptions)

    return any(term in item_text for term in important_terms)


def find_existing_event(novel, chapter, event_type, title, description):
    title_key = event_match_key(title)
    event_rows = WikiEvent.query.filter(
        WikiEvent.novel_id == novel.id,
        WikiEvent.chapter_id == chapter.id,
        db.func.lower(WikiEvent.event_type) == event_type.lower(),
    ).all()

    for event in event_rows:
        if event_match_key(event.title) == title_key:
            return event

        if event_type == "item_acquired" and same_item_acquisition_event(
            title,
            description,
            event.title,
            event.description or "",
        ):
            return event

    return None


def same_item_acquisition_event(title, description, existing_title, existing_description):
    current_text = f"{title} {description}".lower()
    existing_text = f"{existing_title} {existing_description}".lower()

    return any(
        item_term in current_text and item_term in existing_text
        for item_term in {
            "dry spirit pill",
            "spirit condensation pill",
            "qi condensation manual",
            "copper mirror",
            "bag of holding",
            "demonic essence",
            "spirit stone",
        }
    )


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


def is_major_location_event(title, description):
    event_text = f"{title} {description}".lower()
    major_terms = {
        "sect",
        "realm",
        "city",
        "continent",
        "mountain",
        "secret realm",
        "forbidden zone",
        "trial ground",
        "cave",
        "valley",
        "battlefield",
        "long-term base",
    }
    minor_terms = {
        "room",
        "quarter",
        "quarters",
        "pavilion",
        "courtyard",
        "shop",
        "hall",
        "treasure pavilion",
        "servants",
        "outer sect",
        "inner sect",
    }

    if any(term in event_text for term in minor_terms):
        return False

    return any(term in event_text for term in major_terms)


def has_specific_location_evidence(evidence):
    evidence_words = evidence.split()

    if len(evidence_words) < 5:
        return False

    evidence_text = evidence.lower()
    action_terms = {
        "arrived",
        "landed",
        "entered",
        "reached",
        "taken",
        "brought",
        "followed",
        "appeared",
        "transported",
        "flew",
    }

    return any(term in evidence_text for term in action_terms)


def is_disallowed_progression_like_event(title, description):
    event_text = f"{title} {description}".lower()
    progression_terms = {
        "promoted",
        "promotion",
        "breakthrough",
        "broke through",
        "outer sect",
        "inner sect",
        "disciple",
        "qi condensation",
        "cultivation level",
        "rank",
        "realm",
    }

    return any(term in event_text for term in progression_terms)


def is_trackable_character_name(name):
    normalized_name = name.strip().lower()

    if any(character.isdigit() for character in normalized_name):
        return False

    non_character_terms = {
        "spring",
        "sect",
        "mountain",
        "cave",
        "pavilion",
        "manual",
        "pill",
        "stone",
        "mirror",
        "essence",
        "robe",
        "slip",
        "tablet",
    }

    if any(term in normalized_name for term in non_character_terms):
        return False

    blocked_terms = {
        "monk",
        "monks",
        "guard",
        "guards",
        "servant",
        "servants",
        "disciple",
        "disciples",
        "man",
        "men",
        "woman",
        "women",
        "youth",
        "person",
        "people",
        "crowd",
        "group",
    }

    words = set(normalized_name.replace("-", " ").split())
    ordinal_words = {
        "first",
        "second",
        "third",
        "fourth",
        "fifth",
        "sixth",
        "seventh",
        "eighth",
        "ninth",
        "tenth",
    }

    if words & blocked_terms and words & ordinal_words:
        return False

    if words & blocked_terms and (
        normalized_name.startswith(("cultivation ", "unknown ", "unnamed "))
        or normalized_name.endswith(("s", "group"))
    ):
        return False

    return True


def has_meaningful_evidence(evidence):
    if not evidence:
        return False

    normalized_evidence = normalize_evidence_text(evidence)

    if len(normalized_evidence.split()) < 4:
        return False

    vague_phrases = {
        "discussion about",
        "remarks about",
        "murmurs in the crowd",
        "murmurs in crowd",
        "tagging along",
        "mentioned by others",
        "people talk about",
        "the chapter says",
    }

    return not any(phrase in normalized_evidence.lower() for phrase in vague_phrases)


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


def normalize_value(value):
    return " ".join(value.lower().split())


def normalize_progression_type(progression_type):
    normalized_type = progression_type.strip().lower().replace(" ", "_")

    if normalized_type in {"cultivation", "cultivation_rank", "realm"}:
        return "cultivation_level"

    if normalized_type in {"sect_rank", "sect_position", "role", "status", "occupation"}:
        return "position"

    if normalized_type not in {"cultivation_level", "position", "class_rank", "power_rank"}:
        return "power_rank"

    return normalized_type


def is_confirmed_progression(progression):
    text = f"{progression.new_value} {progression.description} {progression.evidence}".lower()
    blocked_terms = {
        "approaching",
        "almost",
        "nearly",
        "close to",
        "hair away",
        "just a hair",
        "sliver away",
        "just a sliver",
        "soon",
        "on the verge",
        "not far from",
        "close to the peak",
        "close to peak",
        "almost at the peak",
        "almost at peak",
        "stronger than before",
        "if you manage",
        "if he manages",
        "if she manages",
        "if they manage",
        "may lead",
        "might lead",
        "can become",
        "could become",
        "may become",
        "requirement",
        "requires",
        "must first",
        "learns that",
        "is told that",
        "will be promoted",
        "would be promoted",
        "can be promoted",
        "path to",
        "opportunity to",
        "standstill",
        "stagnant",
        "stuck",
        "bottleneck",
        "requires more",
        "need more",
        "would require",
    }
    new_value = progression.new_value.lower()

    if any(term in new_value for term in blocked_terms):
        return False

    confirmation_terms = {
        "reached",
        "had reached",
        "achieved",
        "advanced",
        "broke through",
        "breakthrough",
        "promoted",
        "became",
        "becomes",
        "attained",
        "is now",
        "was now",
        "now it was",
        "now he was",
        "now she was",
        "is at",
        "was at",
        "has reached",
        "cultivation foundation was",
        "cultivation base was",
        "known for",
    }

    if any(term in text for term in blocked_terms):
        return False

    return any(term in text for term in confirmation_terms)


def update_character_current_progression(character, progression_type, new_value):
    if progression_type == "cultivation_level":
        character.current_cultivation_level = new_value
    elif progression_type == "position":
        character.current_position = new_value
    elif progression_type == "class_rank":
        character.current_class_rank = new_value
    elif progression_type == "power_rank":
        character.current_power_rank = new_value


def find_existing_progression(character, progression_type, new_value):
    new_value_key = normalize_value(new_value)
    progression_rows = CharacterProgressionEvent.query.filter_by(
        character_id=character.id,
        progression_type=progression_type,
    ).all()

    for progression in progression_rows:
        if normalize_value(progression.new_value) == new_value_key:
            return progression

    return None


def normalize_life_event_type(event_type):
    normalized_type = event_type.strip().lower().replace(" ", "_")

    if normalized_type not in ALLOWED_LIFE_EVENT_TYPES:
        return None

    return normalized_type


def find_existing_life_event(character, chapter, event_type):
    return CharacterLifeEvent.query.filter_by(
        character_id=character.id,
        chapter_id=chapter.id,
        event_type=event_type,
    ).first()


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
        "progression_events_created": 0,
        "life_events_created": 0,
        "evidence_created": 0,
    }

    for extracted_character in extraction.characters:
        if not has_meaningful_evidence(extracted_character.evidence):
            continue

        if not is_trackable_character_name(extracted_character.name):
            continue

        extracted_name = strip_leading_title_from_personal_name(extracted_character.name)
        personal_alias = personal_name_from_aliases(extracted_character.aliases)

        if personal_alias and is_descriptive_or_title_name(extracted_name):
            extracted_name = personal_alias

        appearance_type = normalize_appearance_type(extracted_character.appearance_type)
        character = find_existing_character(novel, extracted_name)

        if not character:
            character = find_existing_character_by_extracted_aliases(
                novel,
                [extracted_character.name, *extracted_character.aliases],
            )

        character_created = False
        canonical_name_promoted = False

        if character:
            if should_promote_canonical_name(character.name, extracted_name):
                canonical_name_promoted = promote_character_canonical_name(
                    character,
                    extracted_name,
                    chapter,
                    extracted_character.evidence,
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
                name=extracted_name,
                description=extracted_character.description,
                first_mentioned_chapter_id=chapter.id,
                first_appeared_chapter_id=first_appeared_chapter_id,
                first_seen_chapter_id=chapter.id,
                review_status="pending",
            )
            db.session.add(character)
            summary["characters_created"] += 1
            character_created = True

        db.session.flush()
        aliases_added = False

        if extracted_name.lower() != extracted_character.name.lower():
            if add_character_alias(
                character,
                extracted_character.name,
                chapter,
                extracted_character.evidence,
                allow_generic=True,
            ):
                aliases_added = True

        for alias in extracted_character.aliases:
            if add_character_alias(
                character,
                alias,
                chapter,
                extracted_character.evidence,
                allow_generic=descriptive_label_key(alias) is not None,
            ):
                aliases_added = True

        durable_update = character_created or is_durable_character_update(
            character,
            extracted_character,
            appearance_type,
            aliases_added or canonical_name_promoted,
        )

        if durable_update:
            character.description = merge_description(
                character.description,
                extracted_character.description,
            )

        if durable_update and add_evidence(
            novel,
            chapter,
            "character",
            character.id,
            extracted_character.evidence,
        ):
            summary["evidence_created"] += 1

    for extracted_skill in extraction.skills:
        if not has_meaningful_evidence(extracted_skill.evidence):
            continue

        skill = find_existing_skill(novel, extracted_skill.name)

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
        for alias in extracted_skill.aliases:
            add_skill_alias(skill, alias, chapter, extracted_skill.evidence)

        if add_evidence(novel, chapter, "skill", skill.id, extracted_skill.evidence):
            summary["evidence_created"] += 1

    for extracted_item in extraction.items:
        if not has_meaningful_evidence(extracted_item.evidence):
            continue

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
        # Timeline events are intentionally disabled for this MVP phase.
        # Keep the table/API in place so we can re-enable them later.
        continue

        if not has_meaningful_evidence(extracted_event.evidence):
            continue

        event_type = extracted_event.event_type.strip().lower().replace(" ", "_")

        if event_type not in ALLOWED_EVENT_TYPES:
            continue

        if is_disallowed_progression_like_event(
            extracted_event.title,
            extracted_event.description,
        ):
            continue

        if event_type == "location_arrived" and not is_major_location_event(
            extracted_event.title,
            extracted_event.description,
        ):
            continue

        if event_type == "location_arrived" and not has_specific_location_evidence(
            extracted_event.evidence,
        ):
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
            extracted_event.description,
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

    for extracted_progression in extraction.progression_events:
        if not has_meaningful_evidence(extracted_progression.evidence):
            continue

        if not is_confirmed_progression(extracted_progression):
            continue

        character = find_existing_character(novel, extracted_progression.character_name)

        if not character:
            if not is_trackable_character_name(extracted_progression.character_name):
                continue

            character = Character(
                novel_id=novel.id,
                name=extracted_progression.character_name,
                description=None,
                first_mentioned_chapter_id=chapter.id,
                first_appeared_chapter_id=None,
                first_seen_chapter_id=chapter.id,
                review_status="pending",
            )
            db.session.add(character)
            db.session.flush()
            summary["characters_created"] += 1

        progression_type = normalize_progression_type(extracted_progression.progression_type)
        existing_progression = find_existing_progression(
            character,
            progression_type,
            extracted_progression.new_value,
        )

        if existing_progression:
            continue

        progression = CharacterProgressionEvent(
            novel_id=novel.id,
            character_id=character.id,
            chapter_id=chapter.id,
            progression_type=progression_type,
            old_value=extracted_progression.old_value,
            new_value=extracted_progression.new_value,
            description=extracted_progression.description,
            review_status="pending",
        )
        db.session.add(progression)
        update_character_current_progression(
            character,
            progression_type,
            extracted_progression.new_value,
        )
        db.session.flush()

        if add_evidence(
            novel,
            chapter,
            "progression",
            progression.id,
            extracted_progression.evidence,
        ):
            summary["evidence_created"] += 1

        summary["progression_events_created"] += 1

    for extracted_life_event in extraction.life_events:
        if not has_meaningful_evidence(extracted_life_event.evidence):
            continue

        life_event_type = normalize_life_event_type(extracted_life_event.event_type)

        if not life_event_type:
            continue

        character = find_existing_character(novel, extracted_life_event.character_name)

        if not character:
            continue

        existing_life_event = find_existing_life_event(character, chapter, life_event_type)

        if existing_life_event:
            continue

        life_event = CharacterLifeEvent(
            novel_id=novel.id,
            character_id=character.id,
            chapter_id=chapter.id,
            event_type=life_event_type,
            description=extracted_life_event.description,
            reason=extracted_life_event.reason,
            review_status="pending",
        )
        db.session.add(life_event)
        db.session.flush()

        if add_evidence(
            novel,
            chapter,
            "life_event",
            life_event.id,
            extracted_life_event.evidence,
        ):
            summary["evidence_created"] += 1

        summary["life_events_created"] += 1

    novel.status = "processed"
    novel.error_message = None
    db.session.commit()

    return summary


def is_important_item_event(novel, title, description):
    event_text = f"{title} {description}".lower()
    blocked_terms = {
        "discovers",
        "discovered",
        "discovery",
        "tests",
        "tested",
        "uses",
        "used",
        "power",
        "property",
        "ability",
        "learns",
        "realizes",
    }

    if any(term in event_text for term in blocked_terms):
        return False

    important_item_names = [
        item.name.lower()
        for item in Item.query.filter_by(novel_id=novel.id).all()
    ]

    return any(item_name in event_text for item_name in important_item_names)
