import re
from types import SimpleNamespace

from app.models import (
    CharacterLifeEvent,
    CharacterMetadataProposal,
    CharacterProgressionEvent,
    Chapter,
    WikiEvidence,
    db,
)
from app.services.extraction.evidence import (
    get_evidence_context,
    recover_fact_evidence,
    verify_evidence_text,
)
from app.services.extraction.attribution import (
    attribution_matches_character,
    resolve_character_attribution,
)
from app.services.extraction.evidence_audit import record_ai_evidence_audit
from app.services.extraction.validation import manually_reviewed_record
from app.services.metadata_normalization import (
    is_weak_variation,
    normalize_metadata_field,
)


CHARACTER_METADATA_FIELDS = {
    "age_text",
    "gender",
    "race_or_species",
    "origin",
    "faction_or_affiliation",
    "status",
}

ALLOWED_LIFE_STATUS_VALUES = {
    "alive",
    "dead",
    "historical",
    "missing",
    "sealed",
    "reincarnated",
    "unknown",
}

REVIEWABLE_LIFE_STATUS_VALUES = ALLOWED_LIFE_STATUS_VALUES - {"unknown"}

STATUS_VALUE_ALIASES = {
    "killed": "dead",
    "died": "dead",
    "deceased": "dead",
    "corpse": "dead",
    "soul dispersed": "dead",
    "sealed away": "sealed",
    "legendary": "historical",
    "ancient": "historical",
    "past era": "historical",
    "past-era": "historical",
}

DEATH_EVIDENCE_TERMS = {
    "dead",
    "died",
    "death",
    "killed",
    "slain",
    "deceased",
    "corpse",
    "lifeless",
    "dead body",
}

ALIVE_EVIDENCE_TERMS = {
    "alive",
    "living",
    "survived",
    "still lived",
    "still alive",
}

SPECIES_CONTEXT_TERMS = {
    "race",
    "species",
    "bloodline",
    "lineage",
    "born as",
    "kind",
    "people",
    "clan",
    "tribe",
}

NON_HUMAN_SPECIES_TERMS = {
    "alien",
    "beast",
    "demon",
    "dragon",
    "dwarf",
    "elf",
    "ghost",
    "monster",
    "spirit",
    "undead",
    "vampire",
    "werewolf",
}

HUMAN_SPECIES_TERMS = {"human", "mortal", "man", "woman"}

GENERIC_TITLE_WORDS = {
    "black-robed man",
    "fat teenager",
    "guard",
    "old man",
    "servant",
    "tall youth",
    "young man",
}

MALE_GENDER_TERMS = {
    "brother",
    "father",
    "grandfather",
    "he",
    "him",
    "himself",
    "his",
    "male",
    "man",
    "son",
    "uncle",
}

FEMALE_GENDER_TERMS = {
    "aunt",
    "daughter",
    "female",
    "girl",
    "grandmother",
    "her",
    "hers",
    "herself",
    "miss",
    "mother",
    "mrs",
    "ms",
    "she",
    "sister",
    "woman",
}

GENDER_TERM_PATTERNS = {
    "male": tuple(
        rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])"
        for term in MALE_GENDER_TERMS
    ),
    "female": tuple(
        rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])"
        for term in FEMALE_GENDER_TERMS
    ),
}

GENDER_OPPOSITE = {
    "male": "female",
    "female": "male",
}

METADATA_INFORMATIONAL_WARNINGS = {
    "evidence_located_with_normalization",
}

METADATA_BLOCKING_WARNINGS = {
    "age_not_factual",
    "age_not_proven",
    "age_attribution_uncertain",
    "apparent_age_only",
    "metadata_attribution_uncertain",
    "metadata_evidence_missing",
    "metadata_evidence_not_raw",
    "metadata_evidence_merged",
    "metadata_evidence_weak",
    "evidence_not_exact",
    "evidence_match_ambiguous",
    "context_unavailable",
    "status_not_confirmed",
    "speculative_status",
    "future_status",
    "title_not_current",
    "promotion_not_completed",
    "title_attribution_uncertain",
    "title_not_proven",
    "affiliation_not_proven",
    "former_affiliation_only",
    "origin_not_proven",
    "origin_attribution_uncertain",
    "location_not_origin",
    "species_not_explicit",
    "species_attribution_uncertain",
}

STATUS_UNCONFIRMED_RE = re.compile(
    r"\b(?:believed|thought|presumed|rumou?red|reported|said)\s+(?:to\s+be\s+)?dead\b|"
    r"\b(?:may|might|could|possibly|perhaps|maybe|probably|likely|apparently)\s+"
    r"(?:be\s+)?dead\b|"
    r"\b(?:nearly|almost)\s+died\b|"
    r"\bwas\s+dying\b|"
    r"\b(?:would|will|could|might)\s+die\b|"
    r"\bthreaten(?:ed|s)?\s+to\s+kill\b",
    re.IGNORECASE,
)

AGE_APPARENT_RE = re.compile(
    r"\b(?:looked|looks|appeared|appears|seemed|seems|looked\s+to\s+be|"
    r"appeared\s+to\s+be|seemed\s+to\s+be)\b",
    re.IGNORECASE,
)

AGE_RHETORICAL_RE = re.compile(
    r"\?|"
    r"\bfelt\s+like\b|"
    r"\bface\s+of\s+(?:a\s+|an\s+)?(?:\w+[-\s])?year[-\s]old\b|"
    r"\bwhat\s+(?:\w+[-\s])?year[-\s]old\b",
    re.IGNORECASE,
)

TITLE_FUTURE_OR_INTENT_RE = re.compile(
    r"\b(?:selected|chosen|nominated|eligible|slated|recommended|approved)\s+"
    r"(?:[^.!?]{0,80}\s+)?(?:to\s+be\s+)?promoted\b|"
    r"\b(?:will|would|could|might|may|soon|eventually|hop(?:ed|es|ing)|intend(?:ed|s)?|"
    r"aspir(?:ed|es|ing)|plan(?:ned|s|ning))\s+(?:[^.!?]{0,80}\s+)?"
    r"(?:become|be\s+promoted|gain|receive|obtain)\b|"
    r"\b(?:future|pending|upcoming)\s+(?:title|promotion|rank|position)\b",
    re.IGNORECASE,
)

