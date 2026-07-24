import re
from dataclasses import dataclass, field

from app.models import Character, db
from app.services.extraction.identity import (
    alias_is_useful_for_resolution,
    looks_like_title_style_name,
    normalize_alias,
)


CHARACTER_PRONOUNS = {
    "he",
    "she",
    "him",
    "her",
    "his",
    "hers",
    "they",
    "them",
    "their",
    "theirs",
}

SUBJECT_CHARACTER_PRONOUNS = {
    "he",
    "she",
    "they",
}

OBJECT_CHARACTER_PRONOUNS = {
    "him",
    "her",
    "them",
}

POSSESSIVE_CHARACTER_PRONOUNS = {
    "his",
    "her",
    "hers",
    "their",
    "theirs",
}

OBJECT_PRONOUNS = {
    "it",
    "its",
    "this",
    "that",
    "these",
    "those",
}

PROGRESSION_POSSESSIVE_NOUNS = {
    "base",
    "class",
    "cultivation",
    "foundation",
    "level",
    "power",
    "rank",
    "realm",
    "stage",
    "state",
}

TITLE_PREFIXES = {
    "Big",
    "Brother",
    "Elder",
    "Founder",
    "Grand",
    "Grandpa",
    "Junior",
    "Lady",
    "Lord",
    "Madam",
    "Master",
    "Senior",
    "Sister",
}

COLLECTIVE_MARKERS = (
    r"\bboth\b",
    r"\beach\b",
    r"\ball\s+(?:of\s+)?(?:three|four|five|six|seven|eight|nine|ten|\d+|them)\b",
    r"\bthe\s+two\s+of\s+them\b",
    r"\bboth\s+of\s+whom\b",
)

AMBIGUOUS_COLLECTIVE_MARKERS = (
    r"\bone\s+of\s+(?:them|whom)\b",
    r"\bsome\s+of\s+(?:them|whom)\b",
)

SUBJECT_PREFIX_WORDS = {
    "afterward",
    "afterwards",
    "finally",
    "however",
    "immediately",
    "later",
    "meanwhile",
    "now",
    "quickly",
    "silently",
    "slowly",
    "soon",
    "suddenly",
    "then",
}


@dataclass(frozen=True)
class CharacterAttributionResult:
    resolved: bool
    character: Character | None = None
    character_id: int | None = None
    canonical_name: str | None = None
    match_type: str = "unresolved"
    confidence: float = 0.0
    ambiguous: bool = False
    supporting_text: str | None = None
    matched_reference: str | None = None
    risk_flags: list[str] = field(default_factory=list)


def text_contains_exact_reference(text, reference):
    normalized_text = " ".join(str(text or "").split())
    normalized_reference = normalize_alias(reference)

    if not normalized_text or not normalized_reference:
        return False

    return re.search(
        rf"(?<![A-Za-z0-9]){re.escape(normalized_reference)}(?![A-Za-z0-9])",
        normalized_text,
        flags=re.IGNORECASE,
    ) is not None


def text_reference_positions(text, reference):
    normalized_text = " ".join(str(text or "").split())
    normalized_reference = normalize_alias(reference)

    if not normalized_text or not normalized_reference:
        return []

    return [
        match.start()
        for match in re.finditer(
            rf"(?<![A-Za-z0-9]){re.escape(normalized_reference)}(?![A-Za-z0-9])",
            normalized_text,
            flags=re.IGNORECASE,
        )
    ]


def _words(text):
    return {
        word.lower()
        for word in re.findall(r"[A-Za-z']+", str(text or ""))
    }


def _candidate_aliases(character):
    aliases = []

    for alias in getattr(character, "aliases", []) or []:
        normalized_alias = normalize_alias(alias.alias)

        if normalized_alias and alias_is_useful_for_resolution(normalized_alias):
            aliases.append(normalized_alias)

    return aliases


def _candidate_references(character):
    references = [(character.name, "canonical_name", 1.0)]

    for alias in _candidate_aliases(character):
        references.append((alias, "approved_alias", 0.92))

    if looks_like_title_style_name(character.name):
        references.append((character.name, "stable_title", 0.9))
        words = normalize_alias(character.name).split()

        if len(words) >= 3 and words[0] in TITLE_PREFIXES:
            title_variant = " ".join(words[1:])

            if looks_like_title_style_name(title_variant):
                references.append((title_variant, "stable_title", 0.9))

    return references


