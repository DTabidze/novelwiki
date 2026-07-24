import unittest

from flask import Flask

from app.models import Character, Item, Novel, Skill, db
from app.services.extraction.memory import build_extraction_memory


class ExtractionMemoryTest(unittest.TestCase):
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

        self.novel = Novel(title="Memory Novel", original_filename="", file_type="txt")
        db.session.add(self.novel)
        db.session.flush()
        db.session.add_all(
            [
                Character(
                    novel_id=self.novel.id,
                    name="Arlen Vale",
                    current_cultivation_level="Third Stage",
                ),
                Skill(
                    novel_id=self.novel.id,
                    name="Ember Step",
                    category="technique",
                ),
                Item(
                    novel_id=self.novel.id,
                    name="Glass Compass",
                    category="artifact",
                ),
            ]
        )
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_skill_memory_contains_characters_and_skills_only(self):
        memory = build_extraction_memory(self.novel, stage_name="skill")

        self.assertIn("Known characters:", memory)
        self.assertIn("Arlen Vale", memory)
        self.assertIn("Known skills:", memory)
        self.assertIn("Ember Step", memory)
        self.assertNotIn("Known items:", memory)
        self.assertNotIn("Glass Compass", memory)
        self.assertNotIn("Known progression values:", memory)

    def test_item_memory_contains_characters_and_items_only(self):
        memory = build_extraction_memory(self.novel, stage_name="item")

        self.assertIn("Known characters:", memory)
        self.assertIn("Arlen Vale", memory)
        self.assertIn("Known items:", memory)
        self.assertIn("Glass Compass", memory)
        self.assertNotIn("Known skills:", memory)
        self.assertNotIn("Ember Step", memory)
        self.assertNotIn("Known progression values:", memory)

    def test_progression_memory_contains_current_state_without_other_entities(self):
        memory = build_extraction_memory(self.novel, stage_name="progression")

        self.assertIn("Known characters:", memory)
        self.assertIn("cultivation: Third Stage", memory)
        self.assertIn("Known progression values:", memory)
        self.assertNotIn("Known skills:", memory)
        self.assertNotIn("Known items:", memory)

    def test_unscoped_memory_preserves_legacy_full_memory(self):
        memory = build_extraction_memory(self.novel)

        self.assertIn("Known characters:", memory)
        self.assertIn("Known skills:", memory)
        self.assertIn("Known items:", memory)
        self.assertIn("Known progression values:", memory)


if __name__ == "__main__":
    unittest.main()
