from django import forms
from .models import TechVideo

class TechVideoForm(forms.ModelForm):
    class Meta:
        model = TechVideo
        fields = ['video', 'description']