FACTION_FORMER_RE = re.compile(
    r"\b(?:formerly|once|previously)\s+(?:belonged|served|was|were|had\s+been|"
    r"was\s+a|were\s+a)\b|"
    r"\b(?:former|ex)[-\s]+(?:member|disciple|servant|elder|captain|commander)\b|"
    r"\b(?:left|expelled\s+from|cast\s+out\s+of|betrayed|abandoned)\b",
    re.IGNORECASE,
)

ORIGIN_TRAVEL_RE = re.compile(
    r"\b(?:returned|arrived|traveled|travelled|walked|ran|flew|came\s+back)\s+from\b|"
    r"\bfrom\s+[^.!?]{0,80}\s+(?:after|following)\s+(?:a\s+)?(?:mission|visit|journey|trip)\b|"
    r"\b(?:headed|went|traveled|travelled|journeyed)\s+to\b",
    re.IGNORECASE,
)


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


def _normalized_words(value):
    return re.findall(r"[a-z0-9]+", _normalize_evidence_text(value or "").lower())


def _contains_phrase(text, phrase):
    normalized_text = _normalize_evidence_text(text or "").lower()
    normalized_phrase = _normalize_evidence_text(phrase or "").lower()
    return bool(normalized_text and normalized_phrase and normalized_phrase in normalized_text)


def character_reference_values(character):
    values = [getattr(character, "name", None)]
    values.extend(alias.alias for alias in getattr(character, "aliases", []) or [])
    return [value for value in values if value]


def character_reference_patterns(character):
    return [
        rf"(?<![A-Za-z0-9]){re.escape(_normalize_alias(value))}(?![A-Za-z0-9])"
        for value in character_reference_values(character)
        if _normalize_alias(value)
    ]


def value_phrase_pattern(value):
    normalized_value = _normalize_alias(value or "")

    if not normalized_value:
        return None

    return (
        r"(?<![A-Za-z0-9])"
        + r"\s+".join(re.escape(part) for part in normalized_value.split())
        + r"(?![A-Za-z0-9])"
    )


def article_optional_value_pattern(value):
    pattern = value_phrase_pattern(value)
    return rf"(?:the\s+)?{pattern}" if pattern else None


def competing_character_reference_values(character):
    if not character or not getattr(character, "novel_id", None):
        return []

    references = []

    for other_character in type(character).query.filter(
        type(character).novel_id == character.novel_id,
        type(character).id != character.id,
    ).all():
        references.extend(character_reference_values(other_character))

    return references


def evidence_supports_character(character, evidence):
    return any(_contains_phrase(evidence, value) for value in character_reference_values(character))


def metadata_local_context(chapter, evidence):
    evidence_context = get_evidence_context(
        getattr(chapter, "content", "") if chapter else "",
        evidence,
    )
    return evidence_context.combined_context if evidence_context.found else evidence or ""


def metadata_evidence_attributed_to_character(character, evidence, chapter=None):
    result = metadata_attribution_result(character, evidence, chapter)
    return attribution_matches_character(result, character)


def metadata_attribution_result(character, evidence, chapter=None):
    if not character:
        return None

    candidate_characters = []

    if getattr(character, "novel_id", None):
        candidate_characters = type(character).query.filter_by(novel_id=character.novel_id).all()

    if character not in candidate_characters:
        candidate_characters.append(character)

    return resolve_character_attribution(
        evidence_text=evidence,
        local_context=metadata_local_context(chapter, evidence),
        candidate_characters=candidate_characters,
        novel=getattr(character, "novel", None),
        target_character=character,
    )


def evidence_supports_value(evidence, value):
    if _contains_phrase(evidence, value):
        return True

    evidence_words = set(_normalized_words(evidence))
    value_words = [word for word in _normalized_words(value) if len(word) >= 3]
    return bool(value_words and set(value_words).issubset(evidence_words))


def evidence_has_any(evidence, terms):
    normalized_evidence = _normalize_evidence_text(evidence or "").lower()
    return any(term in normalized_evidence for term in terms)


def evidence_has_gender_signal(evidence, gender_value):
    normalized_gender = _normalize_alias(gender_value or "").lower()

    if normalized_gender not in GENDER_TERM_PATTERNS:
        return False

    return any(
        re.search(pattern, evidence or "", flags=re.IGNORECASE)
        for pattern in GENDER_TERM_PATTERNS[normalized_gender]
    )


def reference_contains_gender_signal(reference, gender_value):
    return evidence_has_gender_signal(reference, gender_value)


def gender_signal_is_conflicted(evidence, gender_value):
    opposite = GENDER_OPPOSITE.get(_normalize_alias(gender_value or "").lower())
    return bool(opposite and evidence_has_gender_signal(evidence, opposite))


def gender_evidence_is_direct(character, gender_value, evidence, chapter=None):
    normalized_gender = _normalize_alias(gender_value or "").lower()

    if normalized_gender not in GENDER_TERM_PATTERNS:
        return False

    if not metadata_evidence_attributed_to_character(character, evidence, chapter):
        return False

    for reference in character_reference_values(character):
        if (
            reference_contains_gender_signal(reference, normalized_gender)
            and _contains_phrase(evidence, reference)
        ):
            return True

    if gender_signal_is_conflicted(evidence, normalized_gender):
        return False

    if evidence_has_gender_signal(evidence, normalized_gender):
        return True

    context = metadata_local_context(chapter, evidence)

    if context and not gender_signal_is_conflicted(context, normalized_gender):
        return evidence_has_gender_signal(context, normalized_gender)

    return False


def metadata_warning_list(warnings):
    if not warnings:
        return []

    if isinstance(warnings, str):
        return [warning.strip() for warning in warnings.splitlines() if warning.strip()]

    return [warning for warning in warnings if warning]


