"""CPU whisper.cpp adapter. Call only after backend media ownership checks.

This internal interface accepts canonical WAV bytes, not browser codecs or paths
supplied by users. Transcripts are untrusted input, never instructions or evidence.
"""

from dataclasses import dataclass
import io
import math
from pathlib import Path
import subprocess
import tempfile
import threading
import wave


MAX_AUDIO_BYTES = 2 * 1024 * 1024
MAX_TRANSCRIPT_BYTES = 16_000
_transcription_slot = threading.BoundedSemaphore(1)


class InvalidAudioError(ValueError):
    pass


class AsrUnavailableError(RuntimeError):
    pass


class AsrBusyError(RuntimeError):
    pass


class AsrTimeoutError(RuntimeError):
    pass


class AsrExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str  # Configured decoding language; not detected language.
    duration_seconds: float
    status: str  # transcribed | no_speech; no calibrated confidence claim.


def validate_wav(content: bytes) -> tuple[bytes, float]:
    """Require complete, nonempty PCM16 mono 16 kHz WAV, at most 60 seconds.

    Re-encode sample frames into a fresh container to remove uploaded metadata.
    Codec conversion belongs to the bounded backend decoder, not this adapter.
    """
    if not isinstance(content, bytes) or not 44 <= len(content) <= MAX_AUDIO_BYTES:
        raise InvalidAudioError("Audio must be a WAV file within the size limit")
    if content[:4] != b"RIFF" or content[8:12] != b"WAVE":
        raise InvalidAudioError("Audio must be a RIFF WAV file")
    if int.from_bytes(content[4:8], "little") + 8 != len(content):
        raise InvalidAudioError("Incomplete or trailing WAV data")
    try:
        with wave.open(io.BytesIO(content), "rb") as source:
            if (source.getnchannels(), source.getsampwidth(), source.getframerate(),
                    source.getcomptype()) != (1, 2, 16000, "NONE"):
                raise InvalidAudioError("Audio must be PCM16 mono at 16000 Hz")
            frames = source.getnframes()
            if not 0 < frames <= 60 * 16000:
                raise InvalidAudioError("Audio duration must be greater than zero and at most 60 seconds")
            samples = source.readframes(frames + 1)
            if len(samples) != frames * 2:
                raise InvalidAudioError("Incomplete WAV sample data")
        output = io.BytesIO()
        with wave.open(output, "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(16000)
            target.writeframes(samples)
        return output.getvalue(), frames / 16000
    except (wave.Error, EOFError, OSError) as error:
        raise InvalidAudioError("Invalid WAV container") from error


def transcribe_audio(
    content: bytes, *, executable: str, model_path: Path,
    language: str = "en", timeout_seconds: float = 90,
    temporary_directory: Path | None = None,
) -> Transcript:
    """Run one local CPU transcription; config paths must be operator-controlled.

    No download, hosted fallback, translation, initial prompt or shell execution.
    The caller must check RAM before enabling inference and authorize media first.
    """
    if language != "en":
        raise ValueError("Only explicitly configured English decoding is supported")
    if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 120:
        raise ValueError("ASR timeout must be greater than zero and at most 120 seconds")
    canonical, duration = validate_wav(content)
    model_path = Path(model_path).resolve()
    if not executable or not model_path.is_file():
        raise AsrUnavailableError("Configure a local whisper-cli executable and model file")
    if not _transcription_slot.acquire(blocking=False):
        raise AsrBusyError("Speech transcription is busy; retry shortly")
    try:
        with tempfile.TemporaryDirectory(prefix="jenga-asr-", dir=temporary_directory) as work:
            audio_path = Path(work) / "input.wav"
            output_prefix = Path(work) / "transcript"
            audio_path.write_bytes(canonical)
            try:
                result = subprocess.run(
                    [executable, "-m", str(model_path), "-f", str(audio_path),
                     "-l", language, "-t", "2", "-p", "1", "-ng", "-np",
                     "-otxt", "-of", str(output_prefix)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=timeout_seconds, shell=False, check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise AsrTimeoutError("Speech transcription timed out") from error
            except OSError as error:
                raise AsrUnavailableError("Local speech engine is unavailable") from error
            if result.returncode != 0:
                raise AsrExecutionError("Speech engine failed")
            try:
                with output_prefix.with_suffix(".txt").open("rb") as output:
                    raw_text = output.read(MAX_TRANSCRIPT_BYTES + 1)
                if len(raw_text) > MAX_TRANSCRIPT_BYTES:
                    raise AsrExecutionError("Speech output exceeds the limit")
                text = raw_text.decode("utf-8", errors="strict").strip()
            except (OSError, UnicodeError) as error:
                raise AsrExecutionError("Speech engine produced no valid transcript file") from error
            return Transcript(text, language, duration, "transcribed" if text else "no_speech")
    finally:
        _transcription_slot.release()
