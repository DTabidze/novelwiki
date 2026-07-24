import json
import re
from dataclasses import dataclass, field

from flask import current_app

from app.models import (
    Character,
    CharacterItem,
    CharacterProgressionEvent,
    CharacterSkill,
    Chapter,
    Item,
    Skill,
)
from app.services.extraction.evidence import (
    get_evidence_context,
    get_evidence_discourse_context,
    verify_evidence_text,
)
from app.services.extraction.attribution import (
    attribution_matches_character,
    resolve_character_attribution,
)
from app.services.extraction.identity import (
    descriptive_label_key,
    is_trackable_character_name,
    looks_like_full_real_name,
    looks_like_generic_visual_description,
    looks_like_stable_nickname_or_label,
    looks_like_title_style_name,
)
from app.services.extraction.progression import (
    character_reference_candidates,
    progression_compare_key,
)


SERIOUS_RISK_FLAGS = {
    "attribution_uncertain",
    "missing_evidence",
    "evidence_not_exact",
    "evidence_match_ambiguous",
    "conflicts_with_database",
    "ambiguous_owner",
    "speculative_statement",
    "future_statement",
    "uncertain_statement",
    "relationship_action_not_proven",
    "relationship_action_ambiguous",
    "relationship_attribution_uncertain",
    "relationship_actor_unresolved",
    "relationship_context_ambiguous",
    "relationship_context_unavailable",
    "relationship_intent_only",
    "relationship_item_uncertain",
    "relationship_pronoun_ambiguous",
    "relationship_skill_uncertain",
    "relationship_target_not_supported",
    "relationship_target_unresolved",
    "relationship_vague_item_reference",
    "item_type_uncertain",
    "possible_location_not_item",
    "possible_organization_not_item",
    "non_item_semantics",
    "life_event_evidence_weak",
    "life_event_attribution_uncertain",
    "life_event_not_confirmed",
    "character_identity_not_directly_supported",
    "non_character_entity",
}

ENTITY_ORIGIN_EXISTING = "existing_before_extraction"
ENTITY_ORIGIN_NEW = "newly_created_this_chapter"
ENTITY_ORIGIN_UNRESOLVED = "unresolved"

SPECULATIVE_TERMS = {
    "almost",
    "close to",
    "nearly",
    "perhaps",
    "maybe",
    "might",
    "could",
    "should be able",
    "would be able",
    "i think",
    "i believe",
    "not yet",
    "preparing to",
    "attempting to",
    "on the verge",
}

FUTURE_TERMS = {
    "will reach",
    "would reach",
    "can reach",
    "could reach",
    "might reach",
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
    "later",
    "future",
    "if he",
    "if she",
    "if they",
    "if i",
}
FUTURE_TERM_PATTERNS = {
    "if he": re.compile(r"(?<!\bas\s)\bif\s+he\b"),
    "if she": re.compile(r"(?<!\bas\s)\bif\s+she\b"),
    "if they": re.compile(r"(?<!\bas\s)\bif\s+they\b"),
    "if i": re.compile(r"(?<!\bas\s)\bif\s+i\b"),
}

DEATH_EVENT_TERMS = {
    "corpse",
    "dead",
    "dead body",
    "death",
    "deceased",
    "died",
    "killed",
    "lifeless",
    "slain",
}

DEATH_EVENT_STRONG_PATTERNS = (
    r"\bdead\b",
    r"\bdied\b",
    r"\bdeath\b",
    r"\bdeceased\b",
    r"\bkilled\b",
    r"\bslain\b",
    r"\bcorpse\b",
    r"\blifeless\b",
    r"\bno\s+longer\s+alive\b",
    r"\bdead\s+body\b",
    r"\bbody\s+(?:was|is)\s+dead\b",
    r"\bfatal(?:ly)?\b",
)

LIFE_EVENT_WEAK_HARM_TERMS = {
    "blood",
    "collapsed",
    "defeated",
    "disappeared",
    "dropped",
    "fell",
    "injured",
    "wounded",
}

LIFE_EVENT_DETAIL_SPECULATIVE_TERMS = {
    "apparently",
    "could have",
    "likely",
    "maybe",
    "might have",
    "must have",
    "perhaps",
    "possibly",
    "presumably",
    "probably",
    "rumor",
    "rumors said",
    "seemed",
    "seems to have",
}

LIFE_EVENT_CORE_DETAIL_WORDS = DEATH_EVENT_TERMS | {
    "character",
    "confirmed",
    "event",
    "occurred",
}

LIFE_EVENT_DETAIL_STOP_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "he",
    "her",
    "hers",
    "him",
    "his",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "she",
    "that",
    "the",
    "their",
    "them",
    "then",
    "they",
    "this",
    "to",
    "was",
    "were",
    "with",
}

LIFE_EVENT_CAUSE_SUPPORT_PATTERNS = (
    r"\bafter\s+being\b",
    r"\bbecause\b",
    r"\bbeheaded\b",
    r"\bcaused\s+by\b",
    r"\bdue\s+to\b",
    r"\bexecuted\b",
    r"\bfell\s+(?:from|off)\b",
    r"\bfrom\s+(?:the\s+)?(?:attack|blow|fall|wound|poison|curse)\b",
    r"\bkilled\s+by\b",
    r"\bknocked\s+(?:from|off)\b",
    r"\bmurdered\b",
    r"\bpoisoned\b",
    r"\bslain\s+by\b",
    r"\bstabbed\b",
    r"\bstruck\s+by\b",
    r"\bthrown\s+(?:from|off)\b",
)

PROGRESSION_REALM_TERMS = {
    "condensation",
    "establishment",
    "formation",
    "nascent",
    "realm",
    "rank",
    "stage",
    "circle",
}

PROGRESSION_POSITION_TERMS = {
    "apprentice",
    "disciple",
    "mage",
    "sect",
    "servant",
    "warrior",
}

PROGRESSION_ORDINAL_TERMS = {
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

PROGRESSION_SYSTEM_TERMS = {
    "bronze",
    "class",
    "condensation",
    "core",
    "cultivation",
    "establishment",
    "formation",
    "foundation",
    "level",
    "mage",
    "nascent",
    "outer",
    "qi",
    "rank",
    "realm",
    "sect",
    "soul",
    "stage",
    "warrior",
}

QUESTION_UNCERTAIN_TERMS = {
    "is it",
    "are they",
    "could it be",
    "could they be",
    "seems like",
    "seemed like",
}

BASE_WEAK_ENTITY_NAMES = {
    "he",
    "she",
    "they",
    "someone",
    "somebody",
    "the man",
    "the woman",
    "disciple",
    "cultivator",
    "servant",
}

CHARACTER_ROLE_NOUNS = {
    "boy",
    "companion",
    "cultivator",
    "disciple",
    "elder",
    "fellow",
    "girl",
    "guard",
    "man",
    "servant",
    "teenager",
    "woman",
    "youth",
}

DESCRIPTIVE_CHARACTER_MODIFIERS = {
    "aged",
    "black",
    "chubby",
    "clean",
    "clad",
    "clever",
    "eyed",
    "faced",
    "fat",
    "haired",
    "injured",
    "looking",
    "masked",
    "middle",
    "old",
    "pock",
    "pudgy",
    "robed",
    "shrewd",
    "short",
    "tall",
    "thin",
    "white",
    "young",
}

GENERIC_ITEM_NOUNS = {
    "bag",
    "blade",
    "bottle",
    "gourd",
    "manual",
    "map",
    "mirror",
    "pendant",
    "pill",
    "robe",
    "scroll",
    "slip",
    "stone",
    "sword",
    "token",
}

GENERIC_ITEM_MODIFIERS = {
    "black",
    "blue",
    "broken",
    "common",
    "dark",
    "green",
    "grey",
    "flying",
    "heavy",
    "large",
    "little",
    "medicinal",
    "old",
    "ordinary",
    "plain",
    "red",
    "small",
    "storage",
    "tiny",
    "white",
    "wooden",
}

ITEM_ARTIFACT_NOUNS = {
    "artifact",
    "banner",
    "bell",
    "cauldron",
    "cicada",
    "flame",
    "mirror",
    "pagoda",
    "pennant",
    "seal",
    "treasure",
}

ITEM_TREASURE_NOUNS = {
    "treasure",
}

ITEM_MANUAL_NOUNS = {
    "book",
    "inscription",
    "jade",
    "manual",
    "record",
    "scripture",
    "slip",
    "sutra",
    "tablet",
    "tome",
}

ITEM_RESOURCE_NOUNS = {
    "crystal",
    "elixir",
    "essence",
    "flame",
    "medicine",
    "pill",
    "resource",
    "stone",
}

ITEM_WEAPON_NOUNS = {
    "axe",
    "blade",
    "bow",
    "dagger",
    "saber",
    "spear",
    "staff",
    "sword",
}

ITEM_PHYSICAL_MEDIUM_NOUNS = {
    "book",
    "inscription",
    "jade",
    "manual",
    "map",
    "record",
    "scroll",
    "scripture",
    "slip",
    "tablet",
    "talisman",
    "tome",
}

LOCATION_NOUNS = {
    "arena",
    "battlefield",
    "building",
    "cave",
    "city",
    "forest",
    "hall",
    "kingdom",
    "mountain",
    "pavilion",
    "realm",
    "region",
    "residence",
    "room",
    "valley",
    "village",
    "workshop",
}

ORGANIZATION_NOUNS = {
    "army",
    "association",
    "clan",
    "faction",
    "family",
    "guild",
    "organization",
    "school",
    "sect",
}

GENERIC_SKILL_TERMS = {
    "attack",
    "cultivation",
    "flying",
    "kick",
    "meditation",
    "punch",
    "slash",
}

SKILL_FORMAL_NOUNS = {
    "ability",
    "art",
    "arts",
    "exercise",
    "exercises",
    "chant",
    "curse",
    "form",
    "hex",
    "magic",
    "mantra",
    "method",
    "spell",
    "skill",
    "technique",
    "transformation",
}

SKILL_ACTION_TERMS = {
    "activate",
    "activated",
    "cast",
    "casts",
    "cultivate",
    "cultivated",
    "learn",
    "learned",
    "perform",
    "performed",
    "practice",
    "practiced",
    "study",
    "studied",
    "unleash",
    "unleashed",
    "use",
    "used",
}

OPTIONAL_SKILL_SUFFIXES = {
    "ability",
    "art",
    "arts",
    "chant",
    "curse",
    "hex",
    "magic",
    "mantra",
    "method",
    "skill",
    "spell",
    "technique",
}

ENTITY_TYPE_SUPPORT_TERMS = {
    "item": {
        "artifact",
        "book",
        "elixir",
        "manual",
        "mirror",
        "object",
        "pill",
        "record",
        "scroll",
        "scripture",
        "slip",
        "stone",
        "sword",
        "tome",
        "treasure",
        "weapon",
    },
    "skill": {
        "activate",
        "activated",
        "art",
        "cast",
        "casts",
        "chant",
        "curse",
        "form",
        "hex",
        "mantra",
        "perform",
        "performed",
        "skill",
        "spell",
        "technique",
        "use",
        "used",
        "uses",
    },
}

UNIQUENESS_EVIDENCE_TERMS = {
    "artifact",
    "divine",
    "heavenly",
    "immortal",
    "legacy",
    "magic",
    "magical",
    "named",
    "plot-critical",
    "precious",
    "rare",
    "scripture",
    "spiritual",
    "treasure",
    "unique",
}


@dataclass
class ValidationContext:
    novel: object
    chapter: object
    fact_type: str
    entity_name: str | None = None
    value: str | None = None
    evidence: str | None = None
    character: Character | None = None
    skill: Skill | None = None
    item: Item | None = None
    relationship_type: str | None = None
    entity_origin: str = ENTITY_ORIGIN_UNRESOLVED
    source_extractors: set[str] = field(default_factory=set)
    existing_record: object | None = None
    conflict: bool = False
    ambiguous_owner: bool = False
    repeated_known_fact: bool = False
    progression_downgrade: bool = False
    attribution_uncertain: bool = False
    context_supported_attribution: bool = False
    description: str | None = None
    reason: str | None = None
    evidence_start_offset: int | None = None
    evidence_end_offset: int | None = None
    evidence_match_type: str | None = None


@dataclass
class ValidationResult:
    confidence_score: int
    risk_flags: list[str]
    auto_approved: bool


@dataclass
class EntityClassification:
    entity_type: str
    is_generic: bool
    is_distinctive: bool
    reason: str


@dataclass
class CharacterIdentityValidation:
    supported: bool
    confidence_bonus: int = 0
    risk_flags: list[str] = field(default_factory=list)
    reason: str | None = None


@dataclass
class RelationshipSemanticAnalysis:
    actor_supported: bool = False
    actor_context_supported: bool = False
    actor_ambiguous: bool = False
    candidate_actor: str | None = None
    resolved_actor: str | None = None
    actor_resolution_method: str | None = None
    target_supported: bool = False
    target_context_supported: bool = False
    target_ambiguous: bool = False
    candidate_target: str | None = None
    resolved_target: str | None = None
    target_resolution_method: str | None = None
    action_supported: bool = False
    action_ambiguous: bool = False
    candidate_canonical_action: str | None = None
    detected_semantic_action: str | None = None
    intent_only: bool = False
    completion_status: str = "unproven"
    context_available: bool = True
    evidence_match_type: str | None = None
    local_context_used: bool = False
    proven_sentence: str | None = None
    flags: list[str] = field(default_factory=list)


def normalize_text(value):
    return " ".join(str(value or "").split()).strip()


def normalized_words(value):
    return re.findall(r"[a-z0-9]+", normalize_text(value).lower().replace("-", " "))


def contains_number_or_ordinal(words):
    return bool(
        set(words) & PROGRESSION_ORDINAL_TERMS
        or any(word.isdigit() for word in words)
        or any(re.match(r"^\d+(st|nd|rd|th)$", word) for word in words)
    )


def has_short_direct_evidence(evidence):
    evidence = normalize_text(evidence)
    return bool(evidence and len(evidence) <= 500)


def text_contains_value(text, value):
    text = normalize_text(text).lower()
    value = normalize_text(value).lower()

    if not text or not value:
        return False

    if value in text:
        return True

    words = [word for word in re.findall(r"[a-z0-9]+", value) if len(word) >= 3]
    return bool(words and all(word in text for word in words[:4]))


def text_contains_exact_phrase(text, phrase):
    text = normalize_text(text)
    phrase = normalize_text(phrase)

    if not text or not phrase:
        return False

    return re.search(
        rf"(?<![A-Za-z0-9]){re.escape(phrase)}(?![A-Za-z0-9])",
        text,
        flags=re.IGNORECASE,
    ) is not None


def singularize_word(word):
    if word.endswith("ies") and len(word) > 4:
        return f"{word[:-3]}y"

    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]

    return word


def normalized_entity_words(value):
    return [singularize_word(word) for word in normalized_words(value)]


def strip_optional_skill_suffix(words):
    stripped_words = list(words)

    while stripped_words and stripped_words[-1] in OPTIONAL_SKILL_SUFFIXES:
        stripped_words.pop()

    return stripped_words


def text_contains_entity_variant(text, value, fact_type=None, relationship_backed=False):
    if text_contains_value(text, value):
        return True

    text_words = set(normalized_entity_words(text))
    value_words = normalized_entity_words(value)

    if not text_words or not value_words:
        return False

    if set(value_words).issubset(text_words):
        return True

    if fact_type == "skill":
        core_words = strip_optional_skill_suffix(value_words)

        if core_words and set(core_words).issubset(text_words):
            return True

    if fact_type == "item" and relationship_backed:
        noun_words = set(value_words) & (
            GENERIC_ITEM_NOUNS
            | ITEM_ARTIFACT_NOUNS
            | ITEM_RESOURCE_NOUNS
            | ITEM_WEAPON_NOUNS
            | ITEM_TREASURE_NOUNS
        )

        if noun_words and noun_words.issubset(text_words):
            return True

    return False


def entity_value_supported(context, value):
    if death_life_event_supported(context):
        return True

    relationship_backed = bool(
        context.character
        and (
            context.fact_type in {"character_item", "character_skill"}
            or "character_item" in context.source_extractors
            or "character_skill" in context.source_extractors
        )
    )

    if context.fact_type in {"item", "character_item"}:
        if context.fact_type == "character_item":
            supported, _, ambiguous = relationship_value_reference_status(context)
            return supported and not ambiguous

        return text_contains_entity_variant(
            context.evidence,
            value,
            fact_type="item",
            relationship_backed=relationship_backed,
        )

    if context.fact_type in {"skill", "character_skill"}:
        if value_looks_like_progression_state(value, context.evidence):
            return False

        if context.fact_type == "character_skill":
            supported, _, ambiguous = relationship_value_reference_status(context)
            return supported and not ambiguous

        return text_contains_entity_variant(
            context.evidence,
            value,
            fact_type="skill",
            relationship_backed=relationship_backed,
        )

    return text_contains_value(context.evidence, value)


def evidence_supports_entity_type(context):
    evidence_words = set(normalized_entity_words(context.evidence))
    value_words = set(normalized_entity_words(context.value or context.entity_name))
    value = context.value or context.entity_name

    if context.fact_type in {"item", "character_item"}:
        if value_looks_like_intangible_skill_concept(value):
            return False

        if value_looks_like_progression_state(value, context.evidence):
            return False

        if item_has_non_item_semantics(value, context.evidence):
            return False

        if evidence_words & ENTITY_TYPE_SUPPORT_TERMS["item"]:
            return True

        return value_has_physical_item_noun(value) or evidence_has_item_semantics(context.evidence)

    if context.fact_type in {"skill", "character_skill"}:
        if value_looks_like_physical_item_concept(value):
            return False

        if evidence_describes_physical_medium(context.evidence) and not evidence_describes_skill_action(
            context.evidence,
        ):
            return False

        if evidence_words & ENTITY_TYPE_SUPPORT_TERMS["skill"]:
            return True

        return bool(value_words & SKILL_FORMAL_NOUNS)

    return True


def death_life_event_supported(context):
    if context.fact_type != "life_event":
        return False

    if normalize_text(context.value).lower() != "death":
        return False

    return death_text_has_strong_signal(context.evidence) or death_text_has_strong_signal(
        local_context_for_evidence(context),
    )


def death_text_has_strong_signal(text):
    normalized_text = normalize_text(text).lower()

    if not normalized_text:
        return False

    return any(
        re.search(pattern, normalized_text)
        for pattern in DEATH_EVENT_STRONG_PATTERNS
    )


def life_event_text_has_weak_harm_signal(text):
    return bool(set(normalized_words(text)) & LIFE_EVENT_WEAK_HARM_TERMS)


def life_event_text_has_speculative_detail(text):
    normalized_text = normalize_text(text).lower()
    return any(term in normalized_text for term in LIFE_EVENT_DETAIL_SPECULATIVE_TERMS)


def life_event_detail_words(detail, context):
    character_words = set(normalized_words(getattr(context.character, "name", "")))
    value_words = set(normalized_words(context.value))
    ignored_words = (
        LIFE_EVENT_DETAIL_STOP_WORDS
        | LIFE_EVENT_CORE_DETAIL_WORDS
        | character_words
        | value_words
    )

    return [
        word
        for word in normalized_words(detail)
        if word not in ignored_words and len(word) > 2
    ]


def life_event_raw_text_supports_cause(detail, raw_text):
    detail_text = normalize_text(detail).lower()
    raw_text = normalize_text(raw_text).lower()

    if not detail_text or not raw_text:
        return False

    detail_words = set(normalized_words(detail_text)) - LIFE_EVENT_DETAIL_STOP_WORDS
    sentences = re.split(r"(?<=[.!?])\s+", raw_text)

    for sentence in sentences:
        sentence_words = set(normalized_words(sentence))

        if detail_words and not detail_words.issubset(sentence_words):
            continue

        if not death_text_has_strong_signal(sentence):
            continue

        if any(
            re.search(pattern, sentence)
            for pattern in LIFE_EVENT_CAUSE_SUPPORT_PATTERNS
        ):
            return True

        if re.search(r"\b(?:beheaded|executed|killed|murdered|poisoned|slain|stabbed)\b", detail_text) and re.search(
            r"\b(?:beheaded|executed|killed|murdered|poisoned|slain|stabbed)\b",
            sentence,
        ):
            return True

    return False


def life_event_detail_supported_by_raw_context(detail, context, allow_core_event=True):
    detail = normalize_text(detail)

    if not detail or context.fact_type != "life_event":
        return False

    if life_event_text_has_speculative_detail(detail):
        return False

    local_context = local_context_for_evidence(context)
    raw_support = normalize_text(" ".join([context.evidence or "", local_context]))

    if not raw_support:
        return False

    detail_words = life_event_detail_words(detail, context)

    if not detail_words:
        return bool(
            allow_core_event
            and death_life_event_supported(context)
            and life_event_attribution_supported(context)
        )

    if allow_core_event and text_contains_exact_phrase(raw_support, detail):
        return True

    raw_words = set(normalized_words(raw_support))
    matched_words = {word for word in detail_words if word in raw_words}
    required_matches = max(1, int(len(set(detail_words)) * 0.7))

    if len(matched_words) < required_matches:
        return False

    return life_event_raw_text_supports_cause(detail, raw_support)


def canonical_life_event_details(context, description=None, reason=None):
    description = normalize_text(description) or None
    reason = normalize_text(reason) or None
    flags = []

    canonical_description = description
    canonical_reason = reason

    if description and not life_event_detail_supported_by_raw_context(
        description,
        context,
        allow_core_event=True,
    ):
        canonical_description = None
        flags.append(
            "life_event_detail_speculative"
            if life_event_text_has_speculative_detail(description)
            else "life_event_detail_unsupported"
        )

    if reason and not life_event_detail_supported_by_raw_context(
        reason,
        context,
        allow_core_event=False,
    ):
        canonical_reason = None
        flags.append(
            "life_event_detail_speculative"
            if life_event_text_has_speculative_detail(reason)
            else "life_event_cause_unsupported"
        )

    return canonical_description, canonical_reason, flags


def local_context_for_evidence(context, window_size=360):
    reference_groups = []

    if context.character:
        reference_groups.append(character_reference_candidates(context.character))

    evidence_context = get_evidence_discourse_context(
        getattr(context.chapter, "content", "") if context.chapter else "",
        context.evidence,
        start_offset=context.evidence_start_offset,
        end_offset=context.evidence_end_offset,
        match_type=context.evidence_match_type,
        reference_groups=reference_groups,
    )
    return evidence_context.combined_context if evidence_context.found else context.evidence or ""


def character_reference_matches_in_text(character, text):
    if not character:
        return []

    return [
        candidate
        for candidate in character_reference_candidates(character)
        if text_contains_value(text, candidate)
    ]


def attribution_candidate_characters(context):
    if not context.novel:
        return [context.character] if context.character else []

    characters = Character.query.filter_by(novel_id=context.novel.id).all()

    if context.character and context.character not in characters:
        characters.append(context.character)

    return characters


def character_attribution_for_context(context):
    local_context = local_context_for_evidence(context)

    return resolve_character_attribution(
        mention=None,
        evidence_text=context.evidence,
        local_context=local_context,
        candidate_characters=attribution_candidate_characters(context),
        novel=context.novel,
        target_character=context.character,
        target_value=context.value,
    )


def life_event_attribution_supported(context):
    return attribution_matches_character(character_attribution_for_context(context), context.character)


def local_context_attribution_supported(context):
    return attribution_matches_character(character_attribution_for_context(context), context.character)


def relationship_attribution_status(context):
    if not context.character:
        return False, False, False

    role_supported, role_context_supported = relationship_role_attribution_status(context)

    if role_supported:
        return True, role_context_supported, False

    direct_result = resolve_character_attribution(
        mention=None,
        evidence_text=context.evidence,
        local_context=context.evidence,
        candidate_characters=attribution_candidate_characters(context),
        novel=context.novel,
        target_character=context.character,
        target_value=context.value,
    )

    if direct_result.ambiguous:
        return False, True, True

    if attribution_matches_character(direct_result, context.character):
        return True, False, False

    result = character_attribution_for_context(context)

    if result.ambiguous:
        return False, True, True

    if not attribution_matches_character(result, context.character):
        return False, False, False

    return True, result.match_type in {
        "collective_both",
        "collective_statement",
        "local_pronoun",
        "unique_object_coreference",
        "unique_possessive_pronoun",
        "unique_subject_continuity",
    }, False


def relationship_role_attribution_status(context):
    if context.fact_type not in {"character_item", "character_skill"} or not context.character:
        return False, False

    evidence = normalize_text(context.evidence)
    local_context = local_context_for_evidence(context)
    relationship_type = normalize_character_item_relationship_type(context.relationship_type)

    if relationship_role_text_supports_character(context.character, relationship_type, evidence):
        return True, False

    if local_context and local_context != evidence and relationship_role_text_supports_character(
        context.character,
        relationship_type,
        local_context,
    ):
        return True, True

    return False, False


def relationship_role_text_supports_character(character, relationship_type, text):
    if not character or not text:
        return False

    normalized_text = normalize_text(text)

    for reference in character_reference_candidates(character):
        if relationship_reference_role_supported(reference, relationship_type, normalized_text):
            return True

    return False


