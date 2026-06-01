import json
import threading
from pathlib import Path
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from openai import AuthenticationError, RateLimitError
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from app.models import (
    Book,
    Chapter,
    Character,
    CharacterItem,
    CharacterLifeEvent,
    CharacterMetadataProposal,
    CharacterProgressionEvent,
    CharacterSkill,
    ExtractionRun,
    ExtractionRunChapter,
    Novel,
    WikiEvent,
    WikiEvidence,
    db,
    serialize_datetime,
    utc_now,
)
from app.services.ai_extraction_service import ExtractionCancelled, extract_chapter_with_ai
from app.services.chapter_parser import split_txt_into_chapters
from app.services.extraction_service import get_extracted_data, run_placeholder_extraction


admin_novels_bp = Blueprint("admin_novels", __name__)


def success(data, status=200):
    return jsonify({"data": data, "error": None}), status


def failure(message, status=400):
    return jsonify({"data": None, "error": message}), status


def decode_uploaded_text(uploaded_file):
    raw_bytes = uploaded_file.read()
    return raw_bytes, decode_text_bytes(raw_bytes)


def decode_text_bytes(raw_bytes):
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = raw_bytes.decode("utf-8-sig", errors="replace")

    return text


def save_uploaded_file(uploaded_file, original_filename):
    upload_dir = Path(current_app.instance_path) / current_app.config["UPLOAD_FOLDER"]
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = upload_dir / original_filename
    stored_path.write_bytes(uploaded_file)
    return stored_path


def stored_book_filename(novel_id, book_number, original_filename):
    return f"novel-{novel_id}-book-{book_number}-{original_filename}"


def find_stored_book_path(novel, book):
    if not book.source_filename:
        return None

    upload_dir = Path(current_app.instance_path) / current_app.config["UPLOAD_FOLDER"]
    exact_path = upload_dir / stored_book_filename(novel.id, book.number, secure_filename(book.source_filename))

    if exact_path.exists():
        return exact_path

    matches = sorted(upload_dir.glob(f"novel-{novel.id}-book-*-{secure_filename(book.source_filename)}"))
    return matches[-1] if matches else None


def book_has_extraction_or_review_data(book):
    chapter_ids = [chapter.id for chapter in book.chapters]

    if not chapter_ids:
        return False

    if ExtractionRunChapter.query.filter(ExtractionRunChapter.chapter_id.in_(chapter_ids)).first():
        return True

    if Character.query.filter(
        Character.novel_id == book.novel_id,
        or_(
            Character.first_mentioned_chapter_id.in_(chapter_ids),
            Character.first_appeared_chapter_id.in_(chapter_ids),
            Character.first_seen_chapter_id.in_(chapter_ids),
        ),
    ).first():
        return True

    review_models = [
        CharacterMetadataProposal,
        WikiEvent,
        WikiEvidence,
        CharacterProgressionEvent,
        CharacterSkill,
        CharacterItem,
        CharacterLifeEvent,
    ]

    return any(
        model.query.filter(model.novel_id == book.novel_id, model.chapter_id.in_(chapter_ids)).first()
        for model in review_models
    )


def aggregate_book_summary(book):
    data = book.to_admin_dict()
    data["pending_review_count"] = 0
    data["warning_count"] = 0

    completed_chapter_ids = {
        run_chapter.chapter_id
        for run_chapter in ExtractionRunChapter.query.join(Chapter)
        .filter(Chapter.book_id == book.id)
        .filter(ExtractionRunChapter.status == "completed")
        .all()
    }

    data["extracted_chapter_count"] = len(completed_chapter_ids)

    latest_run_chapter = (
        ExtractionRunChapter.query.join(Chapter)
        .filter(Chapter.book_id == book.id)
        .order_by(ExtractionRunChapter.updated_at.desc())
        .first()
    )
    failed_run_chapter = (
        ExtractionRunChapter.query.join(Chapter)
        .filter(Chapter.book_id == book.id)
        .filter(ExtractionRunChapter.status == "failed")
        .order_by(ExtractionRunChapter.updated_at.desc())
        .first()
    )

    data["last_extraction_status"] = latest_run_chapter.status if latest_run_chapter else None
    data["last_extraction_at"] = (
        serialize_datetime(
            latest_run_chapter.finished_at
            or latest_run_chapter.started_at
            or latest_run_chapter.updated_at
        )
        if latest_run_chapter
        else None
    )
    data["failed_chapter_number"] = (
        failed_run_chapter.chapter.chapter_number
        if failed_run_chapter and failed_run_chapter.chapter
        else None
    )
    data["can_reparse"] = not book_has_extraction_or_review_data(book)
    return data


