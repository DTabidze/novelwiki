import re
from dataclasses import dataclass

from app.services.metadata_normalization import normalize_metadata_field


QUOTE_TRANSLATION = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "„": '"',
        "‟": '"',
        "‚": "'",
        "‛": "'",
    }
)

DASH_TRANSLATION = str.maketrans(
    {
        "—": "-",
        "–": "-",
        "−": "-",
    }
)

SURROUNDING_QUOTES = "\"'“”‘’„‟‚‛"
QUOTE_MARK_CHARS = "\"'“”‘’„‟‚‛"


@dataclass(frozen=True)
class EvidenceVerification:
    verified: bool
    evidence_text: str
    match_type: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    ambiguous: bool = False


@dataclass(frozen=True)
class EvidenceContext:
    found: bool
    previous_sentence: str | None = None
    evidence_sentence: str | None = None
    next_sentence: str | None = None
    combined_context: str = ""
    match_type: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    matched_raw_text: str | None = None
    ambiguous: bool = False


@dataclass(frozen=True)
class EvidenceLocation:
    matched: bool
    match_method: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    matched_raw_text: str | None = None
    ambiguous: bool = False
    match_count: int = 0


@dataclass(frozen=True)
class EvidenceRecovery:
    recovered: bool
    evidence_text: str = ""
    start_offset: int | None = None
    end_offset: int | None = None
    recovery_method: str | None = None
    confidence: float = 0.0
    ambiguous: bool = False


@dataclass(frozen=True)
class EvidenceSupport:
    verified: bool
    evidence_text: str = ""
    source: str | None = None
    match_type: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    recovery_method: str | None = None
    ambiguous: bool = False


def _collapse_whitespace(value):
    return " ".join(str(value or "").split())


def _candidate_value(candidate, *names):
    if candidate is None:
        return None

    if isinstance(candidate, dict):
        for name in names:
            value = candidate.get(name)

            if value:
                return value

        return None

    for name in names:
        value = getattr(candidate, name, None)

        if value:
            return value

    return None


def _normalize_quotes(value):
    return str(value or "").translate(QUOTE_TRANSLATION)


def _normalize_dashes(value):
    return str(value or "").translate(DASH_TRANSLATION)


def _strip_surrounding_quotes(value):
    normalized = str(value or "").strip()

    while len(normalized) >= 2 and normalized[0] in SURROUNDING_QUOTES and normalized[-1] in SURROUNDING_QUOTES:
        normalized = normalized[1:-1].strip()

    return normalized


def _is_boundary_quote(raw, raw_index, char):
    if char == '"':
        return True

    if char != "'":
        return False

    previous_char = raw[raw_index - 1] if raw_index > 0 else ""
    next_char = raw[raw_index + 1] if raw_index + 1 < len(raw) else ""
    return not (previous_char.isalnum() and next_char.isalnum())


def _normalized_index(
    value,
    *,
    normalize_quotes=False,
    normalize_dashes=False,
    drop_boundary_quotes=False,
):
    raw = str(value or "")
    normalized_chars = []
    index_map = []
    previous_was_space = False

    for raw_index, char in enumerate(raw):
        original_char = char
        current = char

        if current == "\xa0":
            current = " "

        if normalize_quotes:
            current = current.translate(QUOTE_TRANSLATION)

        if normalize_dashes:
            current = current.translate(DASH_TRANSLATION)

        if drop_boundary_quotes and original_char in QUOTE_MARK_CHARS and _is_boundary_quote(
            raw,
            raw_index,
            current,
        ):
            continue

        if current.isspace():
            if normalized_chars and not previous_was_space:
                normalized_chars.append(" ")
                index_map.append(raw_index)
                previous_was_space = True
            continue

        normalized_chars.append(current)
        index_map.append(raw_index)
        previous_was_space = False

    if normalized_chars and normalized_chars[-1] == " ":
        normalized_chars.pop()
        index_map.pop()

    return "".join(normalized_chars), index_map


def _normalized_evidence(
    value,
    *,
    normalize_quotes=False,
    normalize_dashes=False,
    strip_quotes=False,
    drop_boundary_quotes=False,
):
    normalized, _ = _normalized_index(
        value,
        normalize_quotes=normalize_quotes,
        normalize_dashes=normalize_dashes,
        drop_boundary_quotes=drop_boundary_quotes,
    )

    if strip_quotes:
        normalized = _strip_surrounding_quotes(normalized)

    return normalized


def _match_offsets_from_normalized(index_map, normalized_start, normalized_end, raw_text):
    if normalized_start < 0 or normalized_end <= normalized_start:
        return None

    if normalized_start >= len(index_map) or normalized_end - 1 >= len(index_map):
        return None

    raw_start = index_map[normalized_start]
    raw_end = index_map[normalized_end - 1] + 1

    return raw_start, raw_end


def _find_all(haystack, needle):
    if not haystack or not needle:
        return []

    matches = []
    start = 0

    while True:
        index = haystack.find(needle, start)

        if index < 0:
            break

        matches.append((index, index + len(needle)))
        start = index + max(1, len(needle))

    return matches


def _token_safe_phrase_pattern(phrase):
    normalized_phrase = _collapse_whitespace(phrase)

    if not normalized_phrase:
        return None

    parts = [part for part in re.split(r"\s+", normalized_phrase) if part]

    if not parts:
        return None

    return (
        r"(?<![A-Za-z0-9])"
        + r"\s+".join(re.escape(part) for part in parts)
        + r"(?![A-Za-z0-9])"
    )