def relationship_reference_role_supported(reference, relationship_type, text):
    reference = normalize_text(reference)

    if not reference:
        return False

    ref_pattern = re.escape(reference)
    action_before_ref = r"(?:gave|gifted|handed|passed|presented|tossed|threw|delivered|bestowed)"
    received_actions = r"(?:accepted|caught|claimed|collected|grabbed|picked\s+up|received|snatched|took)"
    obtained_actions = r"(?:acquired|accepted|caught|claimed|collected|found|gained|got|grabbed|obtained|picked\s+up|received|snatched|took)"
    use_actions = r"(?:activated|attacked\s+with|cast|consumed|drank|drew|equipped|executed|ingested|opened|performed|poured|practiced|swallowed|used|wielded|wore)"
    gave_actions = r"(?:bestowed|delivered|gave|gifted|handed|passed|presented|tossed|threw)"
    lost_actions = r"(?:confiscated|destroyed|dropped|lost|ripped\s+away|shattered|snatched|stole|stolen|taken|took|wrenched\s+away)"
    owns_actions = r"(?:belonged\s+to|carried|carries|had|has|held|holding|owned|owns|possessed|possesses|wore|wearing)"

    patterns_by_relationship = {
        "received": [
            rf"\b{ref_pattern}\b[^.!?]{{0,80}}\b{received_actions}\b",
            rf"\b{action_before_ref}\b[^.!?]{{0,120}}\b(?:to|toward|upon|on)\s+\b{ref_pattern}\b",
            rf"\b(?:appeared|flew|shot|landed|went)\b[^.!?]{{0,120}}\b(?:into|in)\s+\b{ref_pattern}\b['’]?\s*(?:s)?\s*(?:hand|hands|bag|storage|possession)\b",
            rf"\b(?:put|placed|slipped)\b[^.!?]{{0,120}}\b(?:into|in)\s+\b{ref_pattern}\b['’]?\s*(?:s)?\s*(?:hand|hands|bag|storage|possession)\b",
        ],
        "obtained": [
            rf"\b{ref_pattern}\b[^.!?]{{0,100}}\b{obtained_actions}\b",
            rf"\b{action_before_ref}\b[^.!?]{{0,120}}\b(?:to|toward|upon|on)\s+\b{ref_pattern}\b",
            rf"\b(?:appeared|flew|shot|landed|went)\b[^.!?]{{0,120}}\b(?:into|in)\s+\b{ref_pattern}\b['’]?\s*(?:s)?\s*(?:hand|hands|bag|storage|possession)\b",
            rf"\b(?:put|placed|slipped)\b[^.!?]{{0,120}}\b(?:into|in)\s+\b{ref_pattern}\b['’]?\s*(?:s)?\s*(?:hand|hands|bag|storage|possession)\b",
        ],
        "gave": [
            rf"\b{ref_pattern}\b[^.!?]{{0,100}}\b{gave_actions}\b",
            rf"\b{ref_pattern}\b[^.!?]{{0,120}}\b(?:to|toward)\b",
        ],
        "used": [
            rf"\b{ref_pattern}\b[^.!?]{{0,100}}\b{use_actions}\b",
        ],
        "lost": [
            rf"\b{ref_pattern}\b[^.!?]{{0,100}}\b{lost_actions}\b",
            rf"\b{lost_actions}\b[^.!?]{{0,120}}\b(?:from|away\s+from)\s+\b{ref_pattern}\b",
            rf"\b(?:from|away\s+from)\s+\b{ref_pattern}\b",
        ],
        "owns": [
            rf"\b{ref_pattern}\b[^.!?]{{0,100}}\b{owns_actions}\b",
            rf"\b{ref_pattern}\b['’]s\b",
            rf"\b(?:in|inside)\s+\b{ref_pattern}\b['’]?\s*(?:s)?\s*(?:bag|hand|hands|storage|possession)\b",
        ],
    }

    patterns = patterns_by_relationship.get(relationship_type, [])

    if relationship_type == "has":
        patterns = [
            rf"\b{ref_pattern}\b[^.!?]{{0,100}}\b(?:activated|cast|cultivated|displayed|executed|learned|mastered|performed|practiced|trained|used)\b",
        ]

    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def life_event_risk_flags(context):
    if context.fact_type != "life_event":
        return []

    if normalize_text(context.value).lower() != "death":
        return []

    flags = []
    local_context = local_context_for_evidence(context)
    death_supported = death_life_event_supported(context)

    if death_supported:
        flags.append("life_event_occurrence_supported")

    if not death_supported:
        if life_event_text_has_weak_harm_signal(context.evidence) or life_event_text_has_weak_harm_signal(local_context):
            flags.append("life_event_evidence_weak")
            flags.append("life_event_occurrence_uncertain")
        else:
            flags.append("life_event_not_confirmed")
            flags.append("life_event_occurrence_uncertain")

    if not life_event_attribution_supported(context):
        flags.append("life_event_attribution_uncertain")

    if life_event_text_has_speculative_detail(context.evidence):
        flags.append("life_event_detail_speculative")
        flags.append("life_event_cause_uncertain")

    _, _, detail_flags = canonical_life_event_details(
        context,
        context.description,
        context.reason,
    )

    for detail_flag in detail_flags:
        flags.append(detail_flag)

    if "life_event_detail_speculative" in detail_flags:
        flags.append("life_event_cause_uncertain")

    return flags


def character_or_alias_in_evidence(character, evidence):
    if not character:
        return False

    return any(
        text_contains_value(evidence, candidate)
        for candidate in character_reference_candidates(character)
    )


RELATIONSHIP_ACTION_PATTERNS = {
    "obtained": [
        r"\bacquired\b",
        r"\baccepted\b",
        r"\bclaimed\b",
        r"\bcollected\b",
        r"\bended\s+up\s+in\b",
        r"\bended\s+up\s+possess(?:ed|ing)?\b",
        r"\bended\s+up\s+with\b",
        r"\bappeared\s+in\s+[^.!?]{0,80}\b(?:hand|hands|bag|storage|possession)\b",
        r"\b(?:flew|landed|shot|went)\s+[^.!?]{0,80}\b(?:into|in)\s+[^.!?]{0,80}\b(?:hand|hands|bag|storage|possession)\b",
        r"\bbestowed\s+(?:upon|on)\b",
        r"\bbestowed\s+[^.!?]{1,100}\s+(?:upon|on)\b",
        r"\bfound\b",
        r"\bgained\b",
        r"\bgot\b",
        r"\bgrabbed\b",
        r"\bhanded\s+to\b",
        r"\bobtained\b",
        r"\bpicked\s+up\b",
        r"\bpicked\s+(?:it|this|that|them)\s+up\b",
        r"\bput(?:ting)?\s+(?:it|this|that|them)?\s*into\b",
        r"\bplaced\s+into\s+[^.!?]{0,80}\b(?:hand|hands|bag|storage|possession)\b",
        r"\breceived\b",
        r"\bsnatched\b",
        r"\btook\b",
        r"\bwas\s+given\b",
        r"\bwas\s+handed\b",
        r"\bwere\s+given\b",
    ],
    "received": [
        r"\baccepted\b",
        r"\bappeared\s+in\s+[^.!?]{0,80}\b(?:hand|hands|bag|storage|possession)\b",
        r"\b(?:flew|landed|shot|went)\s+[^.!?]{0,80}\b(?:into|in)\s+[^.!?]{0,80}\b(?:hand|hands|bag|storage|possession)\b",
        r"\bbestowed\s+(?:upon|on)\b",
        r"\bbestowed\s+[^.!?]{1,100}\s+(?:upon|on)\b",
        r"\bgot\b",
        r"\bgrabbed\b",
        r"\bhanded\s+to\b",
        r"\bhanded\s+[^.!?]{1,100}\s+to\b",
        r"\bplaced\s+into\s+[^.!?]{0,80}\b(?:hand|hands|bag|storage|possession)\b",
        r"\bput(?:ting)?\s+(?:it|this|that|them)?\s*into\b",
        r"\breceived\b",
        r"\bwas\s+given\b",
        r"\bwere\s+given\b",
        r"\bwas\s+handed\b",
        r"\bwere\s+handed\b",
        r"\bcaught\b",
    ],
    "gave": [
        r"\bbestowed\b",
        r"\bdelivered\s+to\b",
        r"\bgave\b",
        r"\bgifted\b",
        r"\bhanded\b",
        r"\bhanded\s+[^.!?]{1,100}\s+to\b",
        r"\bhanded\s+over\b",
        r"\bpassed\b",
        r"\bpassed\s+[^.!?]{1,100}\s+to\b",
        r"\bpresented\b",
        r"\btossed\b",
        r"\btossed\s+[^.!?]{1,100}\s+to\b",
        r"\bthrew\b",
    ],
    "used": [
        r"\bactivated\b",
        r"\battacked\s+with\b",
        r"\bconsumed\b",
        r"\bdrank\b",
        r"\bdrew\b",
        r"\bate\b",
        r"\bequipped\b",
        r"\bfired\b",
        r"\bingested\b",
        r"\bopened\b",
        r"\bpopped\s+it\s+into\b",
        r"\bpoured\s+[^.!?]{0,80}\s+into\b",
        r"\bshined\b",
        r"\bshone\b",
        r"\bstruck\s+with\b",
        r"\bswallowed\b",
        r"\bthrew\b",
        r"\bused\b",
        r"\bwielded\b",
        r"\bwore\b",
    ],
    "lost": [
        r"\bbroke\b",
        r"\bbroken\b",
        r"\bconfiscated\b",
        r"\bdestroyed\b",
        r"\bdropped\b",
        r"\bhanded\s+over\b",
        r"\blost\b",
        r"\bno\s+longer\s+had\b",
        r"\bripped\s+away\b",
        r"\bshattered\b",
        r"\bsnatched\b",
        r"\bstole\b",
        r"\bstolen\b",
        r"\btaken\b",
        r"\btaken\s+away\b",
        r"\btook\b",
        r"\bwrenched\s+away\b",
    ],
    "owns": [
        r"\bbelonged\s+to\b",
        r"\bcarried\b",
        r"\bcarries\b",
        r"\bhad\b",
        r"\bhas\b",
        r"\bheld\b",
        r"\bholding\b",
        r"\bin\s+(?:his|her|their)\s+(?:bag|hand|hands|pocket|possession)\b",
        r"\bowned\b",
        r"\bowns\b",
        r"\bpossessed\b",
        r"\bpossesses\b",
        r"\bwore\b",
        r"\bwearing\b",
    ],
}

CHARACTER_SKILL_ACTION_PATTERNS = [
    r"\bacquired\b",
    r"\bactivated\b",
    r"\bbegan\s+(?:practicing|cultivating|training|using)\b",
    r"\bcast\b",
    r"\bcultivated\b",
    r"\bdemonstrated\b",
    r"\bdisplayed\b",
    r"\bexecuted\b",
    r"\blearned\b",
    r"\bmastered\b",
    r"\bperformed\b",
    r"\bpicked\s+up\b",
    r"\bpossessed\s+knowledge\s+of\b",
    r"\bpracticed\b",
    r"\bstarted\s+(?:practicing|cultivating|training|using)\b",
    r"\btrained\s+in\b",
    r"\bused\b",
]

RELATIONSHIP_INTENT_PATTERNS = [
    r"\babout\s+to\b",
    r"\balmost\b",
    r"\battempt(?:ed|ing)?\s+to\b",
    r"\bdemand(?:ed|s)?\b",
    r"\bhand\s+over\b",
    r"\bif\s+(?:he|she|they|i|you)\b",
    r"\bintend(?:ed|s|ing)?\s+to\b",
    r"\bmay\b",
    r"\bmight\b",
    r"\bmust\s+(?:give|hand|use|take|return|surrender)\b",
    r"\border(?:ed|s)?\s+.*\bto\b",
    r"\bplan(?:ned|s|ning)?\s+to\b",
    r"\breached\s+for\b",
    r"\bshould\s+(?:give|hand|use|take|return|surrender)\b",
    r"\bthreaten(?:ed|s)?\b",
    r"\btold\s+.*\bto\b",
    r"\bwant(?:ed|s|ing)?\s+to\b",
    r"\bwill\s+(?:give|hand|use|take|return|surrender|receive|obtain|lose)\b",
    r"\bwould\s+(?:give|hand|use|take|return|surrender|receive|obtain|lose)\b",
]

VAGUE_ITEM_REFERENCES = {
    "artifact",
    "artifacts",
    "belongings",
    "equipment",
    "goods",
    "item",
    "items",
    "object",
    "objects",
    "possessions",
    "supplies",
    "thing",
    "things",
    "treasure",
    "treasures",
    "weapon",
    "weapons",
}


OBJECT_RELATIONSHIP_PRONOUN_RE = r"(?:it|its|this|that|these|those|them|one)"
CHARACTER_RELATIONSHIP_PRONOUN_RE = r"(?:he|she|him|her|his|they|them|their)"
RELATIONSHIP_GAP = r"[^.!?]{0,120}"
RELATIONSHIP_SHORT_GAP = r"[^.!?]{0,60}"
RELATIONSHIP_ACTION_BLOCKERS = [
    r"\bdid\s+not\b",
    r"\bdidn't\b",
    r"\bnever\b",
    r"\bfailed\s+to\b",
    r"\balmost\b",
    r"\breached\s+for\b",
    r"\btr(?:y|ied|ying)\s+to\b",
    r"\bwant(?:ed|s|ing)?\s+to\b",
    r"\bcould\s+not\b",
    r"\bwas\s+unable\s+to\b",
    r"\bwere\s+unable\s+to\b",
    r"\b(?:it\s+was\s+)?rumou?red\b",
    r"\breportedly\b",
    r"\bsaid\s+to\b",
    r"\bbelieved\s+to\b",
]
RELATIONSHIP_POSSESSION_CONTAINERS = (
    "bag|bags|grasp|hand|hands|palm|palms|pocket|pockets|robe|robes|sleeve|sleeves|"
    "storage|possession|inventory|pack|packs|pouch|pouches"
)


def relationship_semantic_analysis(context):
    if context.fact_type not in {"character_item", "character_skill"}:
        return RelationshipSemanticAnalysis()

    cached = getattr(context, "_relationship_semantic_analysis", None)

    if cached is not None:
        return cached

    analysis = build_relationship_semantic_analysis(context)
    setattr(context, "_relationship_semantic_analysis", analysis)
    return analysis


