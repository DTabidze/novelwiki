import unittest
from types import SimpleNamespace

from flask import Flask

from app.models import (
    AIEvidenceAudit,
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
from app.services.ai_extraction_service import (
    add_evidence,
    revalidate_fact,
    save_chapter_extraction,
    trace_fact_validation,
    validate_item_entity_from_relationship,
)
from app.services.extraction.memory import build_extraction_memory
from app.services.extraction.progression import (
    detect_direct_cultivation_progression,
    progression_candidate_variants,
    recalculate_character_current_progression,
)
from app.services.extraction.validation import (
    ValidationContext,
    ValidationResult,
    set_validation_metadata,
    validate_extracted_fact,
)
from app.services.extraction.evidence import (
    get_evidence_context,
    locate_evidence_text,
    recover_fact_evidence,
    verify_evidence_text,
)
from app.services.extraction.attribution import resolve_character_attribution
from app.services.extraction.metadata import (
    create_character_metadata_proposals,
    metadata_warnings_block_auto_approval,
)
from app.api.wiki import current_values_from_progression, evidence_for
from app.services.wiki_admin_responses import admin_review_response


class ExtractionPipelineValidationTest(unittest.TestCase):
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
            chapter_number=10,
            title="Chapter 10",
            content="\n".join(
                [
                    "Meng Hao reached the third level of Qi Condensation.",
                    "Meng Hao appears in the chapter.",
                    "Founder Reliance was mentioned in the chapter.",
                    "Meng Hao obtained a Spirit Condensing Pill.",
                    "Meng Hao obtained the Copper Mirror.",
                    "Meng Hao raised the Blood Demon Banner.",
                    "Meng Hao obtained a Flying Sword.",
                    "The mirror was said to be a treasure.",
                    "Meng Hao picked up the mirror and carried it away.",
                    "Meng Hao used the Wind Blade Technique.",
                    "Meng Hao used Water Arrows, which shot toward his enemy.",
                    "She entered Foundation Establishment.",
                    "She learned the Foundation Establishment method.",
                    "Meng Hao used the Flame Serpent Art in battle.",
                    "Meng Hao found the Flame Serpent Art manual in the library.",
                    "Meng Hao obtained a Copper Mirror.",
                    "Meng Hao handed the Jade Slip to Elder Xu.",
                    "Meng Hao swallowed the Dry Spirit Pill.",
                    "Meng Hao had the Copper Mirror in his bag.",
                    "Zhao Wugang's dead eyes still shone with horror.",
                    "Zhao Wugang was killed during the battle.",
                    "Zhao Wugang's body was lifeless on the ground.",
                    '"He died," said the young man. "Big Bro Youcai was knocked off a cliff."',
                    "Zhao Wugang died. He was probably eaten by wild animals.",
                    "Meng Hao broke through to the second level of Qi Condensation.",
                    "Meng Hao's Spirit Teeth had become treasures. If he keeps training, they will transform into true treasures.",
                    "A shrewd-looking man appeared in the chapter.",
                ]
            ),
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

    def empty_extraction(self, **overrides):
        data = {
            "characters": [],
            "skills": [],
            "items": [],
            "events": [],
            "progression_events": [],
            "life_events": [],
            "character_skills": [],
            "character_items": [],
        }
        data.update(overrides)
        return SimpleNamespace(**data)

    def metadata_ns(self, **overrides):
        data = {
            "age_text": None,
            "gender": None,
            "race_or_species": None,
            "origin": None,
            "faction_or_affiliation": None,
            "status": None,
            "titles": [],
        }
        data.update(overrides)
        return SimpleNamespace(**data)

    def set_chapter_content(self, content):
        self.chapter.content = content
        db.session.commit()

    def test_evidence_verification_exact_evidence_verifies(self):
        verification = verify_evidence_text(
            "Meng Hao reached the third level of Qi Condensation.",
            "Meng Hao reached the third level of Qi Condensation.",
        )

        self.assertTrue(verification.verified)
        self.assertEqual(verification.evidence_text, "Meng Hao reached the third level of Qi Condensation.")
        self.assertEqual(verification.match_type, "exact")

    def test_evidence_verification_missing_evidence_does_not_verify(self):
        verification = verify_evidence_text("Meng Hao appeared.", "")

        self.assertFalse(verification.verified)

    def test_evidence_verification_paraphrase_does_not_verify(self):
        verification = verify_evidence_text(
            "Meng Hao reached the third level of Qi Condensation.",
            "Meng Hao advanced to the third level of Qi Condensation.",
        )

        self.assertFalse(verification.verified)

    def test_evidence_verification_changed_wording_does_not_verify(self):
        verification = verify_evidence_text(
            "Meng Hao swallowed the pill.",
            "Meng Hao consumed the pill.",
        )

        self.assertFalse(verification.verified)

    def test_evidence_verification_whitespace_difference_can_verify(self):
        verification = verify_evidence_text(
            "Meng Hao reached the third level\nof Qi Condensation.",
            "Meng Hao reached the third level of Qi Condensation.",
        )

        self.assertTrue(verification.verified)
        self.assertEqual(verification.evidence_text, "Meng Hao reached the third level\nof Qi Condensation.")
        self.assertEqual(verification.match_type, "whitespace_normalized")

    def test_evidence_verification_quote_difference_can_verify(self):
        verification = verify_evidence_text(
            "Meng Hao shouted, “The third level!”",
            'Meng Hao shouted, "The third level!"',
        )

        self.assertTrue(verification.verified)
        self.assertEqual(verification.evidence_text, "Meng Hao shouted, “The third level!”")
        self.assertEqual(verification.match_type, "quote_normalized")

    def test_evidence_verification_curly_apostrophe_difference_can_verify(self):
        verification = verify_evidence_text(
            "Meng Hao’s eyes shone.",
            "Meng Hao's eyes shone.",
        )

        self.assertTrue(verification.verified)
        self.assertEqual(verification.evidence_text, "Meng Hao’s eyes shone.")
        self.assertEqual(verification.match_type, "quote_normalized")

    def test_evidence_verification_non_breaking_space_can_verify(self):
        verification = verify_evidence_text(
            "Meng Hao reached the third\u00a0level.",
            "Meng Hao reached the third level.",
        )

        self.assertTrue(verification.verified)
        self.assertEqual(verification.evidence_text, "Meng Hao reached the third\u00a0level.")
        self.assertEqual(verification.match_type, "whitespace_normalized")

    def test_evidence_verification_dash_difference_can_verify(self):
        verification = verify_evidence_text(
            "The sword-light flashed—then vanished.",
            "The sword-light flashed-then vanished.",
        )

        self.assertTrue(verification.verified)
        self.assertEqual(verification.evidence_text, "The sword-light flashed—then vanished.")
        self.assertEqual(verification.match_type, "dash_normalized")

    def test_evidence_verification_surrounding_quote_difference_can_verify(self):
        verification = verify_evidence_text(
            "Meng Hao shouted, The third level!",
            '"The third level!"',
        )

        self.assertTrue(verification.verified)
        self.assertEqual(verification.evidence_text, "The third level!")
        self.assertEqual(verification.match_type, "quote_normalized")

    def test_evidence_verification_quote_boundary_difference_can_verify(self):
        chapter_text = "“Wang Youcai?” Meng Hao’s eyes grew wide."
        verification = verify_evidence_text(
            chapter_text,
            "Wang Youcai? Meng Hao's eyes grew wide.",
        )

        self.assertTrue(verification.verified)
        self.assertEqual(verification.match_type, "quote_boundary_normalized")
        self.assertEqual(
            verification.evidence_text,
            "Wang Youcai?” Meng Hao’s eyes grew wide.",
        )
        self.assertEqual(
            chapter_text[verification.start_offset:verification.end_offset],
            verification.evidence_text,
        )

    def test_evidence_verification_missing_words_do_not_match(self):
        verification = verify_evidence_text(
            "Meng Hao reached the third level of Qi Condensation.",
            "Meng Hao reached Qi Condensation.",
        )

        self.assertFalse(verification.verified)

    def test_evidence_verification_changed_alias_does_not_match(self):
        verification = verify_evidence_text(
            "Fatty broke through to the second level.",
            "Li Furui broke through to the second level.",
        )

        self.assertFalse(verification.verified)

    def test_evidence_recovery_finds_unique_proper_name_sentence(self):
        recovery = recover_fact_evidence(
            "Wang Youcai turned toward the doorway.",
            "character",
            {"name": "Wang Youcai", "evidence": "He turned toward the doorway."},
        )

        self.assertTrue(recovery.recovered)
        self.assertEqual(recovery.evidence_text, "Wang Youcai turned toward the doorway.")
        self.assertEqual(recovery.recovery_method, "exact_character_reference")

    def test_evidence_recovery_uses_token_safe_name_matching(self):
        recovery = recover_fact_evidence(
            "The State of Zhao was far away.",
            "character",
            {"name": "Hao", "evidence": ""},
        )

        self.assertFalse(recovery.recovered)

    def test_evidence_recovery_uses_first_repeated_full_name_character_mention(self):
        recovery = recover_fact_evidence(
            "Wang Youcai entered. Wang Youcai bowed.",
            "character",
            {"name": "Wang Youcai", "evidence": ""},
        )

        self.assertTrue(recovery.recovered)
        self.assertEqual(recovery.evidence_text, "Wang Youcai entered.")
        self.assertEqual(recovery.recovery_method, "exact_character_reference")

    def test_progression_recovery_requires_candidate_value_not_different_source_value(self):
        recovery = recover_fact_evidence(
            "Meng Hao reached the fifth level.",
            "progression",
            {
                "character_name": "Meng Hao",
                "new_value": "sixth level",
                "evidence": "Meng Hao reached the sixth level.",
            },
            aliases=["Meng Hao"],
        )

        self.assertFalse(recovery.recovered)

    def test_progression_recovery_rejects_near_breakthrough_as_achieved(self):
        recovery = recover_fact_evidence(
            "Meng Hao was close to the third level.",
            "progression",
            {
                "character_name": "Meng Hao",
                "new_value": "third level",
                "evidence": "Meng Hao reached the third level.",
            },
            aliases=["Meng Hao"],
        )

        self.assertFalse(recovery.recovered)

    def test_metadata_age_recovery_preserves_raw_written_age_sentence(self):
        recovery = recover_fact_evidence(
            "Meng Hao looked to be about thirty years old.",
            "metadata",
            {
                "field_name": "age_text",
                "value": "about 30 years old",
                "character_name": "Meng Hao",
                "evidence": "Meng Hao was about 30 years old.",
            },
            aliases=["Meng Hao"],
        )

        self.assertTrue(recovery.recovered)
        self.assertEqual(recovery.evidence_text, "Meng Hao looked to be about thirty years old.")

    def test_life_event_recovery_supports_unique_local_pronoun_death(self):
        recovery = recover_fact_evidence(
            'The others asked, "What happened to Wang Youcai?" "He died."',
            "life_event",
            {
                "character_name": "Wang Youcai",
                "event_type": "death",
                "evidence": "Wang Youcai died.",
            },
            aliases=["Wang Youcai"],
        )

        self.assertTrue(recovery.recovered)
        self.assertEqual(recovery.evidence_text, '"He died."')

    def test_evidence_locator_duplicate_normalized_match_is_ambiguous(self):
        location = locate_evidence_text(
            "Meng Hao shouted, “The third level!” Later, Meng Hao shouted, “The third level!”",
            'Meng Hao shouted, "The third level!"',
        )

        self.assertFalse(location.matched)
        self.assertTrue(location.ambiguous)
        self.assertEqual(location.match_method, "quote_normalized")

    def test_evidence_locator_offsets_map_to_raw_chapter_text(self):
        chapter_text = "Before.\nMeng Hao shouted, “The third level!”\nAfter."
        location = locate_evidence_text(
            chapter_text,
            'Meng Hao shouted, "The third level!"',
        )

        self.assertTrue(location.matched)
        self.assertEqual(location.matched_raw_text, "Meng Hao shouted, “The third level!”")
        self.assertEqual(chapter_text[location.start_offset:location.end_offset], location.matched_raw_text)

    def test_evidence_context_returns_previous_current_and_next_sentence(self):
        context = get_evidence_context(
            "First sentence. Meng Hao raised the Copper Mirror! The room shook?",
            "Meng Hao raised the Copper Mirror!",
        )

        self.assertTrue(context.found)
        self.assertEqual(context.previous_sentence, "First sentence.")
        self.assertEqual(context.evidence_sentence, "Meng Hao raised the Copper Mirror!")
        self.assertEqual(context.next_sentence, "The room shook?")
        self.assertEqual(
            context.combined_context,
            "First sentence. Meng Hao raised the Copper Mirror! The room shook?",
        )

    def test_evidence_context_at_chapter_start_has_no_previous_sentence(self):
        context = get_evidence_context(
            "Meng Hao raised the Copper Mirror. The room shook.",
            "Meng Hao raised the Copper Mirror.",
        )

        self.assertTrue(context.found)
        self.assertIsNone(context.previous_sentence)
        self.assertEqual(context.evidence_sentence, "Meng Hao raised the Copper Mirror.")
        self.assertEqual(context.next_sentence, "The room shook.")

    def test_evidence_context_at_chapter_end_has_no_next_sentence(self):
        context = get_evidence_context(
            "The room shook. Meng Hao raised the Copper Mirror.",
            "Meng Hao raised the Copper Mirror.",
        )

        self.assertTrue(context.found)
        self.assertEqual(context.previous_sentence, "The room shook.")
        self.assertEqual(context.evidence_sentence, "Meng Hao raised the Copper Mirror.")
        self.assertIsNone(context.next_sentence)

    def test_evidence_context_unmatched_evidence_returns_empty_context(self):
        context = get_evidence_context(
            "Meng Hao raised the Copper Mirror.",
            "Meng Hao lifted the Copper Mirror.",
        )

        self.assertFalse(context.found)
        self.assertEqual(context.combined_context, "")

    def test_evidence_context_preserves_raw_chapter_wording(self):
        context = get_evidence_context(
            "Meng Hao shouted, “The third level!”",
            'Meng Hao shouted, "The third level!"',
        )

        self.assertTrue(context.found)
        self.assertEqual(context.evidence_sentence, "Meng Hao shouted, “The third level!”")

    def test_evidence_context_supports_newline_space_difference(self):
        context = get_evidence_context(
            "Before. Meng Hao reached the third level\nof Qi Condensation. After.",
            "Meng Hao reached the third level of Qi Condensation.",
        )

        self.assertTrue(context.found)
        self.assertEqual(context.match_type, "whitespace_normalized")
        self.assertEqual(context.evidence_sentence, "Meng Hao reached the third level\nof Qi Condensation.")

    def test_evidence_context_spanning_two_sentences(self):
        context = get_evidence_context(
            "Before. Meng Hao swallowed the pill. The third level! After.",
            "Meng Hao swallowed the pill. The third level!",
        )

        self.assertTrue(context.found)
        self.assertEqual(context.previous_sentence, "Before.")
        self.assertEqual(context.evidence_sentence, "Meng Hao swallowed the pill. The third level!")
        self.assertEqual(context.next_sentence, "After.")

    def test_evidence_context_ambiguous_normalized_match_returns_no_context(self):
        context = get_evidence_context(
            "Meng Hao shouted, “The third level!” Later, Meng Hao shouted, “The third level!”",
            'Meng Hao shouted, "The third level!"',
        )

        self.assertFalse(context.found)
        self.assertTrue(context.ambiguous)

    def test_evidence_context_can_use_offsets_for_duplicate_sentence(self):
        chapter_text = (
            "Alex entered the cave. He reached the third level. "
            "Borin entered the cave. He reached the third level."
        )
        evidence = "He reached the third level."
        second_start = chapter_text.rfind(evidence)
        context = get_evidence_context(
            chapter_text,
            evidence,
            start_offset=second_start,
            end_offset=second_start + len(evidence),
            match_type="exact",
        )

        self.assertTrue(context.found)
        self.assertFalse(context.ambiguous)
        self.assertEqual(context.previous_sentence, "Borin entered the cave.")
        self.assertEqual(context.evidence_sentence, evidence)

    def test_add_evidence_preserves_duplicate_occurrences_with_offsets(self):
        self.set_chapter_content(
            "Alex entered the cave. He reached the third level. "
            "Borin entered the cave. He reached the third level."
        )
        evidence = "He reached the third level."
        first_start = self.chapter.content.find(evidence)
        second_start = self.chapter.content.rfind(evidence)

        self.assertTrue(
            add_evidence(
                self.novel,
                self.chapter,
                "character",
                self.character.id,
                evidence,
                start_offset=first_start,
                end_offset=first_start + len(evidence),
                match_type="exact",
            )
        )
        self.assertTrue(
            add_evidence(
                self.novel,
                self.chapter,
                "character",
                self.character.id,
                evidence,
                start_offset=second_start,
                end_offset=second_start + len(evidence),
                match_type="exact",
            )
        )
        rows = WikiEvidence.query.filter_by(
            entity_type="character",
            entity_id=self.character.id,
        ).order_by(WikiEvidence.start_offset).all()

        self.assertEqual(len(rows), 2)
        self.assertEqual([row.start_offset for row in rows], [first_start, second_start])

    def test_character_attribution_exact_canonical_full_name(self):
        result = resolve_character_attribution(
            evidence_text="Meng Hao reached the third level.",
            local_context="Meng Hao reached the third level.",
            candidate_characters=[self.character],
        )

        self.assertTrue(result.resolved)
        self.assertEqual(result.character_id, self.character.id)
        self.assertEqual(result.match_type, "canonical_name")

    def test_character_attribution_exact_approved_alias(self):
        db.session.add(
            CharacterAlias(
                character_id=self.character.id,
                alias="Brother Meng",
                first_seen_chapter_id=self.chapter.id,
            )
        )
        db.session.commit()

        result = resolve_character_attribution(
            evidence_text="Brother Meng reached the third level.",
            local_context="Brother Meng reached the third level.",
            candidate_characters=[self.character],
        )

        self.assertTrue(result.resolved)
        self.assertEqual(result.character_id, self.character.id)
        self.assertEqual(result.match_type, "approved_alias")

    def test_character_attribution_stable_title_style_resolution(self):
        elder = Character(
            novel_id=self.novel.id,
            name="Elder Chen",
            review_status="approved",
        )
        db.session.add(elder)
        db.session.commit()

        result = resolve_character_attribution(
            mention="Elder Chen",
            evidence_text="Elder Chen entered the hall.",
            local_context="Elder Chen entered the hall.",
            candidate_characters=[elder],
        )

        self.assertTrue(result.resolved)
        self.assertEqual(result.character_id, elder.id)
        self.assertIn(result.match_type, {"canonical_name", "stable_title"})

    def test_character_attribution_full_name_outranks_alias(self):
        other = Character(
            novel_id=self.novel.id,
            name="Other Character",
            review_status="approved",
        )
        db.session.add(other)
        db.session.flush()
        db.session.add(CharacterAlias(character_id=other.id, alias="Meng Hao", first_seen_chapter_id=self.chapter.id))
        db.session.commit()

        result = resolve_character_attribution(
            evidence_text="Meng Hao entered the hall.",
            local_context="Meng Hao entered the hall.",
            candidate_characters=[self.character, other],
        )

        self.assertTrue(result.resolved)
        self.assertEqual(result.character_id, self.character.id)
        self.assertEqual(result.match_type, "canonical_name")

    def test_character_attribution_unsafe_substring_does_not_match(self):
        db.session.add(
            CharacterAlias(
                character_id=self.character.id,
                alias="Hao",
                first_seen_chapter_id=self.chapter.id,
            )
        )
        db.session.commit()

        result = resolve_character_attribution(
            evidence_text="The State of Zhao was far away.",
            local_context="The State of Zhao was far away.",
            candidate_characters=[self.character],
        )

        self.assertFalse(result.resolved)

    def test_character_attribution_unapproved_partial_name_does_not_match(self):
        result = resolve_character_attribution(
            evidence_text="Hao reached the third level.",
            local_context="Hao reached the third level.",
            candidate_characters=[self.character],
        )

        self.assertFalse(result.resolved)

    def test_character_attribution_ambiguous_alias_unresolved(self):
        other = Character(
            novel_id=self.novel.id,
            name="Other Character",
            review_status="approved",
        )
        db.session.add(other)
        db.session.flush()
        db.session.add_all(
            [
                CharacterAlias(character_id=self.character.id, alias="Little Tiger", first_seen_chapter_id=self.chapter.id),
                CharacterAlias(character_id=other.id, alias="Little Tiger", first_seen_chapter_id=self.chapter.id),
            ]
        )
        db.session.commit()

        result = resolve_character_attribution(
            evidence_text="Little Tiger entered the hall.",
            local_context="Little Tiger entered the hall.",
            candidate_characters=[self.character, other],
        )

        self.assertFalse(result.resolved)
        self.assertTrue(result.ambiguous)
        self.assertIn("alias_ambiguous", result.risk_flags)

    def test_character_attribution_pronoun_resolves_one_clear_antecedent(self):
        result = resolve_character_attribution(
            evidence_text="He reached the third level.",
            local_context="Meng Hao swallowed the pill. He reached the third level.",
            candidate_characters=[self.character],
        )

        self.assertTrue(result.resolved)
        self.assertEqual(result.character_id, self.character.id)
        self.assertEqual(result.match_type, "unique_subject_continuity")

    def test_character_attribution_she_resolves_one_clear_antecedent(self):
        jane = Character(
            novel_id=self.novel.id,
            name="Jane Doe",
            review_status="approved",
        )
        db.session.add(jane)
        db.session.commit()

        result = resolve_character_attribution(
            evidence_text="She opened the box.",
            local_context="Jane Doe entered the room. She opened the box.",
            candidate_characters=[jane],
        )

        self.assertTrue(result.resolved)
        self.assertEqual(result.character_id, jane.id)
        self.assertEqual(result.match_type, "unique_subject_continuity")

    def test_character_attribution_possessive_pronoun_resolves_unique_subject(self):
        jane = Character(
            novel_id=self.novel.id,
            name="Jane Doe",
            review_status="approved",
        )
        db.session.add(jane)
        db.session.commit()

        result = resolve_character_attribution(
            evidence_text="Her cultivation had reached the fourth level.",
            local_context="Jane Doe stood silently. Her cultivation had reached the fourth level.",
            candidate_characters=[jane],
        )

        self.assertTrue(result.resolved)
        self.assertEqual(result.character_id, jane.id)
        self.assertEqual(result.match_type, "unique_possessive_pronoun")

    def test_character_attribution_repeated_subject_continuity_resolves(self):
        john = Character(
            novel_id=self.novel.id,
            name="John Smith",
            review_status="approved",
        )
        db.session.add(john)
        db.session.commit()

        result = resolve_character_attribution(
            evidence_text="He swallowed the pill.",
            local_context="John Smith entered the chamber. He opened the box. He swallowed the pill.",
            candidate_characters=[john],
        )

        self.assertTrue(result.resolved)
        self.assertEqual(result.character_id, john.id)
        self.assertEqual(result.match_type, "unique_subject_continuity")

    def test_character_attribution_new_explicit_subject_resets_continuity(self):
        john = Character(
            novel_id=self.novel.id,
            name="John Smith",
            review_status="approved",
        )
        robert = Character(
            novel_id=self.novel.id,
            name="Robert Stone",
            review_status="approved",
        )
        db.session.add_all([john, robert])
        db.session.commit()

        result = resolve_character_attribution(
            evidence_text="He swallowed the pill.",
            local_context="John Smith entered the chamber. Robert Stone opened the box. He swallowed the pill.",
            candidate_characters=[john, robert],
        )

        self.assertTrue(result.resolved)
        self.assertEqual(result.character_id, robert.id)
        self.assertEqual(result.match_type, "unique_subject_continuity")

    def test_character_attribution_distant_pronoun_does_not_resolve(self):
        john = Character(
            novel_id=self.novel.id,
            name="John Smith",
            review_status="approved",
        )
        db.session.add(john)
        db.session.commit()

        result = resolve_character_attribution(
            evidence_text="He left the room.",
            local_context="John Smith entered the chamber. The room was silent. A bell rang. He left the room.",
            candidate_characters=[john],
        )

        self.assertFalse(result.resolved)

    def test_character_attribution_pronoun_ambiguous_with_two_antecedents(self):
        other = Character(
            novel_id=self.novel.id,
            name="Han Zong",
            review_status="approved",
        )
        db.session.add(other)
        db.session.commit()

        result = resolve_character_attribution(
            evidence_text="He reached the third level.",
            local_context="Meng Hao faced Han Zong. He reached the third level.",
            candidate_characters=[self.character, other],
        )

        self.assertFalse(result.resolved)
        self.assertTrue(result.ambiguous)
        self.assertIn("context_attribution_ambiguous", result.risk_flags)

    def test_character_attribution_nearest_name_not_used_when_sentence_has_two_people(self):
        john = Character(
            novel_id=self.novel.id,
            name="John Smith",
            review_status="approved",
        )
        robert = Character(
            novel_id=self.novel.id,
            name="Robert Stone",
            review_status="approved",
        )
        db.session.add_all([john, robert])
        db.session.commit()

        result = resolve_character_attribution(
            evidence_text="He attacked.",
            local_context="John Smith spoke to Robert Stone. He attacked.",
            candidate_characters=[john, robert],
        )

        self.assertFalse(result.resolved)
        self.assertTrue(result.ambiguous)
        self.assertIn("context_attribution_ambiguous", result.risk_flags)

    def test_character_attribution_collective_both_supports_each_named_character(self):
        alice = Character(
            novel_id=self.novel.id,
            name="Alice Vale",
            review_status="approved",
        )
        bob = Character(
            novel_id=self.novel.id,
            name="Bob Stone",
            review_status="approved",
        )
        db.session.add_all([alice, bob])
        db.session.commit()

        text = "Alice Vale and Bob Stone were both at the seventh level."
        alice_result = resolve_character_attribution(
            evidence_text=text,
            local_context=text,
            candidate_characters=[alice, bob],
            target_character=alice,
        )
        bob_result = resolve_character_attribution(
            evidence_text=text,
            local_context=text,
            candidate_characters=[alice, bob],
            target_character=bob,
        )

        self.assertTrue(alice_result.resolved)
        self.assertEqual(alice_result.character_id, alice.id)
        self.assertEqual(alice_result.match_type, "collective_both")
        self.assertTrue(bob_result.resolved)
        self.assertEqual(bob_result.character_id, bob.id)
        self.assertEqual(bob_result.match_type, "collective_both")

    def test_character_attribution_ambiguous_collective_one_of_them_does_not_distribute(self):
        alice = Character(
            novel_id=self.novel.id,
            name="Alice Vale",
            review_status="approved",
        )
        bob = Character(
            novel_id=self.novel.id,
            name="Bob Stone",
            review_status="approved",
        )
        db.session.add_all([alice, bob])
        db.session.commit()

        text = "Alice Vale and Bob Stone entered, one of them at the seventh level."
        result = resolve_character_attribution(
            evidence_text=text,
            local_context=text,
            candidate_characters=[alice, bob],
            target_character=alice,
        )

        self.assertFalse(result.resolved)
        self.assertTrue(result.ambiguous)

    def test_character_attribution_object_pronoun_does_not_resolve_character(self):
        result = resolve_character_attribution(
            evidence_text="It reached the third level.",
            local_context="Meng Hao picked up the mirror. It reached the third level.",
            candidate_characters=[self.character],
        )

        self.assertFalse(result.resolved)

    def test_confirmed_progression_auto_approved(self):
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi Condensation",
                    description="Meng Hao reached the third level of Qi Condensation.",
                    evidence="Meng Hao reached the third level of Qi Condensation.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)
        self.assertGreaterEqual(progression.confidence_score, 90)

    def test_unverified_evidence_adds_risk_and_prevents_auto_approval(self):
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="fourth level of Qi Condensation",
                    description="Meng Hao advanced to the fourth level of Qi Condensation.",
                    evidence="Meng Hao advanced to the fourth level of Qi Condensation.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.review_status, "pending")
        self.assertFalse(progression.auto_approved)
        self.assertIn("evidence_not_exact", progression.risk_flags)
        self.assertIn("context_unavailable", progression.risk_flags)

    def test_new_full_real_name_character_with_score_70_auto_approved(self):
        db.session.delete(self.character)
        db.session.commit()

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao appears in the chapter.",
                    evidence="Meng Hao appears in the chapter.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.one()

        self.assertEqual(character.name, "Meng Hao")
        self.assertGreaterEqual(character.confidence_score, 90)
        self.assertEqual(character.review_status, "approved")
        self.assertTrue(character.auto_approved)

    def test_new_full_real_name_literal_mention_auto_approves_character_identity(self):
        db.session.delete(self.character)
        db.session.commit()
        self.set_chapter_content("Wang Youcai looked at Meng Hao and frowned.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Wang Youcai",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Wang Youcai appears.",
                    evidence="Wang Youcai looked at Meng Hao and frowned.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.one()

        self.assertEqual(character.name, "Wang Youcai")
        self.assertEqual(character.review_status, "approved")
        self.assertTrue(character.auto_approved)
        self.assertGreaterEqual(character.confidence_score, 90)

    def test_new_title_style_character_with_direct_evidence_auto_approved(self):
        db.session.delete(self.character)
        db.session.commit()

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Founder Reliance",
                    aliases=[],
                    appearance_type="mentioned",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Founder Reliance was mentioned in the chapter.",
                    evidence="Founder Reliance was mentioned in the chapter.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.one()

        self.assertEqual(character.name, "Founder Reliance")
        self.assertGreaterEqual(character.confidence_score, 90)
        self.assertEqual(character.review_status, "approved")
        self.assertTrue(character.auto_approved)

    def test_pronoun_only_evidence_does_not_auto_approve_character_identity(self):
        db.session.delete(self.character)
        db.session.commit()
        self.set_chapter_content("He looked at Meng Hao and frowned.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Wang Youcai",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Wang Youcai appears.",
                    evidence="He looked at Meng Hao and frowned.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.one()

        self.assertEqual(character.review_status, "pending")
        self.assertFalse(character.auto_approved)
        self.assertIn("character_identity_not_directly_supported", character.risk_flags)

    def test_non_exact_character_identity_evidence_recovers_from_raw_chapter(self):
        db.session.delete(self.character)
        db.session.commit()
        self.set_chapter_content("Wang Youcai looked at Meng Hao and frowned.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Wang Youcai",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Wang Youcai appears.",
                    evidence="Wang Youcai frowned at Meng Hao.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.one()

        self.assertEqual(character.review_status, "approved")
        self.assertTrue(character.auto_approved)
        self.assertNotIn("evidence_not_exact", character.risk_flags)
        evidence = WikiEvidence.query.filter_by(entity_type="character", entity_id=character.id).one()
        self.assertEqual(evidence.evidence_text, "Wang Youcai looked at Meng Hao and frowned.")

    def test_proper_name_character_recovers_from_typographic_quote_boundary(self):
        db.session.delete(self.character)
        db.session.commit()
        self.set_chapter_content("“Wang Youcai?” Meng Hao’s eyes grew wide as he looked at the young man.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Wang Youcai",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=self.metadata_ns(gender="male"),
                    description="Wang Youcai appears.",
                    evidence="Wang Youcai? Meng Hao's eyes grew wide as he looked at the young man.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Wang Youcai").one()
        evidence = WikiEvidence.query.filter_by(entity_type="character", entity_id=character.id).one()

        self.assertEqual(character.review_status, "approved")
        self.assertTrue(character.auto_approved)
        self.assertNotIn("evidence_not_exact", character.risk_flags)
        self.assertIn("Wang Youcai", evidence.evidence_text)
        self.assertEqual(
            evidence.evidence_text,
            "Wang Youcai?” Meng Hao’s eyes grew wide as he looked at the young man.",
        )

    def test_recovered_character_evidence_does_not_match_inside_other_words(self):
        db.session.delete(self.character)
        db.session.commit()
        self.set_chapter_content("The State of Zhao was far away.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Hao",
                    aliases=[],
                    appearance_type="mentioned",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Hao is mentioned.",
                    evidence="Hao was mentioned.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(Character.query.count(), 0)

    def test_progression_bad_evidence_recovers_exact_raw_support(self):
        self.set_chapter_content("Meng Hao reached the third level of Qi Condensation.")
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi Condensation",
                    description="Meng Hao advanced to the third level.",
                    evidence="Meng Hao advanced to the third level of Qi Condensation.",
                    source_extractor="progression_reasoning",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()
        evidence = WikiEvidence.query.filter_by(entity_type="progression", entity_id=progression.id).one()

        self.assertEqual(progression.review_status, "approved")
        self.assertNotIn("evidence_not_exact", progression.risk_flags)
        self.assertEqual(evidence.evidence_text, "Meng Hao reached the third level of Qi Condensation.")

    def test_generic_revalidation_uses_progression_specific_attribution(self):
        self.set_chapter_content(
            "Meng Hao entered the chamber alone. "
            "He broke through to the second level."
        )
        progression = CharacterProgressionEvent(
            novel_id=self.novel.id,
            character_id=self.character.id,
            chapter_id=self.chapter.id,
            progression_type="cultivation_level",
            new_value="second level",
            review_status="pending",
            confidence_score=50,
            risk_flags='["attribution_uncertain"]',
            source_extractor="progression_reasoning",
        )
        db.session.add(progression)
        db.session.flush()

        validation = revalidate_fact(
            self.novel,
            progression,
            "He broke through to the second level.",
            "recovered_progression_evidence",
            source_extractors={"progression_reasoning"},
            chapter=self.chapter,
        )

        self.assertIsNotNone(validation)
        self.assertTrue(validation.auto_approved)
        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)
        self.assertIn("context_supported_attribution", progression.risk_flags)
        self.assertNotIn("attribution_uncertain", progression.risk_flags)

    def test_item_and_skill_entity_bad_evidence_recover_exact_raw_mentions(self):
        self.set_chapter_content(
            "Meng Hao obtained the Copper Mirror. Meng Hao used the Wind Blade Technique."
        )
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Copper Mirror",
                    category="artifact",
                    importance="important",
                    description="A mirror.",
                    evidence="Meng Hao obtained a bronze mirror.",
                ),
            ],
            skills=[
                SimpleNamespace(
                    name="Wind Blade Technique",
                    aliases=[],
                    category="technique",
                    description="A technique.",
                    evidence="Meng Hao used a wind blade skill.",
                ),
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.filter_by(name="Copper Mirror").one()
        skill = Skill.query.filter_by(name="Wind Blade Technique").one()
        item_evidence = WikiEvidence.query.filter_by(entity_type="item", entity_id=item.id).one()
        skill_evidence = WikiEvidence.query.filter_by(entity_type="skill", entity_id=skill.id).one()

        self.assertEqual(item_evidence.evidence_text, "Meng Hao obtained the Copper Mirror.")
        self.assertEqual(skill_evidence.evidence_text, "Meng Hao used the Wind Blade Technique.")
        self.assertNotIn("evidence_not_exact", item.risk_flags)
        self.assertNotIn("evidence_not_exact", skill.risk_flags)

    def test_character_item_relationship_uses_recovered_raw_evidence_for_validation(self):
        self.set_chapter_content("Meng Hao picked up the ancient Copper Mirror artifact.")
        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Copper Mirror",
                    relationship_type="obtained",
                    description="Meng Hao obtained the mirror.",
                    evidence="Meng Hao obtained the Copper Mirror.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.filter_by(name="Copper Mirror").one()
        relationship = CharacterItem.query.filter_by(item_id=item.id).one()
        evidence = WikiEvidence.query.filter_by(
            entity_type="character_item",
            entity_id=relationship.id,
        ).one()
        audit = AIEvidenceAudit.query.filter_by(
            entity_type="character_item",
            entity_id=relationship.id,
        ).one()

        self.assertEqual(evidence.evidence_text, "Meng Hao picked up the ancient Copper Mirror artifact.")
        self.assertIsNotNone(evidence.start_offset)
        self.assertEqual(relationship.review_status, "approved")
        self.assertNotIn("evidence_not_exact", relationship.risk_flags)
        self.assertEqual(audit.ai_proposed_evidence, "Meng Hao obtained the Copper Mirror.")
        self.assertEqual(audit.canonical_evidence_text, "Meng Hao picked up the ancient Copper Mirror artifact.")

    def test_same_run_progression_merge_keeps_strongest_verified_evidence(self):
        self.set_chapter_content(
            "Meng Hao broke through to the third level of Qi Condensation. "
            "Later, his cultivation foundation was at the third level of Qi Condensation."
        )
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi Condensation",
                    description="Meng Hao was at the third level.",
                    evidence="Later, his cultivation foundation was at the third level of Qi Condensation.",
                    source_extractor="progression_audit",
                ),
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi Condensation",
                    description="Meng Hao broke through.",
                    evidence="Meng Hao broke through to the third level of Qi Condensation.",
                    source_extractor="progression_reasoning",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()
        rows = WikiEvidence.query.filter_by(
            entity_type="progression",
            entity_id=progression.id,
        ).all()

        self.assertEqual(CharacterProgressionEvent.query.count(), 1)
        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(
            any(
                row.evidence_text
                == "Meng Hao broke through to the third level of Qi Condensation."
                for row in rows
            )
        )
        self.assertNotIn("attribution_uncertain", progression.risk_flags)

    def test_failed_ai_evidence_is_preserved_without_canonical_evidence(self):
        self.set_chapter_content("A scholar stood beside the doorway.")
        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Wang Youcai",
                    aliases=[],
                    appearance_type="mentioned",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Wang Youcai appeared.",
                    evidence="Wang Youcai stood beside the doorway.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Wang Youcai").one()
        audit = AIEvidenceAudit.query.filter_by(
            entity_type="character",
            entity_id=character.id,
        ).one()

        self.assertEqual(character.review_status, "pending")
        self.assertFalse(character.auto_approved)
        self.assertEqual(WikiEvidence.query.filter_by(entity_type="character", entity_id=character.id).count(), 0)
        self.assertEqual(audit.ai_proposed_evidence, "Wang Youcai stood beside the doorway.")
        self.assertEqual(audit.verification_status, "failed")
        self.assertEqual(audit.failure_reason, "not_exact")
        self.assertEqual(audit.evidence_source, "unverified_ai")
        self.assertIsNone(audit.canonical_evidence_text)

    def test_recovered_evidence_preserves_failed_ai_evidence_for_audit(self):
        self.set_chapter_content("Wang Youcai looked at Meng Hao and frowned.")
        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Wang Youcai",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Wang Youcai appeared.",
                    evidence="He looked at Meng Hao and frowned.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Wang Youcai").one()
        canonical_evidence = WikiEvidence.query.filter_by(
            entity_type="character",
            entity_id=character.id,
        ).one()
        audit = AIEvidenceAudit.query.filter_by(
            entity_type="character",
            entity_id=character.id,
        ).one()

        self.assertEqual(character.review_status, "approved")
        self.assertEqual(canonical_evidence.evidence_text, "Wang Youcai looked at Meng Hao and frowned.")
        self.assertEqual(audit.ai_proposed_evidence, "He looked at Meng Hao and frowned.")
        self.assertEqual(audit.verification_status, "failed")
        self.assertEqual(audit.evidence_source, "backend_recovered")
        self.assertEqual(audit.canonical_evidence_text, "Wang Youcai looked at Meng Hao and frowned.")
        self.assertEqual(audit.recovery_method, "exact_character_reference")

    def test_verified_ai_evidence_becomes_canonical_without_debug_duplication(self):
        self.set_chapter_content("Li Ming entered the hall.")
        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Li Ming",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Li Ming appeared.",
                    evidence="Li Ming entered the hall.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Li Ming").one()
        evidence = WikiEvidence.query.filter_by(entity_type="character", entity_id=character.id).one()

        self.assertEqual(evidence.evidence_text, "Li Ming entered the hall.")
        self.assertEqual(AIEvidenceAudit.query.filter_by(entity_type="character", entity_id=character.id).count(), 0)

    def test_missing_ai_evidence_can_recover_and_records_missing_audit_status(self):
        self.set_chapter_content("Li Ming entered the hall.")
        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Li Ming",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Li Ming appeared.",
                    evidence="",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Li Ming").one()
        audit = AIEvidenceAudit.query.filter_by(entity_type="character", entity_id=character.id).one()

        self.assertEqual(character.review_status, "approved")
        self.assertEqual(audit.ai_proposed_evidence, "")
        self.assertEqual(audit.verification_status, "missing")
        self.assertEqual(audit.failure_reason, "missing")
        self.assertEqual(audit.evidence_source, "backend_recovered")

    def test_admin_response_exposes_ai_audit_but_public_evidence_does_not(self):
        self.set_chapter_content("Wang Youcai looked at Meng Hao and frowned.")
        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Wang Youcai",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Wang Youcai appeared.",
                    evidence="He looked at Meng Hao and frowned.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Wang Youcai").one()
        admin_payload = admin_review_response("characters", character)
        public_evidence = evidence_for("character", character.id)

        self.assertEqual(admin_payload["ai_evidence_audit"][0]["ai_proposed_evidence"], "He looked at Meng Hao and frowned.")
        self.assertEqual(public_evidence[0]["evidence_text"], "Wang Youcai looked at Meng Hao and frowned.")
        self.assertNotIn("ai_proposed_evidence", public_evidence[0])

    def test_multiple_progression_ai_evidence_audits_preserve_source_provenance(self):
        self.set_chapter_content("Meng Hao reached the third level of Qi Condensation.")
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi Condensation",
                    description="Meng Hao advanced to the third level.",
                    evidence="Meng Hao advanced to the third level of Qi Condensation.",
                    source_extractor="progression_extractor",
                ),
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi Condensation",
                    description="Meng Hao achieved the third level.",
                    evidence="Meng Hao achieved the third level of Qi Condensation.",
                    source_extractor="progression_audit",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()
        audits = AIEvidenceAudit.query.filter_by(
            entity_type="progression",
            entity_id=progression.id,
        ).order_by(AIEvidenceAudit.source_extractor).all()

        self.assertEqual(
            [(audit.source_extractor, audit.ai_proposed_evidence) for audit in audits],
            [
                ("progression_audit", "Meng Hao achieved the third level of Qi Condensation."),
                ("progression_extractor", "Meng Hao advanced to the third level of Qi Condensation."),
            ],
        )
        self.assertTrue(all(audit.evidence_source == "backend_recovered" for audit in audits))

    def test_existing_metadata_proposal_revalidates_when_stronger_evidence_merges(self):
        self.set_chapter_content("Meng Hao was about thirty years old.")
        proposal = CharacterMetadataProposal(
            novel_id=self.novel.id,
            character_id=self.character.id,
            chapter_id=self.chapter.id,
            field_name="age_text",
            old_value=None,
            raw_proposed_value="about 30 years old",
            proposed_value="about 30 years old",
            normalized_value="about 30 years old",
            confidence_score=0.8,
            evidence="Meng Hao appeared nearby.",
            review_warnings="metadata_evidence_weak\nevidence_not_exact",
            review_status="pending",
            auto_approved=False,
        )
        db.session.add(proposal)
        db.session.commit()

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text="about 30 years old",
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao appeared.",
                    evidence="Meng Hao appeared nearby.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        db.session.refresh(proposal)

        self.assertEqual(proposal.review_status, "approved")
        self.assertTrue(proposal.auto_approved)
        self.assertEqual(proposal.evidence, "Meng Hao was about thirty years old.")
        self.assertIsNone(proposal.review_warnings)
        self.assertEqual(self.character.age_text, "about 30 years old")
        audit = AIEvidenceAudit.query.filter_by(
            entity_type="character_metadata_proposal",
            entity_id=proposal.id,
        ).one()
        self.assertEqual(audit.ai_proposed_evidence, "Meng Hao appeared nearby.")
        self.assertEqual(audit.evidence_source, "backend_recovered")

    def test_existing_character_skill_revalidates_when_stronger_evidence_merges(self):
        self.set_chapter_content("Aria Vale cast the Wind Blade Technique.")
        character = Character(
            novel_id=self.novel.id,
            name="Aria Vale",
            review_status="approved",
        )
        skill = Skill(
            novel_id=self.novel.id,
            name="Wind Blade Technique",
            category="Technique",
            review_status="approved",
        )
        db.session.add_all([character, skill])
        db.session.flush()
        relationship = CharacterSkill(
            novel_id=self.novel.id,
            character_id=character.id,
            skill_id=skill.id,
            chapter_id=self.chapter.id,
            relationship_type="has",
            description="Weak old relationship.",
            confidence_score=40,
            risk_flags='["evidence_not_exact", "relationship_action_not_proven"]',
            source_extractor="character_skill",
            review_status="pending",
            auto_approved=False,
        )
        db.session.add(relationship)
        db.session.commit()

        extraction = self.empty_extraction(
            character_skills=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    skill_name="Wind Blade Technique",
                    relationship_type="has",
                    description="Aria Vale used the Wind Blade Technique.",
                    evidence="Aria Vale cast the Wind Blade Technique.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        db.session.refresh(relationship)

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertNotIn("evidence_not_exact", relationship.risk_flags)
        self.assertNotIn("relationship_action_not_proven", relationship.risk_flags)

    def test_existing_character_item_revalidates_when_stronger_evidence_merges(self):
        self.set_chapter_content("Aria Vale swallowed the silver pill.")
        character = Character(
            novel_id=self.novel.id,
            name="Aria Vale",
            review_status="approved",
        )
        item = Item(
            novel_id=self.novel.id,
            name="silver pill",
            category="Pill",
            review_status="approved",
        )
        db.session.add_all([character, item])
        db.session.flush()
        relationship = CharacterItem(
            novel_id=self.novel.id,
            character_id=character.id,
            item_id=item.id,
            chapter_id=self.chapter.id,
            relationship_type="used",
            description="Weak old relationship.",
            confidence_score=40,
            risk_flags='["evidence_not_exact", "relationship_action_not_proven"]',
            source_extractor="character_item",
            review_status="pending",
            auto_approved=False,
        )
        db.session.add(relationship)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver pill",
                    relationship_type="used",
                    description="Aria Vale used the silver pill.",
                    evidence="Aria Vale swallowed the silver pill.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        db.session.refresh(relationship)

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertNotIn("evidence_not_exact", relationship.risk_flags)
        self.assertNotIn("relationship_action_not_proven", relationship.risk_flags)

    def test_existing_life_event_revalidates_when_stronger_evidence_merges(self):
        self.set_chapter_content("Aria Vale died.")
        character = Character(
            novel_id=self.novel.id,
            name="Aria Vale",
            review_status="approved",
        )
        db.session.add(character)
        db.session.flush()
        life_event = CharacterLifeEvent(
            novel_id=self.novel.id,
            character_id=character.id,
            chapter_id=self.chapter.id,
            event_type="death",
            description="Aria Vale may have died.",
            confidence_score=35,
            risk_flags='["evidence_not_exact", "life_event_evidence_weak"]',
            source_extractor="life_event",
            review_status="pending",
            auto_approved=False,
        )
        db.session.add(life_event)
        db.session.commit()

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    event_type="death",
                    description="Aria Vale died.",
                    reason=None,
                    evidence="Aria Vale died.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        db.session.refresh(life_event)

        self.assertEqual(life_event.review_status, "approved")
        self.assertTrue(life_event.auto_approved)
        self.assertNotIn("evidence_not_exact", life_event.risk_flags)
        self.assertNotIn("life_event_evidence_weak", life_event.risk_flags)

    def test_item_name_misclassified_as_character_does_not_auto_approve(self):
        validation = validate_extracted_fact(
            ValidationContext(
                novel=self.novel,
                chapter=self.chapter,
                fact_type="character",
                entity_name="Copper Mirror",
                value="Copper Mirror",
                evidence="Meng Hao obtained the Copper Mirror.",
                character=Character(novel_id=self.novel.id, name="Copper Mirror"),
                entity_origin="newly_created_this_chapter",
                source_extractors={"character"},
            )
        )

        self.assertFalse(validation.auto_approved)
        self.assertIn("non_character_entity", validation.risk_flags)

    def test_group_label_misclassified_as_character_does_not_auto_approve(self):
        self.set_chapter_content("The guards entered the hall.")

        validation = validate_extracted_fact(
            ValidationContext(
                novel=self.novel,
                chapter=self.chapter,
                fact_type="character",
                entity_name="guards",
                value="guards",
                evidence="The guards entered the hall.",
                character=Character(novel_id=self.novel.id, name="guards"),
                entity_origin="newly_created_this_chapter",
                source_extractors={"character"},
            )
        )

        self.assertFalse(validation.auto_approved)
        self.assertIn("non_character_entity", validation.risk_flags)

    def test_pending_proper_name_character_approved_by_verified_progression_support(self):
        self.set_chapter_content("Han Zong's cultivation foundation reached the fifth level.")
        han = Character(
            novel_id=self.novel.id,
            name="Han Zong",
            review_status="pending",
            auto_approved=False,
        )
        db.session.add(han)
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Han Zong",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="fifth level",
                    description="Han Zong reached the fifth level.",
                    evidence="Han Zong's cultivation foundation reached the fifth level.",
                    source_extractor="progression_extractor",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Han Zong").one()

        self.assertEqual(character.review_status, "approved")
        self.assertTrue(character.auto_approved)
        self.assertIn("identity_supported_by_progression", character.risk_flags)

    def test_proper_name_character_created_through_life_event_evidence_auto_approves_identity(self):
        self.set_chapter_content("Wang Youcai died after falling from the cliff.")

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="Wang Youcai",
                    event_type="death",
                    description="Wang Youcai died.",
                    reason=None,
                    evidence="Wang Youcai died after falling from the cliff.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Wang Youcai").one()

        self.assertEqual(character.review_status, "approved")
        self.assertTrue(character.auto_approved)
        self.assertIn("identity_supported_by_life_event", character.risk_flags)

    def test_pending_character_item_does_not_approve_parent_identity(self):
        self.set_chapter_content("Han Zong saw the copper sword on the ground.")
        item = Item(
            novel_id=self.novel.id,
            name="copper sword",
            category="Weapon",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Han Zong",
                    item_name="copper sword",
                    relationship_type="used",
                    description="Han Zong used the copper sword.",
                    evidence="Han Zong saw the copper sword on the ground.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Han Zong").one()
        relationship = CharacterItem.query.one()

        self.assertEqual(character.review_status, "pending")
        self.assertFalse(character.auto_approved)
        self.assertNotIn("identity_supported_by_character_item", character.risk_flags or "")
        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_action_not_proven", relationship.risk_flags)

    def test_pending_character_skill_does_not_approve_parent_identity(self):
        self.set_chapter_content("Han Zong thought about the Wind Blade Technique.")
        skill = Skill(
            novel_id=self.novel.id,
            name="Wind Blade Technique",
            category="Technique",
            review_status="approved",
        )
        db.session.add(skill)
        db.session.commit()

        extraction = self.empty_extraction(
            character_skills=[
                SimpleNamespace(
                    character_name="Han Zong",
                    skill_name="Wind Blade Technique",
                    relationship_type="has",
                    description="Han Zong has the Wind Blade Technique.",
                    evidence="Han Zong thought about the Wind Blade Technique.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Han Zong").one()
        relationship = CharacterSkill.query.one()

        self.assertEqual(character.review_status, "pending")
        self.assertFalse(character.auto_approved)
        self.assertNotIn("identity_supported_by_character_skill", character.risk_flags or "")
        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_action_not_proven", relationship.risk_flags)

    def test_pronoun_only_support_does_not_create_or_approve_character_identity(self):
        self.set_chapter_content("He saw the copper sword on the ground.")
        item = Item(
            novel_id=self.novel.id,
            name="copper sword",
            category="Weapon",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Han Zong",
                    item_name="copper sword",
                    relationship_type="used",
                    description="Han Zong used the copper sword.",
                    evidence="He saw the copper sword on the ground.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertIsNone(Character.query.filter_by(name="Han Zong").first())
        self.assertEqual(CharacterItem.query.count(), 0)

    def test_generic_descriptive_character_support_does_not_auto_approve_identity(self):
        self.set_chapter_content("The old man saw the copper sword on the ground.")
        item = Item(
            novel_id=self.novel.id,
            name="copper sword",
            category="Weapon",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="old man",
                    item_name="copper sword",
                    relationship_type="used",
                    description="The old man used the copper sword.",
                    evidence="The old man saw the copper sword on the ground.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertIsNone(Character.query.filter_by(name="old man").first())

    def test_capitalized_descriptive_character_label_stays_pending(self):
        db.session.delete(self.character)
        db.session.commit()
        self.set_chapter_content("One was the clever fellow; the other one was clean and pudgy.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Clever Fellow",
                    aliases=[],
                    appearance_type="mentioned",
                    metadata=self.metadata_ns(),
                    description="A clever fellow is mentioned.",
                    evidence="One was the clever fellow; the other one was clean and pudgy.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Clever Fellow").one()

        self.assertEqual(character.review_status, "pending")
        self.assertFalse(character.auto_approved)
        self.assertIn("generic_character_label", character.risk_flags)

    def test_stable_single_word_nickname_can_still_auto_approve(self):
        db.session.delete(self.character)
        db.session.commit()
        self.set_chapter_content("Fatty hurried over and waved.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Fatty",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=self.metadata_ns(),
                    description="Fatty appears.",
                    evidence="Fatty hurried over and waved.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Fatty").one()

        self.assertEqual(character.review_status, "approved")
        self.assertTrue(character.auto_approved)
        self.assertNotIn("generic_character_label", character.risk_flags)

    def test_stable_title_style_character_created_through_support_auto_approves_identity(self):
        self.set_chapter_content("Elder Chen used the copper sword in battle.")
        item = Item(
            novel_id=self.novel.id,
            name="copper sword",
            category="Weapon",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Elder Chen",
                    item_name="copper sword",
                    relationship_type="used",
                    description="Elder Chen used the copper sword.",
                    evidence="Elder Chen used the copper sword in battle.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Elder Chen").one()

        self.assertEqual(character.review_status, "approved")
        self.assertTrue(character.auto_approved)

    def test_item_name_misclassified_as_character_does_not_promote_identity(self):
        self.set_chapter_content("Copper Mirror reached the fifth level.")

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Copper Mirror",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="fifth level",
                    description="Copper Mirror reached the fifth level.",
                    evidence="Copper Mirror reached the fifth level.",
                    source_extractor="progression_extractor",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertIsNone(Character.query.filter_by(name="Copper Mirror").first())

    def test_new_named_item_with_score_90_auto_approved(self):
        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Spirit Condensing Pill",
                    relationship_type="obtained",
                    description="Meng Hao obtained a Spirit Condensing Pill.",
                    evidence="Meng Hao obtained a Spirit Condensing Pill.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.name, "Spirit Condensing Pill")
        self.assertEqual(item.confidence_score, 90)
        self.assertEqual(item.review_status, "approved")
        self.assertTrue(item.auto_approved)

    def test_new_named_item_with_direct_evidence_auto_approved_below_90(self):
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Copper Mirror",
                    category="Artifact",
                    importance="important",
                    description="The Copper Mirror is a significant artifact.",
                    evidence="Meng Hao obtained the Copper Mirror.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.name, "Copper Mirror")
        self.assertEqual(item.confidence_score, 70)
        self.assertEqual(item.review_status, "approved")
        self.assertTrue(item.auto_approved)

    def test_new_named_artifact_with_direct_evidence_auto_approved(self):
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Blood Demon Banner",
                    category="Artifact",
                    importance="important",
                    description="The Blood Demon Banner is a named artifact.",
                    evidence="Meng Hao raised the Blood Demon Banner.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.name, "Blood Demon Banner")
        self.assertEqual(item.review_status, "approved")
        self.assertTrue(item.auto_approved)

    def test_new_generic_item_with_score_90_stays_pending(self):
        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Flying Sword",
                    relationship_type="obtained",
                    description="Meng Hao obtained a Flying Sword.",
                    evidence="Meng Hao obtained a Flying Sword.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.name, "Flying Sword")
        self.assertEqual(item.confidence_score, 90)
        self.assertEqual(item.review_status, "pending")
        self.assertFalse(item.auto_approved)

    def test_new_generic_direct_item_stays_pending(self):
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Flying Sword",
                    category="Weapon",
                    importance="important",
                    description="Meng Hao obtained a flying sword.",
                    evidence="Meng Hao obtained a Flying Sword.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.name, "Flying Sword")
        self.assertEqual(item.review_status, "pending")
        self.assertFalse(item.auto_approved)

    def test_obvious_item_category_is_inferred_from_name(self):
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Spirit Condensation Pill",
                    category="Other",
                    importance="important",
                    description="A medicinal pill used in cultivation.",
                    evidence="Meng Hao held the Spirit Condensation Pill.",
                ),
                SimpleNamespace(
                    name="Spirit Stone",
                    category="Other",
                    importance="important",
                    description="A cultivation resource.",
                    evidence="Meng Hao held a Spirit Stone.",
                ),
                SimpleNamespace(
                    name="White Sword",
                    category="Other",
                    importance="important",
                    description="A white sword.",
                    evidence="Meng Hao drew the White Sword.",
                ),
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        categories = {item.name: item.category for item in Item.query.all()}

        self.assertEqual(categories["Spirit Condensation Pill"], "Pill")
        self.assertEqual(categories["Spirit Stone"], "Resource")
        self.assertEqual(categories["White Sword"], "Weapon")

    def test_item_category_overrides_noisy_ai_category_from_name(self):
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Spirit Stone",
                    category="Pill",
                    importance="important",
                    description="A cultivation resource.",
                    evidence="Meng Hao held a Spirit Stone.",
                ),
                SimpleNamespace(
                    name="Shop Banner",
                    category="Pill",
                    importance="important",
                    description="A banner sign.",
                    evidence="Written on the Shop Banner were several large characters.",
                ),
                SimpleNamespace(
                    name="Bone Fragment",
                    category="Manual",
                    importance="important",
                    description="A bone fragment.",
                    evidence="Meng Hao picked up a Bone Fragment.",
                ),
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        categories = {item.name: item.category for item in Item.query.all()}

        self.assertEqual(categories["Spirit Stone"], "Resource")
        self.assertEqual(categories["Shop Banner"], "Other")
        self.assertEqual(categories["Bone Fragment"], "Other")

    def test_inscribed_fragment_without_instructional_semantics_is_not_manual(self):
        self.set_chapter_content("The Bone Fragment was covered with readable inscriptions.")
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Bone Fragment",
                    category="Other",
                    importance="important",
                    description="An inscribed bone fragment.",
                    evidence="The Bone Fragment was covered with readable inscriptions.",
                ),
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.category, "Other")

    def test_fragment_with_instructional_semantics_can_be_manual(self):
        self.set_chapter_content("The Bone Fragment contained instructions for the Moon Sword Technique.")
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Bone Fragment",
                    category="Other",
                    importance="important",
                    description="An instructional bone fragment.",
                    evidence="The Bone Fragment contained instructions for the Moon Sword Technique.",
                ),
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.category, "Manual")

    def test_core_item_category_types_are_preserved(self):
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Healing Pill",
                    category="Other",
                    importance="important",
                    description="A pill.",
                    evidence="Meng Hao swallowed the Healing Pill.",
                ),
                SimpleNamespace(
                    name="Wind Blade Scroll",
                    category="Other",
                    importance="important",
                    description="A scroll.",
                    evidence="Meng Hao obtained the Wind Blade Scroll.",
                ),
                SimpleNamespace(
                    name="Iron Sword",
                    category="Other",
                    importance="important",
                    description="A sword.",
                    evidence="Meng Hao drew the Iron Sword.",
                ),
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        categories = {item.name: item.category for item in Item.query.all()}

        self.assertEqual(categories["Healing Pill"], "Pill")
        self.assertEqual(categories["Wind Blade Scroll"], "Manual")
        self.assertEqual(categories["Iron Sword"], "Weapon")

    def test_clear_physical_item_passes_item_type_boundary(self):
        self.set_chapter_content("Aria Vale held the Silver Ring.")
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Silver Ring",
                    category="Artifact",
                    importance="important",
                    description="A ring.",
                    evidence="Aria Vale held the Silver Ring.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.review_status, "approved")
        self.assertTrue(item.auto_approved)

    def test_consumable_passes_item_type_boundary(self):
        self.set_chapter_content("Aria Vale swallowed the Healing Pill.")
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Healing Pill",
                    category="Pill",
                    importance="important",
                    description="A pill.",
                    evidence="Aria Vale swallowed the Healing Pill.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.review_status, "approved")
        self.assertTrue(item.auto_approved)

    def test_manual_passes_item_type_boundary(self):
        self.set_chapter_content("Aria Vale examined the Moon Sword Manual.")
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Moon Sword Manual",
                    category="Manual",
                    importance="important",
                    description="A manual.",
                    evidence="Aria Vale examined the Moon Sword Manual.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.review_status, "approved")
        self.assertTrue(item.auto_approved)

    def test_location_does_not_auto_approve_as_item(self):
        self.set_chapter_content("Aria Vale entered Crystal Cave.")
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Crystal Cave",
                    category="Artifact",
                    importance="important",
                    description="A cave location.",
                    evidence="Aria Vale entered Crystal Cave.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.review_status, "pending")
        self.assertFalse(item.auto_approved)
        self.assertIn("possible_location_not_item", item.risk_flags)

    def test_building_does_not_auto_approve_as_item(self):
        self.set_chapter_content("Aria Vale walked into Azure Hall.")
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Azure Hall",
                    category="Artifact",
                    importance="important",
                    description="A hall.",
                    evidence="Aria Vale walked into Azure Hall.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.review_status, "pending")
        self.assertFalse(item.auto_approved)
        self.assertIn("possible_location_not_item", item.risk_flags)

    def test_geographic_place_does_not_auto_approve_as_item(self):
        self.set_chapter_content("Aria Vale traveled to Northern Valley.")
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Northern Valley",
                    category="Artifact",
                    importance="important",
                    description="A valley.",
                    evidence="Aria Vale traveled to Northern Valley.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.review_status, "pending")
        self.assertFalse(item.auto_approved)
        self.assertIn("possible_location_not_item", item.risk_flags)

    def test_organization_does_not_auto_approve_as_item(self):
        self.set_chapter_content("Aria Vale joined Azure Sect.")
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Azure Sect",
                    category="Artifact",
                    importance="important",
                    description="A sect organization.",
                    evidence="Aria Vale joined Azure Sect.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.review_status, "pending")
        self.assertFalse(item.auto_approved)
        self.assertIn("possible_organization_not_item", item.risk_flags)

    def test_progression_realm_does_not_auto_approve_as_item(self):
        self.set_chapter_content("Aria Vale entered Foundation Establishment.")
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Foundation Establishment",
                    category="Artifact",
                    importance="important",
                    description="A realm.",
                    evidence="Aria Vale entered Foundation Establishment.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.review_status, "pending")
        self.assertFalse(item.auto_approved)
        self.assertIn("non_item_semantics", item.risk_flags)

    def test_skill_does_not_auto_approve_as_item(self):
        self.set_chapter_content("Aria Vale used Flame Serpent Art.")
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Flame Serpent Art",
                    category="Artifact",
                    importance="important",
                    description="A combat art.",
                    evidence="Aria Vale used Flame Serpent Art.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(Item.query.count(), 0)

    def test_ambiguous_proper_noun_item_stays_pending(self):
        self.set_chapter_content("Aria Vale noticed Silent Lotus.")
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Silent Lotus",
                    category="Artifact",
                    importance="important",
                    description="A named-looking phrase.",
                    evidence="Aria Vale noticed Silent Lotus.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.review_status, "pending")
        self.assertFalse(item.auto_approved)
        self.assertIn("item_type_uncertain", item.risk_flags)

    def test_location_like_word_in_physical_artifact_name_can_auto_approve(self):
        self.set_chapter_content("Aria Vale held the Cave Pearl.")
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Cave Pearl",
                    category="Artifact",
                    importance="important",
                    description="A pearl artifact.",
                    evidence="Aria Vale held the Cave Pearl.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.review_status, "approved")
        self.assertTrue(item.auto_approved)
        self.assertNotIn("possible_location_not_item", item.risk_flags)

    def test_ordinary_clothing_item_is_skipped_unless_significant(self):
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Green Robe",
                    category="Other",
                    importance="important",
                    description="A robe.",
                    evidence="Meng Hao received a green robe.",
                ),
                SimpleNamespace(
                    name="Rank-signifying Green Robe",
                    category="Other",
                    importance="important",
                    description="A robe that signifies rank.",
                    evidence="Meng Hao received a rank-signifying green robe.",
                ),
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item_names = {item.name for item in Item.query.all()}

        self.assertNotIn("Green Robe", item_names)
        self.assertIn("Rank-signifying Green Robe", item_names)

    def test_item_entity_promoted_from_approved_character_item_relationship(self):
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Copper Mirror",
                    category="Artifact",
                    importance="important",
                    description="A mysterious artifact mirror.",
                    evidence="The mirror was said to be a treasure.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.name, "Copper Mirror")
        self.assertEqual(item.review_status, "pending")

        relationship_extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Copper Mirror",
                    relationship_type="obtained",
                    description="Meng Hao obtained the mirror.",
                    evidence="Meng Hao picked up the mirror and carried it away.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, relationship_extraction)
        item = Item.query.one()
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertEqual(item.review_status, "approved")
        self.assertTrue(item.auto_approved)

    def test_generic_mirror_evidence_alone_does_not_approve_named_item(self):
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Copper Mirror",
                    category="Artifact",
                    importance="important",
                    description="A mysterious artifact mirror.",
                    evidence="The mirror was said to be a treasure.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.name, "Copper Mirror")
        self.assertEqual(item.review_status, "pending")
        self.assertFalse(item.auto_approved)

    def test_new_named_skill_with_direct_evidence_auto_approved(self):
        extraction = self.empty_extraction(
            skills=[
                SimpleNamespace(
                    name="Wind Blade Technique",
                    aliases=[],
                    category="Technique",
                    description="Wind Blade Technique is a named combat technique.",
                    evidence="Meng Hao used the Wind Blade Technique.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        skill = Skill.query.one()

        self.assertEqual(skill.name, "Wind Blade Technique")
        self.assertEqual(skill.confidence_score, 70)
        self.assertEqual(skill.review_status, "approved")
        self.assertTrue(skill.auto_approved)

    def test_water_arrows_variant_approves_skill_and_relationship(self):
        extraction = self.empty_extraction(
            character_skills=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    skill_name="Water Arrow technique",
                    relationship_type="has",
                    description="Meng Hao used Water Arrow technique.",
                    evidence="Meng Hao used Water Arrows, which shot toward his enemy.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        skill = Skill.query.one()
        relationship = CharacterSkill.query.one()

        self.assertEqual(skill.name, "Water Arrow technique")
        self.assertEqual(skill.review_status, "approved")
        self.assertTrue(skill.auto_approved)
        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)

    def test_progression_realm_is_rejected_as_skill_and_relationship(self):
        extraction = self.empty_extraction(
            skills=[
                SimpleNamespace(
                    name="Qi Condensation",
                    aliases=[],
                    category="Technique",
                    description="A cultivation level.",
                    evidence="Meng Hao reached the third level of Qi Condensation.",
                )
            ],
            character_skills=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    skill_name="Qi Condensation",
                    relationship_type="has",
                    description="Meng Hao reached Qi Condensation.",
                    evidence="Meng Hao reached the third level of Qi Condensation.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(Skill.query.count(), 0)
        self.assertEqual(CharacterSkill.query.count(), 0)

    def test_foundation_establishment_rejected_as_skill_unless_method(self):
        extraction = self.empty_extraction(
            skills=[
                SimpleNamespace(
                    name="Foundation Establishment",
                    aliases=[],
                    category="Technique",
                    description="A realm.",
                    evidence="She entered Foundation Establishment.",
                ),
                SimpleNamespace(
                    name="Foundation Establishment method",
                    aliases=[],
                    category="Technique",
                    description="A formal cultivation method.",
                    evidence="She learned the Foundation Establishment method.",
                ),
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        skill = Skill.query.one()

        self.assertEqual(skill.name, "Foundation Establishment method")
        self.assertEqual(skill.review_status, "approved")

    def test_existing_item_name_does_not_create_character_skill_link(self):
        item = Item(
            novel_id=self.novel.id,
            name="Wind Pennant",
            category="Artifact",
            description="A flying artifact.",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_skills=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    skill_name="Wind Pennant",
                    relationship_type="has",
                    description="The Wind Pennant lets Meng Hao fly.",
                    evidence="The Wind Pennant let Meng Hao fly through the sky.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(CharacterSkill.query.count(), 0)
        self.assertEqual(Skill.query.count(), 0)

    def test_skill_like_art_used_in_combat_is_not_saved_as_item(self):
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Flame Serpent Art",
                    category="Other",
                    importance="important",
                    description="A combat art used to create a serpent of flame.",
                    evidence="Meng Hao used the Flame Serpent Art in battle.",
                )
            ],
            skills=[
                SimpleNamespace(
                    name="Flame Serpent Art",
                    aliases=[],
                    category="Technique",
                    description="A combat art used to create a serpent of flame.",
                    evidence="Meng Hao used the Flame Serpent Art in battle.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(Item.query.count(), 0)
        self.assertEqual(Skill.query.count(), 1)
        self.assertEqual(Skill.query.one().review_status, "approved")

    def test_skill_like_value_is_rejected_as_progression(self):
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="class_rank",
                    old_value=None,
                    new_value="Were-demon skill",
                    description="Meng Hao used the Were-demon skill.",
                    evidence="Meng Hao used the Were-demon skill in battle.",
                ),
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="class_rank",
                    old_value=None,
                    new_value="Flame Serpent Art",
                    description="Meng Hao used the Flame Serpent Art.",
                    evidence="Meng Hao used the Flame Serpent Art in battle.",
                ),
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(CharacterProgressionEvent.query.count(), 0)

    def test_skill_manual_can_be_saved_as_item(self):
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Flame Serpent Art manual",
                    category="Manual",
                    importance="important",
                    description="A written manual for the Flame Serpent Art.",
                    evidence="Meng Hao found the Flame Serpent Art manual in the library.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.name, "Flame Serpent Art manual")
        self.assertEqual(item.review_status, "approved")
        self.assertTrue(item.auto_approved)

    def test_intangible_technique_is_skill_only_not_item(self):
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Fire Dragon Technique",
                    category="Manual",
                    importance="important",
                    description="A combat technique.",
                    evidence="Meng Hao used the Fire Dragon Technique.",
                )
            ],
            skills=[
                SimpleNamespace(
                    name="Fire Dragon Technique",
                    aliases=[],
                    category="Technique",
                    description="A combat technique.",
                    evidence="Meng Hao used the Fire Dragon Technique.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(Item.query.count(), 0)
        self.assertEqual(Skill.query.count(), 1)
        self.assertEqual(Skill.query.one().name, "Fire Dragon Technique")

    def test_common_intangible_skill_forms_save_as_skills(self):
        extraction = self.empty_extraction(
            skills=[
                SimpleNamespace(
                    name="Tiger Fist Martial Art",
                    aliases=[],
                    category="Art",
                    description="A martial art.",
                    evidence="Meng Hao practiced the Tiger Fist Martial Art.",
                ),
                SimpleNamespace(
                    name="Fireball Spell",
                    aliases=[],
                    category="Spell",
                    description="A spell.",
                    evidence="Meng Hao cast the Fireball Spell.",
                ),
                SimpleNamespace(
                    name="Tu Na Breathing Exercise",
                    aliases=[],
                    category="Cultivation Method",
                    description="A breathing exercise.",
                    evidence="Meng Hao practiced the Tu Na Breathing Exercise.",
                ),
                SimpleNamespace(
                    name="Seven Sword Art",
                    aliases=[],
                    category="Art",
                    description="A sword art.",
                    evidence="Meng Hao used the Seven Sword Art.",
                ),
                SimpleNamespace(
                    name="Golden Core Cultivation Method",
                    aliases=[],
                    category="Cultivation Method",
                    description="A cultivation method.",
                    evidence="Meng Hao learned the Golden Core Cultivation Method.",
                ),
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        skill_names = {skill.name for skill in Skill.query.all()}

        self.assertEqual(Item.query.count(), 0)
        self.assertEqual(
            skill_names,
            {
                "Tiger Fist Martial Art",
                "Fireball Spell",
                "Tu Na Breathing Exercise",
                "Seven Sword Art",
                "Golden Core Cultivation Method",
            },
        )

    def test_physical_skill_media_save_as_items_not_skills(self):
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Fire Dragon Manual",
                    category="Manual",
                    importance="important",
                    description="A manual.",
                    evidence="Meng Hao found the Fire Dragon Manual.",
                ),
                SimpleNamespace(
                    name="Wind Blade Scroll",
                    category="Manual",
                    importance="important",
                    description="A scroll.",
                    evidence="Meng Hao obtained the Wind Blade Scroll.",
                ),
                SimpleNamespace(
                    name="Water Arrow Jade Slip",
                    category="Manual",
                    importance="important",
                    description="A jade slip.",
                    evidence="Meng Hao received the Water Arrow Jade Slip.",
                ),
                SimpleNamespace(
                    name="Iron Body Book",
                    category="Manual",
                    importance="important",
                    description="A book.",
                    evidence="Meng Hao picked up the Iron Body Book.",
                ),
                SimpleNamespace(
                    name="Thunder Palm Tablet",
                    category="Artifact",
                    importance="important",
                    description="A tablet.",
                    evidence="Meng Hao carried the Thunder Palm Tablet.",
                ),
            ],
            skills=[
                SimpleNamespace(
                    name="Fire Dragon Manual",
                    aliases=[],
                    category="Technique",
                    description="Incorrectly extracted as a skill.",
                    evidence="Meng Hao found the Fire Dragon Manual.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item_names = {item.name for item in Item.query.all()}

        self.assertEqual(Skill.query.count(), 0)
        self.assertEqual(
            item_names,
            {
                "Fire Dragon Manual",
                "Wind Blade Scroll",
                "Water Arrow Jade Slip",
                "Iron Body Book",
                "Thunder Palm Tablet",
            },
        )

    def test_technique_manual_creates_item_only_without_separate_skill_evidence(self):
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Fire Dragon Technique Manual",
                    category="Manual",
                    importance="important",
                    description="A written manual.",
                    evidence="Meng Hao found the Fire Dragon Technique Manual.",
                )
            ],
            skills=[
                SimpleNamespace(
                    name="Fire Dragon Technique",
                    aliases=[],
                    category="Technique",
                    description="A technique inferred from a manual.",
                    evidence="Meng Hao found the Fire Dragon Technique Manual.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(Item.query.count(), 1)
        self.assertEqual(Item.query.one().name, "Fire Dragon Technique Manual")
        self.assertEqual(Skill.query.count(), 0)

    def test_technique_name_does_not_create_manual_item(self):
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Fire Dragon Technique",
                    category="Manual",
                    importance="important",
                    description="Incorrectly extracted as a manual.",
                    evidence="Meng Hao used the Fire Dragon Technique.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(Item.query.count(), 0)

    def test_manual_and_skill_with_similar_names_can_coexist_when_both_supported(self):
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Fire Dragon Technique Manual",
                    category="Manual",
                    importance="important",
                    description="A written manual.",
                    evidence="Meng Hao obtained the Fire Dragon Technique Manual.",
                )
            ],
            skills=[
                SimpleNamespace(
                    name="Fire Dragon Technique",
                    aliases=[],
                    category="Technique",
                    description="A combat technique.",
                    evidence="Meng Hao used the Fire Dragon Technique in battle.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(Item.query.one().name, "Fire Dragon Technique Manual")
        self.assertEqual(Skill.query.one().name, "Fire Dragon Technique")

    def test_speculative_spirit_teeth_stays_pending(self):
        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Spirit Teeth",
                    relationship_type="owns",
                    description="Meng Hao's teeth might become Spirit Teeth.",
                    evidence="Have his teeth become Spirit Teeth? If he keeps training, they will become true treasures.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()
        relationship = CharacterItem.query.one()

        self.assertEqual(item.review_status, "pending")
        self.assertFalse(item.auto_approved)
        self.assertEqual(relationship.review_status, "pending")
        self.assertFalse(relationship.auto_approved)

    def test_current_entity_can_be_approved_despite_separate_future_upgrade(self):
        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Spirit Teeth",
                    relationship_type="owns",
                    description="Meng Hao's Spirit Teeth are current treasures.",
                    evidence="Meng Hao's Spirit Teeth had become treasures. If he keeps training, they will transform into true treasures.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()
        relationship = CharacterItem.query.one()

        self.assertEqual(item.review_status, "approved")
        self.assertTrue(item.auto_approved)
        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)

    def test_generic_named_looking_skill_without_type_support_stays_pending(self):
        extraction = self.empty_extraction(
            skills=[
                SimpleNamespace(
                    name="Silent Lotus",
                    aliases=[],
                    category="Other",
                    description="A named-looking phrase.",
                    evidence="Meng Hao noticed the Silent Lotus.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(Skill.query.count(), 0)

    def test_new_generic_ability_action_is_skipped(self):
        extraction = self.empty_extraction(
            skills=[
                SimpleNamespace(
                    name="punch",
                    aliases=[],
                    category="Other",
                    description="Meng Hao punched his opponent.",
                    evidence="Meng Hao punched his opponent.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(Skill.query.count(), 0)

    def test_new_generic_character_stays_pending(self):
        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="old man",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="An old man appears in the chapter.",
                    evidence="An old man appears in the chapter.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="old man").one()

        self.assertEqual(character.review_status, "pending")
        self.assertFalse(character.auto_approved)

    def test_new_visual_label_character_stays_pending(self):
        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Shrewd-looking Man",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="A shrewd-looking man appeared in the chapter.",
                    evidence="A shrewd-looking man appeared in the chapter.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Shrewd-looking Man").one()

        self.assertEqual(character.confidence_score, 70)
        self.assertEqual(character.review_status, "pending")
        self.assertFalse(character.auto_approved)

    def test_direct_proper_name_character_auto_approves_with_consistent_state(self):
        db.session.delete(self.character)
        db.session.commit()
        self.set_chapter_content("Aria Vale entered the hall.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Aria Vale",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Aria Vale entered the hall.",
                    evidence="Aria Vale entered the hall.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Aria Vale").one()

        self.assertEqual(character.review_status, "approved")
        self.assertTrue(character.auto_approved)
        self.assertGreaterEqual(character.confidence_score, 90)
        self.assertNotIn("character_identity_not_directly_supported", character.risk_flags)

    def test_approved_character_identity_not_downgraded_by_later_weak_evidence(self):
        self.set_chapter_content("Meng Hao appeared in the chapter.")

        first_extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao appeared.",
                    evidence="Meng Hao appeared in the chapter.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, first_extraction)
        self.character.risk_flags = "[]"
        self.character.auto_approved = True
        self.character.review_status = "approved"
        db.session.commit()

        weak_chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=11,
            title="Chapter 11",
            content="He looked around the hall.",
            character_count=0,
        )
        db.session.add(weak_chapter)
        db.session.commit()

        weak_extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao appeared.",
                    evidence="He looked around the hall.",
                )
            ]
        )

        save_chapter_extraction(self.novel, weak_chapter, weak_extraction)
        character = Character.query.filter_by(name="Meng Hao").one()

        self.assertEqual(character.review_status, "approved")
        self.assertTrue(character.auto_approved)
        self.assertNotIn("character_identity_not_directly_supported", character.risk_flags)

    def test_source_independent_support_repairs_backend_auto_approval_state(self):
        self.character.review_status = "approved"
        self.character.auto_approved = False
        self.character.source_extractor = "character"
        self.character.risk_flags = '["character_identity_not_directly_supported"]'
        self.set_chapter_content("Meng Hao swallowed the copper pill.")
        item = Item(
            novel_id=self.novel.id,
            name="copper pill",
            category="Pill",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="copper pill",
                    relationship_type="used",
                    description="Meng Hao used the copper pill.",
                    evidence="Meng Hao swallowed the copper pill.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Meng Hao").one()

        self.assertEqual(character.review_status, "approved")
        self.assertTrue(character.auto_approved)
        self.assertIn("identity_supported_by_character_item", character.source_extractor)
        self.assertNotIn("character_identity_not_directly_supported", character.risk_flags)

    def test_manual_approval_state_is_not_marked_auto_without_identity_support(self):
        self.character.review_status = "approved"
        self.character.auto_approved = False
        self.character.source_extractor = "manual"
        self.character.risk_flags = "[]"
        db.session.commit()

        weak_chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=11,
            title="Chapter 11",
            content="Meng Hao entered the room.",
            character_count=0,
        )
        db.session.add(weak_chapter)
        db.session.commit()

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao appeared.",
                    evidence="Meng Hao entered the room.",
                )
            ]
        )

        save_chapter_extraction(self.novel, weak_chapter, extraction)
        character = Character.query.filter_by(name="Meng Hao").one()

        self.assertEqual(character.review_status, "approved")
        self.assertFalse(character.auto_approved)
        self.assertEqual(character.source_extractor, "manual")

    def test_promoted_stable_label_to_real_name_auto_approved(self):
        db.session.delete(self.character)
        db.session.commit()

        early_extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Fat Teenager",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="A fat teenager appeared in the chapter.",
                    evidence="A fat teenager appeared in the chapter.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, early_extraction)
        character = Character.query.one()

        self.assertEqual(character.name, "Fat Teenager")
        self.assertEqual(character.review_status, "pending")
        self.assertFalse(character.auto_approved)

        reveal_chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=11,
            title="Chapter 11",
            content="Fatty grinned and said his real name was Li Furui.",
            character_count=0,
        )
        db.session.add(reveal_chapter)
        db.session.commit()

        reveal_extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Li Furui",
                    aliases=["Fatty"],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Li Furui is the real name of Fatty.",
                    evidence="Fatty grinned and said his real name was Li Furui.",
                )
            ]
        )

        save_chapter_extraction(self.novel, reveal_chapter, reveal_extraction)
        character = Character.query.one()
        aliases = {alias.alias for alias in CharacterAlias.query.all()}

        self.assertEqual(character.name, "Li Furui")
        self.assertIn("Fatty", aliases)
        self.assertIn("Fat Teenager", aliases)
        self.assertEqual(character.review_status, "approved")
        self.assertTrue(character.auto_approved)
        self.assertGreaterEqual(character.confidence_score, 90)

    def test_unresolved_generic_label_remains_pending(self):
        db.session.delete(self.character)
        db.session.commit()

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Shrewd-looking Man",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="The Shrewd-looking Man appeared in the chapter.",
                    evidence="The Shrewd-looking Man appeared in the chapter.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Shrewd-looking Man").one()

        self.assertEqual(character.review_status, "pending")
        self.assertFalse(character.auto_approved)

    def test_stable_title_alias_is_stored_when_exact_evidence_supports_it(self):
        db.session.delete(self.character)
        db.session.commit()
        self.set_chapter_content("Sister Xu has reached the seventh level.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Elder Sister Xu",
                    aliases=[],
                    appearance_type="mentioned",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Elder Sister Xu is mentioned.",
                    evidence="Sister Xu has reached the seventh level.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Elder Sister Xu").one()
        aliases = {alias.alias: alias.evidence for alias in CharacterAlias.query.filter_by(character_id=character.id)}

        self.assertIn("Sister Xu", aliases)
        self.assertEqual(aliases["Sister Xu"], "Sister Xu has reached the seventh level.")

    def test_nickname_alias_is_stored_when_exact_evidence_supports_it(self):
        db.session.delete(self.character)
        db.session.commit()
        self.set_chapter_content("Fatty grinned and said his real name was Li Furui.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Li Furui",
                    aliases=["Fatty"],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Li Furui is Fatty.",
                    evidence="Fatty grinned and said his real name was Li Furui.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Li Furui").one()

        self.assertEqual(CharacterAlias.query.filter_by(character_id=character.id, alias="Fatty").count(), 1)

    def test_generic_and_pronoun_aliases_are_not_stored(self):
        db.session.delete(self.character)
        db.session.commit()
        self.set_chapter_content("Elder Sister Xu saw the woman, and she frowned.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Elder Sister Xu",
                    aliases=["woman", "she", "the woman"],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Elder Sister Xu appears.",
                    evidence="Elder Sister Xu saw the woman, and she frowned.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(CharacterAlias.query.count(), 0)

    def test_alias_evidence_must_be_exact_raw_chapter_text(self):
        db.session.delete(self.character)
        db.session.commit()
        self.set_chapter_content("Sister Xu has reached the seventh level.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Elder Sister Xu",
                    aliases=["Sister Xu"],
                    appearance_type="mentioned",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Elder Sister Xu is mentioned.",
                    evidence="Sister Xu reached the seventh level.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        alias = CharacterAlias.query.one()
        self.assertEqual(alias.alias, "Sister Xu")
        self.assertEqual(alias.evidence, "Sister Xu has reached the seventh level.")

    def test_ambiguous_alias_is_not_added_to_second_character(self):
        db.session.delete(self.character)
        db.session.commit()
        first = Character(novel_id=self.novel.id, name="First Named Character", review_status="approved")
        second = Character(novel_id=self.novel.id, name="Second Named Character", review_status="approved")
        db.session.add_all([first, second])
        db.session.flush()
        db.session.add(CharacterAlias(character_id=first.id, alias="Little Tiger", first_seen_chapter_id=self.chapter.id))
        db.session.commit()
        self.set_chapter_content("Little Tiger waved from the courtyard.")

        added = save_chapter_extraction(
            self.novel,
            self.chapter,
            self.empty_extraction(
                characters=[
                    SimpleNamespace(
                        name="Second Named Character",
                        aliases=["Little Tiger"],
                        appearance_type="appeared",
                        metadata=SimpleNamespace(
                            age_text=None,
                            gender=None,
                            race_or_species=None,
                            origin=None,
                            faction_or_affiliation=None,
                            status=None,
                            titles=[],
                        ),
                        description="Second Named Character appears.",
                        evidence="Little Tiger waved from the courtyard.",
                    )
                ]
            ),
        )

        self.assertEqual(CharacterAlias.query.filter_by(alias="Little Tiger").count(), 1)

    def test_alias_capture_resolves_future_fact_without_duplicate_character(self):
        db.session.delete(self.character)
        db.session.commit()
        self.set_chapter_content("Sister Xu has reached the seventh level.")

        first_extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Elder Sister Xu",
                    aliases=[],
                    appearance_type="mentioned",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Elder Sister Xu is mentioned.",
                    evidence="Sister Xu has reached the seventh level.",
                )
            ]
        )
        save_chapter_extraction(self.novel, self.chapter, first_extraction)

        later_chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=11,
            title="Chapter 11",
            content="Sister Xu appeared again.",
            character_count=0,
        )
        db.session.add(later_chapter)
        db.session.commit()

        second_extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Sister Xu",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Sister Xu appeared again.",
                    evidence="Sister Xu appeared again.",
                )
            ]
        )
        save_chapter_extraction(self.novel, later_chapter, second_extraction)

        self.assertEqual(Character.query.count(), 1)
        self.assertEqual(Character.query.one().name, "Elder Sister Xu")

    def test_metadata_status_dead_from_direct_evidence_auto_approves(self):
        self.set_chapter_content("Meng Hao's dead body lay on the stone floor.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status="dead",
                        titles=[],
                    ),
                    description="Meng Hao was confirmed dead.",
                    evidence="Meng Hao's dead body lay on the stone floor.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.field_name, "status")
        self.assertEqual(proposal.proposed_value, "dead")
        self.assertEqual(proposal.review_status, "approved")
        self.assertTrue(proposal.auto_approved)
        self.assertEqual(self.character.status, "dead")

    def test_metadata_status_from_vague_injury_stays_pending(self):
        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status="dead",
                        titles=[],
                    ),
                    description="Meng Hao was badly injured.",
                    evidence="Meng Hao was badly injured during the fight.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.field_name, "status")
        self.assertEqual(proposal.review_status, "pending")
        self.assertFalse(proposal.auto_approved)

    def test_metadata_status_believed_dead_stays_pending(self):
        self.set_chapter_content("Meng Hao was believed to be dead after the explosion.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status="dead",
                        titles=[],
                    ),
                    description="Meng Hao was believed dead.",
                    evidence="Meng Hao was believed to be dead after the explosion.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.review_status, "pending")
        self.assertFalse(proposal.auto_approved)
        self.assertIn("speculative_status", proposal.review_warnings)

    def test_metadata_status_dead_can_revalidate_from_approved_life_event(self):
        self.set_chapter_content("Meng Hao was badly hurt. Meng Hao collapsed and died.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status="dead",
                        titles=[],
                    ),
                    description="Meng Hao was hurt.",
                    evidence="Meng Hao was badly hurt.",
                )
            ],
            life_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    event_type="death",
                    description="Meng Hao died.",
                    reason=None,
                    evidence="Meng Hao collapsed and died.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.review_status, "approved")
        self.assertTrue(proposal.auto_approved)
        self.assertEqual(proposal.evidence, "Meng Hao collapsed and died.")

    def test_metadata_status_alive_from_direct_evidence_auto_approves(self):
        self.set_chapter_content("Meng Hao was still alive after the battle.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status="alive",
                        titles=[],
                    ),
                    description="Meng Hao was confirmed alive.",
                    evidence="Meng Hao was still alive after the battle.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.field_name, "status")
        self.assertEqual(proposal.proposed_value, "alive")
        self.assertEqual(proposal.review_status, "approved")
        self.assertTrue(proposal.auto_approved)

    def test_age_metadata_with_direct_evidence_auto_approves(self):
        self.set_chapter_content("Meng Hao was about twenty-four or twenty-five years old.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text="about twenty-four or twenty-five years old",
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao's age is stated.",
                    evidence="Meng Hao was about twenty-four or twenty-five years old.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.field_name, "age_text")
        self.assertEqual(proposal.proposed_value, "about 24-25 years old")
        self.assertEqual(proposal.review_status, "approved")
        self.assertTrue(proposal.auto_approved)
        self.assertEqual(
            proposal.evidence,
            "Meng Hao was about twenty-four or twenty-five years old.",
        )
        self.assertNotIn("Chapter", proposal.evidence)
        self.assertEqual(self.character.age_text, "about 24-25 years old")

    def test_metadata_evidence_recovers_from_artificial_chapter_prefix(self):
        self.set_chapter_content("Meng Hao was about thirty years old.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text="about thirty years old",
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao's age is stated.",
                    evidence="Chapter 10: Meng Hao was about thirty years old.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.evidence, "Meng Hao was about thirty years old.")
        self.assertEqual(proposal.review_status, "approved")
        self.assertTrue(proposal.auto_approved)
        self.assertFalse(proposal.review_warnings)
        self.assertNotIn("Chapter 10:", proposal.evidence)

    def test_informational_evidence_normalization_does_not_block_metadata_approval(self):
        self.set_chapter_content("Meng Hao was about thirty\u00a0years old.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text="about 30 years old",
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao's age is stated.",
                    evidence="Meng Hao was about thirty years old.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.review_status, "approved")
        self.assertTrue(proposal.auto_approved)
        self.assertEqual(proposal.evidence, "Meng Hao was about thirty\u00a0years old.")
        self.assertIsNone(proposal.review_warnings)
        self.assertFalse(
            metadata_warnings_block_auto_approval(["evidence_located_with_normalization"])
        )

    def test_metadata_evidence_does_not_merge_multiple_chapter_snippets(self):
        self.set_chapter_content("Meng Hao walked past the Reliance Sect gate.")

        first_extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation="Reliance Sect",
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao was near the Reliance Sect.",
                    evidence="Meng Hao walked past the Reliance Sect gate.",
                )
            ]
        )
        save_chapter_extraction(self.novel, self.chapter, first_extraction)

        chapter_two = Chapter(
            novel_id=self.novel.id,
            chapter_number=11,
            title="Chapter 11",
            content="Meng Hao saw Reliance Sect banners nearby.",
            character_count=0,
        )
        db.session.add(chapter_two)
        db.session.commit()

        second_extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation="Reliance Sect",
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao was near the Reliance Sect.",
                    evidence="Meng Hao saw Reliance Sect banners nearby.",
                )
            ]
        )
        save_chapter_extraction(self.novel, chapter_two, second_extraction)

        proposal = CharacterMetadataProposal.query.one()

        self.assertNotIn("Chapter", proposal.evidence)
        self.assertNotIn("\n\n", proposal.evidence)
        self.assertIn(
            proposal.evidence,
            {
                "Meng Hao walked past the Reliance Sect gate.",
                "Meng Hao saw Reliance Sect banners nearby.",
            },
        )

    def test_metadata_without_exact_chapter_evidence_stays_pending_with_warning(self):
        self.set_chapter_content("Meng Hao entered the valley.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text="about thirty years old",
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao's age is stated.",
                    evidence="Meng Hao was about thirty years old.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.evidence, "Meng Hao was about thirty years old.")
        self.assertEqual(proposal.review_status, "pending")
        self.assertIn("metadata_evidence_weak", proposal.review_warnings)

    def test_conflicting_age_metadata_stays_pending(self):
        self.character.age_text = "20 years old"
        db.session.commit()

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text="about thirty years old",
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao's age is stated differently.",
                    evidence="Meng Hao was about thirty years old.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.field_name, "age_text")
        self.assertEqual(proposal.review_status, "pending")
        self.assertFalse(proposal.auto_approved)
        self.assertIn("differs", proposal.review_warnings)

    def test_inferred_human_species_metadata_is_ignored(self):
        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species="human",
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao's body was described.",
                    evidence="Meng Hao's dead eyes still shone with horror.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(CharacterMetadataProposal.query.count(), 0)

    def test_explicit_non_human_species_metadata_auto_approves(self):
        self.set_chapter_content("Meng Hao revealed that he was a dragon.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species="dragon",
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao's species was revealed.",
                    evidence="Meng Hao revealed that he was a dragon.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.field_name, "race_or_species")
        self.assertEqual(proposal.review_status, "approved")
        self.assertTrue(proposal.auto_approved)
        self.assertEqual(self.character.race_or_species, "dragon")

    def test_explicit_human_species_metadata_auto_approves_only_when_discussed(self):
        self.set_chapter_content("Meng Hao said he was born as a human.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species="human",
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao's species was revealed.",
                    evidence="Meng Hao said he was born as a human.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.field_name, "race_or_species")
        self.assertEqual(proposal.review_status, "approved")
        self.assertTrue(proposal.auto_approved)
        self.assertEqual(self.character.race_or_species, "human")

    def test_weak_faction_cooccurrence_stays_pending(self):
        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation="Reliance Sect",
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao appeared near the sect.",
                    evidence="Meng Hao walked through the valley. Reliance Sect bells rang nearby.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.field_name, "faction_or_affiliation")
        self.assertEqual(proposal.review_status, "pending")
        self.assertFalse(proposal.auto_approved)

    def test_direct_faction_membership_auto_approves(self):
        self.set_chapter_content("Meng Hao became a disciple of the Reliance Sect.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation="Reliance Sect",
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao joined the Reliance Sect.",
                    evidence="Meng Hao became a disciple of the Reliance Sect.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.field_name, "faction_or_affiliation")
        self.assertEqual(proposal.review_status, "approved")
        self.assertTrue(proposal.auto_approved)
        self.assertEqual(self.character.faction_or_affiliation, "reliance sect")

    def test_former_faction_affiliation_stays_pending(self):
        self.set_chapter_content("Meng Hao had once belonged to the Reliance Sect but was expelled.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation="Reliance Sect",
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao formerly belonged to the Reliance Sect.",
                    evidence="Meng Hao had once belonged to the Reliance Sect but was expelled.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.review_status, "pending")
        self.assertFalse(proposal.auto_approved)
        self.assertIn("former_affiliation_only", proposal.review_warnings)

    def test_location_near_faction_does_not_prove_membership(self):
        self.set_chapter_content("Meng Hao entered the Reliance Sect compound.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation="Reliance Sect",
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao visited the compound.",
                    evidence="Meng Hao entered the Reliance Sect compound.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.review_status, "pending")
        self.assertFalse(proposal.auto_approved)
        self.assertIn("affiliation_not_proven", proposal.review_warnings)

    def test_current_title_auto_approves(self):
        self.set_chapter_content("Meng Hao was an Inner Sect disciple.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=["Inner Sect disciple"],
                    ),
                    description="Meng Hao held a title.",
                    evidence="Meng Hao was an Inner Sect disciple.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.review_status, "approved")
        self.assertTrue(proposal.auto_approved)
        self.assertEqual(self.character.titles, "Inner Sect disciple")

    def test_future_title_promotion_stays_pending(self):
        self.set_chapter_content("Meng Hao was selected to be promoted to Inner Sect disciple.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=["Inner Sect disciple"],
                    ),
                    description="Meng Hao was selected for promotion.",
                    evidence="Meng Hao was selected to be promoted to Inner Sect disciple.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.review_status, "pending")
        self.assertFalse(proposal.auto_approved)
        self.assertIn("promotion_not_completed", proposal.review_warnings)

    def test_title_progression_overlap_stays_pending_with_warning(self):
        db.session.add(
            CharacterProgressionEvent(
                novel_id=self.novel.id,
                character_id=self.character.id,
                chapter_id=self.chapter.id,
                progression_type="position",
                new_value="outer sect disciple",
                description="Meng Hao became an Outer Sect disciple.",
                review_status="approved",
                auto_approved=True,
            )
        )
        db.session.commit()

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=["Outer Sect disciple"],
                    ),
                    description="Meng Hao became an Outer Sect disciple.",
                    evidence="Meng Hao became an Outer Sect disciple.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.field_name, "titles")
        self.assertEqual(proposal.review_status, "pending")
        self.assertFalse(proposal.auto_approved)
        self.assertIn("overlaps", proposal.review_warnings)

    def test_alias_evidence_supports_metadata_after_canonical_promotion(self):
        self.set_chapter_content("Fatty became a disciple of the Reliance Sect.")

        self.character.name = "Li Furui"
        db.session.add(
            CharacterAlias(
                character_id=self.character.id,
                alias="Fatty",
                first_seen_chapter_id=self.chapter.id,
            )
        )
        db.session.commit()

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Li Furui",
                    aliases=["Fatty"],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation="Reliance Sect",
                        status=None,
                        titles=[],
                    ),
                    description="Fatty joined the Reliance Sect.",
                    evidence="Fatty became a disciple of the Reliance Sect.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.field_name, "faction_or_affiliation")
        self.assertEqual(proposal.review_status, "approved")
        self.assertTrue(proposal.auto_approved)

    def test_direct_origin_auto_approves(self):
        self.set_chapter_content("Meng Hao was originally from River City.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin="River City",
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao's origin is stated.",
                    evidence="Meng Hao was originally from River City.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.field_name, "origin")
        self.assertEqual(proposal.review_status, "approved")
        self.assertTrue(proposal.auto_approved)
        self.assertEqual(self.character.origin, "river city")

    def test_travel_from_place_does_not_prove_origin(self):
        self.set_chapter_content("Meng Hao returned from River City after a mission.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin="River City",
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao traveled from River City.",
                    evidence="Meng Hao returned from River City after a mission.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.review_status, "pending")
        self.assertFalse(proposal.auto_approved)
        self.assertIn("location_not_origin", proposal.review_warnings)

    def test_origin_attaches_to_appositive_character(self):
        bob = Character(
            novel_id=self.novel.id,
            name="Bob Stone",
            review_status="approved",
        )
        db.session.add(bob)
        db.session.commit()
        self.set_chapter_content("Meng Hao spoke with Bob Stone, a native of River City.")

        alex_extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin="River City",
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao spoke with Bob.",
                    evidence="Meng Hao spoke with Bob Stone, a native of River City.",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, alex_extraction)
        alex_proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(alex_proposal.review_status, "pending")
        self.assertFalse(alex_proposal.auto_approved)

        CharacterMetadataProposal.query.delete()
        db.session.commit()

        create_character_metadata_proposals(
            self.novel,
            self.chapter,
            bob,
            SimpleNamespace(
                age_text=None,
                gender=None,
                race_or_species=None,
                origin="River City",
                faction_or_affiliation=None,
                status=None,
                titles=[],
            ),
            "Meng Hao spoke with Bob Stone, a native of River City.",
        )

        bob_proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(bob_proposal.review_status, "approved")
        self.assertTrue(bob_proposal.auto_approved)

    def test_pronoun_metadata_resolves_when_local_subject_is_unique(self):
        jane = Character(
            novel_id=self.novel.id,
            name="Jane Doe",
            review_status="approved",
        )
        db.session.add(jane)
        db.session.commit()
        self.set_chapter_content("Jane Doe entered the room. She was about thirty years old.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Jane Doe",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text="about 30 years old",
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Jane Doe's age was stated.",
                    evidence="She was about thirty years old.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.field_name, "age_text")
        self.assertEqual(proposal.review_status, "approved")
        self.assertTrue(proposal.auto_approved)

    def test_apparent_age_metadata_remains_pending(self):
        jane = Character(
            novel_id=self.novel.id,
            name="Jane Doe",
            review_status="approved",
        )
        db.session.add(jane)
        db.session.commit()
        self.set_chapter_content("Jane Doe entered the room. She looked about thirty years old.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Jane Doe",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text="about 30 years old",
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Jane Doe appeared around thirty.",
                    evidence="She looked about thirty years old.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.review_status, "pending")
        self.assertFalse(proposal.auto_approved)
        self.assertIn("apparent_age_only", proposal.review_warnings)

    def test_rhetorical_age_metadata_remains_pending(self):
        self.set_chapter_content("What seventeen-year-old would behave this way?")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text="17 years old",
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao was mentioned.",
                    evidence="What seventeen-year-old would behave this way?",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.review_status, "pending")
        self.assertFalse(proposal.auto_approved)
        self.assertIn("age_not_factual", proposal.review_warnings)

    def test_ambiguous_pronoun_metadata_remains_pending(self):
        jane = Character(
            novel_id=self.novel.id,
            name="Jane Doe",
            review_status="approved",
        )
        mira = Character(
            novel_id=self.novel.id,
            name="Mira Stone",
            review_status="approved",
        )
        db.session.add_all([jane, mira])
        db.session.commit()
        self.set_chapter_content("Jane Doe stood beside Mira Stone. She looked about thirty years old.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Jane Doe",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text="about 30 years old",
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Jane Doe's age was stated.",
                    evidence="She looked about thirty years old.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(proposal.review_status, "pending")
        self.assertFalse(proposal.auto_approved)

    def test_death_life_event_from_direct_death_evidence_auto_approves(self):
        zhao = Character(
            novel_id=self.novel.id,
            name="Zhao Wugang",
            review_status="approved",
        )
        db.session.add(zhao)
        db.session.commit()

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="Zhao Wugang",
                    event_type="death",
                    description="Zhao Wugang died.",
                    reason="Killed in battle.",
                    evidence="Zhao Wugang's dead eyes still shone with horror.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        event = CharacterLifeEvent.query.one()

        self.assertEqual(event.event_type, "death")
        self.assertEqual(event.review_status, "approved")
        self.assertTrue(event.auto_approved)

    def test_death_life_event_from_killed_evidence_auto_approves(self):
        zhao = Character(
            novel_id=self.novel.id,
            name="Zhao Wugang",
            review_status="approved",
        )
        db.session.add(zhao)
        db.session.commit()

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="Zhao Wugang",
                    event_type="death",
                    description="Zhao Wugang was killed.",
                    reason="Killed in battle.",
                    evidence="Zhao Wugang was killed during the battle.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        event = CharacterLifeEvent.query.one()

        self.assertEqual(event.review_status, "approved")
        self.assertTrue(event.auto_approved)

    def test_death_life_event_from_lifeless_body_auto_approves(self):
        zhao = Character(
            novel_id=self.novel.id,
            name="Zhao Wugang",
            review_status="approved",
        )
        db.session.add(zhao)
        db.session.commit()

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="Zhao Wugang",
                    event_type="death",
                    description="Zhao Wugang died.",
                    reason="His body was lifeless.",
                    evidence="Zhao Wugang's body was lifeless on the ground.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        event = CharacterLifeEvent.query.one()

        self.assertEqual(event.review_status, "approved")
        self.assertTrue(event.auto_approved)

    def test_death_life_event_from_name_variant_evidence_auto_approves(self):
        wang = Character(
            novel_id=self.novel.id,
            name="Wang Youcai",
            review_status="approved",
        )
        db.session.add(wang)
        db.session.flush()
        db.session.add(
            CharacterAlias(
                character_id=wang.id,
                alias="Big Bro Youcai",
                first_seen_chapter_id=self.chapter.id,
            )
        )
        db.session.commit()

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="Wang Youcai",
                    event_type="death",
                    description="Wang Youcai died.",
                    reason="Knocked from a cliff.",
                    evidence='"He died," said the young man. "Big Bro Youcai was knocked off a cliff."',
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        event = CharacterLifeEvent.query.one()

        self.assertEqual(event.event_type, "death")
        self.assertEqual(event.review_status, "approved")
        self.assertTrue(event.auto_approved)

    def test_unique_local_pronoun_death_auto_approves(self):
        john = Character(
            novel_id=self.novel.id,
            name="John Smith",
            review_status="approved",
        )
        db.session.add(john)
        db.session.commit()
        self.set_chapter_content("John Smith staggered backward. He died moments later.")

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="John Smith",
                    event_type="death",
                    description="John Smith died.",
                    reason=None,
                    evidence="He died moments later.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        event = CharacterLifeEvent.query.one()

        self.assertEqual(event.review_status, "approved")
        self.assertTrue(event.auto_approved)
        self.assertNotIn("life_event_attribution_uncertain", event.risk_flags)

    def test_ambiguous_combat_pronoun_death_remains_pending(self):
        john = Character(
            novel_id=self.novel.id,
            name="John Smith",
            review_status="approved",
        )
        robert = Character(
            novel_id=self.novel.id,
            name="Robert Stone",
            review_status="approved",
        )
        db.session.add_all([john, robert])
        db.session.commit()
        self.set_chapter_content("John Smith fought Robert Stone. He died moments later.")

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="John Smith",
                    event_type="death",
                    description="John Smith died.",
                    reason=None,
                    evidence="He died moments later.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        event = CharacterLifeEvent.query.one()

        self.assertEqual(event.review_status, "pending")
        self.assertFalse(event.auto_approved)
        self.assertIn("life_event_attribution_uncertain", event.risk_flags)

    def test_vague_injury_does_not_auto_approve_death_life_event(self):
        zhao = Character(
            novel_id=self.novel.id,
            name="Zhao Wugang",
            review_status="approved",
        )
        db.session.add(zhao)
        db.session.commit()

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="Zhao Wugang",
                    event_type="death",
                    description="Zhao Wugang was injured.",
                    reason="Battle injury.",
                    evidence="Zhao Wugang was badly injured during the fight.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        event = CharacterLifeEvent.query.one()

        self.assertEqual(event.event_type, "death")
        self.assertEqual(event.review_status, "pending")
        self.assertFalse(event.auto_approved)

    def test_body_dropped_without_death_confirmation_stays_pending(self):
        zhao = Character(
            novel_id=self.novel.id,
            name="Zhao Wugang",
            review_status="approved",
        )
        db.session.add(zhao)
        db.session.commit()

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="Zhao Wugang",
                    event_type="death",
                    description="Zhao Wugang died.",
                    reason="His body dropped.",
                    evidence="Zhao Wugang's body dropped to the ground.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        event = CharacterLifeEvent.query.one()

        self.assertEqual(event.review_status, "pending")
        self.assertFalse(event.auto_approved)
        self.assertIn("life_event_evidence_weak", event.risk_flags)

    def test_confirmed_death_with_speculative_cause_approves_core_event_only(self):
        zhao = Character(
            novel_id=self.novel.id,
            name="Zhao Wugang",
            review_status="approved",
        )
        db.session.add(zhao)
        db.session.commit()

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="Zhao Wugang",
                    event_type="death",
                    description="Zhao Wugang died.",
                    reason="Probably eaten by wild animals.",
                    evidence="Zhao Wugang died. He was probably eaten by wild animals.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        event = CharacterLifeEvent.query.one()

        self.assertEqual(event.review_status, "approved")
        self.assertTrue(event.auto_approved)
        self.assertIsNone(event.reason)
        self.assertIn("life_event_detail_speculative", event.risk_flags)
        self.assertIn("life_event_cause_uncertain", event.risk_flags)

    def test_supported_death_cause_is_retained(self):
        mara = Character(
            novel_id=self.novel.id,
            name="Mara Vale",
            review_status="approved",
        )
        db.session.add(mara)
        self.chapter.content = "Mara Vale was killed by the silver blade."
        db.session.commit()

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="Mara Vale",
                    event_type="death",
                    description="Mara Vale was killed.",
                    reason="killed by the silver blade",
                    evidence="Mara Vale was killed by the silver blade.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        event = CharacterLifeEvent.query.one()

        self.assertEqual(event.review_status, "approved")
        self.assertEqual(event.reason, "killed by the silver blade")
        self.assertNotIn("life_event_cause_unsupported", event.risk_flags)

    def test_ai_life_event_description_alone_cannot_prove_unsupported_cause(self):
        mara = Character(
            novel_id=self.novel.id,
            name="Mara Vale",
            review_status="approved",
        )
        db.session.add(mara)
        self.chapter.content = "Mara Vale died in the hall."
        db.session.commit()

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="Mara Vale",
                    event_type="death",
                    description="Mara Vale was poisoned by the duke.",
                    reason="poisoned by the duke",
                    evidence="Mara Vale died in the hall.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        event = CharacterLifeEvent.query.one()

        self.assertEqual(event.review_status, "approved")
        self.assertIsNone(event.description)
        self.assertIsNone(event.reason)
        self.assertIn("life_event_detail_unsupported", event.risk_flags)
        self.assertIn("life_event_cause_unsupported", event.risk_flags)

    def test_event_sequence_does_not_establish_death_cause(self):
        mara = Character(
            novel_id=self.novel.id,
            name="Mara Vale",
            review_status="approved",
        )
        db.session.add(mara)
        self.chapter.content = "Mara Vale fell from the tower. Mara Vale died."
        db.session.commit()

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="Mara Vale",
                    event_type="death",
                    description="Mara Vale died.",
                    reason="fell from the tower",
                    evidence="Mara Vale died.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        event = CharacterLifeEvent.query.one()

        self.assertEqual(event.review_status, "approved")
        self.assertIsNone(event.reason)
        self.assertIn("life_event_cause_unsupported", event.risk_flags)

    def test_local_pronoun_death_attribution_can_approve_when_unambiguous(self):
        wang = Character(
            novel_id=self.novel.id,
            name="Wang Youcai",
            review_status="approved",
        )
        db.session.add(wang)
        self.chapter.content = 'What happened to Wang Youcai? "He died."'
        db.session.commit()

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="Wang Youcai",
                    event_type="death",
                    description="Wang Youcai died.",
                    reason=None,
                    evidence='"He died."',
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        event = CharacterLifeEvent.query.one()

        self.assertEqual(event.review_status, "approved")
        self.assertTrue(event.auto_approved)

    def test_ambiguous_pronoun_death_attribution_stays_pending(self):
        zhao = Character(
            novel_id=self.novel.id,
            name="Zhao Wugang",
            review_status="approved",
        )
        lu_hong = Character(
            novel_id=self.novel.id,
            name="Lu Hong",
            review_status="approved",
        )
        db.session.add_all([zhao, lu_hong])
        self.chapter.content = "Zhao Wugang fought Lu Hong. He died after the battle."
        db.session.commit()

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="Zhao Wugang",
                    event_type="death",
                    description="Zhao Wugang died.",
                    reason=None,
                    evidence="He died after the battle.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        event = CharacterLifeEvent.query.one()

        self.assertEqual(event.review_status, "pending")
        self.assertFalse(event.auto_approved)
        self.assertIn("life_event_attribution_uncertain", event.risk_flags)

    def test_serious_flags_block_new_full_name_character_auto_approval(self):
        validation = validate_extracted_fact(
            ValidationContext(
                novel=self.novel,
                chapter=self.chapter,
                fact_type="character",
                entity_name="Wang Youcai",
                value="Wang Youcai",
                evidence="Wang Youcai might appear later in the chapter.",
                character=Character(
                    novel_id=self.novel.id,
                    name="Wang Youcai",
                ),
                entity_origin="newly_created_this_chapter",
                source_extractors={"character"},
            )
        )

        self.assertFalse(validation.auto_approved)
        self.assertIn("future_statement", validation.risk_flags)

    def test_possible_duplicate_blocks_new_full_name_character_auto_approval(self):
        validation = validate_extracted_fact(
            ValidationContext(
                novel=self.novel,
                chapter=self.chapter,
                fact_type="character",
                entity_name="Wang Youcai",
                value="Wang Youcai",
                evidence="Wang Youcai appeared in the chapter.",
                character=Character(
                    novel_id=self.novel.id,
                    name="Wang Youcai",
                ),
                entity_origin="newly_created_this_chapter",
                source_extractors={"character"},
                existing_record=Character(
                    novel_id=self.novel.id,
                    name="Wang Youcai",
                ),
            )
        )

        self.assertFalse(validation.auto_approved)
        self.assertIn("possible_duplicate", validation.risk_flags)

    def test_serious_flags_block_new_entity_auto_approval(self):
        validation = validate_extracted_fact(
            ValidationContext(
                novel=self.novel,
                chapter=self.chapter,
                fact_type="item",
                entity_name="Spirit Condensing Pill",
                value="Spirit Condensing Pill",
                evidence="Meng Hao could later obtain a Spirit Condensing Pill.",
                item=Item(
                    novel_id=self.novel.id,
                    name="Spirit Condensing Pill",
                    category="Pill",
                ),
                entity_origin="newly_created_this_chapter",
                source_extractors={"item", "character_item"},
            )
        )

        self.assertIn("future_statement", validation.risk_flags)
        self.assertFalse(validation.auto_approved)

    def test_as_if_comparison_does_not_trigger_future_statement(self):
        validation = validate_extracted_fact(
            ValidationContext(
                novel=self.novel,
                chapter=self.chapter,
                fact_type="character_item",
                entity_name="Li Furui - Dry Spirit Pill",
                value="Dry Spirit Pill",
                evidence="Fatty threw him the Dry Spirit Pill as if it were a hot potato.",
                character=self.character,
                item=Item(
                    novel_id=self.novel.id,
                    name="Dry Spirit Pill",
                    category="Pill",
                ),
                entity_origin="existing_before_extraction",
                source_extractors={"character_item", "item"},
            )
        )

        self.assertNotIn("future_statement", validation.risk_flags)

    def test_serious_flags_block_new_named_skill_auto_approval(self):
        validation = validate_extracted_fact(
            ValidationContext(
                novel=self.novel,
                chapter=self.chapter,
                fact_type="skill",
                entity_name="Fireball Spell",
                value="Fireball Spell",
                evidence="Meng Hao could later learn the Fireball Spell.",
                skill=Skill(
                    novel_id=self.novel.id,
                    name="Fireball Spell",
                    category="Spell",
                ),
                entity_origin="newly_created_this_chapter",
                source_extractors={"skill"},
            )
        )

        self.assertIn("future_statement", validation.risk_flags)
        self.assertFalse(validation.auto_approved)

    def test_possible_duplicate_blocks_new_named_item_auto_approval(self):
        validation = validate_extracted_fact(
            ValidationContext(
                novel=self.novel,
                chapter=self.chapter,
                fact_type="item",
                entity_name="Copper Mirror",
                value="Copper Mirror",
                evidence="Meng Hao obtained the Copper Mirror.",
                item=Item(
                    novel_id=self.novel.id,
                    name="Copper Mirror",
                    category="Artifact",
                ),
                entity_origin="newly_created_this_chapter",
                source_extractors={"item"},
                existing_record=Item(
                    novel_id=self.novel.id,
                    name="Copper Mirror",
                    category="Artifact",
                ),
            )
        )

        self.assertIn("possible_duplicate", validation.risk_flags)
        self.assertFalse(validation.auto_approved)

    def test_near_breakthrough_is_flagged_by_validator(self):
        validation = validate_extracted_fact(
            ValidationContext(
                novel=self.novel,
                chapter=self.chapter,
                fact_type="progression",
                entity_name="Meng Hao",
                value="fourth level of Qi Condensation",
                evidence="Meng Hao was almost at the fourth level of Qi Condensation.",
                character=self.character,
                source_extractors={"progression"},
            )
        )

        self.assertFalse(validation.auto_approved)
        self.assertIn("speculative_statement", validation.risk_flags)

    def test_item_ownership_extracted_into_character_items(self):
        item = Item(
            novel_id=self.novel.id,
            name="Copper Mirror",
            category="Artifact",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Copper Mirror",
                    relationship_type="obtained",
                    description="Meng Hao obtained the Copper Mirror.",
                    evidence="Meng Hao obtained the Copper Mirror.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.character.name, "Meng Hao")
        self.assertEqual(relationship.item.name, "Copper Mirror")
        self.assertEqual(relationship.relationship_type, "obtained")
        self.assertEqual(relationship.review_status, "approved")

    def test_character_item_demand_does_not_prove_lost_relationship(self):
        item = Item(
            novel_id=self.novel.id,
            name="Jade Gourd",
            category="Artifact",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Jade Gourd",
                    relationship_type="lost",
                    description="Meng Hao lost the Jade Gourd.",
                    evidence='Wang Tengfei said to Meng Hao, "Hand over your treasures."',
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertFalse(relationship.auto_approved)
        self.assertIn("relationship_vague_item_reference", relationship.risk_flags)
        self.assertIn("relationship_intent_only", relationship.risk_flags)

    def test_character_item_appearance_does_not_prove_received_relationship(self):
        item = Item(
            novel_id=self.novel.id,
            name="Purple Jade Slip",
            category="Artifact",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Purple Jade Slip",
                    relationship_type="received",
                    description="Meng Hao received the Purple Jade Slip.",
                    evidence="A Purple Jade Slip appeared next to Meng Hao.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertFalse(relationship.auto_approved)
        self.assertIn("relationship_action_not_proven", relationship.risk_flags)

    def test_character_item_vague_treasures_do_not_prove_specific_relationship(self):
        item = Item(
            novel_id=self.novel.id,
            name="Jade Gourd",
            category="Artifact",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Jade Gourd",
                    relationship_type="lost",
                    description="Meng Hao lost the Jade Gourd.",
                    evidence="Meng Hao handed over his treasures.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertFalse(relationship.auto_approved)
        self.assertIn("relationship_vague_item_reference", relationship.risk_flags)

    def test_character_item_intention_does_not_prove_used_relationship(self):
        item = Item(
            novel_id=self.novel.id,
            name="Copper Mirror",
            category="Artifact",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Copper Mirror",
                    relationship_type="used",
                    description="Meng Hao used the Copper Mirror.",
                    evidence="Meng Hao was about to use the Copper Mirror.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertFalse(relationship.auto_approved)
        self.assertIn("relationship_intent_only", relationship.risk_flags)

    def test_character_item_clear_transfer_approves_gave_relationship(self):
        item = Item(
            novel_id=self.novel.id,
            name="Jade Slip",
            category="Artifact",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Jade Slip",
                    relationship_type="gave",
                    description="Meng Hao gave the Jade Slip.",
                    evidence="Meng Hao handed the Jade Slip to Elder Xu.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)

    def test_character_item_clear_use_approves_used_relationship(self):
        item = Item(
            novel_id=self.novel.id,
            name="Dry Spirit Pill",
            category="Pill",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Dry Spirit Pill",
                    relationship_type="used",
                    description="Meng Hao used the Dry Spirit Pill.",
                    evidence="Meng Hao swallowed the Dry Spirit Pill.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)

    def test_character_item_clear_possession_approves_owns_relationship(self):
        item = Item(
            novel_id=self.novel.id,
            name="Copper Mirror",
            category="Artifact",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Copper Mirror",
                    relationship_type="owns",
                    description="Meng Hao owns the Copper Mirror.",
                    evidence="Meng Hao had the Copper Mirror in his bag.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)

    def test_character_item_ambiguous_pronoun_stays_pending(self):
        self.set_chapter_content(
            "Meng Hao stood beside Lu Hong. He swallowed the Dry Spirit Pill."
        )
        item = Item(
            novel_id=self.novel.id,
            name="Dry Spirit Pill",
            category="Pill",
            review_status="approved",
        )
        db.session.add(item)
        db.session.add(
            Character(
                novel_id=self.novel.id,
                name="Lu Hong",
                review_status="approved",
            )
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Dry Spirit Pill",
                    relationship_type="used",
                    description="Meng Hao used the Dry Spirit Pill.",
                    evidence="He swallowed the Dry Spirit Pill.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertFalse(relationship.auto_approved)
        self.assertIn("relationship_attribution_uncertain", relationship.risk_flags)

    def test_character_item_pronoun_attribution_can_use_clear_local_context(self):
        self.set_chapter_content(
            "Meng Hao picked up the Dry Spirit Pill. He swallowed the Dry Spirit Pill."
        )
        item = Item(
            novel_id=self.novel.id,
            name="Dry Spirit Pill",
            category="Pill",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Dry Spirit Pill",
                    relationship_type="used",
                    description="Meng Hao used the Dry Spirit Pill.",
                    evidence="He swallowed the Dry Spirit Pill.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertNotIn("relationship_attribution_uncertain", relationship.risk_flags)

    def test_character_item_pronoun_item_can_use_clear_local_context(self):
        self.set_chapter_content(
            "Meng Hao took out the Dry Spirit Pill. He swallowed it down."
        )
        item = Item(
            novel_id=self.novel.id,
            name="Dry Spirit Pill",
            category="Pill",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Dry Spirit Pill",
                    relationship_type="used",
                    description="Meng Hao used the Dry Spirit Pill.",
                    evidence="He swallowed it down.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertIn("relationship_context_supported", relationship.risk_flags)

    def test_character_item_ambiguous_item_context_stays_pending(self):
        self.set_chapter_content(
            "Meng Hao held the Dry Spirit Pill and the Blood Pill. He swallowed it down."
        )
        dry = Item(
            novel_id=self.novel.id,
            name="Dry Spirit Pill",
            category="Pill",
            review_status="approved",
        )
        blood = Item(
            novel_id=self.novel.id,
            name="Blood Pill",
            category="Pill",
            review_status="approved",
        )
        db.session.add_all([dry, blood])
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Dry Spirit Pill",
                    relationship_type="used",
                    description="Meng Hao used the Dry Spirit Pill.",
                    evidence="He swallowed it down.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertFalse(relationship.auto_approved)
        self.assertIn("relationship_context_ambiguous", relationship.risk_flags)
        self.assertIn("relationship_item_uncertain", relationship.risk_flags)

    def test_character_item_appeared_in_hands_alone_stays_pending(self):
        self.set_chapter_content("A gray bag appeared in Meng Hao's hands.")
        item = Item(
            novel_id=self.novel.id,
            name="bag of holding",
            category="Artifact",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="bag of holding",
                    relationship_type="obtained",
                    description="Meng Hao obtained the bag of holding.",
                    evidence="A gray bag appeared in Meng Hao's hands.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertFalse(relationship.auto_approved)
        self.assertIn("relationship_action_not_proven", relationship.risk_flags)

    def test_character_item_bestowed_upon_context_supports_received(self):
        self.set_chapter_content(
            "Sister Xu stood before the crowd. The elder bestowed a Wind Pennant upon her."
        )
        xu = Character(
            novel_id=self.novel.id,
            name="Elder Sister Xu",
            review_status="approved",
        )
        item = Item(
            novel_id=self.novel.id,
            name="Wind Pennant",
            category="Artifact",
            review_status="approved",
        )
        db.session.add_all([xu, item])
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Elder Sister Xu",
                    item_name="Wind Pennant",
                    relationship_type="received",
                    description="Elder Sister Xu received the Wind Pennant.",
                    evidence="The elder bestowed a Wind Pennant upon her.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertIn("relationship_context_supported", relationship.risk_flags)

    def test_character_item_picked_it_up_uses_context_for_item_identity(self):
        self.set_chapter_content("The Copper Mirror lay on the ground. Meng Hao picked it up.")
        item = Item(
            novel_id=self.novel.id,
            name="Copper Mirror",
            category="Artifact",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    item_name="Copper Mirror",
                    relationship_type="obtained",
                    description="Meng Hao obtained the Copper Mirror.",
                    evidence="Meng Hao picked it up.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertIn("relationship_context_supported", relationship.risk_flags)

    def test_character_skill_mention_alone_does_not_approve_link(self):
        skill = Skill(
            novel_id=self.novel.id,
            name="Wind Blade Technique",
            category="Technique",
            review_status="approved",
        )
        db.session.add(skill)
        db.session.commit()
        self.set_chapter_content("Meng Hao thought about the Wind Blade Technique.")

        extraction = self.empty_extraction(
            character_skills=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    skill_name="Wind Blade Technique",
                    relationship_type="has",
                    description="Meng Hao has the Wind Blade Technique.",
                    evidence="Meng Hao thought about the Wind Blade Technique.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterSkill.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertFalse(relationship.auto_approved)
        self.assertIn("relationship_action_not_proven", relationship.risk_flags)

    def test_character_skill_practice_approves_link(self):
        skill = Skill(
            novel_id=self.novel.id,
            name="Wind Blade Technique",
            category="Technique",
            review_status="approved",
        )
        db.session.add(skill)
        db.session.commit()
        self.set_chapter_content("Meng Hao practiced the Wind Blade Technique.")

        extraction = self.empty_extraction(
            character_skills=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    skill_name="Wind Blade Technique",
                    relationship_type="has",
                    description="Meng Hao has the Wind Blade Technique.",
                    evidence="Meng Hao practiced the Wind Blade Technique.",
                )
            ],
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterSkill.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)

    def test_relationship_explicit_actor_and_explicit_item_approves(self):
        self.set_chapter_content("Aria picked up the silver ring.")
        aria = Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved")
        db.session.add_all(
            [
                aria,
                CharacterAlias(character=aria, alias="Aria", first_seen_chapter_id=self.chapter.id),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver ring",
                    relationship_type="obtained",
                    description="Aria Vale obtained the silver ring.",
                    evidence="Aria picked up the silver ring.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)

    def test_relationship_pronoun_actor_and_explicit_item_approves_when_clear(self):
        self.set_chapter_content("Aria Vale entered the vault. She picked up the silver ring.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver ring",
                    relationship_type="obtained",
                    description="Aria Vale obtained the silver ring.",
                    evidence="She picked up the silver ring.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertIn("relationship_context_supported", relationship.risk_flags)

    def test_relationship_pronoun_actor_continuity_crosses_more_than_one_sentence(self):
        self.set_chapter_content(
            "Aria Vale entered the vault alone. "
            "She opened the lacquered box. "
            "She swallowed the silver pill."
        )
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver pill", category="Pill", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver pill",
                    relationship_type="used",
                    description="Aria Vale used the silver pill.",
                    evidence="She swallowed the silver pill.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertIn("relationship_context_supported", relationship.risk_flags)

    def test_relationship_explicit_actor_and_pronoun_item_approves_when_clear(self):
        self.set_chapter_content("The silver ring lay on the floor. Aria Vale picked it up.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver ring",
                    relationship_type="obtained",
                    description="Aria Vale obtained the silver ring.",
                    evidence="Aria Vale picked it up.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertIn("relationship_context_supported", relationship.risk_flags)

    def test_relationship_pronoun_item_continuity_crosses_more_than_one_sentence(self):
        self.set_chapter_content(
            "The silver ring lay on the floor. "
            "Its surface glimmered faintly. "
            "Aria Vale picked it up."
        )
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver ring",
                    relationship_type="obtained",
                    description="Aria Vale obtained the silver ring.",
                    evidence="Aria Vale picked it up.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertIn("relationship_context_supported", relationship.risk_flags)

    def test_relationship_pronoun_actor_and_pronoun_item_approves_when_clear(self):
        self.set_chapter_content("Aria Vale saw the silver ring on the floor. She picked it up.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver ring",
                    relationship_type="obtained",
                    description="Aria Vale obtained the silver ring.",
                    evidence="She picked it up.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertIn("relationship_context_supported", relationship.risk_flags)

    def test_relationship_ambiguous_actor_remains_pending(self):
        self.set_chapter_content("Aria Vale stood beside Mira Stone. She picked up the silver ring.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Character(novel_id=self.novel.id, name="Mira Stone", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver ring",
                    relationship_type="obtained",
                    description="Aria Vale obtained the silver ring.",
                    evidence="She picked up the silver ring.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_actor_unresolved", relationship.risk_flags)
        self.assertIn("relationship_pronoun_ambiguous", relationship.risk_flags)

    def test_relationship_ambiguous_target_remains_pending(self):
        self.set_chapter_content("Aria Vale saw the silver ring and the copper ring. She picked it up.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
                Item(novel_id=self.novel.id, name="copper ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver ring",
                    relationship_type="obtained",
                    description="Aria Vale obtained the silver ring.",
                    evidence="She picked it up.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_action_not_proven", relationship.risk_flags)

    def test_relationship_handed_to_named_recipient_approves_received(self):
        self.set_chapter_content("Aria Vale handed the silver ring to Mira Stone.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Character(novel_id=self.novel.id, name="Mira Stone", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Mira Stone",
                    item_name="silver ring",
                    relationship_type="received",
                    description="Mira Stone received the silver ring.",
                    evidence="Aria Vale handed the silver ring to Mira Stone.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)

    def test_relationship_flew_into_named_hand_approves_received(self):
        self.set_chapter_content("The silver ring flew into Mira Stone's hand.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Mira Stone", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Mira Stone",
                    item_name="silver ring",
                    relationship_type="received",
                    description="Mira Stone received the silver ring.",
                    evidence="The silver ring flew into Mira Stone's hand.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)

    def test_relationship_snatched_from_named_owner_approves_lost(self):
        self.set_chapter_content("Aria Vale snatched the silver ring from Mira Stone.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Character(novel_id=self.novel.id, name="Mira Stone", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Mira Stone",
                    item_name="silver ring",
                    relationship_type="lost",
                    description="Mira Stone lost the silver ring.",
                    evidence="Aria Vale snatched the silver ring from Mira Stone.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)

    def test_relationship_skill_pronoun_target_approves_when_context_is_unique(self):
        self.set_chapter_content("Aria Vale studied the Wind Blade Technique. She practiced it at dawn.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Skill(novel_id=self.novel.id, name="Wind Blade Technique", category="Technique", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_skills=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    skill_name="Wind Blade Technique",
                    relationship_type="has",
                    description="Aria Vale practiced the Wind Blade Technique.",
                    evidence="She practiced it at dawn.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterSkill.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)

    def test_relationship_threat_does_not_prove_loss(self):
        self.set_chapter_content("Aria Vale held the silver ring. The guard demanded that she hand over the silver ring.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver ring",
                    relationship_type="lost",
                    description="Aria Vale lost the silver ring.",
                    evidence="The guard demanded that she hand over the silver ring.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_intent_only", relationship.risk_flags)

    def test_relationship_future_intent_does_not_prove_use(self):
        self.set_chapter_content("Aria Vale would use the silver ring later.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver ring",
                    relationship_type="used",
                    description="Aria Vale used the silver ring.",
                    evidence="Aria Vale would use the silver ring later.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("future_statement", relationship.risk_flags)
        self.assertIn("relationship_intent_only", relationship.risk_flags)

    def test_relationship_skill_cast_action_approves(self):
        self.set_chapter_content("Aria Vale cast the Wind Blade Technique.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Skill(novel_id=self.novel.id, name="Wind Blade Technique", category="Technique", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_skills=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    skill_name="Wind Blade Technique",
                    relationship_type="has",
                    description="Aria Vale used the Wind Blade Technique.",
                    evidence="Aria Vale cast the Wind Blade Technique.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterSkill.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)

    def test_relationship_transfer_sentence_approves_giver_and_receiver(self):
        self.set_chapter_content("Aria Vale handed the silver ring to Mira Stone.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Character(novel_id=self.novel.id, name="Mira Stone", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver ring",
                    relationship_type="gave",
                    description="Aria Vale gave the silver ring.",
                    evidence="Aria Vale handed the silver ring to Mira Stone.",
                ),
                SimpleNamespace(
                    character_name="Mira Stone",
                    item_name="silver ring",
                    relationship_type="received",
                    description="Mira Stone received the silver ring.",
                    evidence="Aria Vale handed the silver ring to Mira Stone.",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationships = CharacterItem.query.order_by(CharacterItem.relationship_type).all()

        self.assertEqual(len(relationships), 2)
        self.assertTrue(all(relationship.review_status == "approved" for relationship in relationships))
        self.assertEqual(
            {(relationship.character.name, relationship.relationship_type) for relationship in relationships},
            {("Aria Vale", "gave"), ("Mira Stone", "received")},
        )

    def test_relationship_transfer_direction_blocks_wrong_receiver(self):
        self.set_chapter_content("Aria Vale handed the silver ring to Mira Stone.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Character(novel_id=self.novel.id, name="Mira Stone", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver ring",
                    relationship_type="received",
                    description="Aria Vale received the silver ring.",
                    evidence="Aria Vale handed the silver ring to Mira Stone.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_action_not_proven", relationship.risk_flags)

    def test_relationship_action_on_different_item_does_not_approve_target(self):
        self.set_chapter_content("Aria Vale saw the silver ring. She picked up the copper ring.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
                Item(novel_id=self.novel.id, name="copper ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver ring",
                    relationship_type="obtained",
                    description="Aria Vale obtained the silver ring.",
                    evidence="She picked up the copper ring.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_action_not_proven", relationship.risk_flags)

    def test_relationship_count_noun_one_resolves_unique_item(self):
        self.set_chapter_content("The rack held a red pill. Aria Vale picked one up.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="red pill", category="Pill", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="red pill",
                    relationship_type="obtained",
                    description="Aria Vale obtained the red pill.",
                    evidence="Aria Vale picked one up.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertIn("relationship_context_supported", relationship.risk_flags)

    def test_relationship_negated_use_does_not_approve(self):
        self.set_chapter_content("Aria Vale did not use the silver ring.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver ring",
                    relationship_type="used",
                    description="Aria Vale used the silver ring.",
                    evidence="Aria Vale did not use the silver ring.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_action_not_proven", relationship.risk_flags)

    def test_relationship_attempted_use_does_not_approve(self):
        self.set_chapter_content("Aria Vale tried to use the silver ring.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver ring",
                    relationship_type="used",
                    description="Aria Vale used the silver ring.",
                    evidence="Aria Vale tried to use the silver ring.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_intent_only", relationship.risk_flags)

    def test_relationship_skill_pronoun_activation_approves_when_unique(self):
        self.set_chapter_content("Aria Vale studied the Wind Blade Technique. She activated it at dawn.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Skill(novel_id=self.novel.id, name="Wind Blade Technique", category="Technique", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_skills=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    skill_name="Wind Blade Technique",
                    relationship_type="has",
                    description="Aria Vale activated the Wind Blade Technique.",
                    evidence="She activated it at dawn.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterSkill.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)

    def test_character_skill_has_from_trained_possessive_skill(self):
        self.set_chapter_content("Aria Vale spent the month training. She trained her Flame Serpent Art.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Skill(novel_id=self.novel.id, name="Flame Serpent Art", category="Art", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_skills=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    skill_name="Flame Serpent Art",
                    relationship_type="has",
                    description="Aria Vale trained the Flame Serpent Art.",
                    evidence="She trained her Flame Serpent Art.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterSkill.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertNotIn("relationship_action_not_proven", relationship.risk_flags)

    def test_character_skill_watching_another_actor_use_skill_stays_pending(self):
        self.set_chapter_content("Aria Vale watched Bob Stone activate the Water Globe.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Character(novel_id=self.novel.id, name="Bob Stone", review_status="approved"),
                Skill(novel_id=self.novel.id, name="Water Globe", category="Spell", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_skills=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    skill_name="Water Globe",
                    relationship_type="has",
                    description="Aria Vale used Water Globe.",
                    evidence="Aria Vale watched Bob Stone activate the Water Globe.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterSkill.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertFalse(relationship.auto_approved)
        self.assertIn("relationship_action_not_proven", relationship.risk_flags)

    def test_relationship_storage_proves_possession_not_new_acquisition(self):
        self.set_chapter_content("Aria Vale put her sword into her bag.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="sword", category="Weapon", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="sword",
                    relationship_type="obtained",
                    description="Aria Vale obtained the sword.",
                    evidence="Aria Vale put her sword into her bag.",
                ),
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="sword",
                    relationship_type="owns",
                    description="Aria Vale possessed the sword.",
                    evidence="Aria Vale put her sword into her bag.",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationships = {
            relationship.relationship_type: relationship
            for relationship in CharacterItem.query.all()
        }

        self.assertEqual(relationships["obtained"].review_status, "pending")
        self.assertIn("relationship_action_not_proven", relationships["obtained"].risk_flags)
        self.assertEqual(relationships["owns"].review_status, "approved")
        self.assertTrue(relationships["owns"].auto_approved)

    def test_relationship_pocketed_object_supports_possession(self):
        self.set_chapter_content("Aria Vale pocketed the silver token.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver token", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver token",
                    relationship_type="owns",
                    description="Aria Vale possessed the silver token.",
                    evidence="Aria Vale pocketed the silver token.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)

    def test_relationship_theft_supports_correct_gain_and_loss_direction(self):
        self.set_chapter_content("Aria Vale stole the silver sword from Mira Stone.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Character(novel_id=self.novel.id, name="Mira Stone", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver sword", category="Weapon", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver sword",
                    relationship_type="obtained",
                    description="Aria Vale obtained the silver sword.",
                    evidence="Aria Vale stole the silver sword from Mira Stone.",
                ),
                SimpleNamespace(
                    character_name="Mira Stone",
                    item_name="silver sword",
                    relationship_type="lost",
                    description="Mira Stone lost the silver sword.",
                    evidence="Aria Vale stole the silver sword from Mira Stone.",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationships = CharacterItem.query.all()

        self.assertEqual(len(relationships), 2)
        self.assertTrue(all(relationship.review_status == "approved" for relationship in relationships))

    def test_relationship_later_holding_does_not_prove_loss(self):
        self.set_chapter_content("Mira Stone carried the silver sword. Later, Aria Vale held the silver sword.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Mira Stone", review_status="approved"),
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver sword", category="Weapon", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Mira Stone",
                    item_name="silver sword",
                    relationship_type="lost",
                    description="Mira Stone lost the silver sword.",
                    evidence="Later, Aria Vale held the silver sword.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_action_not_proven", relationship.risk_flags)

    def test_relationship_destination_into_hand_supports_receipt(self):
        self.set_chapter_content("Aria Vale stood still. The jade slip flew into her hand.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="jade slip", category="Manual", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="jade slip",
                    relationship_type="received",
                    description="Aria Vale received the jade slip.",
                    evidence="The jade slip flew into her hand.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertIn("relationship_context_supported", relationship.risk_flags)

    def test_relationship_flew_past_hand_does_not_support_receipt(self):
        self.set_chapter_content("Aria Vale stood still. The jade slip flew past her hand.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="jade slip", category="Manual", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="jade slip",
                    relationship_type="received",
                    description="Aria Vale received the jade slip.",
                    evidence="The jade slip flew past her hand.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_action_not_proven", relationship.risk_flags)

    def test_relationship_looked_at_item_does_not_support_use(self):
        self.set_chapter_content("Aria Vale looked at the silver pill.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver pill", category="Pill", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver pill",
                    relationship_type="used",
                    description="Aria Vale used the silver pill.",
                    evidence="Aria Vale looked at the silver pill.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_action_not_proven", relationship.risk_flags)

    def test_relationship_almost_swallowed_does_not_support_use(self):
        self.set_chapter_content("Aria Vale almost swallowed the silver pill.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver pill", category="Pill", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="silver pill",
                    relationship_type="used",
                    description="Aria Vale used the silver pill.",
                    evidence="Aria Vale almost swallowed the silver pill.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_intent_only", relationship.risk_flags)

    def test_relationship_tight_coreference_chain_supports_possession(self):
        self.set_chapter_content(
            "Aria Vale picked up the Ancient Bronze Mirror. "
            "He examined the mirror. He put it into his robe."
        )
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="Ancient Bronze Mirror", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="Ancient Bronze Mirror",
                    relationship_type="owns",
                    description="Aria Vale possessed the Ancient Bronze Mirror.",
                    evidence="He examined the mirror. He put it into his robe.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertIn("relationship_context_supported", relationship.risk_flags)

    def test_relationship_ambiguous_shorthand_mirror_stays_pending(self):
        self.set_chapter_content(
            "Aria Vale held a bronze mirror and a silver mirror. He put the mirror into his robe."
        )
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="bronze mirror", category="Artifact", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver mirror", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="bronze mirror",
                    relationship_type="obtained",
                    description="Aria Vale obtained the bronze mirror.",
                    evidence="He put the mirror into his robe.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_context_ambiguous", relationship.risk_flags)

    def test_relationship_possessive_grammar_preserves_giver_receiver_roles(self):
        self.set_chapter_content("Alice Vale handed Bob Stone her sword.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Alice Vale", review_status="approved"),
                Character(novel_id=self.novel.id, name="Bob Stone", review_status="approved"),
                Item(novel_id=self.novel.id, name="sword", category="Weapon", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Alice Vale",
                    item_name="sword",
                    relationship_type="gave",
                    description="Alice Vale gave the sword.",
                    evidence="Alice Vale handed Bob Stone her sword.",
                ),
                SimpleNamespace(
                    character_name="Bob Stone",
                    item_name="sword",
                    relationship_type="received",
                    description="Bob Stone received the sword.",
                    evidence="Alice Vale handed Bob Stone her sword.",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationships = CharacterItem.query.all()

        self.assertEqual(len(relationships), 2)
        self.assertTrue(all(relationship.review_status == "approved" for relationship in relationships))

    def test_relationship_ambiguous_count_noun_one_stays_pending(self):
        self.set_chapter_content("Aria Vale saw a red pill and a blue pill. He swallowed one in silence.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="red pill", category="Pill", review_status="approved"),
                Item(novel_id=self.novel.id, name="blue pill", category="Pill", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="red pill",
                    relationship_type="used",
                    description="Aria Vale used the red pill.",
                    evidence="He swallowed one in silence.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_context_ambiguous", relationship.risk_flags)

    def test_relationship_count_noun_one_does_not_resolve_distant_target(self):
        self.set_chapter_content("A red pill sat on the shelf. Aria Vale entered the room. He picked one up.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="red pill", category="Pill", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="red pill",
                    relationship_type="obtained",
                    description="Aria Vale obtained the red pill.",
                    evidence="He picked one up.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_target_unresolved", relationship.risk_flags)

    def test_relationship_alias_subject_outranks_competing_helper_name(self):
        self.set_chapter_content("With Alex Vale's help, Fatty swallowed the silver pill.")
        fatty = Character(novel_id=self.novel.id, name="Li Furui", review_status="approved")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Alex Vale", review_status="approved"),
                fatty,
                Item(novel_id=self.novel.id, name="silver pill", category="Pill", review_status="approved"),
            ]
        )
        db.session.flush()
        db.session.add(CharacterAlias(character=fatty, alias="Fatty", first_seen_chapter_id=self.chapter.id))
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Li Furui",
                    item_name="silver pill",
                    relationship_type="used",
                    description="Li Furui used the silver pill.",
                    evidence="With Alex Vale's help, Fatty swallowed the silver pill.",
                ),
                SimpleNamespace(
                    character_name="Alex Vale",
                    item_name="silver pill",
                    relationship_type="used",
                    description="Alex Vale used the silver pill.",
                    evidence="With Alex Vale's help, Fatty swallowed the silver pill.",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationships = {relationship.character.name: relationship for relationship in CharacterItem.query.all()}

        self.assertEqual(relationships["Li Furui"].review_status, "approved")
        self.assertEqual(relationships["Alex Vale"].review_status, "pending")
        self.assertIn("relationship_action_not_proven", relationships["Alex Vale"].risk_flags)

    def test_relationship_causal_skill_manifestation_approves_use(self):
        self.set_chapter_content("Alice Vale flicked her fingers and Water Globe appeared.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Alice Vale", review_status="approved"),
                Skill(novel_id=self.novel.id, name="Water Globe", category="Spell", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_skills=[
                SimpleNamespace(
                    character_name="Alice Vale",
                    skill_name="Water Globe",
                    relationship_type="has",
                    description="Alice Vale used Water Globe.",
                    evidence="Alice Vale flicked her fingers and Water Globe appeared.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterSkill.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)

    def test_relationship_environmental_skill_like_effect_does_not_prove_use(self):
        self.set_chapter_content("Alice Vale entered the chamber. A Water Globe floated nearby.")
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Alice Vale", review_status="approved"),
                Skill(novel_id=self.novel.id, name="Water Globe", category="Spell", review_status="approved"),
            ]
        )
        db.session.commit()

        extraction = self.empty_extraction(
            character_skills=[
                SimpleNamespace(
                    character_name="Alice Vale",
                    skill_name="Water Globe",
                    relationship_type="has",
                    description="Alice Vale used Water Globe.",
                    evidence="A Water Globe floated nearby.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterSkill.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_action_not_proven", relationship.risk_flags)

    def test_relationship_completion_guard_variants_do_not_approve(self):
        db.session.add_all(
            [
                Character(novel_id=self.novel.id, name="Aria Vale", review_status="approved"),
                Item(novel_id=self.novel.id, name="silver ring", category="Artifact", review_status="approved"),
            ]
        )
        db.session.commit()
        guarded_sentences = [
            "Aria Vale wanted to use the silver ring.",
            "Aria Vale planned to give the silver ring to Mira Stone.",
            "Aria Vale would later use the silver ring.",
            "Aria Vale was about to swallow the silver ring.",
            "Aria Vale tried to take the silver ring.",
            "Aria Vale reached for the silver ring.",
            "Aria Vale failed to activate the silver ring.",
            "Aria Vale did not use the silver ring.",
        ]

        for sentence in guarded_sentences:
            with self.subTest(sentence=sentence):
                self.set_chapter_content(sentence)
                extraction = self.empty_extraction(
                    character_items=[
                        SimpleNamespace(
                            character_name="Aria Vale",
                            item_name="silver ring",
                            relationship_type="used",
                            description="Aria Vale used the silver ring.",
                            evidence=sentence,
                        )
                    ]
                )

                save_chapter_extraction(self.novel, self.chapter, extraction)
                relationship = CharacterItem.query.one()

                self.assertEqual(relationship.review_status, "pending")
                self.assertFalse(relationship.auto_approved)
                self.assertIn("relationship_action_not_proven", relationship.risk_flags)
                db.session.delete(relationship)
                db.session.commit()

    def test_ambiguous_character_item_is_logged_as_skipped(self):
        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="the cultivator",
                    item_name="Copper Mirror",
                    relationship_type="obtained",
                    description="The cultivator obtained the Copper Mirror.",
                    evidence="The cultivator obtained the Copper Mirror.",
                )
            ],
        )

        summary = save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(CharacterItem.query.count(), 0)
        self.assertEqual(summary["skipped_extractions"][0]["reason"], "ambiguous_owner")
        self.assertEqual(summary["skipped_extractions"][0]["item_name"], "Copper Mirror")

    def test_ambiguous_owner_sent_to_review_by_validator(self):
        item = Item(
            novel_id=self.novel.id,
            name="Copper Mirror",
            category="Artifact",
            review_status="approved",
        )
        db.session.add(item)
        db.session.commit()

        validation = validate_extracted_fact(
            ValidationContext(
                novel=self.novel,
                chapter=self.chapter,
                fact_type="character_item",
                entity_name="Unknown - Copper Mirror",
                value="Copper Mirror",
                evidence="The Copper Mirror was taken.",
                item=item,
                source_extractors={"character_item"},
                ambiguous_owner=True,
            )
        )

        self.assertFalse(validation.auto_approved)
        self.assertIn("ambiguous_owner", validation.risk_flags)

    def test_duplicate_character_alias_not_recreated(self):
        alias = CharacterAlias(
            character_id=self.character.id,
            alias="Fat Teenager",
            first_seen_chapter_id=self.chapter.id,
            evidence="Fat Teenager was Meng Hao.",
        )
        db.session.add(alias)
        db.session.commit()

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Meng Hao",
                    aliases=["Fat Teenager"],
                    appearance_type="appeared",
                    metadata=SimpleNamespace(
                        age_text=None,
                        gender=None,
                        race_or_species=None,
                        origin=None,
                        faction_or_affiliation=None,
                        status=None,
                        titles=[],
                    ),
                    description="Meng Hao appears.",
                    evidence="Meng Hao, the Fat Teenager, appeared.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(CharacterAlias.query.filter_by(alias="Fat Teenager").count(), 1)

    def test_progression_agreement_counts_alias_and_canonical_character(self):
        alias = CharacterAlias(
            character_id=self.character.id,
            alias="Fat Teenager",
            first_seen_chapter_id=self.chapter.id,
            evidence="Fat Teenager was Meng Hao.",
        )
        db.session.add(alias)
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Fat Teenager",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi Condensation",
                    description="Fat Teenager reached the third level of Qi Condensation.",
                    evidence="Fat Teenager reached the third level of Qi Condensation.",
                    source_extractor="progression_extractor",
                ),
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi Condensation",
                    description="Meng Hao reached the third level of Qi Condensation.",
                    evidence="Meng Hao reached the third level of Qi Condensation.",
                    source_extractor="progression_audit",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progressions = CharacterProgressionEvent.query.filter_by(
            character_id=self.character.id,
            new_value="third level of Qi Condensation",
            source_extractor="progression_audit,progression_extractor",
        ).all()

        self.assertTrue(progressions)
        self.assertTrue(all(progression.character.name == "Meng Hao" for progression in progressions))
        self.assertTrue(
            all(
                progression.source_extractor
                == "progression_audit,progression_extractor"
                for progression in progressions
            )
        )
        self.assertTrue(
            all("attribution_uncertain" not in progression.risk_flags for progression in progressions)
        )

    def test_progression_agreement_ignores_unconfirmed_matching_source(self):
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi Condensation",
                    description="Meng Hao reached the third level of Qi Condensation.",
                    evidence="Meng Hao reached the third level of Qi Condensation.",
                    source_extractor="progression_extractor",
                ),
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi Condensation",
                    description="Meng Hao was almost at the third level of Qi Condensation.",
                    evidence="Meng Hao was almost at the third level of Qi Condensation.",
                    source_extractor="progression_audit",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.filter_by(
            new_value="third level of Qi Condensation"
        ).one()

        self.assertEqual(progression.source_extractor, "progression_extractor")
        self.assertTrue(progression.auto_approved)

    def test_progression_placeholder_values_are_skipped(self):
        for placeholder in ["unknown", "unspecified", "", None, "?", "not stated", "undetermined"]:
            with self.subTest(placeholder=placeholder):
                extraction = self.empty_extraction(
                    progression_events=[
                        SimpleNamespace(
                            character_name="Meng Hao",
                            progression_type="cultivation_level",
                            old_value=None,
                            new_value=placeholder,
                            description="Meng Hao reached an unknown state.",
                            evidence="Meng Hao reached an unknown state.",
                            source_extractor="progression_extractor",
                        )
                    ]
                )

                summary = save_chapter_extraction(self.novel, self.chapter, extraction)

                self.assertEqual(CharacterProgressionEvent.query.count(), 0)
                self.assertTrue(
                    any(
                        skipped["reason"] == "invalid_progression_placeholder"
                        for skipped in summary["skipped_extractions"]
                    )
                )
                db.session.rollback()

    def test_unfamiliar_fictional_progression_value_is_preserved(self):
        self.set_chapter_content("Aria Vale reached the Azure Crown.")
        aria = Character(
            novel_id=self.novel.id,
            name="Aria Vale",
            review_status="approved",
        )
        db.session.add(aria)
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    progression_type="power_rank",
                    old_value=None,
                    new_value="Azure Crown",
                    description="Aria Vale reached the Azure Crown.",
                    evidence="Aria Vale reached the Azure Crown.",
                    source_extractor="progression_extractor",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.new_value, "Azure Crown")
        self.assertEqual(progression.review_status, "approved")

    def test_progression_placeholder_does_not_change_current_progression_or_downgrade(self):
        existing = CharacterProgressionEvent(
            novel_id=self.novel.id,
            character_id=self.character.id,
            chapter_id=self.chapter.id,
            progression_type="cultivation_level",
            new_value="third level of Qi Condensation",
            review_status="approved",
            auto_approved=True,
        )
        db.session.add(existing)
        db.session.commit()
        recalculate_character_current_progression(self.character, "cultivation_level")
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="unknown",
                    description="Meng Hao's level was unknown.",
                    evidence="Meng Hao's level was unknown.",
                    source_extractor="progression_audit",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(CharacterProgressionEvent.query.count(), 1)
        self.assertEqual(self.character.current_cultivation_level, "third level of Qi Condensation")
        self.assertIsNone(CharacterProgressionEvent.query.one().review_warnings)

    def test_progression_placeholder_source_does_not_interfere_with_valid_source(self):
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="unknown",
                    description="Meng Hao's level was unknown.",
                    evidence="Meng Hao's level was unknown.",
                    source_extractor="progression_extractor",
                ),
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi Condensation",
                    description="Meng Hao reached the third level of Qi Condensation.",
                    evidence="Meng Hao reached the third level of Qi Condensation.",
                    source_extractor="progression_audit",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.new_value, "third level of Qi Condensation")
        self.assertEqual(progression.source_extractor, "progression_audit")

    def test_same_run_duplicate_progression_merges_sources_into_one_row(self):
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi Condensation",
                    description="Meng Hao reached the third level of Qi Condensation.",
                    evidence="Meng Hao reached the third level of Qi Condensation.",
                    source_extractor="legacy_extractor",
                ),
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi Condensation",
                    description="Meng Hao reached the third level of Qi Condensation.",
                    evidence="Meng Hao reached the third level of Qi Condensation.",
                    source_extractor="progression_audit",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.new_value, "third level of Qi Condensation")
        self.assertEqual(progression.source_extractor, "legacy_extractor,progression_audit")
        self.assertEqual(CharacterProgressionEvent.query.count(), 1)

    def test_same_run_semantic_progression_variants_merge_sources_and_preserve_evidence(self):
        self.set_chapter_content(
            "Meng Hao reached peak of the second level. "
            "Meng Hao reached peak second level."
        )
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="peak of the second level",
                    description="Meng Hao reached peak of the second level.",
                    evidence="Meng Hao reached peak of the second level.",
                    source_extractor="progression_extractor",
                ),
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="peak second level",
                    description="Meng Hao reached peak second level.",
                    evidence="Meng Hao reached peak second level.",
                    source_extractor="progression_audit",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()
        evidence_rows = WikiEvidence.query.filter_by(
            entity_type="progression",
            entity_id=progression.id,
        ).order_by(WikiEvidence.id).all()

        self.assertEqual(progression.new_value, "peak of the second level")
        self.assertEqual(progression.source_extractor, "progression_audit,progression_extractor")
        self.assertEqual(CharacterProgressionEvent.query.count(), 1)
        self.assertEqual(
            [row.evidence_text for row in evidence_rows],
            [
                "Meng Hao reached peak of the second level.",
                "Meng Hao reached peak second level.",
            ],
        )

    def test_same_run_pending_duplicate_progression_merges_sources_into_one_row(self):
        self.set_chapter_content("he had broken through the first level of Qi condensation into the second.")

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value="first level of Qi Condensation",
                    new_value="second level of Qi Condensation",
                    description="Meng Hao broke through to the second level.",
                    evidence="he had broken through the first level of Qi condensation into the second.",
                    source_extractor="legacy_extractor",
                ),
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value="first level of Qi Condensation",
                    new_value="second level of Qi Condensation",
                    description="Meng Hao broke through to the second level.",
                    evidence="he had broken through the first level of Qi condensation into the second.",
                    source_extractor="progression_audit",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.new_value, "second level of Qi Condensation")
        self.assertEqual(progression.review_status, "pending")
        self.assertEqual(progression.source_extractor, "legacy_extractor,progression_audit")
        self.assertIn("attribution_uncertain", progression.risk_flags)
        self.assertEqual(CharacterProgressionEvent.query.count(), 1)

    def test_context_supported_pronoun_progression_auto_approved_with_ai_agreement(self):
        self.chapter.content = (
            "Meng Hao swallowed the pill and sat down to cultivate. "
            "After several hours, he had broken through into the second level."
        )
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="second level",
                    description="Meng Hao broke through into the second level.",
                    evidence="he had broken through into the second level.",
                    source_extractor="progression_extractor",
                ),
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="second level",
                    description="Meng Hao broke through into the second level.",
                    evidence="he had broken through into the second level.",
                    source_extractor="progression_audit",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)
        self.assertIn("context_supported_attribution", progression.risk_flags)
        self.assertNotIn("attribution_uncertain", progression.risk_flags)

    def test_direct_progression_subject_auto_approves(self):
        alex = Character(
            novel_id=self.novel.id,
            name="Alex Vale",
            review_status="approved",
        )
        db.session.add(alex)
        db.session.commit()
        self.set_chapter_content("Alex Vale reached the second level.")

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Alex Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="second level",
                    description="Alex Vale reached the second level.",
                    evidence="Alex Vale reached the second level.",
                    source_extractor="progression_extractor",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.filter_by(
            character_id=alex.id,
            new_value="second level",
        ).one()

        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)
        self.assertNotIn("attribution_uncertain", progression.risk_flags or "")

    def test_helper_name_does_not_beat_alias_progression_subject(self):
        alex = Character(
            novel_id=self.novel.id,
            name="Alex Vale",
            review_status="approved",
        )
        li_furui = Character(
            novel_id=self.novel.id,
            name="Li Furui",
            review_status="approved",
        )
        db.session.add_all([alex, li_furui])
        db.session.flush()
        db.session.add(
            CharacterAlias(
                character_id=li_furui.id,
                alias="Fatty",
                first_seen_chapter_id=self.chapter.id,
            )
        )
        db.session.commit()
        self.set_chapter_content("With Alex Vale's help, Fatty reached the second level.")

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Li Furui",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="second level",
                    description="Li Furui reached the second level.",
                    evidence="With Alex Vale's help, Fatty reached the second level.",
                    source_extractor="progression_extractor",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.filter_by(
            character_id=li_furui.id,
            new_value="second level",
        ).one()

        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)
        self.assertNotIn("attribution_uncertain", progression.risk_flags or "")
        self.assertIsNone(progression.review_warnings)

    def test_helper_name_candidate_stays_pending_when_not_progression_subject(self):
        alex = Character(
            novel_id=self.novel.id,
            name="Alex Vale",
            review_status="approved",
        )
        li_furui = Character(
            novel_id=self.novel.id,
            name="Li Furui",
            review_status="approved",
        )
        db.session.add_all([alex, li_furui])
        db.session.flush()
        db.session.add(
            CharacterAlias(
                character_id=li_furui.id,
                alias="Fatty",
                first_seen_chapter_id=self.chapter.id,
            )
        )
        db.session.commit()
        self.set_chapter_content("With Alex Vale's help, Fatty reached the second level.")

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Alex Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="second level",
                    description="Alex Vale reached the second level.",
                    evidence="With Alex Vale's help, Fatty reached the second level.",
                    source_extractor="progression_extractor",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.filter_by(
            character_id=alex.id,
            new_value="second level",
        ).one()

        self.assertEqual(progression.review_status, "pending")
        self.assertFalse(progression.auto_approved)
        self.assertIn("attribution_uncertain", progression.risk_flags)

    def test_possessive_pronoun_progression_uses_unique_local_antecedent(self):
        jane = Character(
            novel_id=self.novel.id,
            name="Jane Vale",
            review_status="approved",
        )
        db.session.add(jane)
        db.session.commit()
        self.set_chapter_content(
            "Jane Vale stepped forward before the elders. "
            "Her cultivation foundation was at the fourth level."
        )

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Jane Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="fourth level",
                    description="Jane Vale's cultivation foundation was at the fourth level.",
                    evidence="Her cultivation foundation was at the fourth level.",
                    source_extractor="progression_reasoning",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.filter_by(
            character_id=jane.id,
            new_value="fourth level",
        ).one()

        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)
        self.assertIn("context_supported_attribution", progression.risk_flags)

    def test_progression_pronoun_continuity_crosses_short_context(self):
        alex = Character(
            novel_id=self.novel.id,
            name="Alex Vale",
            review_status="approved",
        )
        db.session.add(alex)
        db.session.commit()
        self.set_chapter_content(
            "Alex Vale walked into the cave alone. "
            "He sat down in silence. "
            "Soon, he broke through to the third level."
        )

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Alex Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level",
                    description="Alex Vale broke through to the third level.",
                    evidence="Soon, he broke through to the third level.",
                    source_extractor="progression_reasoning",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.filter_by(
            character_id=alex.id,
            new_value="third level",
        ).one()

        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)
        self.assertIn("context_supported_attribution", progression.risk_flags)

    def test_progression_pronoun_continuity_crosses_more_than_one_prior_sentence(self):
        alex = Character(
            novel_id=self.novel.id,
            name="Alex Vale",
            review_status="approved",
        )
        db.session.add(alex)
        db.session.commit()
        self.set_chapter_content(
            "Alex Vale entered the chamber alone. "
            "He set a pill on his palm. "
            "He closed his eyes. "
            "Sure enough, he had broken through into the second level."
        )

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Alex Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="second level",
                    description="Alex Vale broke through into the second level.",
                    evidence="Sure enough, he had broken through into the second level.",
                    source_extractor="progression_extractor",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.filter_by(
            character_id=alex.id,
            new_value="second level",
        ).one()

        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)
        self.assertIn("context_supported_attribution", progression.risk_flags)
        self.assertNotIn("attribution_uncertain", progression.risk_flags)

    def test_progression_pronoun_subject_switch_stays_pending(self):
        alex = Character(
            novel_id=self.novel.id,
            name="Alex Vale",
            review_status="approved",
        )
        brian = Character(
            novel_id=self.novel.id,
            name="Brian Stone",
            review_status="approved",
        )
        db.session.add_all([alex, brian])
        db.session.commit()
        self.set_chapter_content(
            "Alex Vale entered the chamber alone. "
            "He set a pill on his palm. "
            "Brian Stone stepped between the pillars. "
            "He had broken through into the second level."
        )

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Alex Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="second level",
                    description="Alex Vale broke through into the second level.",
                    evidence="He had broken through into the second level.",
                    source_extractor="progression_extractor",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.filter_by(
            character_id=alex.id,
            new_value="second level",
        ).one()

        self.assertEqual(progression.review_status, "pending")
        self.assertFalse(progression.auto_approved)
        self.assertIn("attribution_uncertain", progression.risk_flags)

    def test_possessive_progression_chain_uses_clear_subject_not_object_name(self):
        zhao = Character(
            novel_id=self.novel.id,
            name="Zhao Wugang",
            review_status="approved",
        )
        db.session.add(zhao)
        db.session.commit()
        self.set_chapter_content(
            "Zhao Wugang stared coldly at Meng Hao. "
            "His cultivation foundation was not that of an ordinary person. "
            "It was the third level of Qi condensation."
        )

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Zhao Wugang",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi condensation",
                    description="Zhao Wugang was at the third level.",
                    evidence="It was the third level of Qi condensation.",
                    source_extractor="progression_reasoning",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.filter_by(
            character_id=zhao.id,
            new_value="third level of Qi condensation",
        ).one()

        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)
        self.assertIn("context_supported_attribution", progression.risk_flags)
        self.assertNotIn("attribution_uncertain", progression.risk_flags)

    def test_ambiguous_progression_pronoun_stays_pending(self):
        alex = Character(
            novel_id=self.novel.id,
            name="Alex Vale",
            review_status="approved",
        )
        brian = Character(
            novel_id=self.novel.id,
            name="Brian Stone",
            review_status="approved",
        )
        db.session.add_all([alex, brian])
        db.session.commit()
        self.set_chapter_content(
            "Alex Vale and Brian Stone entered the chamber. "
            "He broke through to the second level."
        )

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Alex Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="second level",
                    description="Alex Vale broke through to the second level.",
                    evidence="He broke through to the second level.",
                    source_extractor="progression_reasoning",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.filter_by(
            character_id=alex.id,
            new_value="second level",
        ).one()

        self.assertEqual(progression.review_status, "pending")
        self.assertFalse(progression.auto_approved)
        self.assertIn("attribution_uncertain", progression.risk_flags)

    def test_collective_progression_supports_each_explicit_character(self):
        self.set_chapter_content("Alice Vale and Bob Stone were both at the seventh level.")
        alice = Character(
            novel_id=self.novel.id,
            name="Alice Vale",
            review_status="approved",
        )
        bob = Character(
            novel_id=self.novel.id,
            name="Bob Stone",
            review_status="approved",
        )
        db.session.add_all([alice, bob])
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Alice Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="seventh level",
                    description="Alice Vale was at the seventh level.",
                    evidence="Alice Vale and Bob Stone were both at the seventh level.",
                    source_extractor="progression_extractor",
                ),
                SimpleNamespace(
                    character_name="Bob Stone",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="seventh level",
                    description="Bob Stone was at the seventh level.",
                    evidence="Alice Vale and Bob Stone were both at the seventh level.",
                    source_extractor="progression_extractor",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        rows = CharacterProgressionEvent.query.order_by(CharacterProgressionEvent.character_id).all()

        self.assertEqual(len(rows), 2)
        self.assertEqual({row.character.name for row in rows}, {"Alice Vale", "Bob Stone"})
        self.assertTrue(all(row.review_status == "approved" for row in rows))
        self.assertTrue(all("attribution_uncertain" not in row.risk_flags for row in rows))
        self.assertTrue(all(not row.review_warnings for row in rows))

    def test_respectively_progression_maps_ordered_characters_to_ordered_values(self):
        self.set_chapter_content("Alice Vale and Bob Stone were at the fifth and sixth levels, respectively.")
        alice = Character(
            novel_id=self.novel.id,
            name="Alice Vale",
            review_status="approved",
        )
        bob = Character(
            novel_id=self.novel.id,
            name="Bob Stone",
            review_status="approved",
        )
        db.session.add_all([alice, bob])
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Alice Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="fifth level",
                    description="Alice Vale was at the fifth level.",
                    evidence="Alice Vale and Bob Stone were at the fifth and sixth levels, respectively.",
                    source_extractor="progression_extractor",
                ),
                SimpleNamespace(
                    character_name="Bob Stone",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="sixth level",
                    description="Bob Stone was at the sixth level.",
                    evidence="Alice Vale and Bob Stone were at the fifth and sixth levels, respectively.",
                    source_extractor="progression_extractor",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        rows = CharacterProgressionEvent.query.order_by(CharacterProgressionEvent.new_value).all()

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {(row.character.name, row.new_value, row.review_status) for row in rows},
            {
                ("Alice Vale", "fifth level", "approved"),
                ("Bob Stone", "sixth level", "approved"),
            },
        )

    def test_malformed_respectively_progression_stays_pending(self):
        self.set_chapter_content("Alice Vale and Bob Stone were at the fifth level, respectively.")
        alice = Character(
            novel_id=self.novel.id,
            name="Alice Vale",
            review_status="approved",
        )
        bob = Character(
            novel_id=self.novel.id,
            name="Bob Stone",
            review_status="approved",
        )
        db.session.add_all([alice, bob])
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Alice Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="fifth level",
                    description="Alice Vale was at the fifth level.",
                    evidence="Alice Vale and Bob Stone were at the fifth level, respectively.",
                    source_extractor="progression_extractor",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.review_status, "pending")
        self.assertIn("attribution_uncertain", progression.risk_flags)

    def test_comparative_character_reference_uses_progression_subject(self):
        self.set_chapter_content("Unlike Alice Vale, Bob Stone had reached the fifth level.")
        alice = Character(
            novel_id=self.novel.id,
            name="Alice Vale",
            review_status="approved",
        )
        bob = Character(
            novel_id=self.novel.id,
            name="Bob Stone",
            review_status="approved",
        )
        db.session.add_all([alice, bob])
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Bob Stone",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="fifth level",
                    description="Bob Stone had reached the fifth level.",
                    evidence="Unlike Alice Vale, Bob Stone had reached the fifth level.",
                    source_extractor="progression_extractor",
                ),
                SimpleNamespace(
                    character_name="Alice Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="fifth level",
                    description="Alice Vale had reached the fifth level.",
                    evidence="Unlike Alice Vale, Bob Stone had reached the fifth level.",
                    source_extractor="progression_extractor",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        bob_progression = CharacterProgressionEvent.query.filter_by(
            character_id=bob.id,
            new_value="fifth level",
        ).one()
        alice_progression = CharacterProgressionEvent.query.filter_by(
            character_id=alice.id,
            new_value="fifth level",
        ).one()

        self.assertEqual(bob_progression.review_status, "approved")
        self.assertEqual(alice_progression.review_status, "pending")
        self.assertIn("attribution_uncertain", alice_progression.risk_flags)

    def test_relative_clause_progression_uses_possessor_subject(self):
        self.set_chapter_content("Alice Vale looked at Bob Stone, whose cultivation was at the fifth level.")
        alice = Character(
            novel_id=self.novel.id,
            name="Alice Vale",
            review_status="approved",
        )
        bob = Character(
            novel_id=self.novel.id,
            name="Bob Stone",
            review_status="approved",
        )
        db.session.add_all([alice, bob])
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Bob Stone",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="fifth level",
                    description="Bob Stone's cultivation was at the fifth level.",
                    evidence="Alice Vale looked at Bob Stone, whose cultivation was at the fifth level.",
                    source_extractor="progression_extractor",
                ),
                SimpleNamespace(
                    character_name="Alice Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="fifth level",
                    description="Alice Vale's cultivation was at the fifth level.",
                    evidence="Alice Vale looked at Bob Stone, whose cultivation was at the fifth level.",
                    source_extractor="progression_extractor",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        bob_progression = CharacterProgressionEvent.query.filter_by(
            character_id=bob.id,
            new_value="fifth level",
        ).one()
        alice_progression = CharacterProgressionEvent.query.filter_by(
            character_id=alice.id,
            new_value="fifth level",
        ).one()

        self.assertEqual(bob_progression.review_status, "approved")
        self.assertEqual(alice_progression.review_status, "pending")
        self.assertIn("attribution_uncertain", alice_progression.risk_flags)

    def test_selected_to_be_promoted_is_not_current_progression(self):
        self.set_chapter_content("The elders selected Alex Vale to be promoted to the Inner Sect.")
        alex = Character(
            novel_id=self.novel.id,
            name="Alex Vale",
            review_status="approved",
        )
        db.session.add(alex)
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Alex Vale",
                    progression_type="position",
                    old_value=None,
                    new_value="Inner Sect disciple",
                    description="Alex Vale was selected to be promoted to the Inner Sect.",
                    evidence="The elders selected Alex Vale to be promoted to the Inner Sect.",
                    source_extractor="progression_extractor",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(CharacterProgressionEvent.query.count(), 0)

    def test_cultivation_damage_state_is_not_rank_progression(self):
        self.set_chapter_content("Alex Vale's cultivation foundation was destroyed.")
        alex = Character(
            novel_id=self.novel.id,
            name="Alex Vale",
            review_status="approved",
        )
        db.session.add(alex)
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Alex Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="destroyed",
                    description="Alex Vale's cultivation foundation was destroyed.",
                    evidence="Alex Vale's cultivation foundation was destroyed.",
                    source_extractor="progression_extractor",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(CharacterProgressionEvent.query.count(), 0)

    def test_temporary_power_is_not_canonical_progression(self):
        self.set_chapter_content("Alex Vale's aura briefly reached the strength of the fifth level.")
        alex = Character(
            novel_id=self.novel.id,
            name="Alex Vale",
            review_status="approved",
        )
        db.session.add(alex)
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Alex Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="fifth level",
                    description="Alex Vale's aura briefly reached fifth-level strength.",
                    evidence="Alex Vale's aura briefly reached the strength of the fifth level.",
                    source_extractor="progression_extractor",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(CharacterProgressionEvent.query.count(), 0)

    def test_comparative_power_is_not_canonical_progression(self):
        self.set_chapter_content("Alex Vale's strength had reached a level comparable to the sixth level.")
        alex = Character(
            novel_id=self.novel.id,
            name="Alex Vale",
            review_status="approved",
        )
        db.session.add(alex)
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Alex Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="sixth level",
                    description="Alex Vale's strength was comparable to the sixth level.",
                    evidence="Alex Vale's strength had reached a level comparable to the sixth level.",
                    source_extractor="progression_extractor",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(CharacterProgressionEvent.query.count(), 0)

    def test_ambiguous_collective_progression_stays_pending(self):
        self.set_chapter_content("Alice Vale and Bob Stone entered, one of them at the seventh level.")
        alice = Character(
            novel_id=self.novel.id,
            name="Alice Vale",
            review_status="approved",
        )
        bob = Character(
            novel_id=self.novel.id,
            name="Bob Stone",
            review_status="approved",
        )
        db.session.add_all([alice, bob])
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Alice Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="seventh level",
                    description="Alice Vale was at the seventh level.",
                    evidence="Alice Vale and Bob Stone entered, one of them at the seventh level.",
                    source_extractor="progression_extractor",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.review_status, "pending")
        self.assertIn("attribution_uncertain", progression.risk_flags)

    def test_context_supported_exclamation_progression_auto_approved_with_reasoning(self):
        self.chapter.content = (
            "Meng Hao consumed the pills. His body expelled impurities. "
            "'The third level of Qi condensation!'"
        )
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi condensation",
                    description="Meng Hao broke through to the third level.",
                    evidence=(
                        "His body expelled impurities. "
                        "'The third level of Qi condensation!'"
                    ),
                    source_extractor="progression_reasoning",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)
        self.assertIn("context_supported_attribution", progression.risk_flags)
        self.assertNotIn("attribution_uncertain", progression.risk_flags)

    def test_short_breakthrough_exclamation_uses_local_context(self):
        self.chapter.content = (
            "Meng Hao consumed the pills and meditated through the night. "
            "His body thrummed, and filth was expelled through his pores. "
            "When he opened his eyes, they shone brilliantly. "
            "'The third level!'"
        )
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level",
                    description="Meng Hao completed a breakthrough to the third level.",
                    evidence="The third level!",
                    source_extractor="progression_reasoning",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.new_value, "third level")
        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)
        self.assertIn("context_supported_attribution", progression.risk_flags)

    def test_short_rank_up_exclamation_uses_generic_local_context(self):
        self.chapter.content = (
            "Meng Hao trained in silence until the system notification rang out. "
            "Power flooded his body and his aura changed. "
            "'Bronze Rank!'"
        )
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="power_rank",
                    old_value=None,
                    new_value="Bronze Rank",
                    description="Meng Hao ranked up to Bronze Rank.",
                    evidence="Bronze Rank!",
                    source_extractor="progression_reasoning",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.new_value, "Bronze Rank")
        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)

    def test_short_fourth_level_exclamation_uses_local_power_context(self):
        self.chapter.content = (
            "Meng Hao swallowed the resources and continued cultivating. "
            "His cultivation base roiled like a massive river, and power surged "
            "through his body. 'The fourth level!'"
        )
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value="third level",
                    new_value="fourth level",
                    description="Meng Hao broke through to the fourth level.",
                    evidence="The fourth level!",
                    source_extractor="progression_reasoning",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.new_value, "fourth level")
        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)

    def test_mixed_same_run_progression_prefers_breakthrough_evidence(self):
        self.chapter.content = (
            "Meng Hao consumed the resources and meditated until dawn. "
            "His body thrummed, and filth was expelled through his pores. "
            "When his eyes opened, they shone brightly. "
            "'The third level!' He was still not content. "
            "Later, his foundation was just a hair away from the peak of the third level."
        )
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value="second level",
                    new_value="third level",
                    description="Meng Hao breaks through to the third level.",
                    evidence=(
                        "His body thrummed, and filth was expelled through his pores. "
                        "When his eyes opened, they shone brightly. 'The third level!'"
                    ),
                    source_extractor="progression_extractor",
                ),
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value="second level",
                    new_value="third level",
                    description="Meng Hao reaches the third level.",
                    evidence="The third level!",
                    source_extractor="progression_audit",
                ),
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value="second level",
                    new_value="third level",
                    description="Meng Hao is nearly at the peak of the third level.",
                    evidence=(
                        "his foundation was just a hair away from the peak "
                        "of the third level."
                    ),
                    source_extractor="progression_reasoning",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.new_value, "third level")
        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)
        self.assertIn("context_supported_attribution", progression.risk_flags)
        self.assertNotIn("attribution_uncertain", progression.risk_flags)
        self.assertEqual(
            progression.source_extractor,
            "progression_audit,progression_extractor",
        )

    def test_negative_earlier_value_mention_does_not_steal_exclamation_context(self):
        self.chapter.content = (
            "Meng Hao swallowed the resources and cultivated. "
            "His power surged, but he still had not reached the fourth level. "
            "He swallowed more pills and his body transformed. "
            "Filth poured from his pores, and Meng Hao's vision grew clear. "
            "'The fourth level!' He felt power roiling like a river."
        )
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value="third level",
                    new_value="fourth level",
                    description="Meng Hao breaks through to the fourth level.",
                    evidence="The fourth level!",
                    source_extractor="progression_extractor",
                ),
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value="third level",
                    new_value="fourth level",
                    description="Meng Hao breaks through to the fourth level.",
                    evidence="The fourth level! He felt power roiling like a river.",
                    source_extractor="progression_reasoning",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.new_value, "fourth level")
        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)
        self.assertIn("context_supported_attribution", progression.risk_flags)
        self.assertNotIn("attribution_uncertain", progression.risk_flags)

    def test_competing_progression_claim_keeps_attribution_uncertain(self):
        sister_xu = Character(
            novel_id=self.novel.id,
            name="Sister Xu",
            review_status="approved",
        )
        db.session.add(sister_xu)
        db.session.commit()
        self.chapter.content = (
            "Sister Xu has reached the seventh level of Qi condensation. "
            "Meng Hao watched from nearby."
        )
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="seventh level of Qi condensation",
                    description="Meng Hao reached the seventh level.",
                    evidence=(
                        "Sister Xu has reached the seventh level of Qi condensation. "
                        "Meng Hao watched from nearby."
                    ),
                    source_extractor="progression_reasoning",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.review_status, "pending")
        self.assertFalse(progression.auto_approved)
        self.assertIn("attribution_uncertain", progression.risk_flags)

    def test_regex_only_context_supported_progression_stays_pending(self):
        self.chapter.content = (
            "Meng Hao consumed the pills. His body expelled impurities. "
            "'The third level of Qi condensation!'"
        )
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi condensation",
                    description="Meng Hao broke through to the third level.",
                    evidence=(
                        "His body expelled impurities. "
                        "'The third level of Qi condensation!'"
                    ),
                    source_extractor="regex_detector",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.review_status, "pending")
        self.assertFalse(progression.auto_approved)
        self.assertIn("attribution_uncertain", progression.risk_flags)

    def test_near_peak_progression_is_skipped(self):
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi Condensation",
                    description=(
                        "Meng Hao states his cultivation foundation is just a hair away "
                        "from the peak of the third level."
                    ),
                    evidence=(
                        "My cultivation foundation is just a hair away from the peak "
                        "of the third level of Qi condensation."
                    ),
                    source_extractor="progression_audit",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(CharacterProgressionEvent.query.count(), 0)

    def test_short_near_peak_exclamation_is_rejected(self):
        self.chapter.content = (
            "Meng Hao cultivated for hours, but his power had not fully changed. "
            "'Almost at the peak of the third level!'"
        )
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="peak of the third level",
                    description="Meng Hao was almost at the peak of the third level.",
                    evidence="Almost at the peak of the third level!",
                    source_extractor="progression_reasoning",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)

        self.assertEqual(CharacterProgressionEvent.query.count(), 0)

    def test_alias_evidence_supports_progression_attribution(self):
        self.character.name = "Li Furui"
        db.session.add(
            CharacterAlias(
                character_id=self.character.id,
                alias="Fatty",
                first_seen_chapter_id=self.chapter.id,
                evidence="Fatty is Li Furui.",
            )
        )
        self.chapter.content = (
            "With Meng Hao's help, Fatty reached the second level of Qi condensation."
        )
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Li Furui",
                    progression_type="cultivation_level",
                    old_value="first level of Qi condensation",
                    new_value="second level of Qi condensation",
                    description="Li Furui reached the second level.",
                    evidence="With Meng Hao's help, Fatty reached the second level of Qi condensation.",
                    source_extractor="progression_extractor",
                ),
                SimpleNamespace(
                    character_name="Li Furui",
                    progression_type="cultivation_level",
                    old_value="first level of Qi condensation",
                    new_value="second level of Qi condensation",
                    description="Li Furui reached the second level.",
                    evidence="With Meng Hao's help, Fatty reached the second level of Qi condensation.",
                    source_extractor="progression_reasoning",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.new_value, "second level of Qi condensation")
        self.assertEqual(progression.review_status, "approved")
        self.assertNotIn("attribution_uncertain", progression.risk_flags or "")

    def test_confirmed_peak_state_is_preserved(self):
        cao = Character(
            novel_id=self.novel.id,
            name="Cao Yang",
            review_status="approved",
        )
        db.session.add(cao)
        db.session.commit()

        self.chapter.content = (
            "Cao Yang was at the peak of the second level of Qi condensation, "
            "one step away from the third."
        )
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Cao Yang",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="peak of the second level of Qi condensation",
                    description="Cao Yang was at the peak of the second level.",
                    evidence=(
                        "Cao Yang was at the peak of the second level of Qi condensation, "
                        "one step away from the third."
                    ),
                    source_extractor="progression_extractor",
                ),
                SimpleNamespace(
                    character_name="Cao Yang",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi condensation",
                    description="Cao Yang was one step away from the third level.",
                    evidence="one step away from the third level of Qi condensation",
                    source_extractor="progression_audit",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progressions = CharacterProgressionEvent.query.all()

        self.assertEqual(len(progressions), 1)
        self.assertEqual(
            progressions[0].new_value,
            "peak of the second level of Qi condensation",
        )
        self.assertEqual(progressions[0].review_status, "approved")

    def test_indirect_breakthrough_saves_confirmed_level_not_later_near_peak(self):
        passage = (
            'His body thrummed, and gobs of filth had been excreted through his pores. '
            'When he opened his eyes they shone brilliantly. '
            '"The third level of Qi Condensation!" Meng Hao was still not content. '
            'His cultivation foundation was just a hair away from being at the peak '
            'of the third level of Qi Condensation.'
        )
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi Condensation",
                    description="Meng Hao completed a breakthrough to the third level.",
                    evidence=passage,
                    source_extractor="progression_reasoning",
                ),
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="peak of the third level of Qi Condensation",
                    description="Meng Hao was close to the peak of the third level.",
                    evidence=(
                        "His cultivation foundation was just a hair away from being "
                        "at the peak of the third level of Qi Condensation."
                    ),
                    source_extractor="progression_reasoning",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progressions = CharacterProgressionEvent.query.all()

        self.assertEqual(len(progressions), 1)
        self.assertEqual(progressions[0].new_value, "third level of Qi Condensation")

    def test_later_current_state_promotes_earlier_pending_breakthrough(self):
        chapter_breakthrough = Chapter(
            novel_id=self.novel.id,
            chapter_number=14,
            title="Breakthrough",
            content=(
                "Meng Hao swallowed the resources and cultivated. "
                "His body transformed and his aura changed. "
                "'The fourth level!'"
            ),
            character_count=0,
        )
        chapter_later = Chapter(
            novel_id=self.novel.id,
            chapter_number=15,
            title="Later State",
            content="Meng Hao's cultivation foundation was now at the fourth level.",
            character_count=0,
        )
        db.session.add_all([chapter_breakthrough, chapter_later])
        db.session.flush()

        pending_progression = CharacterProgressionEvent(
            novel_id=self.novel.id,
            character_id=self.character.id,
            chapter_id=chapter_breakthrough.id,
            progression_type="cultivation_level",
            old_value="third level",
            new_value="fourth level",
            description="Meng Hao breaks through to the fourth level.",
            review_status="pending",
            confidence_score=60,
            risk_flags='["attribution_uncertain"]',
            source_extractor="progression_extractor",
        )
        db.session.add(pending_progression)
        db.session.flush()
        db.session.add(
            WikiEvidence(
                novel_id=self.novel.id,
                chapter_id=chapter_breakthrough.id,
                entity_type="progression",
                entity_id=pending_progression.id,
                evidence_text="The fourth level!",
            )
        )
        db.session.commit()

        save_chapter_extraction(
            self.novel,
            chapter_later,
            self.empty_extraction(
                progression_events=[
                    SimpleNamespace(
                        character_name="Meng Hao",
                        progression_type="cultivation_level",
                        old_value="third level",
                        new_value="fourth level",
                        description="Meng Hao's cultivation foundation was now fourth level.",
                        evidence="Meng Hao's cultivation foundation was now at the fourth level.",
                        source_extractor="progression_audit",
                    ),
                    SimpleNamespace(
                        character_name="Meng Hao",
                        progression_type="cultivation_level",
                        old_value="third level",
                        new_value="fourth level",
                        description="Meng Hao's cultivation foundation was now fourth level.",
                        evidence="Meng Hao's cultivation foundation was now at the fourth level.",
                        source_extractor="progression_reasoning",
                    ),
                ]
            ),
        )

        progressions = CharacterProgressionEvent.query.filter_by(
            character_id=self.character.id,
            new_value="fourth level",
        ).all()
        promoted = db.session.get(CharacterProgressionEvent, pending_progression.id)

        self.assertEqual(len(progressions), 1)
        self.assertEqual(promoted.chapter_id, chapter_breakthrough.id)
        self.assertEqual(promoted.review_status, "approved")
        self.assertTrue(promoted.auto_approved)
        self.assertIn("context_supported_attribution", promoted.risk_flags)

    def test_later_current_state_does_not_create_first_canonical_row_when_breakthrough_exists(self):
        chapter_breakthrough = Chapter(
            novel_id=self.novel.id,
            chapter_number=9,
            title="Breakthrough",
            content=(
                "Meng Hao consumed the resources. His body transformed and his aura changed. "
                "'The third level!'"
            ),
            character_count=0,
        )
        chapter_later = Chapter(
            novel_id=self.novel.id,
            chapter_number=11,
            title="Later State",
            content="Meng Hao's cultivation foundation was now at the third level.",
            character_count=0,
        )
        db.session.add_all([chapter_breakthrough, chapter_later])
        db.session.commit()

        save_chapter_extraction(
            self.novel,
            chapter_breakthrough,
            self.empty_extraction(
                progression_events=[
                    SimpleNamespace(
                        character_name="Meng Hao",
                        progression_type="cultivation_level",
                        old_value=None,
                        new_value="third level",
                        description="Meng Hao broke through to the third level.",
                        evidence="The third level!",
                        source_extractor="progression_reasoning",
                    )
                ]
            ),
        )
        save_chapter_extraction(
            self.novel,
            chapter_later,
            self.empty_extraction(
                progression_events=[
                    SimpleNamespace(
                        character_name="Meng Hao",
                        progression_type="cultivation_level",
                        old_value=None,
                        new_value="third level",
                        description="Meng Hao's cultivation foundation was now at the third level.",
                        evidence="Meng Hao's cultivation foundation was now at the third level.",
                        source_extractor="progression_extractor",
                    )
                ]
            ),
        )

        progressions = CharacterProgressionEvent.query.filter_by(
            character_id=self.character.id,
            new_value="third level",
        ).all()

        self.assertEqual(len(progressions), 1)
        self.assertEqual(progressions[0].chapter_id, chapter_breakthrough.id)

    def test_conflicting_progression_sent_to_review(self):
        approved_progression = CharacterProgressionEvent(
            novel_id=self.novel.id,
            character_id=self.character.id,
            chapter_id=self.chapter.id,
            progression_type="cultivation_level",
            new_value="third level of Qi Condensation",
            review_status="approved",
        )
        db.session.add(approved_progression)
        db.session.commit()
        recalculate_character_current_progression(self.character, "cultivation_level")

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="second level of Qi Condensation",
                    description="Meng Hao was at the second level of Qi Condensation.",
                    evidence="Meng Hao was at the second level of Qi Condensation.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.filter_by(
            new_value="second level of Qi Condensation"
        ).one()

        self.assertEqual(progression.review_status, "pending")
        self.assertFalse(progression.auto_approved)
        self.assertIn("progression_downgrade", progression.risk_flags)

    def test_pending_progression_does_not_poison_later_valid_progression(self):
        pending_progression = CharacterProgressionEvent(
            novel_id=self.novel.id,
            character_id=self.character.id,
            chapter_id=self.chapter.id,
            progression_type="cultivation_level",
            new_value="seventh level of Qi Condensation",
            review_status="pending",
            risk_flags='["speculative_statement", "future_statement"]',
        )
        db.session.add(pending_progression)
        db.session.commit()

        recalculate_character_current_progression(self.character, "cultivation_level")
        self.assertIsNone(self.character.current_cultivation_level)

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="second level of Qi Condensation",
                    description="Meng Hao broke through to the second level.",
                    evidence="Meng Hao broke through to the second level of Qi Condensation.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        second_level = CharacterProgressionEvent.query.filter_by(
            new_value="second level of Qi Condensation"
        ).one()

        self.assertEqual(second_level.review_status, "approved")
        self.assertNotIn("conflicts_with_database", second_level.risk_flags)
        self.assertNotIn("progression_downgrade", second_level.risk_flags)

        current_values = current_values_from_progression(self.character.id)
        self.assertEqual(
            current_values["current_cultivation_level"],
            "second level of Qi Condensation",
        )

    def test_pending_speculative_progression_does_not_dedupe_later_confirmed_same_value(self):
        chapter_eight = Chapter(
            novel_id=self.novel.id,
            chapter_number=8,
            title="Chapter 8",
            content="I think with three or maybe five more, I can reach the third level.",
            character_count=0,
        )
        chapter_nine = Chapter(
            novel_id=self.novel.id,
            chapter_number=9,
            title="Chapter 9",
            content=(
                "His body thrummed, and gobs of filth had been excreted through his pores. "
                "When he opened his eyes they shone brilliantly. "
                'Meng Hao opened his eyes and shouted, "The third level of Qi Condensation!"'
            ),
            character_count=0,
        )
        db.session.add_all([chapter_eight, chapter_nine])
        db.session.flush()
        pending_progression = CharacterProgressionEvent(
            novel_id=self.novel.id,
            character_id=self.character.id,
            chapter_id=chapter_eight.id,
            progression_type="cultivation_level",
            new_value="third level of Qi Condensation",
            review_status="pending",
            risk_flags='["speculative_statement", "future_statement"]',
        )
        db.session.add(pending_progression)
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of Qi Condensation",
                    description="Meng Hao broke through to the third level.",
                    evidence=(
                        "Meng Hao opened his eyes and shouted, "
                        '"The third level of Qi Condensation!"'
                    ),
                )
            ]
        )

        save_chapter_extraction(self.novel, chapter_nine, extraction)
        confirmed_progression = CharacterProgressionEvent.query.filter_by(
            chapter_id=chapter_nine.id,
            new_value="third level of Qi Condensation",
        ).one()

        self.assertNotEqual(confirmed_progression.id, pending_progression.id)
        self.assertEqual(confirmed_progression.review_status, "approved")
        self.assertTrue(confirmed_progression.auto_approved)

    def test_regex_progression_prefers_same_sentence_character_alias(self):
        elder_sister_xu = Character(
            novel_id=self.novel.id,
            name="Elder Sister Xu",
            review_status="approved",
        )
        db.session.add(elder_sister_xu)
        db.session.flush()
        db.session.add(
            CharacterAlias(
                character_id=elder_sister_xu.id,
                alias="Sister Xu",
                first_seen_chapter_id=self.chapter.id,
            )
        )
        chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=1,
            title="Scholar Meng Hao",
            content=(
                "Sister Xu has reached the seventh level of Qi condensation, "
                "lamented the second of the Cultivation monks. "
                "He looked arrogantly down at Meng Hao and the others."
            ),
            character_count=0,
        )
        db.session.add(chapter)
        db.session.commit()

        detected_events = detect_direct_cultivation_progression(
            self.novel,
            chapter,
            self.empty_extraction(),
            SimpleNamespace,
        )

        self.assertEqual(len(detected_events), 1)
        self.assertIn(detected_events[0].character_name, {"Elder Sister Xu", "Sister Xu"})
        self.assertNotEqual(detected_events[0].character_name, "Meng Hao")

        save_chapter_extraction(
            self.novel,
            chapter,
            self.empty_extraction(progression_events=detected_events),
        )
        progression = CharacterProgressionEvent.query.filter_by(
            chapter_id=chapter.id,
            new_value="seventh level of Qi condensation",
        ).one()

        self.assertEqual(progression.character.name, "Elder Sister Xu")
        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)

    def test_regex_progression_does_not_match_name_variant_inside_another_word(self):
        wang_tengfei = Character(
            novel_id=self.novel.id,
            name="Wang Tengfei",
            review_status="approved",
        )
        chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=18,
            title="Substring Attribution",
            content=(
                "Wang Tengfei has an important background. "
                "He's not from the State of Zhao, and his Cultivation Base is at "
                "the sixth level of Qi Condensation. "
                "Meng Hao listened quietly."
            ),
            character_count=0,
        )
        db.session.add_all([wang_tengfei, chapter])
        db.session.commit()

        detected_events = detect_direct_cultivation_progression(
            self.novel,
            chapter,
            self.empty_extraction(),
            SimpleNamespace,
        )

        self.assertEqual(detected_events, [])

    def test_progression_candidate_variants_do_not_generate_last_name_tokens(self):
        self.assertEqual(progression_candidate_variants("Meng Hao"), ["Meng Hao"])

    def test_regex_progression_still_matches_full_character_name(self):
        chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=19,
            title="Full Name Attribution",
            content=(
                "Meng Hao's Cultivation Base is at the sixth level of Qi "
                "Condensation."
            ),
            character_count=0,
        )
        db.session.add(chapter)
        db.session.commit()

        detected_events = detect_direct_cultivation_progression(
            self.novel,
            chapter,
            self.empty_extraction(),
            SimpleNamespace,
        )

        self.assertEqual(len(detected_events), 1)
        self.assertEqual(detected_events[0].character_name, "Meng Hao")
        self.assertEqual(
            detected_events[0].new_value,
            "sixth level of Qi condensation",
        )

    def test_regex_progression_matches_known_alias_as_standalone_token(self):
        li_furui = Character(
            novel_id=self.novel.id,
            name="Li Furui",
            review_status="approved",
        )
        db.session.add(li_furui)
        db.session.flush()
        db.session.add(
            CharacterAlias(
                character_id=li_furui.id,
                alias="Fatty",
                first_seen_chapter_id=self.chapter.id,
            )
        )
        chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=20,
            title="Alias Attribution",
            content=(
                "Fatty's cultivation foundation was at the second level of "
                "Qi Condensation."
            ),
            character_count=0,
        )
        db.session.add(chapter)
        db.session.commit()

        detected_events = detect_direct_cultivation_progression(
            self.novel,
            chapter,
            self.empty_extraction(),
            SimpleNamespace,
        )

        self.assertEqual(len(detected_events), 1)
        self.assertEqual(detected_events[0].character_name, "Fatty")
        self.assertEqual(
            detected_events[0].new_value,
            "second level of Qi condensation",
        )

    def test_regex_progression_skips_without_same_sentence_owner(self):
        chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=11,
            title="No Local Owner",
            content=(
                "The cultivation foundation was at the third level of Qi condensation. "
                "Meng Hao watched from the doorway."
            ),
            character_count=0,
        )
        db.session.add(chapter)
        db.session.commit()

        detected_events = detect_direct_cultivation_progression(
            self.novel,
            chapter,
            self.empty_extraction(),
            SimpleNamespace,
        )

        self.assertEqual(detected_events, [])

    def test_regex_progression_does_not_guess_from_multiple_nearby_names(self):
        wang_youcai = Character(
            novel_id=self.novel.id,
            name="Wang Youcai",
            review_status="approved",
        )
        chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=12,
            title="Nearby Names",
            content=(
                "Meng Hao watched from the doorway. "
                "The cultivation foundation was at the third level of Qi condensation. "
                "Wang Youcai frowned."
            ),
            character_count=0,
        )
        db.session.add_all([wang_youcai, chapter])
        db.session.commit()

        detected_events = detect_direct_cultivation_progression(
            self.novel,
            chapter,
            self.empty_extraction(),
            SimpleNamespace,
        )

        self.assertEqual(detected_events, [])

    def test_regex_progression_leaves_indirect_breakthrough_without_local_owner_to_ai(self):
        chapter = Chapter(
            novel_id=self.novel.id,
            chapter_number=13,
            title="Indirect Breakthrough",
            content=(
                "His body thrummed, and filth had been excreted through his pores. "
                '"The third level of Qi condensation!" '
                "Meng Hao was still not content."
            ),
            character_count=0,
        )
        db.session.add(chapter)
        db.session.commit()

        detected_events = detect_direct_cultivation_progression(
            self.novel,
            chapter,
            self.empty_extraction(),
            SimpleNamespace,
        )

        self.assertEqual(detected_events, [])

    def test_progression_missing_character_mention_gets_attribution_risk(self):
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Meng Hao",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="seventh level of Qi condensation",
                    description="Meng Hao's cultivation is confirmed at the seventh level.",
                    evidence="Sister Xu has reached the seventh level of Qi condensation.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.review_status, "pending")
        self.assertFalse(progression.auto_approved)
        self.assertIn("attribution_uncertain", progression.risk_flags)

    def test_extraction_memory_ignores_pending_progression_values(self):
        pending_progression = CharacterProgressionEvent(
            novel_id=self.novel.id,
            character_id=self.character.id,
            chapter_id=self.chapter.id,
            progression_type="cultivation_level",
            new_value="seventh level of Qi Condensation",
            review_status="pending",
        )
        approved_progression = CharacterProgressionEvent(
            novel_id=self.novel.id,
            character_id=self.character.id,
            chapter_id=self.chapter.id,
            progression_type="cultivation_level",
            new_value="first level of Qi Condensation",
            review_status="approved",
        )
        db.session.add_all([pending_progression, approved_progression])
        db.session.commit()
        recalculate_character_current_progression(self.character, "cultivation_level")

        memory = build_extraction_memory(self.novel)

        self.assertIn("first level of Qi Condensation", memory)
        self.assertNotIn("seventh level of Qi Condensation", memory)

    def test_automatic_validation_approval_sets_coherent_state(self):
        item = Item(
            novel_id=self.novel.id,
            name="Silver Compass",
            category="Artifact",
            review_status="pending",
        )
        db.session.add(item)
        db.session.flush()

        result = ValidationResult(95, ["context_supported_attribution"], True)

        changed = set_validation_metadata(item, result, "item")

        self.assertTrue(changed)
        self.assertEqual(item.review_status, "approved")
        self.assertTrue(item.auto_approved)
        self.assertEqual(item.confidence_score, 95)
        self.assertEqual(item.source_extractor, "item")
        self.assertEqual(item.risk_flags, '["context_supported_attribution"]')

    def test_automatic_validation_with_serious_blocker_stays_pending(self):
        item = Item(
            novel_id=self.novel.id,
            name="Silver Compass",
            category="Artifact",
            review_status="pending",
        )
        db.session.add(item)
        db.session.flush()

        result = ValidationResult(100, ["evidence_not_exact"], True)

        set_validation_metadata(item, result, "item")

        self.assertEqual(item.review_status, "pending")
        self.assertFalse(item.auto_approved)
        self.assertEqual(item.confidence_score, 100)
        self.assertEqual(item.risk_flags, '["evidence_not_exact"]')

    def test_manual_approval_remains_distinct_from_automatic_approval(self):
        item = Item(
            novel_id=self.novel.id,
            name="Silver Compass",
            category="Artifact",
            review_status="approved",
            auto_approved=False,
            confidence_score=10,
            risk_flags='["evidence_not_exact"]',
            source_extractor="manual",
            last_review_action="approved",
        )
        db.session.add(item)
        db.session.flush()

        result = ValidationResult(95, [], True)

        changed = set_validation_metadata(item, result, "item")

        self.assertFalse(changed)
        self.assertEqual(item.review_status, "approved")
        self.assertFalse(item.auto_approved)
        self.assertEqual(item.confidence_score, 10)
        self.assertEqual(item.risk_flags, '["evidence_not_exact"]')

    def test_invalid_automatic_approval_is_repairable(self):
        item = Item(
            novel_id=self.novel.id,
            name="Silver Compass",
            category="Artifact",
            review_status="approved",
            auto_approved=True,
            confidence_score=10,
            risk_flags='["evidence_not_exact"]',
            source_extractor="item",
        )
        db.session.add(item)
        db.session.flush()

        result = ValidationResult(70, ["evidence_not_exact"], False)

        changed = set_validation_metadata(item, result, "item")

        self.assertTrue(changed)
        self.assertEqual(item.review_status, "pending")
        self.assertFalse(item.auto_approved)
        self.assertEqual(item.confidence_score, 70)
        self.assertEqual(item.risk_flags, '["evidence_not_exact"]')

    def test_clean_automatic_approval_is_not_downgraded_by_weaker_later_support(self):
        item = Item(
            novel_id=self.novel.id,
            name="Silver Compass",
            category="Artifact",
            review_status="approved",
            auto_approved=True,
            confidence_score=95,
            risk_flags="[]",
            source_extractor="item",
        )
        db.session.add(item)
        db.session.flush()

        result = ValidationResult(60, ["relationship_action_not_proven"], False)

        changed = set_validation_metadata(item, result, "character_item")

        self.assertFalse(changed)
        self.assertEqual(item.review_status, "approved")
        self.assertTrue(item.auto_approved)
        self.assertEqual(item.confidence_score, 95)
        self.assertEqual(item.risk_flags, "[]")

    def test_relationship_backed_parent_support_cannot_bypass_parent_validator(self):
        self.set_chapter_content("Aria Vale entered Moon Hall.")
        character = Character(
            novel_id=self.novel.id,
            name="Aria Vale",
            review_status="approved",
            auto_approved=True,
        )
        item = Item(
            novel_id=self.novel.id,
            name="Moon Hall",
            category="Other",
            review_status="approved",
            auto_approved=False,
            confidence_score=10,
            risk_flags='["evidence_not_exact"]',
            source_extractor="item",
        )
        db.session.add_all([character, item])
        db.session.flush()

        validation = validate_item_entity_from_relationship(
            self.novel,
            self.chapter,
            character,
            item,
            "Aria Vale entered Moon Hall.",
            created=False,
        )

        self.assertIsNotNone(validation)
        self.assertFalse(validation.auto_approved)
        self.assertEqual(item.review_status, "pending")
        self.assertFalse(item.auto_approved)
        self.assertIn("possible_location_not_item", item.risk_flags)

    def test_pipeline_recovers_repeated_proper_name_identity_evidence(self):
        db.session.delete(self.character)
        db.session.commit()
        self.set_chapter_content("Aria Vale entered the hall. Aria Vale bowed to the elder.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Aria Vale",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=self.metadata_ns(),
                    description="Aria Vale appears.",
                    evidence="Aria Vale appeared in the hall.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Aria Vale").one()
        evidence = WikiEvidence.query.filter_by(
            entity_type="character",
            entity_id=character.id,
        ).one()

        self.assertEqual(character.review_status, "approved")
        self.assertTrue(character.auto_approved)
        self.assertEqual(evidence.evidence_text, "Aria Vale entered the hall.")
        self.assertEqual(evidence.match_type, "exact_character_reference")

    def test_pipeline_approved_supporting_fact_revalidates_parent_identity(self):
        db.session.delete(self.character)
        pending_character = Character(
            novel_id=self.novel.id,
            name="Aria Vale",
            review_status="pending",
            auto_approved=False,
            confidence_score=40,
            risk_flags='["evidence_not_exact"]',
        )
        db.session.add(pending_character)
        db.session.commit()
        self.set_chapter_content('"What happened to Aria Vale?" "He died."')

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    event_type="death",
                    description="Aria Vale died.",
                    reason=None,
                    evidence='"He died."',
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        life_event = CharacterLifeEvent.query.one()

        self.assertEqual(life_event.review_status, "approved")
        self.assertEqual(pending_character.review_status, "approved")
        self.assertTrue(pending_character.auto_approved)
        self.assertNotIn("evidence_not_exact", pending_character.risk_flags)

    def test_pipeline_progression_revalidates_from_strong_merged_support(self):
        self.set_chapter_content(
            "Aria Vale entered the chamber. "
            "When she returned, her cultivation was now second level."
        )
        db.session.delete(self.character)
        character = Character(
            novel_id=self.novel.id,
            name="Aria Vale",
            review_status="approved",
            auto_approved=True,
        )
        db.session.add(character)
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="second level",
                    description="Aria Vale reached the second level.",
                    evidence="her cultivation was now second level.",
                    source_extractor="progression_extractor",
                ),
                SimpleNamespace(
                    character_name="Aria Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="second level",
                    description="Aria Vale reached the second level.",
                    evidence="When she returned, her cultivation was now second level.",
                    source_extractor="progression_reasoning",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)
        self.assertIn("context_supported_attribution", progression.risk_flags)
        self.assertNotIn("attribution_uncertain", progression.risk_flags)

    def test_pipeline_character_item_acquired_action_uses_attached_evidence_revalidation(self):
        self.set_chapter_content("Aria Vale looked down at the Spirit Stones she had acquired.")
        db.session.delete(self.character)
        character = Character(
            novel_id=self.novel.id,
            name="Aria Vale",
            review_status="approved",
            auto_approved=True,
        )
        db.session.add(character)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="Spirit Stones",
                    relationship_type="obtained",
                    description="Aria Vale obtained the Spirit Stones.",
                    evidence="Aria Vale looked down at the Spirit Stones she had acquired.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertNotIn("relationship_action_not_proven", relationship.risk_flags)

        trace = trace_fact_validation(
            self.novel.id,
            "character_item",
            relationship.id,
        )

        self.assertTrue(trace["found"])
        self.assertEqual(
            trace["selected_support"]["evidence"],
            "Aria Vale looked down at the Spirit Stones she had acquired.",
        )
        self.assertTrue(trace["relationship_semantic_analysis"]["action_supported"])
        self.assertEqual(trace["validator"]["auto_approved"], True)

    def test_pipeline_character_item_consumed_action_uses_attached_evidence_revalidation(self):
        self.set_chapter_content("Aria Vale swallowed the Healing Pill.")
        db.session.delete(self.character)
        character = Character(
            novel_id=self.novel.id,
            name="Aria Vale",
            review_status="approved",
            auto_approved=True,
        )
        db.session.add(character)
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Aria Vale",
                    item_name="Healing Pill",
                    relationship_type="used",
                    description="Aria Vale consumed the pill.",
                    evidence="Aria Vale swallowed the Healing Pill.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertNotIn("relationship_action_not_proven", relationship.risk_flags)

    def test_pipeline_metadata_gender_plural_membership_and_title_validate_from_source(self):
        db.session.delete(self.character)
        db.session.commit()
        self.set_chapter_content(
            "Elder Sister Aria tightened her grip. "
            "Inner Sect disciples Aria Vale and Borin Stone arrived. "
            "Sect Leader Aria Vale entered the hall."
        )

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Aria Vale",
                    aliases=["Elder Sister Aria"],
                    appearance_type="appeared",
                    metadata=self.metadata_ns(
                        gender="female",
                        faction_or_affiliation="Inner Sect",
                        titles=["Sect Leader"],
                    ),
                    description="Aria Vale appears.",
                    evidence="Elder Sister Aria tightened her grip.",
                ),
                SimpleNamespace(
                    name="Borin Stone",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=self.metadata_ns(faction_or_affiliation="Inner Sect"),
                    description="Borin Stone appears.",
                    evidence="Borin Stone arrived.",
                ),
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        aria = Character.query.filter_by(name="Aria Vale").one()
        proposals = {
            (proposal.field_name, proposal.normalized_value): proposal
            for proposal in CharacterMetadataProposal.query.filter_by(
                character_id=aria.id,
            ).all()
        }

        self.assertEqual(aria.gender, "female")
        self.assertIn(("gender", "female"), proposals)
        self.assertIn(("faction_or_affiliation", "inner sect"), proposals)
        self.assertIn(("titles", "sect leader"), proposals)
        self.assertEqual(proposals[("gender", "female")].review_status, "approved")
        self.assertEqual(
            proposals[("faction_or_affiliation", "inner sect")].review_status,
            "approved",
        )
        self.assertEqual(proposals[("titles", "sect leader")].review_status, "approved")

    def test_pipeline_same_raw_evidence_supports_character_and_metadata_context(self):
        db.session.delete(self.character)
        db.session.commit()
        self.set_chapter_content("Aria Vale, a scholar from River Town, entered the hall.")

        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Aria Vale",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=self.metadata_ns(origin="River Town"),
                    description="Aria Vale appears.",
                    evidence="Aria Vale, a scholar from River Town, entered the hall.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Aria Vale").one()
        metadata = CharacterMetadataProposal.query.filter_by(
            character_id=character.id,
            field_name="origin",
        ).one()
        evidence = WikiEvidence.query.filter_by(
            entity_type="character",
            entity_id=character.id,
        ).one()

        self.assertEqual(metadata.review_status, "approved")
        self.assertEqual(metadata.evidence, evidence.evidence_text)
        self.assertTrue(
            get_evidence_context(self.chapter.content, metadata.evidence).found
        )

    def test_pipeline_progression_pronoun_resolves_across_continuous_paragraphs(self):
        self.set_chapter_content(
            "Alex Vale entered the chamber alone.\n\n"
            "He settled onto the floor and closed his eyes. "
            "Sure enough, he had broken through into the second level."
        )
        alex = Character(
            novel_id=self.novel.id,
            name="Alex Vale",
            review_status="approved",
            auto_approved=True,
        )
        db.session.add(alex)
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Alex Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="second level",
                    description="Alex Vale reached the second level.",
                    evidence="Sure enough, he had broken through into the second level.",
                    source_extractor="progression_extractor",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)
        self.assertIn("context_supported_attribution", progression.risk_flags)
        self.assertNotIn("attribution_uncertain", progression.risk_flags)

    def test_pipeline_progression_pronoun_does_not_cross_subject_switch(self):
        self.set_chapter_content(
            "Alex Vale entered the chamber alone.\n\n"
            "Brian Stone stepped between the pillars. "
            "He had broken through into the second level."
        )
        alex = Character(
            novel_id=self.novel.id,
            name="Alex Vale",
            review_status="approved",
            auto_approved=True,
        )
        brian = Character(
            novel_id=self.novel.id,
            name="Brian Stone",
            review_status="approved",
            auto_approved=True,
        )
        db.session.add_all([alex, brian])
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Alex Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="second level",
                    description="Alex Vale reached the second level.",
                    evidence="He had broken through into the second level.",
                    source_extractor="progression_extractor",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.review_status, "pending")
        self.assertFalse(progression.auto_approved)
        self.assertIn("attribution_uncertain", progression.risk_flags)

    def test_pipeline_possessive_progression_chain_resolves_across_paragraphs(self):
        self.set_chapter_content(
            "Look, Han Zong is here.\n\n"
            "His cultivation foundation had advanced without pause. "
            "It was the fifth level."
        )
        han = Character(
            novel_id=self.novel.id,
            name="Han Zong",
            review_status="approved",
            auto_approved=True,
        )
        db.session.add(han)
        db.session.commit()

        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Han Zong",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="fifth level",
                    description="Han Zong was at the fifth level.",
                    evidence="It was the fifth level.",
                    source_extractor="progression_reasoning",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.review_status, "approved")
        self.assertTrue(progression.auto_approved)
        self.assertIn("context_supported_attribution", progression.risk_flags)
        self.assertNotIn("attribution_uncertain", progression.risk_flags)

    def test_pipeline_relationship_completed_consumption_uses_cross_paragraph_actor(self):
        self.set_chapter_content(
            "Rowan Vale inspected the medicine shelf alone.\n\n"
            "His gaze shifted to the silver pill. "
            "He picked up the silver pill and popped it into his mouth."
        )
        rowan = Character(
            novel_id=self.novel.id,
            name="Rowan Vale",
            review_status="approved",
            auto_approved=True,
        )
        pill = Item(
            novel_id=self.novel.id,
            name="silver pill",
            category="Pill",
            review_status="approved",
            auto_approved=True,
        )
        db.session.add_all([rowan, pill])
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Rowan Vale",
                    item_name="silver pill",
                    relationship_type="used",
                    description="Rowan Vale used the silver pill.",
                    evidence="He picked up the silver pill and popped it into his mouth.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertIn("relationship_context_supported", relationship.risk_flags)
        self.assertNotIn("relationship_actor_unresolved", relationship.risk_flags)
        self.assertNotIn("relationship_intent_only", relationship.risk_flags)
        self.assertNotIn("relationship_action_not_proven", relationship.risk_flags)

    def test_pipeline_relationship_intent_does_not_become_completed_use(self):
        self.set_chapter_content(
            "Rowan Vale inspected the medicine shelf alone.\n\n"
            "He wanted to swallow the silver pill."
        )
        rowan = Character(
            novel_id=self.novel.id,
            name="Rowan Vale",
            review_status="approved",
            auto_approved=True,
        )
        pill = Item(
            novel_id=self.novel.id,
            name="silver pill",
            category="Pill",
            review_status="approved",
            auto_approved=True,
        )
        db.session.add_all([rowan, pill])
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Rowan Vale",
                    item_name="silver pill",
                    relationship_type="used",
                    description="Rowan Vale used the silver pill.",
                    evidence="He wanted to swallow the silver pill.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertFalse(relationship.auto_approved)
        self.assertIn("relationship_intent_only", relationship.risk_flags)
        self.assertIn("relationship_action_not_proven", relationship.risk_flags)

    def test_pipeline_relationship_target_coreference_crosses_paragraphs(self):
        self.set_chapter_content(
            "A silver mirror rested on the shelf.\n\n"
            "Faint symbols shimmered across it.\n\n"
            "Rowan Vale picked it up and examined it."
        )
        rowan = Character(
            novel_id=self.novel.id,
            name="Rowan Vale",
            review_status="approved",
            auto_approved=True,
        )
        mirror = Item(
            novel_id=self.novel.id,
            name="silver mirror",
            category="Artifact",
            review_status="approved",
            auto_approved=True,
        )
        db.session.add_all([rowan, mirror])
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Rowan Vale",
                    item_name="silver mirror",
                    relationship_type="obtained",
                    description="Rowan Vale obtained the silver mirror.",
                    evidence="Rowan Vale picked it up and examined it.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertNotIn("relationship_target_unresolved", relationship.risk_flags)
        self.assertNotIn("relationship_action_not_proven", relationship.risk_flags)

    def test_pipeline_relationship_target_coreference_stays_pending_when_ambiguous(self):
        self.set_chapter_content(
            "A silver mirror and a bronze mirror rested on the shelf.\n\n"
            "Rowan Vale picked it up and examined it."
        )
        rowan = Character(
            novel_id=self.novel.id,
            name="Rowan Vale",
            review_status="approved",
            auto_approved=True,
        )
        silver = Item(
            novel_id=self.novel.id,
            name="silver mirror",
            category="Artifact",
            review_status="approved",
            auto_approved=True,
        )
        bronze = Item(
            novel_id=self.novel.id,
            name="bronze mirror",
            category="Artifact",
            review_status="approved",
            auto_approved=True,
        )
        db.session.add_all([rowan, silver, bronze])
        db.session.commit()

        extraction = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Rowan Vale",
                    item_name="silver mirror",
                    relationship_type="obtained",
                    description="Rowan Vale obtained the silver mirror.",
                    evidence="Rowan Vale picked it up and examined it.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertFalse(relationship.auto_approved)
        self.assertIn("relationship_target_unresolved", relationship.risk_flags)

    def test_pipeline_stronger_relationship_support_clears_stale_blockers(self):
        self.set_chapter_content("Rowan Vale considered the silver pill.")
        rowan = Character(
            novel_id=self.novel.id,
            name="Rowan Vale",
            review_status="approved",
            auto_approved=True,
        )
        pill = Item(
            novel_id=self.novel.id,
            name="silver pill",
            category="Pill",
            review_status="approved",
            auto_approved=True,
        )
        db.session.add_all([rowan, pill])
        db.session.commit()

        weak = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Rowan Vale",
                    item_name="silver pill",
                    relationship_type="used",
                    description="Rowan Vale used the silver pill.",
                    evidence="Rowan Vale considered the silver pill.",
                )
            ]
        )
        strong = self.empty_extraction(
            character_items=[
                SimpleNamespace(
                    character_name="Rowan Vale",
                    item_name="silver pill",
                    relationship_type="used",
                    description="Rowan Vale used the silver pill.",
                    evidence="Later, Rowan Vale swallowed the silver pill.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, weak)
        relationship = CharacterItem.query.one()
        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_action_not_proven", relationship.risk_flags)

        self.set_chapter_content(
            "Rowan Vale considered the silver pill. "
            "Later, Rowan Vale swallowed the silver pill."
        )
        save_chapter_extraction(self.novel, self.chapter, strong)
        db.session.refresh(relationship)

        self.assertEqual(relationship.review_status, "approved")
        self.assertTrue(relationship.auto_approved)
        self.assertNotIn("relationship_action_not_proven", relationship.risk_flags)
        self.assertNotIn("relationship_actor_unresolved", relationship.risk_flags)
        self.assertNotIn("relationship_target_unresolved", relationship.risk_flags)

    def test_pipeline_pending_uncertain_life_event_does_not_promote_parent(self):
        self.set_chapter_content("Wild Chicken's body dropped to the ground.")

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="Wild Chicken",
                    event_type="death",
                    description="Wild Chicken died.",
                    reason=None,
                    evidence="Wild Chicken's body dropped to the ground.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        character = Character.query.filter_by(name="Wild Chicken").one()
        life_event = CharacterLifeEvent.query.one()

        self.assertEqual(life_event.review_status, "pending")
        self.assertFalse(life_event.auto_approved)
        self.assertEqual(character.review_status, "pending")
        self.assertFalse(character.auto_approved)
        self.assertNotIn("identity_supported_by_life_event", character.risk_flags or "")

    def test_pipeline_approved_child_does_not_bypass_generic_parent_identity(self):
        self.set_chapter_content("The old man died.")
        old_man = Character(
            novel_id=self.novel.id,
            name="old man",
            review_status="pending",
            auto_approved=False,
        )
        db.session.add(old_man)
        db.session.commit()

        extraction = self.empty_extraction(
            life_events=[
                SimpleNamespace(
                    character_name="old man",
                    event_type="death",
                    description="The old man died.",
                    reason=None,
                    evidence="The old man died.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        life_event = CharacterLifeEvent.query.one()

        self.assertEqual(life_event.review_status, "approved")
        self.assertEqual(old_man.review_status, "pending")
        self.assertFalse(old_man.auto_approved)

    def test_pipeline_title_attached_to_target_character_approves(self):
        self.set_chapter_content("Uncle Rowan Vale entered the hall.")
        rowan = Character(
            novel_id=self.novel.id,
            name="Rowan Vale",
            review_status="approved",
            auto_approved=True,
        )
        db.session.add(rowan)
        db.session.commit()

        created = create_character_metadata_proposals(
            self.novel,
            self.chapter,
            rowan,
            self.metadata_ns(titles=["Uncle"]),
            "Uncle Rowan Vale entered the hall.",
        )
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(created, 1)
        self.assertEqual(proposal.review_status, "approved")
        self.assertTrue(proposal.auto_approved)

    def test_pipeline_title_belonging_to_relative_does_not_approve(self):
        self.set_chapter_content(
            "Rowan Vale returned home. "
            "He was the son of Uncle Vale."
        )
        rowan = Character(
            novel_id=self.novel.id,
            name="Rowan Vale",
            review_status="approved",
            auto_approved=True,
        )
        db.session.add(rowan)
        db.session.flush()
        db.session.add(
            CharacterAlias(
                character=rowan,
                alias="Vale",
                first_seen_chapter_id=self.chapter.id,
            )
        )
        db.session.commit()

        created = create_character_metadata_proposals(
            self.novel,
            self.chapter,
            rowan,
            self.metadata_ns(titles=["Uncle"]),
            "He was the son of Uncle Vale.",
        )
        proposal = CharacterMetadataProposal.query.one()

        self.assertEqual(created, 1)
        self.assertEqual(proposal.review_status, "pending")
        self.assertFalse(proposal.auto_approved)

    def test_pipeline_physical_tablet_uses_conservative_item_category(self):
        self.set_chapter_content("Rowan Vale carried the Spirit Tablet in his hand.")
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Spirit Tablet",
                    category="Manual",
                    importance="important",
                    description="A marked stone tablet.",
                    evidence="Rowan Vale carried the Spirit Tablet in his hand.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.category, "Other")

    def test_pipeline_instructional_tablet_can_remain_manual(self):
        self.set_chapter_content(
            "The Stone Tablet recorded the instructions for the Moon Step technique."
        )
        extraction = self.empty_extraction(
            items=[
                SimpleNamespace(
                    name="Stone Tablet",
                    category="Manual",
                    importance="important",
                    description="A tablet containing instructions.",
                    evidence=(
                        "The Stone Tablet recorded the instructions for the Moon Step "
                        "technique."
                    ),
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        item = Item.query.one()

        self.assertEqual(item.category, "Manual")

    def test_progression_uses_generic_record_validation_context(self):
        self.set_chapter_content(
            "Arlen Vale broke through to the third level of the Ember Path."
        )
        character = Character(
            novel_id=self.novel.id,
            name="Arlen Vale",
            review_status="approved",
            auto_approved=True,
        )
        db.session.add(character)
        db.session.flush()
        progression = CharacterProgressionEvent(
            novel_id=self.novel.id,
            character_id=character.id,
            chapter_id=self.chapter.id,
            progression_type="cultivation_level",
            new_value="third level of the Ember Path",
            review_status="pending",
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
                evidence_text=(
                    "Arlen Vale broke through to the third level of the Ember Path."
                ),
            )
        )
        db.session.commit()

        trace = trace_fact_validation(
            self.novel.id,
            "progression",
            progression.id,
        )
        validation = revalidate_fact(
            self.novel,
            progression,
            "Arlen Vale broke through to the third level of the Ember Path.",
            "test_generic_progression_context",
            chapter=self.chapter,
            source_extractors={"progression_reasoning"},
        )

        self.assertIsNotNone(trace["selected_support"])
        self.assertIsNotNone(trace["validator"])
        self.assertIsNotNone(validation)
        self.assertEqual(progression.review_status, "approved")

    def test_quoted_dialogue_reporting_subject_resolves_following_pronoun(self):
        arlen = Character(
            novel_id=self.novel.id,
            name="Arlen Vale",
            review_status="approved",
        )
        db.session.add(arlen)
        db.session.commit()
        context = (
            '"You returned?" Arlen Vale asked. '
            "Sure enough, he had broken through to the third level."
        )

        result = resolve_character_attribution(
            evidence_text="Sure enough, he had broken through to the third level.",
            local_context=context,
            candidate_characters=[arlen],
            target_character=arlen,
            target_value="third level",
        )

        self.assertTrue(result.resolved)
        self.assertEqual(result.character_id, arlen.id)

    def test_quoted_dialogue_without_clear_subject_does_not_resolve_topic(self):
        arlen = Character(
            novel_id=self.novel.id,
            name="Arlen Vale",
            review_status="approved",
        )
        bram = Character(
            novel_id=self.novel.id,
            name="Bram Cole",
            review_status="approved",
        )
        db.session.add_all([arlen, bram])
        db.session.commit()
        context = (
            '"Did you return, Arlen Vale?" Bram Cole watched. '
            "Sure enough, he had broken through to the third level."
        )

        result = resolve_character_attribution(
            evidence_text="Sure enough, he had broken through to the third level.",
            local_context=context,
            candidate_characters=[arlen, bram],
            target_character=arlen,
            target_value="third level",
        )

        self.assertFalse(result.resolved and result.character_id == arlen.id)

    def test_bounded_forward_identity_supports_progression(self):
        self.set_chapter_content(
            "He entered the chamber. "
            "His cultivation foundation was at the third level of the Ember Path. "
            "His name was Arlen Vale."
        )
        arlen = Character(
            novel_id=self.novel.id,
            name="Arlen Vale",
            review_status="approved",
            auto_approved=True,
        )
        db.session.add(arlen)
        db.session.commit()
        extraction = self.empty_extraction(
            progression_events=[
                SimpleNamespace(
                    character_name="Arlen Vale",
                    progression_type="cultivation_level",
                    old_value=None,
                    new_value="third level of the Ember Path",
                    description="Arlen Vale was at the third level.",
                    evidence=(
                        "His cultivation foundation was at the third level of the "
                        "Ember Path."
                    ),
                    source_extractor="progression_reasoning",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        progression = CharacterProgressionEvent.query.one()

        self.assertEqual(progression.review_status, "approved")
        self.assertNotIn("attribution_uncertain", progression.risk_flags)

    def test_forward_identity_rejects_intervening_character(self):
        arlen = Character(
            novel_id=self.novel.id,
            name="Arlen Vale",
            review_status="approved",
        )
        db.session.add(arlen)
        db.session.commit()
        context = (
            "He entered the room. "
            "His cultivation was at the third level. "
            "Another man approached. "
            "His name was Arlen Vale."
        )

        result = resolve_character_attribution(
            evidence_text="His cultivation was at the third level.",
            local_context=context,
            candidate_characters=[arlen],
            target_character=arlen,
            target_value="third level",
        )

        self.assertFalse(result.resolved)

    def test_exact_irrelevant_character_evidence_recovers_direct_name(self):
        db.session.delete(self.character)
        self.set_chapter_content(
            "Mira Stone entered the courtyard. "
            "Arlen Vale introduced himself to the guards."
        )
        db.session.add(
            Character(
                novel_id=self.novel.id,
                name="Mira Stone",
                review_status="approved",
                auto_approved=True,
            )
        )
        db.session.commit()
        extraction = self.empty_extraction(
            characters=[
                SimpleNamespace(
                    name="Arlen Vale",
                    aliases=[],
                    appearance_type="appeared",
                    metadata=self.metadata_ns(),
                    description="Arlen Vale appeared.",
                    evidence="Mira Stone entered the courtyard.",
                )
            ]
        )

        save_chapter_extraction(self.novel, self.chapter, extraction)
        arlen = Character.query.filter_by(name="Arlen Vale").one()
        evidence = WikiEvidence.query.filter_by(
            entity_type="character",
            entity_id=arlen.id,
        ).one()
        audit = AIEvidenceAudit.query.filter_by(
            entity_type="character",
            entity_id=arlen.id,
        ).one()

        self.assertEqual(arlen.review_status, "approved")
        self.assertEqual(
            evidence.evidence_text,
            "Arlen Vale introduced himself to the guards.",
        )
        self.assertEqual(
            audit.ai_proposed_evidence,
            "Mira Stone entered the courtyard.",
        )

    def _save_character_skill_case(self, sentence, description=None):
        self.set_chapter_content(sentence)
        character = Character(
            novel_id=self.novel.id,
            name="Arlen Vale",
            review_status="approved",
            auto_approved=True,
        )
        skill = Skill(
            novel_id=self.novel.id,
            name="Moon Step Technique",
            category="Technique",
            review_status="approved",
            auto_approved=True,
        )
        db.session.add_all([character, skill])
        db.session.commit()
        save_chapter_extraction(
            self.novel,
            self.chapter,
            self.empty_extraction(
                character_skills=[
                    SimpleNamespace(
                        character_name="Arlen Vale",
                        skill_name="Moon Step Technique",
                        relationship_type="has",
                        description=description or "Arlen Vale has Moon Step Technique.",
                        evidence=sentence,
                    )
                ]
            ),
        )
        return CharacterSkill.query.one()

    def test_character_skill_began_practicing_approves(self):
        relationship = self._save_character_skill_case(
            "Arlen Vale began practicing Moon Step Technique."
        )

        self.assertEqual(relationship.review_status, "approved")

    def test_character_skill_picked_up_technique_approves(self):
        relationship = self._save_character_skill_case(
            "Arlen Vale had picked up Moon Step Technique during training."
        )

        self.assertEqual(relationship.review_status, "approved")

    def test_character_skill_reporting_clause_execution_approves(self):
        relationship = self._save_character_skill_case(
            '"Moon Step Technique!" Arlen Vale cried as he executed it.'
        )

        self.assertEqual(relationship.review_status, "approved")

    def test_character_skill_wrong_actor_remains_pending(self):
        self.set_chapter_content(
            "Arlen Vale watched Bram Cole use Moon Step Technique."
        )
        arlen = Character(
            novel_id=self.novel.id,
            name="Arlen Vale",
            review_status="approved",
        )
        bram = Character(
            novel_id=self.novel.id,
            name="Bram Cole",
            review_status="approved",
        )
        skill = Skill(
            novel_id=self.novel.id,
            name="Moon Step Technique",
            category="Technique",
            review_status="approved",
        )
        db.session.add_all([arlen, bram, skill])
        db.session.commit()
        save_chapter_extraction(
            self.novel,
            self.chapter,
            self.empty_extraction(
                character_skills=[
                    SimpleNamespace(
                        character_name="Arlen Vale",
                        skill_name="Moon Step Technique",
                        relationship_type="has",
                        description="Arlen Vale has Moon Step Technique.",
                        evidence=(
                            "Arlen Vale watched Bram Cole use Moon Step Technique."
                        ),
                    )
                ]
            ),
        )
        relationship = CharacterSkill.query.one()

        self.assertEqual(relationship.review_status, "pending")
        self.assertIn("relationship_action_not_proven", relationship.risk_flags)

    def test_character_skill_intent_and_failure_remain_pending(self):
        for sentence in (
            "Arlen Vale wanted to learn Moon Step Technique.",
            "Arlen Vale almost activated Moon Step Technique.",
        ):
            with self.subTest(sentence=sentence):
                db.session.query(CharacterSkill).delete()
                db.session.query(WikiEvidence).filter_by(
                    entity_type="character_skill"
                ).delete()
                db.session.commit()
                relationship = self._save_character_skill_case(sentence)
                self.assertEqual(relationship.review_status, "pending")
                self.assertFalse(relationship.auto_approved)

    def test_strongest_character_skill_support_clears_stale_blockers(self):
        self.set_chapter_content(
            "Arlen Vale considered Moon Step Technique. "
            "Later, Arlen Vale demonstrated Moon Step Technique."
        )
        character = Character(
            novel_id=self.novel.id,
            name="Arlen Vale",
            review_status="approved",
        )
        skill = Skill(
            novel_id=self.novel.id,
            name="Moon Step Technique",
            category="Technique",
            review_status="approved",
        )
        db.session.add_all([character, skill])
        db.session.flush()
        relationship = CharacterSkill(
            novel_id=self.novel.id,
            character_id=character.id,
            skill_id=skill.id,
            chapter_id=self.chapter.id,
            relationship_type="has",
            review_status="pending",
            confidence_score=40,
            risk_flags=(
                '["relationship_action_not_proven",'
                '"relationship_actor_unresolved",'
                '"relationship_target_unresolved"]'
            ),
            source_extractor="character_skill",
        )
        db.session.add(relationship)
        db.session.flush()

        for evidence in (
            "Arlen Vale considered Moon Step Technique.",
            "Later, Arlen Vale demonstrated Moon Step Technique.",
        ):
            db.session.add(
                WikiEvidence(
                    novel_id=self.novel.id,
                    chapter_id=self.chapter.id,
                    entity_type="character_skill",
                    entity_id=relationship.id,
                    evidence_text=evidence,
                )
            )
        db.session.commit()

        revalidate_fact(
            self.novel,
            relationship,
            "Later, Arlen Vale demonstrated Moon Step Technique.",
            "stronger_support",
            chapter=self.chapter,
            source_extractors={"character_skill"},
        )

        self.assertEqual(relationship.review_status, "approved")
        self.assertNotIn("relationship_action_not_proven", relationship.risk_flags)
        self.assertNotIn("relationship_actor_unresolved", relationship.risk_flags)
        self.assertNotIn("relationship_target_unresolved", relationship.risk_flags)

    def test_descriptive_character_label_remains_pending(self):
        db.session.delete(self.character)
        self.set_chapter_content("A Fat Teenager entered the room.")
        db.session.commit()
        save_chapter_extraction(
            self.novel,
            self.chapter,
            self.empty_extraction(
                characters=[
                    SimpleNamespace(
                        name="Fat Teenager",
                        aliases=[],
                        appearance_type="appeared",
                        metadata=self.metadata_ns(),
                        description="A descriptive character.",
                        evidence="A Fat Teenager entered the room.",
                    )
                ]
            ),
        )
        character = Character.query.one()

        self.assertEqual(character.review_status, "pending")
        self.assertIn("generic_character_label", character.risk_flags)

    def test_stable_nickname_can_be_supported_without_approving_description(self):
        db.session.delete(self.character)
        self.set_chapter_content(
            'Everyone called him "Fatty." Fatty entered the room.'
        )
        db.session.commit()
        save_chapter_extraction(
            self.novel,
            self.chapter,
            self.empty_extraction(
                characters=[
                    SimpleNamespace(
                        name="Fatty",
                        aliases=[],
                        appearance_type="appeared",
                        metadata=self.metadata_ns(),
                        description="A stable nickname.",
                        evidence="Fatty entered the room.",
                    )
                ]
            ),
        )
        character = Character.query.one()

        self.assertEqual(character.name, "Fatty")
        self.assertEqual(character.review_status, "approved")

    def test_source_supported_spelling_variant_merges(self):
        db.session.delete(self.character)
        first = Chapter(
            novel_id=self.novel.id,
            chapter_number=11,
            title="First",
            content="Founder Radiant entered the hall.",
            character_count=0,
        )
        second = Chapter(
            novel_id=self.novel.id,
            chapter_number=12,
            title="Second",
            content=(
                "Founder Radiance, also known as Founder Radiant, addressed them."
            ),
            character_count=0,
        )
        db.session.add_all([first, second])
        db.session.commit()
        save_chapter_extraction(
            self.novel,
            first,
            self.empty_extraction(
                characters=[
                    SimpleNamespace(
                        name="Founder Radiant",
                        aliases=[],
                        appearance_type="appeared",
                        metadata=self.metadata_ns(),
                        description="A founder.",
                        evidence="Founder Radiant entered the hall.",
                    )
                ]
            ),
        )
        save_chapter_extraction(
            self.novel,
            second,
            self.empty_extraction(
                characters=[
                    SimpleNamespace(
                        name="Founder Radiance",
                        aliases=[],
                        appearance_type="appeared",
                        metadata=self.metadata_ns(),
                        description="The same founder.",
                        evidence=(
                            "Founder Radiance, also known as Founder Radiant, "
                            "addressed them."
                        ),
                    )
                ]
            ),
        )

        self.assertEqual(Character.query.count(), 1)
        aliases = {alias.alias for alias in CharacterAlias.query.all()}
        self.assertIn("Founder Radiance", aliases)

    def test_unsupported_similar_names_do_not_merge(self):
        db.session.delete(self.character)
        self.set_chapter_content(
            "Founder Radiant entered the ceremonial hall. "
            "Founder Radiance waited outside the ceremonial hall."
        )
        db.session.commit()
        save_chapter_extraction(
            self.novel,
            self.chapter,
            self.empty_extraction(
                characters=[
                    SimpleNamespace(
                        name="Founder Radiant",
                        aliases=[],
                        appearance_type="appeared",
                        metadata=self.metadata_ns(),
                        description="One founder.",
                        evidence="Founder Radiant entered the ceremonial hall.",
                    ),
                    SimpleNamespace(
                        name="Founder Radiance",
                        aliases=[],
                        appearance_type="appeared",
                        metadata=self.metadata_ns(),
                        description="Another founder.",
                        evidence=(
                            "Founder Radiance waited outside the ceremonial hall."
                        ),
                    ),
                ]
            ),
        )
        characters = Character.query.order_by(Character.id).all()

        self.assertEqual(len(characters), 2)
        self.assertEqual(characters[1].review_status, "pending")
        self.assertIn("possible_duplicate", characters[1].risk_flags)

    def test_generic_one_off_object_remains_pending(self):
        self.set_chapter_content("A small white sword lay on the table.")
        save_chapter_extraction(
            self.novel,
            self.chapter,
            self.empty_extraction(
                items=[
                    SimpleNamespace(
                        name="small white sword",
                        category="Weapon",
                        importance="important",
                        description="A small white sword.",
                        evidence="A small white sword lay on the table.",
                    )
                ]
            ),
        )
        item = Item.query.one()

        self.assertEqual(item.review_status, "pending")

    def test_unnamed_but_significant_artifact_can_approve(self):
        self.set_chapter_content(
            "The small white sword was a unique magical artifact that returned "
            "to its owner after every battle."
        )
        save_chapter_extraction(
            self.novel,
            self.chapter,
            self.empty_extraction(
                items=[
                    SimpleNamespace(
                        name="small white sword",
                        category="Weapon",
                        importance="important",
                        description="A recurring magical artifact.",
                        evidence=(
                            "The small white sword was a unique magical artifact "
                            "that returned to its owner after every battle."
                        ),
                    )
                ]
            ),
        )
        item = Item.query.one()

        self.assertEqual(item.review_status, "approved")

    def test_unrelated_speculation_does_not_poison_completed_relationship(self):
        self.set_chapter_content(
            "Arlen Vale used the silver mirror. "
            "He could only imagine what would happen next."
        )
        arlen = Character(
            novel_id=self.novel.id,
            name="Arlen Vale",
            review_status="approved",
        )
        mirror = Item(
            novel_id=self.novel.id,
            name="silver mirror",
            category="Artifact",
            review_status="approved",
        )
        db.session.add_all([arlen, mirror])
        db.session.commit()
        save_chapter_extraction(
            self.novel,
            self.chapter,
            self.empty_extraction(
                character_items=[
                    SimpleNamespace(
                        character_name="Arlen Vale",
                        item_name="silver mirror",
                        relationship_type="used",
                        description="Arlen Vale used the mirror.",
                        evidence=(
                            "Arlen Vale used the silver mirror. "
                            "He could only imagine what would happen next."
                        ),
                    )
                ]
            ),
        )
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "approved")
        self.assertNotIn("speculative_statement", relationship.risk_flags)

    def test_speculation_governing_relationship_remains_blocked(self):
        self.set_chapter_content(
            "Arlen Vale could only imagine using the silver mirror."
        )
        arlen = Character(
            novel_id=self.novel.id,
            name="Arlen Vale",
            review_status="approved",
        )
        mirror = Item(
            novel_id=self.novel.id,
            name="silver mirror",
            category="Artifact",
            review_status="approved",
        )
        db.session.add_all([arlen, mirror])
        db.session.commit()
        save_chapter_extraction(
            self.novel,
            self.chapter,
            self.empty_extraction(
                character_items=[
                    SimpleNamespace(
                        character_name="Arlen Vale",
                        item_name="silver mirror",
                        relationship_type="used",
                        description="Arlen Vale used the mirror.",
                        evidence=(
                            "Arlen Vale could only imagine using the silver mirror."
                        ),
                    )
                ]
            ),
        )
        relationship = CharacterItem.query.one()

        self.assertEqual(relationship.review_status, "pending")

    def test_physical_map_carrier_is_not_an_organization(self):
        self.set_chapter_content(
            "The Azure Sect Map appeared in Arlen Vale's hand on a jade slip."
        )
        save_chapter_extraction(
            self.novel,
            self.chapter,
            self.empty_extraction(
                items=[
                    SimpleNamespace(
                        name="Azure Sect Map",
                        category="Manual",
                        importance="important",
                        description="A magical physical map stored on a jade slip.",
                        evidence=(
                            "The Azure Sect Map appeared in Arlen Vale's hand on "
                            "a jade slip."
                        ),
                    )
                ]
            ),
        )
        item = Item.query.one()

        self.assertEqual(item.review_status, "approved")
        self.assertNotIn("possible_organization_not_item", item.risk_flags)
        self.assertNotIn("non_item_semantics", item.risk_flags)


if __name__ == "__main__":
    unittest.main()
