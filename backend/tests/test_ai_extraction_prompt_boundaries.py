from app.services.ai_extraction_prompts import (
    BASE_EXTRACTION_SYSTEM_PROMPT,
    CHARACTER_EXTRACTION_PROMPT,
    ITEM_EXTRACTION_PROMPT,
    LIFE_EVENT_EXTRACTION_PROMPT,
    PROGRESSION_EXTRACTION_PROMPT,
    PROGRESSION_AUDIT_PROMPT,
    PROGRESSION_REASONING_PROMPT,
    SKILL_EXTRACTION_PROMPT,
)
from app.services.ai_extraction_schemas import (
    ExtractedCharacter,
    ExtractedCharacterItem,
    ExtractedCharacterSkill,
    ExtractedEvent,
    ExtractedItem,
    ExtractedLifeEvent,
    ExtractedProgressionEvent,
    ExtractedSkill,
)
import unittest


def field_description(model, field_name):
    if hasattr(model, "model_fields"):
        return model.model_fields[field_name].description

    return model.__fields__[field_name].field_info.description


def normalized_prompt_text(prompt):
    return " ".join(prompt.lower().split())


def test_skill_prompt_blocks_progression_states_as_skills():
    prompt = normalized_prompt_text(SKILL_EXTRACTION_PROMPT)

    assert "do not extract cultivation realms, ranks, levels" in prompt
    assert "qi condensation" in prompt
    assert "foundation establishment" in prompt
    assert "bronze rank" in prompt
    assert "level 7" in prompt
    assert "outer sect disciple" in prompt
    assert "qi condensation method" in prompt
    assert "qi condensation manual" in prompt


def test_skill_prompt_blocks_item_artifact_links_as_character_skills():
    prompt = normalized_prompt_text(SKILL_EXTRACTION_PROMPT)

    assert "do not create character_skills entries for items or artifacts" in prompt
    assert "wind pennant" in prompt
    assert "character_item, not character_skill" in prompt
    assert "flame serpent art" in prompt
    assert "character_skill" in prompt


def test_item_prompt_blocks_skills_unless_physical_media():
    prompt = normalized_prompt_text(ITEM_EXTRACTION_PROMPT)

    assert "do not extract techniques, arts, spells, abilities, methods, or skills as items" in prompt
    assert "manual, book, scroll, jade slip, tome, scripture, written record" in prompt
    assert "flame serpent art" in prompt
    assert "skill, not item" in prompt
    assert "flame serpent art manual" in prompt
    assert "water arrow technique jade slip" in prompt


def test_progression_prompts_block_skills_as_progression_values():
    for prompt_text in (
        PROGRESSION_EXTRACTION_PROMPT,
        PROGRESSION_REASONING_PROMPT,
    ):
        prompt = normalized_prompt_text(prompt_text)

        assert "skills, techniques, arts, spells, abilities" in prompt
        assert "were-demon skill" in prompt
        assert "flame serpent art" in prompt
        assert "skills/arts/techniques are skills, not progression" in prompt
        assert "bronze rank" in prompt
        assert "level 7" in prompt


def test_schema_descriptions_do_not_invite_rank_as_skill():
    skill_category_description = field_description(ExtractedSkill, "category").lower()
    skill_name_description = field_description(ExtractedSkill, "name").lower()
    item_name_description = field_description(ExtractedItem, "name").lower()

    assert "or rank" not in skill_category_description
    assert "such as technique, ability, spell, or rank" not in skill_category_description
    assert "not a realm/rank/level" in skill_category_description
    assert "progression ranks/realms/levels are not skills" in skill_name_description
    assert "items and artifacts are not skills" in skill_name_description
    assert "are not items unless evidence says they are a physical medium" in item_name_description


