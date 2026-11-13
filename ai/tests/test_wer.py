"""Metric examples verify arithmetic, not measured ASR quality."""

import unittest

from ai.multimodal.wer import aggregate_word_errors, normalize_words, word_errors


class WordErrorTests(unittest.TestCase):
    def test_normalization_preserves_numbers_and_model_characters(self):
        self.assertEqual(normalize_words("  Compare SYN-100, ＰＵＭＰ!\n"),
                         ["compare", "syn", "100", "pump"])
        self.assertGreater(word_errors("100", "one hundred").wer, 0)

    def test_exact_substitution_deletion_and_insertion_counts(self):
        cases = (("a b c", "a b c", (0, 0, 0, 3)),
                 ("a b c", "a x c", (1, 0, 0, 3)),
                 ("a b c", "a c", (0, 1, 0, 3)),
                 ("a b c", "a b x c", (0, 0, 1, 3)),
                 ("a b c d", "a x c y d", (1, 0, 1, 4)))
        for reference, hypothesis, expected in cases:
            result = word_errors(reference, hypothesis)
            self.assertEqual((result.substitutions, result.deletions,
                              result.insertions, result.reference_words), expected)

    def test_empty_reference_has_no_defined_wer_but_counts_insertions(self):
        for hypothesis, count in (("", 0), ("invented speech", 2)):
            result = word_errors("", hypothesis)
            self.assertIsNone(result.wer)
            self.assertEqual(result.insertions, count)
        result = word_errors("actual speech", "")
        self.assertEqual((result.deletions, result.wer), (2, 1.0))

    def test_wer_can_exceed_one(self):
        self.assertEqual(word_errors("a", "a b c").wer, 2.0)

    def test_corpus_uses_reference_word_weighting(self):
        samples = [word_errors("a", "x"), word_errors("a b c", "a b c")]
        self.assertEqual(aggregate_word_errors(samples).wer, 0.25)
        self.assertIsNone(aggregate_word_errors([]).wer)

    def test_silence_insertions_contribute_to_corpus_total(self):
        samples = [word_errors("", "phantom words"), word_errors("a b", "a b")]
        self.assertEqual(aggregate_word_errors(samples).wer, 1.0)

    def test_scoring_work_is_bounded(self):
        with self.assertRaises(ValueError):
            word_errors("word " * 1001, "word")


if __name__ == "__main__":
    unittest.main()
