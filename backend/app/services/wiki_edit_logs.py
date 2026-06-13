import json
import re
from datetime import datetime, time, timezone

from app.models import Character, Item, Skill, WikiEditLog, db
from app.services.wiki_editor_payloads import PayloadValidationError


def edit_log_json(value):
    if value in (None, ""):
        return None

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def normalize_log_value(value):
    if value in (None, ""):
        return None

    if isinstance(value, dict):
        return {key: normalize_log_value(item) for key, item in value.items()}

    if isinstance(value, list):
        return [normalize_log_value(item) for item in value]

    return value


def display_log_value(value):
    value = normalize_log_value(value)

    if value in (None, ""):
        return None

    if isinstance(value, dict):
        chapter_number = value.get("chapter_number")
        chapter_title = value.get("title")

        if chapter_number and chapter_title:
            title = re.sub(rf"^chapter\s+{chapter_number}\s*[:\-]\s*", "", str(chapter_title), flags=re.I)
            return f"Chapter {chapter_number} - {title}"

        if chapter_number:
            return f"Chapter {chapter_number}"

        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    if isinstance(value, list):
        return ", ".join(filter(None, [display_log_value(item) for item in value]))

    return str(value)


def values_equal(first, second):
    return normalize_log_value(first) == normalize_log_value(second)


def log_summary(change_type, field_label, old_value=None, new_value=None, context=None):
    old_display = display_log_value(old_value)
    new_display = display_log_value(new_value)

    if change_type == "updated" and old_display is not None and new_display is not None:
        return f'{field_label} changed from "{old_display}" to "{new_display}".'

    if change_type == "added":
        return f"Added {field_label.lower()}{f' to {context}' if context else ''}."

    if change_type == "removed":
        return f"Removed {field_label.lower()}{f' from {context}' if context else ''}."

    return field_label


def add_wiki_edit_log(
    *,
    novel_id,
    entity_type,
    entity_id,
    entity_label,
    change_type,
    field_name=None,
    old_value=None,
    new_value=None,
    parent_entity_type=None,
    parent_entity_id=None,
    summary=None,
):
    db.session.add(
        WikiEditLog(
            novel_id=novel_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_label=entity_label or "Wiki Data",
            parent_entity_type=parent_entity_type,
            parent_entity_id=parent_entity_id,
            change_type=change_type,
            field_name=field_name,
            old_value_json=edit_log_json(normalize_log_value(old_value)),
            new_value_json=edit_log_json(normalize_log_value(new_value)),
            summary=summary,
            edited_by="Admin",
        )
    )


def record_field_logs(novel_id, entity_type, entity_id, entity_label, before, after, fields):
    for field_name, field_label in fields.items():
        old_value = before.get(field_name)
        new_value = after.get(field_name)

        if values_equal(old_value, new_value):
            continue

        add_wiki_edit_log(
            novel_id=novel_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_label=entity_label,
            change_type="updated",
            field_name=field_label,
            old_value=old_value,
            new_value=new_value,
            summary=log_summary("updated", field_label, old_value, new_value),
        )


def first_evidence_text(row):
    evidence_rows = row.get("evidence") or []

    if not evidence_rows:
        return None

    return evidence_rows[0].get("evidence_text")


def row_by_id(rows):
    return {row["id"]: row for row in rows if row.get("id")}


def record_collection_logs(
    *,
    novel_id,
    parent_type,
    parent_id,
    parent_label,
    entity_type,
    before_rows,
    after_rows,
    entity_label_getter,
    field_getters,
    added_field,
    removed_field,
):
    before_by_id = row_by_id(before_rows)
    after_by_id = row_by_id(after_rows)

    for row_id, after_row in after_by_id.items():
        if row_id not in before_by_id:
            label = entity_label_getter(after_row)
            log_entity_label = parent_label or label
            add_wiki_edit_log(
                novel_id=novel_id,
                entity_type=entity_type,
                entity_id=row_id,
                entity_label=log_entity_label,
                parent_entity_type=parent_type,
                parent_entity_id=parent_id,
                change_type="added",
                field_name=added_field,
                new_value=label,
                summary=log_summary("added", added_field, new_value=label, context=parent_label),
            )
            continue

        before_row = before_by_id[row_id]
        label = entity_label_getter(after_row)
        log_entity_label = parent_label or label

        for _field_key, field_label, value_getter in field_getters:
            old_value = value_getter(before_row)
            new_value = value_getter(after_row)

            if values_equal(old_value, new_value):
                continue

            add_wiki_edit_log(
                novel_id=novel_id,
                entity_type=entity_type,
                entity_id=row_id,
                entity_label=log_entity_label,
                parent_entity_type=parent_type,
                parent_entity_id=parent_id,
                change_type="updated",
                field_name=field_label,
                old_value=old_value,
                new_value=new_value,
                summary=log_summary("updated", field_label, old_value, new_value),
            )

    for row_id, before_row in before_by_id.items():
        if row_id in after_by_id:
            continue

        label = entity_label_getter(before_row)
        log_entity_label = parent_label or label
        add_wiki_edit_log(
            novel_id=novel_id,
            entity_type=entity_type,
            entity_id=row_id,
            entity_label=log_entity_label,
            parent_entity_type=parent_type,
            parent_entity_id=parent_id,
            change_type="removed",
            field_name=removed_field,
            old_value=label,
            summary=log_summary("removed", removed_field, old_value=label, context=parent_label),
        )