def build_relationship_semantic_analysis(context):
    evidence_context = relationship_evidence_context(context)
    context_available = bool(evidence_context.found) if context.evidence else True
    sentences = relationship_context_sentences(context, evidence_context)
    local_context = evidence_context.combined_context if evidence_context.found else context.evidence or ""
    candidate_action = relationship_candidate_action(context)
    candidate_target = relationship_candidate_target_name(context)

    intent_only = any(
        relationship_evidence_is_intent_only(sentence)
        or relationship_sentence_has_action_blocker(sentence)
        for role, sentence in sentences
        if role == "evidence"
    )
    evidence_has_object_pronoun = any(
        role == "evidence" and relationship_text_has_object_pronoun(sentence)
        for role, sentence in sentences
    )

    best_actor = (False, False, False, None, None)
    best_target = (False, False, False, None, None)

    for role, sentence in sentences:
        actor_match = relationship_actor_match_for_sentence(context, sentence, local_context)
        target_match = relationship_target_match_for_sentence(context, sentence, evidence_context)

        if actor_match[2]:
            best_actor = (best_actor[0], best_actor[1], True, best_actor[3], best_actor[4])
        elif actor_match[0] and not best_actor[0] and not best_actor[2]:
            best_actor = actor_match

        if evidence_has_object_pronoun and role != "evidence" and not target_match[2]:
            continue

        if target_match[2]:
            best_target = (best_target[0], best_target[1], True, best_target[3], best_target[4])
        elif target_match[0] and not best_target[0] and not best_target[2]:
            best_target = target_match

    for _, sentence in sentences:
        actor_match = relationship_actor_match_for_sentence(context, sentence, local_context)
        target_match = relationship_target_match_for_sentence(context, sentence, evidence_context)

        if not actor_match[0] or not target_match[0] or actor_match[2] or target_match[2]:
            continue

        if relationship_evidence_is_intent_only(sentence) or relationship_sentence_has_action_blocker(sentence):
            continue

        if relationship_sentence_proves_action(
            context,
            sentence,
            actor_pattern=actor_match[3],
            target_pattern=target_match[3],
        ):
            analysis = RelationshipSemanticAnalysis(
                actor_supported=True,
                actor_context_supported=actor_match[1],
                actor_ambiguous=False,
                candidate_actor=getattr(context.character, "name", None),
                resolved_actor=getattr(context.character, "name", None),
                actor_resolution_method=actor_match[4] or "explicit_reference",
                target_supported=True,
                target_context_supported=target_match[1],
                target_ambiguous=False,
                candidate_target=candidate_target,
                resolved_target=candidate_target,
                target_resolution_method=target_match[4] or "explicit_reference",
                action_supported=True,
                intent_only=False,
                candidate_canonical_action=candidate_action,
                detected_semantic_action=candidate_action,
                completion_status="completed",
                context_available=context_available,
                evidence_match_type=evidence_context.match_type,
                local_context_used=actor_match[1] or target_match[1],
                proven_sentence=sentence,
            )
            analysis.flags = relationship_flags_from_analysis(analysis)
            return analysis

    analysis = RelationshipSemanticAnalysis(
        actor_supported=best_actor[0],
        actor_context_supported=best_actor[1],
        actor_ambiguous=best_actor[2],
        candidate_actor=getattr(context.character, "name", None),
        resolved_actor=getattr(context.character, "name", None) if best_actor[0] else None,
        actor_resolution_method=best_actor[4],
        target_supported=best_target[0],
        target_context_supported=best_target[1],
        target_ambiguous=best_target[2],
        candidate_target=candidate_target,
        resolved_target=candidate_target if best_target[0] else None,
        target_resolution_method=best_target[4],
        action_supported=False,
        candidate_canonical_action=candidate_action,
        detected_semantic_action=None,
        intent_only=intent_only,
        completion_status="intent_or_blocked" if intent_only else "unproven",
        context_available=context_available,
        evidence_match_type=evidence_context.match_type,
        local_context_used=best_actor[1] or best_target[1],
    )
    analysis.flags = relationship_flags_from_analysis(analysis)
    return analysis


def relationship_evidence_context(context):
    reference_groups = []

    if context.character:
        reference_groups.append(character_reference_candidates(context.character))

    target = context.item if context.fact_type == "character_item" else context.skill
    target_references = []

    if target:
        target_references.append(getattr(target, "name", None))
        target_references.extend(
            getattr(alias, "alias", None)
            for alias in getattr(target, "aliases", []) or []
        )

    if any(target_references):
        reference_groups.append(target_references)

    return get_evidence_discourse_context(
        getattr(context.chapter, "content", "") if context.chapter else "",
        context.evidence,
        start_offset=context.evidence_start_offset,
        end_offset=context.evidence_end_offset,
        match_type=context.evidence_match_type,
        reference_groups=reference_groups,
    )


def relationship_context_sentences(context, evidence_context):
    if evidence_context.found:
        ordered_sentences = [
            ("previous", evidence_context.previous_sentence),
            ("evidence", evidence_context.evidence_sentence),
            ("next", evidence_context.next_sentence),
        ]
    else:
        ordered_sentences = [("evidence", context.evidence)]

    sentences = []

    for role, sentence in ordered_sentences:
        sentence_parts = [
            part
            for part in re.split(r"(?<=[.!?])\s+|\n+", normalize_text(sentence))
            if normalize_text(part)
        ]

        for sentence_part in sentence_parts:
            normalized_sentence = normalize_text(sentence_part)

            if normalized_sentence and normalized_sentence not in [existing[1] for existing in sentences]:
                sentences.append((role, normalized_sentence))

    return sentences


def relationship_flags_from_analysis(analysis):
    flags = []

    if not analysis.context_available:
        flags.append("relationship_context_unavailable")

    if analysis.actor_ambiguous:
        flags.append("relationship_pronoun_ambiguous")
        flags.append("relationship_context_ambiguous")
        flags.append("relationship_actor_unresolved")
        flags.append("relationship_attribution_uncertain")

    if not analysis.actor_supported:
        flags.append("relationship_actor_unresolved")
        flags.append("relationship_attribution_uncertain")
    elif analysis.actor_context_supported:
        flags.append("relationship_context_supported")

    if analysis.target_ambiguous:
        flags.append("relationship_pronoun_ambiguous")
        flags.append("relationship_context_ambiguous")
        flags.append("relationship_target_unresolved")
    elif not analysis.target_supported:
        flags.append("relationship_target_unresolved")
        flags.append("relationship_target_not_supported")
        flags.append("relationship_evidence_weak")
    elif analysis.target_context_supported:
        flags.append("relationship_context_supported")

    if analysis.intent_only and not analysis.action_supported:
        flags.append("relationship_intent_only")

    if not analysis.action_supported:
        flags.append("relationship_action_not_proven")

    unique_flags = []

    for flag in flags:
        if flag not in unique_flags:
            unique_flags.append(flag)

    return unique_flags


def relationship_candidate_action(context):
    if context.fact_type == "character_item":
        return normalize_character_item_relationship_type(context.relationship_type)

    if context.fact_type == "character_skill":
        return normalize_text(context.relationship_type or "has").lower() or "has"

    return None


def relationship_candidate_target_name(context):
    target = context.item if context.fact_type == "character_item" else context.skill
    return getattr(target, "name", None)


def relationship_actor_match_for_sentence(context, sentence, local_context):
    if not context.character or not sentence:
        return False, False, False, None, None

    references = character_reference_candidates(context.character)
    explicit_pattern = relationship_reference_pattern(references, sentence)

    if explicit_pattern:
        return True, False, False, explicit_pattern, "explicit_name_or_alias"

    if not re.search(rf"\b{CHARACTER_RELATIONSHIP_PRONOUN_RE}\b", sentence, flags=re.IGNORECASE):
        return False, False, False, None, None

    result = resolve_character_attribution(
        mention=None,
        evidence_text=sentence,
        local_context=local_context,
        candidate_characters=attribution_candidate_characters(context),
        novel=context.novel,
        target_character=context.character,
        target_value=context.value,
    )

    if result.ambiguous:
        return False, True, True, None, "ambiguous_pronoun"

    if attribution_matches_character(result, context.character):
        return True, True, False, CHARACTER_RELATIONSHIP_PRONOUN_RE, result.match_type

    return False, False, False, None, None


def relationship_pronoun_actor_has_competing_antecedents(context, sentence, local_context):
    sentences = [
        normalize_text(part)
        for part in re.split(r"(?<=[.!?])\s+|\n+", normalize_text(local_context))
        if normalize_text(part)
    ]

    if not sentences:
        return False

    sentence_index = None

    for index, candidate_sentence in enumerate(sentences):
        if candidate_sentence == normalize_text(sentence):
            sentence_index = index
            break

    if sentence_index is None:
        sentence_index = len(sentences) - 1

    for candidate_sentence in sentences[max(0, sentence_index - 2):sentence_index]:
        character_ids = relationship_character_ids_in_text(context, candidate_sentence)

        if len(character_ids) > 1:
            return True

    return False


def relationship_character_ids_in_text(context, text):
    character_ids = set()

    for character in attribution_candidate_characters(context):
        if relationship_reference_pattern(character_reference_candidates(character), text):
            character_ids.add(getattr(character, "id", None))

    return {character_id for character_id in character_ids if character_id is not None}


def relationship_target_match_for_sentence(context, sentence, evidence_context):
    target = context.item if context.fact_type == "character_item" else context.skill

    if not target or not sentence:
        return False, False, False, None, None

    explicit_pattern = relationship_target_pattern_for_text(context, target, sentence)

    if explicit_pattern:
        return True, False, False, explicit_pattern, "explicit_target"

    shorthand_pattern = relationship_target_shorthand_pattern_for_text(context, target, sentence)

    if shorthand_pattern:
        if relationship_target_shorthand_is_unique(context, shorthand_pattern, sentence):
            return True, True, False, shorthand_pattern, "unique_shorthand"

        return False, True, True, None, "ambiguous_shorthand"

    if not relationship_text_has_object_pronoun(sentence):
        return False, False, False, None, None

    return relationship_pronoun_target_status(context, target, evidence_context)


def relationship_reference_pattern(references, text=None):
    matched_references = []

    for reference in sorted({normalize_text(reference) for reference in references if normalize_text(reference)}, key=len, reverse=True):
        pattern = rf"(?<![A-Za-z0-9]){re.escape(reference)}(?![A-Za-z0-9])"

        if text is None or re.search(pattern, text, flags=re.IGNORECASE):
            matched_references.append(pattern)

    if not matched_references:
        return None

    return "(?:" + "|".join(matched_references) + ")"


def relationship_target_reference_pattern(references, text=None):
    base_pattern = relationship_reference_pattern(references, text)

    if not base_pattern:
        return None

    optional_modifier = r"(?:(?:the|a|an|this|that|these|those|his|her|their)\s+(?:[A-Za-z-]+\s+){0,3})?"
    return f"{optional_modifier}{base_pattern}"


def relationship_entity_words_pattern(words, text=None):
    words = [word for word in words if word]

    if not words:
        return None

    word_patterns = []

    for word in words:
        suffix = "s?" if len(word) > 3 and not word.endswith("s") else ""
        word_patterns.append(rf"{re.escape(word)}{suffix}")

    base_pattern = (
        r"(?<![A-Za-z0-9])"
        + r"\s+".join(word_patterns)
        + r"(?![A-Za-z0-9])"
    )

    if text is not None and not re.search(base_pattern, text, flags=re.IGNORECASE):
        return None

    optional_modifier = r"(?:(?:the|a|an|this|that|these|those|his|her|their)\s+(?:[A-Za-z-]+\s+){0,3})?"
    return f"{optional_modifier}{base_pattern}"


def relationship_target_pattern_for_text(context, target, text):
    target_name = getattr(target, "name", None)
    fact_type = "item" if context.fact_type == "character_item" else "skill"

    if target_name and text_contains_entity_variant(
        text,
        target_name,
        fact_type=fact_type,
        relationship_backed=False,
    ):
        return relationship_target_reference_pattern([target_name], text) or relationship_entity_words_pattern(
            strip_optional_skill_suffix(normalized_entity_words(target_name))
            if fact_type == "skill"
            else normalized_entity_words(target_name),
            text,
        )

    if context.fact_type == "character_skill":
        aliases = [
            alias.alias
            for alias in getattr(target, "aliases", []) or []
            if getattr(alias, "alias", None)
        ]

        for alias in aliases:
            if text_contains_entity_variant(
                text,
                alias,
                fact_type="skill",
                relationship_backed=False,
            ):
                return relationship_target_reference_pattern([alias], text) or relationship_entity_words_pattern(
                    strip_optional_skill_suffix(normalized_entity_words(alias)),
                    text,
                )

        core_words = strip_optional_skill_suffix(normalized_entity_words(target_name))

        if core_words and set(core_words).issubset(set(normalized_entity_words(text))):
            return relationship_target_reference_pattern([" ".join(core_words)], text) or relationship_entity_words_pattern(
                core_words,
                text,
            )

    return None


