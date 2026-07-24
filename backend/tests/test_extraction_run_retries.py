import unittest
from unittest.mock import patch

from flask import Flask

from app.api.admin_novels import run_extraction_scope
from app.models import (
    Book,
    Chapter,
    ExtractionRun,
    ExtractionRunChapter,
    Novel,
    db,
)


class ExtractionRunRetryTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        self.novel = Novel(title="Run Novel", original_filename="", file_type="txt")
        db.session.add(self.novel)
        db.session.flush()
        self.book = Book(
            novel_id=self.novel.id,
            number=1,
            title="Book 1",
        )
        db.session.add(self.book)
        db.session.flush()
        self.chapter = Chapter(
            novel_id=self.novel.id,
            book_id=self.book.id,
            chapter_number=1,
            title="Chapter 1",
            content="A quiet chapter.",
            character_count=0,
        )
        db.session.add(self.chapter)
        db.session.flush()
        self.run = ExtractionRun(
            novel_id=self.novel.id,
            book_id=self.book.id,
            chapter_start=1,
            chapter_end=1,
            scope_type="chapter_range",
            status="queued",
            total_chapters=1,
        )
        db.session.add(self.run)
        db.session.flush()
        db.session.add(
            ExtractionRunChapter(
                extraction_run_id=self.run.id,
                chapter_id=self.chapter.id,
                status="pending",
            )
        )
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_failed_extraction_is_not_retried_at_whole_chapter_level(self):
        with patch(
            "app.api.admin_novels.extract_chapter_with_ai",
            side_effect=RuntimeError("stage exhausted"),
        ) as extract:
            with self.assertRaisesRegex(RuntimeError, "stage exhausted"):
                run_extraction_scope(self.novel, self.run)

        self.assertEqual(extract.call_count, 1)
        run_chapter = ExtractionRunChapter.query.one()
        self.assertEqual(run_chapter.status, "failed")
        self.assertIn("stage exhausted", run_chapter.error_message)


if __name__ == "__main__":
    unittest.main()