def aggregate_novel_summary(novel):
    data = novel.to_admin_dict()
    review_data = get_extracted_data(novel)
    review_keys = [
        "characters",
        "character_metadata_proposals",
        "progression_events",
        "character_skills",
        "skills",
        "items",
        "character_items",
        "life_events",
        "events",
    ]
    today = datetime.now(timezone.utc).date()

    data["pending_review_count"] = sum(
        1
        for key in review_keys
        for record in review_data.get(key, [])
        if record.get("review_status") == "pending"
    )
    data["approved_record_count"] = sum(
        1
        for key in review_keys
        for record in review_data.get(key, [])
        if record.get("review_status") == "approved"
    )
    data["warning_count"] = count_review_warnings(review_data)
    data["active_extraction_count"] = ExtractionRun.query.filter(
        ExtractionRun.novel_id == novel.id,
        ExtractionRun.status.in_(["queued", "running"]),
    ).count()
    data["completed_today_count"] = ExtractionRun.query.filter(
        ExtractionRun.novel_id == novel.id,
        ExtractionRun.status == "completed",
        ExtractionRun.finished_at.isnot(None),
    ).filter(db.func.date(ExtractionRun.finished_at) == today.isoformat()).count()

    completed_chapter_ids = {
        run_chapter.chapter_id
        for run_chapter in ExtractionRunChapter.query.join(ExtractionRun)
        .filter(ExtractionRun.novel_id == novel.id)
        .filter(ExtractionRunChapter.status == "completed")
        .all()
    }
    data["extracted_chapter_count"] = len(completed_chapter_ids)

    latest_run = (
        ExtractionRun.query.filter_by(novel_id=novel.id)
        .order_by(ExtractionRun.created_at.desc())
        .first()
    )
    data["last_extraction_status"] = latest_run.status if latest_run else None
    data["last_extraction_at"] = serialize_datetime(
        latest_run.finished_at or latest_run.started_at or latest_run.created_at
    ) if latest_run else None

    return data


def next_book_number(novel):
    existing_numbers = [book.number for book in novel.books]
    return max(existing_numbers, default=0) + 1


def parse_book_number(value, novel):
    if value in (None, ""):
        return next_book_number(novel)

    try:
        number = int(value)
    except (TypeError, ValueError):
        return None

    return number if number > 0 else None


def append_chapters_to_book(novel, book, chapters):
    for chapter_data in chapters:
        book.chapters.append(
            Chapter(
                novel=novel,
                book=book,
                chapter_number=chapter_data["chapter_number"],
                title=chapter_data["title"],
                content=chapter_data["content"],
                character_count=len(chapter_data["content"]),
            )
        )


def conflicting_chapter_numbers(novel, book, chapters):
    chapter_numbers = sorted({chapter_data["chapter_number"] for chapter_data in chapters})

    if not chapter_numbers:
        return []

    query = Chapter.query.filter(
        Chapter.novel_id == novel.id,
        Chapter.chapter_number.in_(chapter_numbers),
    )

    if book and book.id:
        query = query.filter(Chapter.book_id != book.id)

    return sorted({chapter.chapter_number for chapter in query.all()})


def chapter_conflict_message(conflicts):
    if not conflicts:
        return ""

    preview = ", ".join(str(number) for number in conflicts[:5])
    suffix = "..." if len(conflicts) > 5 else ""
    return (
        "This source contains chapter numbers already used by another book: "
        f"{preview}{suffix}. Check that the selected file belongs to this book."
    )


def empty_extraction_summary():
    return {
        "characters_created": 0,
        "characters_updated": 0,
        "skills_created": 0,
        "skills_updated": 0,
        "items_created": 0,
        "items_updated": 0,
        "events_created": 0,
        "progression_events_created": 0,
        "metadata_proposals_created": 0,
        "character_skills_created": 0,
        "life_events_created": 0,
        "evidence_created": 0,
    }


def count_created_records(summary):
    return sum(value for value in summary.values() if isinstance(value, int))


def count_review_warnings(review_data):
    warning_keys = ["progression_events", "character_metadata_proposals"]
    return sum(
        len(
            [
                record
                for record in review_data.get(key, [])
                if record.get("review_warnings")
            ]
        )
        for key in warning_keys
    )


