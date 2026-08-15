# eduplay/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Question, Answer, Score, UserAnswer, ElectroUserAnswer, ArduinoUserAnswer, IotUserAnswer
from django.core.paginator import Paginator
from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt

def score_page(request):
    scores = Score.objects.all().order_by('-score')
    return render(request, 'eduplay/score_page.html', {'scores': scores})

# eduplay/views.py

@login_required
def quiz_view(request):
    questions = Question.objects.prefetch_related('answers').all()

    # Calculer le nombre de tentatives de l'utilisateur sur ce quiz
    # Ici j'assume que toutes les questions appartiennent au même quiz
    attempts = UserAnswer.objects.filter(
        user=request.user,
        question__in=questions
    ).values('attempt').distinct().count()

    can_retry = attempts < 2  # autoriser une tentative si moins de 2 tentatives

    return render(request, 'eduplay/quiz_page.html', {
        'questions': questions,
        'can_retry': can_retry,
        'current_attempt': attempts + 1 if attempts < 2 else 2
    })


#vues pour stocker les reponses données par l'utilisateur
@login_required
@csrf_exempt
def save_user_answers(request):
    if request.method == "POST":
        data = json.loads(request.body)
        answers = data.get("answers", {})
        attempt = data.get("attempt", 1)

        # Vérifie si l'utilisateur a dépassé la limite de tentatives (max 2)
        previous_attempts = UserAnswer.objects.filter(user=request.user).values('attempt').distinct()
        if attempt > 2 or (attempt not in [a['attempt'] for a in previous_attempts] and len(previous_attempts) >= 2):
            return JsonResponse({"status": "error", "message": "Limite de tentatives atteinte."}, status=403)

        # Supprime les réponses de la tentative actuelle avant sauvegarde (update)
        UserAnswer.objects.filter(user=request.user, attempt=attempt).delete()

        for qid, ans_ids in answers.items():
            for ans_id in ans_ids:
                UserAnswer.objects.create(
                    user=request.user,
                    question_id=int(qid),
                    answer_id=ans_id,
                    attempt=attempt
                )
        return JsonResponse({"status": "saved", "attempt": attempt})

    return JsonResponse({"error": "Invalid request"}, status=400)

@login_required
@csrf_exempt
def reset_quiz(request):
    if request.method == 'POST':
        # Supprimer uniquement les réponses attempt=1 (première tentative)
        UserAnswer.objects.filter(user=request.user, attempt=1).delete()
        return JsonResponse({'status': 'reset done'})
    return JsonResponse({'error': 'Invalid request'}, status=400)




@login_required
def submit_answer(request):
    if request.method == 'POST':
        total_score = 0
        user = request.user

        question_ids = request.POST.getlist('question_ids')

        for question_id in question_ids:
            try:
                question = Question.objects.get(id=question_id)
            except Question.DoesNotExist:
                continue

            selected_answers = request.POST.getlist(f'answers_{question_id}')
            correct_answers = question.answers.filter(is_correct=True).values_list('id', flat=True)

            if set(map(int, selected_answers)) == set(correct_answers):
                total_score += 1

        score_obj, created = Score.objects.get_or_create(user=user)
        score_obj.score += total_score
        score_obj.save()

        return redirect('eduplay:score_page')

    return redirect('eduplay:quiz_page')