def _token_safe_phrase_matches(chapter_text, phrase):
    pattern = _token_safe_phrase_pattern(phrase)

    if not pattern:
        return []

    return [
        (match.start(), match.end())
        for match in re.finditer(pattern, str(chapter_text or ""), flags=re.IGNORECASE)
    ]


def _text_contains_token_safe_phrase(text, phrase):
    return bool(_token_safe_phrase_matches(text, phrase))


def _unique_sentence_from_matches(chapter_text, matches, method, confidence=0.9):
    if not matches:
        return EvidenceRecovery(False)

    sentences = _sentence_spans(chapter_text)
    sentence_matches = []

    for match_start, match_end in matches:
        for sentence_start, sentence_end, sentence_text in sentences:
            if sentence_start <= match_start and match_end <= sentence_end:
                sentence_matches.append((sentence_start, sentence_end, sentence_text))
                break

    unique_sentences = []
    seen_offsets = set()

    for sentence in sentence_matches:
        offset_key = (sentence[0], sentence[1])

        if offset_key in seen_offsets:
            continue

        unique_sentences.append(sentence)
        seen_offsets.add(offset_key)

    if len(unique_sentences) != 1:
        return EvidenceRecovery(
            False,
            recovery_method=method,
            ambiguous=bool(unique_sentences),
        )

    start_offset, end_offset, sentence_text = unique_sentences[0]
    return EvidenceRecovery(
        True,
        evidence_text=sentence_text,
        start_offset=start_offset,
        end_offset=end_offset,
        recovery_method=method,
        confidence=confidence,
    )


def _location_from_matches(chapter, matches, method, index_map=None):
    if not matches:
        return EvidenceLocation(False)

    if len(matches) > 1:
        return EvidenceLocation(
            False,
            match_method=method,
            ambiguous=True,
            match_count=len(matches),
        )

    match_start, match_end = matches[0]

    if index_map is not None:
        offsets = _match_offsets_from_normalized(index_map, match_start, match_end, chapter)

        if not offsets:
            return EvidenceLocation(False)

        start_offset, end_offset = offsets
    else:
        start_offset, end_offset = match_start, match_end

    return EvidenceLocation(
        True,
        match_method=method,
        start_offset=start_offset,
        end_offset=end_offset,
        matched_raw_text=chapter[start_offset:end_offset],
        match_count=1,
    )


def locate_evidence_text(chapter_text, evidence_text):
    evidence = str(evidence_text or "").strip()
    chapter = str(chapter_text or "")

    if not evidence or not chapter:
        return EvidenceLocation(False)

    exact_matches = _find_all(chapter, evidence)

    if exact_matches:
        return _location_from_matches(chapter, exact_matches, "exact")

    search_plan = [
        ("whitespace_normalized", False, False, False, False),
        ("quote_normalized", True, False, False, False),
        ("quote_normalized", True, False, True, False),
        ("quote_boundary_normalized", True, False, False, True),
        ("quote_boundary_normalized", True, False, True, True),
        ("dash_normalized", True, True, False, False),
        ("dash_normalized", True, True, True, False),
        ("dash_quote_boundary_normalized", True, True, False, True),
        ("dash_quote_boundary_normalized", True, True, True, True),
    ]

    for method, normalize_quotes, normalize_dashes, strip_quotes, drop_boundary_quotes in search_plan:
        normalized_chapter, index_map = _normalized_index(
            chapter,
            normalize_quotes=normalize_quotes,
            normalize_dashes=normalize_dashes,
            drop_boundary_quotes=drop_boundary_quotes,
        )
        normalized_evidence = _normalized_evidence(
            evidence,
            normalize_quotes=normalize_quotes,
            normalize_dashes=normalize_dashes,
            strip_quotes=strip_quotes,
            drop_boundary_quotes=drop_boundary_quotes,
        )

        matches = _find_all(normalized_chapter, normalized_evidence)

        if matches:
            return _location_from_matches(chapter, matches, method, index_map=index_map)

    return EvidenceLocation(False)


def _location_from_offsets(chapter_text, evidence_text, start_offset, end_offset, match_type=None):
    chapter = str(chapter_text or "")
    evidence = str(evidence_text or "").strip()

    if (
        not evidence
        or not chapter
        or start_offset is None
        or end_offset is None
        or start_offset < 0
        or end_offset <= start_offset
        or end_offset > len(chapter)
    ):
        return EvidenceLocation(False)

    matched_raw_text = chapter[start_offset:end_offset]

    if matched_raw_text == evidence:
        return EvidenceLocation(
            True,
            match_method=match_type or "exact",
            start_offset=start_offset,
            end_offset=end_offset,
            matched_raw_text=matched_raw_text,
            match_count=1,
        )

    normalized_matched = _normalized_evidence(
        matched_raw_text,
        normalize_quotes=True,
        normalize_dashes=True,
        strip_quotes=True,
    )
    normalized_evidence = _normalized_evidence(
        evidence,
        normalize_quotes=True,
        normalize_dashes=True,
        strip_quotes=True,
    )

    if normalized_matched == normalized_evidence:
        return EvidenceLocation(
            True,
            match_method=match_type or "offset_normalized",
            start_offset=start_offset,
            end_offset=end_offset,
            matched_raw_text=matched_raw_text,
            match_count=1,
        )

    return EvidenceLocation(False)


def verify_evidence_text(
    chapter_text,
    evidence_text,
    start_offset=None,
    end_offset=None,
    match_type=None,
):
    evidence = str(evidence_text or "").strip()
    location = _location_from_offsets(
        chapter_text,
        evidence,
        start_offset,
        end_offset,
        match_type=match_type,
    )

    if not location.matched:
        location = locate_evidence_text(chapter_text, evidence)

    canonical_evidence = location.matched_raw_text if location.matched else evidence

    return EvidenceVerification(
        location.matched,
        canonical_evidence,
        location.match_method,
        start_offset=location.start_offset,
        end_offset=location.end_offset,
        ambiguous=location.ambiguous,
    )


