import re

from app.models import Character, CharacterProgressionEvent, Chapter, WikiEvidence
from app.services.extraction.identity import alias_is_useful_for_resolution


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
    r"\b(now|currently|current|foundation|base|cultivation|at|is|was|am|"
    r"had reached|has reached|have reached|finally reached|reached|achieved)\b",
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

INVALID_PROGRESSION_PLACEHOLDER_VALUES = {
    "?",
    "-",
    "--",
    "n/a",
    "na",
    "none",
    "not applicable",
    "not available",
    "not given",
    "not mentioned",
    "not provided",
    "not specified",
    "not stated",
    "null",
    "tbd",
    "to be determined",
    "uncertain",
    "unclear",
    "undetermined",
    "unknown",
    "unknown level",
    "unknown rank",
    "unknown realm",
    "unknown stage",
    "unspecified",
}

INVALID_PROGRESSION_PLACEHOLDER_PATTERNS = (
    r"^\?+$",
    r"^(?:currently\s+)?(?:unknown|unclear|unspecified|undetermined)$",
    r"^(?:not|no)\s+(?:clear\s+)?(?:stated|specified|known|provided|available|mentioned)\s+(?:level|rank|realm|stage|state|status|value)?$",
    r"^(?:level|rank|realm|stage|state|status)\s+(?:unknown|unclear|unspecified|not\s+stated)$",
)

PROGRESSION_DISTRIBUTIVE_PATTERNS = (
    r"\bboth\b",
    r"\beach\b",
    r"\ball\s+(?:of\s+)?(?:three|four|five|six|seven|eight|nine|ten|\d+|them)\b",
    r"\bthe\s+two\s+of\s+them\b",
    r"\bboth\s+of\s+whom\b",
    r"\brespectively\b",
)
PROGRESSION_AMBIGUOUS_DISTRIBUTIVE_PATTERNS = (
    r"\bone\s+of\s+(?:them|whom)\b",
    r"\bsome\s+of\s+(?:them|whom)\b",
)

