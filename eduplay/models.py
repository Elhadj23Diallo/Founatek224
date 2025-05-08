# eduplay/models.py
from django.db import models
from django.contrib.auth.models import User

class Question(models.Model):
    question_text = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    multiple_answers = models.BooleanField(default=False)  # ⬅️ permet de savoir si on doit utiliser des cases à cocher


    def __str__(self):
        return self.question_text

class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")
    answer_text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.answer_text

class Score(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.score} points"

# ===== Domaine : Électronique =====
class ElectroniqueQuestion(models.Model):
    question_text = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    multiple_answers = models.BooleanField(default=False)

    def __str__(self):
        return self.question_text

class ElectroniqueAnswer(models.Model):
    question = models.ForeignKey(ElectroniqueQuestion, on_delete=models.CASCADE, related_name="answers")
    answer_text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.answer_text

class ElectroniqueScore(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.score} pts (Électronique)"


# ===== Domaine : Arduino =====
class ArduinoQuestion(models.Model):
    question_text = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    multiple_answers = models.BooleanField(default=False)

    def __str__(self):
        return self.question_text

class ArduinoAnswer(models.Model):
    question = models.ForeignKey(ArduinoQuestion, on_delete=models.CASCADE, related_name="answers")
    answer_text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.answer_text

class ArduinoScore(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.score} pts (Arduino)"


# ===== Domaine : IoT =====
class IoTQuestion(models.Model):
    question_text = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    multiple_answers = models.BooleanField(default=False)

    def __str__(self):
        return self.question_text

class IoTAnswer(models.Model):
    question = models.ForeignKey(IoTQuestion, on_delete=models.CASCADE, related_name="answers")
    answer_text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.answer_text

class IoTScore(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.score} pts (IoT)"
