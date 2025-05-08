# eduplay/urls.py
from django.urls import path
from . import views

app_name = 'eduplay'
urlpatterns = [
    path('scores/', views.score_page, name='score_page'),
    path('quiz/', views.quiz_view, name='quiz'),  # Page d'affichage des questions
    path('submit/', views.submit_answer, name='submit_answer'),  # Route pour soumettre la réponse
    path('answers/', views.answers_page, name='answers_page'),
    path('save-score/', views.save_score, name='save_score'),

    # Quiz Électronique
    path('quiz/electronique/', views.quiz_electronique, name='quiz_electronique'),
    path('submit/electronique/', views.submit_electronique, name='submit_electronique'),
    path('scores/electronique/', views.score_electronique, name='score_electronique'),

    # Quiz Arduino
    path('quiz/arduino/', views.quiz_arduino, name='quiz_arduino'),
    path('submit/arduino/', views.submit_arduino, name='submit_arduino'),
    path('scores/arduino/', views.score_arduino, name='score_arduino'),

    # Quiz IoT
    path('quiz/iot/', views.quiz_iot, name='quiz_iot'),
    path('submit/iot/', views.submit_iot, name='submit_iot'),
    path('scores/iot/', views.score_iot, name='score_iot'),

    # Optionnel : pour API ou Ajax
    path('save-score/', views.save_score, name='save_score'),
]