PROGRESSION_DAMAGE_VALUE_TERMS = {
    "abolished",
    "broken",
    "crippled",
    "damaged",
    "destroyed",
    "sealed",
    "shattered",
}
PROGRESSION_DAMAGE_TARGET_TERMS = {
    "core",
    "cultivation",
    "cultivation base",
    "cultivation foundation",
    "dantian",
    "foundation",
    "realm",
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
        evidence = snippet_around_match(text, match, following_sentences=2)
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
    same_sentence_start = max(
        text.rfind(".", 0, start),
        text.rfind("!", 0, start),
        text.rfind("?", 0, start),
        text.rfind("\n", 0, start),
    ) + 1
    same_sentence_end = sentence_boundary_after(text, end)
    same_sentence = text[same_sentence_start: same_sentence_end + 1]

    same_sentence_candidate = closest_progression_candidate(
        same_sentence,
        same_sentence_start,
        start,
        end,
        candidate_names,
        prefer_before=True,
    )

    return same_sentence_candidate


def closest_progression_candidate(
    context,
    context_start,
    progression_start,
    progression_end,
    candidate_names,
    prefer_before=False,
):
    best_candidate = None
    best_distance = None
    best_match_key = None
    ambiguous = False

    for candidate in candidate_names:
        for variant in progression_candidate_variants(candidate):
            for match in progression_reference_matches(variant, context):
                absolute_start = context_start + match.start()
                absolute_end = context_start + match.end()

                if prefer_before and absolute_start > progression_end:
                    continue

                distance = min(
                    abs(progression_start - absolute_end),
                    abs(progression_end - absolute_start),
                )

                if best_distance is None or distance < best_distance:
                    best_candidate = candidate
                    best_distance = distance
                    best_match_key = match.group(0).lower()
                    ambiguous = False
                elif (
                    distance == best_distance
                    and candidate != best_candidate
                    and match.group(0).lower() != best_match_key
                ):
                    ambiguous = True

    return None if ambiguous else best_candidate


def progression_candidate_variants(candidate):
    normalized_candidate = _normalize_alias(candidate)
    variants = [normalized_candidate]
    words = normalized_candidate.split()
    removable_title_prefixes = {
        "Big",
        "Brother",
        "Elder",
        "Grand",
        "Grandpa",
        "Junior",
        "Little",
        "Master",
        "Senior",
        "Sister",
    }

    if len(words) >= 3 and words[0] in removable_title_prefixes:
        variants.append(" ".join(words[1:]))

    unique_variants = []
    seen = set()

    for variant in variants:
        variant_key = variant.lower()

        if variant and variant_key not in seen:
            unique_variants.append(variant)
            seen.add(variant_key)

    return unique_variants


def progression_reference_matches(variant, context):
    if not variant:
        return []

    pattern = re.compile(rf"(?<!\w){re.escape(variant)}(?!\w)", re.IGNORECASE)
    return pattern.finditer(context)


def text_contains_progression_reference(text, variant):
    return any(progression_reference_matches(variant, text))


def snippet_around_match(text, match, following_sentences=0):
    start = match.start()
    end = match.end()
    left_boundary = max(
        text.rfind(".", 0, start),
        text.rfind("!", 0, start),
        text.rfind("?", 0, start),
        text.rfind("\n", 0, start),
    )
    right_boundary = sentence_boundary_after(text, end, following_sentences)
    snippet = text[left_boundary + 1: right_boundary + 1].strip()

    if len(snippet) > 500:
        snippet = text[max(0, start - 180): min(len(text), end + 220)].strip()

    return _normalize_evidence_text(snippet)


def sentence_boundary_after(text, start, following_sentences=0):
    search_from = start
    boundary = -1

    for _ in range(following_sentences + 1):
        right_candidates = [
            index
            for index in (
                text.find(".", search_from),
                text.find("!", search_from),
                text.find("?", search_from),
                text.find("\n", search_from),
            )
            if index != -1
        ]

        if not right_candidates:
            return min(len(text) - 1, start + 220)

        boundary = min(right_candidates)
        search_from = boundary + 1

    return boundary


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

    return _normalize_alias(value)


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

PROGRESSION_ARTICLES = {"a", "an", "the"}
PROGRESSION_FILLER_WORDS = PROGRESSION_ARTICLES | {"at", "of", "to"}
PROGRESSION_DIMENSION_WORDS = {
    "circle",
    "class",
    "grade",
    "layer",
    "level",
    "rank",
    "realm",
    "stage",
    "step",
    "tier",
}
PROGRESSION_MODIFIER_WORDS = {
    "completed": "completed",
    "complete": "completed",
    "early": "early",
    "half": "half-step",
    "halfstep": "half-step",
    "initial": "early",
    "late": "late",
    "middle": "middle",
    "mid": "middle",
    "peak": "peak",
}
NEAR_PROGRESSION_MODIFIER_WORDS = {
    "almost": "near",
    "approaching": "near",
    "close": "near",
    "nearly": "near",
    "verge": "near",
}


def normalized_progression_words(value):
    return re.findall(r"[a-z0-9]+", normalize_value(value).replace("-", " "))


def progression_number_from_word(word):
    clean_word = word.strip(".,:;!?()[]")

    if clean_word in ORDINAL_WORDS:
        return ORDINAL_WORDS[clean_word]

    ordinal_match = re.match(r"^(\d+)(?:st|nd|rd|th)$", clean_word)

    if ordinal_match:
        return int(ordinal_match.group(1))

    if clean_word.isdigit():
        try:
            return int(clean_word)
        except ValueError:
            return None

    return None


def semantic_progression_modifier(words):
    modifiers = []
    word_set = set(words)

    if "half" in word_set and "step" in word_set:
        modifiers.append("half-step")

    for word in words:
        modifier = PROGRESSION_MODIFIER_WORDS.get(word) or NEAR_PROGRESSION_MODIFIER_WORDS.get(word)

        if modifier and modifier not in modifiers:
            modifiers.append(modifier)

    return "+".join(modifiers) if modifiers else None


def semantic_progression_dimension(words):
    for word in words:
        if word in PROGRESSION_DIMENSION_WORDS:
            return word

    return None


def semantic_progression_system(words, level_number, dimension, modifier):
    system_words = []

    for word in words:
        if word in PROGRESSION_FILLER_WORDS:
            continue

        if word in PROGRESSION_DIMENSION_WORDS:
            continue

        if word in PROGRESSION_MODIFIER_WORDS or word in NEAR_PROGRESSION_MODIFIER_WORDS:
            continue

        if modifier == "half-step" and word in {"half", "step"}:
            continue

        if progression_number_from_word(word) == level_number:
            continue

        system_words.append(word)

    return " ".join(system_words) or None


def semantic_progression_key(progression_type, value):
    normalized_value = normalize_value(canonicalize_progression_value(progression_type, value))
    words = normalized_progression_words(normalized_value)

    if not words:
        return normalized_value

    level_number = None

    for word in words:
        level_number = progression_number_from_word(word)

        if level_number is not None:
            break

    modifier = semantic_progression_modifier(words)
    dimension = semantic_progression_dimension(words)
    system = semantic_progression_system(words, level_number, dimension, modifier)

    if level_number is not None or dimension:
        semantic_value = level_number if level_number is not None else system
        semantic_system = system if level_number is not None else None

        return (
            "semantic_progression",
            progression_type,
            dimension,
            semantic_value,
            modifier,
            semantic_system,
        )

    article_free_words = [
        word
        for word in words
        if word not in PROGRESSION_ARTICLES
    ]
    return ("literal_progression", progression_type, " ".join(article_free_words))


def progression_compare_key(progression_type, value):
    progression_type = normalize_progression_type(progression_type)
    return semantic_progression_key(progression_type, value)


def progression_keys_match(existing_key, new_key):
    if existing_key == new_key:
        return True

    if not (
        isinstance(existing_key, tuple)
        and isinstance(new_key, tuple)
        and len(existing_key) == 6
        and len(new_key) == 6
        and existing_key[0] == "semantic_progression"
        and new_key[0] == "semantic_progression"
    ):
        return False

    _, existing_type, existing_dimension, existing_value, existing_modifier, existing_system = existing_key
    _, new_type, new_dimension, new_value, new_modifier, new_system = new_key

    if existing_type != new_type:
        return False

    if existing_dimension != new_dimension:
        return False

    if existing_value != new_value:
        return False

    if existing_modifier != new_modifier:
        return False

    return existing_system is None or new_system is None or existing_system == new_system


def progression_key_specificity(key):
    if not isinstance(key, tuple):
        return 0

    if len(key) == 6 and key[0] == "semantic_progression":
        _, _, dimension, value, modifier, system = key
        return sum(1 for part in (dimension, value, modifier, system) if part is not None)

    return len(str(key))


def progression_key_has_omitted_system_match(key):
    return (
        isinstance(key, tuple)
        and len(key) == 6
        and key[0] == "semantic_progression"
        and key[5] is None
    )


def is_more_specific_progression_value(progression_type, existing_value, new_value):
    existing_key = progression_compare_key(progression_type, existing_value)
    new_key = progression_compare_key(progression_type, new_value)

    if progression_values_match(progression_type, existing_value, new_value):
        return progression_key_specificity(new_key) > progression_key_specificity(existing_key)

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
    normalized_value = _normalize_evidence_text(new_value or "").lower()
    normalized_value = normalized_value.strip(" .,:;!?()[]{}\"'")

    if not normalized_value:
        return False

    if normalized_value in INVALID_PROGRESSION_PLACEHOLDER_VALUES:
        return False

    if any(
        re.search(pattern, normalized_value)
        for pattern in INVALID_PROGRESSION_PLACEHOLDER_PATTERNS
    ):
        return False

    if progression_type == "position":
        return is_valid_position_progression(new_value)

    return True


def progression_value_has_damage_semantics(progression_type, new_value, evidence="", description=""):
    normalized_type = normalize_progression_type(progression_type)
    normalized_value = _normalize_evidence_text(new_value or "").lower()
    normalized_context = _normalize_evidence_text(f"{evidence} {description}").lower()
    value_words = set(re.findall(r"[a-z0-9]+", normalized_value))

    if not normalized_value or normalized_type == "position":
        return False

    if normalized_value in PROGRESSION_DAMAGE_VALUE_TERMS:
        return True

    if not (value_words & PROGRESSION_DAMAGE_VALUE_TERMS):
        return False

    if value_words & {"level", "rank", "realm", "stage", "tier", "circle", "grade"}:
        return False

    return any(term in normalized_value or term in normalized_context for term in PROGRESSION_DAMAGE_TARGET_TERMS)


def progression_statement_is_not_yet_achieved(text):
    normalized_text = _normalize_evidence_text(text or "").lower()
    patterns = (
        r"\bselected\s+(?:him|her|them|[a-z][a-z'\-]*(?:\s+[a-z][a-z'\-]*){0,3})\s+to\s+be\s+promoted\b",
        r"\bchosen\s+(?:him|her|them|[a-z][a-z'\-]*(?:\s+[a-z][a-z'\-]*){0,3})\s+to\s+be\s+promoted\b",
        r"\b(?:selected|chosen|slated|scheduled)\s+to\s+be\s+promoted\b",
        r"\bto\s+be\s+promoted\s+to\b",
        r"\bwill\s+be\s+promoted\b",
        r"\bwould\s+be\s+promoted\b",
        r"\bcan\s+be\s+promoted\b",
        r"\bcould\s+be\s+promoted\b",
        r"\beligible\s+for\s+promotion\b",
        r"\b(?:will|would|could|might)\s+soon\s+(?:reach|become|enter|advance|break\s+through|be\s+promoted)\b",
        r"\bsoon\s+(?:reach|become|enter|advance|break\s+through|be\s+promoted)\b",
        r"\bexpected\s+to\s+(?:reach|become|enter|advance|break\s+through)\b",
        r"\bpotential\s+to\s+(?:reach|become|enter|advance|break\s+through)\b",
    )
    return any(re.search(pattern, normalized_text) for pattern in patterns)


def progression_statement_is_temporary_or_comparative(text):
    normalized_text = _normalize_evidence_text(text or "").lower()
    patterns = (
        r"\btemporar(?:y|ily)\b",
        r"\bbriefly\b",
        r"\bfor\s+(?:a|one)\s+(?:brief\s+)?moment\b",
        r"\bcomparable\s+to\b",
        r"\bequivalent\s+to\b",
        r"\bon\s+par\s+with\b",
        r"\bas\s+strong\s+as\b",
        r"\bstrength\s+of\s+(?:a\s+|an\s+|the\s+)?(?:\w+\s+){0,5}(?:level|rank|realm|stage|tier|circle)\b",
        r"\baura\s+(?:like|comparable\s+to|equivalent\s+to)\b",
        r"\bpower\s+(?:like|comparable\s+to|equivalent\s+to|approaching)\b",
        r"\bcould\s+(?:fight|battle|contend\s+with|match)\b",
        r"\bwhile\s+using\b.*\b(?:fought|fight|battle|power|strength|aura|realm|level|rank|stage)\b",
    )
    return any(re.search(pattern, normalized_text) for pattern in patterns)


def _contains_progression_value(text, new_value):
    normalized_text = _normalize_evidence_text(text or "").lower()
    normalized_value = _normalize_evidence_text(new_value or "").lower()

    if not normalized_text or not normalized_value:
        return False

    if normalized_value in normalized_text:
        return True

    if normalized_value.replace(" of ", " ") in normalized_text.replace(" of ", " "):
        return True

    def without_articles(value):
        return " ".join(
            word for word in value.split() if word not in {"a", "an", "the"}
        )

    article_free_text = without_articles(normalized_text)
    article_free_value = without_articles(normalized_value)

    if article_free_value and article_free_value in article_free_text:
        return True

    value_words = normalized_value.split()

    return len(value_words) >= 2 and " ".join(value_words[:2]) in normalized_text


def _progression_value_index(text, new_value):
    normalized_text = _normalize_evidence_text(text or "").lower()
    normalized_value = _normalize_evidence_text(new_value or "").lower()

    if not normalized_text or not normalized_value:
        return -1

    index = normalized_text.find(normalized_value)

    if index >= 0:
        return index

    return normalized_text.replace(" of ", " ").find(
        normalized_value.replace(" of ", " ")
    )


def _is_exclaimed_progression_value(evidence_text, new_value):
    evidence_text = _normalize_evidence_text(evidence_text or "").lower()
    new_value = _normalize_evidence_text(new_value or "").lower()

    if not evidence_text or not new_value:
        return False

    return (
        f'"{new_value}' in evidence_text
        or f"'{new_value}" in evidence_text
        or f"{new_value}!" in evidence_text
        or (
            _contains_progression_value(evidence_text, new_value)
            and evidence_text.rstrip().endswith("!")
        )
    )


def _has_breakthrough_supporting_context(local_context):
    context = _normalize_evidence_text(local_context or "").lower()
    context_indicators = {
        "advanced",
        "advancement",
        "aura",
        "awakening",
        "battle",
        "body",
        "breakthrough",
        "broke through",
        "cultivat",
        "cultivation base",
        "energy",
        "enlightenment",
        "essence",
        "expelled",
        "filth",
        "foundation",
        "internal energy",
        "level up",
        "level-up",
        "meditat",
        "pill",
        "power",
        "rank up",
        "rank-up",
        "realm",
        "resource",
        "spiritual energy",
        "system",
        "training",
        "transformation",
        "tribulation",
    }

    return any(indicator in context for indicator in context_indicators)


def is_confirmed_progression(progression, local_context=None):
    if not is_valid_progression_value(
        normalize_progression_type(progression.progression_type),
        progression.new_value,
    ):
        return False

    progression_type = normalize_progression_type(progression.progression_type)
    text = f"{progression.new_value} {progression.description} {progression.evidence}".lower()
    evidence_text = (progression.evidence or "").lower()

    if progression_value_has_damage_semantics(
        progression_type,
        progression.new_value,
        evidence=progression.evidence,
        description=progression.description,
    ):
        return False

    if progression_statement_is_not_yet_achieved(text):
        return False

    if progression_statement_is_temporary_or_comparative(text):
        return False

    blocked_terms = {
        "approaching",
        "almost",
        "nearly",
        "close to",
        "hair away",
        "just a hair",
        "sliver away",
        "just a sliver",
        "on the verge",
        "not far from",
        "one step away",
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
        "selected to be promoted",
        "selected him to be promoted",
        "selected her to be promoted",
        "selected them to be promoted",
        "chosen to be promoted",
        "chosen him to be promoted",
        "chosen her to be promoted",
        "chosen them to be promoted",
        "to be promoted",
        "will be promoted",
        "would be promoted",
        "can be promoted",
        "could be promoted",
        "will soon reach",
        "would soon reach",
        "could soon reach",
        "might soon reach",
        "soon reach",
        "soon become",
        "soon enter",
        "soon advance",
        "soon break through",
        "soon be promoted",
        "path to",
        "opportunity to",
        "standstill",
        "stagnant",
        "stuck",
        "bottleneck",
        "requires more",
        "need more",
        "would require",
        "did not change",
        "has not changed",
        "no change",
        "same level",
        "without change",
        "without indication of change",
        "had not reached",
        "has not reached",
        "have not reached",
        "not reached",
        "not yet reached",
        "still had not reached",
        "still has not reached",
        "never reached",
        "never broke through",
        "had never broken through",
        "no longer at",
    }
    new_value = progression.new_value.lower()

    if any(term in new_value for term in blocked_terms):
        return False

    near_progression_terms = {
        "approaching",
        "almost",
        "nearly",
        "close to",
        "hair away",
        "just a hair",
        "sliver away",
        "just a sliver",
        "on the verge",
        "not far from",
        "one step away",
        "close to the peak",
        "close to peak",
        "almost at the peak",
        "almost at peak",
    }
    confirmation_terms = {
        "reached",
        "had reached",
        "achieved",
        "advanced",
        "broken through",
        "broke through",
        "breakthrough",
        "promoted",
        "became",
        "becomes",
        "attained",
        "entered",
        "is now",
        "was now",
        "now it was",
        "now he was",
        "now she was",
        "already at",
        "already reached",
        "is at",
        "was at",
        "were at",
        "are at",
        "has reached",
        "have reached",
        "cultivation foundation was",
        "cultivation foundation is",
        "cultivation base was",
        "cultivation base is",
        "known for",
    }
    indirect_breakthrough_terms = {
        "body thrummed",
        "filth had been excreted",
        "impurities",
        "pores",
        "eyes shone",
        "shone brilliantly",
        "spiritual energy poured",
        "cultivation foundation",
    }

    has_confirmation = any(term in text for term in confirmation_terms)
    has_indirect_breakthrough_context = any(
        term in evidence_text for term in indirect_breakthrough_terms
    )
    quoted_or_exclaimed_value = _is_exclaimed_progression_value(evidence_text, new_value)
    local_context_supports_breakthrough = (
        quoted_or_exclaimed_value
        and _contains_progression_value(local_context, new_value)
        and _has_breakthrough_supporting_context(local_context)
    )

    confirmed_value_with_later_near_context = False

    if any(term in evidence_text for term in blocked_terms):
        value_index = _progression_value_index(evidence_text, new_value)
        first_near_index = min(
            (
                evidence_text.find(term)
                for term in near_progression_terms
                if term in evidence_text
            ),
            default=-1,
        )

        if first_near_index >= 0 and (value_index < 0 or first_near_index < value_index):
            return False

        if any(term in evidence_text for term in near_progression_terms) and evidence_text.strip().startswith(
            (
                "almost",
                "close to",
                "nearly",
                "just a hair",
                "hair away",
                "not far from",
                "one step away",
                "on the verge",
            )
        ):
            return False

        has_only_near_progression_block = (
            any(term in evidence_text for term in near_progression_terms)
            and not any(
                term in text
                for term in blocked_terms - near_progression_terms
            )
        )

        confirmed_current_value_with_later_near_context = (
            has_only_near_progression_block
            and has_confirmation
            and _contains_progression_value(evidence_text, new_value)
        )

        confirmed_exclamation_with_later_near_context = (
            has_only_near_progression_block
            and quoted_or_exclaimed_value
            and (has_indirect_breakthrough_context or local_context_supports_breakthrough)
        )

        if not (
            confirmed_current_value_with_later_near_context
            or confirmed_exclamation_with_later_near_context
        ):
            return False

        confirmed_value_with_later_near_context = True

    if quoted_or_exclaimed_value and (
        has_indirect_breakthrough_context or local_context_supports_breakthrough
    ):
        return True

    if not confirmed_value_with_later_near_context and any(term in text for term in blocked_terms):
        return False

    return has_confirmation


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
            CharacterProgressionEvent.review_status == "approved",
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
        review_status="approved",
    ).all()
    matches = []

    for progression in progression_rows:
        existing_key = progression_compare_key(progression.progression_type, progression.new_value)

        if progression_keys_match(existing_key, new_value_key):
            matches.append(progression)

    if len(matches) == 1:
        return matches[0]

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
    candidates.extend(
        alias.alias
        for alias in character.aliases
        if alias_is_useful_for_resolution(alias.alias)
    )
    normalized_candidates = []
    seen_candidates = set()

    for candidate in candidates:
        for normalized_candidate in progression_candidate_variants(candidate):
            candidate_key = normalized_candidate.lower()

            if not normalized_candidate or candidate_key in seen_candidates:
                continue

            normalized_candidates.append(normalized_candidate)
            seen_candidates.add(candidate_key)

    return normalized_candidates


def evidence_mentions_character(evidence, character):
    if not evidence:
        return False

    for candidate in character_reference_candidates(character):
        if text_contains_progression_reference(evidence, candidate):
            return True

    return False


def progression_evidence_has_distributive_attribution(evidence):
    normalized_evidence = _normalize_evidence_text(evidence or "").lower()

    if not normalized_evidence:
        return False

    if any(
        re.search(pattern, normalized_evidence)
        for pattern in PROGRESSION_AMBIGUOUS_DISTRIBUTIVE_PATTERNS
    ):
        return False

    return any(
        re.search(pattern, normalized_evidence)
        for pattern in PROGRESSION_DISTRIBUTIVE_PATTERNS
    )


def progression_duplicate_attribution_conflicts(
    novel,
    chapter,
    character,
    progression_type,
    new_value,
    evidence,
):
    if progression_evidence_has_distributive_attribution(evidence):
        return []

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

        if not progression_keys_match(
            progression_compare_key(progression_type, new_value),
            progression_compare_key(progression.progression_type, progression.new_value),
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