def _reference_matches(characters, text, allowed_match_types):
    matches = []

    for character in characters:
        for reference, match_type, confidence in _candidate_references(character):
            if match_type not in allowed_match_types:
                continue

            for position in text_reference_positions(text, reference):
                matches.append((character, reference, match_type, confidence, position))

    return matches


def _unique_reference_matches(characters, text, allowed_match_types):
    matches = _reference_matches(characters, text, allowed_match_types)

    if not matches:
        return None

    character_ids = {match[0].id for match in matches}

    if len(character_ids) > 1:
        return CharacterAttributionResult(
            False,
            ambiguous=True,
            supporting_text=text,
            risk_flags=["alias_ambiguous"],
        )

    priority = {
        "canonical_name": 3,
        "approved_alias": 2,
        "stable_title": 1,
    }
    character, reference, match_type, confidence, _ = max(
        matches,
        key=lambda match: priority.get(match[2], 0),
    )
    return CharacterAttributionResult(
        True,
        character=character,
        character_id=character.id,
        canonical_name=character.name,
        match_type=match_type,
        confidence=confidence,
        supporting_text=text,
        matched_reference=reference,
        risk_flags=[f"{match_type}_supported"],
    )


def _target_reference_match(matches, target_character):
    if not target_character:
        return None

    target_matches = [
        match
        for match in matches
        if match[0].id == getattr(target_character, "id", None)
    ]

    if not target_matches:
        return None

    priority = {
        "canonical_name": 3,
        "approved_alias": 2,
        "stable_title": 1,
    }
    return max(target_matches, key=lambda match: priority.get(match[2], 0))


def _has_collective_distribution(text):
    normalized_text = " ".join(str(text or "").split()).lower()

    if not normalized_text:
        return False

    if any(re.search(pattern, normalized_text) for pattern in AMBIGUOUS_COLLECTIVE_MARKERS):
        return False

    return any(re.search(pattern, normalized_text) for pattern in COLLECTIVE_MARKERS)


def _collective_reference_match(characters, text, allowed_match_types, target_character):
    if not target_character or not _has_collective_distribution(text):
        return None

    matches = _reference_matches(characters, text, allowed_match_types)
    character_ids = {match[0].id for match in matches}

    if len(character_ids) < 2 or getattr(target_character, "id", None) not in character_ids:
        return None

    target_match = _target_reference_match(matches, target_character)

    if not target_match:
        return None

    character, reference, _, _, _ = target_match
    method = "collective_both" if re.search(r"\bboth\b", text, flags=re.IGNORECASE) else "collective_statement"

    return CharacterAttributionResult(
        True,
        character=character,
        character_id=character.id,
        canonical_name=character.name,
        match_type=method,
        confidence=0.88,
        supporting_text=text,
        matched_reference=reference,
        risk_flags=["collective_statement_supported"],
    )


def _contains_character_pronoun(text):
    return bool(_words(text) & CHARACTER_PRONOUNS)


def _contains_object_pronoun_without_character_pronoun(text):
    words = _words(text)
    return bool(words & OBJECT_PRONOUNS) and not bool(words & CHARACTER_PRONOUNS)


def _split_sentences(text):
    text = str(text or "").strip()

    if not text:
        return []

    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text)
        if sentence.strip()
    ]


def _normalized_sentence(text):
    return " ".join(str(text or "").split()).lower()


def _evidence_sentence_index(sentences, evidence_text):
    normalized_evidence = _normalized_sentence(evidence_text)

    if not normalized_evidence:
        return len(sentences) - 1 if sentences else None

    for index, sentence in enumerate(sentences):
        normalized_sentence = _normalized_sentence(sentence)

        if normalized_evidence == normalized_sentence or normalized_evidence in normalized_sentence:
            return index

    for index, sentence in enumerate(sentences):
        normalized_sentence = _normalized_sentence(sentence)

        if normalized_sentence and normalized_sentence in normalized_evidence:
            return index

    return len(sentences) - 1 if sentences else None