def _sentence_spans(chapter_text):
    text = str(chapter_text or "")
    spans = []
    start = None
    index = 0

    while index < len(text):
        char = text[index]

        if start is None and not char.isspace():
            start = index

        if start is None:
            index += 1
            continue

        paragraph_break = char == "\n" and index + 1 < len(text) and text[index + 1] == "\n"
        sentence_end = char in ".!?"

        if sentence_end:
            end = index + 1
            while end < len(text) and text[end] in '"\'”’)]}':
                end += 1
            spans.append((start, end, text[start:end].strip()))
            start = None
            index = end
            continue

        if paragraph_break:
            end = index
            spans.append((start, end, text[start:end].strip()))
            start = None
            while index < len(text) and text[index].isspace():
                index += 1
            continue

        index += 1

    if start is not None:
        spans.append((start, len(text), text[start:].strip()))

    return [span for span in spans if span[2]]


def _combined_context(previous_sentence, evidence_sentence, next_sentence):
    return " ".join(
        sentence
        for sentence in (previous_sentence, evidence_sentence, next_sentence)
        if sentence
    )


def get_evidence_context(
    chapter_text,
    evidence_text,
    start_offset=None,
    end_offset=None,
    match_type=None,
):
    evidence = str(evidence_text or "").strip()
    chapter = str(chapter_text or "")

    if not evidence or not chapter:
        return EvidenceContext(False)

    sentences = _sentence_spans(chapter)

    if not sentences:
        return EvidenceContext(False)

    location = _location_from_offsets(
        chapter,
        evidence,
        start_offset,
        end_offset,
        match_type=match_type,
    )

    if not location.matched:
        location = locate_evidence_text(chapter, evidence)

    if location.ambiguous:
        return EvidenceContext(
            False,
            match_type=location.match_method,
            ambiguous=True,
        )

    if not location.matched or location.start_offset is None or location.end_offset is None:
        return EvidenceContext(False)

    first_sentence_index = None
    last_sentence_index = None

    for index, (start, end, _) in enumerate(sentences):
        if start <= location.start_offset < end:
            first_sentence_index = index

        if start < location.end_offset <= end or (
            location.end_offset >= end and start <= location.end_offset <= end + 1
        ):
            last_sentence_index = index

        if first_sentence_index is not None and last_sentence_index is not None:
            break

    if first_sentence_index is None:
        return EvidenceContext(False)

    if last_sentence_index is None:
        last_sentence_index = first_sentence_index

    previous_sentence = sentences[first_sentence_index - 1][2] if first_sentence_index > 0 else None
    evidence_sentence = " ".join(
        sentence for _, _, sentence in sentences[first_sentence_index:last_sentence_index + 1]
    )
    next_sentence = (
        sentences[last_sentence_index + 1][2]
        if last_sentence_index + 1 < len(sentences)
        else None
    )

    return EvidenceContext(
        True,
        previous_sentence=previous_sentence,
        evidence_sentence=evidence_sentence,
        next_sentence=next_sentence,
        combined_context=_combined_context(previous_sentence, evidence_sentence, next_sentence),
        match_type=location.match_method,
        start_offset=location.start_offset,
        end_offset=location.end_offset,
        matched_raw_text=location.matched_raw_text,
    )


def _paragraph_bounds_for_offset(chapter_text, offset):
    text = str(chapter_text or "")

    if offset is None or offset < 0 or offset > len(text):
        return 0, len(text)

    paragraph_start = text.rfind("\n\n", 0, offset)
    paragraph_end = text.find("\n\n", offset)

    if paragraph_start < 0:
        paragraph_start = 0
    else:
        paragraph_start += 2

    if paragraph_end < 0:
        paragraph_end = len(text)

    return paragraph_start, paragraph_end


def _paragraph_spans(chapter_text):
    text = str(chapter_text or "")
    spans = []

    for match in re.finditer(r"\S(?:.*?)(?=\n\s*\n|\Z)", text, flags=re.DOTALL):
        paragraph_text = match.group(0).strip()

        if paragraph_text:
            spans.append((match.start(), match.end(), paragraph_text))

    return spans


def _is_hard_discourse_boundary(paragraph_text):
    normalized = _collapse_whitespace(paragraph_text)

    if not normalized:
        return True

    if re.fullmatch(r"(?:[*#~=_-]\s*){3,}", normalized):
        return True

    return re.fullmatch(
        r"(?:chapter|book|part|volume)\s+(?:\d+|[ivxlcdm]+)(?::.*)?",
        normalized,
        flags=re.IGNORECASE,
    ) is not None


def _context_contains_reference_group(text, references):
    for reference in references or []:
        normalized_reference = _collapse_whitespace(reference)

        if not normalized_reference:
            continue

        if re.search(
            rf"(?<![A-Za-z0-9]){re.escape(normalized_reference)}(?![A-Za-z0-9])",
            text or "",
            flags=re.IGNORECASE,
        ):
            return True

    return False


