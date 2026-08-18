from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
import uuid
import qrcode
from io import BytesIO
from django.core.files import File
from reportlab.lib.utils import ImageReader



class Organisation(models.Model):
    nom = models.CharField(max_length=200)
    type = models.CharField(
        choices=[('Université', 'Université'), ('Entreprise', 'Entreprise')],
        max_length=20
    )

    logo = models.ImageField(
        upload_to="organisations/logos/",
        blank=True,
        null=True
    )

    couleur_principale = models.CharField(
        max_length=7,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)  # ✅ AJOUT ICI

    def __str__(self):
        return f"{self.nom} ({self.type})"





class FormateurProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="formateur_profile"
    )
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.PROTECT,
        related_name="formateurs"
    )
    photo = models.ImageField(
        upload_to="formateurs/photos/",
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.organisation.nom}"


class FormateurFollow(models.Model):
    """Abonnement d'un apprenant a un formateur, pour etre notifie de ses publications."""
    follower = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="formateurs_suivis"
    )
    formateur = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="abonnes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("follower", "formateur")

    def __str__(self):
        return f"{self.follower.username} suit {self.formateur.username}"



class Parcours(models.Model):
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.PROTECT,
        related_name="parcours"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="parcours_crees"
    )

    titre = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField()

    niveau = models.CharField(
        choices=[
            ('Débutant', 'Débutant'),
            ('Intermédiaire', 'Intermédiaire'),
            ('Avancé', 'Avancé'),
        ],
        max_length=20
    )

    prix = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    certifiant = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)

    materiel_requis = models.TextField(
        blank=True, null=True,
        help_text="Liste du matériel nécessaire pour suivre ce parcours en pratique (une ligne par élément)."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def duree_totale_minutes(self):
        return sum((l.duree_minutes or 0) for l in self.lecons.all())

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.titre)
            slug = base_slug
            counter = 1
            while Parcours.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.titre




class Lecon(models.Model):
    parcours = models.ForeignKey(
        Parcours,
        on_delete=models.CASCADE,
        related_name="lecons"
    )

    titre = models.CharField(max_length=200)
    ordre = models.PositiveIntegerField(default=0)
    resume = models.TextField(blank=True, null=True)
    duree_minutes = models.PositiveIntegerField(
        default=15, blank=True, null=True,
        help_text="Temps estimé pour suivre cette leçon (théorie + pratique), en minutes."
    )

    class Meta:
        ordering = ["ordre"]

    def __str__(self):
        return f"{self.parcours.titre} - {self.titre}"



class BlocPedagogique(models.Model):
    lecon = models.ForeignKey(
        Lecon,
        on_delete=models.CASCADE,
        related_name="blocs"
    )

    ordre = models.PositiveIntegerField(default=0)

    type = models.CharField(choices=[
        ('texte', 'Texte'),
        ('image', 'Image'),
        ('video', 'Vidéo'),
        ('code', 'Code'),
    ], max_length=20)

    contenu = models.TextField(blank=True, null=True)
    media_file = models.FileField(upload_to="blocs/", blank=True, null=True)
    language = models.CharField(max_length=30, blank=True, null=True)
    code = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["ordre"]

    def __str__(self):
        return f"{self.lecon.titre} - {self.type}"



class Quiz(models.Model):
    lecon = models.ForeignKey(
        Lecon,
        on_delete=models.CASCADE,
        related_name="quizzes"
    )

    question = models.TextField()
    choix_a = models.CharField(max_length=255)
    choix_b = models.CharField(max_length=255)
    choix_c = models.CharField(max_length=255, blank=True, null=True)
    choix_d = models.CharField(max_length=255, blank=True, null=True)

    # Une ou plusieurs lettres separees par des virgules, ex: "A" ou "A,C"
    bonne_reponse = models.CharField(max_length=10, default="A")

    plusieurs_reponses = models.BooleanField(
        default=False,
        help_text="Coche si cette question accepte plusieurs bonnes réponses (cases à cocher au lieu de bouton radio)."
    )

    explication = models.TextField(blank=True, null=True)

    def bonnes_reponses_set(self):
        return {r.strip().upper() for r in self.bonne_reponse.split(",") if r.strip()}

    def __str__(self):
        return f"Quiz - {self.lecon.titre}"



class Progression(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    lecon = models.ForeignKey(Lecon, on_delete=models.CASCADE)

    completed = models.BooleanField(default=False)
    score = models.FloatField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'lecon')

    def __str__(self):
        return f"{self.user.username} - {self.lecon.titre} ({self.score})"


class Project(models.Model):
    parcours = models.ForeignKey(
        Parcours,
        on_delete=models.CASCADE,
        related_name="projects"
    )

    titre = models.CharField(max_length=200)
    description = models.TextField()
    ordre = models.PositiveIntegerField(default=0)

    video = models.FileField(upload_to="projects/videos/", blank=True, null=True)
    image = models.ImageField(upload_to="projects/images/", blank=True, null=True)
    language = models.CharField(max_length=30, blank=True, null=True)
    code = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ordre"]

    def __str__(self):
        return self.titre




class Certification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    parcours = models.ForeignKey(Parcours, on_delete=models.CASCADE)

    score_final = models.FloatField()

    pdf = models.FileField(
        upload_to="certificats/",
        blank=True,
        null=True
    )

    pdf_generated_at = models.DateTimeField(   # ✅ SEULE LIGNE AJOUTÉE
        blank=True,
        null=True
    )

    qr_code = models.ImageField(
        upload_to="certificats/qrcodes/",
        blank=True,
        null=True
    )

    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    is_valid = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "parcours"],
                name="unique_certification_per_user_parcours"
            )
        ]

    def save(self, *args, **kwargs):
        if not self.qr_code:
            qr = qrcode.make(
                f"https://founatek224.pythonanywhere.com/certificat/{self.uuid}/"
            )
            buffer = BytesIO()
            qr.save(buffer, format="PNG")
            self.qr_code.save(
                f"qr_{self.uuid}.png",
                File(buffer),
                save=False
            )

        super().save(*args, **kwargs)