def test_extraction_prompts_require_exact_raw_evidence():
    for prompt_text in (
        BASE_EXTRACTION_SYSTEM_PROMPT,
        CHARACTER_EXTRACTION_PROMPT,
        PROGRESSION_EXTRACTION_PROMPT,
        PROGRESSION_REASONING_PROMPT,
        PROGRESSION_AUDIT_PROMPT,
        SKILL_EXTRACTION_PROMPT,
        ITEM_EXTRACTION_PROMPT,
        LIFE_EVENT_EXTRACTION_PROMPT,
    ):
        prompt = normalized_prompt_text(prompt_text)

        assert "return only exact raw text from the provided chapter" in prompt
        assert "the evidence string must appear in the chapter text" in prompt
        assert "do not paraphrase" in prompt
        assert "do not replace aliases with canonical names in evidence" in prompt
        assert "if no exact excerpt supports the fact, do not extract that fact" in prompt
        assert "do not stitch together non-contiguous sentences" in prompt
        assert "do not add \"...\" unless the ellipsis appears in the chapter text" in prompt


def test_extraction_prompts_require_evidence_to_directly_prove_fact():
    for prompt_text in (
        BASE_EXTRACTION_SYSTEM_PROMPT,
        CHARACTER_EXTRACTION_PROMPT,
        PROGRESSION_EXTRACTION_PROMPT,
        PROGRESSION_REASONING_PROMPT,
        PROGRESSION_AUDIT_PROMPT,
        SKILL_EXTRACTION_PROMPT,
        ITEM_EXTRACTION_PROMPT,
        LIFE_EVENT_EXTRACTION_PROMPT,
    ):
        prompt = normalized_prompt_text(prompt_text)

        assert "evidence must directly prove the candidate fact itself" in prompt
        assert "weak nearby evidence" in prompt
        assert "scene, location, movement, owner, item, skill, or character" in prompt
        assert "if exact raw evidence does not directly prove the fact, omit the fact" in prompt
        assert "the backend verifies evidence against chapter text" in prompt


def test_relationship_prompts_require_action_proof():
    item_prompt = normalized_prompt_text(ITEM_EXTRACTION_PROMPT)
    skill_prompt = normalized_prompt_text(SKILL_EXTRACTION_PROMPT)

    assert "the evidence must prove both the character/item attribution and the exact relationship action" in item_prompt
    assert "obtained/received evidence must show the character actually got" in item_prompt
    assert "used evidence must show actual use, not intent or preparation" in item_prompt
    assert "lost evidence must show the item was actually lost" in item_prompt
    assert "demand/threat" in item_prompt
    assert "nearby scene movement" in item_prompt
    assert "vague possession like \"treasures\"" in item_prompt

    assert "the evidence must prove the character-skill relationship action" in skill_prompt
    assert "only mentions the skill name nearby" in skill_prompt


def test_entity_metadata_progression_and_life_event_evidence_quality_rules_exist():
    prompt = normalized_prompt_text(BASE_EXTRACTION_SYSTEM_PROMPT)

    assert "for character identity, evidence should contain the character name, alias, stable label" in prompt
    assert "for items, evidence should directly mention the item and show it as a real physical object" in prompt
    assert "for skills, evidence should directly mention the skill/technique/art/ability" in prompt
    assert "age evidence contains age wording" in prompt
    assert "faction evidence contains membership/affiliation wording" in prompt
    assert "species evidence explicitly communicates species/race" in prompt
    assert "preserve wording such as \"peak of the second level\"" in prompt
    assert "death evidence must clearly show death, killed, corpse, lifeless, dead" in prompt


def test_prompt_examples_reject_weak_nearby_or_rewritten_evidence():
    prompt = normalized_prompt_text(BASE_EXTRACTION_SYSTEM_PROMPT)

    assert "li furui broke through to the second level" in prompt
    assert "fatty broke through to the second level" in prompt
    assert "hand over your treasures" in prompt
    assert "a demand or threat does not prove the item was actually lost" in prompt
    assert "scene-related movement does not prove the character obtained the item" in prompt