def _discourse_start_for_reference_groups(chapter_text, evidence_offset, reference_groups):
    paragraphs = _paragraph_spans(chapter_text)

    if not paragraphs or evidence_offset is None:
        return None

    current_index = None

    for index, (start, end, _) in enumerate(paragraphs):
        if start <= evidence_offset <= end:
            current_index = index
            break

    if current_index is None:
        return None

    groups = [
        [reference for reference in group or [] if _collapse_whitespace(reference)]
        for group in reference_groups or []
    ]
    groups = [group for group in groups if group]
    selected_start = paragraphs[current_index][0]

    if not groups:
        return selected_start

    while current_index >= 0:
        context_before_evidence = str(chapter_text or "")[selected_start:evidence_offset]

        if all(
            _context_contains_reference_group(context_before_evidence, group)
            for group in groups
        ):
            break

        previous_index = current_index - 1

        if previous_index < 0:
            break

        previous_paragraph = paragraphs[previous_index]

        if _is_hard_discourse_boundary(previous_paragraph[2]):
            break

        selected_start = previous_paragraph[0]
        current_index = previous_index

    return selected_start


def _paragraph_breaks_forward_identity(paragraph_text, reference_groups):
    normalized = _collapse_whitespace(paragraph_text)

    if not normalized:
        return True

    if any(
        _context_contains_reference_group(normalized, group)
        for group in reference_groups or []
    ):
        return False

    if re.match(
        r"^(?:meanwhile|elsewhere|later|afterward|afterwards|the next "
        r"(?:day|morning|night)|at the same time)\b",
        normalized,
        flags=re.IGNORECASE,
    ):
        return True

    if normalized.startswith(("\"", "'", "“", "‘")):
        return True

    return re.match(
        r"^(?:another|a|an|the)\s+"
        r"(?:boy|cultivator|disciple|elder|figure|girl|guard|man|person|"
        r"servant|woman|youth)\b",
        normalized,
        flags=re.IGNORECASE,
    ) is not None


def _discourse_end_for_reference_groups(
    chapter_text,
    evidence_offset,
    current_end,
    reference_groups,
):
    paragraphs = _paragraph_spans(chapter_text)

    if not paragraphs or evidence_offset is None:
        return current_end

    current_index = None

    for index, (start, end, _) in enumerate(paragraphs):
        if start <= evidence_offset <= end:
            current_index = index
            break

    if current_index is None:
        return current_end

    groups = [
        [reference for reference in group or [] if _collapse_whitespace(reference)]
        for group in reference_groups or []
    ]
    groups = [group for group in groups if group]

    if not groups:
        return current_end

    selected_end = max(current_end, paragraphs[current_index][1])
    selected_start = paragraphs[current_index][0]

    if all(
        _context_contains_reference_group(
            str(chapter_text or "")[selected_start:selected_end],
            group,
        )
        for group in groups
    ):
        return selected_end

    for next_index in range(current_index + 1, len(paragraphs)):
        paragraph = paragraphs[next_index]

        if _is_hard_discourse_boundary(paragraph[2]):
            break

        if _paragraph_breaks_forward_identity(paragraph[2], groups):
            break

        selected_end = paragraph[1]
        candidate_context = str(chapter_text or "")[selected_start:selected_end]

        if all(
            _context_contains_reference_group(candidate_context, group)
            for group in groups
        ):
            break

    return selected_end


def get_evidence_discourse_context(
    chapter_text,
    evidence_text,
    start_offset=None,
    end_offset=None,
    match_type=None,
    max_previous_sentences=6,
    max_next_sentences=1,
    reference_groups=None,
):
    evidence = str(evidence_text or "").strip()
    chapter = str(chapter_text or "")

    if not evidence or not chapter:
        return EvidenceContext(False)

    location = _location_from_offsets(
        chapter,
        evidence,
        start_offset,
        end_offset,
        match_type=match_type,
    )

    if not location.matched:
        location = locate_evidence_text(chapter, evidence)

    if location.ambiguous:
        return EvidenceContext(
            False,
            match_type=location.match_method,
            ambiguous=True,
        )

    if not location.matched or location.start_offset is None or location.end_offset is None:
        return EvidenceContext(False)

    paragraph_start, paragraph_end = _paragraph_bounds_for_offset(
        chapter,
        location.start_offset,
    )
    discourse_start = _discourse_start_for_reference_groups(
        chapter,
        location.start_offset,
        reference_groups,
    )

    if discourse_start is not None:
        paragraph_start = min(paragraph_start, discourse_start)

    if reference_groups:
        paragraph_end = _discourse_end_for_reference_groups(
            chapter,
            location.start_offset,
            paragraph_end,
            reference_groups,
        )

    sentences = [
        sentence
        for sentence in _sentence_spans(chapter)
        if paragraph_start <= sentence[0] and sentence[1] <= paragraph_end
    ]

    if not sentences:
        return get_evidence_context(
            chapter,
            evidence,
            start_offset=location.start_offset,
            end_offset=location.end_offset,
            match_type=location.match_method,
        )

    first_sentence_index = None
    last_sentence_index = None

    for index, (start, end, _) in enumerate(sentences):
        if start <= location.start_offset < end:
            first_sentence_index = index

        if start < location.end_offset <= end or (
            location.end_offset >= end and start <= location.end_offset <= end + 1
        ):
            last_sentence_index = index

        if first_sentence_index is not None and last_sentence_index is not None:
            break

    if first_sentence_index is None:
        return EvidenceContext(False)

    if last_sentence_index is None:
        last_sentence_index = first_sentence_index

    previous_start = (
        0
        if reference_groups
        else max(0, first_sentence_index - max_previous_sentences)
    )
    next_end = min(len(sentences), last_sentence_index + max_next_sentences + 1)

    if reference_groups:
        context_through_evidence = chapter[paragraph_start:location.end_offset]
        missing_groups = [
            group
            for group in reference_groups
            if not _context_contains_reference_group(context_through_evidence, group)
        ]

        if missing_groups:
            for index in range(last_sentence_index + 1, len(sentences)):
                context_through_sentence = chapter[
                    paragraph_start:sentences[index][1]
                ]
                next_end = index + 1

                if all(
                    _context_contains_reference_group(
                        context_through_sentence,
                        group,
                    )
                    for group in missing_groups
                ):
                    break

    previous_sentence = " ".join(
        sentence
        for _, _, sentence in sentences[previous_start:first_sentence_index]
        if sentence
    ) or None
    evidence_sentence = " ".join(
        sentence
        for _, _, sentence in sentences[first_sentence_index:last_sentence_index + 1]
        if sentence
    )
    next_sentence = " ".join(
        sentence
        for _, _, sentence in sentences[last_sentence_index + 1:next_end]
        if sentence
    ) or None

    return EvidenceContext(
        True,
        previous_sentence=previous_sentence,
        evidence_sentence=evidence_sentence,
        next_sentence=next_sentence,
        combined_context=_combined_context(previous_sentence, evidence_sentence, next_sentence),
        match_type=location.match_method,
        start_offset=location.start_offset,
        end_offset=location.end_offset,
        matched_raw_text=location.matched_raw_text,
    )


