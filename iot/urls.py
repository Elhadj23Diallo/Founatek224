from django.urls import path, include
from rest_framework.routers import DefaultRouter

app_name = 'iot'
from .views import (
    ParcoursViewSet, LeconViewSet, BlocPedagogiqueViewSet,
    QuizViewSet, ProgressionViewSet, ProjectViewSet,
    verifier_certificat, lire_lecon, register, formateur_progressions_excel,
    liste_lecons, liste_parcours, edit_profil, comment_ca_marche,
    faq_certification, landing,

    # ✅ Dashboard formateur
    formateur_dashboard,
    parcours_list, parcours_create, parcours_update,
    lecon_list, lecon_create, lecon_update,
    bloc_list, bloc_create, bloc_update,
    quiz_list, quiz_create, quiz_update,
    project_list, project_create, project_update,
    formateur_progressions, formateur_progressions_pdf,
    verifier_certificat, organisation_dashboard, profil,
    apprenant_dashboard, parcours_materiel_pdf, toggle_follow_formateur,
)

router = DefaultRouter()
router.register(r'parcours', ParcoursViewSet, basename='parcours')
router.register(r'lecons', LeconViewSet, basename='lecons')
router.register(r'blocs', BlocPedagogiqueViewSet, basename='blocs')
router.register(r'quiz', QuizViewSet, basename='quiz')
router.register(r'progression', ProgressionViewSet, basename='progression')
router.register(r'projects', ProjectViewSet, basename='projects')

urlpatterns = [
    # ✅ API
    path('api/', include(router.urls)),
    path("profil/", profil, name="profil"),
    path("profil/modifier/", edit_profil, name="edit_profil"),
    # ✅ UX étudiant (déjà fait)
    path('lecon/<int:lecon_id>/', lire_lecon, name='lire_lecon'),
    path('certificat/<uuid:uuid>/', verifier_certificat, name='verifier_certificat'),

    # ✅ Inscription (si tu l’utilises ici)
    path('register/', register, name='register'),

    # ✅ Dashboard formateur
    path("faq-certification/", faq_certification, name="faq_certification"),
    path("landing/", landing, name="landing"),
    path("comment-ca-marche/", comment_ca_marche, name="comment_ca_marche"),
    path('formateur/', formateur_dashboard, name='formateur_dashboard'),

    path('formateur/parcours/', parcours_list, name='formateur_parcours_list'),
    path('formateur/parcours/create/', parcours_create, name='formateur_parcours_create'),
    path('formateur/parcours/<int:pk>/edit/', parcours_update, name='formateur_parcours_update'),

    path('formateur/lecons/', lecon_list, name='formateur_lecon_list'),
    path('formateur/lecons/create/', lecon_create, name='formateur_lecon_create'),
    path('formateur/lecons/<int:pk>/edit/', lecon_update, name='formateur_lecon_update'),

    path('formateur/blocs/', bloc_list, name='formateur_bloc_list'),
    path('formateur/blocs/create/', bloc_create, name='formateur_bloc_create'),
    path('formateur/blocs/<int:pk>/edit/', bloc_update, name='formateur_bloc_update'),

    path('formateur/quiz/', quiz_list, name='formateur_quiz_list'),
    path('formateur/quiz/create/', quiz_create, name='formateur_quiz_create'),
    path('formateur/quiz/<int:pk>/edit/', quiz_update, name='formateur_quiz_update'),

    path('formateur/projects/', project_list, name='formateur_project_list'),
    path('formateur/projects/create/', project_create, name='formateur_project_create'),
    path('formateur/projects/<int:pk>/edit/', project_update, name='formateur_project_update'),
    path("formateur/progressions/", formateur_progressions, name="formateur_progressions"),
    path("formateur/progressions/pdf/", formateur_progressions_pdf, name="formateur_progressions_pdf"),
    path("formateur/progressions/excel/", formateur_progressions_excel, name="formateur_progressions_excel"),
    path("parcours/<int:parcours_id>/materiel/pdf/", parcours_materiel_pdf, name="parcours_materiel_pdf"),
    path("parcours/<int:parcours_id>/", liste_lecons, name="liste_lecons"),
    path("parcours/", liste_parcours, name="liste_parcours"),
    path("apprenant/", apprenant_dashboard, name="apprenant_dashboard"),
    path("formateur/<int:formateur_id>/suivre/", toggle_follow_formateur, name="toggle_follow_formateur"),
    path("certificat/<uuid:uuid>/", verifier_certificat, name="verifier_certificat"),
    path("organisation/dashboard/", organisation_dashboard, name="organisation_dashboard"),
]
