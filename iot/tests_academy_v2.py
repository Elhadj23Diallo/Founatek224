"""Leçons enrichies du Livre 1 : rendu Markdown, import v2, brouillons visibles par l'équipe."""
import json
import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.core.files.base import ContentFile

from . import academy_audio
from .academy_access import can_read_lesson
from .book_catalog import BOOK_SLUG
from .models import AcademyBookLesson, BlocPedagogique, Lecon, Parcours, Quiz
from .templatetags.lesson_extras import markdown_lite
from .management.commands import import_academy_book_v2

BOOK_V2_SOURCE = import_academy_book_v2.SOURCE

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
       b"\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


def lesson(**overrides):
    data = {
        "id": "0.9", "titre": "Leçon de test", "resume": "Résumé", "duree_minutes": 30,
        "photo": {"fichier": "photo.png", "legende": "Une photo", "credit": "Pixabay"},
        "materiel": ["1 × LED", "1 × résistance 220 Ω"],
        "video": "Plan de la vidéo",
        "blocs": [
            {"type": "texte", "contenu": "## 🎯 Objectifs\n\n- comprendre"},
            {"type": "schema", "fichier": "schema.svg", "legende": "Le schéma"},
            {"type": "code", "language": "cpp", "code": "void setup() {}"},
        ],
        "quiz": [
            {"question": "Q1 ?", "choix": ["a", "b", "c", "d"], "bonnes": ["B"], "explication": "car b"},
            {"question": "Q2 ?", "choix": ["a", "b", "c"], "bonnes": ["A", "C"], "explication": "a et c"},
        ],
    }
    data.update(overrides)
    return data


class MarkdownLiteTests(TestCase):
    def test_rich_blocks(self):
        html = markdown_lite(
            "## Titre\n\n- un\n- deux\n\n1. premier\n2. second\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n"
            "> 💡 astuce **forte**\n\n$$U = R \\times I$$\n\nTexte avec `code` et \\( I = U/R \\)."
        )
        self.assertIn('<h4 class="lesson-h">Titre</h4>', html)
        self.assertIn("<ul", html)
        self.assertIn("<ol", html)
        self.assertIn("<th>A</th>", html)
        self.assertIn("lesson-callout-tip", html)
        self.assertIn("<strong>forte</strong>", html)
        self.assertIn('<div class="academy-formula">$$U = R \\times I$$</div>', html)
        self.assertIn("<code>code</code>", html)
        self.assertIn("\\( I = U/R \\)", html)

    def test_html_is_escaped(self):
        html = markdown_lite("<script>alert(1)</script>\n\n## <b>x</b>")
        self.assertNotIn("<script>", html)
        self.assertNotIn("<b>", html)

    def test_plain_text_keeps_old_behaviour(self):
        self.assertEqual(markdown_lite("ligne 1\nligne 2\n\nparagraphe"), "<p>ligne 1<br>ligne 2</p><p>paragraphe</p>")