GENERIC_CHARACTER_REFERENCES = {
    "a man",
    "a woman",
    "boy",
    "cultivator",
    "disciple",
    "figure",
    "guard",
    "he",
    "her",
    "him",
    "his",
    "man",
    "old man",
    "person",
    "servant",
    "she",
    "the man",
    "the woman",
    "they",
    "woman",
    "young man",
    "young woman",
}

CHARACTER_PRONOUNS = {"he", "she", "him", "her", "his", "hers"}

DEATH_SIGNAL_RE = re.compile(
    r"\b(?:dead|died|death|deceased|killed|slain|corpse|lifeless|dead\s+body|no\s+longer\s+alive)\b",
    re.IGNORECASE,
)

NEAR_PROGRESSION_RE = re.compile(
    r"\b(?:almost|close\s+to|nearly|near|not\s+yet|preparing\s+to|about\s+to|"
    r"(?:will|would|could|might)\s+soon\s+(?:reach|become|enter|advance|break\s+through|be\s+promoted)|"
    r"soon\s+(?:reach|become|enter|advance|break\s+through|be\s+promoted)|"
    r"could\s+reach|might\s+reach|would\s+reach|will\s+reach|hair\s+away|"
    r"just\s+a\s+hair|on\s+the\s+verge)\b",
    re.IGNORECASE,
)

UNCERTAIN_OR_FUTURE_EVIDENCE_RE = re.compile(
    r"\b(?:may|might|could|would|will|eventually|almost|seems?|seemed|"
    r"probably|maybe|perhaps|possibly|likely|apparently)\b",
    re.IGNORECASE,
)

NEGATED_PROGRESSION_RE = re.compile(
    r"\b(?:had|has|have|still\s+had|still\s+has)?\s*not\s+(?:yet\s+)?(?:reached|achieved|attained|entered|advanced|broken\s+through|broke\s+through)\b|"
    r"\bnever\s+(?:reached|achieved|attained|entered|advanced|broken\s+through|broke\s+through)\b|"
    r"\bno\s+longer\s+at\b",
    re.IGNORECASE,
)

TEMPORARY_OR_COMPARATIVE_PROGRESSION_RE = re.compile(
    r"\b(?:temporar(?:y|ily)|briefly|comparable\s+to|equivalent\s+to|on\s+par\s+with|as\s+strong\s+as|could\s+(?:fight|battle|contend\s+with|match))\b",
    re.IGNORECASE,
)

AGE_CONTEXT_RE = re.compile(
    r"\b(?:years?\s+old|yrs?\s+old|aged|age|looked\s+to\s+be|appeared\s+to\s+be|"
    r"seemed\s+to\s+be)\b",
    re.IGNORECASE,
)

MEMBERSHIP_CONTEXT_RE = re.compile(
    r"\b(?:of|from|belonged\s+to|belongs\s+to|member\s+of|disciple\s+of|servant\s+of|"
    r"elder\s+of|captain\s+of|commander\s+of|joined|entered|served|serves|"
    r"affiliated\s+with)\b",
    re.IGNORECASE,
)

SPECIES_CONTEXT_RE = re.compile(
    r"\b(?:race|species|bloodline|lineage|born\s+as|human|mortal|demon|beast|spirit|"
    r"ghost|dragon|elf|dwarf|alien|undead|monster|vampire|werewolf)\b",
    re.IGNORECASE,
)


def _normalized_reference_list(*reference_groups):
    references = []
    seen = set()

    for group in reference_groups:
        if not group:
            continue

        if isinstance(group, str):
            values = [group]
        else:
            values = group

        for value in values:
            normalized = _collapse_whitespace(value)
            key = normalized.lower()

            if not normalized or key in seen:
                continue

            references.append(normalized)
            seen.add(key)

    return references


def _references_supported_in_text(text, references):
    return [
        reference
        for reference in references
        if _text_contains_token_safe_phrase(text, reference)
    ]


def _reference_is_generic(reference):
    normalized = _collapse_whitespace(reference).lower()
    words = set(re.findall(r"[a-z0-9]+", normalized))

    if not normalized:
        return True

    if normalized in GENERIC_CHARACTER_REFERENCES:
        return True

    return bool(words) and words <= GENERIC_CHARACTER_REFERENCES


