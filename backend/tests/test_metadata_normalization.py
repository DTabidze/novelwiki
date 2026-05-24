import unittest

from app.services.metadata_normalization import (
    is_weak_variation,
    normalize_age_text,
    normalize_gender,
    normalize_status,
)


class MetadataNormalizationTest(unittest.TestCase):
    def test_gender_normalizes_masculine_terms(self):
        self.assertEqual(normalize_gender("he").normalized_value, "male")
        self.assertEqual(normalize_gender("young man").normalized_value, "male")

    def test_gender_normalizes_feminine_terms(self):
        self.assertEqual(normalize_gender("she").normalized_value, "female")
        self.assertEqual(normalize_gender("elder sister").normalized_value, "female")

    def test_age_text_normalizes_approximate_wording(self):
        self.assertEqual(
            normalize_age_text("looked around thirty").normalized_value,
            "about 30 years old",
        )
        self.assertEqual(
            normalize_age_text("around thirty years old man").normalized_value,
            "about 30 years old",
        )
        self.assertEqual(
            normalize_age_text("thirty-year-old man").normalized_value,
            "30 years old",
        )
        self.assertEqual(
            normalize_age_text("about sixteen or seventeen").normalized_value,
            "about 16-17 years old",
        )

    def test_age_text_preserves_large_scale_words(self):
        self.assertEqual(
            normalize_age_text("three billion years old").normalized_value,
            "3 billion years old",
        )
        self.assertEqual(
            normalize_age_text("about three million years old").normalized_value,
            "about 3 million years old",
        )

    def test_status_only_accepts_life_status_values(self):
        self.assertIsNone(normalize_status("number one disciple in the Low-Level Public Zone"))
        self.assertEqual(normalize_status("sealed away").normalized_value, "sealed")
        self.assertEqual(normalize_status("he was killed").normalized_value, "dead")

    def test_weak_variation_detects_close_metadata_values(self):
        self.assertTrue(
            is_weak_variation(
                "number one disciple in the low level public zone",
                "number one disciple in the low level",
            )
        )


if __name__ == "__main__":
    unittest.main()