def count_chapter_warnings(review_data, chapter_id):
    warning_keys = ["progression_events", "character_metadata_proposals"]
    total = 0

    for key in warning_keys:
        for record in review_data.get(key, []):
            source_chapter = record.get("source_chapter") or record.get("chapter") or {}
            if source_chapter.get("id") == chapter_id and record.get("review_warnings"):
                total += 1

    return total


def scope_label(scope_type):
    return scope_type.replace("_", " ").title()


def chapters_for_extraction_scope(novel, payload):
    scope_type = payload.get("scope_type")
    book_id = payload.get("book_id")
    chapter_id = payload.get("chapter_id")
    chapter_start = payload.get("chapter_start")
    chapter_end = payload.get("chapter_end")
    source_run_id = payload.get("source_run_id")

    query = Chapter.query.filter_by(novel_id=novel.id)

    try:
        chapter_start = int(chapter_start) if chapter_start not in (None, "") else None
        chapter_end = int(chapter_end) if chapter_end not in (None, "") else None
        book_id = int(book_id) if book_id not in (None, "") else None
        chapter_id = int(chapter_id) if chapter_id not in (None, "") else None
        source_run_id = int(source_run_id) if source_run_id not in (None, "") else None
    except (TypeError, ValueError):
        return None, "Book and chapter values must be numbers."

    if chapter_start and chapter_end and chapter_start > chapter_end:
        return None, "Chapter start cannot be greater than chapter end."

    if scope_type == "single_chapter":
        if not chapter_id:
            return None, "A chapter is required for single chapter extraction."
        chapters = query.filter_by(id=chapter_id).all()
    elif scope_type == "chapter_range":
        if not book_id:
            return None, "A book is required for chapter range extraction."
        book = Book.query.filter_by(id=book_id, novel_id=novel.id).first()
        if not book:
            return None, "Book not found."
        query = query.filter_by(book_id=book.id)
        first_book_chapter = query.order_by(Chapter.chapter_number.asc()).first()
        last_book_chapter = query.order_by(Chapter.chapter_number.desc()).first()

        if not first_book_chapter or not last_book_chapter:
            return None, "This book has no parsed chapters yet. Reparse the book before starting extraction."

        if chapter_start is None:
            chapter_start = first_book_chapter.chapter_number
        if chapter_end is None:
            chapter_end = last_book_chapter.chapter_number

        if chapter_start > chapter_end:
            return None, "Chapter start cannot be greater than chapter end."

        if (
            chapter_start < first_book_chapter.chapter_number
            or chapter_start > last_book_chapter.chapter_number
            or chapter_end < first_book_chapter.chapter_number
            or chapter_end > last_book_chapter.chapter_number
        ):
            return None, (
                f"Book {book.number} contains chapters "
                f"{first_book_chapter.chapter_number}-{last_book_chapter.chapter_number}. "
                "Choose a chapter range inside this book."
            )

        if chapter_start:
            query = query.filter(Chapter.chapter_number >= chapter_start)
        if chapter_end:
            query = query.filter(Chapter.chapter_number <= chapter_end)
        chapters = query.order_by(Chapter.chapter_number).all()
    elif scope_type == "book":
        if not book_id:
            return None, "A book is required for book extraction."
        book = Book.query.filter_by(id=book_id, novel_id=novel.id).first()
        if not book:
            return None, "Book not found."
        chapters = query.filter_by(book_id=book.id).order_by(Chapter.chapter_number).all()
    elif scope_type == "novel":
        chapters = query.order_by(Chapter.book_id, Chapter.chapter_number).all()
    elif scope_type == "retry_failed":
        source_run = None

        if source_run_id:
            source_run = ExtractionRun.query.filter_by(id=source_run_id, novel_id=novel.id).first()
        else:
            source_run = (
                ExtractionRun.query.filter_by(novel_id=novel.id, status="failed")
                .order_by(ExtractionRun.created_at.desc())
                .first()
            )

        if not source_run:
            return None, "No failed extraction run found to retry."

        failed_row = next(
            (run_chapter for run_chapter in source_run.run_chapters if run_chapter.status == "failed"),
            None,
        )

        if not failed_row:
            return None, "No failed chapter found in the selected extraction run."

        retry_chapter_ids = [
            run_chapter.chapter_id
            for run_chapter in source_run.run_chapters
            if run_chapter.id >= failed_row.id and run_chapter.status in {"failed", "pending", "skipped"}
        ]
        chapters = query.filter(Chapter.id.in_(retry_chapter_ids)).order_by(
            Chapter.book_id,
            Chapter.chapter_number,
        ).all()
    else:
        return None, "Unsupported extraction scope."

    if not chapters:
        return None, f"No chapters found for {scope_label(scope_type or 'unknown')} extraction."

    return chapters, None