def _recover_by_unique_reference(chapter_text, references, method, confidence=0.92):
    safe_references = [
        reference for reference in references if not _reference_is_generic(reference)
    ]
    matches = []

    for reference in safe_references:
        matches.extend(_token_safe_phrase_matches(chapter_text, reference))

    return _unique_sentence_from_matches(
        chapter_text,
        matches,
        method,
        confidence=confidence,
    )


def _recover_by_first_full_reference(chapter_text, references, method, confidence=0.92):
    safe_references = [
        reference
        for reference in references
        if not _reference_is_generic(reference)
        and len(re.findall(r"[A-Za-z0-9]+", reference)) >= 2
    ]
    matches = []

    for reference in safe_references:
        matches.extend(_token_safe_phrase_matches(chapter_text, reference))

    if not matches:
        return EvidenceRecovery(False)

    sentences = _sentence_spans(chapter_text)
    first_match = min(matches, key=lambda match: match[0])

    for sentence_start, sentence_end, sentence_text in sentences:
        if sentence_start <= first_match[0] and first_match[1] <= sentence_end:
            return EvidenceRecovery(
                True,
                evidence_text=sentence_text,
                start_offset=sentence_start,
                end_offset=sentence_end,
                recovery_method=method,
                confidence=confidence,
            )

    return EvidenceRecovery(False)


def _progression_value_words(value):
    return [
        word
        for word in re.findall(r"[a-z0-9]+", _collapse_whitespace(value).lower().replace("-", " "))
        if word not in {"a", "an", "the", "at", "of", "to"}
    ]


def _text_supports_progression_value(text, value):
    normalized_text = _collapse_whitespace(text).lower()
    normalized_value = _collapse_whitespace(value).lower()

    if not normalized_text or not normalized_value:
        return False

    if _text_contains_token_safe_phrase(text, value):
        return True

    compact_text = normalized_text.replace(" of ", " ")
    compact_value = normalized_value.replace(" of ", " ")

    if compact_value in compact_text:
        return True

    value_words = _progression_value_words(value)

    if len(value_words) >= 2:
        return all(word in normalized_text for word in value_words[:2])

    return False


def _evidence_recovery_blocked_by_uncertainty(evidence_text):
    evidence = str(evidence_text or "").strip()

    if not evidence:
        return False

    normalized = re.sub(r"\bas\s+if\b", "", evidence, flags=re.IGNORECASE)
    return "?" in normalized or bool(UNCERTAIN_OR_FUTURE_EVIDENCE_RE.search(normalized))


def _sentence_has_character_pronoun(sentence):
    words = set(re.findall(r"[a-z']+", str(sentence or "").lower()))
    return bool(words & CHARACTER_PRONOUNS)


def _unique_direct_or_pronoun_supported_sentence(
    chapter_text,
    references,
    value_supported,
    method,
    confidence=0.9,
    competing_references=None,
):
    sentences = _sentence_spans(chapter_text)
    competing_references = _normalized_reference_list(competing_references)
    matches = []

    for index, (sentence_start, sentence_end, sentence_text) in enumerate(sentences):
        if not value_supported(sentence_text):
            continue

        if _references_supported_in_text(sentence_text, competing_references):
            return EvidenceRecovery(False, recovery_method=method, ambiguous=True)

        if _references_supported_in_text(sentence_text, references):
            matches.append((sentence_start, sentence_end, sentence_text))
            continue

        if not _sentence_has_character_pronoun(sentence_text):
            continue

        previous_sentence = sentences[index - 1][2] if index > 0 else ""
        next_sentence = sentences[index + 1][2] if index + 1 < len(sentences) else ""
        local_context = " ".join(
            sentence for sentence in (previous_sentence, sentence_text, next_sentence) if sentence
        )

        if _references_supported_in_text(local_context, competing_references):
            return EvidenceRecovery(False, recovery_method=method, ambiguous=True)

        reference_hits = _references_supported_in_text(previous_sentence, references)

        if len(reference_hits) == 1:
            matches.append((sentence_start, sentence_end, sentence_text))

    unique_offsets = []
    seen = set()

    for match in matches:
        key = (match[0], match[1])

        if key in seen:
            continue

        unique_offsets.append(match)
        seen.add(key)

    if len(unique_offsets) != 1:
        return EvidenceRecovery(
            False,
            recovery_method=method,
            ambiguous=bool(unique_offsets),
        )

    start_offset, end_offset, sentence_text = unique_offsets[0]
    return EvidenceRecovery(
        True,
        evidence_text=sentence_text,
        start_offset=start_offset,
        end_offset=end_offset,
        recovery_method=method,
        confidence=confidence,
    )


def _recover_character_evidence(chapter_text, candidate, aliases=None):
    name = _candidate_value(candidate, "name", "character_name", "entity_name", "value")
    references = _normalized_reference_list(name, aliases)
    full_reference_recovery = _recover_by_first_full_reference(
        chapter_text,
        references,
        "exact_character_reference",
        confidence=0.95,
    )

    if full_reference_recovery.recovered:
        return full_reference_recovery

    return _recover_by_unique_reference(
        chapter_text,
        references,
        "exact_character_reference",
        confidence=0.95,
    )


def _recover_named_entity_evidence(chapter_text, candidate, aliases=None, fact_type="entity"):
    name = _candidate_value(candidate, "name", "item_name", "skill_name", "entity_name", "value")
    references = _normalized_reference_list(name, aliases)

    return _recover_by_unique_reference(
        chapter_text,
        references,
        f"exact_{fact_type}_reference",
        confidence=0.88,
    )


