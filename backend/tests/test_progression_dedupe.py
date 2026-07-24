import unittest

from flask import Flask

from app.models import Character, CharacterProgressionEvent, Chapter, Novel, db
from app.services.extraction.progression import (
    find_existing_progression,
    progression_compare_key,
    progression_keys_match,
    progression_values_match,
)


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

    def test_pending_progression_does_not_block_confirmed_later_proposal(self):
        db.session.add(
            CharacterProgressionEvent(
                novel_id=self.novel.id,
                character_id=self.character.id,
                chapter_id=self.chapter.id,
                progression_type="cultivation_level",
                new_value="ninth level of Qi condensation",
                review_status="pending",
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

    def test_approved_progression_blocks_duplicate_proposal(self):
        approved_progression = CharacterProgressionEvent(
            novel_id=self.novel.id,
            character_id=self.character.id,
            chapter_id=self.chapter.id,
            progression_type="cultivation_level",
            new_value="ninth level of Qi condensation",
            review_status="approved",
        )
        db.session.add(approved_progression)
        db.session.commit()

        self.assertEqual(
            find_existing_progression(
                self.character,
                "cultivation_level",
                "ninth level of Qi Condensation",
            ).id,
            approved_progression.id,
        )

    def test_article_variation_matches_same_progression_state(self):
        self.assertTrue(
            progression_values_match(
                "cultivation_level",
                "peak of second level",
                "peak of the second level",
            )
        )

    def test_ordinal_and_numeric_level_variants_match(self):
        self.assertTrue(
            progression_values_match(
                "power_rank",
                "Level 2",
                "second level",
            )
        )

    def test_realm_present_and_omitted_match_when_unique(self):
        approved_progression = CharacterProgressionEvent(
            novel_id=self.novel.id,
            character_id=self.character.id,
            chapter_id=self.chapter.id,
            progression_type="cultivation_level",
            new_value="peak of the second level of Azure Realm",
            review_status="approved",
        )
        db.session.add(approved_progression)
        db.session.commit()

        self.assertEqual(
            find_existing_progression(
                self.character,
                "cultivation_level",
                "peak second level",
            ).id,
            approved_progression.id,
        )

    def test_ambiguous_omitted_realm_does_not_match_existing_progression(self):
        db.session.add_all(
            [
                CharacterProgressionEvent(
                    novel_id=self.novel.id,
                    character_id=self.character.id,
                    chapter_id=self.chapter.id,
                    progression_type="cultivation_level",
                    new_value="second level of Azure Realm",
                    review_status="approved",
                ),
                CharacterProgressionEvent(
                    novel_id=self.novel.id,
                    character_id=self.character.id,
                    chapter_id=self.chapter.id,
                    progression_type="cultivation_level",
                    new_value="second level of Crimson Path",
                    review_status="approved",
                ),
            ]
        )
        db.session.commit()

        self.assertIsNone(
            find_existing_progression(
                self.character,
                "cultivation_level",
                "second level",
            )
        )

    def test_peak_and_plain_level_do_not_match(self):
        self.assertFalse(
            progression_values_match(
                "cultivation_level",
                "second level",
                "peak second level",
            )
        )

    def test_near_breakthrough_and_peak_state_do_not_match(self):
        self.assertFalse(
            progression_values_match(
                "cultivation_level",
                "almost third level",
                "peak second level",
            )
        )

    def test_different_progression_dimensions_do_not_match(self):
        self.assertFalse(
            progression_keys_match(
                progression_compare_key("cultivation_level", "second level"),
                progression_compare_key("position", "second level"),
            )
        )


if __name__ == "__main__":
    unittest.main()
