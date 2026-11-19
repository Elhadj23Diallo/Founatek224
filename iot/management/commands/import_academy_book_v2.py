"""Importer les leçons ENRICHIES du Livre 1 (cours complet, photo, schéma de
câblage, matériel, emplacement vidéo, quiz) depuis iot/academy_source/v2/.

Usage :
    python manage.py import_academy_book_v2                  # simulation
    python manage.py import_academy_book_v2 --apply          # tout le livre
    python manage.py import_academy_book_v2 --chapter 00 --apply

Garanties :
- ne publie RIEN : les nouvelles leçons sont en brouillon, et l'état
  « publié » des leçons existantes n'est pas modifié ;
- ne touche ni aux progressions des apprenants, ni aux certificats ;
- une leçon déjà à jour (même empreinte) n'est pas reconstruite ;
- une vidéo déjà envoyée par le formateur est conservée ;
- si une leçon change, ses blocs et ses quiz sont remplacés par la source.

Format d'une leçon (chapter_XX.json = liste de leçons) :
{
  "id": "0.1", "titre": "…", "resume": "…", "duree_minutes": 35,
  "photo": {"fichier": "0.1-photo.jpg", "legende": "…", "credit": "…"},
  "materiel": ["1 × …", …],
  "video": "Ce que montrera la vidéo (markdown)",
  "blocs": [
     {"type": "texte", "contenu": "markdown + formules"},
     {"type": "schema", "fichier": "0.1-schema.svg", "legende": "…"},
     {"type": "image",  "fichier": "…", "legende": "…", "credit": "…"},
     {"type": "code", "language": "cpp", "code": "…"}
  ],
  "quiz": [{"question": "…", "choix": ["…", "…", "…", "…"],
            "bonnes": ["B"], "explication": "…"}]
}
Le premier bloc texte (objectifs) est suivi du matériel puis de la vidéo.
Les fichiers (photos, schémas) sont dans iot/academy_source/v2/assets/.
"""
import hashlib
import json
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from iot.book_catalog import BOOK_SLUG
from iot.models import AcademyBookLesson, BlocPedagogique, Lecon, Parcours, Quiz

SOURCE = Path(__file__).resolve().parents[2] / "academy_source" / "v2"
ASSETS = SOURCE / "assets"
MEDIA_DIR = "academy/livre1"
LETTERS = "ABCD"


