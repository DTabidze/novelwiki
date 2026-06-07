import unittest

from flask import Flask

from app.api.admin_review import admin_review_bp
from app.models import (
    Character,
    CharacterItem,
    CharacterSkill,
    Chapter,
    Item,
    Novel,
    Skill,
    WikiEvidence,
    db,
)


class ReviewItemConversionTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        self.app.register_blueprint(admin_review_bp, url_prefix="/api/admin/review")
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()

        self.novel = Novel(title="Test Novel", original_filename="", file_type="txt")
        db.session.add(self.novel)
        db.session.flush()

        self.chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=141,
            title="Chapter 141: Time Sword",
            content="",
            character_count=0,
        )
        self.character = Character(
            novel_id=self.novel.id,
            name="Meng Hao",
            review_status="approved",
        )
        db.session.add_all([self.chapter, self.character])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def create_pending_skill(self):
        skill = Skill(
            novel_id=self.novel.id,
            name="Time Sword",
            category="Technique",
            description="A sword refined through Time.",
            review_status="pending",
            admin_notes="Needs type correction.",
        )
        db.session.add(skill)
        db.session.flush()
        db.session.add(WikiEvidence(
            novel_id=self.novel.id,
            chapter_id=self.chapter.id,
            entity_type="skill",
            entity_id=skill.id,
            evidence_text="the magical Time Sword",
        ))
        db.session.commit()
        return skill

    def create_pending_item(self):
        item = Item(
            novel_id=self.novel.id,
            name="Time Sword",
            category="Weapon",
            description="A sword refined through Time.",
            review_status="pending",
            admin_notes="Needs type correction.",
        )
        db.session.add(item)
        db.session.flush()
        db.session.add(WikiEvidence(
            novel_id=self.novel.id,
            chapter_id=self.chapter.id,
            entity_type="item",
            entity_id=item.id,
            evidence_text="the magical Time Sword",
        ))
        db.session.commit()
        return item

    def test_converts_skill_proposal_to_item_transactionally(self):
        skill = self.create_pending_skill()

        response = self.client.post(
            f"/api/admin/review/skills/{skill.id}/convert",
            json={
                "target_entity_type": "items",
                "name": "Time Sword",
                "category": "Weapon",
                "description": "A magical sword produced through Time refinement.",
                "admin_notes": "Converted from skill.",
            },
        )

        self.assertEqual(response.status_code, 201)
        body = response.get_json()["data"]
        self.assertEqual(body["entity_type"], "items")
        self.assertEqual(body["review_item"]["name"], "Time Sword")
        self.assertEqual(body["review_item"]["category"], "Weapon")
        self.assertEqual(body["review_item"]["review_status"], "pending")

        self.assertIsNone(db.session.get(Skill, skill.id))

        converted_item = db.session.get(Item, body["review_item"]["id"])
        self.assertIsNotNone(converted_item)
        self.assertEqual(converted_item.description, "A magical sword produced through Time refinement.")

        evidence = WikiEvidence.query.one()
        self.assertEqual(evidence.entity_type, "item")
        self.assertEqual(evidence.entity_id, converted_item.id)
        self.assertEqual(evidence.evidence_text, "the magical Time Sword")

    def test_invalid_conversion_rolls_back_source_and_evidence(self):
        skill = self.create_pending_skill()

        response = self.client.post(
            f"/api/admin/review/skills/{skill.id}/convert",
            json={
                "target_entity_type": "items",
                "name": "Time Sword",
                "category": "Technique",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Item category must be one of the supported categories.")

        self.assertIsNotNone(db.session.get(Skill, skill.id))
        self.assertEqual(Item.query.count(), 0)

        evidence = WikiEvidence.query.one()
        self.assertEqual(evidence.entity_type, "skill")
        self.assertEqual(evidence.entity_id, skill.id)

    def test_converts_pending_item_relationships_to_skill_relationships(self):
        item = self.create_pending_item()
        relationship = CharacterItem(
            novel_id=self.novel.id,
            character_id=self.character.id,
            item_id=item.id,
            chapter_id=self.chapter.id,
            relationship_type="owns",
            description="Meng Hao has the Time Sword.",
            review_status="pending",
        )
        db.session.add(relationship)
        db.session.flush()
        db.session.add(WikiEvidence(
            novel_id=self.novel.id,
            chapter_id=self.chapter.id,
            entity_type="character_item",
            entity_id=relationship.id,
            evidence_text="Meng Hao drew the Time Sword.",
        ))
        db.session.commit()

        response = self.client.post(
            f"/api/admin/review/items/{item.id}/convert",
            json={
                "target_entity_type": "skills",
                "name": "Time Sword",
                "category": "Technique",
                "description": "A technique produced through Time refinement.",
            },
        )

        self.assertEqual(response.status_code, 201)
        converted_skill_id = response.get_json()["data"]["review_item"]["id"]

        self.assertIsNone(db.session.get(Item, item.id))
        self.assertEqual(CharacterItem.query.count(), 0)

        converted_relationship = CharacterSkill.query.one()
        self.assertEqual(converted_relationship.skill_id, converted_skill_id)
        self.assertEqual(converted_relationship.character_id, self.character.id)
        self.assertEqual(converted_relationship.relationship_type, "has")
        self.assertEqual(converted_relationship.description, "Meng Hao has the Time Sword.")

        relationship_evidence = WikiEvidence.query.filter_by(entity_type="character_skill").one()
        self.assertEqual(relationship_evidence.entity_id, converted_relationship.id)
        self.assertEqual(relationship_evidence.evidence_text, "Meng Hao drew the Time Sword.")


if __name__ == "__main__":
    unittest.main()
