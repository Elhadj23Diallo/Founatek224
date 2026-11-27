"""Process existing Academy videos or prepare a portable cache offline."""

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management.base import BaseCommand, CommandError

from iot import academy_audio
from iot.book_catalog import BOOK_SLUG
from iot.management.commands.import_academy_book_v2 import (
    MEDIA_DIR, _video_source, lesson_hash, optimize_video, read_entries,
    update_video_audio, video_sources,
)
from iot.models import BlocPedagogique, Lecon


class Command(BaseCommand):
    help = "Normaliser l'audio des vidéos Academy hors requête HTTP (simulation par défaut)."

    def add_arguments(self, parser):
        selection = parser.add_mutually_exclusive_group(required=True)
        selection.add_argument("--lesson", help="Identifiant du Livre 1, par exemple 0.1.")
        selection.add_argument("--chapter", help="Partie du Livre 1.")
        selection.add_argument("--uploaded-lesson-id", type=int, help="Clé Django d'une leçon avec vidéos envoyées.")
        selection.add_argument("--uploaded", action="store_true", help="Toutes les vidéos MP4 envoyées dans les leçons.")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--export-cache", type=Path, help="Préparer les copies du Livre 1 dans ce dossier, sans base.")
        parser.add_argument("--audio-cache-dir", type=Path, help="Réutiliser un dossier préparé sur une autre machine.")

    def handle(self, *args, **options):
        executable = academy_audio.find_ffmpeg() if options["apply"] else None
        if options["uploaded"] or options["uploaded_lesson_id"] is not None:
            if options["export_cache"]:
                raise CommandError("--export-cache est réservé aux vidéos sources du Livre 1.")
            self._uploaded(options, executable)
            return

        if options["export_cache"] and options["audio_cache_dir"]:
            raise CommandError("Choisis soit l'export, soit la lecture d'un cache.")
        for entry in read_entries(options["chapter"], options["lesson"]):
            names = video_sources(entry)
            if not names:
                continue
            if not options["apply"]:
                self.stdout.write(f"Simulation {entry['id']} : " + ", ".join(names))
            elif options["export_cache"]:
                if not executable:
                    raise CommandError("FFmpeg est introuvable. Configure ACADEMY_FFMPEG.")
                for name in names:
                    try:
                        output = academy_audio.export_rendition(_video_source(name), options["export_cache"], executable)
                    except (academy_audio.AudioNormalizationError, OSError) as error:
                        raise CommandError(f"{name} : {error}") from error
                    self.stdout.write(f"{name} : {output}")
            else:
                lesson = Lecon.objects.filter(
                    parcours__slug=BOOK_SLUG, titre__startswith=f"{entry['id']} —",
                    academy_book_entry__content_hash=lesson_hash(entry),
                ).first()
                if lesson is None:
                    self.stderr.write(f"{entry['id']} : importe d'abord la version actuelle de la leçon.")
                    continue
                count = update_video_audio(lesson, entry, executable, options["audio_cache_dir"], self.stderr.write)
                self.stdout.write(f"{entry['id']} : {count} vidéo(s) mise(s) à jour.")

    def _uploaded(self, options, executable):
        blocks = (BlocPedagogique.objects.filter(type="video", media_file__iendswith=".mp4")
                  .exclude(media_file__startswith=f"{MEDIA_DIR}/")
                  .exclude(media_file__startswith=f"{academy_audio.MEDIA_PREFIX}/"))
        if options["uploaded_lesson_id"] is not None:
            blocks = blocks.filter(lecon_id=options["uploaded_lesson_id"])
        for block in blocks.iterator():
            current = block.media_file.name
            if not options["apply"]:
                self.stdout.write(f"Simulation — bloc {block.pk} : {current}")
                continue
            try:
                with TemporaryDirectory(prefix="academy-upload-") as temporary:
                    source = Path(temporary) / "original.mp4"
                    with block.media_file.storage.open(current, "rb") as upload, source.open("wb") as local:
                        shutil.copyfileobj(upload, local)
                    rendition = optimize_video(source, executable, options["audio_cache_dir"], self.stderr.write)
            except OSError as error:
                self.stderr.write(f"Bloc {block.pk} : {error}. La vidéo originale est conservée.")
                continue
            if rendition and blocks.filter(pk=block.pk, media_file=current).update(media_file=rendition):
                self.stdout.write(f"Bloc {block.pk} : audio optimisé.")