def answers_page(request):
    questions = Question.objects.prefetch_related('answers')
    return render(request, 'eduplay/answers_page.html', {'questions': questions})


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def save_score(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        score = data.get('score')
        # Tu peux sauvegarder le score ici (en base de données ou ailleurs)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)



from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

# Importation des modèles pour chaque domaine
from .models import (
    ElectroniqueQuestion, ElectroniqueAnswer, ElectroniqueScore,
    ArduinoQuestion, ArduinoAnswer, ArduinoScore,
    IoTQuestion, IoTAnswer, IoTScore,
)

# ==========================
# === ÉLECTRONIQUE QUIZ ===
# =========================

@login_required
def quiz_electronique(request):
    questions = ElectroniqueQuestion.objects.prefetch_related('answers').all()
    return render(request, 'eduplay/quiz_electronique.html', {'questions': questions, 'domain': 'Électronique'})

@login_required
def submit_electronique(request):
    if request.method == 'POST':
        total_score = 0
        user = request.user
        question_ids = request.POST.getlist('question_ids')

        for qid in question_ids:
            try:
                question = ElectroniqueQuestion.objects.get(id=qid)
            except ElectroniqueQuestion.DoesNotExist:
                continue

            selected_answers = request.POST.getlist(f'answers_{qid}')
            correct_answers = question.answers.filter(is_correct=True).values_list('id', flat=True)

            if set(map(int, selected_answers)) == set(correct_answers):
                total_score += 1

        score_obj, created = ElectroniqueScore.objects.get_or_create(user=user)
        score_obj.score += total_score
        score_obj.save()

        return redirect('eduplay:score_electronique')

    return redirect('eduplay:quiz_electronique')



@csrf_exempt
def save_score_electro(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        score = data.get('score')
        # Tu peux sauvegarder le score ici (en base de données ou ailleurs)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)


def score_electronique(request):
    scores = ElectroniqueScore.objects.all().order_by('-score')
    return render(request, 'eduplay/score_electronique.html', {'scores': scores, 'domain': 'Électronique'})


# eduplay/views.py

@login_required
def quiz_view_arduino(request):
    questions = ArduinoQuestion.objects.prefetch_related('answers').all()

    # Calculer le nombre de tentatives de l'utilisateur sur ce quiz
    # Ici j'assume que toutes les questions appartiennent au même quiz
    attempts = ArduinoUserAnswer.objects.filter(
        user=request.user,
        question__in=questions
    ).values('attempt').distinct().count()

    can_retry = attempts < 2  # autoriser une tentative si moins de 2 tentatives

    return render(request, 'eduplay/quiz_arduino.html', {
        'questions': questions,
        'can_retry': can_retry,
        'current_attempt': attempts + 1 if attempts < 2 else 2
    })


#vues pour stocker les reponses données par l'utilisateur
@login_required
@csrf_exempt
def arduino_save_user_answers(request):
    if request.method == "POST":
        data = json.loads(request.body)
        answers = data.get("answers", {})
        attempt = data.get("attempt", 1)

        # Vérifie si l'utilisateur a dépassé la limite de tentatives (max 2)
        previous_attempts = ArduinoUserAnswer.objects.filter(user=request.user).values('attempt').distinct()
        if attempt > 2 or (attempt not in [a['attempt'] for a in previous_attempts] and len(previous_attempts) >= 2):
            return JsonResponse({"status": "error", "message": "Limite de tentatives atteinte."}, status=403)

        # Supprime les réponses de la tentative actuelle avant sauvegarde (update)
        ArduinoUserAnswer.objects.filter(user=request.user, attempt=attempt).delete()

        for qid, ans_ids in answers.items():
            for ans_id in ans_ids:
                ArduinoUserAnswer.objects.create(
                    user=request.user,
                    question_id=int(qid),
                    answer_id=ans_id,
                    attempt=attempt
                )
        return JsonResponse({"status": "saved", "attempt": attempt})

    return JsonResponse({"error": "Invalid request"}, status=400)

@login_required
@csrf_exempt
def reset_quiz_arduino(request):
    if request.method == 'POST':
        # Supprimer uniquement les réponses attempt=1 (première tentative)
        ArduinoUserAnswer.objects.filter(user=request.user, attempt=1).delete()
        return JsonResponse({'status': 'reset done'})
    return JsonResponse({'error': 'Invalid request'}, status=400)



@csrf_exempt
def save_score_arduino(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        score = data.get('score')
        # Tu peux sauvegarder le score ici (en base de données ou ailleurs)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)




# =====================
# === ARDUINO QUIZ ===
# =====================

@login_required
def quiz_arduino(request):
    questions = ArduinoQuestion.objects.prefetch_related('answers').all()
    return render(request, 'eduplay/quiz_arduino.html', {'questions': questions, 'domain': 'Arduino'})


@login_required
def submit_arduino(request):
    if request.method == 'POST':
        total_score = 0
        user = request.user
        question_ids = request.POST.getlist('question_ids')

        for qid in question_ids:
            try:
                question = ArduinoQuestion.objects.get(id=qid)
            except ArduinoQuestion.DoesNotExist:
                continue

            selected_answers = request.POST.getlist(f'answers_{qid}')
            correct_answers = question.answers.filter(is_correct=True).values_list('id', flat=True)

            if set(map(int, selected_answers)) == set(correct_answers):
                total_score += 1

        score_obj, created = ArduinoScore.objects.get_or_create(user=user)
        score_obj.score += total_score
        score_obj.save()

        return redirect('eduplay:score_arduino')

    return redirect('eduplay:quiz_arduino')




def score_arduino(request):
    questions = ArduinoAnswer.objects.prefetch_related('answers')
    return render(request, 'eduplay/score_arduino.html', {'questions': questions})




# eduplay/views.py

@login_required
def quiz_view_electro(request):
    questions = ElectroniqueQuestion.objects.prefetch_related('answers').all()

    # Calculer le nombre de tentatives de l'utilisateur sur ce quiz
    # Ici j'assume que toutes les questions appartiennent au même quiz
    attempts = ElectroUserAnswer.objects.filter(
        user=request.user,
        question__in=questions
    ).values('attempt').distinct().count()

    can_retry = attempts < 2  # autoriser une tentative si moins de 2 tentatives

    return render(request, 'eduplay/quiz_electronique.html', {
        'questions': questions,
        'can_retry': can_retry,
        'current_attempt': attempts + 1 if attempts < 2 else 2
    })


#vues pour stocker les reponses données par l'utilisateur
@login_required
@csrf_exempt
def electro_save_user_answers(request):
    if request.method == "POST":
        data = json.loads(request.body)
        answers = data.get("answers", {})
        attempt = data.get("attempt", 1)

        # Vérifie si l'utilisateur a dépassé la limite de tentatives (max 2)
        previous_attempts = ElectroUserAnswer.objects.filter(user=request.user).values('attempt').distinct()
        if attempt > 2 or (attempt not in [a['attempt'] for a in previous_attempts] and len(previous_attempts) >= 2):
            return JsonResponse({"status": "error", "message": "Limite de tentatives atteinte."}, status=403)

        # Supprime les réponses de la tentative actuelle avant sauvegarde (update)
        ElectroAnswer.objects.filter(user=request.user, attempt=attempt).delete()

        for qid, ans_ids in answers.items():
            for ans_id in ans_ids:
                ElectroAnswer.objects.create(
                    user=request.user,
                    question_id=int(qid),
                    answer_id=ans_id,
                    attempt=attempt
                )
        return JsonResponse({"status": "saved", "attempt": attempt})

    return JsonResponse({"error": "Invalid request"}, status=400)

@login_required
@csrf_exempt
def reset_quiz_electro(request):
    if request.method == 'POST':
        # Supprimer uniquement les réponses attempt=1 (première tentative)
        ElectroAnswer.objects.filter(user=request.user, attempt=1).delete()
        return JsonResponse({'status': 'reset done'})
    return JsonResponse({'error': 'Invalid request'}, status=400)




# =================
# === IOT QUIZ ===
# =================
@login_required

@login_required
def submit_iot(request):
    if request.method == 'POST':
        total_score = 0
        user = request.user
        question_ids = request.POST.getlist('question_ids')

        for qid in question_ids:
            try:
                question = IoTQuestion.objects.get(id=qid)
            except IoTQuestion.DoesNotExist:
                continue

            selected_answers = request.POST.getlist(f'answers_{qid}')
            correct_answers = question.answers.filter(is_correct=True).values_list('id', flat=True)

            if set(map(int, selected_answers)) == set(correct_answers):
                total_score += 1

        score_obj, created = IoTScore.objects.get_or_create(user=user)
        score_obj.score += total_score
        score_obj.save()

        return redirect('eduplay:score_iot')

    return redirect('eduplay:quiz_iot')



def score_iot(request):
    questions = IoTQuestion.objects.prefetch_related('answers')
    return render(request, 'eduplay/score_iot.html', {'questions': questions})


# ================================
# === Autres fonctions utiles ===
# ================================
@csrf_exempt
def save_score(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        score = data.get('score')
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)







# eduplay/views.py

@login_required
def quiz_view_iot(request):
    questions = IoTQuestion.objects.prefetch_related('answers').all()

    # Calculer le nombre de tentatives de l'utilisateur sur ce quiz
    # Ici j'assume que toutes les questions appartiennent au même quiz
    attempts = IotUserAnswer.objects.filter(
        user=request.user,
        question__in=questions
    ).values('attempt').distinct().count()

    can_retry = attempts < 2  # autoriser une tentative si moins de 2 tentatives

    return render(request, 'eduplay/quiz_iot.html', {
        'questions': questions,
        'can_retry': can_retry,
        'current_attempt': attempts + 1 if attempts < 2 else 2
    })


#vues pour stocker les reponses données par l'utilisateur
@login_required
@csrf_exempt
def iot_save_user_answers(request):
    if request.method == "POST":
        data = json.loads(request.body)
        answers = data.get("answers", {})
        attempt = data.get("attempt", 1)

        # Vérifie si l'utilisateur a dépassé la limite de tentatives (max 2)
        previous_attempts = ArduinoUserAnswer.objects.filter(user=request.user).values('attempt').distinct()
        if attempt > 2 or (attempt not in [a['attempt'] for a in previous_attempts] and len(previous_attempts) >= 2):
            return JsonResponse({"status": "error", "message": "Limite de tentatives atteinte."}, status=403)

        # Supprime les réponses de la tentative actuelle avant sauvegarde (update)
        IotUserAnswer.objects.filter(user=request.user, attempt=attempt).delete()

        for qid, ans_ids in answers.items():
            for ans_id in ans_ids:
                IotUserAnswer.objects.create(
                    user=request.user,
                    question_id=int(qid),
                    answer_id=ans_id,
                    attempt=attempt
                )
        return JsonResponse({"status": "saved", "attempt": attempt})

    return JsonResponse({"error": "Invalid request"}, status=400)

@login_required
@csrf_exempt
def reset_quiz_iot(request):
    if request.method == 'POST':
        # Supprimer uniquement les réponses attempt=1 (première tentative)
        IotUserAnswer.objects.filter(user=request.user, attempt=1).delete()
        return JsonResponse({'status': 'reset done'})
    return JsonResponse({'error': 'Invalid request'}, status=400)


@csrf_exempt
def save_score_iot(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        score = data.get('score')
        # Tu peux sauvegarder le score ici (en base de données ou ailleurs)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)
