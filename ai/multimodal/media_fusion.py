"""Deterministic input fusion; callers supply only authorized model candidates."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FusedInput:
    question: str
    model_number: str | None
    needs_clarification: bool
    reason: str


def fuse_inputs(text: str, transcript: str, image_models: list[str],
                mentioned_models: list[str], *, has_image: bool, truncated: bool = False) -> FusedInput:
    question = "\n".join(part.strip() for part in (text, transcript) if part.strip())
    if not question:
        return FusedInput("", None, True, "missing_question")
    if has_image and (len(image_models) != 1 or truncated):
        return FusedInput(question, None, True, "ambiguous_image" if image_models else "unidentified_image")
    if has_image and any(model != image_models[0] for model in mentioned_models):
        return FusedInput(question, None, True, "model_disagreement")
    model = image_models[0] if has_image else mentioned_models[0] if len(mentioned_models) == 1 else None
    return FusedInput(question, model, False, "inputs_ready")