def test_evidence_schema_descriptions_require_exact_raw_chapter_text():
    evidence_models = (
        ExtractedCharacter,
        ExtractedSkill,
        ExtractedItem,
        ExtractedEvent,
        ExtractedProgressionEvent,
        ExtractedLifeEvent,
        ExtractedCharacterSkill,
        ExtractedCharacterItem,
    )

    for model in evidence_models:
        description = field_description(model, "evidence").lower()

        assert "exact short excerpt copied verbatim from the chapter text" in description
        assert "do not paraphrase" in description
        assert "the evidence string must appear in the chapter text" in description
        assert "directly prove the candidate fact" in description
        assert "snippet or paraphrase" not in description


def test_relationship_schema_descriptions_require_exact_action_support():
    character_item_description = field_description(ExtractedCharacterItem, "evidence").lower()
    character_skill_description = field_description(ExtractedCharacterSkill, "evidence").lower()

    assert "prove both character/item attribution and the exact relationship action" in character_item_description
    assert "demands, threats, item appearances" in character_item_description
    assert "nearby scene movement" in character_item_description
    assert "vague treasures" in character_item_description

    assert "prove the character learned, used, cultivated, practiced, displayed, mastered" in character_skill_description
    assert "do not use evidence that only mentions the skill nearby" in character_skill_description


def test_entity_schema_descriptions_require_type_specific_evidence_support():
    character_description = field_description(ExtractedCharacter, "evidence").lower()
    item_description = field_description(ExtractedItem, "evidence").lower()
    skill_description = field_description(ExtractedSkill, "evidence").lower()
    progression_description = field_description(ExtractedProgressionEvent, "evidence").lower()
    life_event_description = field_description(ExtractedLifeEvent, "evidence").lower()

    assert "character name, alias, stable label" in character_description
    assert "directly mention the item and show it as a real physical object" in item_description
    assert "directly mention the skill/technique/art/ability" in skill_description
    assert "directly support the exact new_value" in progression_description
    assert "preserve uncertainty or near-breakthrough wording" in progression_description
    assert "directly support the hard life-status event" in life_event_description


class TestAiExtractionPromptBoundaries(unittest.TestCase):
    def test_skill_prompt_blocks_progression_states_as_skills(self):
        test_skill_prompt_blocks_progression_states_as_skills()

    def test_skill_prompt_blocks_item_artifact_links_as_character_skills(self):
        test_skill_prompt_blocks_item_artifact_links_as_character_skills()

    def test_item_prompt_blocks_skills_unless_physical_media(self):
        test_item_prompt_blocks_skills_unless_physical_media()

    def test_progression_prompts_block_skills_as_progression_values(self):
        test_progression_prompts_block_skills_as_progression_values()

    def test_schema_descriptions_do_not_invite_rank_as_skill(self):
        test_schema_descriptions_do_not_invite_rank_as_skill()

    def test_extraction_prompts_require_exact_raw_evidence(self):
        test_extraction_prompts_require_exact_raw_evidence()

    def test_extraction_prompts_require_evidence_to_directly_prove_fact(self):
        test_extraction_prompts_require_evidence_to_directly_prove_fact()

    def test_relationship_prompts_require_action_proof(self):
        test_relationship_prompts_require_action_proof()

    def test_entity_metadata_progression_and_life_event_evidence_quality_rules_exist(self):
        test_entity_metadata_progression_and_life_event_evidence_quality_rules_exist()

    def test_prompt_examples_reject_weak_nearby_or_rewritten_evidence(self):
        test_prompt_examples_reject_weak_nearby_or_rewritten_evidence()

    def test_evidence_schema_descriptions_require_exact_raw_chapter_text(self):
        test_evidence_schema_descriptions_require_exact_raw_chapter_text()

    def test_relationship_schema_descriptions_require_exact_action_support(self):
        test_relationship_schema_descriptions_require_exact_action_support()

    def test_entity_schema_descriptions_require_type_specific_evidence_support(self):
        test_entity_schema_descriptions_require_type_specific_evidence_support()
