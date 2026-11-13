"""Nameplate OCR and matching against a caller-authorized candidate list.

The backend must authenticate the user and filter candidates before calling this
module. OCR text is untrusted and must never be treated as instructions.
"""

from __future__ import annotations

import re
import subprocess
import math
import os
from dataclasses import dataclass
from typing import Iterable


class OcrUnavailableError(RuntimeError):
    pass


class OcrTimeoutError(RuntimeError):
    pass


class OcrExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelCandidate:
    product_id: str
    model_number: str


@dataclass(frozen=True)
class Identification:
    candidates: tuple[ModelCandidate, ...]
    requires_confirmation: bool


def read_nameplate(image_bytes: bytes, *, timeout_seconds: float = 20) -> str:
    """Run local Tesseract on image bytes; the caller must validate the image first."""
    if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 20:
        raise ValueError("OCR timeout must be positive and at most 20 seconds")
    environment = os.environ.copy()
    environment["OMP_THREAD_LIMIT"] = "1"
    try:
        result = subprocess.run(
            [os.getenv("TESSERACT_CMD", "tesseract"), "stdin", "stdout", "-l", "eng", "--psm", "6"],
            input=image_bytes, capture_output=True, timeout=timeout_seconds,
            check=False, env=environment, shell=False,
        )
    except subprocess.TimeoutExpired as error:
        raise OcrTimeoutError("OCR timed out") from error
    except OSError as error:
        raise OcrUnavailableError("OCR executable is unavailable") from error
    except subprocess.CalledProcessError as error:
        raise OcrExecutionError("OCR failed") from error
    if result.returncode != 0 or len(result.stdout) > 10_000:
        raise OcrExecutionError("OCR could not produce bounded readable text")
    return result.stdout.decode("utf-8", errors="replace")


def identify_models(text: str, authorized_candidates: Iterable[ModelCandidate]) -> Identification:
    """Find exact model numbers; multiple matches must be confirmed by the user."""
    matches = []
    for candidate in authorized_candidates:
        model = re.sub(r"[^A-Z0-9]", "", candidate.model_number.upper())
        if len(model) < 2:
            continue
        pattern = r"(?<![A-Za-z0-9])" + r"[\s./_-]*".join(re.escape(char) for char in model) + r"(?![A-Za-z0-9])"
        if re.search(pattern, text, flags=re.IGNORECASE):
            matches.append(candidate)
    return Identification(tuple(matches), requires_confirmation=len(matches) != 1)