def relationship_target_shorthand_pattern_for_text(context, target, text):
    target_words = set(normalized_entity_words(getattr(target, "name", "")))
    text_words = set(normalized_entity_words(text))

    if not target_words or not text_words:
        return None

    if context.fact_type == "character_item":
        noun_words = target_words & (
            GENERIC_ITEM_NOUNS
            | ITEM_ARTIFACT_NOUNS
            | ITEM_RESOURCE_NOUNS
            | ITEM_WEAPON_NOUNS
            | ITEM_TREASURE_NOUNS
            | {"bag", "bottle", "gourd", "mirror", "pill", "ring", "stone"}
        )
    else:
        noun_words = strip_optional_skill_suffix(list(target_words))
        noun_words = set(noun_words) & SKILL_FORMAL_NOUNS

    matched_words = sorted(noun_words & text_words, key=len, reverse=True)

    if not matched_words:
        return None

    return relationship_target_reference_pattern(matched_words, text)


def relationship_target_shorthand_is_unique(context, shorthand_pattern, text):
    candidates = relationship_target_candidates(context)
    matched_ids = []

    for candidate in candidates:
        candidate_pattern = relationship_target_shorthand_pattern_for_text(context, candidate, text)

        if candidate_pattern and re.search(shorthand_pattern, text, flags=re.IGNORECASE):
            matched_ids.append(getattr(candidate, "id", None))

    target = context.item if context.fact_type == "character_item" else context.skill
    target_id = getattr(target, "id", None)

    return bool(matched_ids) and set(matched_ids) == {target_id}


def relationship_text_has_object_pronoun(text):
    return re.search(rf"\b{OBJECT_RELATIONSHIP_PRONOUN_RE}\b", text, flags=re.IGNORECASE) is not None


def relationship_pronoun_target_status(context, target, evidence_context):
    candidates = relationship_target_candidates(context)
    target_id = getattr(target, "id", None)
    context_texts = relationship_coreference_search_texts(context, evidence_context)
    matched_ids = []

    for candidate in candidates:
        for text in context_texts:
            if not text:
                continue

            if relationship_target_pattern_for_text(context, candidate, text):
                matched_ids.append(getattr(candidate, "id", None))
                break

            shorthand_pattern = relationship_target_shorthand_pattern_for_text(context, candidate, text)

            if shorthand_pattern:
                matched_ids.append(getattr(candidate, "id", None))
                break

    matched_ids = [matched_id for matched_id in matched_ids if matched_id is not None]

    if not matched_ids:
        return False, False, False, None, None

    if set(matched_ids) != {target_id}:
        return False, True, True, None, "ambiguous_object_coreference"

    return True, True, False, OBJECT_RELATIONSHIP_PRONOUN_RE, "unique_object_coreference"


def relationship_coreference_search_texts(context, evidence_context):
    if not evidence_context.found:
        return [context.evidence]

    sentences = relationship_context_sentences(context, evidence_context)
    evidence_indexes = [
        index
        for index, (role, _) in enumerate(sentences)
        if role == "evidence"
    ]

    if not evidence_indexes:
        return [
            evidence_context.previous_sentence,
            evidence_context.evidence_sentence,
            evidence_context.next_sentence,
        ]

    evidence_index = evidence_indexes[0]
    search_texts = []

    for index in range(evidence_index - 1, -1, -1):
        _, sentence = sentences[index]

        if not sentence:
            continue

        search_texts.append(sentence)

        if relationship_text_has_object_pronoun(sentence):
            continue

        if relationship_character_ids_in_text(context, sentence):
            break

        if not any(
            relationship_target_pattern_for_text(context, candidate, sentence)
            or relationship_target_shorthand_pattern_for_text(context, candidate, sentence)
            for candidate in relationship_target_candidates(context)
        ):
            break

    search_texts.append(evidence_context.evidence_sentence)

    if evidence_context.next_sentence:
        search_texts.append(evidence_context.next_sentence)

    return search_texts


def relationship_target_candidates(context):
    target = context.item if context.fact_type == "character_item" else context.skill
    model = Item if context.fact_type == "character_item" else Skill
    candidates = []

    if context.novel:
        candidates = model.query.filter_by(novel_id=context.novel.id).all()

    if target and target not in candidates:
        candidates.append(target)

    return candidates


def relationship_sentence_has_action_blocker(sentence):
    sentence = normalize_text(sentence).lower()

    if not sentence:
        return False

    return any(re.search(pattern, sentence) for pattern in RELATIONSHIP_ACTION_BLOCKERS)


def relationship_sentence_proves_action(context, sentence, actor_pattern, target_pattern):
    if context.fact_type == "character_item":
        relationship_type = normalize_character_item_relationship_type(context.relationship_type)
        return character_item_sentence_proves_action(
            relationship_type,
            sentence,
            actor_pattern,
            target_pattern,
        )

    if context.fact_type == "character_skill":
        return character_skill_sentence_proves_action(sentence, actor_pattern, target_pattern)

    return False


def character_item_sentence_proves_action(relationship_type, sentence, actor_pattern, target_pattern):
    actor = actor_pattern
    subject_actor = rf"{actor}(?!['’]s)"
    actor_or_pronoun = rf"(?:{actor}|\b{CHARACTER_RELATIONSHIP_PRONOUN_RE}\b)"
    target = target_pattern
    gap = RELATIONSHIP_GAP
    short_gap = RELATIONSHIP_SHORT_GAP

    action_patterns = {
        "obtained": [
            rf"{subject_actor}{gap}\b(?:acquired|accepted|caught|claimed|collected|found|gained|got|grabbed|obtained|received|snatched|stole|took)\b{gap}{target}",
            rf"{subject_actor}{gap}\bpicked\s+(?:up\s+{target}|{target}\s+up)\b",
            rf"{subject_actor}{gap}\b(?:was|were)\s+(?:given|handed)\b{gap}{target}",
            rf"{subject_actor}{gap}{target}{gap}{actor_or_pronoun}{short_gap}\b(?:had\s+|has\s+)?(?:acquired|accepted|caught|claimed|collected|found|gained|got|grabbed|obtained|received|snatched|stole|took)\b",
            rf"{target}{gap}{actor_or_pronoun}{short_gap}\b(?:had\s+|has\s+)?(?:acquired|accepted|caught|claimed|collected|found|gained|got|grabbed|obtained|received|snatched|stole|took)\b",
            rf"\b(?:bestowed|delivered|gave|gifted|handed|passed|presented|tossed|threw)\b{gap}{target}{gap}\b(?:to|toward|upon|on)\b{short_gap}{actor}",
            rf"\b(?:gave|handed|passed|presented|tossed|threw)\b{gap}{actor}{gap}{target}",
            rf"{target}{gap}\b(?:was|were)\s+(?:given|handed|bestowed|passed|presented|tossed|delivered)\b{gap}\b(?:to|toward|upon|on)\b{short_gap}{actor}",
            rf"{target}{gap}\b(?:fell|flew|landed|passed|shot|slid|slipped|went)\b{gap}\b(?:into|in)\b{short_gap}{actor}(?:['’]s)?{short_gap}\b(?:{RELATIONSHIP_POSSESSION_CONTAINERS})\b",
            rf"\b(?:put|placed|slipped|tucked)\b{gap}{target}{gap}\b(?:into|in)\b{short_gap}{actor}(?:['’]s)?{short_gap}\b(?:{RELATIONSHIP_POSSESSION_CONTAINERS})\b",
        ],
        "received": [
            rf"{subject_actor}{gap}\b(?:accepted|caught|got|grabbed|received)\b{gap}{target}",
            rf"{subject_actor}{gap}\b(?:was|were)\s+(?:given|handed|bestowed)\b{gap}{target}",
            rf"{subject_actor}{gap}{target}{gap}{actor_or_pronoun}{short_gap}\b(?:had\s+|has\s+)?(?:accepted|caught|got|grabbed|received)\b",
            rf"{target}{gap}{actor_or_pronoun}{short_gap}\b(?:had\s+|has\s+)?(?:accepted|caught|got|grabbed|received)\b",
            rf"\b(?:bestowed|delivered|gave|gifted|handed|passed|presented|tossed|threw)\b{gap}{target}{gap}\b(?:to|toward|upon|on)\b{short_gap}{actor}",
            rf"\b(?:gave|handed|passed|presented|tossed|threw)\b{gap}{actor}{gap}{target}",
            rf"{target}{gap}\b(?:was|were)\s+(?:given|handed|bestowed|passed|presented|tossed|delivered)\b{gap}\b(?:to|toward|upon|on)\b{short_gap}{actor}",
            rf"{target}{gap}\b(?:fell|flew|landed|passed|shot|slid|slipped|went)\b{gap}\b(?:into|in)\b{short_gap}{actor}(?:['’]s)?{short_gap}\b(?:{RELATIONSHIP_POSSESSION_CONTAINERS})\b",
            rf"\b(?:put|placed|slipped|tucked)\b{gap}{target}{gap}\b(?:into|in)\b{short_gap}{actor}(?:['’]s)?{short_gap}\b(?:{RELATIONSHIP_POSSESSION_CONTAINERS})\b",
        ],
        "gave": [
            rf"{subject_actor}{gap}\b(?:bestowed|delivered|gave|gifted|handed|passed|presented|tossed|threw)\b{gap}{target}{gap}\b(?:to|toward|upon|on)\b",
            rf"{subject_actor}{gap}\b(?:gave|handed|passed|tossed|threw)\b{gap}\b[A-Za-z][^.!?]{{0,60}}\b{target}\b",
            rf"{subject_actor}{gap}\bhanded\s+over\b{gap}{target}",
            rf"{subject_actor}{gap}\bsurrendered\b{gap}{target}",
        ],
        "used": [
            rf"{subject_actor}{gap}\b(?:activated|applied|ate|consumed|drank|drew|equipped|fired|ingested|opened|read|shined|shone|swallowed|threw|used|wielded|wore)\b{gap}{target}",
            rf"{subject_actor}{gap}\bpopped\b{gap}{target}{gap}\b(?:into|in)\b{short_gap}\b(?:his|her|their|the)\b{short_gap}\b(?:mouth|throat)\b",
            rf"{subject_actor}{gap}\bpopped\b{gap}\b(?:it|this|that|them|one)\b{gap}\b(?:into|in)\b{short_gap}\b(?:his|her|their|the)\b{short_gap}\b(?:mouth|throat)\b",
            rf"{subject_actor}{gap}\bpopped\b{gap}(?:one\s+of\s+)?{target}{gap}\b(?:into|in)\b{short_gap}\b(?:his|her|their|the)\b{short_gap}\b(?:mouth|throat)\b",
            rf"{target}{gap}{actor_or_pronoun}{short_gap}\b(?:ate|consumed|drank|ingested|swallowed)\b",
            rf"{subject_actor}{gap}\b(?:attacked|struck)\s+with\b{gap}{target}",
            rf"{subject_actor}{gap}\bpoured\b{gap}\b(?:energy|power|mana|qi|spiritual\s+energy)\b{gap}\binto\b{gap}{target}",
        ],
        "lost": [
            rf"{subject_actor}{gap}\b(?:dropped|lost|surrendered)\b{gap}{target}",
            rf"{subject_actor}{gap}\bhanded\s+over\b{gap}{target}",
            rf"\b(?:snatched|stole|took|ripped|wrenched)\b{gap}{target}{gap}\b(?:from|away\s+from)\b{short_gap}{actor}",
            rf"{target}{gap}\b(?:was|were)\s+(?:confiscated|destroyed|shattered|stolen|taken)\b{gap}\b(?:from|away\s+from)\b{short_gap}{actor}",
            rf"{actor}(?:['’]s)?{short_gap}{target}{gap}\b(?:was|were)\s+(?:confiscated|destroyed|shattered|stolen|taken)\b",
        ],
        "owns": [
            rf"{subject_actor}{gap}\b(?:carried|carries|had|has|held|holding|owned|owns|possessed|possesses|wore|wearing)\b{gap}{target}",
            rf"{target}{gap}\bbelonged\s+to\b{gap}{actor}",
            rf"{target}{gap}\b(?:was|were)?\s*(?:in|inside)\b{short_gap}{actor}(?:['’]s)?{short_gap}\b(?:{RELATIONSHIP_POSSESSION_CONTAINERS})\b",
            rf"{actor}(?:['’]s){short_gap}{target}",
            rf"{subject_actor}{gap}\b(?:pocketed)\b{gap}{target}",
            rf"{subject_actor}{gap}\b(?:put|placed|slipped|tucked)\b{gap}{target}{gap}\b(?:into|in)\b{short_gap}\b(?:his|her|their)\b{short_gap}\b(?:{RELATIONSHIP_POSSESSION_CONTAINERS})\b",
        ],
    }

    return any(
        re.search(pattern, sentence, flags=re.IGNORECASE)
        for pattern in action_patterns.get(relationship_type, [])
    )