def _reference_is_subject_like(sentence, position, reference):
    prefix = str(sentence or "")[:position].strip()
    prefix = prefix.strip("\"'“”‘’()[]")

    if not prefix:
        return True

    prefix_words = re.findall(r"[A-Za-z']+", prefix.lower())

    if not prefix_words:
        return True

    if prefix_words[-1] in {"at", "beside", "by", "for", "from", "in", "into", "near", "of", "on", "to", "toward", "with"}:
        return False

    if all(word in SUBJECT_PREFIX_WORDS for word in prefix_words):
        return True

    suffix = str(sentence or "")[position + len(reference):]
    return re.match(
        r"^\s*,?\s*(?:who\s+)?(?:"
        r"am|are|became|becomes|can|could|did|does|entered|felt|found|"
        r"had|has|have|is|looked|opened|reached|said|sat|stood|was|were|"
        r"will|would|[A-Za-z]+(?:ed|ing)"
        r")\b",
        suffix,
        flags=re.IGNORECASE,
    ) is not None


def _breaks_character_subject_continuity(sentence):
    text = str(sentence or "").strip().strip("\"'“”‘’")

    if not text or _contains_character_pronoun(text):
        return False

    return re.match(
        r"^(?:(?:meanwhile|later|elsewhere|afterward|afterwards|then)\s*,?\s*)?"
        r"(?:a|an|another|the|this|that)\s+"
        r"[A-Za-z][A-Za-z'’-]*(?:\s+[A-Za-z][A-Za-z'’-]*){0,4}\s+"
        r"(?:am|are|became|began|came|did|fell|grew|had|has|is|opened|rang|rose|"
        r"seemed|stood|was|were|[A-Za-z]+(?:ed|ing))\b",
        text,
        flags=re.IGNORECASE,
    ) is not None


def _explicit_character_references(characters, sentence):
    references = []

    for match in _reference_matches(
        characters,
        sentence,
        {"canonical_name", "approved_alias", "stable_title"},
    ):
        character, reference, match_type, confidence, position = match
        references.append(
            {
                "character": character,
                "reference": reference,
                "match_type": match_type,
                "confidence": confidence,
                "position": position,
                "subject_like": _reference_is_subject_like(
                    sentence,
                    position,
                    reference,
                ),
            }
        )

    return references


def _unique_subject_reference(characters, sentence):
    references = _explicit_character_references(characters, sentence)

    if not references:
        return None, False

    character_ids = {reference["character"].id for reference in references}

    if len(character_ids) > 1:
        return None, True

    subject_references = [reference for reference in references if reference["subject_like"]]
    subject_character_ids = {reference["character"].id for reference in subject_references}

    if len(subject_character_ids) == 1:
        subject_reference = min(subject_references, key=lambda reference: reference["position"])
        return subject_reference, False

    return None, True


def _unique_grammatical_subject_reference(characters, sentence):
    references = _explicit_character_references(characters, sentence)

    if not references:
        return None, False

    subject_references = [reference for reference in references if reference["subject_like"]]
    subject_character_ids = {reference["character"].id for reference in subject_references}

    if len(subject_character_ids) == 1:
        return min(subject_references, key=lambda reference: reference["position"]), False

    if len(subject_character_ids) > 1:
        return None, True

    character_ids = {reference["character"].id for reference in references}
    return None, len(character_ids) > 1


def _reporting_clause_subject_reference(characters, sentence):
    text = str(sentence or "")
    quote_end = max(
        text.rfind("\""),
        text.rfind("”"),
        text.rfind("’"),
    )

    if quote_end < 0:
        return None, False

    reporting_clause = text[quote_end + 1:]

    if not re.search(
        r"\b(?:asked|called|cried|exclaimed|replied|said|shouted|whispered|"
        r"yelled)\b",
        reporting_clause,
        flags=re.IGNORECASE,
    ):
        return None, False

    references = _explicit_character_references(characters, reporting_clause)

    if not references:
        return None, False

    subject_references = [
        reference
        for reference in references
        if reference["subject_like"]
    ]
    character_ids = {
        reference["character"].id
        for reference in subject_references
    }

    if len(character_ids) == 1:
        return min(
            subject_references,
            key=lambda reference: reference["position"],
        ), False

    return None, bool(character_ids)


