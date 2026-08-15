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
)


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ("nom", "type", "created_at")
    search_fields = ("nom",)


@admin.register(FormateurProfile)
class FormateurProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "organisation", "created_at")
    list_select_related = ("user", "organisation")


@admin.register(Parcours)
class ParcoursAdmin(admin.ModelAdmin):
    list_display = ("titre", "organisation", "created_by", "is_published")
    list_filter = ("organisation", "is_published")
    search_fields = ("titre",)

    def save_model(self, request, obj, form, change):
        if not obj.organisation:
            if hasattr(request.user, "formateur_profile"):
                obj.organisation = request.user.formateur_profile.organisation
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
