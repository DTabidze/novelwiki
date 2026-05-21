import json
import os
import re

from app.models import (
    Character,
    CharacterAlias,
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


BASE_EXTRACTION_SYSTEM_PROMPT = """
You extract structured wiki-style information from Asian cultivation and LitRPG novel chapters.

Return ONLY valid JSON.
Use only facts directly supported by the provided chapter text.
Use short evidence snippets. Do not include full chapter text.
If a category has no clear entries, return an empty list.

Primary MVP goal:
- character identity
- aliases
- confirmed character progression
- important skills/items
- character-skill relationships
- hard life-status changes

Timeline events are disabled for now.
Always return "events": [].
Do not put cultivation breakthroughs, rank changes, deaths, fake deaths, resurrections,
body/soul changes, item acquisitions, skill acquisitions, location arrivals, or battles in events.

Use the known wiki memory provided in the user message:
- Use canonical names from memory when a chapter uses a known alias.
- Do not create duplicate entities for known aliases.
- Do not infer two characters are the same unless the chapter or memory strongly supports it.
- Do not output known characters, skills, or items when they are merely mentioned again.
- Output known entities only when this chapter adds durable new wiki information.

GENERAL RULES:
- Never invent facts.
- Preserve the chapter's exact terminology for realms, ranks, skills, items, sects, and titles.
- Evidence must directly support the exact extracted fact.
- Do not attach evidence about one character, item, skill, or event to another.
- Prefer "unknown" or an empty field over guessing.

CHARACTERS:
Extract named characters and distinctive recurring unnamed characters.

Extract a character if they:
- are physically present, speak, act, fight, teach, capture, rescue, attack, distribute resources, or drive the scene
- are important titled/role-named figures, even if their full name is not revealed yet
- have a stable recurring descriptive label, such as "Fat Teenager", "Horse-faced Young Man", "Green-robed Man", "Elder Sister Xu", "Brother Chen", or "Master Uncle Shangguan"

Skip:
- generic background people
- unnamed groups
- numbered placeholders
- ordinary labels like "a servant", "one disciple", "a guard", "the young man", "the woman"

Do not create group characters such as "cultivation monks", "guards", "disciples", or "servants".
Extract individuals only.

appearance_type:
- Use "appeared" only when the character is physically present, speaks, acts, or directly participates.
- Use "mentioned" when the character is only named, remembered, referenced, or discussed.

ALIASES:
- Include alternate labels used in this chapter: titles, nicknames, partial names, descriptive labels.
- Do not include the canonical name as an alias.
- When a real name is revealed, use the real name as canonical and put the old title/label in aliases.
- Only add an alias when the chapter clearly uses that alias for the same character.

Canonical name priority:
1. Full real name. Examples: Li Furui, Xu Qing, Meng Hao.
2. Stable sect/title name. Examples: Elder Sister Xu, Cultivator Shangguan, Brother Chen, Founder Reliance.
3. Stable nickname or recurring label. Examples: Fatty, Fat Teenager, Horse-faced Young Man.
4. Honorific-only or localized forms. Examples: Ms. Xu, Mr. Shangguan, Sister Xu.
5. Generic visual descriptions. Examples: pale-faced woman, silver robe woman, green-robed man.

Use the highest-priority name clearly supported by the chapter or memory.
If a full real name exists, use it as canonical.
If no full real name exists, prefer a stable title-style name over honorific-only forms.
Example: use "Elder Sister Xu" instead of "Ms. Xu".
If no real name or title-style name exists, use a stable nickname or recurring label.
Example: use "Fatty" or "Fat Teenager" if that is the only stable label.
Do not use generic visual descriptions as canonical unless no better stable name exists.
Put lower-priority labels used for the same character into aliases.
If a real name is revealed later, use the real name as canonical and keep old labels as aliases.

PROGRESSION:
Any confirmed cultivation, power, realm, rank, stage, layer, grade, class, job, position, title, disciple status, promotion, or breakthrough belongs in progression_events.

A progression_event is required when the chapter confirms:
- a breakthrough, advancement, promotion, rank-up, class/job change, or position change happened
- a current cultivation/power level, realm, stage, rank, layer, grade, position, class, job, title, or status is stated for the first time
- a level/rank is stated after training, meditation, pill/resource use, battle, recovery, awakening, or breakthrough context

Do NOT save progression_events for:
- near breakthroughs
- plans, hopes, requirements, guesses, instructions, or future possibilities
- unchanged "still/remains" statements
- repeated known values from memory
- item rewards, gifts, purchases, resources, or temporary possessions

CONFIRMED VS FUTURE PROGRESSION:
Only output progression_events for:
- confirmed current states
- confirmed breakthroughs
- confirmed promotions
- confirmed durable status changes

Do NOT output progression_events for:
- future possibilities
- predictions
- estimates
- plans
- hopes
- intentions
- requirements
- near-breakthroughs
- conditional statements
- internal speculation

Important:
A realm/level mention alone is NOT sufficient.

The text must clearly indicate the character already:
- reached
- entered
- advanced to
- broke through to
- became
- currently is at
- currently possesses
that level/status.

Strong negative indicators include phrases such as:
- can reach
- could reach
- might reach
- maybe
- perhaps
- almost
- close to
- nearly
- with more
- need more
- if I
- should be able to
- would be able to
- I think
- I believe
- soon
- not yet
- preparing to
- attempting to

Example:
"I think with three or maybe five more, I can reach the third level of Qi Condensation."
=> NOT a progression_event.

Example:
"His cultivation foundation was at the third level of Qi Condensation."
=> confirmed progression fact.

IMPORTANT CLARIFICATION:
A short exclamation or realization CAN be confirmed progression if nearby context clearly shows the level/status was already reached.

Example:
"The third level of Qi Condensation!"
after consuming cultivation resources and successfully advancing
=> confirmed progression fact.

But:
"just a hair away from being at the peak of the third level"
=> NOT peak third level progression.
This is near-progression and should not be saved as a confirmed progression_event.

Important distinction:
- speculation about reaching a level later = NOT progression
- confirmed possession of a level now = progression

CONFIRMED PROGRESSION VS LATER NEAR-PROGRESSION:
If the text first confirms that a character reached, advanced to, became, entered, unlocked, achieved, or currently possesses a level/rank/stage/status, extract that confirmed progression_event.

If a later sentence says the character is close to, almost at, near, just short of, approaching, preparing for, or not far from a higher/next/peak level/rank/stage/status, do NOT let that later near-progression wording cancel the earlier confirmed progression.

Extract:
- the confirmed reached/current level/rank/stage/status

Do NOT extract:
- the later near/almost/close-to higher level/rank/stage/status

Reason:
A confirmed current state and a near-future/near-next state are different facts. The confirmed current state should be saved. The near-next state should not be saved as confirmed progression.

Generic example:
"The third rank!"
followed by:
"he was just short of the peak of the third rank"

=> extract:
new_value: "third rank"

=> do NOT extract:
new_value: "peak of the third rank"

Generic example:
"She unlocked Level 20."
followed by:
"she was already close to Level 21"

=> extract:
new_value: "Level 20"

=> do NOT extract:
new_value: "Level 21"

PROGRESSION ATTRIBUTION:
When extracting a progression_event, attach the progression only to the character who is explicitly stated or clearly implied to possess or reach that level/status.

Do not attach the same progression fact to multiple characters unless the text clearly supports multiple characters having that progression.

A progression_event must be directly supported by evidence for that specific character.

If the owner of the progression is unclear or ambiguous:
- prefer the explicitly named subject
- otherwise use the strongest directly-supported subject
- do not guess

Do not copy one character's cultivation/rank/status onto another character without direct textual support.

Progression extraction is mandatory.
If any character description, skill description, character_skill entry, or evidence snippet mentions a confirmed level/rank/status, there must be a matching progression_event.

LIFE EVENTS:
life_events are only for hard status changes:
- death
- fake_death
- resurrection
- body_destroyed
- soul_survived
- sealed

Do not create life_events for:
- injury
- fear
- being trapped
- being captured
- being rescued
- confusion
- uncertain future
- temporary danger

SKILLS:
Skills are named techniques, spells, abilities, martial arts, cultivation methods, divine abilities, classes abilities, or combat moves.

Extract a skill if it is:
- learned
- known
- used
- mastered
- created
- taught
- explained as important
- newly named

Do not put manuals, pills, artifacts, medicines, treasures, resources, scrolls, or physical objects in skills.
A manual or scroll is an item. Only a named technique inside it is a skill.

CHARACTER_SKILLS:
Output a character_skills entry when a character clearly:
- learns
- uses
- knows
- masters
- creates
- teaches
a named skill.

If a character_skills entry references a skill not already listed in memory, also output that skill in skills.
Do not repeat a known character-skill relationship from memory unless the relationship type is new.

ITEMS:
Items must be wiki-significant.

Extract:
- artifacts
- weapons
- cultivation manuals
- technique scrolls/manuals
- pills
- medicines
- treasures
- named quest items
- unique equipment
- recurring plot-critical objects

Skip:
- ordinary clothing
- uniforms
- servant robes
- food
- furniture
- rooms
- buildings
- generic tools
- common supplies
- ordinary jade slips
- direction slips
- administrative paperwork
- badges/passes/tokens unless magical, named, recurring, or plot-critical

Do not extract places, sects, mountains, caves, pavilions, resources, manuals, or items as characters.

FINAL CHECK BEFORE JSON:
1. Resolve aliases inside the chapter.
2. Use canonical names from memory when supported.
3. Check every character for confirmed cultivation/power/rank/status changes.
4. Check every skill and character_skill description for hidden progression facts.
5. Make sure all confirmed progression facts have matching progression_events.
6. Make sure events is always [].
7. Make sure all evidence snippets are short and directly relevant.
"""

PROGRESSION_AUDIT_PROMPT = """
You perform a second-pass audit focused ONLY on character power progression.

Return ONLY valid JSON containing progression_events.
Do not extract characters, skills, items, character_skills, life_events, locations, or timeline events.

Your job:
Catch every confirmed cultivation, power, realm, rank, stage, layer, grade, class, job, position,
title, disciple status, promotion, or breakthrough in the chapter.

Scan for:
- first/second/third/fourth/fifth/etc. level
- Qi Condensation, Foundation Establishment, Core Formation, Nascent Soul, or any other realm
- cultivation base/foundation/power was...
- has reached...
- achieved...
- broke through...
- advanced to...
- became...
- was promoted to...
- short exclamations like "The third level of Qi Condensation!"

For each confirmed match:
- identify the character from nearby context, active viewpoint, or known memory
- use progression_type "cultivation_level" for realms/levels
- use progression_type "rank" for ranks/grades/layers if not cultivation
- use progression_type "position" for durable title, job, class, sect role, or disciple status
- use the chapter's exact wording in new_value
- include old_value only when explicitly stated nearby
- include short direct evidence
- do not include repeated known values from memory

Output progression_events for:
- confirmed current levels
- confirmed breakthroughs
- confirmed promotions
- confirmed durable status/position/class/job changes

Do NOT output:
- near breakthroughs
- hopes
- plans
- requirements
- guesses
- instructions
- future possibilities
- unchanged "still/remains" statements
- rewards, items, pills, gifts, purchases, or temporary possessions

CONFIRMED VS FUTURE PROGRESSION:
Only output progression_events for:
- confirmed current states
- confirmed breakthroughs
- confirmed promotions
- confirmed durable status changes

Do NOT output progression_events for:
- future possibilities
- predictions
- estimates
- plans
- hopes
- intentions
- requirements
- near-breakthroughs
- conditional statements
- internal speculation

Important:
A realm/level mention alone is NOT sufficient.

The text must clearly indicate the character already:
- reached
- entered
- advanced to
- broke through to
- became
- currently is at
- currently possesses
that level/status.

Strong negative indicators include phrases such as:
- can reach
- could reach
- might reach
- maybe
- perhaps
- almost
- close to
- nearly
- with more
- need more
- if I
- should be able to
- would be able to
- I think
- I believe
- soon
- not yet
- preparing to
- attempting to

Example:
"I think with three or maybe five more, I can reach the third level of Qi Condensation."
=> NOT a progression_event.

Example:
"His cultivation foundation was at the third level of Qi Condensation."
=> confirmed progression fact.

IMPORTANT CLARIFICATION:
A short exclamation or realization CAN be confirmed progression if nearby context clearly shows the level/status was already reached.

Example:
"The third level of Qi Condensation!"
after consuming cultivation resources and successfully advancing
=> confirmed progression fact.

But:
"just a hair away from being at the peak of the third level"
=> NOT peak third level progression.
This is near-progression and should not be saved as a confirmed progression_event.

Important distinction:
- speculation about reaching a level later = NOT progression
- confirmed possession of a level now = progression

CONFIRMED PROGRESSION VS LATER NEAR-PROGRESSION:
If the text first confirms that a character reached, advanced to, became, entered, unlocked, achieved, or currently possesses a level/rank/stage/status, extract that confirmed progression_event.

If a later sentence says the character is close to, almost at, near, just short of, approaching, preparing for, or not far from a higher/next/peak level/rank/stage/status, do NOT let that later near-progression wording cancel the earlier confirmed progression.

Extract:
- the confirmed reached/current level/rank/stage/status

Do NOT extract:
- the later near/almost/close-to higher level/rank/stage/status

Reason:
A confirmed current state and a near-future/near-next state are different facts. The confirmed current state should be saved. The near-next state should not be saved as confirmed progression.

Generic example:
"The third rank!"
followed by:
"he was just short of the peak of the third rank"

=> extract:
new_value: "third rank"

=> do NOT extract:
new_value: "peak of the third rank"

Generic example:
"She unlocked Level 20."
followed by:
"she was already close to Level 21"

=> extract:
new_value: "Level 20"

=> do NOT extract:
new_value: "Level 21"

PROGRESSION ATTRIBUTION:
When extracting a progression_event, attach the progression only to the character who is explicitly stated or clearly implied to possess or reach that level/status.

Do not attach the same progression fact to multiple characters unless the text clearly supports multiple characters having that progression.

A progression_event must be directly supported by evidence for that specific character.

If the owner of the progression is unclear or ambiguous:
- prefer the explicitly named subject
- otherwise use the strongest directly-supported subject
- do not guess

Do not copy one character's cultivation/rank/status onto another character without direct textual support.

Before returning JSON:
- Check if the main extraction missed any progression fact.
- Check short realization/exclamation sentences after training, meditation, pill use, resource use, battle, recovery, or awakening.
- Return only confirmed progression_events.
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

    class ExtractedCharacterSkill(BaseModel):
        character_name: str = Field(description="Canonical character name")
        skill_name: str = Field(description="Canonical skill name")
        relationship_type: str = Field(description="learns, knows, uses, creates, teaches, or masters")
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


LEVEL_WORD_PATTERN = (
    r"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"1st|2nd|3rd|4th|5th|6th|7th|8th|9th|10th"
)
QI_LEVEL_PATTERN = rf"(?P<level>{LEVEL_WORD_PATTERN})\s+level(?:\s+of)?\s+qi\s+condensation"
DIRECT_QI_LEVEL_RE = re.compile(QI_LEVEL_PATTERN, re.IGNORECASE)
BREAKTHROUGH_QI_RE = re.compile(
    rf"broken\s+through\s+(?:the\s+)?(?P<old>{LEVEL_WORD_PATTERN})\s+level(?:\s+of)?\s+qi\s+condensation"
    rf"\s+into\s+(?:the\s+)?(?P<new>{LEVEL_WORD_PATTERN})(?:\s+level(?:\s+of)?\s+qi\s+condensation)?",
    re.IGNORECASE,
)
CURRENT_QI_CONTEXT_RE = re.compile(
    r"\b(now|currently|current|foundation|base|cultivation|at|is|was|am|had reached|has reached|achieved)\b",
    re.IGNORECASE,
)
PROPER_NAME_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b")
NON_CHARACTER_NAME_CANDIDATES = {
    "Qi Condensation",
    "Pill Distribution",
    "Distribution Day",
    "Demonic Essence",
    "Demonic Essences",
    "Spirit Stone",
    "Spirit Stones",
}


def detect_direct_cultivation_progression(novel, chapter, extraction, event_model):
    text = chapter.content or ""
    candidate_names = direct_progression_character_candidates(novel, extraction)
    detected_events = []
    seen_keys = set()

    for match in BREAKTHROUGH_QI_RE.finditer(text):
        evidence = snippet_around_match(text, match)
        character_name = infer_progression_character(text, match.start(), match.end(), candidate_names)

        if not character_name:
            continue

        old_value = qi_level_value(match.group("old"))
        new_value = qi_level_value(match.group("new"))
        key = (character_name.lower(), new_value.lower(), evidence_match_key(evidence))

        if key in seen_keys:
            continue

        detected_events.append(
            event_model(
                character_name=character_name,
                progression_type="cultivation_level",
                old_value=old_value,
                new_value=new_value,
                description=f"{character_name} broke through to the {new_value}.",
                evidence=evidence,
            )
        )
        seen_keys.add(key)

    for match in DIRECT_QI_LEVEL_RE.finditer(text):
        evidence = snippet_around_match(text, match)
        evidence_lower = evidence.lower()

        if any(phrase in evidence_lower for phrase in ("away from", "not yet", "almost", "close to")):
            continue

        if not is_direct_current_level_context(evidence):
            continue

        character_name = infer_progression_character(text, match.start(), match.end(), candidate_names)

        if not character_name:
            continue

        new_value = qi_level_value(match.group("level"))
        key = (character_name.lower(), new_value.lower(), evidence_match_key(evidence))

        if key in seen_keys:
            continue

        detected_events.append(
            event_model(
                character_name=character_name,
                progression_type="cultivation_level",
                old_value=None,
                new_value=new_value,
                description=f"{character_name}'s cultivation is confirmed at the {new_value}.",
                evidence=evidence,
            )
        )
        seen_keys.add(key)

    return detected_events


def direct_progression_character_candidates(novel, extraction):
    candidates = []

    for character in Character.query.filter_by(novel_id=novel.id).all():
        candidates.append(character.name)
        candidates.extend(alias.alias for alias in character.aliases)

    for character in extraction.characters:
        candidates.append(character.name)
        candidates.extend(character.aliases)

    unique_candidates = []
    seen = set()

    for candidate in candidates:
        normalized_candidate = normalize_alias(candidate)

        if not normalized_candidate or normalized_candidate.lower() in seen:
            continue

        seen.add(normalized_candidate.lower())
        unique_candidates.append(normalized_candidate)

    return sorted(unique_candidates, key=len, reverse=True)


def infer_progression_character(text, start, end, candidate_names):
    context_start = max(0, start - 700)
    context_end = min(len(text), end + 260)
    context = text[context_start:context_end]

    best_candidate = None
    best_distance = None

    for candidate in candidate_names:
        for match in re.finditer(re.escape(candidate), context, re.IGNORECASE):
            absolute_start = context_start + match.start()
            distance = min(abs(start - absolute_start), abs(end - absolute_start))

            if best_distance is None or distance < best_distance:
                best_candidate = candidate
                best_distance = distance

    if best_candidate:
        return best_candidate

    fallback_context = text[max(0, start - 420): min(len(text), end + 220)]
    fallback_matches = [
        match.group(0)
        for match in PROPER_NAME_RE.finditer(fallback_context)
        if match.group(0) not in NON_CHARACTER_NAME_CANDIDATES
    ]

    return fallback_matches[-1] if fallback_matches else None


def snippet_around_match(text, match):
    start = match.start()
    end = match.end()
    left_boundary = max(
        text.rfind(".", 0, start),
        text.rfind("!", 0, start),
        text.rfind("?", 0, start),
        text.rfind("\n", 0, start),
    )
    right_candidates = [
        index
        for index in (
            text.find(".", end),
            text.find("!", end),
            text.find("?", end),
            text.find("\n", end),
        )
        if index != -1
    ]
    right_boundary = min(right_candidates) if right_candidates else min(len(text), end + 220)
    snippet = text[left_boundary + 1: right_boundary + 1].strip()

    if len(snippet) > 500:
        snippet = text[max(0, start - 180): min(len(text), end + 220)].strip()

    return normalize_evidence_text(snippet)


def qi_level_value(level):
    return f"{level.lower()} level of Qi condensation"


def is_direct_current_level_context(evidence):
    evidence_lower = evidence.lower()

    if "broken through" in evidence_lower or "broke through" in evidence_lower:
        return True

    if re.search(r"\bi\s+am\s+now\b", evidence_lower):
        return True

    if re.search(r"\bfoundation\s+(?:was|is|had been|was only|now was|currently was)", evidence_lower):
        return True

    return bool(CURRENT_QI_CONTEXT_RE.search(evidence))


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
        "madam",
        "miss",
        "mr",
        "mrs",
        "ms",
        "young",
    }
    words = [
        word.strip(".,:;!?()[]")
        for word in normalize_alias(name).lower().replace("-", " ").split()
        if word.strip(".,:;!?()[]") not in title_words
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


def character_name_lookup_candidates(name):
    normalized_name = normalize_alias(name)
    candidates = [normalized_name]
    parenthetical_parts = re.findall(r"\(([^)]+)\)", normalized_name)
    outside_parentheses = re.sub(r"\s*\([^)]*\)\s*", " ", normalized_name).strip()

    candidates.extend(part.strip() for part in parenthetical_parts if part.strip())

    if outside_parentheses and outside_parentheses != normalized_name:
        candidates.append(outside_parentheses)

    unique_candidates = []

    for candidate in candidates:
        candidate_key = candidate.lower()

        if candidate and candidate_key not in {item.lower() for item in unique_candidates}:
            unique_candidates.append(candidate)

    return unique_candidates


def find_existing_character(novel, name):
    candidates = character_name_lookup_candidates(name)

    for candidate in candidates:
        character = find_existing_by_name(Character, novel, candidate)

        if character:
            return character

    for candidate in candidates:
        alias = (
            CharacterAlias.query.join(Character)
            .filter(
                Character.novel_id == novel.id,
                db.func.lower(CharacterAlias.alias) == candidate.lower(),
            )
            .first()
        )

        if alias:
            return alias.character

    for candidate in candidates:
        character = find_existing_character_by_title_variant(novel, candidate)

        if character:
            return character

    return None


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


WEAK_HONORIFIC_PREFIXES = {"ms", "mr", "mrs", "miss", "mister"}

STRONG_TITLE_WORDS = {
    "cultivator",
    "daoist",
    "elder",
    "founder",
    "junior",
    "lord",
    "master",
    "patriarch",
    "saint",
    "sect",
    "senior",
}

TITLE_STYLE_WORDS = STRONG_TITLE_WORDS | {"brother", "sister"}

PERSON_NOUNS = {
    "boy",
    "cultivator",
    "disciple",
    "elder",
    "girl",
    "guard",
    "man",
    "servant",
    "teenager",
    "woman",
    "youth",
}

DESCRIPTOR_MARKERS = {
    "clad",
    "eyed",
    "faced",
    "fat",
    "haired",
    "masked",
    "old",
    "robed",
    "short",
    "tall",
    "thin",
    "young",
}


def character_name_words(name):
    return re.findall(r"[A-Za-z]+", normalize_alias(name))


def lower_name_words(name):
    return [word.lower() for word in character_name_words(name)]


def is_weak_honorific_name(name):
    words = lower_name_words(name)
    return bool(words and words[0] in WEAK_HONORIFIC_PREFIXES)


def phrase_starts_like_title_case(name):
    words = normalize_alias(name).replace("-", " ").split()

    if not words:
        return False

    return all(word[:1].isupper() for word in words if word[:1].isalpha())


def looks_like_full_real_name(name):
    words = character_name_words(name)
    lowered_words = {word.lower() for word in words}

    if is_weak_honorific_name(name):
        return False

    if len(words) < 2 or len(words) > 4:
        return False

    if lowered_words & TITLE_STYLE_WORDS:
        return False

    if lowered_words & PERSON_NOUNS:
        return False

    if lowered_words & DESCRIPTOR_MARKERS:
        return False

    return all(word[:1].isupper() for word in words)


def looks_like_title_style_name(name):
    lowered_words = set(lower_name_words(name))

    if is_weak_honorific_name(name):
        return False

    return bool(lowered_words & TITLE_STYLE_WORDS) and phrase_starts_like_title_case(name)


def looks_like_stable_nickname_or_label(name):
    normalized_name = normalize_alias(name)
    words = lower_name_words(normalized_name)

    if is_weak_honorific_name(normalized_name):
        return False

    if not words or len(words) > 4:
        return False

    if looks_like_full_real_name(normalized_name) or looks_like_title_style_name(normalized_name):
        return False

    if len(words) == 1 and normalized_name[:1].isupper():
        return True

    return phrase_starts_like_title_case(normalized_name) and bool(
        set(words) & (PERSON_NOUNS | DESCRIPTOR_MARKERS)
    )


def looks_like_generic_visual_description(name):
    words = set(lower_name_words(name))

    if looks_like_title_style_name(name):
        return False

    if phrase_starts_like_title_case(name):
        return False

    return bool(words & PERSON_NOUNS) and bool(words & DESCRIPTOR_MARKERS)


def score_character_name_candidate(name):
    normalized_name = normalize_alias(name)

    if not normalized_name:
        return -1000

    if looks_like_full_real_name(normalized_name):
        return 100

    if looks_like_title_style_name(normalized_name):
        words = set(lower_name_words(normalized_name))
        return 85 if words & STRONG_TITLE_WORDS else 65

    if looks_like_stable_nickname_or_label(normalized_name):
        return 50

    if is_weak_honorific_name(normalized_name):
        return 30

    if looks_like_generic_visual_description(normalized_name):
        return 5

    return 40 if any(word[:1].isupper() for word in character_name_words(normalized_name)) else 20


def select_canonical_character_name(name, aliases):
    candidates = [name, *(aliases or [])]
    normalized_candidates = []
    seen_candidates = set()

    for candidate in candidates:
        normalized_candidate = normalize_alias(candidate)
        candidate_key = normalized_candidate.lower()

        if not normalized_candidate or candidate_key in seen_candidates:
            continue

        normalized_candidates.append(normalized_candidate)
        seen_candidates.add(candidate_key)

    if not normalized_candidates:
        return normalize_alias(name), []

    best_index, canonical_name = max(
        enumerate(normalized_candidates),
        key=lambda item: (score_character_name_candidate(item[1]), -item[0]),
    )
    canonical_key = canonical_name.lower()
    canonical_aliases = [
        candidate
        for index, candidate in enumerate(normalized_candidates)
        if index != best_index and candidate.lower() != canonical_key
    ]

    return canonical_name, canonical_aliases


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

    alias_label_key = descriptive_label_key(normalized_alias)

    if alias_label_key:
        normalized_evidence = normalize_evidence_text(evidence or "").lower()
        normalized_label = normalized_alias.lower()

        if normalized_label not in normalized_evidence:
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
    return looks_like_full_real_name(name)


def is_descriptive_or_title_name(name):
    return (
        looks_like_title_style_name(name)
        or looks_like_stable_nickname_or_label(name)
        or looks_like_generic_visual_description(name)
        or is_weak_honorific_name(name)
    )


def should_promote_canonical_name(current_name, new_name):
    return score_character_name_candidate(new_name) > score_character_name_candidate(current_name)


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


def canonicalize_progression_value(progression_type, value):
    if not value:
        return value

    normalized_value = normalize_alias(value)

    if progression_type != "cultivation_level":
        return normalized_value

    return re.sub(
        r"^(?:at\s+)?(?:the\s+)?peak\s+of\s+(?:the\s+)?",
        "",
        normalized_value,
        flags=re.IGNORECASE,
    ).strip()


ORDINAL_WORDS = {
    "first": 1,
    "1st": 1,
    "one": 1,
    "second": 2,
    "2nd": 2,
    "two": 2,
    "third": 3,
    "3rd": 3,
    "three": 3,
    "fourth": 4,
    "4th": 4,
    "four": 4,
    "fifth": 5,
    "5th": 5,
    "five": 5,
    "sixth": 6,
    "6th": 6,
    "six": 6,
    "seventh": 7,
    "7th": 7,
    "seven": 7,
    "eighth": 8,
    "8th": 8,
    "eight": 8,
    "ninth": 9,
    "9th": 9,
    "nine": 9,
    "tenth": 10,
    "10th": 10,
    "ten": 10,
}


def progression_compare_key(progression_type, value):
    normalized_value = normalize_value(canonicalize_progression_value(progression_type, value))

    if progression_type != "cultivation_level":
        return normalized_value

    words = normalized_value.replace("-", " ").split()
    level_number = None

    for word in words:
        clean_word = word.strip(".,:;!?()[]")

        if clean_word in ORDINAL_WORDS:
            level_number = ORDINAL_WORDS[clean_word]
            break

        if clean_word.isdigit():
            level_number = int(clean_word)
            break

    if not level_number:
        return normalized_value

    realm = None
    realm_terms = {
        "qi condensation": "qi_condensation",
        "foundation establishment": "foundation_establishment",
        "core formation": "core_formation",
        "nascent soul": "nascent_soul",
    }

    for term, realm_key in realm_terms.items():
        if term in normalized_value:
            realm = realm_key
            break

    return ("cultivation_level", realm, level_number)


def progression_keys_match(existing_key, new_key):
    if existing_key == new_key:
        return True

    if not (
        isinstance(existing_key, tuple)
        and isinstance(new_key, tuple)
        and len(existing_key) == 3
        and len(new_key) == 3
    ):
        return False

    _, existing_realm, existing_level = existing_key
    _, new_realm, new_level = new_key

    if existing_level != new_level:
        return False

    return existing_realm is None or new_realm is None or existing_realm == new_realm


def is_more_specific_progression_value(progression_type, existing_value, new_value):
    if progression_type == "cultivation_level" and progression_values_match(
        progression_type,
        existing_value,
        new_value,
    ):
        return False

    return len(normalize_value(new_value)) > len(normalize_value(existing_value))


def progression_values_match(progression_type, first_value, second_value):
    if not first_value or not second_value:
        return False

    first_key = progression_compare_key(progression_type, first_value)
    second_key = progression_compare_key(progression_type, second_value)
    return progression_keys_match(first_key, second_key)


def normalize_progression_type(progression_type):
    normalized_type = progression_type.strip().lower().replace(" ", "_")

    if normalized_type in {"cultivation", "cultivation_rank", "realm"}:
        return "cultivation_level"

    if normalized_type in {"sect_rank", "sect_position", "role", "status", "occupation"}:
        return "position"

    if normalized_type not in {"cultivation_level", "position", "class_rank", "power_rank"}:
        return "power_rank"

    return normalized_type


def is_valid_position_progression(new_value):
    normalized_value = normalize_value(new_value)
    blocked_action_terms = {
        "acquired",
        "accepted",
        "bought",
        "collected",
        "consumed",
        "earned",
        "found",
        "given",
        "gifted",
        "got",
        "obtained",
        "picked up",
        "purchased",
        "received",
        "receives",
        "sold",
        "took",
        "used",
        "uses",
        "was given",
        "was gifted",
        "was handed",
        "was rewarded",
        "won",
    }
    blocked_item_terms = {
        "artifact",
        "bag",
        "bottle",
        "elixir",
        "essence",
        "gourd",
        "jade",
        "manual",
        "medicine",
        "mirror",
        "pendant",
        "pill",
        "resource",
        "reward",
        "robe",
        "slip",
        "spirit stone",
        "stone",
        "tablet",
        "treasure",
    }

    if any(term in normalized_value for term in blocked_action_terms):
        return False

    if any(term in normalized_value for term in blocked_item_terms):
        return False

    return True


def is_valid_progression_value(progression_type, new_value):
    if progression_type == "position":
        return is_valid_position_progression(new_value)

    return True


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
        "already at",
        "currently at",
        "currently remains",
        "did not change",
        "has not changed",
        "no change",
        "remained at",
        "remains at",
        "same level",
        "still at",
        "without change",
        "without indication of change",
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


def recalculate_character_current_progression(character, progression_type):
    field_by_type = {
        "cultivation_level": "current_cultivation_level",
        "position": "current_position",
        "class_rank": "current_class_rank",
        "power_rank": "current_power_rank",
    }
    field_name = field_by_type.get(progression_type)

    if not field_name:
        return

    latest_progression = (
        CharacterProgressionEvent.query.join(
            Chapter,
            CharacterProgressionEvent.chapter_id == Chapter.id,
        )
        .filter(
            CharacterProgressionEvent.character_id == character.id,
            CharacterProgressionEvent.progression_type == progression_type,
        )
        .order_by(Chapter.chapter_number.desc(), CharacterProgressionEvent.id.desc())
        .first()
    )

    setattr(
        character,
        field_name,
        latest_progression.new_value if latest_progression else None,
    )


def find_existing_progression(character, progression_type, new_value):
    new_value_key = progression_compare_key(progression_type, new_value)
    progression_rows = CharacterProgressionEvent.query.filter_by(
        character_id=character.id,
        progression_type=progression_type,
    ).all()

    for progression in progression_rows:
        existing_key = progression_compare_key(progression.progression_type, progression.new_value)

        if progression_keys_match(existing_key, new_value_key):
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


def append_review_warning(record, warning):
    existing_warnings = record.review_warnings.splitlines() if record.review_warnings else []

    if warning not in existing_warnings:
        existing_warnings.append(warning)
        record.review_warnings = "\n".join(existing_warnings)
        return True

    return False


def character_reference_candidates(character):
    candidates = [character.name]
    candidates.extend(alias.alias for alias in character.aliases)
    normalized_candidates = []
    seen_candidates = set()

    for candidate in candidates:
        normalized_candidate = normalize_alias(candidate)
        candidate_key = normalized_candidate.lower()

        if not normalized_candidate or candidate_key in seen_candidates:
            continue

        if candidate_key in GENERIC_PERSON_LABELS:
            continue

        normalized_candidates.append(normalized_candidate)
        seen_candidates.add(candidate_key)

    return normalized_candidates


def evidence_mentions_character(evidence, character):
    evidence_key = evidence_match_key(evidence)

    if not evidence_key:
        return False

    for candidate in character_reference_candidates(character):
        candidate_key = evidence_match_key(candidate)

        if candidate_key and candidate_key in evidence_key:
            return True

    return False


def progression_duplicate_attribution_conflicts(
    novel,
    chapter,
    character,
    progression_type,
    new_value,
    evidence,
):
    evidence_key = evidence_match_key(evidence)

    if not evidence_key:
        return []

    conflicts = []
    progression_rows = CharacterProgressionEvent.query.filter_by(
        novel_id=novel.id,
        chapter_id=chapter.id,
    ).all()

    for progression in progression_rows:
        if progression.character_id == character.id:
            continue

        if progression_compare_key(progression_type, new_value) != progression_compare_key(
            progression.progression_type,
            progression.new_value,
        ):
            continue

        evidence_rows = WikiEvidence.query.filter_by(
            entity_type="progression",
            entity_id=progression.id,
        ).all()

        if any(evidence_match_key(row.evidence_text) == evidence_key for row in evidence_rows):
            conflicts.append(progression)

    return conflicts


def progression_review_warnings(
    novel,
    chapter,
    character,
    progression_type,
    new_value,
    evidence,
):
    warnings = []
    duplicate_warning = (
        "Possible duplicate progression attribution: same evidence and progression value "
        "attached to multiple characters."
    )
    missing_name_warning = "Evidence may not directly name this character."
    conflicts = progression_duplicate_attribution_conflicts(
        novel,
        chapter,
        character,
        progression_type,
        new_value,
        evidence,
    )

    if conflicts:
        warnings.append(duplicate_warning)

        for conflict in conflicts:
            append_review_warning(conflict, duplicate_warning)

    if not evidence_mentions_character(evidence, character):
        warnings.append(missing_name_warning)

    return warnings


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
                review_status="pending",
            )
            db.session.add(character)
            summary["characters_created"] += 1
            character_created = True

        db.session.flush()
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