def _unique_question_topic_reference(characters, sentence):
    if "?" not in str(sentence or ""):
        return None, False

    reporting_reference, reporting_ambiguous = _reporting_clause_subject_reference(
        characters,
        sentence,
    )

    if reporting_reference or reporting_ambiguous:
        return None, False

    references = _explicit_character_references(characters, sentence)

    if not references:
        return None, False

    character_ids = {reference["character"].id for reference in references}

    if len(character_ids) != 1:
        return None, True

    reference = min(references, key=lambda item: item["position"])
    pattern = rf"\b(?:what\s+happened\s+to|where\s+(?:is|was)|what\s+about)\s+{re.escape(reference['reference'])}\b"

    if re.search(pattern, sentence, flags=re.IGNORECASE):
        return reference, False

    return None, True


def _forward_identity_reference(characters, sentence):
    references = _explicit_character_references(characters, sentence)

    if not references:
        return None, False

    matches = []

    for reference in references:
        escaped_reference = re.escape(reference["reference"])
        patterns = (
            rf"\b(?:his|her|their)\s+name\s+(?:is|was)\s+{escaped_reference}\b",
            rf"\b(?:he|she|they)\s+(?:is|was|were)\s+"
            rf"(?:called|known\s+as|named)\s+{escaped_reference}\b",
            rf"\b(?:the|this|that)\s+"
            rf"(?:boy|cultivator|disciple|elder|figure|girl|guard|man|person|"
            rf"servant|woman|youth)\s+(?:is|was)\s+"
            rf"(?:called|known\s+as|named)\s+{escaped_reference}\b",
        )

        if any(
            re.search(pattern, sentence, flags=re.IGNORECASE)
            for pattern in patterns
        ):
            matches.append(reference)

    character_ids = {match["character"].id for match in matches}

    if len(character_ids) == 1:
        return matches[0], False

    return None, len(character_ids) > 1


def _forward_address_reference(characters, sentence):
    text = str(sentence or "")

    if not text.startswith(("\"", "'", "“", "‘")):
        return None, False

    quote_end_positions = [
        position
        for position in (
            text.find("\"", 1),
            text.find("”", 1),
            text.find("’", 1),
        )
        if position >= 0
    ]

    if not quote_end_positions:
        return None, False

    quoted_text = text[:min(quote_end_positions) + 1]

    if not re.search(
        r"\b(?:greetings|hello|welcome|brother|sister|elder|master|lord|lady)\b",
        quoted_text,
        flags=re.IGNORECASE,
    ):
        return None, False

    references = _explicit_character_references(characters, quoted_text)
    character_ids = {reference["character"].id for reference in references}

    if len(character_ids) == 1:
        return references[0], False

    return None, len(character_ids) > 1


