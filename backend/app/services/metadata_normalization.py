import re
import string
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True)
class MetadataNormalizationResult:
    raw_value: str
    normalized_value: str
    confidence_score: float
    extraction_reason: str | None = None
    warnings: tuple[str, ...] = ()


UNKNOWN_VALUES = {"", "unknown", "n/a", "none", "null"}

NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
    "thirty": "30",
    "forty": "40",
    "fifty": "50",
    "sixty": "60",
    "seventy": "70",
    "eighty": "80",
    "ninety": "90",
}

AGE_SCALE_WORDS = {"thousand", "million", "billion", "trillion"}

MALE_TERMS = {
    "male",
    "man",
    "boy",
    "he",
    "him",
    "his",
    "brother",
    "father",
    "grandpa",
    "grandfather",
    "uncle",
}

FEMALE_TERMS = {
    "female",
    "woman",
    "girl",
    "she",
    "her",
    "hers",
    "sister",
    "mother",
    "grandma",
    "grandmother",
    "aunt",
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

LIFE_STATUS_ALIASES = {
    "alive": ("alive", "living", "survived"),
    "dead": (
        "dead",
        "death",
        "died",
        "killed",
        "slain",
        "deceased",
        "corpse",
        "soul dispersed",
    ),
    "historical": ("historical", "ancient", "legendary", "past era", "past-era"),
    "missing": ("missing", "disappeared", "whereabouts unknown"),
    "sealed": ("sealed", "sealed away", "sealed within"),
    "reincarnated": ("reincarnated", "reincarnation", "reborn"),
    "unknown": ("unknown",),
}


def normalize_whitespace(value):
    return " ".join(str(value or "").split()).strip()


def strip_noise_punctuation(value):
    return normalize_whitespace(value).strip(string.whitespace + "\"'.,;:!?()[]{}")


def normalize_basic_text(value):
    raw_value = normalize_whitespace(value)

    if raw_value.lower() in UNKNOWN_VALUES:
        return None

    normalized_value = strip_noise_punctuation(raw_value).lower()
    normalized_value = normalized_value.replace("-", " ")
    normalized_value = re.sub(r"[^\w\s/]", " ", normalized_value)
    normalized_value = normalize_whitespace(normalized_value)

    if normalized_value in UNKNOWN_VALUES:
        return None

    return MetadataNormalizationResult(
        raw_value=raw_value,
        normalized_value=normalized_value,
        confidence_score=0.78,
        extraction_reason="Basic text normalization.",
    )


def normalize_gender(value):
    raw_value = normalize_whitespace(value)

    if raw_value.lower() in UNKNOWN_VALUES:
        return None

    words = set(re.findall(r"[a-z]+", raw_value.lower()))
    male_matches = words & MALE_TERMS
    female_matches = words & FEMALE_TERMS

    if male_matches and female_matches:
        return MetadataNormalizationResult(
            raw_value=raw_value,
            normalized_value=raw_value.lower(),
            confidence_score=0.35,
            extraction_reason="Gender wording contains both male and female indicators.",
            warnings=("Ambiguous gender metadata.",),
        )

    if male_matches:
        confidence = 0.98 if "male" in male_matches else 0.9
        return MetadataNormalizationResult(
            raw_value=raw_value,
            normalized_value="male",
            confidence_score=confidence,
            extraction_reason="Gender normalized from explicit masculine wording.",
        )

    if female_matches:
        confidence = 0.98 if "female" in female_matches else 0.9
        return MetadataNormalizationResult(
            raw_value=raw_value,
            normalized_value="female",
            confidence_score=confidence,
            extraction_reason="Gender normalized from explicit feminine wording.",
        )

    normalized = normalize_basic_text(raw_value)

    if not normalized:
        return None

    return MetadataNormalizationResult(
        raw_value=raw_value,
        normalized_value=normalized.normalized_value,
        confidence_score=0.45,
        extraction_reason="Gender value could not be mapped to a known canonical value.",
        warnings=("Low-confidence gender metadata.",),
    )


def number_word_pattern():
    return "|".join(sorted(NUMBER_WORDS, key=len, reverse=True))


def normalize_age_text(value):
    raw_value = normalize_whitespace(value)

    if raw_value.lower() in UNKNOWN_VALUES:
        return None

    normalized = raw_value.lower().replace("-", " ")
    normalized = re.sub(r"\b(years?|yrs?)\s+old\b", " years old", normalized)
    normalized = re.sub(r"\b(man|woman|boy|girl|youth|young man|young woman)\b", "", normalized)
    normalized = re.sub(r"\b(looked|appeared|seemed|looks|appears|seems|to be)\b", "", normalized)
    normalized = re.sub(r"\b(about|around|approximately|roughly|nearly)\b", "about", normalized)

    for word, number in NUMBER_WORDS.items():
        normalized = re.sub(rf"\b{word}\b", number, normalized)

    normalized = re.sub(r"\babout\s+about\b", "about", normalized)
    normalized = normalize_whitespace(re.sub(r"[^\w\s]", " ", normalized))

    numbers = re.findall(r"\b\d+\b", normalized)
    scale_match = re.search(
        rf"\b(?P<number>\d+)\s+(?P<scale>{'|'.join(AGE_SCALE_WORDS)})\b",
        normalized,
    )
    approximate = "about" in normalized

    if scale_match:
        prefix = "about " if approximate else ""
        canonical = (
            f"{prefix}{scale_match.group('number')} {scale_match.group('scale')} years old"
        )
        confidence = 0.84 if approximate else 0.9
    elif len(numbers) >= 2:
        prefix = "about " if approximate else ""
        canonical = f"{prefix}{numbers[0]}-{numbers[1]} years old"
        confidence = 0.82
    elif len(numbers) == 1:
        canonical = f"about {numbers[0]} years old" if approximate else f"{numbers[0]} years old"
        confidence = 0.78 if "about" in canonical else 0.86
    else:
        canonical = normalized
        confidence = 0.48

    warnings = ()

    if confidence < 0.6:
        warnings = ("Low-confidence age metadata.",)

    return MetadataNormalizationResult(
        raw_value=raw_value,
        normalized_value=canonical,
        confidence_score=confidence,
        extraction_reason="Age text normalized from approximate age wording.",
        warnings=warnings,
    )


def normalize_title(value):
    result = normalize_basic_text(value)

    if not result:
        return None

    return MetadataNormalizationResult(
        raw_value=result.raw_value,
        normalized_value=result.normalized_value,
        confidence_score=0.72,
        extraction_reason="Title normalized by punctuation, hyphen, and case cleanup.",
    )


def normalize_status(value):
    result = normalize_basic_text(value)

    if not result:
        return None

    normalized_value = result.normalized_value
    canonical_status = None

    if normalized_value in ALLOWED_LIFE_STATUS_VALUES:
        canonical_status = normalized_value
    else:
        for status, aliases in LIFE_STATUS_ALIASES.items():
            if any(alias in normalized_value for alias in aliases):
                canonical_status = status
                break

    if not canonical_status:
        return None

    confidence = 0.9

    if any(term in normalized_value for term in ("might", "possibly", "seemed", "temporary", "currently in")):
        confidence = 0.45

    warnings = ("Low-confidence status metadata.",) if confidence < 0.6 else ()

    return MetadataNormalizationResult(
        raw_value=result.raw_value,
        normalized_value=canonical_status,
        confidence_score=confidence,
        extraction_reason="Life status normalized to canonical wiki status.",
        warnings=warnings,
    )


def normalize_metadata_field(field_name, value):
    if field_name == "gender":
        return normalize_gender(value)

    if field_name == "age_text":
        return normalize_age_text(value)

    if field_name == "titles":
        return normalize_title(value)

    if field_name in {"status", "faction_or_affiliation", "origin", "race_or_species"}:
        return normalize_status(value) if field_name == "status" else normalize_basic_text(value)

    return normalize_basic_text(value)


def normalized_similarity(first_value, second_value):
    first = normalize_whitespace(first_value).lower()
    second = normalize_whitespace(second_value).lower()

    if not first or not second:
        return 0.0

    return SequenceMatcher(None, first, second).ratio()


def is_weak_variation(first_value, second_value):
    first = normalize_whitespace(first_value).lower()
    second = normalize_whitespace(second_value).lower()

    if normalized_similarity(first, second) >= 0.86:
        return True

    first_tokens = set(first.split())
    second_tokens = set(second.split())

    if not first_tokens or not second_tokens:
        return False

    overlap = len(first_tokens & second_tokens) / min(len(first_tokens), len(second_tokens))
    return overlap >= 0.85
