import re

from app.models import Character, CharacterAlias, db


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


def _normalize_evidence_text(evidence_text):
    return (
        " ".join(evidence_text.split())
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("…", "...")
        .strip("\"'")
    )


def _find_existing_by_name(model, novel, name):
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
        character = _find_existing_by_name(Character, novel, candidate)

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
        normalized_evidence = _normalize_evidence_text(evidence or "").lower()
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
            evidence=_normalize_evidence_text(evidence)[:500] if evidence else None,
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