def _local_forward_character(characters, evidence_text, local_context):
    if not _contains_character_pronoun(evidence_text):
        return None

    sentences = _split_sentences(local_context)
    evidence_index = _evidence_sentence_index(sentences, evidence_text)

    if evidence_index is None or evidence_index >= len(sentences) - 1:
        return None

    addressed_reference = None

    for sentence in sentences[evidence_index + 1:]:
        identity_reference, identity_ambiguous = _forward_identity_reference(
            characters,
            sentence,
        )

        if identity_ambiguous:
            return CharacterAttributionResult(
                False,
                ambiguous=True,
                supporting_text=local_context,
                risk_flags=["context_attribution_ambiguous"],
            )

        if identity_reference:
            character = identity_reference["character"]
            return CharacterAttributionResult(
                True,
                character=character,
                character_id=character.id,
                canonical_name=character.name,
                match_type="unique_forward_identity",
                confidence=0.82,
                supporting_text=local_context,
                matched_reference=identity_reference["reference"],
                risk_flags=["context_supported_attribution"],
            )

        address_reference, address_ambiguous = _forward_address_reference(
            characters,
            sentence,
        )

        if address_ambiguous:
            return CharacterAttributionResult(
                False,
                ambiguous=True,
                supporting_text=local_context,
                risk_flags=["context_attribution_ambiguous"],
            )

        if address_reference:
            addressed_reference = address_reference
            continue

        reporting_reference, reporting_ambiguous = _reporting_clause_subject_reference(
            characters,
            sentence,
        )

        if reporting_ambiguous:
            return CharacterAttributionResult(
                False,
                ambiguous=True,
                supporting_text=local_context,
                risk_flags=["context_attribution_ambiguous"],
            )

        subject_reference, subject_ambiguous = _unique_grammatical_subject_reference(
            characters,
            sentence,
        )

        if subject_ambiguous:
            return CharacterAttributionResult(
                False,
                ambiguous=True,
                supporting_text=local_context,
                risk_flags=["context_attribution_ambiguous"],
            )

        if subject_reference:
            if (
                addressed_reference
                and subject_reference["character"].id
                == addressed_reference["character"].id
            ):
                character = addressed_reference["character"]
                return CharacterAttributionResult(
                    True,
                    character=character,
                    character_id=character.id,
                    canonical_name=character.name,
                    match_type="unique_forward_address_identity",
                    confidence=0.8,
                    supporting_text=local_context,
                    matched_reference=addressed_reference["reference"],
                    risk_flags=["context_supported_attribution"],
                )

            return CharacterAttributionResult(
                False,
                ambiguous=True,
                supporting_text=local_context,
                risk_flags=["context_attribution_ambiguous"],
            )

        references = _explicit_character_references(characters, sentence)

        if references:
            referenced_ids = {
                reference["character"].id
                for reference in references
            }

            if (
                addressed_reference
                and referenced_ids == {addressed_reference["character"].id}
            ):
                character = addressed_reference["character"]
                return CharacterAttributionResult(
                    True,
                    character=character,
                    character_id=character.id,
                    canonical_name=character.name,
                    match_type="unique_forward_address_identity",
                    confidence=0.8,
                    supporting_text=local_context,
                    matched_reference=addressed_reference["reference"],
                    risk_flags=["context_supported_attribution"],
                )

            return CharacterAttributionResult(
                False,
                ambiguous=True,
                supporting_text=local_context,
                risk_flags=["context_attribution_ambiguous"],
            )

        if _breaks_character_subject_continuity(sentence):
            return None

    return None


def _pronoun_method(evidence_text):
    words = _words(evidence_text)

    if words & POSSESSIVE_CHARACTER_PRONOUNS:
        return "unique_possessive_pronoun"

    if words & OBJECT_CHARACTER_PRONOUNS:
        return "unique_object_coreference"

    return "unique_subject_continuity"


def _contains_progression_possessive_chain_phrase(text):
    words = _words(text)

    if not (words & POSSESSIVE_CHARACTER_PRONOUNS):
        return False

    return bool(words & PROGRESSION_POSSESSIVE_NOUNS)


def _object_pronoun_progression_sentence_supports_value(evidence_text, target_value):
    if not _contains_object_pronoun_without_character_pronoun(evidence_text):
        return False

    normalized_evidence = _normalized_sentence(evidence_text)
    normalized_value = _normalized_sentence(target_value)

    if not normalized_evidence or not normalized_value:
        return False

    return normalized_value in normalized_evidence or all(
        word in normalized_evidence
        for word in normalized_value.split()[:2]
    )


