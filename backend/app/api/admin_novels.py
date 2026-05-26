from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from openai import AuthenticationError, RateLimitError
from werkzeug.utils import secure_filename

from app.models import Book, Chapter, ExtractionRun, Novel, db, utc_now
from app.services.ai_extraction_service import extract_chapter_with_ai
from app.services.chapter_parser import split_txt_into_chapters
from app.services.extraction_service import get_extracted_data, run_placeholder_extraction


admin_novels_bp = Blueprint("admin_novels", __name__)


def success(data, status=200):
    return jsonify({"data": data, "error": None}), status


def failure(message, status=400):
    return jsonify({"data": None, "error": message}), status


def decode_uploaded_text(uploaded_file):
    raw_bytes = uploaded_file.read()

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = raw_bytes.decode("utf-8-sig", errors="replace")

    return raw_bytes, text


def save_uploaded_file(uploaded_file, original_filename):
    upload_dir = Path(current_app.instance_path) / current_app.config["UPLOAD_FOLDER"]
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = upload_dir / original_filename
    stored_path.write_bytes(uploaded_file)
    return stored_path


def aggregate_book_summary(book):
    data = book.to_admin_dict()
    data["pending_review_count"] = 0
    data["warning_count"] = 0
    extracted_chapter_numbers = {
        run.chapter_start
        for run in ExtractionRun.query.filter_by(
            book_id=book.id,
            scope_type="single_chapter",
            status="completed",
        ).all()
        if run.chapter_start
    }
    completed_book_runs = ExtractionRun.query.filter_by(
        book_id=book.id,
        scope_type="book",
        status="completed",
    ).all()

    for run in completed_book_runs:
        extracted_chapter_numbers.update(
            chapter.chapter_number
            for chapter in Chapter.query.filter_by(book_id=book.id)
            .filter(Chapter.chapter_number >= (run.chapter_start or 0))
            .filter(Chapter.chapter_number <= (run.chapter_end or 10**9))
            .all()
        )

    data["extracted_chapter_count"] = len(extracted_chapter_numbers)
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


def scope_label(scope_type):
    return scope_type.replace("_", " ").title()


def chapters_for_extraction_scope(novel, payload):
    scope_type = payload.get("scope_type")
    book_id = payload.get("book_id")
    chapter_id = payload.get("chapter_id")
    chapter_start = payload.get("chapter_start")
    chapter_end = payload.get("chapter_end")

    query = Chapter.query.filter_by(novel_id=novel.id)

    try:
        chapter_start = int(chapter_start) if chapter_start not in (None, "") else None
        chapter_end = int(chapter_end) if chapter_end not in (None, "") else None
        book_id = int(book_id) if book_id not in (None, "") else None
        chapter_id = int(chapter_id) if chapter_id not in (None, "") else None
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
        failed_runs = ExtractionRun.query.filter_by(novel_id=novel.id, status="failed").all()
        failed_chapter_ids = {run.current_chapter_id for run in failed_runs if run.current_chapter_id}
        chapters = query.filter(Chapter.id.in_(failed_chapter_ids)).order_by(
            Chapter.book_id,
            Chapter.chapter_number,
        ).all() if failed_chapter_ids else []
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

    if scope_type == "single_chapter":
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


def run_extraction_scope(novel, run, chapters):
    aggregate_summary = empty_extraction_summary()
    chapter_summaries = []

    run.status = "running"
    run.started_at = utc_now()
    novel.status = "processing"
    novel.error_message = None

    if run.book:
        run.book.extraction_status = "running"

    db.session.commit()

    for chapter in chapters:
        run.current_chapter_id = chapter.id
        db.session.commit()

        summary = extract_chapter_with_ai(novel, chapter)
        chapter_summaries.append({"chapter": chapter.to_reference_dict(), "summary": summary})

        for key in aggregate_summary:
            aggregate_summary[key] += summary.get(key, 0)

        run.completed_chapters += 1
        run.created_records_count += count_created_records(summary)
        db.session.commit()

    run.status = "completed"
    run.finished_at = utc_now()
    novel.status = "ready"

    if run.book:
        run.book.extraction_status = "completed"

    review_data = get_extracted_data(novel)
    run.warning_count = count_review_warnings(review_data)
    db.session.commit()

    return aggregate_summary, chapter_summaries


def mark_extraction_run_failed(novel, run, message):
    run.status = "failed"
    run.failed_chapters = max(0, run.total_chapters - run.completed_chapters)
    run.error_message = message
    run.finished_at = utc_now()
    novel.status = "failed"
    novel.error_message = message

    if run.book:
        run.book.extraction_status = "failed"

    db.session.commit()


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

    if not title:
        return failure("Novel title is required.")

    novel = Novel(
        title=title,
        original_filename="",
        file_type="workspace",
        status="ready",
    )
    db.session.add(novel)
    db.session.commit()

    return success({"novel": novel.to_admin_dict()}, status=201)


@admin_novels_bp.get("/novels")
def list_admin_novels():
    novels = Novel.query.order_by(Novel.created_at.desc()).all()
    return success([novel.to_admin_dict() for novel in novels])


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

    stored_filename = f"novel-{novel.id}-book-{book_number}-{original_filename}"
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


@admin_novels_bp.post("/novels/<int:novel_id>/extraction-runs")
def create_extraction_run(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    payload = request.get_json(silent=True) or {}
    chapters, error = chapters_for_extraction_scope(novel, payload)

    if error:
        return failure(error)

    run = build_extraction_run(novel, payload, chapters)
    db.session.add(run)
    db.session.commit()

    try:
        aggregate_summary, chapter_summaries = run_extraction_scope(novel, run, chapters)
    except RuntimeError as error:
        mark_extraction_run_failed(novel, run, str(error))
        return failure(str(error), status=400)
    except AuthenticationError:
        message = "AI API key was rejected. Check backend/.env and restart Flask."
        mark_extraction_run_failed(novel, run, message)
        return failure(message, status=401)
    except RateLimitError:
        message = "AI API quota is unavailable. Check provider billing and usage limits."
        mark_extraction_run_failed(novel, run, message)
        return failure(message, status=429)
    except Exception as error:
        message = "AI extraction failed. Check backend logs for details."
        mark_extraction_run_failed(novel, run, message)
        current_app.logger.exception("AI batch extraction failed: %s", error)
        return failure(message, status=500)

    data = get_extracted_data(novel)
    data["run"] = run.to_admin_dict()
    data["summary"] = aggregate_summary
    data["extracted_chapter_count"] = len(chapter_summaries)
    data["chapter_summaries"] = chapter_summaries
    return success(data)