def metadata_blocking_warnings(warnings):
    blockers = []

    for warning in metadata_warning_list(warnings):
        if warning in METADATA_INFORMATIONAL_WARNINGS:
            continue

        if warning in METADATA_BLOCKING_WARNINGS:
            blockers.append(warning)
            continue

        # Older normalization/conflict warnings are prose strings. Treat them
        # as blockers unless they are explicitly classified as informational.
        blockers.append(warning)

    return blockers


def metadata_warnings_block_auto_approval(warnings):
    return bool(metadata_blocking_warnings(warnings))


def _merge_description(existing_description, new_description):
    if not existing_description:
        return new_description

    if not new_description or new_description in existing_description:
        return existing_description

    return f"{existing_description}\n\n{new_description}"


def _metadata_evidence_has_artificial_chapter_label(evidence):
    return bool(re.search(r"(^|\n)\s*Chapter\s+\d+\s*:", evidence or "", re.IGNORECASE))


def _strip_artificial_chapter_label(evidence):
    return re.sub(
        r"^\s*Chapter\s+\d+\s*:\s*",
        "",
        evidence or "",
        flags=re.IGNORECASE,
    ).strip()


def _metadata_evidence_is_merged(evidence):
    return bool(
        evidence
        and (
            "\n\n" in evidence
            or len(re.findall(r"(^|\n)\s*Chapter\s+\d+\s*:", evidence, re.IGNORECASE)) > 1
        )
    )


def raw_metadata_evidence(evidence):
    raw_evidence = (evidence or "").strip()

    if not raw_evidence:
        return None

    return _strip_artificial_chapter_label(raw_evidence)[:500].strip() or None


def metadata_evidence_warnings(chapter, evidence):
    warnings = []
    raw_evidence = (evidence or "").strip()
    stored_evidence = raw_metadata_evidence(raw_evidence)

    if not raw_evidence:
        return ["metadata_evidence_missing"]

    if _metadata_evidence_has_artificial_chapter_label(raw_evidence):
        warnings.append("metadata_evidence_not_raw")

    if _metadata_evidence_is_merged(raw_evidence):
        warnings.append("metadata_evidence_merged")

    if not stored_evidence:
        warnings.append("metadata_evidence_missing")
    else:
        verification = verify_evidence_text(
            getattr(chapter, "content", "") if chapter else "",
            stored_evidence,
        )
        evidence_context = get_evidence_context(
            getattr(chapter, "content", "") if chapter else "",
            stored_evidence,
        )

        if not verification.verified:
            if verification.ambiguous:
                warnings.append("evidence_match_ambiguous")
            else:
                warnings.append("evidence_not_exact")
            warnings.append("context_unavailable")
            warnings.append("metadata_evidence_weak")
        elif evidence_context.ambiguous:
            warnings.append("evidence_match_ambiguous")
        elif not evidence_context.found:
            warnings.append("context_unavailable")
        elif evidence_context.match_type and evidence_context.match_type != "exact":
            warnings.append("evidence_located_with_normalization")

    return warnings


def metadata_evidence_quality(chapter, evidence):
    warnings = [
        warning
        for warning in metadata_evidence_warnings(chapter, evidence)
        if warning != "evidence_located_with_normalization"
    ]

    if not evidence:
        return 0

    if not warnings:
        return 3

    if warnings == ["metadata_evidence_weak"]:
        return 2

    return 1


def normalize_metadata_value(value):
    if value is None:
        return None

    normalized_value = _normalize_alias(value)

    if not normalized_value or normalized_value.lower() in {"unknown", "n/a", "none", "null"}:
        return None

    return normalized_value


def normalize_title_values(titles):
    normalized_titles = []
    seen_titles = set()

    for title in titles or []:
        normalized_title = normalize_metadata_value(title)

        if not normalized_title:
            continue

        title_key = normalized_title.lower()

        if title_key in seen_titles:
            continue

        normalized_titles.append(normalized_title)
        seen_titles.add(title_key)

    return normalized_titles


def title_list_from_text(titles_text):
    if not titles_text:
        return []

    raw_titles = re.split(r"[\n,;]+", titles_text)
    return normalize_title_values(raw_titles)


def canonical_life_status(value):
    normalized_value = _normalize_alias(value or "").lower().replace("-", " ")

    if not normalized_value:
        return None

    if normalized_value in ALLOWED_LIFE_STATUS_VALUES:
        return normalized_value

    for phrase, status in STATUS_VALUE_ALIASES.items():
        if phrase in normalized_value:
            return status

    return None


def should_keep_status_metadata(status_value, for_existing_character):
    canonical_status = canonical_life_status(status_value)

    if not canonical_status:
        return False

    return canonical_status in REVIEWABLE_LIFE_STATUS_VALUES


def status_evidence_is_direct(status_value, evidence):
    canonical_status = canonical_life_status(status_value)

    if canonical_status == "dead":
        return evidence_has_any(evidence, DEATH_EVIDENCE_TERMS) and not status_evidence_is_uncertain(
            evidence,
        )

    if canonical_status == "alive":
        return evidence_has_any(evidence, ALIVE_EVIDENCE_TERMS) and not status_evidence_is_uncertain(
            evidence,
        )

    return (
        canonical_status is not None
        and evidence_supports_value(evidence, status_value)
        and not status_evidence_is_uncertain(evidence)
    )


def status_evidence_is_uncertain(evidence):
    return bool(STATUS_UNCONFIRMED_RE.search(evidence or ""))


def approved_life_event_status_evidence(character, status_value, chapter=None):
    if canonical_life_status(status_value) != "dead" or not character:
        return None

    query = CharacterLifeEvent.query.filter_by(
        character_id=character.id,
        event_type="death",
        review_status="approved",
    )

    if chapter is not None:
        query = query.filter_by(chapter_id=chapter.id)

    for life_event in query.order_by(CharacterLifeEvent.chapter_id.asc()).all():
        event_chapter = db.session.get(Chapter, life_event.chapter_id)

        for evidence_row in WikiEvidence.query.filter_by(
            entity_type="life_event",
            entity_id=life_event.id,
        ).order_by(WikiEvidence.id.asc()).all():
            event_evidence = (evidence_row.evidence_text or "").strip()

            if not event_evidence:
                continue

            verification = verify_evidence_text(
                getattr(event_chapter, "content", "") if event_chapter else "",
                event_evidence,
                start_offset=evidence_row.start_offset,
                end_offset=evidence_row.end_offset,
                match_type=evidence_row.match_type,
            )

            if not verification.verified:
                continue

            if not status_evidence_is_direct("dead", verification.evidence_text):
                continue

            if not metadata_evidence_attributed_to_character(
                character,
                verification.evidence_text,
                event_chapter,
            ):
                continue

            return verification.evidence_text

    return None


