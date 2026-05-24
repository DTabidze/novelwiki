import json
import os
import re

from app.models import (
    Character,
    CharacterSkill,
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
from app.services.ai_extraction_prompts import (
    BASE_EXTRACTION_SYSTEM_PROMPT,
    PROGRESSION_AUDIT_PROMPT,
)
from app.services.extraction.metadata import (
    create_character_metadata_proposals,
    update_new_character_metadata,
)
from app.services.extraction.progression import (
    canonicalize_progression_value,
    detect_direct_cultivation_progression,
    find_existing_progression,
    is_confirmed_progression,
    is_more_specific_progression_value,
    is_valid_progression_value,
    normalize_progression_type,
    progression_review_warnings,
    progression_values_match,
    recalculate_character_current_progression,
)
from app.services.extraction.identity import (
    add_character_alias,
    descriptive_label_key,
    find_existing_character,
    find_existing_character_by_extracted_aliases,
    is_durable_character_update,
    is_trackable_character_name,
    normalize_alias,
    normalize_appearance_type,
    promote_character_canonical_name,
    select_canonical_character_name,
    should_promote_canonical_name,
)

ALLOWED_EVENT_TYPES = {
    "item_acquired",
    "skill_acquired",
    "location_arrived",
    "major_battle",
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
        from app.services.ai_extraction_schemas import (
            ChapterExtraction,
            ExtractedProgressionEvent,
            ProgressionAuditExtraction,
        )
    except ImportError as exc:
        raise RuntimeError("Install AI dependencies with: pip install -r requirements.txt") from exc

    ai_config = get_ai_config()
    client_kwargs = {"api_key": ai_config["api_key"]}

    if ai_config["base_url"]:
        client_kwargs["base_url"] = ai_config["base_url"]

    if ai_config["provider"] == "openrouter":
        client_kwargs["default_headers"] = {
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:5173"),
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "NovelWiki"),
        }

    client = OpenAI(**client_kwargs)
    model = ai_config["model"]
    memory_context = build_extraction_memory(novel)
    user_content = (
        f"Novel: {novel.title}\n"
        f"Chapter {chapter.chapter_number}: {chapter.title}\n\n"
        f"{memory_context}\n\n"
        "Current chapter text:\n"
        f"{chapter.content}"
    )

    extraction = parse_ai_json_response(
        client=client,
        provider=ai_config["provider"],
        model=model,
        temperature=ai_config["temperature"],
        system_prompt=BASE_EXTRACTION_SYSTEM_PROMPT,
        user_content=user_content,
        schema_model=ChapterExtraction,
    )

    progression_audit = parse_ai_json_response(
        client=client,
        provider=ai_config["provider"],
        model=model,
        temperature=ai_config["temperature"],
        system_prompt=PROGRESSION_AUDIT_PROMPT,
        user_content=user_content,
        schema_model=ProgressionAuditExtraction,
    )
    extraction.progression_events.extend(progression_audit.progression_events)
    extraction.progression_events.extend(
        detect_direct_cultivation_progression(
            novel,
            chapter,
            extraction,
            ExtractedProgressionEvent,
        )
    )

    return save_chapter_extraction(novel, chapter, extraction)


def get_ai_config():
    provider = os.getenv("AI_PROVIDER", "openai").strip().lower()

    if provider == "openai":
        api_key = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY")
        model = os.getenv("AI_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        base_url = os.getenv("AI_BASE_URL") or None
        missing_message = "OPENAI_API_KEY or AI_API_KEY is missing from backend/.env"
    elif provider == "openrouter":
        api_key = os.getenv("AI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        model = os.getenv("AI_MODEL", "deepseek/deepseek-v4-flash")
        base_url = os.getenv("AI_BASE_URL", "https://openrouter.ai/api/v1")
        missing_message = "AI_API_KEY or OPENROUTER_API_KEY is missing from backend/.env"
    elif provider == "deepseek":
        api_key = os.getenv("AI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        model = os.getenv("AI_MODEL", "deepseek-v4-flash")
        base_url = os.getenv("AI_BASE_URL", "https://api.deepseek.com")
        missing_message = "AI_API_KEY or DEEPSEEK_API_KEY is missing from backend/.env"
    else:
        api_key = os.getenv("AI_API_KEY")
        model = os.getenv("AI_MODEL")
        base_url = os.getenv("AI_BASE_URL") or None
        missing_message = "AI_API_KEY is missing from backend/.env"

        if not model:
            raise RuntimeError("AI_MODEL is missing from backend/.env")

    if not api_key:
        raise RuntimeError(missing_message)

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "provider": provider,
        "temperature": float(os.getenv("AI_TEMPERATURE", "0.1")),
    }


def parse_ai_json_response(client, provider, model, temperature, system_prompt, user_content, schema_model):
    if provider == "openai":
        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            text_format=schema_model,
        )
        return response.output_parsed

    messages = [
        {
            "role": "system",
            "content": (
                f"{system_prompt}\n\n"
                "Return only valid JSON matching the requested schema. Do not wrap it in markdown."
            ),
        },
        {
            "role": "user",
            "content": (
                f"{user_content}\n\n"
                "JSON schema to follow:\n"
                f"{json.dumps(schema_model.model_json_schema(), ensure_ascii=False)}"
            ),
        },
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_model.__name__,
                    "schema": schema_model.model_json_schema(),
                    "strict": True,
                },
            },
        )
    except Exception as exc:
        if getattr(exc, "status_code", None) not in {400, 422}:
            raise

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )

    content = response.choices[0].message.content or ""
    return schema_model.model_validate_json(extract_json_content(content))


