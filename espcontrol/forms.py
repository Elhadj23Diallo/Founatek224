# forms.py
from django import forms
from .models import Relais, Comment

class RelaisForm(forms.ModelForm):
    class Meta:
        model = Relais
        fields = ['num']  # Seul le numéro est saisi, l’utilisateur est lié automatiquement


from .models import Comment

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content', 'parent']  # On inclut parent pour pouvoir répondre à un commentaire

    content = forms.CharField(
        label='Votre commentaire',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Écrivez votre commentaire ici...',
            'rows': 5,
            'style': 'resize: vertical;',
        })
    )

    parent = forms.ModelChoiceField(
        queryset=Comment.objects.all(),
        required=False,
        widget=forms.HiddenInput()  # Caché dans le formulaire, géré en JS ou dans la vue
    )

