from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from openai import AuthenticationError, RateLimitError
from werkzeug.utils import secure_filename

from app.models import Book, Chapter, Novel, db
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
    data["extracted_chapter_count"] = 0
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


@admin_novels_bp.post("/novels/<int:novel_id>/extract-first-15")
def extract_first_fifteen_chapters(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    chapters = (
        Chapter.query.filter_by(novel_id=novel.id)
        .order_by(Chapter.chapter_number)
        .limit(15)
        .all()
    )

    if not chapters:
        return failure("No chapters found for this novel.")

    aggregate_summary = {
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
    chapter_summaries = []

    try:
        novel.status = "processing"
        novel.error_message = None
        db.session.commit()

        for chapter in chapters:
            summary = extract_chapter_with_ai(novel, chapter)
            chapter_summaries.append(
                {
                    "chapter": chapter.to_reference_dict(),
                    "summary": summary,
                }
            )

            for key in aggregate_summary:
                aggregate_summary[key] += summary.get(key, 0)
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
        current_app.logger.exception("AI batch extraction failed: %s", error)
        return failure(novel.error_message, status=500)

    data = get_extracted_data(novel)
    data["summary"] = aggregate_summary
    data["extracted_chapter_count"] = len(chapter_summaries)
    data["chapter_summaries"] = chapter_summaries
    return success(data)