def extract_json_content(content):
    stripped = content.strip()

    if stripped.startswith("```"):
        lines = stripped.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]

        stripped = "\n".join(lines).strip()

    if stripped.startswith("{"):
        return stripped

    start = stripped.find("{")
    end = stripped.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise RuntimeError("AI response did not contain valid JSON")

    return stripped[start : end + 1]



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


def is_wiki_significant_skill(name, category, description):
    skill_text = f"{name} {category} {description}".lower()
    blocked_terms = {
        "artifact",
        "bag",
        "bottle",
        "elixir",
        "essence",
        "gourd",
        "jade slip",
        "manual",
        "medicine",
        "mirror",
        "pendant",
        "pill",
        "robe",
        "scroll",
        "spirit stone",
        "stone",
        "tablet",
        "treasure",
        "weapon",
    }

    if any(term in skill_text for term in blocked_terms):
        return False

    skill_terms = {
        "ability",
        "art",
        "breathing",
        "cultivation method",
        "form",
        "magic",
        "method",
        "power",
        "skill",
        "spell",
        "technique",
    }

    return any(term in skill_text for term in skill_terms)


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


def normalize_relationship_type(relationship_type):
    return relationship_type.strip().lower().replace(" ", "_")


def find_existing_character_skill(character, skill, relationship_type):
    return CharacterSkill.query.filter_by(
        character_id=character.id,
        skill_id=skill.id,
        relationship_type=relationship_type,
    ).first()


