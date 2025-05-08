from django.db import models

# Create your models here.
class Chapitre(models.Model):
    titre = models.CharField(max_length=200)
    contenu = models.TextField()
    ordre = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='chapitres/', blank=True, null=True)
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ordre']

    def __str__(self):
        return self.titre
    
class Projects(models.Model):
    titre = models.CharField(max_length=200)
    contenu = models.TextField()
    ordre = models.PositiveIntegerField(default=0)
    video = models.FileField(upload_to='tutos/', blank=True, null=True)
    image = models.ImageField(upload_to='chapitres/', blank=True, null=True)
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ordre']

    def __str__(self):
        return self.titre