from pydantic import BaseModel, Field


EXACT_EVIDENCE_DESCRIPTION = (
    "Evidence must be an exact short excerpt copied verbatim from the chapter text. "
    "Do not paraphrase, summarize, normalize, rewrite, translate, correct grammar, "
    "change punctuation, change capitalization, add words, remove important words, "
    "or interpret the evidence. The evidence string must appear in the chapter text. "
    "Evidence must directly prove the candidate fact, not merely be nearby, scene-related, "
    "or thematically related. If no exact raw excerpt directly proves the fact, omit the fact."
)


class ExtractedCharacterMetadata(BaseModel):
    age_text: str | None = Field(description="Clearly stated age or approximate age, if any")
    gender: str | None = Field(description="Clearly stated gender, if any")
    race_or_species: str | None = Field(description="Clearly stated race or species, if any")
    origin: str | None = Field(description="Clearly stated origin, home, or place of birth, if any")
    faction_or_affiliation: str | None = Field(description="Clearly stated faction, sect, clan, or organization affiliation, if any")
    status: str | None = Field(description="Life status only: dead, historical, missing, sealed, reincarnated, or unknown. Do not use for roles, titles, sect rank, occupation, or affiliation. Do not output alive merely because the character appears or acts.")
    titles: list[str] = Field(description="Clearly stated titles or stable roles")

class ExtractedCharacter(BaseModel):
    name: str = Field(description="Character name")
    aliases: list[str] = Field(description="Alternate names, titles, or descriptive labels used in this chapter")
    appearance_type: str = Field(description="Either mentioned or appeared")
    metadata: ExtractedCharacterMetadata = Field(description="Durable character metadata clearly stated in this chapter")
    description: str = Field(description="Brief wiki-style description")
    evidence: str = Field(
        description=(
            EXACT_EVIDENCE_DESCRIPTION
            + " For characters, evidence should contain the character name, alias, stable label, or clear identifying phrase."
        )
    )

class ExtractedSkill(BaseModel):
    name: str = Field(description="Skill, technique, art, ability, spell, combat method, or cultivation method name. Progression ranks/realms/levels are not skills. Items and artifacts are not skills.")
    aliases: list[str] = Field(description="Alternate names or shortened labels used for this skill")
    category: str = Field(description="Skill category only, such as technique, ability, spell, art, combat method, martial art, divine ability, class ability, or cultivation method. Use cultivation method only when evidence describes a method/practice, not a realm/rank/level.")
    description: str = Field(description="Brief wiki-style description")
    evidence: str = Field(
        description=(
            EXACT_EVIDENCE_DESCRIPTION
            + " For skills, evidence should directly mention the skill/technique/art/ability or clearly describe its use."
        )
    )

class ExtractedItem(BaseModel):
    name: str = Field(description="Physical item, weapon, artifact, pill, manual, book, scroll, jade slip, treasure, or object name. Skills, arts, techniques, spells, abilities, and methods are not items unless evidence says they are a physical medium.")
    category: str = Field(description="Item category such as manual, weapon, artifact, pill, treasure, resource, medicine, scroll, quest_item, or other. Use manual/scroll/book/jade slip only for physical media.")
    importance: str = Field(description="Either important or minor")
    description: str = Field(description="Brief wiki-style description")
    evidence: str = Field(
        description=(
            EXACT_EVIDENCE_DESCRIPTION
            + " For items, evidence should directly mention the item and show it as a real physical object."
        )
    )

class ExtractedEvent(BaseModel):
    event_type: str = Field(
        description=(
            "One of: item_acquired, skill_acquired, location_arrived, major_battle"
        )
    )
    title: str = Field(description="Short event title")
    description: str = Field(description="Brief event summary")
    evidence: str = Field(description=EXACT_EVIDENCE_DESCRIPTION)

class ExtractedProgressionEvent(BaseModel):
    character_name: str = Field(description="Character whose progression changed")
    progression_type: str = Field(description="cultivation_level, position, class_rank, or power_rank")
    old_value: str | None = Field(description="Previous value if explicitly known")
    new_value: str = Field(description="New confirmed rank, level, realm, or title")
    description: str = Field(description="Brief description of the confirmed change")
    evidence: str = Field(
        description=(
            EXACT_EVIDENCE_DESCRIPTION
            + " For progression, evidence must directly support the exact new_value and preserve uncertainty or near-breakthrough wording."
        )
    )
    source_extractor: str | None = Field(
        default=None,
        description="Backend-set source name. Do not populate this field.",
    )

class ExtractedLifeEvent(BaseModel):
    character_name: str = Field(description="Character affected by the life-status event")
    event_type: str = Field(
        description="death, fake_death, resurrection, body_destroyed, soul_survived, or sealed"
    )
    description: str = Field(description="Brief description of what happened")
    reason: str = Field(description="Cause or reason if known")
    evidence: str = Field(
        description=(
            EXACT_EVIDENCE_DESCRIPTION
            + " For life events, evidence must directly support the hard life-status event; death evidence must clearly show death, killed, corpse, lifeless, dead, or equivalent wording."
        )
    )

class ExtractedCharacterSkill(BaseModel):
    character_name: str = Field(description="Canonical character name")
    skill_name: str = Field(description="Canonical skill name")
    relationship_type: str = Field(
        default="has",
        description="Internal extraction action. Canonical character-skill relationships are always stored as has.",
    )
    description: str = Field(description="Brief description of the character-skill relationship")
    evidence: str = Field(
        description=(
            EXACT_EVIDENCE_DESCRIPTION
            + " For character-skill links, evidence must prove the character learned, used, cultivated, practiced, displayed, mastered, taught, or possessed the named skill. Do not use evidence that only mentions the skill nearby."
        )
    )

class ExtractedCharacterItem(BaseModel):
    character_name: str = Field(description="Canonical character name")
    item_name: str = Field(description="Canonical item name")
    relationship_type: str = Field(description="owns, obtained, used, lost, gave, or received")
    description: str = Field(description="Brief description of the character-item relationship")
    evidence: str = Field(
        description=(
            EXACT_EVIDENCE_DESCRIPTION
            + " For character-item links, evidence must prove both character/item attribution and the exact relationship action. Demands, threats, item appearances, nearby scene movement, or vague treasures do not prove obtained, received, gave, used, lost, or owns."
        )
    )

class ChapterExtraction(BaseModel):
    characters: list[ExtractedCharacter]
    skills: list[ExtractedSkill]
    items: list[ExtractedItem]
    events: list[ExtractedEvent]
    progression_events: list[ExtractedProgressionEvent]
    life_events: list[ExtractedLifeEvent]
    character_skills: list[ExtractedCharacterSkill]
    character_items: list[ExtractedCharacterItem] = Field(default_factory=list)

class ProgressionAuditExtraction(BaseModel):
    progression_events: list[ExtractedProgressionEvent]

class CharacterExtraction(BaseModel):
    characters: list[ExtractedCharacter]

class ProgressionExtraction(BaseModel):
    progression_events: list[ExtractedProgressionEvent]

class ProgressionReasoningExtraction(BaseModel):
    progression_events: list[ExtractedProgressionEvent]

class SkillExtraction(BaseModel):
    skills: list[ExtractedSkill]
    character_skills: list[ExtractedCharacterSkill]

class ItemExtraction(BaseModel):
    items: list[ExtractedItem]
    character_items: list[ExtractedCharacterItem]

class LifeEventExtraction(BaseModel):
    life_events: list[ExtractedLifeEvent]