def race_species_evidence_is_explicit(species_value, evidence):
    normalized_value = _normalize_alias(species_value or "").lower()
    normalized_evidence = _normalize_evidence_text(evidence or "").lower()

    if not normalized_value:
        return False

    if not evidence_supports_value(evidence, normalized_value):
        return False

    if normalized_value in HUMAN_SPECIES_TERMS:
        human_patterns = (
            rf"\b(?:is|was|were|became|born as|remained)\s+(?:a\s+)?{re.escape(normalized_value)}\b",
            rf"\b{re.escape(normalized_value)}\s+(?:race|species|bloodline|lineage)\b",
            rf"\b(?:race|species|bloodline|lineage)\s+(?:was|is|of)\s+{re.escape(normalized_value)}\b",
        )
        return any(re.search(pattern, normalized_evidence) for pattern in human_patterns)

    if normalized_value in NON_HUMAN_SPECIES_TERMS:
        return True

    return evidence_has_any(evidence, SPECIES_CONTEXT_TERMS)


def faction_evidence_is_direct(character, faction_value, evidence, chapter=None):
    if FACTION_FORMER_RE.search(evidence or ""):
        return False

    if not evidence_supports_value(evidence, faction_value):
        return False

    faction_pattern = article_optional_value_pattern(faction_value)

    if not faction_pattern:
        return False

    for reference_pattern in character_reference_patterns(character):
        plural_membership_patterns = [
            rf"{faction_pattern}\s+(?:members?|disciples?|servants?|elders?|captains?|"
            rf"commanders?|students?|agents?|officers?|knights?|mages?|warriors?)\s+"
            rf"[^.!?]{{0,160}}{reference_pattern}",
            rf"(?:members?|disciples?|servants?|elders?|captains?|commanders?|students?|"
            rf"agents?|officers?|knights?|mages?|warriors?)\s+of\s+{faction_pattern}\s+"
            rf"[^.!?]{{0,160}}{reference_pattern}",
        ]

        if any(re.search(pattern, evidence or "", re.IGNORECASE) for pattern in plural_membership_patterns):
            return True

    if not metadata_evidence_attributed_to_character(character, evidence, chapter):
        return False

    membership_patterns = [
        rf"\b(?:is|was|were|became|becomes|remained|served|serves|joined)\s+"
        rf"(?:a\s+|an\s+|the\s+)?(?:member|disciple|servant|elder|captain|commander|"
        rf"student|agent|officer|knight|mage|warrior)\s+of\s+{faction_pattern}",
        rf"\b(?:belonged|belongs|affiliated)\s+to\s+{faction_pattern}",
        rf"\b(?:joined)\s+{faction_pattern}",
        rf"\bas\s+(?:a\s+|an\s+|the\s+)?(?:member|disciple|servant|elder|captain|"
        rf"commander|student|agent|officer|knight|mage|warrior)\s+of\s+{faction_pattern}",
        rf"{faction_pattern}\s+(?:member|disciple|servant|elder|captain|commander|"
        rf"student|agent|officer|knight|mage|warrior)\b",
    ]
    return any(re.search(pattern, evidence or "", re.IGNORECASE) for pattern in membership_patterns)


def title_is_generic_label(title_value):
    normalized_title = _normalize_alias(title_value or "").lower()
    title_words = set(_normalized_words(normalized_title))

    if normalized_title in GENERIC_TITLE_WORDS:
        return True

    return bool(title_words & {"man", "woman", "youth", "teenager", "guard", "servant"}) and not (
        title_words & {"disciple", "elder", "captain", "commander", "mage", "warrior"}
    )


def title_overlaps_approved_progression(character, title_value):
    normalized_title = normalize_metadata_field("titles", title_value)

    if not normalized_title:
        return False

    return (
        CharacterProgressionEvent.query.filter_by(
            character_id=character.id,
            review_status="approved",
        )
        .filter(
            db.func.lower(CharacterProgressionEvent.new_value)
            == normalized_title.normalized_value
        )
        .first()
        is not None
    )


def title_evidence_is_direct(character, title_value, evidence, chapter=None):
    if title_is_generic_label(title_value):
        return False

    if TITLE_FUTURE_OR_INTENT_RE.search(evidence or ""):
        return False

    if not evidence_supports_value(evidence, title_value):
        return False

    title_pattern = article_optional_value_pattern(title_value)

    if title_pattern:
        for reference_pattern in character_reference_patterns(character):
            related_person_patterns = [
                rf"(?:\bhe\b|\bshe\b|\bthey\b|{reference_pattern})[^.!?]{{0,80}}"
                rf"\b(?:son|daughter|child|disciple|student|servant|apprentice|"
                rf"brother|sister|wife|husband|friend|companion|assistant)\s+of\s+"
                rf"(?:a\s+|an\s+|the\s+)?{title_pattern}\s+{reference_pattern}",
                rf"(?:\bhe\b|\bshe\b|\bthey\b|{reference_pattern})[^.!?]{{0,80}}"
                rf"\b(?:spoke|talked|met|stood|walked|traveled|fought)\s+"
                rf"(?:to|with|beside|alongside|against)\s+"
                rf"(?:a\s+|an\s+|the\s+)?{title_pattern}\s+{reference_pattern}",
            ]

            if any(
                re.search(pattern, evidence or "", re.IGNORECASE)
                for pattern in related_person_patterns
            ):
                continue

            title_attachment_patterns = [
                rf"{title_pattern}\s+{reference_pattern}",
                rf"{reference_pattern}\s*,\s*(?:the\s+)?{title_pattern}",
                rf"{reference_pattern}\s+(?:was|is|became|becomes|remained)\s+"
                rf"(?:a\s+|an\s+|the\s+)?{title_pattern}",
            ]

            if any(re.search(pattern, evidence or "", re.IGNORECASE) for pattern in title_attachment_patterns):
                return True

    return False