def build_extraction_run(novel, payload, chapters):
    first_chapter = chapters[0]
    last_chapter = chapters[-1]
    scope_type = payload.get("scope_type")
    book_id = payload.get("book_id")

    if scope_type in {"single_chapter", "retry_failed"}:
        book_id = first_chapter.book_id

    return ExtractionRun(
        novel_id=novel.id,
        book_id=book_id,
        chapter_start=first_chapter.chapter_number,
        chapter_end=last_chapter.chapter_number,
        scope_type=scope_type,
        status="queued",
        total_chapters=len(chapters),
    )


def seed_extraction_run_chapters(run, chapters):
    for chapter in chapters:
        db.session.add(
            ExtractionRunChapter(
                extraction_run_id=run.id,
                chapter_id=chapter.id,
                status="pending",
            )
        )


def refresh_run_totals(run):
    run.completed_chapters = sum(
        1 for run_chapter in run.run_chapters if run_chapter.status == "completed"
    )
    run.failed_chapters = sum(
        1 for run_chapter in run.run_chapters if run_chapter.status == "failed"
    )
    run.created_records_count = sum(
        run_chapter.records_created for run_chapter in run.run_chapters
    )
    run.warning_count = sum(run_chapter.warning_count for run_chapter in run.run_chapters)

    aggregate_summary = empty_extraction_summary()

    for run_chapter in run.run_chapters:
        if not run_chapter.summary_json:
            continue

        chapter_summary = json.loads(run_chapter.summary_json)

        for key in aggregate_summary:
            aggregate_summary[key] += chapter_summary.get(key, 0)

    run.summary_json = json.dumps(aggregate_summary)
    return aggregate_summary


def mark_pending_run_chapters_skipped(run):
    for run_chapter in run.run_chapters:
        if run_chapter.status == "pending":
            run_chapter.status = "skipped"
            run_chapter.finished_at = utc_now()


def extraction_run_can_save_chapter(run_id, run_chapter_id):
    db.session.expire_all()
    run = ExtractionRun.query.get(run_id)
    run_chapter = ExtractionRunChapter.query.get(run_chapter_id)
    return (
        run
        and run.status == "running"
        and run_chapter
        and run_chapter.status == "processing"
    )