CHARACTER_LOG_FIELDS = {
    "name": "Canonical Name",
    "description": "Description",
    "first_mentioned_chapter": "First Mentioned Chapter",
    "first_appeared_chapter": "First Appeared Chapter",
    "age_text": "Age",
    "gender": "Gender",
    "race_or_species": "Race / Species",
    "origin": "Origin",
    "faction_or_affiliation": "Affiliation",
    "status": "Status",
    "titles": "Titles",
    "current_position": "Current Position",
    "admin_notes": "Admin Notes",
}

SKILL_LOG_FIELDS = {
    "name": "Canonical Name",
    "category": "Category",
    "description": "Description",
    "admin_notes": "Admin Notes",
}

ITEM_LOG_FIELDS = {
    "name": "Canonical Name",
    "category": "Category",
    "description": "Description",
    "admin_notes": "Admin Notes",
}


def record_character_editor_logs(before, after):
    record_field_logs(after["novel_id"], "character", after["id"], after["name"], before, after, CHARACTER_LOG_FIELDS)
    record_collection_logs(
        novel_id=after["novel_id"],
        parent_type="character",
        parent_id=after["id"],
        parent_label=after["name"],
        entity_type="alias",
        before_rows=before.get("aliases") or [],
        after_rows=after.get("aliases") or [],
        entity_label_getter=lambda row: row.get("alias"),
        field_getters=[
            ("alias", "Alias", lambda row: row.get("alias")),
            ("chapter", "First Mentioned Chapter", lambda row: row.get("first_seen_chapter")),
            ("evidence", "Evidence", lambda row: row.get("evidence")),
            ("is_primary", "Primary Alias", lambda row: row.get("is_primary")),
        ],
        added_field="Alias",
        removed_field="Alias",
    )
    record_collection_logs(
        novel_id=after["novel_id"],
        parent_type="character",
        parent_id=after["id"],
        parent_label=after["name"],
        entity_type="cultivation",
        before_rows=before.get("progression_events") or [],
        after_rows=after.get("progression_events") or [],
        entity_label_getter=lambda row: row.get("new_value") or "Cultivation Breakthrough",
        field_getters=[
            ("new_value", "Cultivation Level", lambda row: row.get("new_value")),
            ("chapter", "Chapter", lambda row: row.get("chapter")),
            ("description", "Notes", lambda row: row.get("description")),
            ("evidence", "Evidence", first_evidence_text),
        ],
        added_field="Cultivation Breakthrough",
        removed_field="Cultivation Breakthrough",
    )
    record_collection_logs(
        novel_id=after["novel_id"],
        parent_type="character",
        parent_id=after["id"],
        parent_label=after["name"],
        entity_type="character_skill",
        before_rows=before.get("skills") or [],
        after_rows=after.get("skills") or [],
        entity_label_getter=lambda row: row.get("skill_name") or "Skill Link",
        field_getters=[
            ("skill", "Skill", lambda row: row.get("skill_name")),
            ("chapter", "First Known Chapter", lambda row: row.get("chapter")),
            ("description", "Description", lambda row: row.get("description")),
            ("evidence", "Evidence", first_evidence_text),
        ],
        added_field="Character Skill Link",
        removed_field="Character Skill Link",
    )
    record_collection_logs(
        novel_id=after["novel_id"],
        parent_type="character",
        parent_id=after["id"],
        parent_label=after["name"],
        entity_type="character_item",
        before_rows=before.get("items") or [],
        after_rows=after.get("items") or [],
        entity_label_getter=lambda row: row.get("item_name") or "Item Link",
        field_getters=[
            ("item", "Item", lambda row: row.get("item_name")),
            ("chapter", "First Known Chapter", lambda row: row.get("chapter")),
            ("description", "Description", lambda row: row.get("description")),
            ("evidence", "Evidence", first_evidence_text),
        ],
        added_field="Character Item Link",
        removed_field="Character Item Link",
    )


