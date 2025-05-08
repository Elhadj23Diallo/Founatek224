# eduplay/admin.py
from django.contrib import admin
from .models import Question, Answer, Score

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 1  # Nombre d'instances vides de réponse à afficher

class QuestionAdmin(admin.ModelAdmin):
    list_display = ['question_text', 'created_at']
    inlines = [AnswerInline]  # Permet d'ajouter des réponses à chaque question

class AnswerAdmin(admin.ModelAdmin):
    list_display = ['answer_text', 'question', 'is_correct']

class ScoreAdmin(admin.ModelAdmin):
    list_display = ['user', 'score', 'created_at']

admin.site.register(Question, QuestionAdmin)
admin.site.register(Answer, AnswerAdmin)
admin.site.register(Score, ScoreAdmin)


from django.contrib import admin
from .models import (
    ElectroniqueQuestion, ElectroniqueAnswer, ElectroniqueScore,
    ArduinoQuestion, ArduinoAnswer, ArduinoScore,
    IoTQuestion, IoTAnswer, IoTScore
)

# ================
# Électronique
# ================
class ElectroniqueAnswerInline(admin.TabularInline):
    model = ElectroniqueAnswer
    extra = 1

class ElectroniqueQuestionAdmin(admin.ModelAdmin):
    inlines = [ElectroniqueAnswerInline]
    list_display = ('question_text',)
    search_fields = ('question_text',)

admin.site.register(ElectroniqueQuestion, ElectroniqueQuestionAdmin)
admin.site.register(ElectroniqueScore)

# ================
# Arduino
# ================
class ArduinoAnswerInline(admin.TabularInline):
    model = ArduinoAnswer
    extra = 1

class ArduinoQuestionAdmin(admin.ModelAdmin):
    inlines = [ArduinoAnswerInline]
    list_display = ('question_text',)
    search_fields = ('question_text',)

admin.site.register(ArduinoQuestion, ArduinoQuestionAdmin)
admin.site.register(ArduinoScore)

# ================
# IoT
# ================
class IoTAnswerInline(admin.TabularInline):
    model = IoTAnswer
    extra = 1

class IoTQuestionAdmin(admin.ModelAdmin):
    inlines = [IoTAnswerInline]
    list_display = ('question_text',)
    search_fields = ('question_text',)

admin.site.register(IoTQuestion, IoTQuestionAdmin)
admin.site.register(IoTScore)
