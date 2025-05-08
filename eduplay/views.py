# eduplay/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Question, Answer, Score
from django.core.paginator import Paginator

def score_page(request):
    scores = Score.objects.all().order_by('-score')
    return render(request, 'eduplay/score_page.html', {'scores': scores})

# eduplay/views.py

from django.shortcuts import render, redirect
from .models import Question, Answer

@login_required
def quiz_view(request):
    questions = Question.objects.prefetch_related('answers').all()
    return render(request, 'eduplay/quiz_page.html', {'questions': questions})


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
# ==========================
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

def score_electronique(request):
    scores = ElectroniqueScore.objects.all().order_by('-score')
    return render(request, 'eduplay/score_electronique.html', {'scores': scores, 'domain': 'Électronique'})


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



# =================
# === IOT QUIZ ===
# =================
@login_required
def quiz_iot(request):
    questions = IoTQuestion.objects.prefetch_related('answers').all()
    return render(request, 'eduplay/quiz_iot.html', {'questions': questions, 'domain': 'IoT'})

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
