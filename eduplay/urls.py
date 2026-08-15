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
    path('quiz/electronique/', views.quiz_view_electro, name='quiz_electronique'),
    path('submit/electronique/', views.submit_electronique, name='submit_electronique'),
    path('scores/electronique/', views.score_electronique, name='score_electronique'),

    # Quiz Arduino
    path('quiz/arduino/', views.quiz_view_arduino, name='quiz_arduino'),
    path('submit/arduino/', views.submit_arduino, name='submit_arduino'),
    path('scores/arduino/', views.score_arduino, name='score_arduino'),

    # Quiz IoT
    path('quiz/iot/', views.quiz_view_iot, name='quiz_iot'),
    path('submit/iot/', views.submit_iot, name='submit_iot'),
    path('scores/iot/', views.score_iot, name='score_iot'),

    # Optionnel : pour API ou Ajax
     # Quiz general
    path('save-score/', views.save_score, name='save_score'),
    path("save-answers/", views.save_user_answers, name="save_user_answers"),
    path('reset-quiz/', views.reset_quiz, name='reset_quiz'),
     # Quiz Arduino
    path('save-score-arduino/', views.save_score_arduino, name='save_score_arduino'),
    path("save-answers-arduino/", views.arduino_save_user_answers, name="save_user_answers_arduino"),
    path('reset-quiz-arduino/', views.reset_quiz_arduino, name='reset_quiz_arduino'),
     # Quiz Electro
    path('save-score-electro/', views.save_score_electro, name='save_score_electro'),
    path("save-answers-electro/", views.electro_save_user_answers, name="save_user_answers_electro"),
    path('reset-quiz-electro/', views.reset_quiz_electro, name='reset_quiz_electro'),
         # Quiz Iot
    path('save-score-iot/', views.save_score_iot, name='save_score_iot'),
    path("save-answers-iot/", views.iot_save_user_answers, name="save_user_answers_iot"),
    path('reset-quiz-iot/', views.reset_quiz_iot, name='reset_quiz_iot'),


]
