import unittest
from datetime import timedelta

from flask import Flask
from sqlalchemy.exc import IntegrityError

from app.api.admin_review import admin_review_bp
from app.models import (
    Character,
    CharacterAlias,
    CharacterProgressionEvent,
    CharacterSkill,
    Chapter,
    Item,
    Novel,
    Skill,
    SkillAlias,
    WikiEditLog,
    db,
    utc_now,
)


class WikiDataEditorValidationTest(unittest.TestCase):
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
        self.other_novel = Novel(title="Other Novel", original_filename="", file_type="txt")
        db.session.add_all([self.novel, self.other_novel])
        db.session.flush()

        self.chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=1,
            title="Chapter 1",
            content="",
            character_count=0,
        )
        self.other_chapter = Chapter(
            novel_id=self.other_novel.id,
            chapter_number=1,
            title="Other Chapter 1",
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
            name="Blood Mastiff Art",
            review_status="approved",
        )
        self.other_skill = Skill(
            novel_id=self.novel.id,
            name="Violet Qi Art",
            review_status="approved",
        )
        self.item = Item(
            novel_id=self.novel.id,
            name="Copper Mirror",
            review_status="approved",
        )
        self.other_item = Item(
            novel_id=self.novel.id,
            name="Blood Mask",
            review_status="approved",
        )
        db.session.add_all([
            self.chapter,
            self.other_chapter,
            self.character,
            self.skill,
            self.other_skill,
            self.item,
            self.other_item,
        ])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def patch_character(self, payload):
        return self.client.patch(
            f"/api/admin/review/wiki-data/characters/{self.character.id}",
            json=payload,
        )

    def patch_skill(self, payload):
        return self.client.patch(
            f"/api/admin/review/wiki-data/skills/{self.skill.id}",
            json=payload,
        )

    def patch_item(self, payload):
        return self.client.patch(
            f"/api/admin/review/wiki-data/items/{self.item.id}",
            json=payload,
        )

    def assert_validation_error(self, response, expected_message):
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], expected_message)

    def test_requires_json_object_and_array_payloads(self):
        response = self.client.patch(
            f"/api/admin/review/wiki-data/characters/{self.character.id}",
            json=[],
        )
        self.assert_validation_error(response, "Request body must be a JSON object.")

        response = self.patch_character({"aliases": {}})
        self.assert_validation_error(response, "Aliases must be an array.")

        response = self.patch_character({"skill_relationships": ["not-an-object"]})
        self.assert_validation_error(
            response,
            "Every Skill relationships entry must be an object.",
        )

    def test_rejects_invalid_numeric_ids(self):
        response = self.patch_character({"first_mentioned_chapter_id": "abc"})
        self.assert_validation_error(response, "IDs must be positive integers.")

    def test_rejects_invalid_text_and_boolean_values(self):
        response = self.patch_character({"description": {"unexpected": "object"}})
        self.assert_validation_error(response, "Character description must be text.")

        response = self.patch_character({
            "aliases": [{
                "alias": "Brother Meng",
                "first_seen_chapter_id": self.chapter.id,
                "is_primary": "false",
            }],
        })
        self.assert_validation_error(response, "Primary alias flag must be true or false.")

        response = self.patch_character({
            "aliases": [{
                "alias": "Brother Meng",
                "first_seen_chapter_id": "abc",
            }],
        })
        self.assert_validation_error(response, "IDs must be positive integers.")

    def test_alias_requires_chapter_and_rejects_duplicates(self):
        response = self.patch_character({"aliases": [{"alias": "Brother Meng"}]})
        self.assert_validation_error(response, "Alias first mentioned chapter is required.")

        response = self.patch_character({
            "aliases": [
                {"alias": "Brother Meng", "first_seen_chapter_id": self.chapter.id},
                {"alias": "brother meng", "first_seen_chapter_id": self.chapter.id},
            ],
        })
        self.assert_validation_error(response, "This character already has this alias.")

    def test_patch_character_creates_wiki_edit_log(self):
        response = self.patch_character({"status": "dead"})

        self.assertEqual(response.status_code, 200)

        logs = WikiEditLog.query.filter_by(novel_id=self.novel.id).all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].entity_type, "character")
        self.assertEqual(logs[0].change_type, "updated")
        self.assertEqual(logs[0].field_name, "Status")
        self.assertEqual(logs[0].old_value(), "unknown")
        self.assertEqual(logs[0].new_value(), "dead")

        response = self.client.get(
            f"/api/admin/review/wiki-data/novels/{self.novel.id}/edit-log"
        )
        payload = response.get_json()["data"]
        self.assertEqual(payload["pagination"]["total"], 1)
        self.assertEqual(payload["logs"][0]["field_name"], "Status")

        self.assertEqual(CharacterAlias.query.count(), 0)

    def test_patch_character_aliases_create_added_edit_log(self):
        response = self.patch_character({
            "aliases": [{
                "alias": "Hao-ge",
                "first_seen_chapter_id": self.chapter.id,
            }],
        })

        self.assertEqual(response.status_code, 200)
        log = WikiEditLog.query.filter_by(entity_type="alias").one()
        self.assertEqual(log.change_type, "added")
        self.assertEqual(log.entity_label, "Meng Hao")
        self.assertEqual(log.field_name, "Alias")
        self.assertEqual(log.new_value(), "Hao-ge")

        response = self.client.get(
            f"/api/admin/review/wiki-data/novels/{self.novel.id}/edit-log"
        )
        self.assertEqual(response.get_json()["data"]["logs"][0]["parent_entity_label"], "Meng Hao")

    def test_patch_skill_aliases_create_added_edit_log(self):
        response = self.patch_skill({
            "aliases": [{
                "alias": "Blood Art",
                "first_seen_chapter_id": self.chapter.id,
            }],
        })

        self.assertEqual(response.status_code, 200)
        log = WikiEditLog.query.filter_by(entity_type="skill_alias").one()
        self.assertEqual(log.change_type, "added")
        self.assertEqual(log.entity_label, "Blood Mastiff Art")
        self.assertEqual(log.field_name, "Alias")
        self.assertEqual(log.new_value(), "Blood Art")

    def test_cultivation_update_log_uses_character_label(self):
        event = CharacterProgressionEvent(
            novel_id=self.novel.id,
            character_id=self.character.id,
            chapter_id=self.chapter.id,
            progression_type="cultivation_level",
            new_value="2nd lvl",
            review_status="approved",
        )
        db.session.add(event)
        db.session.commit()

        response = self.patch_character({
            "cultivation_events": [{
                "id": event.id,
                "cultivation_level": "2nd level of Qi Condensation",
                "chapter_id": self.chapter.id,
            }],
        })

        self.assertEqual(response.status_code, 200)
        log = WikiEditLog.query.filter_by(entity_type="cultivation").one()
        self.assertEqual(log.change_type, "updated")
        self.assertEqual(log.entity_label, "Meng Hao")
        self.assertEqual(log.field_name, "Cultivation Level")
        self.assertEqual(log.old_value(), "2nd lvl")
        self.assertEqual(log.new_value(), "2nd level of Qi Condensation")

    def test_edit_log_date_filter_matches_recent_rows(self):
        old_log = WikiEditLog(
            novel_id=self.novel.id,
            entity_type="character",
            entity_id=self.character.id,
            entity_label=self.character.name,
            change_type="updated",
            field_name="Status",
            old_value_json='"alive"',
            new_value_json='"dead"',
            created_at=utc_now() - timedelta(days=20),
        )
        recent_log = WikiEditLog(
            novel_id=self.novel.id,
            entity_type="character",
            entity_id=self.character.id,
            entity_label=self.character.name,
            change_type="updated",
            field_name="Gender",
            old_value_json='"unknown"',
            new_value_json='"Male"',
            created_at=utc_now(),
        )
        db.session.add_all([old_log, recent_log])
        db.session.commit()

        today = utc_now().date().isoformat()
        response = self.client.get(
            f"/api/admin/review/wiki-data/novels/{self.novel.id}/edit-log"
            f"?date_from={today}&date_to={today}"
        )
        payload = response.get_json()["data"]
        self.assertEqual(payload["pagination"]["total"], 1)
        self.assertEqual(payload["logs"][0]["field_name"], "Gender")

    def test_rejects_multiple_primary_aliases(self):
        response = self.patch_character({
            "aliases": [
                {
                    "alias": "Brother Meng",
                    "first_seen_chapter_id": self.chapter.id,
                    "is_primary": True,
                },
                {
                    "alias": "Meng-ge",
                    "first_seen_chapter_id": self.chapter.id,
                    "is_primary": True,
                },
            ],
        })
        self.assert_validation_error(response, "A character can only have one primary alias.")

    def test_cultivation_validation_happens_before_insert(self):
        response = self.patch_character({
            "cultivation_events": [{
                "cultivation_level": "",
                "chapter_id": self.chapter.id,
            }],
        })
        self.assert_validation_error(response, "Cultivation level is required.")
        self.assertEqual(CharacterProgressionEvent.query.count(), 0)

        response = self.patch_character({
            "cultivation_events": [{
                "cultivation_level": "Foundation Establishment",
                "chapter_id": self.other_chapter.id,
            }],
        })
        self.assert_validation_error(
            response,
            "Cultivation chapter reference must belong to this novel.",
        )
        self.assertEqual(CharacterProgressionEvent.query.count(), 0)

    def test_new_skill_relationship_is_canonicalized_to_has(self):
        response = self.patch_character({
            "skill_relationships": [{
                "skill_id": self.skill.id,
                "chapter_id": self.chapter.id,
            }],
        })
        self.assertEqual(response.status_code, 200)
        relationship = CharacterSkill.query.one()
        self.assertEqual(relationship.relationship_type, "has")

    def test_duplicate_skill_relationship_returns_validation_error(self):
        existing_relationship = CharacterSkill(
            novel_id=self.novel.id,
            character_id=self.character.id,
            skill_id=self.skill.id,
            chapter_id=self.chapter.id,
            relationship_type="uses",
            review_status="approved",
        )
        db.session.add(existing_relationship)
        db.session.commit()

        response = self.patch_character({
            "skill_relationships": [
                {
                    "id": existing_relationship.id,
                    "skill_id": self.other_skill.id,
                    "chapter_id": self.chapter.id,
                },
                {
                    "skill_id": self.other_skill.id,
                    "chapter_id": self.chapter.id,
                },
            ],
        })
        self.assert_validation_error(
            response,
            "This skill is already attached to this character.",
        )
        db.session.refresh(existing_relationship)
        self.assertEqual(existing_relationship.skill_id, self.skill.id)

    def test_same_skill_with_different_relationship_type_is_still_duplicate(self):
        existing_relationship = CharacterSkill(
            novel_id=self.novel.id,
            character_id=self.character.id,
            skill_id=self.skill.id,
            chapter_id=self.chapter.id,
            relationship_type="learns",
            review_status="approved",
        )
        db.session.add(existing_relationship)
        db.session.commit()

        response = self.patch_character({
            "skill_relationships": [
                {
                    "id": existing_relationship.id,
                    "skill_id": self.skill.id,
                    "chapter_id": self.chapter.id,
                },
                {
                    "skill_id": self.skill.id,
                    "chapter_id": self.chapter.id,
                },
            ],
        })
        self.assert_validation_error(
            response,
            "This skill is already attached to this character.",
        )

    def test_database_rejects_duplicate_character_skill_pair(self):
        db.session.add_all([
            CharacterSkill(
                novel_id=self.novel.id,
                character_id=self.character.id,
                skill_id=self.skill.id,
                chapter_id=self.chapter.id,
                relationship_type="has",
                review_status="approved",
            ),
            CharacterSkill(
                novel_id=self.novel.id,
                character_id=self.character.id,
                skill_id=self.skill.id,
                chapter_id=self.chapter.id,
                relationship_type="legacy_action",
                review_status="pending",
            ),
        ])

        with self.assertRaises(IntegrityError):
            db.session.commit()

        db.session.rollback()

    def test_skill_editor_requires_name_and_valid_payload_shapes(self):
        response = self.patch_skill({"name": ""})
        self.assert_validation_error(response, "Skill name is required.")

        response = self.patch_skill({"aliases": {}})
        self.assert_validation_error(response, "Skill aliases must be an array.")

        response = self.patch_skill({"description": {"invalid": True}})
        self.assert_validation_error(response, "Skill description must be text.")

    def test_skill_editor_rejects_duplicate_canonical_name(self):
        response = self.patch_skill({"name": self.other_skill.name.lower()})
        self.assert_validation_error(response, "A canonical skill with this name already exists.")

    def test_skill_category_is_normalized_and_restricted(self):
        response = self.patch_skill({"category": " technique "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(db.session.get(Skill, self.skill.id).category, "Technique")

        response = self.patch_skill({"category": "secret custom category"})
        self.assert_validation_error(
            response,
            "Skill category must be one of the supported categories.",
        )

    def test_skill_alias_requires_chapter_and_rejects_duplicates(self):
        response = self.patch_skill({"aliases": [{"alias": "Flame Art"}]})
        self.assert_validation_error(response, "Skill alias first mentioned chapter is required.")

        response = self.patch_skill({
            "aliases": [
                {"alias": "Flame Art", "first_seen_chapter_id": self.chapter.id},
                {"alias": "flame art", "first_seen_chapter_id": self.chapter.id},
            ],
        })
        self.assert_validation_error(response, "This skill already has this alias.")
        self.assertEqual(SkillAlias.query.count(), 0)

    def test_skill_alias_chapter_must_belong_to_skill_novel(self):
        response = self.patch_skill({
            "aliases": [{
                "alias": "Flame Art",
                "first_seen_chapter_id": self.other_chapter.id,
            }],
        })
        self.assert_validation_error(response, "Skill alias chapter reference must belong to this novel.")

    def test_skill_editor_updates_basic_info_aliases_and_notes(self):
        response = self.patch_skill({
            "name": "Flame Serpent Technique",
            "category": "Combat Move",
            "description": "Creates a serpent of flame.",
            "admin_notes": "Canonicalized by editor.",
            "aliases": [{
                "alias": "Flame Snake Art",
                "first_seen_chapter_id": self.chapter.id,
                "evidence": "A flame snake appeared.",
            }],
        })

        self.assertEqual(response.status_code, 200)
        db.session.refresh(self.skill)
        self.assertEqual(self.skill.name, "Flame Serpent Technique")
        self.assertEqual(self.skill.admin_notes, "Canonicalized by editor.")
        alias = SkillAlias.query.one()
        self.assertEqual(alias.alias, "Flame Snake Art")
        self.assertEqual(alias.first_seen_chapter_id, self.chapter.id)

    def test_item_category_is_normalized_and_restricted(self):
        response = self.patch_item({"category": " quest_item "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(db.session.get(Item, self.item.id).category, "Quest Item")

        response = self.patch_item({"category": "secret custom category"})
        self.assert_validation_error(
            response,
            "Item category must be one of the supported categories.",
        )

    def test_item_character_relationship_rejects_duplicates(self):
        response = self.patch_item({
            "character_relationships": [
                {
                    "character_id": self.character.id,
                    "chapter_id": self.chapter.id,
                },
                {
                    "character_id": self.character.id,
                    "chapter_id": self.chapter.id,
                },
            ],
        })
        self.assert_validation_error(
            response,
            "This character is already attached to this item.",
        )

    def test_character_item_relationship_requires_item_and_chapter(self):
        response = self.patch_character({
            "item_relationships": [{
                "item_id": self.item.id,
            }],
        })
        self.assert_validation_error(response, "Item chapter is required.")

        response = self.patch_character({
            "item_relationships": [{
                "item_id": self.item.id,
                "chapter_id": self.other_chapter.id,
            }],
        })
        self.assert_validation_error(response, "Item chapter reference must belong to this novel.")


if __name__ == "__main__":
    unittest.main()