def _local_pronoun_character(characters, evidence_text, local_context):
    if not _contains_character_pronoun(evidence_text):
        return None

    context = str(local_context or "").strip()
    evidence = str(evidence_text or "").strip()

    if not context or not evidence:
        return None

    sentences = _split_sentences(context)
    evidence_index = _evidence_sentence_index(sentences, evidence)

    if evidence_index is None:
        return None

    evidence_sentence = sentences[evidence_index]
    evidence_references = _explicit_character_references(characters, evidence_sentence)

    if evidence_references:
        character_ids = {reference["character"].id for reference in evidence_references}

        if len(character_ids) > 1:
            return CharacterAttributionResult(
                False,
                ambiguous=True,
                supporting_text=local_context,
                risk_flags=["context_attribution_ambiguous"],
            )

        # Direct explicit names in the evidence sentence should have resolved earlier.
        return None

    antecedent = None
    ambiguous = False
    for sentence_index in range(0, evidence_index):
        sentence = sentences[sentence_index]
        reporting_reference, reporting_ambiguous = _reporting_clause_subject_reference(
            characters,
            sentence,
        )

        if reporting_ambiguous:
            ambiguous = True
            antecedent = None
            continue

        if reporting_reference:
            antecedent = reporting_reference
            ambiguous = False
            continue

        topic_reference, topic_ambiguous = _unique_question_topic_reference(characters, sentence)

        if topic_ambiguous:
            ambiguous = True
            antecedent = None
            continue

        if topic_reference:
            antecedent = topic_reference
            ambiguous = False
            continue

        subject_reference, subject_ambiguous = _unique_subject_reference(characters, sentence)

        if subject_ambiguous:
            ambiguous = True
            antecedent = None
            continue

        if subject_reference:
            antecedent = subject_reference
            ambiguous = False
            continue

        references = _explicit_character_references(characters, sentence)

        if references:
            referenced_ids = {reference["character"].id for reference in references}

            if antecedent and referenced_ids == {antecedent["character"].id}:
                continue

            ambiguous = True
            antecedent = None
            continue

        if _contains_character_pronoun(sentence):
            if antecedent and not ambiguous:
                continue

            ambiguous = True
            antecedent = None
            continue

        if _breaks_character_subject_continuity(sentence):
            antecedent = None
            ambiguous = False

    if ambiguous or not antecedent:
        if ambiguous:
            return CharacterAttributionResult(
                False,
                ambiguous=True,
                supporting_text=local_context,
                risk_flags=["context_attribution_ambiguous"],
            )

        return None

    character = antecedent["character"]
    return CharacterAttributionResult(
        True,
        character=character,
        character_id=character.id,
        canonical_name=character.name,
        match_type=_pronoun_method(evidence_text),
        confidence=0.84,
        supporting_text=local_context,
        matched_reference=antecedent["reference"],
        risk_flags=["context_supported_attribution"],
    )


def _local_progression_possessive_character(characters, evidence_text, local_context, target_value=None):
    if not target_value or not _contains_progression_possessive_chain_phrase(evidence_text):
        return None

    context = str(local_context or "").strip()
    evidence = str(evidence_text or "").strip()

    if not context or not evidence:
        return None

    sentences = _split_sentences(context)
    evidence_index = _evidence_sentence_index(sentences, evidence)

    if evidence_index is None or evidence_index <= 0:
        return None

    antecedent = None
    ambiguous = False
    for sentence in sentences[:evidence_index]:
        reporting_reference, reporting_ambiguous = _reporting_clause_subject_reference(
            characters,
            sentence,
        )

        if reporting_ambiguous:
            ambiguous = True
            antecedent = None
            continue

        if reporting_reference:
            antecedent = reporting_reference
            ambiguous = False
            continue

        subject_reference, subject_ambiguous = _unique_grammatical_subject_reference(
            characters,
            sentence,
        )

        if subject_ambiguous:
            ambiguous = True
            antecedent = None
            continue

        if subject_reference:
            antecedent = subject_reference
            ambiguous = False
            continue

        references = _explicit_character_references(characters, sentence)

        if references:
            ambiguous = True
            antecedent = None
            continue

        if _contains_character_pronoun(sentence):
            if antecedent and not ambiguous:
                continue

            ambiguous = True
            antecedent = None
            continue

        if _breaks_character_subject_continuity(sentence):
            antecedent = None
            ambiguous = False

    if ambiguous or not antecedent:
        if ambiguous:
            return CharacterAttributionResult(
                False,
                ambiguous=True,
                supporting_text=local_context,
                risk_flags=["context_attribution_ambiguous"],
            )

        return None

    character = antecedent["character"]
    return CharacterAttributionResult(
        True,
        character=character,
        character_id=character.id,
        canonical_name=character.name,
        match_type="unique_progression_possessive",
        confidence=0.82,
        supporting_text=local_context,
        matched_reference=antecedent["reference"],
        risk_flags=["context_supported_attribution"],
    )