def run_extraction_scope(novel, run):
    aggregate_summary = empty_extraction_summary()
    chapter_summaries = []

    db.session.refresh(run)

    if run.status == "cancelled":
        mark_pending_run_chapters_skipped(run)
        run.current_chapter_id = None
        run.finished_at = run.finished_at or utc_now()
        novel.status = "ready"
        if run.book:
            run.book.extraction_status = "cancelled"
        refresh_run_totals(run)
        db.session.commit()
        return aggregate_summary, chapter_summaries

    run.status = "running"
    run.started_at = utc_now()
    novel.status = "processing"
    novel.error_message = None

    if run.book:
        run.book.extraction_status = "running"

    db.session.commit()

    for run_chapter in run.run_chapters:
        db.session.refresh(run)

        if run.status == "cancelled":
            mark_pending_run_chapters_skipped(run)
            run.current_chapter_id = None
            run.finished_at = run.finished_at or utc_now()
            novel.status = "ready"
            if run.book:
                run.book.extraction_status = "cancelled"
            refresh_run_totals(run)
            db.session.commit()
            return aggregate_summary, chapter_summaries

        if run_chapter.status != "pending":
            continue

        chapter = run_chapter.chapter
        run_chapter.status = "processing"
        run_chapter.started_at = utc_now()
        run.current_chapter_id = chapter.id
        db.session.commit()

        last_error = None
        run_id = run.id
        run_chapter_id = run_chapter.id

        for attempt in range(2):
            try:
                summary = extract_chapter_with_ai(
                    novel,
                    chapter,
                    should_continue=lambda: extraction_run_can_save_chapter(run_id, run_chapter_id),
                )
                break
            except ExtractionCancelled:
                db.session.rollback()
                run_chapter = ExtractionRunChapter.query.get(run_chapter_id)
                run = ExtractionRun.query.get(run_id)

                if run_chapter:
                    run_chapter.status = "cancelled"
                    run_chapter.error_message = "Canceled before saving chapter output."
                    run_chapter.finished_at = utc_now()

                if run:
                    run.status = "cancelled"
                    run.error_message = "Canceled by user."
                    run.finished_at = utc_now()
                    run.current_chapter_id = None
                    mark_pending_run_chapters_skipped(run)
                    refresh_run_totals(run)

                    if run.book:
                        run.book.extraction_status = "cancelled"

                novel.status = "ready"
                novel.error_message = None
                db.session.commit()
                return aggregate_summary, chapter_summaries
            except Exception as error:
                last_error = error
                db.session.rollback()

                if attempt == 0:
                    current_app.logger.warning(
                        "AI extraction failed for chapter %s; retrying once: %s",
                        chapter.chapter_number,
                        error,
                    )
                    run_chapter = ExtractionRunChapter.query.get(run_chapter_id)
                    run = ExtractionRun.query.get(run_id)
                    continue

                run_chapter = ExtractionRunChapter.query.get(run_chapter_id)
                run = ExtractionRun.query.get(run_id)
                run_chapter.status = "failed"
                run_chapter.error_message = str(error)
                run_chapter.finished_at = utc_now()
                refresh_run_totals(run)
                db.session.commit()
                raise last_error

        review_data = get_extracted_data(novel)
        run_chapter.records_created = count_created_records(summary)
        run_chapter.warning_count = count_chapter_warnings(review_data, chapter.id)
        run_chapter.summary_json = json.dumps(summary)
        run_chapter.status = "completed"
        run_chapter.finished_at = utc_now()
        chapter_summaries.append({"chapter": chapter.to_reference_dict(), "summary": summary})

        for key in aggregate_summary:
            aggregate_summary[key] += summary.get(key, 0)

        refresh_run_totals(run)
        db.session.commit()

        db.session.refresh(run)

        if run.status == "cancelled":
            mark_pending_run_chapters_skipped(run)
            run.current_chapter_id = None
            run.finished_at = run.finished_at or utc_now()
            novel.status = "ready"
            if run.book:
                run.book.extraction_status = "cancelled"
            refresh_run_totals(run)
            db.session.commit()
            return aggregate_summary, chapter_summaries

    run.status = "completed"
    run.finished_at = utc_now()
    run.current_chapter_id = None
    novel.status = "ready"

    if run.book:
        run.book.extraction_status = "completed"

    refresh_run_totals(run)
    db.session.commit()

    return aggregate_summary, chapter_summaries


def mark_extraction_run_failed(novel, run, message):
    run.status = "failed"
    refresh_run_totals(run)
    run.error_message = message
    run.finished_at = utc_now()
    run.current_chapter_id = None
    novel.status = "failed"
    novel.error_message = message

    if run.book:
        run.book.extraction_status = "failed"

    db.session.commit()


def process_extraction_run_in_background(app, run_id):
    with app.app_context():
        try:
            run = ExtractionRun.query.get(run_id)

            if not run:
                return

            novel = Novel.query.get(run.novel_id)

            try:
                run_extraction_scope(novel, run)
            except RuntimeError as error:
                mark_extraction_run_failed(novel, run, str(error))
            except AuthenticationError:
                mark_extraction_run_failed(
                    novel,
                    run,
                    "AI API key was rejected. Check backend/.env and restart Flask.",
                )
            except RateLimitError:
                mark_extraction_run_failed(
                    novel,
                    run,
                    "AI API quota is unavailable. Check provider billing and usage limits.",
                )
            except Exception as error:
                mark_extraction_run_failed(
                    novel,
                    run,
                    "AI extraction failed. Check backend logs for details.",
                )
                app.logger.exception("AI extraction run failed: %s", error)
        finally:
            db.session.remove()


@admin_novels_bp.post("/novels/upload")
def upload_novel():
    uploaded_file = request.files.get("file")
    title = request.form.get("title", "").strip()

    if not uploaded_file:
        return failure("A .txt file is required.")

    original_filename = secure_filename(uploaded_file.filename or "")

    if not original_filename.lower().endswith(".txt"):
        return failure("Only .txt files are supported in this MVP.")

    raw_bytes, text = decode_uploaded_text(uploaded_file)
    chapters = split_txt_into_chapters(text)

    if not chapters:
        return failure("No chapter text could be found in the uploaded file.")

    save_uploaded_file(raw_bytes, original_filename)

    novel = Novel(
        title=title or Path(original_filename).stem,
        original_filename=original_filename,
        file_type="txt",
        status="ready",
    )
    book = Book(
        novel=novel,
        number=1,
        title="Book 1",
        source_filename=original_filename,
        parsing_status="parsed",
        extraction_status="not_started",
    )

    append_chapters_to_book(novel, book, chapters)

    db.session.add(novel)
    db.session.commit()

    return success(
        {
            "novel": novel.to_admin_dict(),
            "chapter_count": len(chapters),
        },
        status=201,
    )


