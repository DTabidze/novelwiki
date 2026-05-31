import unittest

from flask import Flask

from app.models import Character, CharacterProgressionEvent, Chapter, Novel, db
from app.services.extraction.progression import find_existing_progression


class ProgressionDedupeTest(unittest.TestCase):
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

        self.novel = Novel(
            title="Test Novel",
            original_filename="",
            file_type="txt",
        )
        db.session.add(self.novel)
        db.session.flush()

        self.character = Character(
            novel_id=self.novel.id,
            name="Meng Hao",
            review_status="approved",
        )
        db.session.add(self.character)
        db.session.flush()

        self.chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=71,
            title="Chapter 71",
            content="",
            character_count=0,
        )
        db.session.add(self.chapter)
        db.session.flush()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_rejected_progression_does_not_block_new_proposal(self):
        db.session.add(
            CharacterProgressionEvent(
                novel_id=self.novel.id,
                character_id=self.character.id,
                chapter_id=self.chapter.id,
                progression_type="cultivation_level",
                new_value="ninth level of Qi condensation",
                review_status="rejected",
            )
        )
        db.session.commit()

        self.assertIsNone(
            find_existing_progression(
                self.character,
                "cultivation_level",
                "ninth level of Qi Condensation",
            )
        )

    def test_pending_progression_still_blocks_duplicate_proposal(self):
        pending_progression = CharacterProgressionEvent(
            novel_id=self.novel.id,
            character_id=self.character.id,
            chapter_id=self.chapter.id,
            progression_type="cultivation_level",
            new_value="ninth level of Qi condensation",
            review_status="pending",
        )
        db.session.add(pending_progression)
        db.session.commit()

        self.assertEqual(
            find_existing_progression(
                self.character,
                "cultivation_level",
                "ninth level of Qi Condensation",
            ).id,
            pending_progression.id,
        )


if __name__ == "__main__":
    unittest.main()