def record_skill_editor_logs(before, after):
    record_field_logs(after["novel_id"], "skill", after["id"], after["name"], before, after, SKILL_LOG_FIELDS)
    record_collection_logs(
        novel_id=after["novel_id"],
        parent_type="skill",
        parent_id=after["id"],
        parent_label=after["name"],
        entity_type="skill_alias",
        before_rows=before.get("aliases") or [],
        after_rows=after.get("aliases") or [],
        entity_label_getter=lambda row: row.get("alias"),
        field_getters=[
            ("alias", "Alias", lambda row: row.get("alias")),
            ("chapter", "First Mentioned Chapter", lambda row: row.get("first_seen_chapter")),
            ("evidence", "Evidence", lambda row: row.get("evidence")),
        ],
        added_field="Alias",
        removed_field="Alias",
    )
    record_collection_logs(
        novel_id=after["novel_id"],
        parent_type="skill",
        parent_id=after["id"],
        parent_label=after["name"],
        entity_type="character_skill",
        before_rows=before.get("characters") or [],
        after_rows=after.get("characters") or [],
        entity_label_getter=lambda row: row.get("character_name") or "Character Link",
        field_getters=[
            ("character", "Character", lambda row: row.get("character_name")),
            ("chapter", "First Known Chapter", lambda row: row.get("chapter")),
            ("description", "Description", lambda row: row.get("description")),
            ("evidence", "Evidence", first_evidence_text),
        ],
        added_field="Character Skill Link",
        removed_field="Character Skill Link",
    )


def record_item_editor_logs(before, after):
    record_field_logs(after["novel_id"], "item", after["id"], after["name"], before, after, ITEM_LOG_FIELDS)
    record_collection_logs(
        novel_id=after["novel_id"],
        parent_type="item",
        parent_id=after["id"],
        parent_label=after["name"],
        entity_type="character_item",
        before_rows=before.get("characters") or [],
        after_rows=after.get("characters") or [],
        entity_label_getter=lambda row: row.get("character_name") or "Character Link",
        field_getters=[
            ("character", "Character", lambda row: row.get("character_name")),
            ("chapter", "First Known Chapter", lambda row: row.get("chapter")),
            ("description", "Description", lambda row: row.get("description")),
            ("evidence", "Evidence", first_evidence_text),
        ],
        added_field="Character Item Link",
        removed_field="Character Item Link",
    )


def parse_date_filter(value, end_of_day=False):
    if not value:
        return None

    try:
        parsed_date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed_date = datetime.combine(
                datetime.strptime(value, "%Y-%m-%d").date(),
                time.max if end_of_day else time.min,
                tzinfo=timezone.utc,
            )
        except ValueError as error:
            raise PayloadValidationError("Date filters must be valid dates.") from error

    if parsed_date.tzinfo is None:
        parsed_date = parsed_date.replace(tzinfo=timezone.utc)

    return parsed_date


def parent_label_for_edit_log(log):
    if not log.parent_entity_type or not log.parent_entity_id:
        return None

    model_by_type = {
        "character": Character,
        "skill": Skill,
        "item": Item,
    }
    model = model_by_type.get(log.parent_entity_type)

    if not model:
        return None

    record = db.session.get(model, log.parent_entity_id)

    return record.name if record else None


def edit_log_response(log):
    data = log.to_admin_dict()
    data["parent_entity_label"] = parent_label_for_edit_log(log)
    return data


def list_wiki_edit_logs(novel_id, args):
    page = max(args.get("page", 1, type=int), 1)
    per_page = min(max(args.get("per_page", 10, type=int), 1), 50)
    search = (args.get("search") or "").strip()
    entity_type = (args.get("entity_type") or "all").strip()
    change_type = (args.get("change_type") or "all").strip().lower()
    edited_by = (args.get("edited_by") or "all").strip()
    date_from = parse_date_filter(args.get("date_from"))
    date_to = parse_date_filter(args.get("date_to"), end_of_day=True)

    query = WikiEditLog.query.filter_by(novel_id=novel_id)

    if search:
        like_search = f"%{search}%"
        query = query.filter(
            db.or_(
                WikiEditLog.entity_label.ilike(like_search),
                WikiEditLog.field_name.ilike(like_search),
                WikiEditLog.summary.ilike(like_search),
                WikiEditLog.old_value_json.ilike(like_search),
                WikiEditLog.new_value_json.ilike(like_search),
            )
        )

    if entity_type != "all":
        query = query.filter(WikiEditLog.entity_type == entity_type)

    if change_type != "all":
        query = query.filter(WikiEditLog.change_type == change_type)

    if edited_by != "all":
        query = query.filter(WikiEditLog.edited_by == edited_by)

    if date_from:
        query = query.filter(db.func.date(WikiEditLog.created_at) >= date_from.date().isoformat())

    if date_to:
        query = query.filter(db.func.date(WikiEditLog.created_at) <= date_to.date().isoformat())

    total = query.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    logs = (
        query.order_by(WikiEditLog.created_at.desc(), WikiEditLog.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "logs": [edit_log_response(log) for log in logs],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    }