def _local_possessive_chain_character(characters, evidence_text, local_context, target_value=None):
    if not _object_pronoun_progression_sentence_supports_value(evidence_text, target_value):
        return None

    context = str(local_context or "").strip()
    evidence = str(evidence_text or "").strip()

    if not context or not evidence:
        return None

    sentences = _split_sentences(context)
    evidence_index = _evidence_sentence_index(sentences, evidence)

    if evidence_index is None or evidence_index <= 0:
        return None

    for antecedent_index in range(evidence_index - 1, -1, -1):
        antecedent_sentence = sentences[antecedent_index]

        if not _contains_progression_possessive_chain_phrase(antecedent_sentence):
            references = _explicit_character_references(characters, antecedent_sentence)

            if references:
                return CharacterAttributionResult(
                    False,
                    ambiguous=True,
                    supporting_text=local_context,
                    risk_flags=["context_attribution_ambiguous"],
                )

            continue

        antecedent_context = " ".join(sentences[:antecedent_index + 1])
        antecedent_result = _local_progression_possessive_character(
            characters,
            antecedent_sentence,
            antecedent_context,
            target_value=target_value,
        )

        if not antecedent_result:
            antecedent_result = _local_pronoun_character(
                characters,
                antecedent_sentence,
                antecedent_context,
            )

        if not antecedent_result:
            return None

        if antecedent_result.ambiguous:
            return antecedent_result

        return CharacterAttributionResult(
            True,
            character=antecedent_result.character,
            character_id=antecedent_result.character_id,
            canonical_name=antecedent_result.canonical_name,
            match_type="unique_possessive_chain",
            confidence=0.82,
            supporting_text=local_context,
            matched_reference=antecedent_result.matched_reference,
            risk_flags=["context_supported_attribution"],
        )

    return None


def _nearest_context_character(characters, evidence_text, local_context, target_value=None):
    forward_match = _local_forward_character(
        characters,
        evidence_text,
        local_context,
    )

    if forward_match and forward_match.resolved:
        return forward_match

    progression_possessive_match = _local_progression_possessive_character(
        characters,
        evidence_text,
        local_context,
        target_value=target_value,
    )

    if progression_possessive_match:
        return progression_possessive_match

    pronoun_match = _local_pronoun_character(characters, evidence_text, local_context)

    if pronoun_match:
        return pronoun_match

    possessive_chain_match = _local_possessive_chain_character(
        characters,
        evidence_text,
        local_context,
        target_value=target_value,
    )

    if possessive_chain_match:
        return possessive_chain_match

    if forward_match:
        return forward_match

    if not _contains_character_pronoun(evidence_text):
        return None

    if len(_split_sentences(local_context)) > 2:
        return None

    # Fallback only for the very tight legacy case where the local context has
    # one known character reference before the evidence and no competitors.
    context = " ".join(str(local_context or "").split())
    evidence = " ".join(str(evidence_text or "").split())

    if not context or not evidence:
        return None

    evidence_index = context.find(evidence)

    if evidence_index < 0:
        evidence_index = len(context)

    candidates = []

    for character in characters:
        positions = []

        for reference, match_type, _ in _candidate_references(character):
            if match_type not in {"canonical_name", "approved_alias", "stable_title"}:
                continue

            for position in text_reference_positions(context, reference):
                if position <= evidence_index:
                    positions.append((position, reference, match_type))

        if positions:
            candidates.append((character, max(positions, key=lambda item: item[0])))

    if not candidates:
        return None

    if len({character.id for character, _ in candidates}) != 1:
        return CharacterAttributionResult(
            False,
            ambiguous=True,
            supporting_text=local_context,
            risk_flags=["context_attribution_ambiguous"],
        )

    nearest_character, (position, reference, match_type) = candidates[0]

    return CharacterAttributionResult(
        True,
        character=nearest_character,
        character_id=nearest_character.id,
        canonical_name=nearest_character.name,
        match_type=_pronoun_method(evidence_text),
        confidence=0.82,
        supporting_text=local_context,
        matched_reference=reference,
        risk_flags=["context_supported_attribution"],
    )