def age_evidence_is_direct(proposed_metadata, evidence):
    if age_evidence_is_apparent_or_rhetorical(evidence):
        return False

    proposed_age = normalize_metadata_field("age_text", proposed_metadata.raw_value)
    evidence_age = normalize_metadata_field("age_text", evidence)

    if (
        proposed_age
        and evidence_age
        and proposed_age.normalized_value == evidence_age.normalized_value
    ):
        return True

    evidence_numbers = set(re.findall(r"\b\d+\b", _normalize_evidence_text(evidence or "")))
    proposed_numbers = set(re.findall(r"\b\d+\b", proposed_metadata.normalized_value or ""))

    return bool(proposed_numbers and proposed_numbers.issubset(evidence_numbers))


def age_evidence_is_apparent_or_rhetorical(evidence):
    return bool(AGE_APPARENT_RE.search(evidence or "") or AGE_RHETORICAL_RE.search(evidence or ""))


def origin_evidence_is_direct(character, origin_value, evidence, chapter=None):
    if not character or ORIGIN_TRAVEL_RE.search(evidence or ""):
        return False

    origin_pattern = article_optional_value_pattern(origin_value)

    if not origin_pattern:
        return False

    text = evidence or ""

    for reference_pattern in character_reference_patterns(character):
        subject_patterns = [
            rf"{reference_pattern}\s+(?:was|is|were|had\s+been)\s+originally\s+from\s+{origin_pattern}",
            rf"{reference_pattern}\s+(?:was|is|were|had\s+been)\s+from\s+{origin_pattern}",
            rf"{reference_pattern}\s+(?:was|is|were|had\s+been)\s+(?:a\s+|an\s+)?native\s+of\s+{origin_pattern}",
            rf"{reference_pattern}\s*,\s*(?:a\s+|an\s+)?native\s+of\s+{origin_pattern}",
            rf"{reference_pattern}\s*,\s*originally\s+from\s+{origin_pattern}",
            rf"{reference_pattern}\s+(?:was\s+|is\s+|had\s+been\s+)?born\s+in\s+{origin_pattern}",
            rf"{reference_pattern}\s+(?:was\s+|is\s+|had\s+been\s+)?raised\s+in\s+{origin_pattern}",
            rf"{reference_pattern}\s+(?:came|comes|hailed|hails)\s+from\s+{origin_pattern}",
            rf"{reference_pattern}\s*,\s*(?:a\s+|an\s+|the\s+)?"
            rf"(?:[A-Za-z-]+\s+){{0,4}}(?:student|scholar|cultivator|disciple|"
            rf"resident|native|person|man|woman|boy|girl|youth|mage|warrior)\s+from\s+{origin_pattern}",
        ]

        if any(re.search(pattern, text, re.IGNORECASE) for pattern in subject_patterns):
            return True

    if not metadata_evidence_attributed_to_character(character, evidence, chapter):
        return False

    generic_origin_patterns = [
        rf"\boriginally\s+from\s+{origin_pattern}",
        rf"\bnative\s+of\s+{origin_pattern}",
        rf"\bborn\s+in\s+{origin_pattern}",
        rf"\braised\s+in\s+{origin_pattern}",
        rf"\b(?:came|comes|hailed|hails)\s+from\s+{origin_pattern}",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in generic_origin_patterns)


def metadata_semantic_warnings(character, field_name, proposed_metadata, evidence, chapter=None):
    warnings = []
    attributed = metadata_evidence_attributed_to_character(character, evidence, chapter)

    if field_name == "age_text":
        if not attributed:
            warnings.append("age_attribution_uncertain")
        if AGE_RHETORICAL_RE.search(evidence or ""):
            warnings.append("age_not_factual")
        if AGE_APPARENT_RE.search(evidence or ""):
            warnings.append("apparent_age_only")
        if not age_evidence_is_direct(proposed_metadata, evidence):
            warnings.append("age_not_proven")
        return warnings

    if field_name == "gender":
        if not attributed:
            warnings.append("metadata_attribution_uncertain")
        if not gender_evidence_is_direct(
            character,
            proposed_metadata.normalized_value,
            evidence,
            chapter,
        ):
            warnings.append("metadata_evidence_weak")
        return warnings

    if field_name == "status":
        if not attributed:
            warnings.append("metadata_attribution_uncertain")
        if status_evidence_is_uncertain(evidence):
            warnings.append("speculative_status")
        if not status_evidence_is_direct(proposed_metadata.normalized_value, evidence):
            warnings.append("status_not_confirmed")
        return warnings

    if field_name == "race_or_species":
        if not attributed:
            warnings.append("species_attribution_uncertain")
        if not race_species_evidence_is_explicit(proposed_metadata.normalized_value, evidence):
            warnings.append("species_not_explicit")
        return warnings

    if field_name == "faction_or_affiliation":
        if FACTION_FORMER_RE.search(evidence or ""):
            warnings.append("former_affiliation_only")
        if not faction_evidence_is_direct(
            character,
            proposed_metadata.raw_value,
            evidence,
            chapter,
        ):
            warnings.append("affiliation_not_proven")
        return warnings

    if field_name == "titles":
        if title_is_generic_label(proposed_metadata.raw_value):
            warnings.append("title_not_proven")
        if TITLE_FUTURE_OR_INTENT_RE.search(evidence or ""):
            warnings.append("promotion_not_completed")
            warnings.append("title_not_current")
        if not title_evidence_is_direct(
            character,
            proposed_metadata.raw_value,
            evidence,
            chapter,
        ):
            warnings.append("title_not_proven")
        return warnings

    if field_name == "origin":
        if ORIGIN_TRAVEL_RE.search(evidence or ""):
            warnings.append("location_not_origin")
        if not origin_evidence_is_direct(
            character,
            proposed_metadata.raw_value,
            evidence,
            chapter,
        ):
            warnings.append("origin_not_proven")
            if not attributed:
                warnings.append("origin_attribution_uncertain")
        return warnings

    if not evidence_supports_value(evidence, proposed_metadata.raw_value):
        warnings.append("metadata_evidence_weak")

    return warnings


