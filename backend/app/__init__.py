from pathlib import Path

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from sqlalchemy import text

from app.api.admin_novels import admin_novels_bp
from app.api.admin_review import admin_review_bp
from app.api.health import health_bp
from app.api.wiki import wiki_bp
from app.models import db


def ensure_development_schema(app):
    review_tables = {
        "characters",
        "skills",
        "items",
        "wiki_events",
        "character_skills",
        "character_items",
    }

    with db.engine.connect() as connection:
        columns = connection.execute(text("PRAGMA table_info(novels)")).fetchall()
        column_names = {column[1] for column in columns}

        if "error_message" not in column_names:
            connection.execute(text("ALTER TABLE novels ADD COLUMN error_message TEXT"))

        novel_profile_columns = {
            "author": "VARCHAR(255)",
            "description": "TEXT",
            "cover_image_url": "TEXT",
        }

        for column_name, column_type in novel_profile_columns.items():
            if column_name not in column_names:
                connection.execute(
                    text(f"ALTER TABLE novels ADD COLUMN {column_name} {column_type}")
                )

        chapter_columns = connection.execute(text("PRAGMA table_info(chapters)")).fetchall()
        chapter_column_names = {column[1] for column in chapter_columns}

        if "book_id" not in chapter_column_names:
            connection.execute(text("ALTER TABLE chapters ADD COLUMN book_id INTEGER"))

        connection.execute(
            text(
                "DELETE FROM books "
                "WHERE number = 1 "
                "AND title = 'Book 1' "
                "AND COALESCE(source_filename, '') = '' "
                "AND NOT EXISTS (SELECT 1 FROM chapters WHERE chapters.book_id = books.id) "
                "AND EXISTS ("
                "  SELECT 1 FROM novels "
                "  WHERE novels.id = books.novel_id "
                "  AND COALESCE(novels.original_filename, '') = ''"
                ")"
            )
        )

        novels = connection.execute(text("SELECT id, title, original_filename FROM novels")).fetchall()

        for novel_id, novel_title, original_filename in novels:
            unassigned_chapter_count = connection.execute(
                text(
                    "SELECT COUNT(*) FROM chapters "
                    "WHERE novel_id = :novel_id AND book_id IS NULL"
                ),
                {"novel_id": novel_id},
            ).scalar()
            default_book = connection.execute(
                text("SELECT id FROM books WHERE novel_id = :novel_id ORDER BY number LIMIT 1"),
                {"novel_id": novel_id},
            ).fetchone()

            if default_book:
                default_book_id = default_book[0]
            elif not original_filename and not unassigned_chapter_count:
                continue
            else:
                connection.execute(
                    text(
                        "INSERT INTO books "
                        "(novel_id, number, title, source_filename, parsing_status, "
                        "extraction_status, created_at, uploaded_at) "
                        "VALUES "
                        "(:novel_id, 1, :title, :source_filename, 'parsed', "
                        "'not_started', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    ),
                    {
                        "novel_id": novel_id,
                        "title": "Book 1",
                        "source_filename": original_filename,
                    },
                )
                default_book_id = connection.execute(text("SELECT last_insert_rowid()")).scalar()

            connection.execute(
                text(
                    "UPDATE chapters "
                    "SET book_id = :book_id "
                    "WHERE novel_id = :novel_id AND book_id IS NULL"
                ),
                {"book_id": default_book_id, "novel_id": novel_id},
            )

        for table_name in review_tables:
            columns = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            column_names = {column[1] for column in columns}

            if "review_status" not in column_names:
                connection.execute(
                    text(
                        f"ALTER TABLE {table_name} "
                        "ADD COLUMN review_status VARCHAR(50) NOT NULL DEFAULT 'pending'"
                    )
                )

            if "admin_notes" not in column_names:
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN admin_notes TEXT"))

        character_columns = connection.execute(text("PRAGMA table_info(characters)")).fetchall()
        character_column_names = {column[1] for column in character_columns}

        if "first_mentioned_chapter_id" not in character_column_names:
            connection.execute(
                text("ALTER TABLE characters ADD COLUMN first_mentioned_chapter_id INTEGER")
            )

        if "first_appeared_chapter_id" not in character_column_names:
            connection.execute(
                text("ALTER TABLE characters ADD COLUMN first_appeared_chapter_id INTEGER")
            )

        character_summary_columns = {
            "age_text": "VARCHAR(255)",
            "gender": "VARCHAR(255)",
            "race_or_species": "VARCHAR(255)",
            "race_or_species_source": "VARCHAR(50)",
            "race_or_species_confidence": "VARCHAR(50)",
            "origin": "VARCHAR(255)",
            "faction_or_affiliation": "VARCHAR(255)",
            "status": "VARCHAR(255)",
            "titles": "TEXT",
            "current_cultivation_level": "VARCHAR(255)",
            "current_position": "VARCHAR(255)",
            "current_class_rank": "VARCHAR(255)",
            "current_power_rank": "VARCHAR(255)",
        }

        for column_name, column_type in character_summary_columns.items():
            if column_name not in character_column_names:
                connection.execute(
                    text(f"ALTER TABLE characters ADD COLUMN {column_name} {column_type}")
                )

        alias_columns = connection.execute(text("PRAGMA table_info(character_aliases)")).fetchall()
        alias_column_names = {column[1] for column in alias_columns}

        if alias_columns and "is_primary" not in alias_column_names:
            connection.execute(
                text("ALTER TABLE character_aliases ADD COLUMN is_primary BOOLEAN NOT NULL DEFAULT 0")
            )

        character_skill_columns = connection.execute(
            text("PRAGMA table_info(character_skills)")
        ).fetchall()

        if character_skill_columns:
            duplicate_skill_pairs = connection.execute(
                text(
                    "SELECT character_id, skill_id "
                    "FROM character_skills "
                    "GROUP BY character_id, skill_id "
                    "HAVING COUNT(*) > 1"
                )
            ).fetchall()

            for character_id, skill_id in duplicate_skill_pairs:
                skill_rows = connection.execute(
                    text(
                        "SELECT cs.id, cs.description, cs.admin_notes, cs.review_status, "
                        "cs.chapter_id, COALESCE(ch.chapter_number, 2147483647) AS chapter_number "
                        "FROM character_skills cs "
                        "LEFT JOIN chapters ch ON ch.id = cs.chapter_id "
                        "WHERE cs.character_id = :character_id AND cs.skill_id = :skill_id "
                        "ORDER BY chapter_number, cs.id"
                    ),
                    {"character_id": character_id, "skill_id": skill_id},
                ).fetchall()
                keeper = skill_rows[0]
                keeper_id = keeper[0]
                duplicate_ids = [row[0] for row in skill_rows[1:]]

                def merge_unique_text(values):
                    merged_values = []

                    for value in values:
                        normalized_value = (value or "").strip()

                        if normalized_value and normalized_value not in merged_values:
                            merged_values.append(normalized_value)

                    return "\n\n".join(merged_values) or None

                merged_description = merge_unique_text(row[1] for row in skill_rows)
                merged_admin_notes = merge_unique_text(row[2] for row in skill_rows)
                statuses = {row[3] for row in skill_rows}
                merged_status = (
                    "approved"
                    if "approved" in statuses
                    else "pending"
                    if "pending" in statuses
                    else "rejected"
                )

                for duplicate_id in duplicate_ids:
                    connection.execute(
                        text(
                            "UPDATE wiki_evidence SET entity_id = :keeper_id "
                            "WHERE entity_type = 'character_skill' AND entity_id = :duplicate_id"
                        ),
                        {"keeper_id": keeper_id, "duplicate_id": duplicate_id},
                    )
                    connection.execute(
                        text("DELETE FROM character_skills WHERE id = :duplicate_id"),
                        {"duplicate_id": duplicate_id},
                    )

                connection.execute(
                    text(
                        "UPDATE character_skills "
                        "SET relationship_type = 'has', description = :description, "
                        "admin_notes = :admin_notes, review_status = :review_status "
                        "WHERE id = :keeper_id"
                    ),
                    {
                        "description": merged_description,
                        "admin_notes": merged_admin_notes,
                        "review_status": merged_status,
                        "keeper_id": keeper_id,
                    },
                )

            connection.execute(text("UPDATE character_skills SET relationship_type = 'has'"))
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_character_skill_pair "
                    "ON character_skills (character_id, skill_id)"
                )
            )

        if "current_sect_rank" in character_column_names:
            connection.execute(
                text(
                    "UPDATE characters "
                    "SET current_position = current_sect_rank "
                    "WHERE current_position IS NULL AND current_sect_rank IS NOT NULL"
                )
            )

        progression_columns = connection.execute(
            text("PRAGMA table_info(character_progression_events)")
        ).fetchall()
        progression_column_names = {column[1] for column in progression_columns}

        if "review_warnings" not in progression_column_names:
            connection.execute(
                text("ALTER TABLE character_progression_events ADD COLUMN review_warnings TEXT")
            )

        metadata_proposal_columns = connection.execute(
            text("PRAGMA table_info(character_metadata_proposals)")
        ).fetchall()
        metadata_proposal_column_names = {column[1] for column in metadata_proposal_columns}
        metadata_proposal_summary_columns = {
            "raw_proposed_value": "TEXT",
            "normalized_value": "TEXT",
            "confidence_score": "FLOAT",
            "extraction_reason": "TEXT",
            "auto_approved": "BOOLEAN NOT NULL DEFAULT 0",
        }

        for column_name, column_type in metadata_proposal_summary_columns.items():
            if column_name not in metadata_proposal_column_names:
                connection.execute(
                    text(
                        "ALTER TABLE character_metadata_proposals "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )

        extraction_run_columns = connection.execute(
            text("PRAGMA table_info(extraction_runs)")
        ).fetchall()
        extraction_run_column_names = {column[1] for column in extraction_run_columns}

        if extraction_run_columns and "summary_json" not in extraction_run_column_names:
            connection.execute(text("ALTER TABLE extraction_runs ADD COLUMN summary_json TEXT"))

        extraction_run_chapter_columns = connection.execute(
            text("PRAGMA table_info(extraction_run_chapters)")
        ).fetchall()
        extraction_run_chapter_column_names = {
            column[1] for column in extraction_run_chapter_columns
        }
        extraction_run_chapter_summary_columns = {
            "records_created": "INTEGER NOT NULL DEFAULT 0",
            "warning_count": "INTEGER NOT NULL DEFAULT 0",
            "summary_json": "TEXT",
            "error_message": "TEXT",
            "started_at": "DATETIME",
            "finished_at": "DATETIME",
            "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        }

        for column_name, column_type in extraction_run_chapter_summary_columns.items():
            if extraction_run_chapter_columns and column_name not in extraction_run_chapter_column_names:
                connection.execute(
                    text(
                        "ALTER TABLE extraction_run_chapters "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )

        connection.commit()


def create_app():
    backend_dir = Path(__file__).resolve().parents[1]
    load_dotenv(backend_dir / ".env")

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI="sqlite:///novelwiki.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER="uploads",
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,
    )

    CORS(app)
    db.init_app(app)

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(admin_novels_bp, url_prefix="/api/admin")
    app.register_blueprint(admin_review_bp, url_prefix="/api/admin/review")
    app.register_blueprint(wiki_bp, url_prefix="/api/wiki")

    with app.app_context():
        db.create_all()
        ensure_development_schema(app)

    return app