def character_skill_sentence_proves_action(sentence, actor_pattern, target_pattern):
    actor = actor_pattern
    subject_actor = rf"{actor}(?!['’]s)"
    target = target_pattern
    gap = RELATIONSHIP_GAP
    skill_gap = r"(?:(?!\b(?:observed|saw|watch(?:ed|ing)?)\b)[^.!?]){0,120}"
    completed_action = (
        r"(?:acquired|activated|cast|cultivated|demonstrated|displayed|executed|"
        r"learned|mastered|performed|practiced|studied|trained(?:\s+in)?|used)"
    )
    started_action = (
        r"(?:began|started)\s+(?:to\s+)?"
        r"(?:cast|cultivate|execute|learn|perform|practic(?:e|ing)|study|"
        r"train\s+in|use)"
    )
    picked_up_action = r"(?:had\s+)?picked\s+up"
    action = rf"(?:{completed_action}|{started_action}|{picked_up_action})"
    patterns = [
        rf"{subject_actor}{skill_gap}\b{action}\b{gap}{target}",
        rf"{subject_actor}{skill_gap}\bbegan\b{gap}(?:his|her|their)?{gap}{target}",
        rf"{subject_actor}{skill_gap}\bpossessed\s+knowledge\s+of\b{gap}{target}",
        rf"{subject_actor}{gap}\b(?:clapped|flicked|gestured|muttered|pointed|raised|snapped|waved)\b{gap}\band\b{gap}{target}{gap}\b(?:appeared|erupted|formed|manifested|materialized|shot|rose|emerged)\b",
        rf"{subject_actor}{gap}\b(?:conjured|launched|released|sent|summoned)\b{gap}{target}",
        (
            rf"{target}[\s\"'“”‘’!?,:;-]{{1,16}}{subject_actor}"
            rf"{gap}\b(?:asked|called|cried|exclaimed|replied|said|shouted|whispered|yelled)\b"
            rf"{gap}\b(?:as|while)\b{gap}\b(?:he|she|they)\b{gap}"
            rf"\b(?:activated|cast|demonstrated|executed|performed|used)\b"
            rf"{gap}\b(?:it|this|that|the\s+(?:art|skill|spell|technique))\b"
        ),
    ]

    return any(re.search(pattern, sentence, flags=re.IGNORECASE) for pattern in patterns)


def relationship_item_reference_supported(context, evidence):
    if not context.item:
        return False

    return text_contains_entity_variant(
        evidence,
        context.item.name,
        fact_type="item",
        relationship_backed=True,
    )


def relationship_skill_reference_supported(context, evidence):
    if not context.skill:
        return False

    return text_contains_entity_variant(
        evidence,
        context.skill.name,
        fact_type="skill",
        relationship_backed=True,
    )


def relationship_value_reference_status(context):
    if context.fact_type not in {"character_item", "character_skill"}:
        return False, False, False

    analysis = relationship_semantic_analysis(context)
    return (
        analysis.target_supported,
        analysis.target_context_supported,
        analysis.target_ambiguous,
    )


def relationship_evidence_is_intent_only(evidence):
    evidence = normalize_text(evidence).lower()
    return any(re.search(pattern, evidence) for pattern in RELATIONSHIP_INTENT_PATTERNS)


def relationship_action_supported(relationship_type, evidence):
    relationship_type = normalize_character_item_relationship_type(relationship_type)
    evidence = normalize_text(evidence).lower()
    patterns = RELATIONSHIP_ACTION_PATTERNS.get(relationship_type, [])
    return any(re.search(pattern, evidence) for pattern in patterns)


def character_skill_action_supported(evidence):
    evidence = normalize_text(evidence).lower()
    return any(re.search(pattern, evidence) for pattern in CHARACTER_SKILL_ACTION_PATTERNS)


def relationship_context_status(context):
    evidence_context = get_evidence_context(
        getattr(context.chapter, "content", "") if context.chapter else "",
        context.evidence,
    )

    return evidence_context.found, evidence_context.combined_context if evidence_context.found else context.evidence or ""


def relationship_action_status(context, evidence, local_context):
    analysis = relationship_semantic_analysis(context)
    return analysis.action_supported, analysis.intent_only


def relationship_resolution_flags(context):
    if context.fact_type not in {"character_item", "character_skill"}:
        return []

    analysis = relationship_semantic_analysis(context)
    flags = list(analysis.flags)
    target_uncertain_flag = (
        "relationship_item_uncertain"
        if context.fact_type == "character_item"
        else "relationship_skill_uncertain"
    )

    if analysis.target_ambiguous or not analysis.target_supported:
        flags.append(target_uncertain_flag)

    if (
        context.fact_type == "character_item"
        and not analysis.target_supported
        and relationship_uses_only_vague_item_reference(context, context.evidence)
    ):
        flags.append("relationship_vague_item_reference")

    unique_flags = []

    for flag in flags:
        if flag not in unique_flags:
            unique_flags.append(flag)

    return unique_flags


def relationship_uses_only_vague_item_reference(context, evidence):
    if relationship_item_reference_supported(context, evidence):
        return False

    evidence_words = set(normalized_entity_words(evidence))
    return bool(evidence_words & VAGUE_ITEM_REFERENCES)


def character_item_relationship_risk_flags(context):
    if context.fact_type != "character_item":
        return []

    return relationship_resolution_flags(context)


def character_skill_relationship_risk_flags(context):
    if context.fact_type != "character_skill":
        return []

    return relationship_resolution_flags(context)


def value_looks_like_progression_state(value, evidence=None):
    words = normalized_entity_words(value)
    word_set = set(words)

    if not words:
        return False

    if evidence and evidence_supports_physical_carrier(value, evidence):
        return False

    if evidence and evidence_describes_formal_method(evidence):
        return False

    if word_set & PROGRESSION_SYSTEM_TERMS and contains_number_or_ordinal(words):
        return True

    if {"qi", "condensation"}.issubset(word_set):
        return True

    if {"foundation", "establishment"}.issubset(word_set):
        return True

    if {"core", "formation"}.issubset(word_set):
        return True

    if {"nascent", "soul"}.issubset(word_set):
        return True

    if "rank" in word_set and (contains_number_or_ordinal(words) or word_set & {"bronze", "silver", "gold"}):
        return True

    if "level" in word_set and contains_number_or_ordinal(words):
        return True

    if word_set & PROGRESSION_POSITION_TERMS and (
        "sect" in word_set
        or "disciple" in word_set
        or contains_number_or_ordinal(words)
    ):
        return True

    return False


def evidence_describes_formal_method(evidence):
    evidence_words = set(normalized_entity_words(evidence))
    return bool(
        evidence_words
        & {
            "book",
            "manual",
            "method",
            "scripture",
            "scroll",
            "skill",
            "technique",
            "tome",
        }
    )


def value_looks_like_skill_or_technique(value):
    words = set(normalized_entity_words(value))
    return bool(words & SKILL_FORMAL_NOUNS)


def value_has_physical_medium_noun(value):
    words = set(normalized_entity_words(value))
    return bool(words & ITEM_PHYSICAL_MEDIUM_NOUNS)


def value_has_physical_item_noun(value):
    words = set(normalized_entity_words(value))
    return bool(
        words
        & (
            GENERIC_ITEM_NOUNS
            | ITEM_ARTIFACT_NOUNS
            | ITEM_RESOURCE_NOUNS
            | ITEM_WEAPON_NOUNS
            | ITEM_TREASURE_NOUNS
            | ITEM_PHYSICAL_MEDIUM_NOUNS
            | {
                "armor",
                "bone",
                "bottle",
                "inscription",
                "ring",
                "tablet",
                "talisman",
                "teeth",
            }
        )
    )


def evidence_describes_physical_medium(evidence):
    return bool(set(normalized_entity_words(evidence)) & ITEM_PHYSICAL_MEDIUM_NOUNS)


def evidence_describes_skill_action(evidence):
    return bool(set(normalized_entity_words(evidence)) & SKILL_ACTION_TERMS)


ITEM_SEMANTIC_PATTERNS = (
    r"\b(?:held|holding|hold)\b",
    r"\b(?:carried|carrying|carry)\b",
    r"\b(?:stored|storage|bag)\b",
    r"\b(?:wore|wearing|equipped)\b",
    r"\b(?:wielded|wielding|drew|drawn)\b",
    r"\b(?:consumed|swallowed|drank|ate|ingested)\b",
    r"\b(?:bought|purchased|sold|traded)\b",
    r"\b(?:gave|given|received|accepted|handed|tossed|threw|bestowed)\b",
    r"\b(?:dropped|picked\s+up|grabbed|snatched|took)\b",
    r"\b(?:activated|used|opened|inspected|examined)\b",
    r"\b(?:owned|possessed|belonged\s+to)\b",
    r"\b(?:appeared|materialized|rested|was)\b[^.!?]{0,80}\b(?:in|inside|on)\b[^.!?]{0,40}\b(?:hand|hands|palm|palms|bag|storage)\b",
)

LOCATION_SEMANTIC_PATTERNS = (
    r"\b(?:arrived|entered|exited|left|returned|traveled|travelled|went|walked)\b[^.!?]{0,80}\b(?:at|to|from|into|inside|within|through)\b",
    r"\b(?:inside|within|in|at)\b[^.!?]{0,80}\b(?:cave|hall|pavilion|mountain|valley|forest|city|village|room|workshop|building|residence|kingdom|region|realm|battlefield)\b",
    r"\b(?:lived|resided|stayed|stood)\b[^.!?]{0,80}\b(?:in|inside|within|at)\b",
    r"\b(?:located|situated)\b[^.!?]{0,80}\b(?:in|at|within)\b",
)

ORGANIZATION_SEMANTIC_PATTERNS = (
    r"\b(?:joined|belonged\s+to|served|represented)\b",
    r"\b(?:member|disciple|elder|leader|patriarch|captain)\b[^.!?]{0,80}\b(?:of|in)\b",
    r"\b(?:sect|clan|guild|school|family|army|faction|organization)\b",
)


def evidence_has_item_semantics(evidence):
    normalized_evidence = normalize_text(evidence).lower()

    if not normalized_evidence:
        return False

    return any(re.search(pattern, normalized_evidence) for pattern in ITEM_SEMANTIC_PATTERNS)


def value_has_location_noun(value):
    return bool(set(normalized_entity_words(value)) & LOCATION_NOUNS)


def value_has_organization_noun(value):
    return bool(set(normalized_entity_words(value)) & ORGANIZATION_NOUNS)


def evidence_has_location_semantics(evidence):
    normalized_evidence = normalize_text(evidence).lower()

    if not normalized_evidence:
        return False

    return any(re.search(pattern, normalized_evidence) for pattern in LOCATION_SEMANTIC_PATTERNS)


def evidence_has_organization_semantics(evidence):
    normalized_evidence = normalize_text(evidence).lower()

    if not normalized_evidence:
        return False

    return any(re.search(pattern, normalized_evidence) for pattern in ORGANIZATION_SEMANTIC_PATTERNS)


def evidence_supports_physical_carrier(value, evidence):
    carrier_words = set(normalized_entity_words(value)) & ITEM_PHYSICAL_MEDIUM_NOUNS

    if not carrier_words:
        return False

    if evidence_has_item_semantics(evidence):
        return True

    normalized_evidence = normalize_text(evidence).lower()
    return bool(
        normalized_evidence
        and re.search(
            r"\b(?:map|book|manual|record|scroll|slip|tablet|tome)\b"
            r"[^.!?]{0,100}\b(?:bore|contained|displayed|held|recorded|showed)\b"
            r"[^.!?]{0,100}\b(?:inscription|map|route|text|writing)\b",
            normalized_evidence,
        )
    )


def item_has_non_item_semantics(value, evidence):
    if evidence_has_item_semantics(evidence):
        return False

    return (
        value_looks_like_non_item_location(value, evidence)
        or value_looks_like_non_item_organization(value, evidence)
    )


def value_looks_like_non_item_location(value, evidence=None):
    if evidence_supports_physical_carrier(value, evidence):
        return False

    return value_has_location_noun(value) and (
        not evidence
        or evidence_has_location_semantics(evidence)
        or not evidence_has_item_semantics(evidence)
    )


def value_looks_like_non_item_organization(value, evidence=None):
    if evidence_supports_physical_carrier(value, evidence):
        return False

    return value_has_organization_noun(value) and (
        not evidence
        or evidence_has_organization_semantics(evidence)
        or not evidence_has_item_semantics(evidence)
    )


def item_type_boundary_flags(context):
    if context.fact_type not in {"item", "character_item"}:
        return []

    value = context.value or context.entity_name
    evidence = context.evidence
    flags = []

    if value_looks_like_intangible_skill_concept(value):
        flags.append("non_item_semantics")

    if value_looks_like_progression_state(value, evidence):
        flags.append("non_item_semantics")

    if value_looks_like_non_item_location(value, evidence):
        flags.append("possible_location_not_item")
        flags.append("non_item_semantics")

    if value_looks_like_non_item_organization(value, evidence):
        flags.append("possible_organization_not_item")
        flags.append("non_item_semantics")

    if not flags and not value_has_physical_item_noun(value) and not evidence_has_item_semantics(evidence):
        flags.append("item_type_uncertain")

    unique_flags = []

    for flag in flags:
        if flag not in unique_flags:
            unique_flags.append(flag)

    return unique_flags


def value_looks_like_intangible_skill_concept(value):
    words = set(normalized_entity_words(value))

    if not words:
        return False

    if value_has_physical_medium_noun(value):
        return False

    return bool(words & SKILL_FORMAL_NOUNS or {"breathing", "martial", "movement"} & words)


def value_looks_like_physical_item_concept(value):
    if value_looks_like_intangible_skill_concept(value):
        return False

    return value_has_physical_medium_noun(value)


def value_looks_like_non_character_concept(value, evidence=None):
    normalized = normalize_text(value)
    words = set(normalized_words(normalized))

    if not normalized:
        return True

    if value_looks_like_progression_state(normalized, evidence):
        return True

    if value_looks_like_intangible_skill_concept(normalized):
        return True

    if value_has_physical_item_noun(normalized):
        return True

    organization_place_terms = {
        "academy",
        "association",
        "cave",
        "city",
        "clan",
        "company",
        "empire",
        "guild",
        "kingdom",
        "mountain",
        "nation",
        "order",
        "pavilion",
        "realm",
        "school",
        "sect",
        "shop",
        "state",
        "store",
        "temple",
        "town",
        "village",
        "workshop",
    }

    return bool(words & organization_place_terms)


