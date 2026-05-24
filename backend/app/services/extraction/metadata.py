import re

from app.models import CharacterMetadataProposal, db
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

MAJOR_LIFE_STATUS_VALUES = ALLOWED_LIFE_STATUS_VALUES - {"alive", "unknown"}

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


def _merge_description(existing_description, new_description):
    if not existing_description:
        return new_description

    if not new_description or new_description in existing_description:
        return existing_description

    return f"{existing_description}\n\n{new_description}"


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


def title_text_from_list(titles):
    return "\n".join(titles) if titles else None


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

    return canonical_status in MAJOR_LIFE_STATUS_VALUES


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


def metadata_proposal_values(metadata):
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

            proposals.append((field, new_value))

    for title in normalize_title_values(getattr(metadata, "titles", [])):
        normalized_title = normalize_metadata_field("titles", title)

        if normalized_title:
            proposals.append(("titles", normalized_title))

    return proposals


def update_new_character_metadata(character, metadata):
    metadata_updated = False

    if not metadata:
        return False

    for field in CHARACTER_METADATA_FIELDS:
        new_metadata = normalize_metadata_field(field, getattr(metadata, field, None))

        if not new_metadata:
            continue

        if field == "status":
            canonical_status = canonical_life_status(new_metadata.normalized_value)

            if not should_keep_status_metadata(canonical_status, for_existing_character=False):
                continue

            new_metadata = normalize_metadata_field("status", canonical_status)

        new_value = display_metadata_value(field, new_metadata)
        current_metadata = normalize_metadata_field(field, getattr(character, field, None))

        if current_metadata and current_metadata.normalized_value == new_metadata.normalized_value:
            continue

        if not current_metadata or len(new_value) > len(getattr(character, field, "") or ""):
            setattr(character, field, new_value)

            if field == "race_or_species":
                character.race_or_species_source = "extracted"
                character.race_or_species_confidence = "confirmed"

            metadata_updated = True

    current_titles = title_list_from_text(character.titles)
    current_title_keys = {title.lower() for title in current_titles}
    merged_titles = [*current_titles]

    for title in normalize_title_values(getattr(metadata, "titles", [])):
        if title.lower() in current_title_keys:
            continue

        merged_titles.append(title)
        current_title_keys.add(title.lower())
        metadata_updated = True

    if metadata_updated:
        character.titles = title_text_from_list(merged_titles)

    return metadata_updated


def append_metadata_proposal_evidence(proposal, chapter, evidence):
    normalized_evidence = _normalize_evidence_text(evidence or "")[:500]

    if not normalized_evidence:
        return False

    existing_evidence = proposal.evidence or ""
    source_label = f"Chapter {chapter.chapter_number}: {normalized_evidence}"

    if _evidence_match_key(source_label) in {
        _evidence_match_key(part)
        for part in existing_evidence.split("\n\n")
        if part.strip()
    }:
        return False

    proposal.evidence = _merge_description(proposal.evidence, source_label)
    return True


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


def can_auto_approve_metadata(character, field_name, proposed_metadata, warning):
    if field_name != "gender":
        return False

    if proposed_metadata.confidence_score < 0.9:
        return False

    if warning or proposed_metadata.warnings:
        return False

    current_value = normalize_metadata_field(field_name, getattr(character, field_name, None))

    if current_value and current_value.normalized_value != proposed_metadata.normalized_value:
        return False

    return True


def apply_metadata_value_to_character(character, field_name, proposed_metadata):
    if field_name == "titles":
        character.titles = _merge_description(character.titles, proposed_metadata.raw_value)
    else:
        setattr(character, field_name, proposed_metadata.normalized_value)

    if field_name == "race_or_species":
        character.race_or_species_source = "extracted"
        character.race_or_species_confidence = "confirmed"


def create_character_metadata_proposals(novel, chapter, character, metadata, evidence):
    proposals_created = 0

    for field_name, proposed_metadata in metadata_proposal_values(metadata):
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

        if proposal:
            append_metadata_proposal_evidence(proposal, chapter, evidence)

            for warning in warnings:
                append_metadata_proposal_warning(proposal, warning)

            continue

        warning_text = metadata_warning_text(warnings)
        auto_approved = can_auto_approve_metadata(
            character,
            field_name,
            proposed_metadata,
            warning_text,
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
            evidence=f"Chapter {chapter.chapter_number}: {_normalize_evidence_text(evidence)[:500]}",
            review_warnings=warning_text,
            review_status="approved" if auto_approved else "pending",
        )
        db.session.add(proposal)

        if auto_approved:
            apply_metadata_value_to_character(character, field_name, proposed_metadata)

        proposals_created += 1

    return proposals_created
