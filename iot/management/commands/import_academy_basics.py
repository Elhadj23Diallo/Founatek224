"""Importer deux fiches du chapitre 00 en brouillon, sans toucher aux cours existants.

Source : Canva, Lot 00 - Les bases, pages 1 à 4.
Usage : python manage.py import_academy_basics --apply
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from iot.book_catalog import BOOK_SLUG
from iot.models import Parcours, Lecon, BlocPedagogique, Quiz, AcademyBookLesson


FICHES = (
    {
        "title": "0.1 — Tension, courant et loi d'Ohm",
        "summary": "Comprendre U, I, R et P, puis mesurer la tension d'un pont diviseur.",
        "blocks": (
            ("texte", """La tension U s'exprime en volts (V), le courant I en ampères (A) et la résistance R en ohms (Ω). Une résistance limite le courant dans un circuit fermé.

Formules : U = R × I ; I = U / R ; P = U × I.

Exemple du livre : sous 5 V avec une résistance de 1 kΩ, I = 5 / 1000 = 0,005 A, soit 5 mA.

Pour une LED rouge d'environ 2 V alimentée sous 5 V et traversée par 15 mA : R = (5 − 2) / 0,015 = 200 Ω. On peut choisir 220 Ω, une valeur normalisée supérieure.

Attention : la tension se mesure en parallèle et le courant en série. Ne jamais expérimenter directement sur le secteur.""" ),
            ("texte", """Expérience du livre : pont diviseur alimenté en 5 V, R1 = 2,2 kΩ et R2 = 1 kΩ. La broche A0 d'une Arduino Uno mesure la tension aux bornes de R2.

I = 5 / (2200 + 1000) = 1,5625 mA.
U2 = 1000 × 0,0015625 = 1,5625 V.
U1 = 3,4375 V ; U1 + U2 = 5 V.

Mini-défi : remplacez R2 par 2,2 kΩ et recalculez U2 et I avant de vérifier avec le montage. Sur ESP32, les entrées sont en 3,3 V : ne jamais y appliquer directement 5 V.""" ),
            ("code", """const float R2 = 1000.0;
void setup() { Serial.begin(9600); }
void loop() {
  int brut = analogRead(A0);
  float u = brut * 5.0 / 1023.0;
  float i = u / R2 * 1000.0;
  Serial.print("U = "); Serial.print(u, 2);
  Serial.print(" V   I = "); Serial.print(i, 2);
  Serial.println(" mA");
  delay(1000);
}"""),
        ),
        "quiz": ("Quelle est l'intensité traversant une résistance de 1 kΩ sous 5 V ?", "5 mA", "5 A", "500 mA", "0,5 A", "A", "I = U / R = 5 / 1000 A = 5 mA."),
    },
    {
        "title": "0.2 — Courant continu et alternatif",
        "summary": "Distinguer DC, AC, fréquence, valeur efficace et PWM.",
        "blocks": (
            ("texte", """Le courant continu (DC) est fourni notamment par les piles, les batteries et les sorties USB. Le secteur fournit une tension alternative (AC).

Pour une sinusoïde : f = 1 / T. À 50 Hz, la période vaut 20 ms. Pour une tension secteur de 230 V efficaces, la valeur crête est d'environ 325 V : Umax = √2 × Ueff.

Un adaptateur marqué « Input 100–240 V ~ 50/60 Hz ; Output 5 V DC 2 A » accepte une entrée secteur alternative et fournit une sortie continue 5 V, jusqu'à 2 A.

Sécurité : ne jamais manipuler directement le secteur pour cette activité.""" ),
            ("texte", """Expérience du livre : produire un signal PWM avec la broche D9 d'une Arduino Uno et le lisser à l'aide d'un filtre RC (10 kΩ, 10 µF). A0 mesure la tension moyenne.

Umoy ≈ rapport cyclique × 5 V.
analogWrite(9, 64) → environ 1,25 V.
analogWrite(9, 128) → environ 2,5 V.
analogWrite(9, 255) → 5 V.

Le PWM n'est pas une tension analogique continue : c'est un signal commuté. Mini-défi : trouvez la valeur de analogWrite donnant environ 3,3 V de moyenne.""" ),
            ("code", """const int PWM = 9;
void setup() { Serial.begin(9600); }
void loop() {
  for (int r = 0; r <= 255; r += 64) {
    analogWrite(PWM, r);
    delay(1000);
    float u = analogRead(A0) * 5.0 / 1023.0;
    Serial.print(r); Serial.print(" -> ");
    Serial.print(u, 2); Serial.println(" V");
  }
}"""),
        ),
        "quiz": ("Quelle est la période d'un signal alternatif de fréquence 50 Hz ?", "50 ms", "20 ms", "2 ms", "100 ms", "B", "T = 1 / 50 s = 0,02 s = 20 ms."),
    },
)


class Command(BaseCommand):
    help = "Préparer les fiches 0.1 et 0.2 en brouillon ; aucune publication automatique."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Créer les fiches absentes")

    def handle(self, *args, **options):
        parcours = Parcours.objects.filter(slug=BOOK_SLUG).first()
        if parcours is None:
            raise CommandError("Parcours Livre 1 introuvable. Exécutez prepare_academy_book d'abord.")
        if parcours.is_published:
            raise CommandError("Le parcours est publié : import interrompu pour éviter un changement visible.")
        for i, fiche in enumerate(FICHES, start=1):
            if Lecon.objects.filter(parcours=parcours, titre=fiche["title"]).exists():
                self.stdout.write(f"Déjà présente, ignorée : {fiche['title']}")
                continue
            self.stdout.write(f"À préparer : {fiche['title']}")
            if not options["apply"]:
                continue
            with transaction.atomic():
                lecon = Lecon.objects.create(
                    parcours=parcours, titre=fiche["title"],
                    ordre=i, resume=fiche["summary"], duree_minutes=20
                )
                AcademyBookLesson.objects.create(lecon=lecon, chapter_number="00", published=False)
                for ordre, (kind, text) in enumerate(fiche["blocks"], start=1):
                    if kind == "code":
                        BlocPedagogique.objects.create(
                            lecon=lecon, ordre=ordre, type="code", code=text, language="cpp"
                        )
                    else:
                        BlocPedagogique.objects.create(
                            lecon=lecon, ordre=ordre, type="texte", contenu=text
                        )
                q, a, b, c, d, answer, explanation = fiche["quiz"]
                Quiz.objects.create(
                    lecon=lecon, question=q, choix_a=a, choix_b=b,
                    choix_c=c, choix_d=d, bonne_reponse=answer, explication=explanation
                )
                self.stdout.write(self.style.SUCCESS(f"Brouillon créé : {fiche['title']}"))
        if not options["apply"]:
            self.stdout.write("Simulation terminée. Relancez avec --apply pour créer les brouillons.")
