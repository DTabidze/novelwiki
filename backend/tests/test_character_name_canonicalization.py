import unittest

from app.services.ai_extraction_service import select_canonical_character_name


class CharacterNameCanonicalizationTest(unittest.TestCase):
    def test_title_style_name_beats_weak_honorific(self):
        canonical_name, aliases = select_canonical_character_name(
            "Ms. Xu",
            ["Elder Sister Xu", "Sister Xu", "pale-faced woman"],
        )

        self.assertEqual(canonical_name, "Elder Sister Xu")
        self.assertIn("Ms. Xu", aliases)
        self.assertIn("Sister Xu", aliases)
        self.assertIn("pale-faced woman", aliases)

    def test_full_real_name_beats_nicknames(self):
        canonical_name, aliases = select_canonical_character_name(
            "Li Furui",
            ["Fatty", "Fat Teenager"],
        )

        self.assertEqual(canonical_name, "Li Furui")
        self.assertIn("Fatty", aliases)
        self.assertIn("Fat Teenager", aliases)

    def test_stable_label_can_remain_canonical_without_real_name(self):
        canonical_name, aliases = select_canonical_character_name(
            "Fat Teenager",
            ["Fatty"],
        )

        self.assertEqual(canonical_name, "Fat Teenager")
        self.assertIn("Fatty", aliases)

    def test_title_style_name_beats_visual_description(self):
        canonical_name, aliases = select_canonical_character_name(
            "silver-robed woman",
            ["Elder Sister Xu"],
        )

        self.assertEqual(canonical_name, "Elder Sister Xu")
        self.assertIn("silver-robed woman", aliases)

    def test_visual_description_allowed_when_only_candidate(self):
        canonical_name, aliases = select_canonical_character_name(
            "green-robed man",
            [],
        )

        self.assertEqual(canonical_name, "green-robed man")
        self.assertEqual(aliases, [])


if __name__ == "__main__":
    unittest.main()
