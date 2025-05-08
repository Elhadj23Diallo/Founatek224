from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChapitreViewSet, ProjectsViewSet, chapitre_list, projects_list, register, moncompte, creer_chapitre, creer_projet

router = DefaultRouter()
router.register(r'chapitres', ChapitreViewSet)
router.register(r'projects', ProjectsViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('chapitre_list/', chapitre_list, name='chapitre_list'),
    path('projects_list/', projects_list, name='projects_list'),
    path('register/', register, name='register'),
    path('moncompte/', moncompte, name='moncompte'),
    path('creer-chapitre/', creer_chapitre, name='creer_chapitre'),
    path('creer-projet/', creer_projet, name='creer_projet'),
]