@admin_novels_bp.post("/novels")
def create_novel():
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    author = (payload.get("author") or "").strip() or None
    description = (payload.get("description") or "").strip() or None
    cover_image_url = (payload.get("cover_image_url") or "").strip() or None
    status = (payload.get("status") or "ready").strip()

    if not title:
        return failure("Novel title is required.")

    if status not in {"ready", "draft"}:
        return failure("Novel status must be ready or draft.")

    novel = Novel(
        title=title,
        author=author,
        description=description,
        cover_image_url=cover_image_url,
        original_filename="",
        file_type="workspace",
        status=status,
    )
    db.session.add(novel)
    db.session.commit()

    return success({"novel": novel.to_admin_dict()}, status=201)


@admin_novels_bp.get("/novels")
def list_admin_novels():
    novels = Novel.query.order_by(Novel.created_at.desc()).all()
    return success([aggregate_novel_summary(novel) for novel in novels])


@admin_novels_bp.patch("/novels/<int:novel_id>")
def update_novel(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    author = (payload.get("author") or "").strip() or None
    description = (payload.get("description") or "").strip() or None
    cover_image_url = (payload.get("cover_image_url") or "").strip() or None
    status = (payload.get("status") or "ready").strip()

    if not title:
        return failure("Novel title is required.")

    if status not in {"ready", "draft"}:
        return failure("Novel status must be ready or draft.")

    novel.title = title
    novel.author = author
    novel.description = description
    novel.cover_image_url = cover_image_url
    novel.status = status
    novel.updated_at = utc_now()

    db.session.commit()

    return success({"novel": aggregate_novel_summary(novel)})


@admin_novels_bp.get("/novels/<int:novel_id>/books")
def list_admin_books(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    books = Book.query.filter_by(novel_id=novel.id).order_by(Book.number).all()

    return success(
        {
            "novel": novel.to_admin_dict(),
            "books": [aggregate_book_summary(book) for book in books],
        }
    )


@admin_novels_bp.post("/novels/<int:novel_id>/books/upload")
def upload_book(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    uploaded_file = request.files.get("file")
    title = request.form.get("title", "").strip()
    requested_number = request.form.get("number")

    if not uploaded_file:
        return failure("A .txt file is required.")

    original_filename = secure_filename(uploaded_file.filename or "")

    if not original_filename.lower().endswith(".txt"):
        return failure("Only .txt files are supported in this MVP.")

    book_number = parse_book_number(requested_number, novel)

    if book_number is None:
        return failure("Book number must be a positive integer.")

    existing_book = Book.query.filter_by(novel_id=novel.id, number=book_number).first()

    if existing_book:
        return failure(f"Book {book_number} already exists for this novel.")

    raw_bytes, text = decode_uploaded_text(uploaded_file)
    chapters = split_txt_into_chapters(text)

    if not chapters:
        return failure("No chapter text could be found in the uploaded file.")

    conflicts = conflicting_chapter_numbers(novel, None, chapters)

    if conflicts:
        return failure(chapter_conflict_message(conflicts))

    stored_filename = stored_book_filename(novel.id, book_number, original_filename)
    save_uploaded_file(raw_bytes, stored_filename)

    book = Book(
        novel_id=novel.id,
        number=book_number,
        title=title or f"Book {book_number}",
        source_filename=original_filename,
        parsing_status="parsed",
        extraction_status="not_started",
    )
    append_chapters_to_book(novel, book, chapters)
    db.session.add(book)
    db.session.commit()

    return success(
        {
            "novel": novel.to_admin_dict(),
            "book": aggregate_book_summary(book),
            "chapter_count": len(chapters),
        },
        status=201,
    )


@admin_novels_bp.patch("/novels/<int:novel_id>/books/<int:book_id>")
def update_book(novel_id, book_id):
    novel = Novel.query.get_or_404(novel_id)
    book = Book.query.filter_by(id=book_id, novel_id=novel.id).first_or_404()
    payload = request.get_json(silent=True) or {}
    requested_number = payload.get("number", book.number)
    title = (payload.get("title") or "").strip()

    book_number = parse_book_number(requested_number, novel)

    if book_number is None:
        return failure("Book number must be a positive integer.")

    existing_book = Book.query.filter(
        Book.novel_id == novel.id,
        Book.number == book_number,
        Book.id != book.id,
    ).first()

    if existing_book:
        return failure(f"Book {book_number} already exists for this novel.")

    book.number = book_number
    book.title = title or f"Book {book_number}"
    db.session.commit()

    return success({"book": aggregate_book_summary(book)})


@admin_novels_bp.post("/novels/<int:novel_id>/books/<int:book_id>/source")
def replace_book_source(novel_id, book_id):
    novel = Novel.query.get_or_404(novel_id)
    book = Book.query.filter_by(id=book_id, novel_id=novel.id).first_or_404()
    uploaded_file = request.files.get("file")

    if book_has_extraction_or_review_data(book):
        return failure(
            "Source replacement is disabled because this book has extracted or review-linked data."
        )

    if not uploaded_file:
        return failure("A .txt file is required.")

    original_filename = secure_filename(uploaded_file.filename or "")

    if not original_filename.lower().endswith(".txt"):
        return failure("Only .txt files are supported in this MVP.")

    raw_bytes, text = decode_uploaded_text(uploaded_file)
    chapters = split_txt_into_chapters(text)

    if not chapters:
        return failure("Could not parse chapters from this file.")

    conflicts = conflicting_chapter_numbers(novel, book, chapters)

    if conflicts:
        return failure(chapter_conflict_message(conflicts))

    deleted_chapter_count = len(book.chapters)
    stored_filename = stored_book_filename(novel.id, book.number, original_filename)
    save_uploaded_file(raw_bytes, stored_filename)

    for chapter in list(book.chapters):
        db.session.delete(chapter)

    db.session.flush()
    book.source_filename = original_filename
    book.uploaded_at = utc_now()
    book.parsing_status = "source_replaced"
    book.extraction_status = "not_started"
    db.session.commit()

    return success({"book": aggregate_book_summary(book), "deleted_chapter_count": deleted_chapter_count})


@admin_novels_bp.post("/novels/<int:novel_id>/books/<int:book_id>/reparse")
def reparse_book(novel_id, book_id):
    novel = Novel.query.get_or_404(novel_id)
    book = Book.query.filter_by(id=book_id, novel_id=novel.id).first_or_404()

    if book_has_extraction_or_review_data(book):
        return failure(
            "Reparse is disabled because this book has extracted or review-linked data."
        )

    stored_path = find_stored_book_path(novel, book)

    if not stored_path:
        return failure("No stored source file was found for this book.")

    text = decode_text_bytes(stored_path.read_bytes())
    chapters = split_txt_into_chapters(text)

    if not chapters:
        return failure("Could not parse chapters from this file.")

    conflicts = conflicting_chapter_numbers(novel, book, chapters)

    if conflicts:
        return failure(chapter_conflict_message(conflicts))

    for chapter in list(book.chapters):
        db.session.delete(chapter)

    db.session.flush()
    append_chapters_to_book(novel, book, chapters)
    book.parsing_status = "parsed"
    book.extraction_status = "not_started"
    book.uploaded_at = utc_now()

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return failure("Could not reparse this book because chapter numbers conflict with existing chapters.")

    return success({"book": aggregate_book_summary(book), "chapter_count": len(chapters)})


@admin_novels_bp.get("/novels/<int:novel_id>/chapters")
def list_admin_chapters(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    book_id = request.args.get("book_id", type=int)
    query = Chapter.query.filter_by(novel_id=novel.id)

    if book_id:
        Book.query.filter_by(id=book_id, novel_id=novel.id).first_or_404()
        query = query.filter_by(book_id=book_id)

    chapters = query.order_by(Chapter.book_id, Chapter.chapter_number).all()

    return success(
        {
            "novel": novel.to_admin_dict(),
            "books": [
                aggregate_book_summary(book)
                for book in Book.query.filter_by(novel_id=novel.id).order_by(Book.number).all()
            ],
            "chapters": [chapter.to_admin_verification_dict() for chapter in chapters],
        }
    )


@admin_novels_bp.post("/novels/<int:novel_id>/process")
def process_novel(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    run_placeholder_extraction(novel)
    return success(get_extracted_data(novel))


@admin_novels_bp.get("/novels/<int:novel_id>/extracted-data")
def get_admin_extracted_data(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    return success(get_extracted_data(novel))


@admin_novels_bp.post("/novels/<int:novel_id>/chapters/<int:chapter_id>/extract")
def extract_single_chapter(novel_id, chapter_id):
    novel = Novel.query.get_or_404(novel_id)
    chapter = Chapter.query.filter_by(id=chapter_id, novel_id=novel.id).first_or_404()

    try:
        novel.status = "processing"
        novel.error_message = None
        db.session.commit()
        summary = extract_chapter_with_ai(novel, chapter)
    except RuntimeError as error:
        novel.status = "failed"
        novel.error_message = str(error)
        db.session.commit()
        return failure(str(error), status=400)
    except AuthenticationError:
        novel.status = "failed"
        novel.error_message = "AI API key was rejected. Check backend/.env and restart Flask."
        db.session.commit()
        return failure(novel.error_message, status=401)
    except RateLimitError:
        novel.status = "failed"
        novel.error_message = "AI API quota is unavailable. Check provider billing and usage limits."
        db.session.commit()
        return failure(novel.error_message, status=429)
    except Exception as error:
        novel.status = "failed"
        novel.error_message = "AI extraction failed. Check backend logs for details."
        db.session.commit()
        current_app.logger.exception("AI extraction failed: %s", error)
        return failure(novel.error_message, status=500)

    data = get_extracted_data(novel)
    data["summary"] = summary
    data["extracted_chapter"] = chapter.to_reference_dict()
    return success(data)


@admin_novels_bp.get("/novels/<int:novel_id>/extraction-runs")
def list_extraction_runs(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    runs = (
        ExtractionRun.query.filter_by(novel_id=novel.id)
        .order_by(ExtractionRun.created_at.desc())
        .all()
    )

    return success({"runs": [run.to_admin_dict() for run in runs]})


@admin_novels_bp.get("/novels/<int:novel_id>/extraction-runs/<int:run_id>")
def get_extraction_run(novel_id, run_id):
    novel = Novel.query.get_or_404(novel_id)
    run = ExtractionRun.query.filter_by(id=run_id, novel_id=novel.id).first_or_404()
    return success({"run": run.to_admin_dict()})


@admin_novels_bp.post("/novels/<int:novel_id>/extraction-runs/<int:run_id>/cancel")
def cancel_extraction_run(novel_id, run_id):
    novel = Novel.query.get_or_404(novel_id)
    run = ExtractionRun.query.filter_by(id=run_id, novel_id=novel.id).first_or_404()

    if run.status not in {"queued", "running"}:
        return failure("Only queued or running extraction runs can be stopped.")

    has_processing_chapter = any(
        run_chapter.status == "processing" for run_chapter in run.run_chapters
    )

    run.status = "cancelled"
    run.error_message = "Canceled by user."
    run.finished_at = None if has_processing_chapter else utc_now()
    run.current_chapter_id = run.current_chapter_id if has_processing_chapter else None
    novel.status = "ready"
    novel.error_message = None

    if run.book:
        run.book.extraction_status = "cancelled"

    mark_pending_run_chapters_skipped(run)
    refresh_run_totals(run)
    db.session.commit()

    return success({"run": run.to_admin_dict()})


@admin_novels_bp.delete("/novels/<int:novel_id>/extraction-runs/<int:run_id>")
def delete_extraction_run(novel_id, run_id):
    novel = Novel.query.get_or_404(novel_id)
    run = ExtractionRun.query.filter_by(id=run_id, novel_id=novel.id).first_or_404()

    if run.status not in {"completed", "failed"}:
        return failure("Only completed or failed extraction run history can be deleted.")

    deleted_run_id = run.id
    db.session.delete(run)
    db.session.commit()

    return success({"deleted_run_id": deleted_run_id})


@admin_novels_bp.post("/novels/<int:novel_id>/extraction-runs")
def create_extraction_run(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    payload = request.get_json(silent=True) or {}
    chapters, error = chapters_for_extraction_scope(novel, payload)

    if error:
        return failure(error)

    run = build_extraction_run(novel, payload, chapters)
    db.session.add(run)
    db.session.flush()
    seed_extraction_run_chapters(run, chapters)
    db.session.commit()

    app = current_app._get_current_object()
    thread = threading.Thread(
        target=process_extraction_run_in_background,
        args=(app, run.id),
        daemon=True,
    )
    thread.start()

    return success({"run": run.to_admin_dict()}, status=202)
