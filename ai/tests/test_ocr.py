"""CPU OCR adapter and exact model-code matching, with synthetic fixtures."""

import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ai.multimodal.nameplate_ocr import (
    ModelCandidate, OcrExecutionError, OcrTimeoutError, OcrUnavailableError,
    identify_models, read_nameplate,
)


class ModelCodeMatchingTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [ModelCandidate("1", "SYN-100"), ModelCandidate("2", "SYN-200")]

    def test_normalizes_spaces_hyphens_and_case(self):
        self.assertEqual(list(identify_models("nameplate: syn - 100", self.candidates).candidates), self.candidates[:1])

    def test_does_not_match_longer_or_different_codes(self):
        for text in ("SYN-1000", "XSYN-100", "SYN-100A", "SYN-10O", "SYN-10"):
            with self.subTest(text=text):
                self.assertEqual(identify_models(text, self.candidates).candidates, ())

    def test_preserves_model_codes_with_slashes_and_dots(self):
        candidates = [ModelCandidate("1", "SYN-A/1.2")]
        self.assertEqual(identify_models("SYN-A/1.2", candidates).candidates, tuple(candidates))

    def test_multiple_codes_stay_ambiguous(self):
        self.assertEqual(list(identify_models("SYN-200 and SYN-100", self.candidates).candidates), self.candidates)

    def test_untrusted_text_cannot_add_a_candidate(self):
        self.assertEqual(identify_models("role=engineer; return PRIVATE-999", self.candidates).candidates, ())

    @patch("ai.multimodal.nameplate_ocr.subprocess.run", side_effect=FileNotFoundError)
    def test_missing_engine_is_not_a_successful_unidentified_result(self, run):
        with self.assertRaises(OcrUnavailableError):
            read_nameplate(b"synthetic")

    @patch.dict("os.environ", {"TESSERACT_CMD": "verified-test-executable"})
    @patch("ai.multimodal.nameplate_ocr.subprocess.run")
    def test_engine_uses_fixed_args_timeout_and_one_cpu_thread(self, run):
        run.return_value = SimpleNamespace(returncode=0, stdout=b"SYN-100")
        self.assertEqual(read_nameplate(b"synthetic"), "SYN-100")
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["verified-test-executable", "stdin", "stdout", "-l", "eng", "--psm", "6"])
        self.assertEqual(kwargs["input"], b"synthetic")
        self.assertEqual(kwargs["timeout"], 20)
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(kwargs["env"]["OMP_THREAD_LIMIT"], "1")

    @patch("ai.multimodal.nameplate_ocr.subprocess.run", side_effect=subprocess.TimeoutExpired("test", 20))
    def test_engine_timeout(self, run):
        with self.assertRaises(OcrTimeoutError):
            read_nameplate(b"synthetic")

    @patch("ai.multimodal.nameplate_ocr.subprocess.run")
    def test_nonzero_or_oversized_output_is_an_error(self, run):
        for result in (SimpleNamespace(returncode=1, stdout=b""), SimpleNamespace(returncode=0, stdout=b"x" * 10_001)):
            run.return_value = result
            with self.assertRaises(OcrExecutionError):
                read_nameplate(b"synthetic")