def metadata_field_should_be_ignored(character, field_name, proposed_metadata, evidence):
    if field_name == "race_or_species" and not race_species_evidence_is_explicit(
        proposed_metadata.normalized_value,
        evidence,
    ):
        return True

    if field_name == "titles" and title_is_generic_label(proposed_metadata.raw_value):
        return True

    return False


def metadata_evidence_supports_field(character, field_name, proposed_metadata, evidence, chapter=None):
    return not metadata_blocking_warnings(
        metadata_semantic_warnings(
            character,
            field_name,
            proposed_metadata,
            evidence,
            chapter,
        )
    )



def display_metadata_value(field_name, metadata_result):
    if field_name in {"age_text", "gender", "status"}:
        return metadata_result.normalized_value

    return metadata_result.raw_value


def is_assumed_species(character):
    return (
        getattr(character, "race_or_species", None)
        and normalize_metadata_field("race_or_species", character.race_or_species)
        and character.race_or_species_source == "implicit_default"
        and character.race_or_species_confidence == "assumed"
    )


def metadata_proposal_values(metadata, character=None, evidence=None):
    proposals = []

    if not metadata:
        return proposals

    for field in CHARACTER_METADATA_FIELDS:
        new_value = normalize_metadata_field(field, getattr(metadata, field, None))

        if new_value:
            if field == "status" and not should_keep_status_metadata(
                new_value.normalized_value,
                for_existing_character=True,
            ):
                continue

            if character and metadata_field_should_be_ignored(
                character,
                field,
                new_value,
                evidence,
            ):
                continue

            proposals.append((field, new_value))

    for title in normalize_title_values(getattr(metadata, "titles", [])):
        normalized_title = normalize_metadata_field("titles", title)

        if normalized_title:
            if character and metadata_field_should_be_ignored(
                character,
                "titles",
                normalized_title,
                evidence,
            ):
                continue

            proposals.append(("titles", normalized_title))

    return proposals


def append_metadata_proposal_evidence(proposal, chapter, evidence):
    new_evidence = raw_metadata_evidence(evidence)

    if not new_evidence:
        return False

    existing_evidence = proposal.evidence or ""

    if _evidence_match_key(new_evidence) in {
        _evidence_match_key(part)
        for part in existing_evidence.split("\n\n")
        if part.strip()
    }:
        return False

    if not existing_evidence or metadata_evidence_quality(
        chapter,
        new_evidence,
    ) > metadata_evidence_quality(chapter, existing_evidence):
        proposal.evidence = new_evidence
        return True

    return False


def append_metadata_proposal_warning(proposal, warning):
    existing_warnings = proposal.review_warnings.splitlines() if proposal.review_warnings else []

    if warning in existing_warnings:
        return False

    existing_warnings.append(warning)
    proposal.review_warnings = "\n".join(existing_warnings)
    return True


def metadata_value_already_present(character, field_name, proposed_metadata):
    if field_name == "titles":
        return proposed_metadata.normalized_value in {
            normalize_metadata_field("titles", title).normalized_value
            for title in title_list_from_text(character.titles)
            if normalize_metadata_field("titles", title)
        }

    if field_name == "race_or_species" and is_assumed_species(character):
        return False

    current_value = normalize_metadata_field(field_name, getattr(character, field_name, None))
    return bool(
        current_value
        and current_value.normalized_value == proposed_metadata.normalized_value
    )


def current_metadata_value(character, field_name):
    if field_name == "titles":
        return character.titles

    return getattr(character, field_name, None)


def metadata_conflict_warning(character, field_name, proposed_metadata):
    if field_name == "titles":
        return None

    current_value = normalize_metadata_field(field_name, getattr(character, field_name, None))

    if current_value and current_value.normalized_value != proposed_metadata.normalized_value:
        if field_name == "race_or_species" and is_assumed_species(character):
            return "Overrides implicit default species."

        return "Proposed metadata differs from the current character value."

    if field_name == "race_or_species" and is_assumed_species(character):
        return "Confirms previously assumed default species."

    return None


def existing_different_metadata_proposal(character, field_name, proposed_metadata):
    proposal_rows = CharacterMetadataProposal.query.filter_by(
        character_id=character.id,
        field_name=field_name,
    ).all()

    for proposal in proposal_rows:
        if proposal.normalized_value and proposal.normalized_value != proposed_metadata.normalized_value:
            return True

    return False


def find_existing_metadata_proposal(character, field_name, proposed_metadata):
    proposal_rows = CharacterMetadataProposal.query.filter_by(
        character_id=character.id,
        field_name=field_name,
    ).all()

    for proposal in proposal_rows:
        if proposal.normalized_value == proposed_metadata.normalized_value:
            return proposal

    for proposal in proposal_rows:
        normalized_existing = proposal.normalized_value or _evidence_match_key(proposal.proposed_value)

        if is_weak_variation(normalized_existing, proposed_metadata.normalized_value):
            append_metadata_proposal_warning(
                proposal,
                "Weak metadata variation merged by high normalized similarity.",
            )
            return proposal

    return None


def metadata_warning_text(warnings):
    return "\n".join(warnings) if warnings else None


