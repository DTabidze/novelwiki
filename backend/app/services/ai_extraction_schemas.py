from pydantic import BaseModel, Field


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

class ExtractedCharacterSkill(BaseModel):
    character_name: str = Field(description="Canonical character name")
    skill_name: str = Field(description="Canonical skill name")
    relationship_type: str = Field(
        default="has",
        description="Internal extraction action. Canonical character-skill relationships are always stored as has.",
    )
    description: str = Field(description="Brief description of the character-skill relationship")
    evidence: str = Field(description="Short supporting snippet proving the relationship")

class ChapterExtraction(BaseModel):
    characters: list[ExtractedCharacter]
    skills: list[ExtractedSkill]
    items: list[ExtractedItem]
    events: list[ExtractedEvent]
    progression_events: list[ExtractedProgressionEvent]
    life_events: list[ExtractedLifeEvent]
    character_skills: list[ExtractedCharacterSkill]

class ProgressionAuditExtraction(BaseModel):
    progression_events: list[ExtractedProgressionEvent]
