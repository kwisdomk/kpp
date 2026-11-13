"""Reproducible word error counts; this module contains no benchmark gold data."""

from dataclasses import dataclass
from typing import Iterable
import unicodedata


NORMALIZATION = "nfkc-casefold-punctuation-to-space-v1"


def normalize_words(text: str) -> list[str]:
    """Keep letters/numbers, split punctuation, collapse whitespace.

    No number expansion or equipment-code correction: '100' and 'one hundred'
    remain different. Apply this same frozen normalization to both transcripts.
    """
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = "".join(" " if unicodedata.category(char)[0] in "PZC" else char
                         for char in normalized)
    return normalized.split()


@dataclass(frozen=True)
class WordErrors:
    substitutions: int
    deletions: int
    insertions: int
    reference_words: int

    @property
    def wer(self) -> float | None:
        if self.reference_words == 0:
            return None
        return (self.substitutions + self.deletions + self.insertions) / self.reference_words


def word_errors(reference: str, hypothesis: str) -> WordErrors:
    """Minimum edit alignment, ties prefer substitution, deletion, insertion.

    Empty reference has undefined WER (None); hallucinated words still count as
    insertions. Limit each side to 1000 words to bound quadratic scoring work.
    """
    expected, actual = normalize_words(reference), normalize_words(hypothesis)
    if max(len(expected), len(actual)) > 1000:
        raise ValueError("WER scoring is limited to 1000 words per transcript")
    # Entries are (edit cost, substitutions, deletions, insertions).
    previous = [(index, 0, 0, index) for index in range(len(actual) + 1)]
    for row, word in enumerate(expected, 1):
        current = [(row, 0, row, 0)]
        for column, predicted in enumerate(actual, 1):
            cost, substitutions, deletions, insertions = previous[column - 1]
            mismatch = int(word != predicted)
            diagonal = (cost + mismatch, substitutions + mismatch, deletions, insertions)
            cost, substitutions, deletions, insertions = previous[column]
            deletion = (cost + 1, substitutions, deletions + 1, insertions)
            cost, substitutions, deletions, insertions = current[column - 1]
            insertion = (cost + 1, substitutions, deletions, insertions + 1)
            current.append(min((diagonal, deletion, insertion), key=lambda value: value[0]))
        previous = current
    _, substitutions, deletions, insertions = previous[-1]
    return WordErrors(substitutions, deletions, insertions, len(expected))


def aggregate_word_errors(samples: Iterable[WordErrors]) -> WordErrors:
    """Corpus WER uses summed edit counts / summed reference words, not mean WER."""
    samples = list(samples)
    return WordErrors(*(sum(getattr(sample, field) for sample in samples)
                        for field in ("substitutions", "deletions", "insertions", "reference_words")))