def _recover_progression_evidence(chapter_text, candidate, aliases=None, canonical_facts=None):
    character_name = _candidate_value(candidate, "character_name", "entity_name")
    new_value = _candidate_value(candidate, "new_value", "value")
    references = _normalized_reference_list(character_name, aliases)
    competing_references = _normalized_reference_list(
        (canonical_facts or {}).get("competing_character_references")
        if isinstance(canonical_facts, dict)
        else None
    )

    if not references or not new_value:
        return EvidenceRecovery(False)

    def value_supported(sentence):
        if (
            NEAR_PROGRESSION_RE.search(sentence or "")
            or NEGATED_PROGRESSION_RE.search(sentence or "")
            or TEMPORARY_OR_COMPARATIVE_PROGRESSION_RE.search(sentence or "")
        ):
            return False

        return _text_supports_progression_value(sentence, new_value)

    return _unique_direct_or_pronoun_supported_sentence(
        chapter_text,
        references,
        value_supported,
        "progression_context",
        confidence=0.9,
        competing_references=competing_references,
    )


def _metadata_value_supported(field_name, value, sentence):
    if field_name == "gender":
        normalized_value = _collapse_whitespace(value).lower()
        normalized_sentence = _collapse_whitespace(sentence).lower()
        male_patterns = (
            r"\b(?:he|him|his|himself)\b",
            r"\b(?:male|man|boy|brother|father|son|uncle|grandfather)\b",
        )
        female_patterns = (
            r"\b(?:she|her|hers|herself)\b",
            r"\b(?:female|woman|girl|sister|mother|daughter|aunt|grandmother|ms|mrs|miss)\b",
        )

        if normalized_value == "male":
            return any(re.search(pattern, normalized_sentence) for pattern in male_patterns)

        if normalized_value == "female":
            return any(re.search(pattern, normalized_sentence) for pattern in female_patterns)

        return _text_contains_token_safe_phrase(sentence, value)

    if field_name == "age_text":
        if not AGE_CONTEXT_RE.search(sentence or ""):
            return False

        normalized_candidate = normalize_metadata_field("age_text", value)
        normalized_sentence = normalize_metadata_field("age_text", sentence)
        return bool(
            normalized_candidate
            and normalized_sentence
            and normalized_candidate.normalized_value == normalized_sentence.normalized_value
        )

    if field_name == "status":
        normalized_value = _collapse_whitespace(value).lower()

        if normalized_value in {"dead", "deceased"}:
            return bool(DEATH_SIGNAL_RE.search(sentence or ""))

        return _text_contains_token_safe_phrase(sentence, value)

    if field_name == "faction_or_affiliation":
        return _text_contains_token_safe_phrase(sentence, value) and bool(
            MEMBERSHIP_CONTEXT_RE.search(sentence or "")
            or re.search(
                r"\b(?:members?|disciples?|servants?|elders?|captains?|commanders?|"
                r"students?|agents?|officers?|knights?|mages?|warriors?)\b",
                sentence or "",
                re.IGNORECASE,
            )
        )

    if field_name == "titles":
        return _text_contains_token_safe_phrase(sentence, value)

    if field_name == "race_or_species":
        return _text_contains_token_safe_phrase(sentence, value) and bool(
            SPECIES_CONTEXT_RE.search(sentence or "")
        )

    return _text_contains_token_safe_phrase(sentence, value)


def _recover_metadata_evidence(chapter_text, candidate, aliases=None, canonical_facts=None):
    field_name = _candidate_value(candidate, "field_name")
    value = _candidate_value(candidate, "value", "raw_value", "new_value")
    character_name = _candidate_value(candidate, "character_name", "entity_name")
    references = _normalized_reference_list(character_name, aliases)
    competing_references = _normalized_reference_list(
        (canonical_facts or {}).get("competing_character_references")
        if isinstance(canonical_facts, dict)
        else None
    )

    if not field_name or not value:
        return EvidenceRecovery(False)

    def value_supported(sentence):
        return _metadata_value_supported(field_name, value, sentence)

    direct_matches = []

    for sentence_start, sentence_end, sentence_text in _sentence_spans(chapter_text):
        if not value_supported(sentence_text):
            continue

        if _references_supported_in_text(sentence_text, references):
            direct_matches.append((sentence_start, sentence_end, sentence_text))

    unique_direct_matches = []
    seen_direct_matches = set()

    for match in direct_matches:
        key = (match[0], match[1])

        if key in seen_direct_matches:
            continue

        unique_direct_matches.append(match)
        seen_direct_matches.add(key)

    if len(unique_direct_matches) == 1:
        sentence_start, sentence_end, sentence_text = unique_direct_matches[0]
        return EvidenceRecovery(
            True,
            evidence_text=sentence_text,
            start_offset=sentence_start,
            end_offset=sentence_end,
            recovery_method=f"metadata_{field_name}_direct_context",
            confidence=0.9,
        )

    return _unique_direct_or_pronoun_supported_sentence(
        chapter_text,
        references,
        value_supported,
        f"metadata_{field_name}_context",
        confidence=0.86,
        competing_references=competing_references,
    )


def _recover_life_event_evidence(chapter_text, candidate, aliases=None, canonical_facts=None):
    event_type = _collapse_whitespace(_candidate_value(candidate, "event_type", "value")).lower()
    character_name = _candidate_value(candidate, "character_name", "entity_name")
    references = _normalized_reference_list(character_name, aliases)
    competing_references = _normalized_reference_list(
        (canonical_facts or {}).get("competing_character_references")
        if isinstance(canonical_facts, dict)
        else None
    )

    if event_type != "death" or not references:
        return EvidenceRecovery(False)

    return _unique_direct_or_pronoun_supported_sentence(
        chapter_text,
        references,
        lambda sentence: bool(DEATH_SIGNAL_RE.search(sentence or "")),
        "life_event_death_context",
        confidence=0.88,
        competing_references=competing_references,
    )


