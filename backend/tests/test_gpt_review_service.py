import json
import unittest
from unittest.mock import patch

from flask import Flask

from app.models import (
    Character,
    CharacterAlias,
    CharacterItem,
    CharacterLifeEvent,
    CharacterMetadataProposal,
    CharacterProgressionEvent,
    CharacterSkill,
    Chapter,
    Item,
    Novel,
    Skill,
    WikiEvidence,
    db,
)
from app.services.gpt_review_service import (
    GPTReviewDecision,
    GPTReviewResponse,
    GPT_REVIEW_PROMPT,
    apply_gpt_review_decisions,
    build_gpt_review_batch,
    run_gpt_review,
)


class GPTReviewServiceTest(unittest.TestCase):
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

        self.chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=5,
            title="Chapter 5",
            content=(
                "Fatty broke through to the second level.\n\n"
                "Meng Hao watched from the side.\n\n"
                "UNSENT FULL CHAPTER TEXT SHOULD NOT APPEAR."
            ),
            character_count=0,
        )
        self.character = Character(
            novel_id=self.novel.id,
            name="Li Furui",
            review_status="approved",
        )
        db.session.add_all([self.chapter, self.character])
        db.session.flush()
        db.session.add(
            CharacterAlias(
                character_id=self.character.id,
                alias="Fatty",
                first_seen_chapter_id=self.chapter.id,
            )
        )
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def add_progression(self, status="pending", value="second level"):
        progression = CharacterProgressionEvent(
            novel_id=self.novel.id,
            character_id=self.character.id,
            chapter_id=self.chapter.id,
            progression_type="cultivation_level",
            new_value=value,
            description="Li Furui reached the second level.",
            review_status=status,
            confidence_score=80,
            risk_flags=json.dumps(["attribution_uncertain"]),
            source_extractor="progression_reasoning",
        )
        db.session.add(progression)
        db.session.flush()
        db.session.add(
            WikiEvidence(
                novel_id=self.novel.id,
                chapter_id=self.chapter.id,
                entity_type="progression",
                entity_id=progression.id,
                evidence_text="Fatty broke through to the second level.",
            )
        )
        db.session.commit()
        return progression

    def add_metadata(self, status="pending"):
        metadata = CharacterMetadataProposal(
            novel_id=self.novel.id,
            character_id=self.character.id,
            chapter_id=self.chapter.id,
            field_name="faction_or_affiliation",
            old_value=None,
            raw_proposed_value="Reliance Sect",
            proposed_value="Reliance Sect",
            normalized_value="Reliance Sect",
            confidence_score=85,
            evidence="Fatty became a Reliance Sect disciple.",
            review_status=status,
        )
        db.session.add(metadata)
        db.session.commit()
        return metadata

    def add_life_event(self, status="pending"):
        event = CharacterLifeEvent(
            novel_id=self.novel.id,
            character_id=self.character.id,
            chapter_id=self.chapter.id,
            event_type="death",
            description="Li Furui died.",
            reason="Killed in battle.",
            confidence_score=90,
            risk_flags=json.dumps([]),
            source_extractor="life_event",
            review_status=status,
        )
        db.session.add(event)
        db.session.flush()
        db.session.add(
            WikiEvidence(
                novel_id=self.novel.id,
                chapter_id=self.chapter.id,
                entity_type="life_event",
                entity_id=event.id,
                evidence_text="Fatty died in the battle.",
            )
        )
        db.session.commit()
        return event

    def add_skill(self, status="pending", name="Water Arrow Technique"):
        skill = Skill(
            novel_id=self.novel.id,
            name=name,
            category="technique",
            description="A named technique.",
            review_status=status,
            confidence_score=70,
            risk_flags=json.dumps(["evidence_not_exact"]),
            source_extractor="skill",
        )
        db.session.add(skill)
        db.session.flush()
        db.session.add(
            WikiEvidence(
                novel_id=self.novel.id,
                chapter_id=self.chapter.id,
                entity_type="skill",
                entity_id=skill.id,
                evidence_text="Fatty broke through to the second level.",
            )
        )
        db.session.commit()
        return skill

    def add_item(self, status="pending", name="Copper Mirror"):
        item = Item(
            novel_id=self.novel.id,
            name=name,
            category="Artifact",
            description="A named artifact.",
            review_status=status,
            confidence_score=70,
            risk_flags=json.dumps(["relationship_evidence_weak"]),
            source_extractor="item",
        )
        db.session.add(item)
        db.session.flush()
        db.session.add(
            WikiEvidence(
                novel_id=self.novel.id,
                chapter_id=self.chapter.id,
                entity_type="item",
                entity_id=item.id,
                evidence_text="Fatty broke through to the second level.",
            )
        )
        db.session.commit()
        return item

    def add_character_skill(self, skill=None, status="pending"):
        skill = skill or self.add_skill(status="approved")
        relationship = CharacterSkill(
            novel_id=self.novel.id,
            character_id=self.character.id,
            skill_id=skill.id,
            chapter_id=self.chapter.id,
            relationship_type="has",
            description="Li Furui has the technique.",
            review_status=status,
            confidence_score=80,
            risk_flags=json.dumps(["relationship_attribution_uncertain"]),
            source_extractor="character_skill",
        )
        db.session.add(relationship)
        db.session.flush()
        db.session.add(
            WikiEvidence(
                novel_id=self.novel.id,
                chapter_id=self.chapter.id,
                entity_type="character_skill",
                entity_id=relationship.id,
                evidence_text="Fatty broke through to the second level.",
            )
        )
        db.session.commit()
        return relationship

    def add_character_item(self, item=None, status="pending"):
        item = item or self.add_item(status="approved")
        relationship = CharacterItem(
            novel_id=self.novel.id,
            character_id=self.character.id,
            item_id=item.id,
            chapter_id=self.chapter.id,
            relationship_type="used",
            description="Li Furui used the item.",
            review_status=status,
            confidence_score=80,
            risk_flags=json.dumps(["relationship_action_not_proven"]),
            source_extractor="character_item",
        )
        db.session.add(relationship)
        db.session.flush()
        db.session.add(
            WikiEvidence(
                novel_id=self.novel.id,
                chapter_id=self.chapter.id,
                entity_type="character_item",
                entity_id=relationship.id,
                evidence_text="Fatty broke through to the second level.",
            )
        )
        db.session.commit()
        return relationship

    def test_batch_builder_includes_pending_candidates_aliases_and_evidence(self):
        self.add_progression(status="pending")
        self.add_progression(status="approved", value="first level")

        batch = build_gpt_review_batch(self.novel, limit=25, fact_type="progression")

        self.assertEqual(len(batch["candidates"]), 1)
        self.assertEqual(batch["candidates"][0]["candidate_id"].split(":")[0], "progression")
        self.assertEqual(batch["candidates"][0]["evidence"], "Fatty broke through to the second level.")
        self.assertEqual(
            batch["candidates"][0]["local_context"],
            "Fatty broke through to the second level. Meng Hao watched from the side.",
        )
        self.assertNotIn("UNSENT FULL CHAPTER TEXT", json.dumps(batch))
        self.assertEqual(batch["review_context"]["characters"][0]["aliases"], ["Fatty"])

    def test_max_candidate_limit_is_respected(self):
        self.add_progression(value="second level")
        self.add_metadata()
        self.add_life_event()

        batch = build_gpt_review_batch(self.novel, limit=2, fact_type="all")

        self.assertEqual(len(batch["candidates"]), 2)

    def test_all_batch_includes_entity_and_relationship_candidate_types(self):
        self.add_progression(value="second level")
        self.add_metadata()
        self.add_life_event()
        self.add_skill()
        self.add_item()
        self.add_character_skill()
        self.add_character_item()

        pending_character = Character(
            novel_id=self.novel.id,
            name="Named Person",
            description="A pending named character.",
            first_seen_chapter_id=self.chapter.id,
            review_status="pending",
            confidence_score=70,
            risk_flags=json.dumps([]),
            source_extractor="character",
        )
        db.session.add(pending_character)
        db.session.flush()
        db.session.add(
            WikiEvidence(
                novel_id=self.novel.id,
                chapter_id=self.chapter.id,
                entity_type="character",
                entity_id=pending_character.id,
                evidence_text="Fatty broke through to the second level.",
            )
        )
        db.session.commit()

        batch = build_gpt_review_batch(self.novel, limit=25, fact_type="all")
        candidate_types = {candidate["type"] for candidate in batch["candidates"]}

        self.assertEqual(
            candidate_types,
            {
                "character",
                "skill",
                "item",
                "progression",
                "metadata",
                "life_event",
                "character_skill",
                "character_item",
            },
        )
        self.assertIn("items", batch["review_context"]["known_entities"])
        self.assertIn("skills", batch["review_context"]["known_entities"])

    def test_dry_run_does_not_modify_record(self):
        progression = self.add_progression()

        def reviewer(batch, config):
            return GPTReviewResponse(
                decisions=[
                    GPTReviewDecision(
                        candidate_id=f"progression:{progression.id}",
                        decision="approve",
                        confidence=0.95,
                        reason="Alias Fatty directly supports Li Furui.",
                        risk_flags_to_remove=["attribution_uncertain"],
                    )
                ]
            )

        with patch.dict(
            "os.environ",
            {
                "GPT_REVIEW_ENABLED": "true",
                "GPT_REVIEW_MODEL": "test-reviewer",
                "GPT_REVIEW_MAX_CANDIDATES": "25",
                "GPT_REVIEW_DRY_RUN": "true",
            },
        ):
            result = run_gpt_review(self.novel.id, fact_type="progression", reviewer=reviewer)

        db.session.refresh(progression)
        self.assertTrue(result["dry_run"])
        self.assertEqual(progression.review_status, "pending")
        self.assertIsNone(progression.admin_notes)

    def test_approve_decision_updates_progression_and_audit_note(self):
        progression = self.add_progression()
        decisions = [
            GPTReviewDecision(
                candidate_id=f"progression:{progression.id}",
                decision="approve",
                confidence=0.96,
                reason="Evidence uses known alias Fatty and directly states the value.",
                risk_flags_to_remove=["attribution_uncertain"],
            )
        ]

        results = apply_gpt_review_decisions(decisions, dry_run=False, model_name="test-reviewer")

        db.session.refresh(progression)
        self.assertTrue(results[0]["applied"])
        self.assertEqual(progression.review_status, "approved")
        self.assertEqual(json.loads(progression.risk_flags), [])
        self.assertIn("GPT reviewer (test-reviewer)", progression.admin_notes)
        self.assertEqual(progression.last_review_action, "gpt_approve")

    def test_metadata_approve_applies_character_field(self):
        metadata = self.add_metadata()
        decisions = [
            GPTReviewDecision(
                candidate_id=f"metadata:{metadata.id}",
                decision="approve",
                confidence=0.92,
                reason="Evidence directly supports membership.",
            )
        ]

        apply_gpt_review_decisions(decisions, dry_run=False, model_name="test-reviewer")

        db.session.refresh(metadata)
        db.session.refresh(self.character)
        self.assertEqual(metadata.review_status, "approved")
        self.assertEqual(self.character.faction_or_affiliation, "Reliance Sect")

    def test_reject_life_event_sets_rejected_and_note(self):
        event = self.add_life_event()
        decisions = [
            GPTReviewDecision(
                candidate_id=f"life_event:{event.id}",
                decision="reject",
                confidence=0.91,
                reason="Evidence is not clear enough.",
            )
        ]

        apply_gpt_review_decisions(decisions, dry_run=False, model_name="test-reviewer")

        db.session.refresh(event)
        self.assertEqual(event.review_status, "rejected")
        self.assertIn("Evidence is not clear enough.", event.admin_notes)
        self.assertEqual(event.last_review_action, "gpt_reject")

    def test_approve_item_skill_and_relationship_types(self):
        skill = self.add_skill()
        item = self.add_item()
        character_skill = self.add_character_skill(skill=skill)
        character_item = self.add_character_item(item=item)
        decisions = [
            GPTReviewDecision(
                candidate_id=f"skill:{skill.id}",
                decision="approve",
                confidence=0.91,
                reason="Evidence supports the skill.",
                risk_flags_to_remove=["evidence_not_exact"],
            ),
            GPTReviewDecision(
                candidate_id=f"item:{item.id}",
                decision="approve",
                confidence=0.92,
                reason="Evidence supports the item.",
                risk_flags_to_remove=["relationship_evidence_weak"],
            ),
            GPTReviewDecision(
                candidate_id=f"character_skill:{character_skill.id}",
                decision="approve",
                confidence=0.93,
                reason="Evidence supports the character-skill relationship.",
                risk_flags_to_remove=["relationship_attribution_uncertain"],
            ),
            GPTReviewDecision(
                candidate_id=f"character_item:{character_item.id}",
                decision="approve",
                confidence=0.94,
                reason="Evidence supports the character-item relationship.",
                risk_flags_to_remove=["relationship_action_not_proven"],
            ),
        ]

        apply_gpt_review_decisions(decisions, dry_run=False, model_name="test-reviewer")

        for record in (skill, item, character_skill, character_item):
            db.session.refresh(record)
            self.assertEqual(record.review_status, "approved")
            self.assertEqual(json.loads(record.risk_flags), [])
            self.assertEqual(record.last_review_action, "gpt_approve")

    def test_reject_pending_character_type(self):
        character = Character(
            novel_id=self.novel.id,
            name="Old Man",
            description="A generic pending character.",
            first_seen_chapter_id=self.chapter.id,
            review_status="pending",
            confidence_score=50,
            risk_flags=json.dumps([]),
            source_extractor="character",
        )
        db.session.add(character)
        db.session.commit()

        apply_gpt_review_decisions(
            [
                GPTReviewDecision(
                    candidate_id=f"character:{character.id}",
                    decision="reject",
                    confidence=0.9,
                    reason="Generic label is not supported as a durable character.",
                )
            ],
            dry_run=False,
            model_name="test-reviewer",
        )

        db.session.refresh(character)
        self.assertEqual(character.review_status, "rejected")
        self.assertEqual(character.last_review_action, "gpt_reject")

    def test_keep_pending_leaves_status_pending_and_adds_note(self):
        progression = self.add_progression()
        decisions = [
            GPTReviewDecision(
                candidate_id=f"progression:{progression.id}",
                decision="keep_pending",
                confidence=0.55,
                reason="Plausible but not clear enough.",
            )
        ]

        apply_gpt_review_decisions(decisions, dry_run=False, model_name="test-reviewer")

        db.session.refresh(progression)
        self.assertEqual(progression.review_status, "pending")
        self.assertIn("Plausible but not clear enough.", progression.admin_notes)
        self.assertEqual(progression.last_review_action, "gpt_keep_pending")

    def test_invalid_candidate_id_is_ignored_safely(self):
        result = apply_gpt_review_decisions(
            [
                GPTReviewDecision(
                    candidate_id="progression:999",
                    decision="approve",
                    confidence=0.9,
                    reason="Looks good.",
                )
            ],
            dry_run=False,
            model_name="test-reviewer",
        )

        self.assertFalse(result[0]["applied"])
        self.assertEqual(result[0]["reason"], "candidate_not_found")

    def test_reviewer_prompt_forbids_extraction_and_correction(self):
        prompt = GPT_REVIEW_PROMPT.lower()

        self.assertIn("you only recommend", prompt)
        self.assertIn("evaluate only the supplied candidate fact", prompt)
        self.assertIn("never create, modify, merge, repair, substitute, or extract facts", prompt)
        self.assertIn("reject it. do not correct it", prompt)
        self.assertIn("complete universe of information", prompt)
        self.assertIn("return only valid json", prompt)


if __name__ == "__main__":
    unittest.main()
