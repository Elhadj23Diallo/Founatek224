from io import StringIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from iot.models import BlocPedagogique, Lecon, Parcours, Progression, Project, Quiz


class SeedESP32WokwiCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="elhadj",
            password="test-password",
        )

    def run_seed(self):
        call_command("seed_esp32_wokwi", stdout=StringIO())

    def test_seed_is_idempotent_and_preserves_progress_and_publish_state(self):
        self.run_seed()
        parcours = Parcours.objects.get(slug="atelier-esp32-gpio-adc-pwm-wokwi")
        self.assertTrue(parcours.is_published)

        lecon = Lecon.objects.get(parcours=parcours, ordre=3)
        Progression.objects.create(
            user=self.user,
            lecon=lecon,
            completed=True,
            score=100,
        )
        counts = {
            "lecons": Lecon.objects.filter(parcours=parcours).count(),
            "blocs": BlocPedagogique.objects.filter(lecon__parcours=parcours).count(),
            "quiz": Quiz.objects.filter(lecon__parcours=parcours).count(),
            "projects": Project.objects.filter(parcours=parcours).count(),
        }
        self.assertEqual(counts, {"lecons": 6, "blocs": 17, "quiz": 12, "projects": 1})
        self.assertEqual(parcours.created_by_id, self.user.id)
        self.assertEqual(parcours.organisation.nom, "Founatek Academy")

        parcours.is_published = False
        parcours.save(update_fields=["is_published"])
        lecon.titre = "Titre temporaire à remplacer par le seed"
        lecon.save(update_fields=["titre"])

        self.run_seed()

        parcours.refresh_from_db()
        lecon.refresh_from_db()
        self.assertFalse(parcours.is_published)
        self.assertEqual(
            lecon.titre,
            "Entrée numérique : lire un bouton et éviter les faux appuis",
        )
        self.assertTrue(
            Progression.objects.filter(
                user=self.user,
                lecon=lecon,
                completed=True,
                score=100,
            ).exists()
        )
        self.assertEqual(Lecon.objects.filter(parcours=parcours).count(), counts["lecons"])
        self.assertEqual(
            BlocPedagogique.objects.filter(lecon__parcours=parcours).count(),
            counts["blocs"],
        )
        self.assertEqual(Quiz.objects.filter(lecon__parcours=parcours).count(), counts["quiz"])
        self.assertEqual(Project.objects.filter(parcours=parcours).count(), counts["projects"])

    def test_course_visuals_reference_existing_local_assets_and_credits(self):
        self.run_seed()
        parcours = Parcours.objects.get(slug="atelier-esp32-gpio-adc-pwm-wokwi")
        markup = "\n".join(
            value or ""
            for value in BlocPedagogique.objects.filter(lecon__parcours=parcours).values_list(
                "code", flat=True
            )
        )
        for filename in (
            "esp32-devkit-cc0.jpg",
            "breadboard.jpg",
            "red-led.jpg",
            "resistors.jpg",
            "tactile-switches.jpg",
            "potentiometer.jpg",
            "schema-esp32-bouton-led.png",
            "schema-esp32-potentiometre-pwm.png",
        ):
            self.assertIn(filename, markup)
            asset = Path(__file__).resolve().parent / "static" / "iot" / "course_images" / filename
            self.assertTrue(asset.is_file(), filename)
        self.assertEqual(markup.count('class="course-zoom-trigger"'), 14)
        self.assertIn('aria-label="Agrandir le visuel :', markup)
        self.assertNotIn('loading="lazy"', markup)
        self.assertIn("CC BY-SA 3.0", markup)
        self.assertIn("commons.wikimedia.org", markup)
        self.assertNotIn("<iframe", markup.lower())

    def test_missing_formateur_fails_without_creating_course(self):
        with self.assertRaises(CommandError):
            call_command(
                "seed_esp32_wokwi",
                username="compte-inexistant",
                stdout=StringIO(),
            )
        self.assertFalse(
            Parcours.objects.filter(slug="atelier-esp32-gpio-adc-pwm-wokwi").exists()
        )
