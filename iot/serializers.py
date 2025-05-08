from rest_framework import serializers
from .models import Chapitre, Projects

class ChapitreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chapitre
        fields = '__all__'


class ProjectsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Projects
        fields = '__all__'