def lesson_hash(entry):
    digest = hashlib.sha256(json.dumps(entry, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    for name in sorted(_asset_names(entry)):
        path = ASSETS / name
        if path.exists():
            digest.update(name.encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _asset_names(entry):
    names = []
    if entry.get("photo", {}).get("fichier"):
        names.append(entry["photo"]["fichier"])
    for bloc in entry.get("blocs", []):
        if bloc.get("fichier"):
            names.append(bloc["fichier"])
    return names


def validate(entry):
    """Erreurs bloquantes d'une leçon source (liste vide si tout va bien)."""
    errors = []
    lid = entry.get("id", "?")
    for key in ("id", "titre", "resume", "blocs", "quiz"):
        if not entry.get(key):
            errors.append(f"{lid} : champ « {key} » manquant")
    for name in _asset_names(entry):
        if not (ASSETS / name).exists():
            errors.append(f"{lid} : fichier introuvable {name}")
    for n, q in enumerate(entry.get("quiz", []), start=1):
        choix = q.get("choix", [])
        bonnes = q.get("bonnes", [])
        if not 2 <= len(choix) <= 4:
            errors.append(f"{lid} quiz {n} : 2 à 4 choix attendus")
        if not bonnes or any(b not in LETTERS[:len(choix)] for b in bonnes):
            errors.append(f"{lid} quiz {n} : bonne(s) réponse(s) invalide(s)")
        if any(len(c) > 255 for c in choix):
            errors.append(f"{lid} quiz {n} : un choix dépasse 255 caractères")
    return errors


def _caption(legende, credit):
    parts = [p for p in (legende, credit) if p]
    return "\n".join(parts)


def _save_asset(lesson_id, name):
    target = f"{MEDIA_DIR}/{lesson_id}/{name}"
    if default_storage.exists(target):
        default_storage.delete(target)
    return default_storage.save(target, ContentFile((ASSETS / name).read_bytes()))


class Command(BaseCommand):
    help = "Importer en brouillon les leçons enrichies du Livre 1 (sans rien publier)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Écrire en base (sinon simulation).")
        parser.add_argument("--chapter", help="Limiter à une partie, ex. 00, 07.")
        parser.add_argument("--force", action="store_true", help="Reconstruire même si la source n'a pas changé.")

    def handle(self, *args, **options):
        parcours = Parcours.objects.filter(slug=BOOK_SLUG).first()
        if parcours is None:
            raise CommandError("Parcours Livre 1 introuvable : exécutez prepare_academy_book.")

        pattern = f"chapter_{options['chapter'].zfill(2)}.json" if options.get("chapter") else "chapter_*.json"
        files = sorted(SOURCE.glob(pattern))
        if not files:
            raise CommandError(f"Aucune source trouvée dans {SOURCE} ({pattern}).")

        entries = []
        errors = []
        for path in files:
            for entry in json.loads(path.read_text(encoding="utf-8")):
                errors += validate(entry)
                entries.append(entry)
        if errors:
            raise CommandError("Source invalide :\n" + "\n".join(errors))

        counts = {"créées": 0, "mises à jour": 0, "inchangées": 0}
        for entry in entries:
            status = self._import_one(parcours, entry, options)
            counts[status] += 1

        summary = ", ".join(f"{n} {k}" for k, n in counts.items())
        if options["apply"]:
            self.stdout.write(self.style.SUCCESS(
                f"Leçons : {summary}. Rien n'a été publié : utilisez publish_academy_chapter quand une partie est relue."
            ))
        else:
            self.stdout.write(f"Simulation ({summary}). Relancez avec --apply pour importer.")

    def _import_one(self, parcours, entry, options):
        lid = entry["id"]
        major, minor = (int(x) for x in lid.split("."))
        chapter = str(major).zfill(2)
        title = f"{lid} — {entry['titre']}"[:200]
        digest = lesson_hash(entry)

        lecon = Lecon.objects.filter(parcours=parcours, titre__startswith=f"{lid} —").first()
        book_entry = getattr(lecon, "academy_book_entry", None) if lecon else None
        if lecon and book_entry and book_entry.content_hash == digest and not options["force"]:
            self.stdout.write(f"À jour : {title}")
            return "inchangées"

        status = "mises à jour" if lecon else "créées"
        self.stdout.write(f"{'Mise à jour' if lecon else 'Création'} : {title} "
                          f"({len(entry['blocs'])} blocs, {len(entry['quiz'])} quiz)")
        if not options["apply"]:
            return status

        with transaction.atomic():
            if lecon is None:
                lecon = Lecon.objects.create(parcours=parcours, titre=title, ordre=major * 100 + minor)
            lecon.titre = title
            lecon.resume = entry["resume"]
            lecon.duree_minutes = entry.get("duree_minutes", 30)
            lecon.ordre = major * 100 + minor
            lecon.save()

            if book_entry is None:
                book_entry, _ = AcademyBookLesson.objects.get_or_create(
                    lecon=lecon, defaults={"chapter_number": chapter, "published": False}
                )

            # Vidéo déjà envoyée par le formateur : on la garde.
            kept_video = (
                lecon.blocs.filter(type="video").exclude(media_file="").exclude(media_file__isnull=True)
                .values_list("media_file", flat=True).first()
            )
            lecon.blocs.all().delete()
            lecon.quizzes.all().delete()

            ordre = 0

            def add(**fields):
                nonlocal ordre
                ordre += 1
                return BlocPedagogique.objects.create(lecon=lecon, ordre=ordre, **fields)

            photo = entry.get("photo")
            if photo:
                add(type="image", language="photo",
                    media_file=_save_asset(lid, photo["fichier"]),
                    contenu=_caption(photo.get("legende"), photo.get("credit")))

            blocs = entry["blocs"]
            for index, bloc in enumerate(blocs):
                kind = bloc["type"]
                if kind == "texte":
                    add(type="texte", contenu=bloc["contenu"])
                elif kind in ("schema", "image"):
                    add(type="image", language="schema" if kind == "schema" else "photo",
                        media_file=_save_asset(lid, bloc["fichier"]),
                        contenu=_caption(bloc.get("legende"), bloc.get("credit")))
                elif kind == "code":
                    add(type="code", language=bloc.get("language", "cpp"), code=bloc["code"])
                else:
                    raise CommandError(f"{lid} : type de bloc inconnu « {kind} »")

                if index == 0:
                    if entry.get("materiel"):
                        add(type="texte", contenu="## 🧰 Matériel nécessaire\n\n"
                            + "\n".join(f"- {m}" for m in entry["materiel"]))
                    add(type="video", media_file=kept_video or None,
                        contenu=entry.get("video", ""))

            for q in entry["quiz"]:
                choix = q["choix"] + [None] * (4 - len(q["choix"]))
                Quiz.objects.create(
                    lecon=lecon, question=q["question"],
                    choix_a=choix[0], choix_b=choix[1], choix_c=choix[2], choix_d=choix[3],
                    bonne_reponse=",".join(q["bonnes"]),
                    plusieurs_reponses=len(q["bonnes"]) > 1,
                    explication=q.get("explication", ""),
                )

            book_entry.content_hash = digest
            book_entry.save(update_fields=["content_hash"])
        return status