def can_auto_approve_metadata(character, field_name, proposed_metadata, warnings, evidence, chapter=None):
    combined_warnings = [
        *metadata_warning_list(warnings),
        *metadata_warning_list(proposed_metadata.warnings),
    ]

    if metadata_warnings_block_auto_approval(combined_warnings):
        return False

    current_value = normalize_metadata_field(field_name, getattr(character, field_name, None))

    if current_value and current_value.normalized_value != proposed_metadata.normalized_value:
        return False

    if field_name == "gender":
        return (
            proposed_metadata.confidence_score >= 0.9
            and metadata_evidence_attributed_to_character(character, evidence, chapter)
            and metadata_evidence_supports_field(
                character,
                field_name,
                proposed_metadata,
                evidence,
                chapter,
            )
        )

    if field_name == "age_text":
        return (
            proposed_metadata.confidence_score >= 0.78
            and metadata_evidence_attributed_to_character(character, evidence, chapter)
            and metadata_evidence_supports_field(
                character,
                field_name,
                proposed_metadata,
                evidence,
                chapter,
            )
        )

    if field_name == "status":
        return (
            proposed_metadata.confidence_score >= 0.9
            and metadata_evidence_attributed_to_character(character, evidence, chapter)
            and metadata_evidence_supports_field(
                character,
                field_name,
                proposed_metadata,
                evidence,
                chapter,
            )
        )

    if field_name == "race_or_species":
        return (
            proposed_metadata.confidence_score >= 0.78
            and metadata_evidence_attributed_to_character(character, evidence, chapter)
            and metadata_evidence_supports_field(
                character,
                field_name,
                proposed_metadata,
                evidence,
                chapter,
            )
        )

    if field_name == "faction_or_affiliation":
        return (
            proposed_metadata.confidence_score >= 0.78
            and metadata_evidence_supports_field(
                character,
                field_name,
                proposed_metadata,
                evidence,
                chapter,
            )
        )

    if field_name == "titles":
        return (
            proposed_metadata.confidence_score >= 0.72
            and metadata_evidence_supports_field(
                character,
                field_name,
                proposed_metadata,
                evidence,
                chapter,
            )
            and not title_overlaps_approved_progression(character, proposed_metadata.raw_value)
        )

    if field_name == "origin":
        return (
            proposed_metadata.confidence_score >= 0.78
            and metadata_evidence_supports_field(
                character,
                field_name,
                proposed_metadata,
                evidence,
                chapter,
            )
        )

    return False


def metadata_result_from_proposal(proposal):
    normalized = normalize_metadata_field(
        proposal.field_name,
        proposal.raw_proposed_value or proposal.proposed_value,
    )

    if not normalized:
        return None

    return SimpleNamespace(
        raw_value=normalized.raw_value,
        normalized_value=proposal.normalized_value or normalized.normalized_value,
        confidence_score=(
            proposal.confidence_score
            if proposal.confidence_score is not None
            else normalized.confidence_score
        ),
        extraction_reason=proposal.extraction_reason or normalized.extraction_reason,
        warnings=tuple(normalized.warnings or ()),
    )


def apply_metadata_value_to_character(character, field_name, proposed_metadata):
    if field_name == "titles":
        character.titles = _merge_description(character.titles, proposed_metadata.raw_value)
    else:
        setattr(character, field_name, proposed_metadata.normalized_value)

    if field_name == "race_or_species":
        character.race_or_species_source = "extracted"
        character.race_or_species_confidence = "confirmed"


def revalidate_metadata_proposal(proposal, chapter=None, evidence=None):
    stored_proposal = proposal if proposal.character else db.session.get(
        CharacterMetadataProposal,
        proposal.id,
    )
    character = proposal.character or (stored_proposal.character if stored_proposal else None)
    proposed_metadata = metadata_result_from_proposal(proposal)

    if not character or not proposed_metadata:
        return False

    if manually_reviewed_record(proposal):
        return False

    candidate_evidence = evidence if evidence is not None else proposal.evidence
    evidence_verification = verify_evidence_text(
        getattr(chapter, "content", "") if chapter else "",
        candidate_evidence,
    )

    if evidence_verification.verified:
        candidate_evidence = evidence_verification.evidence_text

    field_supported = metadata_evidence_supports_field(
        character,
        proposal.field_name,
        proposed_metadata,
        candidate_evidence,
        chapter,
    )

    if not evidence_verification.verified or not field_supported:
        recovery = recover_fact_evidence(
            getattr(chapter, "content", "") if chapter else "",
            "metadata",
            {
                "field_name": proposal.field_name,
                "value": proposed_metadata.raw_value,
                "character_name": character.name,
                "evidence": candidate_evidence,
            },
            aliases=character_reference_values(character),
            canonical_facts={
                "competing_character_references": competing_character_reference_values(
                    character,
                ),
            },
            allow_verified_recovery=evidence_verification.verified,
        )

        if recovery.recovered:
            candidate_evidence = recovery.evidence_text
            field_supported = metadata_evidence_supports_field(
                character,
                proposal.field_name,
                proposed_metadata,
                candidate_evidence,
                chapter,
            )

    if (
        proposal.field_name == "status"
        and canonical_life_status(proposed_metadata.normalized_value) == "dead"
        and not field_supported
    ):
        life_event_evidence = approved_life_event_status_evidence(
            character,
            proposed_metadata.normalized_value,
            chapter,
        )

        if life_event_evidence:
            candidate_evidence = life_event_evidence
            field_supported = metadata_evidence_supports_field(
                character,
                proposal.field_name,
                proposed_metadata,
                candidate_evidence,
                chapter,
            )

    evidence_text = raw_metadata_evidence(candidate_evidence)
    warnings = list(proposed_metadata.warnings)
    conflict_warning = metadata_conflict_warning(
        character,
        proposal.field_name,
        proposed_metadata,
    )

    if conflict_warning:
        warnings.append(conflict_warning)

    if existing_different_metadata_proposal(character, proposal.field_name, proposed_metadata):
        warnings.append(
            "Another metadata proposal exists for this character and field with a different value."
        )

    if (
        proposal.field_name == "titles"
        and title_overlaps_approved_progression(character, proposed_metadata.raw_value)
    ):
        warnings.append("Title overlaps an approved progression/position fact.")

    warnings.extend(metadata_evidence_warnings(chapter, candidate_evidence))
    warnings.extend(
        metadata_semantic_warnings(
            character,
            proposal.field_name,
            proposed_metadata,
            candidate_evidence,
            chapter,
        )
    )

    if (
        evidence_text
        and not field_supported
        and "metadata_evidence_weak" not in warnings
        and not metadata_blocking_warnings(warnings)
    ):
        warnings.append("metadata_evidence_weak")

    deduped_warnings = []
    for warning in warnings:
        if warning and warning not in deduped_warnings:
            deduped_warnings.append(warning)

    warning_text = metadata_warning_text(deduped_warnings)
    auto_approved = can_auto_approve_metadata(
        character,
        proposal.field_name,
        proposed_metadata,
        deduped_warnings,
        candidate_evidence,
        chapter,
    )

    changed = (
        proposal.evidence != evidence_text
        or proposal.review_warnings != warning_text
        or proposal.confidence_score != proposed_metadata.confidence_score
        or proposal.auto_approved != auto_approved
        or (auto_approved and proposal.review_status != "approved")
        or (
            not auto_approved
            and proposal.review_status == "approved"
            and proposal.auto_approved
        )
    )

    proposal.evidence = evidence_text
    proposal.review_warnings = warning_text
    proposal.confidence_score = proposed_metadata.confidence_score
    proposal.normalized_value = proposed_metadata.normalized_value
    proposal.proposed_value = display_metadata_value(proposal.field_name, proposed_metadata)

    if auto_approved:
        proposal.auto_approved = True
        proposal.review_status = "approved"
        apply_metadata_value_to_character(character, proposal.field_name, proposed_metadata)
    else:
        proposal.auto_approved = False

        if proposal.review_status != "rejected":
            proposal.review_status = "pending"

    return changed


