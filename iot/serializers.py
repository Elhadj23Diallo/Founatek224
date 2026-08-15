from rest_framework import serializers
from .models import (
    Organisation, Parcours, Lecon,
    BlocPedagogique, Quiz,
    Progression, Project
)


class BlocPedagogiqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlocPedagogique
        fields = [
            'id',
            'ordre',
            'type',
            'contenu',
            'media_file',
            'language',
            'code',
        ]


class QuizSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quiz
        fields = [
            'id',
            'question',
            'choix_a',
            'choix_b',
            'choix_c',
            'choix_d',
            'bonne_reponse',
            'explication',
        ]



class LeconSerializer(serializers.ModelSerializer):
    blocs = BlocPedagogiqueSerializer(many=True, read_only=True)
    quizzes = QuizSerializer(many=True, read_only=True)

    class Meta:
        model = Lecon
        fields = [
            'id',
            'titre',
            'resume',
            'ordre',
            'blocs',
            'quizzes',
        ]


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            'id',
            'titre',
            'description',
            'ordre',
            'video',
            'image',
            'language',
            'code',
        ]


class ParcoursSerializer(serializers.ModelSerializer):
    lecons = LeconSerializer(many=True, read_only=True)
    projects = ProjectSerializer(many=True, read_only=True)

    class Meta:
        model = Parcours
        fields = [
            'id',
            'titre',
            'slug',
            'description',
            'niveau',
            'prix',
            'certifiant',
            'is_published',
            'lecons',
            'projects',
        ]



class ProgressionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Progression
        fields = [
            'id',
            'lecon',
            'completed',
            'score',
            'updated_at',
        ]


class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = [
            'id',
            'nom',
            'type',
        ]