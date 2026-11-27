"""Offline audio renditions. Originals and previously served media remain immutable."""

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.core.files.base import ContentFile, File
from django.core.files.storage import default_storage


MEDIA_PREFIX = "academy/audio"
LOUDNESS = -16
MAX_PEAK = -1.5
PROFILE = "v1:mp4:first-audio:copy-video:aac-160k-48k:lra11:tp-2,-3"
NORMALIZED_TAG = "founatek_audio_normalized"
MEASUREMENTS = {
    "measured_I": "input_i", "measured_TP": "input_tp",
    "measured_LRA": "input_lra", "measured_thresh": "input_thresh", "offset": "target_offset",
}


class AudioNormalizationError(Exception):
    pass


def file_sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def cache_key(source):
    return hashlib.sha256(f"{PROFILE}:{LOUDNESS}:{MAX_PEAK}:{file_sha256(source)}".encode()).hexdigest()


def find_ffmpeg():
    return shutil.which(os.environ.get("ACADEMY_FFMPEG") or "ffmpeg")


def _ffmpeg(executable, source, arguments):
    # Restrict demuxing and disable network protocols. Do not invoke a shell.
    try:
        process = subprocess.run(
            [executable, "-nostdin", "-hide_banner", "-y", "-protocol_whitelist", "file",
             "-threads", "2", "-filter_threads", "2", "-f", "mov", "-i",
             str(source.resolve()), *arguments],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, encoding="utf-8",
            errors="replace", timeout=900, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AudioNormalizationError("FFmpeg inaccessible ou délai de traitement dépassé.") from error
    if process.returncode:
        raise AudioNormalizationError("FFmpeg n'a pas pu lire ou traiter les pistes vidéo et audio.")
    return process.stderr


def _filter(peak):
    return f"loudnorm=I={LOUDNESS}:TP={peak}:LRA=11"


def measure(executable, source, peak=-2, *, require_original=False):
    report = _ffmpeg(
        executable, source,
        ["-map", "0:a:0", "-af", f"{_filter(peak)}:print_format=json", "-f", "null", "-"],
    )
    if require_original and re.search(rf"^\s*{NORMALIZED_TAG}\s*:\s*1\s*$", report, re.MULTILINE):
        raise AudioNormalizationError("Ce fichier porte déjà la marque de normalisation Academy.")
    match = re.search(r'\{\s*"input_i"[^{}]*\}', report)
    try:
        return json.loads(match.group())
    except (AttributeError, ValueError) as error:
        raise AudioNormalizationError("Mesures loudnorm introuvables.") from error


def _number_fields(statistics, fields):
    try:
        return [float(statistics[field]) for field in fields]
    except (KeyError, ValueError, TypeError) as error:
        raise AudioNormalizationError("Mesures loudnorm invalides.") from error


def normalize_file(source, destination, executable):
    if source.resolve() == destination.resolve() or (destination.exists() and source.samefile(destination)):
        raise AudioNormalizationError("La sortie doit être distincte de la vidéo originale.")
    if not executable:
        raise AudioNormalizationError("FFmpeg est introuvable.")
    statistics = measure(executable, source, require_original=True)
    numbers = dict(zip(MEASUREMENTS, _number_fields(statistics, MEASUREMENTS.values())))
    if not all(math.isfinite(value) for value in numbers.values()):
        raise AudioNormalizationError("Piste silencieuse ou niveau audio non mesurable.")

    measured = ":".join(f"{name}={value}" for name, value in numbers.items())
    for peak in (-2, -3):
        if peak == -3:
            # FFmpeg's offset is tied to the first pass's true-peak target.
            offset, = _number_fields(measure(executable, source, peak), ("target_offset",))
            if not math.isfinite(offset):
                break
            measured = measured.rsplit(":offset=", 1)[0] + f":offset={offset}"
        _ffmpeg(
            executable, source,
            ["-map", "0:V:0", "-map", "0:a:0", "-c:v", "copy", "-af",
             f"{_filter(peak)}:{measured}:linear=true",
             "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
             "-metadata", f"{NORMALIZED_TAG}=1", "-movflags", "+faststart+use_metadata_tags",
             str(destination.resolve())],
        )
        # The AAC encoder can introduce overshoot. Accept only the measured final file.
        actual = measure(executable, destination)
        actual_peak, actual_loudness = _number_fields(actual, ("input_tp", "input_i"))
        if math.isfinite(actual_peak) and actual_peak <= MAX_PEAK and math.isfinite(actual_loudness):
            return actual
    raise AudioNormalizationError("Le pic vrai dépasse la limite sur le fichier AAC encodé.")


def _portable_file(directory, key):
    if directory is None:
        return None
    video = directory / f"{key}.mp4"
    try:
        manifest = json.loads((directory / f"{key}.json").read_text(encoding="utf-8"))
        if manifest == {"sha256": file_sha256(video)}:
            return video
    except (OSError, ValueError):
        pass
    return None


def export_rendition(source, directory, executable):
    key = cache_key(source)
    if existing := _portable_file(directory, key):
        return existing
    if not executable:
        raise AudioNormalizationError("FFmpeg est introuvable. Configure ACADEMY_FFMPEG.")
    directory.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=directory, prefix=".academy-audio-") as temporary:
        video = Path(temporary) / "video.mp4"
        normalize_file(source, video, executable)
        manifest = Path(temporary) / "ready.json"
        manifest.write_text(json.dumps({"sha256": file_sha256(video)}), encoding="utf-8")
        output = directory / f"{key}.mp4"
        video.replace(output)
        manifest.replace(directory / f"{key}.json")
    return output


def _stored_rendition(prefix, storage):
    manifest = f"{prefix}/ready.json"
    if not storage.exists(manifest):
        return None
    with storage.open(manifest, "rb") as stream:
        name = stream.read(200).decode("ascii", errors="replace")
    if (re.fullmatch(r"[0-9a-f]{16}\.mp4", name)
            and storage.exists(f"{prefix}/{name}")):
        return f"{prefix}/{name}"
    raise AudioNormalizationError("Cache audio incomplet. Vérifie le fichier ready.json.")


def optimize_for_storage(source, executable, cache_directory=None, *, storage=default_storage):
    """Return an immutable Django storage name, processing only an original."""
    prefix = f"{MEDIA_PREFIX}/{cache_key(source)}"
    if existing := _stored_rendition(prefix, storage):
        return existing
    with TemporaryDirectory(prefix="academy-audio-") as temporary:
        video = _portable_file(cache_directory, prefix.rsplit("/", 1)[1])
        if video is None:
            video = Path(temporary) / "video.mp4"
            normalize_file(source, video, executable)
        with video.open("rb") as stream:
            name = storage.save(f"{prefix}/{uuid4().hex[:16]}.mp4", File(stream))
    # Publish only a completely written artifact. Concurrent writers never replace a video.
    marker = storage.save(f"{prefix}/ready.json", ContentFile(Path(name).name.encode("ascii")))
    if marker != f"{prefix}/ready.json":
        storage.delete(marker)
        return _stored_rendition(prefix, storage) or name
    return name