def value_related_sentences(evidence, value, fact_type=None):
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalize_text(evidence))
        if sentence.strip()
    ]

    related = [
        sentence
        for sentence in sentences
        if text_contains_entity_variant(sentence, value, fact_type=fact_type)
    ]

    return related or sentences


def statement_terms_apply(evidence, value, terms, fact_type=None):
    for sentence in value_related_sentences(evidence, value, fact_type=fact_type):
        sentence_text = sentence.lower()

        for term in terms:
            pattern = FUTURE_TERM_PATTERNS.get(term)

            if pattern:
                if pattern.search(sentence_text):
                    return True
                continue

            if fact_type == "life_event" and term == "later" and death_text_has_strong_signal(sentence_text):
                continue

            if term in sentence_text:
                return True

    return False


def fact_type_for_variant(context):
    if context.fact_type in {"item", "character_item"}:
        return "item"

    if context.fact_type in {"skill", "character_skill"}:
        return "skill"

    return context.fact_type


def weak_entity_name(name):
    normalized = normalize_text(name).lower()
    return not normalized or normalized in BASE_WEAK_ENTITY_NAMES or len(normalized) <= 1


def classify_character_entity(name, evidence=None, novel_schema=None):
    normalized = normalize_text(name)
    lower_name = normalized.lower().replace("-", " ")
    words = set(normalized_words(normalized))

    if not normalized:
        return EntityClassification("character", True, False, "empty_name")

    if looks_like_full_real_name(normalized):
        return EntityClassification("character", False, True, "proper_name")

    if looks_like_title_style_name(normalized):
        return EntityClassification("character", False, True, "title_style_name")

    if lower_name in BASE_WEAK_ENTITY_NAMES:
        return EntityClassification("character", True, False, "base_weak_name")

    if looks_like_generic_visual_description(normalized):
        return EntityClassification("character", True, False, "descriptive_role")

    if words & CHARACTER_ROLE_NOUNS and words & DESCRIPTIVE_CHARACTER_MODIFIERS:
        return EntityClassification("character", True, False, "descriptive_role")

    if words and words <= CHARACTER_ROLE_NOUNS:
        return EntityClassification("character", True, False, "role_only")

    if looks_like_stable_nickname_or_label(normalized):
        return EntityClassification("character", False, True, "stable_label")

    return EntityClassification("character", False, False, "unclassified")


def validate_character_identity(context, classification=None):
    if context.fact_type != "character":
        return CharacterIdentityValidation(False, reason="not_character_fact")

    classification = classification or classify_character_entity(
        context.entity_name,
        context.evidence,
    )
    risk_flags = []
    evidence = normalize_text(context.evidence)
    name = normalize_text(context.entity_name or context.value)

    evidence_verification = verify_evidence_text(
        getattr(context.chapter, "content", "") if context.chapter else "",
        context.evidence,
    )

    if not evidence:
        risk_flags.append("missing_evidence")
        return CharacterIdentityValidation(False, risk_flags=risk_flags, reason="missing_evidence")

    if not evidence_verification.verified:
        if evidence_verification.ambiguous:
            risk_flags.append("evidence_match_ambiguous")
            return CharacterIdentityValidation(False, risk_flags=risk_flags, reason="evidence_match_ambiguous")

        risk_flags.append("evidence_not_exact")
        return CharacterIdentityValidation(False, risk_flags=risk_flags, reason="evidence_not_exact")

    if not name:
        risk_flags.append("weak_entity_name")
        return CharacterIdentityValidation(False, risk_flags=risk_flags, reason="missing_name")

    if not is_trackable_character_name(name):
        risk_flags.append("non_character_entity")
        return CharacterIdentityValidation(False, risk_flags=risk_flags, reason="not_trackable")

    if value_looks_like_non_character_concept(name, evidence):
        risk_flags.append("non_character_entity")
        return CharacterIdentityValidation(False, risk_flags=risk_flags, reason="non_character_concept")

    if classification.is_generic:
        risk_flags.append("generic_character_label")
        return CharacterIdentityValidation(False, risk_flags=risk_flags, reason=classification.reason)

    if looks_like_generic_visual_description(name):
        risk_flags.append("generic_character_label")
        return CharacterIdentityValidation(False, risk_flags=risk_flags, reason="generic_visual_description")

    strong_identity_reasons = {
        "proper_name",
        "title_style_name",
        "stable_label",
        "stable_recurring_label",
    }

    if classification.reason not in strong_identity_reasons:
        risk_flags.append("weak_entity_name")
        return CharacterIdentityValidation(False, risk_flags=risk_flags, reason=classification.reason)

    candidate_names = [name]

    if context.character:
        candidate_names.extend(alias.alias for alias in getattr(context.character, "aliases", []) or [])

    candidate_names = [candidate for candidate in candidate_names if normalize_text(candidate)]

    if not any(text_contains_exact_phrase(evidence, candidate) for candidate in candidate_names):
        risk_flags.append("character_identity_not_directly_supported")
        return CharacterIdentityValidation(False, risk_flags=risk_flags, reason="name_not_in_evidence")

    if context.existing_record or context.conflict:
        return CharacterIdentityValidation(False, reason="duplicate_or_conflict")

    return CharacterIdentityValidation(True, confidence_bonus=20, reason=classification.reason)


def has_distinctive_modifier(words, generic_nouns):
    modifiers = set(words) - set(generic_nouns)

    if not modifiers:
        return False

    return not modifiers <= GENERIC_ITEM_MODIFIERS


def evidence_suggests_uniqueness(evidence):
    evidence_words = set(normalized_words(evidence))
    return bool(evidence_words & UNIQUENESS_EVIDENCE_TERMS)


def classify_item_entity(name, evidence=None, novel_schema=None):
    normalized = normalize_text(name)
    words = normalized_words(normalized)
    word_set = set(words)

    if not normalized:
        return EntityClassification("item", True, False, "empty_name")

    if value_looks_like_intangible_skill_concept(normalized):
        return EntityClassification("item", True, False, "skill_concept_not_item")

    if value_looks_like_progression_state(normalized, evidence):
        return EntityClassification("item", True, False, "progression_state_not_item")

    if value_looks_like_non_item_location(normalized, evidence):
        return EntityClassification("item", True, False, "location_not_item")

    if value_looks_like_non_item_organization(normalized, evidence):
        return EntityClassification("item", True, False, "organization_not_item")

    if (
        word_set
        and word_set <= GENERIC_ITEM_NOUNS | GENERIC_ITEM_MODIFIERS
        and not evidence_suggests_uniqueness(evidence)
    ):
        return EntityClassification("item", True, False, "generic_item")

    physical_nouns = (
        GENERIC_ITEM_NOUNS
        | ITEM_ARTIFACT_NOUNS
        | ITEM_RESOURCE_NOUNS
        | ITEM_WEAPON_NOUNS
        | ITEM_TREASURE_NOUNS
        | ITEM_PHYSICAL_MEDIUM_NOUNS
        | {"armor", "bone", "bottle", "ring", "teeth"}
    )

    if not word_set & physical_nouns:
        if not evidence_has_item_semantics(evidence):
            return EntityClassification("item", True, False, "item_type_uncertain")

        if evidence_suggests_uniqueness(evidence):
            return EntityClassification("item", False, True, "named_item")
        return EntityClassification("item", False, True, "named_item")

    if evidence_suggests_uniqueness(evidence):
        if word_set & ITEM_ARTIFACT_NOUNS:
            return EntityClassification("item", False, True, "named_artifact")
        if word_set & ITEM_MANUAL_NOUNS:
            return EntityClassification("item", False, True, "named_manual_or_scripture")
        if word_set & ITEM_RESOURCE_NOUNS:
            return EntityClassification("item", False, True, "significant_resource_type")
        if word_set & ITEM_TREASURE_NOUNS:
            return EntityClassification("item", False, True, "named_treasure")
        if word_set & ITEM_WEAPON_NOUNS:
            return EntityClassification("item", False, True, "named_weapon")
        return EntityClassification("item", False, True, "named_item")

    if has_distinctive_modifier(word_set, GENERIC_ITEM_NOUNS):
        if word_set & ITEM_ARTIFACT_NOUNS:
            return EntityClassification("item", False, True, "named_artifact")
        if word_set & ITEM_MANUAL_NOUNS:
            return EntityClassification("item", False, True, "named_manual_or_scripture")
        if word_set & ITEM_RESOURCE_NOUNS:
            return EntityClassification("item", False, True, "significant_resource_type")
        if word_set & ITEM_TREASURE_NOUNS:
            return EntityClassification("item", False, True, "named_treasure")
        if word_set & ITEM_WEAPON_NOUNS:
            return EntityClassification("item", False, True, "named_weapon")
        return EntityClassification("item", False, True, "named_item")

    return EntityClassification("item", True, False, "generic_item")


def classify_skill_entity(name, evidence=None, novel_schema=None):
    normalized = normalize_text(name)
    words = set(normalized_words(normalized))

    if not normalized:
        return EntityClassification("skill", True, False, "empty_name")

    if not words:
        return EntityClassification("skill", True, False, "empty_name")

    if value_looks_like_physical_item_concept(normalized):
        return EntityClassification("skill", True, False, "physical_item_not_skill")

    if len(words) <= 1 and words <= GENERIC_SKILL_TERMS:
        return EntityClassification("skill", True, False, "ordinary_action")

    if words <= GENERIC_SKILL_TERMS:
        return EntityClassification("skill", True, False, "generic_ability")

    if words & SKILL_FORMAL_NOUNS:
        if "spell" in words:
            return EntityClassification("skill", False, True, "named_spell")
        if "art" in words or "arts" in words:
            return EntityClassification("skill", False, True, "named_art")
        if "technique" in words:
            return EntityClassification("skill", False, True, "named_technique")
        if "ability" in words:
            return EntityClassification("skill", False, True, "named_ability")
        return EntityClassification("skill", False, True, "named_skill")

    if evidence_suggests_uniqueness(evidence) and len(words) > 1:
        return EntityClassification("skill", False, True, "named_skill")

    if len(words) > 1:
        return EntityClassification("skill", False, True, "named_skill")

    return EntityClassification("skill", True, False, "unknown")


def is_generic_new_entity(context):
    if context.fact_type == "character":
        return classify_character_entity(
            context.entity_name,
            context.evidence,
        ).is_generic

    if context.fact_type == "item":
        return classify_item_entity(
            context.entity_name,
            context.evidence,
        ).is_generic

    if context.fact_type == "skill":
        return classify_skill_entity(
            context.entity_name,
            context.evidence,
        ).is_generic

    return False


def is_strong_new_character_identity(context, classification, identity_validation=None):
    if context.fact_type != "character":
        return False

    if context.entity_origin != ENTITY_ORIGIN_NEW:
        return False

    if not identity_validation or not identity_validation.supported:
        return False

    if classification.reason not in {
        "proper_name",
        "title_style_name",
        "stable_label",
        "stable_recurring_label",
    }:
        return False

    if classification.is_generic or not classification.is_distinctive:
        return False

    if looks_like_generic_visual_description(context.entity_name or ""):
        return False

    return True


def is_strong_new_item_identity(context, classification):
    if context.fact_type != "item":
        return False

    if context.entity_origin != ENTITY_ORIGIN_NEW:
        return False

    if not classification or classification.is_generic or not classification.is_distinctive:
        return False

    return classification.reason in {
        "named_item",
        "named_artifact",
        "named_treasure",
        "named_weapon",
        "significant_resource_type",
        "named_manual_or_scripture",
    }


def is_strong_new_skill_identity(context, classification):
    if context.fact_type != "skill":
        return False

    if context.entity_origin != ENTITY_ORIGIN_NEW:
        return False

    if not classification or classification.is_generic or not classification.is_distinctive:
        return False

    return classification.reason in {
        "named_skill",
        "named_technique",
        "named_spell",
        "named_art",
        "named_ability",
    }


def approved_current_progression_value(character, progression_type):
    if not character or not progression_type:
        return None

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

    return latest_progression.new_value if latest_progression else None


def has_progression_downgrade(character, progression_type, new_value):
    if not character or not new_value:
        return False

    current_value = approved_current_progression_value(character, progression_type)

    if not current_value:
        return False

    current_key = progression_compare_key(progression_type, current_value)
    new_key = progression_compare_key(progression_type, new_value)

    if not (
        isinstance(current_key, tuple)
        and isinstance(new_key, tuple)
        and len(current_key) == 6
        and len(new_key) == 6
        and current_key[0] == "semantic_progression"
        and new_key[0] == "semantic_progression"
    ):
        return False

    _, current_type, current_dimension, current_level, _, current_system = current_key
    _, new_type, new_dimension, new_level, _, new_system = new_key

    if current_type != new_type or current_dimension != new_dimension:
        return False

    if not isinstance(current_level, int) or not isinstance(new_level, int):
        return False

    if current_system and new_system and current_system != new_system:
        return False

    return new_level < current_level