class ImportV2Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(username="equipe", password="p", is_staff=True)
        self.learner = User.objects.create_user(username="eleve", password="p")
        from .models import Organisation
        self.parcours = Parcours.objects.create(
            organisation=Organisation.objects.create(nom="FOUNATEK"), created_by=self.staff,
            titre="Livre 1", slug=BOOK_SLUG, description="Livre 1",
        )
        self.tmp = Path(tempfile.mkdtemp())
        self.media = tempfile.mkdtemp()
        (self.tmp / "assets").mkdir()
        (self.tmp / "assets" / "photo.png").write_bytes(PNG)
        (self.tmp / "assets" / "schema.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>')
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(shutil.rmtree, self.media, True)
        for p in (
            patch("iot.management.commands.import_academy_book_v2.SOURCE", self.tmp),
            patch("iot.management.commands.import_academy_book_v2.ASSETS", self.tmp / "assets"),
        ):
            p.start()
            self.addCleanup(p.stop)
        media = override_settings(MEDIA_ROOT=self.media)
        media.enable()
        self.addCleanup(media.disable)

    def write(self, *lessons):
        (self.tmp / "chapter_00.json").write_text(json.dumps(list(lessons), ensure_ascii=False), encoding="utf-8")

    def run_import(self, *args):
        out = StringIO()
        call_command("import_academy_book_v2", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_writes_nothing(self):
        self.write(lesson())
        self.assertIn("Simulation", self.run_import())
        self.assertFalse(Lecon.objects.exists())

    def test_import_builds_lesson_as_draft(self):
        self.write(lesson())
        self.run_import("--apply")
        lecon = Lecon.objects.get()
        self.assertEqual(lecon.titre, "0.9 — Leçon de test")
        self.assertEqual(lecon.ordre, 9)
        self.assertFalse(lecon.academy_book_entry.published)
        types = list(lecon.blocs.order_by("ordre").values_list("type", flat=True))
        self.assertEqual(types, ["image", "texte", "texte", "video", "image", "code"])
        self.assertIn("Matériel nécessaire", lecon.blocs.get(ordre=3).contenu)
        self.assertEqual(lecon.blocs.get(ordre=5).language, "schema")
        quizzes = list(Quiz.objects.filter(lecon=lecon).order_by("id"))
        self.assertEqual(len(quizzes), 2)
        self.assertEqual((quizzes[1].bonne_reponse, quizzes[1].plusieurs_reponses, quizzes[1].choix_d), ("A,C", True, None))

    def test_second_run_is_noop_and_changes_rebuild_keeping_video(self):
        self.write(lesson())
        self.run_import("--apply")
        self.assertIn("1 inchangées", self.run_import("--apply"))
        video = BlocPedagogique.objects.get(type="video")
        video.media_file = "videos/ma-video.mp4"
        video.save()
        self.write(lesson(resume="Nouveau résumé"))
        self.assertIn("1 mises à jour", self.run_import("--apply"))
        lecon = Lecon.objects.get()
        self.assertEqual(lecon.resume, "Nouveau résumé")
        self.assertEqual(lecon.blocs.get(type="video").media_file.name, "videos/ma-video.mp4")

    def test_existing_draft_with_same_number_is_updated_not_duplicated(self):
        old = Lecon.objects.create(parcours=self.parcours, titre="0.9 — Ancien titre", ordre=9)
        AcademyBookLesson.objects.create(lecon=old, chapter_number="00", published=True)
        self.write(lesson())
        self.run_import("--apply")
        self.assertEqual(Lecon.objects.count(), 1)
        old.refresh_from_db()
        self.assertEqual(old.titre, "0.9 — Leçon de test")
        self.assertTrue(old.academy_book_entry.published, "l'état publié n'est jamais modifié")

    def test_invalid_source_is_refused(self):
        self.write(lesson(quiz=[{"question": "?", "choix": ["a", "b"], "bonnes": ["D"]}]))
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            self.run_import("--apply")
        self.assertFalse(Lecon.objects.exists())

    def test_draft_visible_to_staff_only(self):
        self.write(lesson())
        self.run_import("--apply")
        lecon = Lecon.objects.get()
        self.assertTrue(can_read_lesson(self.staff, lecon))
        self.assertFalse(can_read_lesson(self.learner, lecon))
        self.client.force_login(self.staff)
        resp = self.client.get(f"/lecon/{lecon.id}/")
        self.assertContains(resp, "Brouillon")
        self.assertContains(resp, "Vidéo de la leçon : bientôt disponible")
        self.assertContains(resp, "academy-schematic")
        self.client.force_login(self.learner)
        resp = self.client.get(f"/lecon/{lecon.id}/")
        self.assertRedirects(resp, "/academy/livre-1/", fetch_redirect_response=False)

    def test_lesson_0_1_renders_theory_and_wokwi_at_their_positions(self):
        chapter = json.loads((BOOK_V2_SOURCE / "chapter_00.json").read_text(encoding="utf-8"))
        source_lesson = next(entry for entry in chapter if entry["id"] == "0.1")
        blocs = source_lesson["blocs"]
        reserved = next(i for i, bloc in enumerate(blocs) if bloc.get("emplacement") == "tension-courant")
        self.assertIn("Les quatre grandeurs à connaître", blocs[reserved - 1]["contenu"])
        self.assertIn("La loi d'Ohm", blocs[reserved + 1]["contenu"])
        self.assertEqual(blocs[reserved]["fichier"], "lecon_0_1/video_01.mp4")
        with (
            patch.object(import_academy_book_v2, "SOURCE", BOOK_V2_SOURCE),
            patch.object(import_academy_book_v2, "ASSETS", BOOK_V2_SOURCE / "assets"),
            patch.object(academy_audio, "find_ffmpeg", return_value=None),
        ):
            self.run_import("--lesson", "0.1", "--apply")
            self.assertIn("1 inchangées", self.run_import("--lesson", "0.1", "--apply"))

        lecon = Lecon.objects.get()
        self.assertEqual(lecon.quizzes.count(), len(source_lesson["quiz"]))
        theory, practice = lecon.blocs.filter(type="video").order_by("ordre")
        for video, filename in ((theory, "video_01.mp4"), (practice, "video_02.mp4")):
            source = import_academy_book_v2.COURSE_MEDIA / "lecon_0_1" / filename
            self.assertTrue(video.media_file.name.endswith(f"/{filename}"))
            self.assertEqual(video.media_file.size, source.stat().st_size)
        self.client.force_login(self.staff)
        response = self.client.get(f"/lecon/{lecon.id}/")
        self.assertContains(response, "<video controls", count=2)
        self.assertNotContains(response, "Vidéo de la leçon : bientôt disponible")
        html = response.content.decode()
        markers = (
            "Les quatre grandeurs à connaître",
            f'<source src="{theory.media_file.url}">',
            "La loi d",
            "Exemple résolu",
            "Le montage pas à pas",
            "BROCHE_LED",
            f'<source src="{practice.media_file.url}">',
            "Mesurer pour vérifier",
        )
        positions = [html.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))

    def test_reserved_video_only_appears_after_adding_its_file(self):
        slot = {"type": "video", "emplacement": "tension-courant", "legende": "Vidéo théorique"}
        entry = lesson(blocs=[
            {"type": "texte", "contenu": "## Notions de tension et de courant"},
            slot,
            {"type": "texte", "contenu": "## Application de la formule"},
        ])
        self.write(entry)
        self.run_import("--apply")
        url = f"/lecon/{Lecon.objects.get().pk}/"
        self.client.force_login(self.staff)
        response = self.client.get(url)
        self.assertNotContains(response, "<video")
        self.assertNotContains(response, "Vidéo de la leçon : bientôt disponible")

        slot["fichier"] = "theorie.mp4"
        (self.tmp / slot["fichier"]).write_bytes(b"synthetic test clip")
        self.write(entry)
        with patch.object(import_academy_book_v2, "COURSE_MEDIA", self.tmp):
            self.run_import("--apply")
        response = self.client.get(url)
        self.assertContains(response, "<video controls", count=1)
        html = response.content.decode()
        self.assertLess(html.index("Notions de tension et de courant"), html.index("/theorie.mp4"))
        self.assertLess(html.index("/theorie.mp4"), html.index("Application de la formule"))

    def test_audio_import_reuses_cache_and_updates_modified_video_from_original(self):
        self.write(lesson(blocs=[{"type": "video", "fichier": "lesson.mp4"}]))
        source = self.tmp / "lesson.mp4"
        source.write_bytes(b"original one")
        with (
            patch.object(import_academy_book_v2, "COURSE_MEDIA", self.tmp),
            patch.object(academy_audio, "find_ffmpeg", return_value="ffmpeg"),
            patch.object(academy_audio, "normalize_file",
                         side_effect=lambda src, dest, _: dest.write_bytes(src.read_bytes() + b" normalized")) as convert,
        ):
            self.assertIn("Simulation", self.run_import())
            self.assertFalse(Lecon.objects.exists())
            self.assertEqual(list(Path(self.media).iterdir()), [])
            convert.assert_not_called()
            self.run_import("--apply")
            lecon = Lecon.objects.get()
            first = lecon.blocs.get(type="video").media_file
            self.assertTrue(first.name.startswith(f"{academy_audio.MEDIA_PREFIX}/"))
            self.assertIn("1 inchangées", self.run_import("--apply"))
            self.assertEqual(convert.call_count, 1)
            source.write_bytes(b"original two")
            self.run_import("--apply")
            self.assertEqual(convert.call_count, 2)
            self.assertNotEqual(lecon.blocs.get(type="video").media_file.name, first.name)
            self.assertTrue(first.storage.exists(first.name))
            self.assertEqual(source.read_bytes(), b"original two")

    def test_manual_audio_upgrade_after_fallback_preserves_blocks_quizzes_and_urls(self):
        self.write(lesson(blocs=[{"type": "video", "fichier": "lesson.mp4"}]))
        source = self.tmp / "lesson.mp4"
        source.write_bytes(b"original")
        with patch.object(import_academy_book_v2, "COURSE_MEDIA", self.tmp):
            with patch.object(academy_audio, "find_ffmpeg", return_value=None):
                self.run_import("--apply")
            lecon = Lecon.objects.get()
            block = lecon.blocs.get(type="video")
            original = block.media_file
            quiz_ids = list(lecon.quizzes.values_list("pk", flat=True))
            with (
                patch.object(academy_audio, "find_ffmpeg", return_value="ffmpeg"),
                patch.object(academy_audio, "normalize_file",
                             side_effect=lambda src, dest, _: dest.write_bytes(b"optimized")) as convert,
            ):
                call_command("normalize_academy_audio", "--lesson", "0.9", stdout=StringIO())
                convert.assert_not_called()
                call_command("normalize_academy_audio", "--lesson", "0.9", "--apply", stdout=StringIO())
            block.refresh_from_db()
            self.assertTrue(block.media_file.name.startswith(f"{academy_audio.MEDIA_PREFIX}/"))
            self.assertEqual(list(lecon.quizzes.values_list("pk", flat=True)), quiz_ids)
            with original.open() as old:
                self.assertEqual(old.read(), b"original")

    def test_audio_export_simulation_does_not_create_a_cache(self):
        self.write(lesson(blocs=[{"type": "video", "fichier": "lesson.mp4"}]))
        (self.tmp / "lesson.mp4").write_bytes(b"original")
        directory = self.tmp / "portable"
        with (
            patch.object(import_academy_book_v2, "COURSE_MEDIA", self.tmp),
            patch.object(academy_audio, "find_ffmpeg") as find,
        ):
            call_command("normalize_academy_audio", "--lesson", "0.9", "--export-cache", str(directory),
                         stdout=StringIO())
            find.assert_not_called()
        self.assertFalse(directory.exists())
        self.assertFalse(Lecon.objects.exists())

    def test_uploaded_video_processing_is_scoped_and_preserves_original_on_failure(self):
        self.write(lesson(), lesson(id="0.10", titre="Autre leçon"))
        self.run_import("--apply")
        block, other = BlocPedagogique.objects.filter(type="video").order_by("lecon__ordre")
        block.media_file.save("from-form.mp4", ContentFile(b"uploaded original"))
        other.media_file.save("other.mp4", ContentFile(b"other original"))
        original = block.media_file
        with (
            patch.object(academy_audio, "find_ffmpeg", return_value="ffmpeg"),
            patch.object(academy_audio, "normalize_file", side_effect=academy_audio.AudioNormalizationError("fixture")),
        ):
            call_command("normalize_academy_audio", "--uploaded-lesson-id", str(block.lecon_id), "--apply",
                         stdout=StringIO(), stderr=StringIO())
        block.refresh_from_db()
        self.assertEqual(block.media_file.name, original.name)
        with (
            patch.object(academy_audio, "find_ffmpeg", return_value="ffmpeg"),
            patch.object(academy_audio, "normalize_file", side_effect=lambda src, dest, _: dest.write_bytes(b"optimized")) as convert,
        ):
            for _ in range(2):
                call_command("normalize_academy_audio", "--uploaded-lesson-id", str(block.lecon_id), "--apply", stdout=StringIO())
            convert.assert_called_once()
        block.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(block.media_file.name.startswith(f"{academy_audio.MEDIA_PREFIX}/"))
        self.assertTrue(other.media_file.name.endswith("/other.mp4"))
        with original.open() as old:
            self.assertEqual(old.read(), b"uploaded original")


class AdminFullAccessTests(TestCase):
    """L'administrateur (createsuperuser) lit tout ; les autres comptes restent limités."""
    write = ImportV2Tests.write
    run_import = ImportV2Tests.run_import

    def setUp(self):
        ImportV2Tests.setUp(self)
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="admin", password="p", email="a@example.com")
        self.write(lesson(id="0.9"), lesson(id="0.10", titre="Deuxième leçon"))
        self.run_import("--apply")
        # Une partie payante publiée (07), sans achat
        self.paid = Lecon.objects.get(titre__contains="Deuxième leçon")
        AcademyBookLesson.objects.filter(lecon=self.paid).update(published=True, chapter_number="07")

    def test_admin_reads_paid_and_draft_lessons(self):
        from .academy_access import can_read_book_chapter, filter_readable_lessons
        draft = Lecon.objects.exclude(pk=self.paid.pk).get()
        for lecon in (draft, self.paid):
            self.assertTrue(can_read_lesson(self.admin, lecon))
        self.assertTrue(can_read_book_chapter(self.admin, "07"))
        self.assertEqual(filter_readable_lessons(Lecon.objects.all(), self.admin).count(), Lecon.objects.count())
        self.client.force_login(self.admin)
        for lecon in (draft, self.paid):
            self.assertEqual(self.client.get(f"/lecon/{lecon.id}/").status_code, 200)

    def test_learner_still_needs_the_pack(self):
        from .academy_access import can_read_book_chapter
        self.assertFalse(can_read_lesson(self.learner, self.paid))
        self.assertFalse(can_read_book_chapter(self.learner, "07"))
        self.client.force_login(self.learner)
        resp = self.client.get(f"/lecon/{self.paid.id}/")
        self.assertRedirects(resp, "/academy/livre-1/", fetch_redirect_response=False)

    def test_admin_sees_unpublished_parcours_and_book_link(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/parcours/"), "Non publié")
        liste = self.client.get(f"/parcours/{self.parcours.id}/")
        import re
        html = liste.content.decode()
        self.assertRegex(html, r'lesson-marker">\s*0\.10\s*<')
        self.assertIsNone(re.search(r'lesson-marker">\s*10\s*<', html))
        resp = self.client.get("/academy/livre-1/")
        self.assertContains(resp, "Vue administrateur")
        self.assertContains(resp, "1 leçon enrichie, pas encore publiée")
        self.assertContains(resp, "publish_academy_chapter --chapter 00 --apply")
        self.assertContains(resp, f"/parcours/{self.parcours.id}/")
        self.client.force_login(self.learner)
        self.assertNotContains(self.client.get("/academy/livre-1/"), "Vue administrateur")

    def test_staff_without_superuser_does_not_see_admin_panel(self):
        """Le panneau admin (brouillons, commande de publication) est réservé
        au superutilisateur (createsuperuser) : un compte is_staff seul n'y a pas droit."""
        self.client.force_login(self.staff)
        resp = self.client.get("/academy/livre-1/")
        self.assertNotContains(resp, "Vue administrateur")
        self.assertNotContains(resp, "leçon enrichie, pas encore publiée")
        self.assertNotContains(resp, "publish_academy_chapter")


class RawCanvaDraftTests(TestCase):
    """Les fiches brutes de l'ancien import Canva restent masquées, même pour l'admin."""
    write = ImportV2Tests.write
    run_import = ImportV2Tests.run_import

    def setUp(self):
        ImportV2Tests.setUp(self)
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="admin", password="p", email="a@example.com")
        self.raw = Lecon.objects.create(parcours=self.parcours, titre="7.1 — Version brute", ordre=701)
        AcademyBookLesson.objects.create(lecon=self.raw, chapter_number="07", published=False)
        self.write(lesson())
        self.run_import("--apply")

    def test_raw_draft_hidden_from_admin_list_and_page(self):
        self.client.force_login(self.admin)
        liste = self.client.get(f"/parcours/{self.parcours.id}/")
        self.assertNotContains(liste, "Version brute")
        self.assertContains(liste, "fiche brute du livre Canva masquée (partie 07)")
        self.assertContains(liste, "Leçon de test")
        resp = self.client.get(f"/lecon/{self.raw.id}/")
        self.assertRedirects(resp, f"/parcours/{self.parcours.id}/", fetch_redirect_response=False)

    def test_reimport_v2_makes_it_visible(self):
        self.write(lesson(id="7.1", titre="Les DHT11 et DHT22"))
        self.run_import("--apply")
        self.raw.refresh_from_db()
        self.assertTrue(self.raw.titre.startswith("7.1 — Les DHT11"))
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(f"/lecon/{self.raw.id}/").status_code, 200)
