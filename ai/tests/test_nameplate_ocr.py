import subprocess
import unittest
from unittest.mock import patch

from ai.multimodal.nameplate_ocr import ModelCandidate, identify_models, read_nameplate


class NameplateTests(unittest.TestCase):
    def test_matches_only_supplied_candidates_and_respects_boundaries(self):
        candidates = [ModelCandidate("1", "JCG-1000"), ModelCandidate("2", "JCG-100")]
        result = identify_models("Model: jcg-1000", candidates)
        self.assertEqual(result.candidates, (candidates[0],))
        self.assertFalse(result.requires_confirmation)

    def test_ambiguous_and_missing_models_require_confirmation(self):
        candidates = [ModelCandidate("1", "A-1"), ModelCandidate("2", "B-2")]
        self.assertTrue(identify_models("A-1 / B-2", candidates).requires_confirmation)
        self.assertTrue(identify_models("unknown", candidates).requires_confirmation)

    @patch("ai.multimodal.nameplate_ocr.subprocess.run")
    def test_ocr_uses_bytes_and_fails_closed(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout=b"Model A-1", stderr=b"")
        self.assertEqual(read_nameplate(b"image"), "Model A-1")
        self.assertEqual(run.call_args.kwargs["input"], b"image")
        run.side_effect = subprocess.TimeoutExpired("tesseract", 20)
        with self.assertRaises(RuntimeError):
            read_nameplate(b"image")


if __name__ == "__main__":
    unittest.main()
