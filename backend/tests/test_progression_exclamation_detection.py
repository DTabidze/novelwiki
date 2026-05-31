import unittest

from app.services.extraction.progression import (
    DIRECT_QI_LEVEL_RE,
    is_direct_current_level_context,
    snippet_around_match,
)


class ProgressionExclamationDetectionTest(unittest.TestCase):
    def test_exclamation_context_includes_following_confirmation(self):
        text = (
            "The aura around him surged. "
            "“The ninth level of Qi Condensation! I, Meng Hao, have finally reached the ninth level! "
            "My next step will be Foundation Establishment!” "
            "His eyes filled with exuberance, he took several deep breaths."
        )
        match = DIRECT_QI_LEVEL_RE.search(text)

        self.assertIsNotNone(match)
        evidence = snippet_around_match(text, match, following_sentences=2)

        self.assertIn("ninth level of Qi Condensation", evidence)
        self.assertIn("have finally reached the ninth level", evidence)
        self.assertTrue(is_direct_current_level_context(evidence))


if __name__ == "__main__":
    unittest.main()
