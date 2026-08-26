from django.contrib import admin
from .models import (
    Organisation,
    FormateurProfile,
    Parcours,
    Lecon,
    BlocPedagogique,
    Quiz,
    Project,
    Progression,
    Certification,
    PlatformModule,
)


@admin.register(PlatformModule)
class PlatformModuleAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "is_published", "updated_at")
    list_editable = ("is_published",)  # coche/décoche directement dans la liste
    search_fields = ("name", "key")


# ===========================
# Inlines
# ===========================

class LeconInline(admin.TabularInline):
    model = Lecon
    extra = 0


class BlocPedagogiqueInline(admin.TabularInline):
    model = BlocPedagogique
    extra = 0


class QuizInline(admin.TabularInline):
    model = Quiz
    extra = 0


class ProjectInline(admin.TabularInline):
    model = Project
    extra = 0


# ===========================
# Organisation
# ===========================

@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = (
        "nom",
        "type",
        "created_at",
        "updated_at",
    )

    list_filter = ("type",)
    search_fields = ("nom",)
    ordering = ("nom",)


# ===========================
# Formateur
# ===========================

@admin.register(FormateurProfile)
class FormateurProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "organisation",
        "created_at",
    )

    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "organisation__nom",
    )

    list_filter = ("organisation",)

    list_select_related = (
        "user",
        "organisation",
    )


# ===========================
# Parcours
# ===========================

@admin.register(Parcours)
class ParcoursAdmin(admin.ModelAdmin):
    list_display = (
        "titre",
        "organisation",
        "created_by",
        "niveau",
        "prix",
        "certifiant",
        "is_published",
        "created_at",
    )

    list_filter = (
        "organisation",
        "niveau",
        "certifiant",
        "is_published",
    )

    search_fields = (
        "titre",
        "description",
    )

    prepopulated_fields = {
        "slug": ("titre",)
    }

    list_select_related = (
        "organisation",
        "created_by",
    )

    inlines = [
        LeconInline,
        ProjectInline,
    ]

    def save_model(self, request, obj, form, change):
        if not obj.organisation:
            if hasattr(request.user, "formateur_profile"):
                obj.organisation = request.user.formateur_profile.organisation

        if not obj.created_by:
            obj.created_by = request.user

        super().save_model(request, obj, form, change)


# ===========================
# Leçon
# ===========================

@admin.register(Lecon)
class LeconAdmin(admin.ModelAdmin):
    list_display = (
        "titre",
        "parcours",
        "ordre",
    )

    list_filter = (
        "parcours",
    )

    search_fields = (
        "titre",
        "resume",
    )

    ordering = ("parcours", "ordre")

    list_select_related = (
        "parcours",
    )

    inlines = [
        BlocPedagogiqueInline,
        QuizInline,
    ]


# ===========================
# Bloc pédagogique
# ===========================

@admin.register(BlocPedagogique)
class BlocPedagogiqueAdmin(admin.ModelAdmin):
    list_display = (
        "lecon",
        "type",
        "ordre",
    )

    list_filter = (
        "type",
    )

    search_fields = (
        "lecon__titre",
        "contenu",
    )

    ordering = (
        "lecon",
        "ordre",
    )

    list_select_related = (
        "lecon",
    )


# ===========================
# Quiz
# ===========================

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        "question",
        "lecon",
        "bonne_reponse",
    )

    search_fields = (
        "question",
    )

    list_filter = (
        "bonne_reponse",
    )

    list_select_related = (
        "lecon",
    )


# ===========================
# Projet
# ===========================

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "titre",
        "parcours",
        "ordre",
        "created_at",
    )

    list_filter = (
        "parcours",
    )

    search_fields = (
        "titre",
        "description",
    )

    ordering = (
        "parcours",
        "ordre",
    )

    list_select_related = (
        "parcours",
    )


# ===========================
# Progression
# ===========================

@admin.register(Progression)
class ProgressionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "lecon",
        "completed",
        "score",
        "updated_at",
    )

    list_filter = (
        "completed",
    )

    search_fields = (
        "user__username",
        "lecon__titre",
    )

    list_select_related = (
        "user",
        "lecon",
    )


# ===========================
# Certification
# ===========================

@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "parcours",
        "score_final",
        "is_valid",
        "created_at",
    )

    list_filter = (
        "is_valid",
        "parcours",
    )

    search_fields = (
        "user__username",
        "parcours__titre",
        "uuid",
    )

    readonly_fields = (
        "uuid",
        "qr_code",
        "pdf_generated_at",
        "created_at",
    )

    list_select_related = (
        "user",
        "parcours",
    )