def validate_extracted_fact(context):
    flags = []
    score = 0
    evidence_verification = verify_evidence_text(
        getattr(context.chapter, "content", "") if context.chapter else "",
        context.evidence,
        start_offset=context.evidence_start_offset,
        end_offset=context.evidence_end_offset,
        match_type=context.evidence_match_type,
    )

    if evidence_verification.verified:
        context.evidence = evidence_verification.evidence_text

    evidence_context = get_evidence_context(
        getattr(context.chapter, "content", "") if context.chapter else "",
        context.evidence,
        start_offset=evidence_verification.start_offset,
        end_offset=evidence_verification.end_offset,
        match_type=evidence_verification.match_type,
    )
    evidence = normalize_text(context.evidence)
    value = normalize_text(context.value or context.entity_name)
    combined_text = f"{value} {evidence}".lower()

    if has_short_direct_evidence(evidence):
        score += 30
    else:
        flags.append("missing_evidence")

    if evidence and not evidence_verification.verified:
        if evidence_verification.ambiguous:
            flags.append("evidence_match_ambiguous")
        else:
            flags.append("evidence_not_exact")
        score -= 30

    if evidence and not evidence_context.found:
        if evidence_context.ambiguous:
            flags.append("evidence_match_ambiguous")
        else:
            flags.append("context_unavailable")
    elif evidence_context.match_type and evidence_context.match_type != "exact":
        flags.append("evidence_located_with_normalization")

    value_supported = bool(value and entity_value_supported(context, value))
    type_supported = evidence_supports_entity_type(context)

    if context.fact_type in {"skill", "character_skill"} and value_looks_like_progression_state(
        value,
        evidence,
    ):
        type_supported = False

    item_boundary_flags = item_type_boundary_flags(context)
    for item_boundary_flag in item_boundary_flags:
        flags.append(item_boundary_flag)

    if item_boundary_flags:
        type_supported = False

    if value_supported:
        score += 20

    if context.entity_origin == ENTITY_ORIGIN_EXISTING:
        score += 15
    elif context.entity_origin == ENTITY_ORIGIN_NEW:
        score += 5
    elif context.character or context.skill or context.item:
        score += 10
    elif context.fact_type not in {"character"}:
        flags.append("entity_not_found")

    if len(context.source_extractors) > 1:
        score += 20

    if not context.conflict:
        score += 15
    else:
        flags.append("conflicts_with_database")

    if context.entity_origin == ENTITY_ORIGIN_EXISTING:
        score += 10
    elif context.entity_origin == ENTITY_ORIGIN_UNRESOLVED and not (
        context.character or context.skill or context.item
    ):
        flags.append("entity_not_found")

    if weak_entity_name(context.entity_name):
        flags.append("weak_entity_name")
        score -= 10

    variant_fact_type = fact_type_for_variant(context)
    statement_evidence = evidence

    if context.fact_type in {"character_item", "character_skill"}:
        relationship_analysis = relationship_semantic_analysis(context)

        if relationship_analysis.action_supported and relationship_analysis.proven_sentence:
            statement_evidence = relationship_analysis.proven_sentence

    if statement_terms_apply(
        statement_evidence,
        value,
        SPECULATIVE_TERMS,
        fact_type=variant_fact_type,
    ):
        flags.append("speculative_statement")
        score -= 30

    future_terms = FUTURE_TERMS

    if (
        context.fact_type in {"character_item", "character_skill"}
        and relationship_analysis.action_supported
    ):
        future_terms = FUTURE_TERMS - {"later"}

    if statement_terms_apply(
        statement_evidence,
        value,
        future_terms,
        fact_type=variant_fact_type,
    ):
        flags.append("future_statement")
        score -= 30

    uncertain_statement = "?" in " ".join(
        value_related_sentences(statement_evidence, value, fact_type=variant_fact_type)
    ) or any(
        term in f"{value} {statement_evidence}".lower()
        for term in QUESTION_UNCERTAIN_TERMS
    )

    if uncertain_statement and not (context.fact_type == "character" and value_supported):
        flags.append("uncertain_statement")
        score -= 20

    if context.existing_record:
        flags.append("possible_duplicate")
        score -= 10

    if context.repeated_known_fact:
        flags.append("repeated_known_fact")
        score -= 15

    if context.progression_downgrade:
        flags.append("progression_downgrade")
        score -= 20

    if context.attribution_uncertain:
        flags.append("attribution_uncertain")
        score -= 30
    elif context.context_supported_attribution:
        flags.append("context_supported_attribution")

    if context.ambiguous_owner:
        flags.append("ambiguous_owner")
        score -= 30

    relationship_flags = [
        *character_item_relationship_risk_flags(context),
        *character_skill_relationship_risk_flags(context),
    ]
    for relationship_flag in relationship_flags:
        flags.append(relationship_flag)

    if SERIOUS_RISK_FLAGS & set(relationship_flags):
        score -= 30

    life_event_flags = life_event_risk_flags(context)
    for life_event_flag in life_event_flags:
        flags.append(life_event_flag)

    if SERIOUS_RISK_FLAGS & set(life_event_flags):
        score -= 30

    score = max(0, min(100, score))
    unique_flags = []

    for flag in flags:
        if flag not in unique_flags:
            unique_flags.append(flag)

    direct_value_supported = value_supported
    character_classification = (
        classify_character_entity(context.entity_name, context.evidence)
        if context.fact_type == "character"
        else None
    )
    character_identity_validation = (
        validate_character_identity(context, character_classification)
        if context.fact_type == "character"
        else CharacterIdentityValidation(False)
    )
    if character_identity_validation.supported:
        score = min(100, score + character_identity_validation.confidence_bonus)
    for identity_flag in character_identity_validation.risk_flags:
        if identity_flag not in unique_flags:
            unique_flags.append(identity_flag)

    score = max(0, min(100, score))
    serious_flags_present = bool(SERIOUS_RISK_FLAGS & set(unique_flags))
    strong_entity_name = "weak_entity_name" not in unique_flags
    item_classification = (
        classify_item_entity(context.entity_name, context.evidence)
        if context.fact_type == "item"
        else classify_item_entity(context.value, context.evidence)
        if context.fact_type == "character_item"
        else None
    )
    skill_classification = (
        classify_skill_entity(context.entity_name, context.evidence)
        if context.fact_type == "skill"
        else classify_skill_entity(context.value, context.evidence)
        if context.fact_type == "character_skill"
        else None
    )
    generic_new_entity = (
        character_classification.is_generic
        if character_classification
        else item_classification.is_generic
        if item_classification
        else skill_classification.is_generic
        if skill_classification
        else is_generic_new_entity(context)
    )
    possible_duplicate = "possible_duplicate" in unique_flags
    repeated_known_fact = "repeated_known_fact" in unique_flags
    strong_new_character_identity = is_strong_new_character_identity(
        context,
        character_classification,
        character_identity_validation,
    )
    strong_new_item_identity = is_strong_new_item_identity(
        context,
        item_classification,
    )
    strong_new_skill_identity = is_strong_new_skill_identity(
        context,
        skill_classification,
    )
    strong_new_entity_identity = (
        strong_new_character_identity
        or strong_new_item_identity
        or strong_new_skill_identity
    )
    relationship_identity_supported = (
        context.fact_type in {"character_item", "character_skill"}
        and direct_value_supported
        and type_supported
        and not generic_new_entity
        and not (SERIOUS_RISK_FLAGS & set(relationship_flags))
    )

    if context.entity_origin == ENTITY_ORIGIN_NEW:
        auto_approved = (
            (score >= 90 or strong_new_entity_identity or relationship_identity_supported)
            and not serious_flags_present
            and direct_value_supported
            and type_supported
            and strong_entity_name
            and not generic_new_entity
            and not possible_duplicate
            and not repeated_known_fact
        )
    elif relationship_identity_supported:
        auto_approved = (
            score >= 70
            and not serious_flags_present
            and strong_entity_name
            and not possible_duplicate
            and not repeated_known_fact
        )
    elif context.fact_type == "life_event" and normalize_text(value).lower() == "death":
        auto_approved = (
            score >= 90
            and not serious_flags_present
            and death_life_event_supported(context)
            and life_event_attribution_supported(context)
        )
    else:
        auto_approved = score >= 90 and not serious_flags_present

    return ValidationResult(score, unique_flags, auto_approved)


def set_validation_metadata(record, validation, source_extractor):
    if not validation:
        return False

    if manually_reviewed_record(record):
        return False

    old_status = getattr(record, "review_status", None)
    old_auto_approved = getattr(record, "auto_approved", None)
    active_blockers = sorted(SERIOUS_RISK_FLAGS & set(validation.risk_flags))
    auto_approved = validation.auto_approved and not active_blockers

    if (
        old_status == "approved"
        and old_auto_approved
        and not auto_approved
        and not automatic_approval_state_needs_repair(record)
    ):
        log_automatic_validation_rejected(
            record,
            source_extractor,
            validation,
            active_blockers,
            "clean_existing_approval_preserved",
        )
        return False

    if hasattr(record, "confidence_score"):
        record.confidence_score = validation.confidence_score

    if hasattr(record, "risk_flags"):
        record.risk_flags = json.dumps(validation.risk_flags)

    if hasattr(record, "source_extractor"):
        record.source_extractor = source_extractor

    if hasattr(record, "auto_approved"):
        record.auto_approved = auto_approved

    if auto_approved:
        record.review_status = "approved"
    elif getattr(record, "review_status", None) != "rejected":
        record.review_status = "pending"

    log_automatic_validation_finalized(
        record,
        old_status,
        old_auto_approved,
        source_extractor,
        validation,
        active_blockers,
    )

    return True


def manually_reviewed_record(record):
    if getattr(record, "auto_approved", False):
        return False

    if getattr(record, "last_reviewed_by_user_id", None):
        return True

    manual_actions = {"approved", "rejected", "edited"}
    if getattr(record, "last_review_action", None) in manual_actions:
        return True

    sources = {
        source.strip().lower()
        for source in str(getattr(record, "source_extractor", None) or "").split(",")
        if source.strip()
    }
    return bool(sources & {"admin", "manual", "human"})


def risk_flags_from_record(record):
    raw_flags = getattr(record, "risk_flags", None)

    if not raw_flags:
        return []

    if isinstance(raw_flags, list):
        return raw_flags

    try:
        parsed_flags = json.loads(raw_flags)
    except (TypeError, ValueError):
        return []

    return parsed_flags if isinstance(parsed_flags, list) else []


def record_has_active_serious_blockers(record):
    return bool(SERIOUS_RISK_FLAGS & set(risk_flags_from_record(record)))


def automatic_approval_state_needs_repair(record):
    if getattr(record, "review_status", None) != "approved":
        return False

    if not getattr(record, "auto_approved", False):
        return not manually_reviewed_record(record)

    if record_has_active_serious_blockers(record):
        return True

    confidence_score = getattr(record, "confidence_score", None)

    return confidence_score is not None and confidence_score < 90


def approve_character_identity(record, validation=None, source_extractor=None):
    if not isinstance(record, Character):
        return False

    if not validation:
        return False

    return set_validation_metadata(record, validation, source_extractor or "character")


def log_automatic_validation_finalized(
    record,
    old_status,
    old_auto_approved,
    source_extractor,
    validation,
    active_blockers,
):
    new_status = getattr(record, "review_status", None)
    new_auto_approved = getattr(record, "auto_approved", None)

    if old_status == new_status and old_auto_approved == new_auto_approved:
        return

    try:
        logger = current_app.logger
    except RuntimeError:
        return

    logger.info(
        "Automatic validation finalized: type=%s id=%s status=%s->%s "
        "auto_approved=%s->%s source=%s confidence=%s blockers=%s flags=%s",
        record.__class__.__name__,
        getattr(record, "id", None),
        old_status,
        new_status,
        old_auto_approved,
        new_auto_approved,
        source_extractor,
        validation.confidence_score,
        active_blockers,
        validation.risk_flags,
    )


def log_automatic_validation_rejected(
    record,
    source_extractor,
    validation,
    active_blockers,
    reason,
):
    try:
        logger = current_app.logger
    except RuntimeError:
        return

    logger.info(
        "Automatic validation did not change approved row: type=%s id=%s "
        "reason=%s source=%s confidence=%s blockers=%s flags=%s",
        record.__class__.__name__,
        getattr(record, "id", None),
        reason,
        source_extractor,
        validation.confidence_score,
        active_blockers,
        validation.risk_flags,
    )


def normalize_character_item_relationship_type(relationship_type):
    normalized = normalize_text(relationship_type).lower().replace(" ", "_")
    aliases = {
        "has": "owns",
        "owned": "owns",
        "owner": "owns",
        "owns": "owns",
        "obtains": "obtained",
        "obtained": "obtained",
        "gets": "obtained",
        "got": "obtained",
        "receives": "received",
        "received": "received",
        "uses": "used",
        "used": "used",
        "loses": "lost",
        "lost": "lost",
        "gives": "gave",
        "gave": "gave",
    }
    return aliases.get(normalized, "owns")


def find_existing_character_item(character, item, relationship_type):
    if not character or not item:
        return None

    return CharacterItem.query.filter_by(
        character_id=character.id,
        item_id=item.id,
        relationship_type=relationship_type,
    ).first()


def find_existing_character_skill(character, skill):
    if not character or not skill:
        return None

    return CharacterSkill.query.filter_by(
        character_id=character.id,
        skill_id=skill.id,
    ).first()
