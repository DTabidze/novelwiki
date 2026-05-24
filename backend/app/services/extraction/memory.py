from app.models import (
    Character,
    CharacterProgressionEvent,
    CharacterSkill,
    Item,
    Skill,
)


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

            metadata_facts = []

            if character.age_text:
                metadata_facts.append(f"age: {character.age_text}")

            if character.gender:
                metadata_facts.append(f"gender: {character.gender}")

            if character.race_or_species:
                species_source = (
                    f" ({character.race_or_species_source}, "
                    f"{character.race_or_species_confidence})"
                    if character.race_or_species_source or character.race_or_species_confidence
                    else ""
                )
                metadata_facts.append(f"race/species: {character.race_or_species}{species_source}")

            if character.origin:
                metadata_facts.append(f"origin: {character.origin}")

            if character.faction_or_affiliation:
                metadata_facts.append(f"affiliation: {character.faction_or_affiliation}")

            if character.status:
                metadata_facts.append(f"status: {character.status}")

            if character.titles:
                metadata_facts.append(f"titles: {character.titles}")

            current_text = f" | current: {', '.join(current_facts)}" if current_facts else ""
            metadata_text = f" | metadata: {', '.join(metadata_facts)}" if metadata_facts else ""
            lines.append(f"- {character.name}{alias_text}{current_text}{metadata_text}")
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

    lines.extend(["", "Known character-skill relationships:"])
    character_skill_rows = (
        CharacterSkill.query.filter_by(novel_id=novel.id)
        .order_by(CharacterSkill.id.desc())
        .limit(120)
        .all()
    )

    if character_skill_rows:
        for relationship in character_skill_rows:
            character_name = relationship.character.name if relationship.character else "Unknown"
            skill_name = relationship.skill.name if relationship.skill else "Unknown"
            lines.append(
                f"- {character_name}: {relationship.relationship_type} {skill_name}"
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
            "- If a known character-skill relationship is repeated, do not output it.",
            "- Only output new facts from the current chapter.",
        ]
    )

    return "\n".join(lines)
