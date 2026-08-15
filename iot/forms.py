from django import forms
from .models import (
    Parcours, Lecon, BlocPedagogique,
    Quiz, Project, Certification, Organisation, FormateurProfile
)


from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm



class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
        }


class FormateurProfileForm(forms.ModelForm):
    class Meta:
        model = FormateurProfile
        fields = ["photo"]



class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(label="Prénom", max_length=30)
    last_name = forms.CharField(label="Nom", max_length=30)

    # Inscription publique => Abonné seulement
    role = forms.ChoiceField(
        choices=[
            ('Abonné', 'Abonné'),
        ],
        required=True
    )

    referral_code = forms.CharField(
        label="Code de parrainage (facultatif)",
        max_length=36,
        required=False
    )

    class Meta:
        model = User
        fields = (
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'password1',
            'password2',
            'referral_code',
        )




class OrganisationForm(forms.ModelForm):
    class Meta:
        model = Organisation
        fields = ["nom", "type"]
        widgets = {
            "nom": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Nom de l’organisation"
            }),
            "type": forms.Select(attrs={
                "class": "form-select"
            }),
        }


class ParcoursForm(forms.ModelForm):
    class Meta:
        model = Parcours
        fields = [
            "titre",
            "description",
            "niveau",
            "prix",
            "certifiant",
            "is_published",
        ]
        widgets = {
            "titre": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Titre du parcours"
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Description pédagogique"
            }),
            "niveau": forms.Select(attrs={
                "class": "form-select"
            }),
            "prix": forms.NumberInput(attrs={
                "class": "form-control"
            }),
            "certifiant": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),
            "is_published": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),
        }



class LeconForm(forms.ModelForm):
    class Meta:
        model = Lecon
        fields = [
            "parcours",
            "titre",
            "resume",
            "ordre",
        ]
        widgets = {
            "parcours": forms.Select(attrs={
                "class": "form-select"
            }),
            "titre": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Titre de la leçon"
            }),
            "resume": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Résumé / objectif pédagogique"
            }),
            "ordre": forms.NumberInput(attrs={
                "class": "form-control"
            }),
        }



class BlocPedagogiqueForm(forms.ModelForm):
    class Meta:
        model = BlocPedagogique
        fields = [
            "lecon",
            "ordre",
            "type",
            "contenu",
            "media_file",
            "language",
            "code",
        ]
        widgets = {
            "lecon": forms.Select(attrs={
                "class": "form-select"
            }),
            "ordre": forms.NumberInput(attrs={
                "class": "form-control"
            }),
            "type": forms.Select(attrs={
                "class": "form-select"
            }),
            "contenu": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Contenu texte / Markdown"
            }),
            "media_file": forms.ClearableFileInput(attrs={
                "class": "form-control"
            }),
            "language": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "arduino / python / json"
            }),
            "code": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 6,
                "placeholder": "Code pédagogique"
            }),
        }



class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = [
            "lecon",
            "question",
            "choix_a",
            "choix_b",
            "choix_c",
            "choix_d",
            "bonne_reponse",
            "explication",
        ]
        widgets = {
            "lecon": forms.Select(attrs={
                "class": "form-select"
            }),
            "question": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3
            }),
            "choix_a": forms.TextInput(attrs={"class": "form-control"}),
            "choix_b": forms.TextInput(attrs={"class": "form-control"}),
            "choix_c": forms.TextInput(attrs={"class": "form-control"}),
            "choix_d": forms.TextInput(attrs={"class": "form-control"}),
            "bonne_reponse": forms.Select(attrs={
                "class": "form-select"
            }),
            "explication": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Explication pédagogique"
            }),
        }




class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            "parcours",
            "titre",
            "description",
            "ordre",
            "video",
            "image",
            "language",
            "code",
        ]
        widgets = {
            "parcours": forms.Select(attrs={
                "class": "form-select"
            }),
            "titre": forms.TextInput(attrs={
                "class": "form-control"
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4
            }),
            "ordre": forms.NumberInput(attrs={
                "class": "form-control"
            }),
            "video": forms.ClearableFileInput(attrs={
                "class": "form-control"
            }),
            "image": forms.ClearableFileInput(attrs={
                "class": "form-control"
            }),
            "language": forms.TextInput(attrs={
                "class": "form-control"
            }),
            "code": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 6
            }),
        }



class CertificationForm(forms.ModelForm):
    class Meta:
        model = Certification
        fields = [
            "user",
            "parcours",
            "score_final",
            "is_valid",
        ]
        widgets = {
            "user": forms.Select(attrs={"class": "form-select"}),
            "parcours": forms.Select(attrs={"class": "form-select"}),
            "score_final": forms.NumberInput(attrs={"class": "form-control"}),
            "is_valid": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }




