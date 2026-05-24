import re

from app.models import Character, CharacterProgressionEvent, Chapter, WikiEvidence


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


def _normalize_alias(alias):
    return " ".join(alias.split()).strip()


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


def _evidence_match_key(evidence_text):
    return "".join(
        character.lower()
        for character in _normalize_evidence_text(evidence_text)
        if character.isalnum() or character.isspace()
    )

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
        key = (character_name.lower(), new_value.lower(), _evidence_match_key(evidence))

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
        key = (character_name.lower(), new_value.lower(), _evidence_match_key(evidence))

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
        normalized_candidate = _normalize_alias(candidate)

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

    return _normalize_evidence_text(snippet)


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

def normalize_value(value):
    return " ".join(value.lower().split())


def canonicalize_progression_value(progression_type, value):
    if not value:
        return value

    normalized_value = _normalize_alias(value)

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
        normalized_candidate = _normalize_alias(candidate)
        candidate_key = normalized_candidate.lower()

        if not normalized_candidate or candidate_key in seen_candidates:
            continue

        if candidate_key in GENERIC_PERSON_LABELS:
            continue

        normalized_candidates.append(normalized_candidate)
        seen_candidates.add(candidate_key)

    return normalized_candidates


def evidence_mentions_character(evidence, character):
    evidence_key = _evidence_match_key(evidence)

    if not evidence_key:
        return False

    for candidate in character_reference_candidates(character):
        candidate_key = _evidence_match_key(candidate)

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
    evidence_key = _evidence_match_key(evidence)

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

        if any(_evidence_match_key(row.evidence_text) == evidence_key for row in evidence_rows):
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