def create_character_metadata_proposals(novel, chapter, character, metadata, evidence):
    proposals_created = 0

    for field_name, proposed_metadata in metadata_proposal_values(metadata, character, evidence):
        candidate_evidence = evidence
        evidence_verification = verify_evidence_text(
            getattr(chapter, "content", "") if chapter else "",
            candidate_evidence,
        )

        if evidence_verification.verified:
            candidate_evidence = evidence_verification.evidence_text

        if not evidence_verification.verified or not metadata_evidence_supports_field(
            character,
            field_name,
            proposed_metadata,
            candidate_evidence,
            chapter,
        ):
            recovery = recover_fact_evidence(
                getattr(chapter, "content", "") if chapter else "",
                "metadata",
                {
                    "field_name": field_name,
                    "value": proposed_metadata.raw_value,
                    "character_name": character.name,
                    "evidence": candidate_evidence,
                },
                aliases=character_reference_values(character),
                canonical_facts={
                    "competing_character_references": competing_character_reference_values(
                        character,
                    ),
                },
                allow_verified_recovery=evidence_verification.verified,
            )

            if recovery.recovered:
                candidate_evidence = recovery.evidence_text

        if (
            field_name == "status"
            and canonical_life_status(proposed_metadata.normalized_value) == "dead"
            and not metadata_evidence_supports_field(
                character,
                field_name,
                proposed_metadata,
                candidate_evidence,
                chapter,
            )
        ):
            life_event_evidence = approved_life_event_status_evidence(
                character,
                proposed_metadata.normalized_value,
                chapter,
            )

            if life_event_evidence:
                candidate_evidence = life_event_evidence

        evidence_text = raw_metadata_evidence(candidate_evidence)
        evidence_warnings = metadata_evidence_warnings(chapter, candidate_evidence)

        if metadata_value_already_present(character, field_name, proposed_metadata):
            continue

        proposal = find_existing_metadata_proposal(character, field_name, proposed_metadata)
        warnings = list(proposed_metadata.warnings)
        conflict_warning = metadata_conflict_warning(character, field_name, proposed_metadata)

        if conflict_warning:
            warnings.append(conflict_warning)

        if existing_different_metadata_proposal(character, field_name, proposed_metadata):
            warnings.append(
                "Another metadata proposal exists for this character and field with a different value."
            )

        if (
            field_name == "titles"
            and title_overlaps_approved_progression(character, proposed_metadata.raw_value)
        ):
            warnings.append("Title overlaps an approved progression/position fact.")

        warnings.extend(evidence_warnings)
        warnings.extend(
            metadata_semantic_warnings(
                character,
                field_name,
                proposed_metadata,
                candidate_evidence,
                chapter,
            )
        )

        field_supported = metadata_evidence_supports_field(
            character,
            field_name,
            proposed_metadata,
            candidate_evidence,
            chapter,
        )

        if (
            not field_supported
            and "metadata_evidence_weak" not in warnings
            and not metadata_blocking_warnings(warnings)
        ):
            warnings.append("metadata_evidence_weak")

        if proposal:
            evidence_changed = append_metadata_proposal_evidence(
                proposal,
                chapter,
                candidate_evidence,
            )
            record_ai_evidence_audit(
                novel,
                chapter,
                "character_metadata_proposal",
                proposal.id,
                evidence,
                source_extractor="metadata",
                canonical_evidence_text=proposal.evidence,
            )
            if evidence_changed:
                revalidate_metadata_proposal(proposal, chapter, proposal.evidence)
            else:
                for warning in warnings:
                    append_metadata_proposal_warning(proposal, warning)
            continue

        warning_text = metadata_warning_text(warnings)
        auto_approved = can_auto_approve_metadata(
            character,
            field_name,
            proposed_metadata,
            warnings,
            candidate_evidence,
            chapter,
        )

        proposal = CharacterMetadataProposal(
            novel_id=novel.id,
            character_id=character.id,
            chapter_id=chapter.id,
            field_name=field_name,
            old_value=current_metadata_value(character, field_name),
            raw_proposed_value=proposed_metadata.raw_value,
            proposed_value=display_metadata_value(field_name, proposed_metadata),
            normalized_value=proposed_metadata.normalized_value,
            confidence_score=proposed_metadata.confidence_score,
            extraction_reason=proposed_metadata.extraction_reason,
            auto_approved=auto_approved,
            evidence=evidence_text,
            review_warnings=warning_text,
            review_status="approved" if auto_approved else "pending",
        )
        db.session.add(proposal)
        db.session.flush()
        record_ai_evidence_audit(
            novel,
            chapter,
            "character_metadata_proposal",
            proposal.id,
            evidence,
            source_extractor="metadata",
            canonical_evidence_text=evidence_text,
        )

        if auto_approved:
            apply_metadata_value_to_character(character, field_name, proposed_metadata)

        proposals_created += 1

    return proposals_created