def find_existing_character_skill_pair(character, skill):
    return CharacterSkill.query.filter_by(
        character_id=character.id,
        skill_id=skill.id,
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
        "metadata_proposals_created": 0,
        "character_skills_created": 0,
        "life_events_created": 0,
        "evidence_created": 0,
    }

    for extracted_character in extraction.characters:
        if not has_meaningful_evidence(extracted_character.evidence):
            continue

        extracted_name, extracted_aliases = select_canonical_character_name(
            extracted_character.name,
            extracted_character.aliases,
        )

        if not is_trackable_character_name(extracted_name):
            continue

        appearance_type = normalize_appearance_type(extracted_character.appearance_type)
        character = find_existing_character(novel, extracted_name)

        if not character:
            character = find_existing_character_by_extracted_aliases(
                novel,
                [extracted_name, *extracted_aliases],
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
                status="unknown",
                review_status="pending",
            )
            db.session.add(character)
            summary["characters_created"] += 1
            character_created = True

        db.session.flush()
        metadata_updated = False

        if character_created:
            metadata_updated = update_new_character_metadata(
                character,
                extracted_character.metadata,
            )
        else:
            summary["metadata_proposals_created"] += create_character_metadata_proposals(
                novel,
                chapter,
                character,
                extracted_character.metadata,
                extracted_character.evidence,
            )

        aliases_added = False

        for alias in extracted_aliases:
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
            aliases_added or canonical_name_promoted or metadata_updated,
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

        if not is_wiki_significant_skill(
            extracted_skill.name,
            extracted_skill.category,
            extracted_skill.description,
        ):
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

    for extracted_relationship in extraction.character_skills:
        if not has_meaningful_evidence(extracted_relationship.evidence):
            continue

        character = find_existing_character(novel, extracted_relationship.character_name)
        skill = find_existing_skill(novel, extracted_relationship.skill_name)

        if not character:
            continue

        if not is_wiki_significant_skill(
            extracted_relationship.skill_name,
            "technique",
            extracted_relationship.description,
        ):
            continue

        if not skill:
            skill = Skill(
                novel_id=novel.id,
                name=extracted_relationship.skill_name,
                category="technique",
                description=extracted_relationship.description,
                review_status="pending",
            )
            db.session.add(skill)
            db.session.flush()
            summary["skills_created"] += 1

            if add_evidence(
                novel,
                chapter,
                "skill",
                skill.id,
                extracted_relationship.evidence,
            ):
                summary["evidence_created"] += 1

        relationship_type = normalize_relationship_type(extracted_relationship.relationship_type)
        existing_skill_pair = find_existing_character_skill_pair(character, skill)

        if existing_skill_pair:
            continue

        existing_relationship = find_existing_character_skill(
            character,
            skill,
            relationship_type,
        )

        if existing_relationship:
            existing_relationship.description = merge_description(
                existing_relationship.description,
                extracted_relationship.description,
            )
            continue

        relationship = CharacterSkill(
            novel_id=novel.id,
            character_id=character.id,
            skill_id=skill.id,
            chapter_id=chapter.id,
            relationship_type=relationship_type,
            description=extracted_relationship.description,
            review_status="pending",
        )
        db.session.add(relationship)
        db.session.flush()

        if add_evidence(
            novel,
            chapter,
            "character_skill",
            relationship.id,
            extracted_relationship.evidence,
        ):
            summary["evidence_created"] += 1

        summary["character_skills_created"] += 1

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
                status="unknown",
                review_status="pending",
            )
            db.session.add(character)
            db.session.flush()
            summary["characters_created"] += 1

        progression_type = normalize_progression_type(extracted_progression.progression_type)
        new_value = canonicalize_progression_value(
            progression_type,
            extracted_progression.new_value,
        )
        old_value = canonicalize_progression_value(
            progression_type,
            extracted_progression.old_value,
        )

        if not is_valid_progression_value(progression_type, new_value):
            continue

        if progression_values_match(
            progression_type,
            old_value,
            new_value,
        ):
            continue

        existing_progression = find_existing_progression(
            character,
            progression_type,
            new_value,
        )

        if existing_progression:
            if is_more_specific_progression_value(
                progression_type,
                existing_progression.new_value,
                new_value,
            ):
                existing_progression.new_value = new_value
                existing_progression.description = merge_description(
                    existing_progression.description,
                    extracted_progression.description,
                )
                recalculate_character_current_progression(character, progression_type)

                if add_evidence(
                    novel,
                    chapter,
                    "progression",
                    existing_progression.id,
                    extracted_progression.evidence,
                ):
                    summary["evidence_created"] += 1

            recalculate_character_current_progression(character, progression_type)
            continue

        review_warnings = progression_review_warnings(
            novel,
            chapter,
            character,
            progression_type,
            new_value,
            extracted_progression.evidence,
        )
        progression = CharacterProgressionEvent(
            novel_id=novel.id,
            character_id=character.id,
            chapter_id=chapter.id,
            progression_type=progression_type,
            old_value=old_value,
            new_value=new_value,
            description=extracted_progression.description,
            review_warnings="\n".join(review_warnings) if review_warnings else None,
            review_status="pending",
        )
        db.session.add(progression)
        db.session.flush()
        recalculate_character_current_progression(character, progression_type)

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