def _recover_relationship_evidence(chapter_text, candidate, aliases=None, canonical_facts=None, fact_type="relationship"):
    character_name = _candidate_value(candidate, "character_name", "entity_name")
    target_name = _candidate_value(
        candidate,
        "item_name",
        "skill_name",
        "target_name",
        "name",
        "value",
    )
    if not target_name and isinstance(canonical_facts, dict):
        target_name = canonical_facts.get("target_name")
    references = _normalized_reference_list(character_name, aliases)
    target_references = _normalized_reference_list(
        target_name,
        (canonical_facts or {}).get("target_aliases")
        if isinstance(canonical_facts, dict)
        else None,
    )
    competing_references = _normalized_reference_list(
        (canonical_facts or {}).get("competing_character_references")
        if isinstance(canonical_facts, dict)
        else None
    )

    if not references or not target_references:
        return EvidenceRecovery(False)

    def target_supported(sentence):
        return bool(_references_supported_in_text(sentence, target_references))

    return _unique_direct_or_pronoun_supported_sentence(
        chapter_text,
        references,
        target_supported,
        f"{fact_type}_context",
        confidence=0.82,
        competing_references=competing_references,
    )


def recover_fact_evidence(
    chapter_text,
    fact_type,
    candidate,
    aliases=None,
    canonical_facts=None,
    allow_verified_recovery=False,
):
    chapter = str(chapter_text or "")

    if not chapter:
        return EvidenceRecovery(False)

    evidence_text = _candidate_value(candidate, "evidence")

    if verify_evidence_text(chapter, evidence_text).verified and not allow_verified_recovery:
        return EvidenceRecovery(
            False,
            evidence_text=str(evidence_text or "").strip(),
            recovery_method="already_verified",
        )

    if _evidence_recovery_blocked_by_uncertainty(evidence_text):
        return EvidenceRecovery(False, recovery_method="uncertain_ai_evidence")

    normalized_fact_type = _collapse_whitespace(fact_type).lower()

    if normalized_fact_type == "character":
        return _recover_character_evidence(chapter, candidate, aliases=aliases)

    if normalized_fact_type == "progression":
        return _recover_progression_evidence(
            chapter,
            candidate,
            aliases=aliases,
            canonical_facts=canonical_facts,
        )

    if normalized_fact_type == "metadata":
        return _recover_metadata_evidence(
            chapter,
            candidate,
            aliases=aliases,
            canonical_facts=canonical_facts,
        )

    if normalized_fact_type == "life_event":
        return _recover_life_event_evidence(
            chapter,
            candidate,
            aliases=aliases,
            canonical_facts=canonical_facts,
        )

    if normalized_fact_type == "item":
        return _recover_named_entity_evidence(
            chapter,
            candidate,
            aliases=aliases,
            fact_type="item",
        )

    if normalized_fact_type == "skill":
        return _recover_named_entity_evidence(
            chapter,
            candidate,
            aliases=aliases,
            fact_type="skill",
        )

    if normalized_fact_type in {"character_item", "character_skill"}:
        return _recover_relationship_evidence(
            chapter,
            candidate,
            aliases=aliases,
            canonical_facts=canonical_facts,
            fact_type=normalized_fact_type,
        )

    return EvidenceRecovery(False)


def build_evidence_support(
    chapter_text,
    fact_type,
    candidate,
    aliases=None,
    canonical_facts=None,
):
    chapter = str(chapter_text or "")
    original_evidence = _candidate_value(candidate, "evidence")
    verification = verify_evidence_text(chapter, original_evidence)
    normalized_fact_type = _collapse_whitespace(fact_type).lower()

    if verification.verified:
        if normalized_fact_type == "character":
            name = _candidate_value(
                candidate,
                "name",
                "character_name",
                "entity_name",
                "value",
            )
            references = _normalized_reference_list(name, aliases)

            if references and not _references_supported_in_text(
                verification.evidence_text,
                references,
            ):
                recovery = _recover_character_evidence(
                    chapter,
                    candidate,
                    aliases=aliases,
                )

                if recovery.recovered:
                    return EvidenceSupport(
                        True,
                        evidence_text=recovery.evidence_text,
                        source="backend_recovered",
                        match_type=recovery.recovery_method,
                        start_offset=recovery.start_offset,
                        end_offset=recovery.end_offset,
                        recovery_method=recovery.recovery_method,
                        ambiguous=recovery.ambiguous,
                    )

        return EvidenceSupport(
            True,
            evidence_text=verification.evidence_text,
            source="ai_verified",
            match_type=verification.match_type,
            start_offset=verification.start_offset,
            end_offset=verification.end_offset,
            ambiguous=verification.ambiguous,
        )

    recovery = recover_fact_evidence(
        chapter,
        fact_type,
        candidate,
        aliases=aliases,
        canonical_facts=canonical_facts,
    )

    if recovery.recovered:
        return EvidenceSupport(
            True,
            evidence_text=recovery.evidence_text,
            source="backend_recovered",
            match_type=recovery.recovery_method,
            start_offset=recovery.start_offset,
            end_offset=recovery.end_offset,
            recovery_method=recovery.recovery_method,
            ambiguous=recovery.ambiguous,
        )

    return EvidenceSupport(
        False,
        evidence_text=str(original_evidence or "").strip(),
        source="unverified_ai",
        ambiguous=verification.ambiguous or recovery.ambiguous,
        recovery_method=recovery.recovery_method,
    )
