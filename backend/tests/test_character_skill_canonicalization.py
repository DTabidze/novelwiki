import unittest
from types import SimpleNamespace

from flask import Flask

from app.models import Character, CharacterSkill, Chapter, Novel, Skill, db
from app.services.ai_extraction_service import save_chapter_extraction


class CharacterSkillCanonicalizationTest(unittest.TestCase):
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

        self.novel = Novel(title="Test Novel", original_filename="", file_type="txt")
        db.session.add(self.novel)
        db.session.flush()

        self.earlier_chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=5,
            title="Chapter 5",
            content="",
            character_count=0,
        )
        self.later_chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=8,
            title="Chapter 8",
            content="",
            character_count=0,
        )
        self.character = Character(
            novel_id=self.novel.id,
            name="Meng Hao",
            review_status="approved",
        )
        self.skill = Skill(
            novel_id=self.novel.id,
            name="Flame Serpent Art",
            category="technique",
            review_status="approved",
        )
        db.session.add_all([
            self.earlier_chapter,
            self.later_chapter,
            self.character,
            self.skill,
        ])
        db.session.flush()

        self.relationship = CharacterSkill(
            novel_id=self.novel.id,
            character_id=self.character.id,
            skill_id=self.skill.id,
            chapter_id=self.later_chapter.id,
            relationship_type="learns",
            review_status="approved",
        )
        db.session.add(self.relationship)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_extraction_reuses_pair_and_keeps_earliest_chapter(self):
        extraction = SimpleNamespace(
            characters=[],
            skills=[],
            items=[],
            events=[],
            progression_events=[],
            life_events=[],
            character_skills=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    skill_name="Flame Serpent Art",
                    relationship_type="uses",
                    description="Meng Hao uses the Flame Serpent Art.",
                    evidence="Meng Hao unleashed the Flame Serpent Art.",
                )
            ],
        )

        summary = save_chapter_extraction(self.novel, self.earlier_chapter, extraction)
        db.session.flush()

        self.assertEqual(CharacterSkill.query.count(), 1)
        self.assertEqual(self.relationship.relationship_type, "has")
        self.assertEqual(self.relationship.chapter_id, self.earlier_chapter.id)
        self.assertEqual(summary["character_skills_created"], 0)


if __name__ == "__main__":
    unittest.main()
