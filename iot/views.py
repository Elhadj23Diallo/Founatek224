from django.shortcuts import render, redirect
from rest_framework import viewsets
from .models import Chapitre, Projects
from .serializers import ChapitreSerializer, ProjectsSerializer
from django.core.paginator import Paginator
from django.contrib.auth.models import Group
from .forms import CustomUserCreationForm
from django.contrib.auth.decorators import login_required


# Create your views here.

from django.shortcuts import render, redirect
from django.contrib.auth.models import Group
from .forms import CustomUserCreationForm  # Assure-toi que ce formulaire existe
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User

from django.shortcuts import render, redirect
from .forms import ChapitreForm, ProjectsForm

def creer_chapitre(request):
    if request.method == 'POST':
        form = ChapitreForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('chapitre_list')
    else:
        form = ChapitreForm()
    return render(request, 'iot/creer_chapitre.html', {'form': form})

def creer_projet(request):
    if request.method == 'POST':
        form = ProjectsForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('projects_list')
    else:
        form = ProjectsForm()
    return render(request, 'iot/creer_projet.html', {'form': form})


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data.get('email')
            user.first_name = form.cleaned_data.get('first_name')
            user.last_name = form.cleaned_data.get('last_name')
            user.save()

            # Attribution du groupe/role
            role = form.cleaned_data.get('role')
            try:
                group = Group.objects.get(name=role)
                user.groups.add(group)
            except Group.DoesNotExist:
                pass

            # Vérification et création du token
            token, created = Token.objects.get_or_create(user=user)

            # Redirection vers la page de profil après inscription avec le token dans l'URL
            return redirect(f'login')  # Passer le token dans l'URL
    else:
        form = CustomUserCreationForm()
        
    return render(request, 'iot/register.html', {'form': form})

from django.shortcuts import render
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import Group

from django.shortcuts import render
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import Group

def moncompte(request):
    if request.user.is_authenticated:
        user = request.user
        token = Token.objects.get(user=user)  # Récupérer le token de l'utilisateur

        # Vérifier si l'utilisateur appartient aux groupes 'abonne' ou 'Administrateur'
        is_abonne = user.groups.filter(name='abonne').exists()
        is_admin = user.groups.filter(name='Administrateur').exists()

        # Ajouter ces informations dans le contexte
        context = {
            'user': user,
            'token': token.key,
            'is_abonne': is_abonne or is_admin,  # True si l'utilisateur est 'abonne' ou 'Administrateur'
        }

        return render(request, 'iot/moncompte.html', context)
    else:
        return render(request, 'iot/moncompte.html', {'message': 'Vous devez être connecté pour voir vos informations.'})




class ChapitreViewSet(viewsets.ModelViewSet):
    queryset = Chapitre.objects.all()
    serializer_class = ChapitreSerializer

class ProjectsViewSet(viewsets.ModelViewSet):
    queryset = Projects.objects.all()
    serializer_class = ProjectsSerializer


@login_required
def chapitre_list(request):
    chapitres_list = Chapitre.objects.all().order_by('date_ajout')
    paginator = Paginator(chapitres_list, 5)  # 5 chapitres par page

    page_number = request.GET.get('page')
    chapitres = paginator.get_page(page_number)

    return render(request, 'iot/chapitre_list.html', {
        'chapitres': chapitres,
        'paginator': paginator,
    })

@login_required
def projects_list(request):
    user = request.user
    is_abonne = user.groups.filter(name='Abonné').exists() 
    all_projects = Projects.objects.all().order_by('date_ajout')  # Pour le sommaire
    paginator = Paginator(all_projects, 5)  # 5 projets par page

    page_number = request.GET.get('page')
    projects = paginator.get_page(page_number)  # projets paginés (Page object)

    return render(request, 'iot/projects_list.html', {
        'projects': projects,          # <- utiliser la page paginée ici
        'all_projects': all_projects,  # <- pour le sommaire complet
        'is_abonne':is_abonne, #pour vérifier si l'utilisateur est abonné
    })
