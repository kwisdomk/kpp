"""Input resolution examples, not measured multimodal answer quality."""

import unittest
from ai.multimodal.media_fusion import fuse_inputs


class FusionTests(unittest.TestCase):
    def test_voice_and_photo_resolve_without_redundant_confirmation(self):
        result = fuse_inputs("", "What is this alarm?", ["SYN-1"], [], has_image=True)
        self.assertFalse(result.needs_clarification)
        self.assertEqual((result.question, result.model_number), ("What is this alarm?", "SYN-1"))

    def test_both_text_and_transcript_are_preserved(self):
        result = fuse_inputs("For my workshop", "Compare these", [], [], has_image=False)
        self.assertEqual(result.question, "For my workshop\nCompare these")

    def test_missing_question_ambiguous_unknown_and_disagreement(self):
        for text, image, mentions, reason in (
            ("", ["SYN-1"], [], "missing_question"),
            ("Question", [], [], "unidentified_image"),
            ("Question", ["SYN-1", "SYN-2"], [], "ambiguous_image"),
            ("Question", ["SYN-1"], ["SYN-2"], "model_disagreement"),
        ):
            result = fuse_inputs(text, "", image, mentions, has_image=True)
            self.assertTrue(result.needs_clarification)
            self.assertIsNone(result.model_number)
            self.assertEqual(result.reason, reason)

    def test_truncated_candidates_never_resolve(self):
        result = fuse_inputs("Question", "", ["SYN-1"], [], has_image=True, truncated=True)
        self.assertTrue(result.needs_clarification)
