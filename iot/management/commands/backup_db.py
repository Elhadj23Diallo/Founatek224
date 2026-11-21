"""Sauvegarde de la base SQLite : copie cohérente, vérifiée, compressée, avec rotation.

Usage (tâche planifiée quotidienne sur PythonAnywhere) :
    cd ~/Founatek224 && python manage.py backup_db

Par défaut, les sauvegardes vont dans ~/founatek_backups (hors du dépôt Git)
et les 14 plus récentes sont gardées. Variable BACKUP_DIR du .env ou option
--dest pour un autre dossier ; --keep pour un autre nombre.
"""
import gzip
import os
import shutil
import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

PREFIX = "founatek-"
SUFFIX = ".sqlite3.gz"


class Command(BaseCommand):
    help = "Sauvegarde la base SQLite (copie cohérente, vérifiée et compressée) et garde les N dernières."

    def add_arguments(self, parser):
        parser.add_argument("--dest", default=os.getenv("BACKUP_DIR") or str(Path.home() / "founatek_backups"))
        parser.add_argument("--keep", type=int, default=14)
        parser.add_argument("--source", default=None, help="Fichier SQLite à sauvegarder (par défaut : la base du site).")

    def handle(self, *args, **options):
        source = Path(options["source"] or self._database_path())
        if not source.is_file():
            raise CommandError(f"Base introuvable : {source}")
        if options["keep"] < 1:
            raise CommandError("--keep doit valoir au moins 1.")
        dest = Path(options["dest"]).expanduser()
        dest.mkdir(parents=True, exist_ok=True)

        stamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
        raw = dest / f"{PREFIX}{stamp}.sqlite3"
        final = dest / f"{PREFIX}{stamp}{SUFFIX}"

        # API de sauvegarde SQLite : copie cohérente même si le site écrit pendant ce temps.
        src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
        dst = sqlite3.connect(raw)
        try:
            src.backup(dst)
        finally:
            src.close()
            dst.close()

        check = sqlite3.connect(raw)
        try:
            result = check.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            check.close()
        if result != "ok":
            raw.unlink(missing_ok=True)
            raise CommandError(f"Sauvegarde corrompue ({result}) : rien n'a été gardé.")

        with open(raw, "rb") as fin, gzip.open(final, "wb", compresslevel=6) as fout:
            shutil.copyfileobj(fin, fout)
        raw.unlink()

        backups = sorted(dest.glob(f"{PREFIX}*{SUFFIX}"))
        removed = backups[:-options["keep"]]
        for old in removed:
            old.unlink()

        size_mb = final.stat().st_size / 1_048_576
        self.stdout.write(self.style.SUCCESS(
            f"Sauvegarde OK : {final} ({size_mb:.1f} Mo). "
            f"{len(backups) - len(removed)} sauvegarde(s) gardée(s), {len(removed)} supprimée(s)."
        ))

    def _database_path(self):
        db = settings.DATABASES["default"]
        if db.get("ENGINE") != "django.db.backends.sqlite3":
            raise CommandError("Cette commande sauvegarde uniquement une base SQLite.")
        return db["NAME"]