def resolve_character_attribution(
    mention=None,
    evidence_text=None,
    local_context=None,
    candidate_characters=None,
    novel=None,
    target_character=None,
    target_value=None,
):
    characters = list(candidate_characters or [])

    if not characters and novel is not None:
        characters = Character.query.filter_by(novel_id=novel.id).all()

    if not characters:
        return CharacterAttributionResult(False, risk_flags=["attribution_uncertain"])

    mention_text = str(mention or "").strip()
    evidence = str(evidence_text or "").strip()
    context = str(local_context or "").strip()

    for text in (mention_text, evidence):
        exact_match = _unique_reference_matches(characters, text, {"canonical_name"})

        if exact_match and exact_match.resolved:
            return exact_match

        collective_match = _collective_reference_match(
            characters,
            text,
            {"canonical_name"},
            target_character,
        )

        if collective_match:
            return collective_match

        if exact_match:
            return exact_match

    for text in (mention_text, evidence):
        alias_match = _unique_reference_matches(characters, text, {"approved_alias"})

        if alias_match and alias_match.resolved:
            return alias_match

        collective_match = _collective_reference_match(
            characters,
            text,
            {"approved_alias"},
            target_character,
        )

        if collective_match:
            return collective_match

        if alias_match:
            return alias_match

    if mention_text and looks_like_title_style_name(mention_text):
        stable_title_match = _unique_reference_matches(characters, mention_text, {"stable_title"})

        if stable_title_match and stable_title_match.resolved:
            return stable_title_match

        collective_match = _collective_reference_match(
            characters,
            mention_text,
            {"stable_title"},
            target_character,
        )

        if collective_match:
            return collective_match

        if stable_title_match:
            return stable_title_match

    stable_title_match = _unique_reference_matches(characters, evidence, {"stable_title"})

    if stable_title_match and stable_title_match.resolved:
        return stable_title_match

    collective_match = _collective_reference_match(
        characters,
        evidence,
        {"stable_title"},
        target_character,
    )

    if collective_match:
        return collective_match

    if stable_title_match:
        return stable_title_match

    if _contains_object_pronoun_without_character_pronoun(evidence):
        possessive_chain_match = _nearest_context_character(
            characters,
            evidence,
            context,
            target_value=target_value,
        )

        if possessive_chain_match:
            return possessive_chain_match

        return CharacterAttributionResult(False, risk_flags=["attribution_uncertain"])

    if _contains_character_pronoun(evidence):
        pronoun_match = _nearest_context_character(
            characters,
            evidence,
            context,
            target_value=target_value,
        )

        if pronoun_match:
            return pronoun_match

        return CharacterAttributionResult(False, risk_flags=["attribution_uncertain"])

    for text in (context,):
        exact_match = _unique_reference_matches(characters, text, {"canonical_name"})

        if exact_match and exact_match.resolved:
            return exact_match

        collective_match = _collective_reference_match(
            characters,
            text,
            {"canonical_name"},
            target_character,
        )

        if collective_match:
            return collective_match

        if exact_match:
            return exact_match

    for text in (context,):
        alias_match = _unique_reference_matches(characters, text, {"approved_alias"})

        if alias_match and alias_match.resolved:
            return alias_match

        collective_match = _collective_reference_match(
            characters,
            text,
            {"approved_alias"},
            target_character,
        )

        if collective_match:
            return collective_match

        if alias_match:
            return alias_match

    stable_title_match = _unique_reference_matches(characters, context, {"stable_title"})

    if stable_title_match and stable_title_match.resolved:
        return stable_title_match

    collective_match = _collective_reference_match(
        characters,
        context,
        {"stable_title"},
        target_character,
    )

    if collective_match:
        return collective_match

    if stable_title_match:
        return stable_title_match

    return CharacterAttributionResult(False, risk_flags=["attribution_uncertain"])


def attribution_matches_character(result, character):
    return bool(
        result
        and result.resolved
        and character
        and result.character_id == getattr(character, "id", None)
    )
