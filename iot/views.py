from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.cache import never_cache
from django.db.models import Avg
from django.utils import timezone
from monetisation.models import Referral
from django.shortcuts import render, redirect
from django.contrib.auth.models import Group
from rest_framework.authtoken.models import Token
import uuid
import json
from .utils.certification import ensure_certificat_pdf
from .models import Lecon, Progression
from iot.utils.pdf import generer_certificat_pdf
from .decorators import formateur_required
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from django.contrib.auth.models import User, Group
from openpyxl import Workbook
# Forms
from .forms import (
    CustomUserCreationForm,
    ParcoursForm,
    LeconForm,
    BlocPedagogiqueForm,
    QuizForm,
    ProjectForm,
    FormateurProfileForm,
    UserProfileForm,
    AccountProfileForm,
)

from .models import (
    Parcours, Lecon, BlocPedagogique,
    Quiz, Progression, Project, Certification, Organisation, FormateurFollow
)

from .serializers import (
    ParcoursSerializer, LeconSerializer,
    BlocPedagogiqueSerializer, QuizSerializer,
    ProgressionSerializer, ProjectSerializer
)

from .utils.pedagogy import lecon_est_debloquee, valider_lecon
from .utils.certification import parcours_est_certifiable, calculer_score_parcours
from .utils.pdf import generer_certificat_pdf
from .decorators import organisation_required






class IsPublishedOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if obj.is_published:
            return True
        return request.user.is_authenticated and request.user.is_staff




def comment_ca_marche(request):
    return render(request, "iot/comment_ca_marche.html")


def landing(request):
    return render(request, "iot/landing.html")


def faq_certification(request):
    return render(request, "iot/faq_certification.html")




@login_required
def edit_profil(request):
    from espcontrol.models import UserProfile
    user = request.user
    is_formateur = hasattr(user, "formateur_profile")
    account_profile, _ = UserProfile.objects.get_or_create(user=user)

    user_form = UserProfileForm(
        request.POST or None,
        instance=user
    )
    account_form = AccountProfileForm(
        request.POST or None,
        request.FILES or None,
        instance=account_profile
    )

    formateur_form = None
    if is_formateur:
        formateur_form = FormateurProfileForm(
            request.POST or None,
            request.FILES or None,
            instance=user.formateur_profile
        )

    if request.method == "POST":
        if user_form.is_valid() and account_form.is_valid() and (
            not is_formateur or formateur_form.is_valid()
        ):
            user_form.save()
            account_form.save()

            if is_formateur:
                formateur_form.save()

            messages.success(request, "Profil mis à jour avec succès ✅")
            return redirect("iot:profil")

    context = {
        "user_form": user_form,
        "account_form": account_form,
        "formateur_form": formateur_form,
        "is_formateur": is_formateur,
    }

    return render(request, "iot/edit_profil.html", context)



class ParcoursViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ParcoursSerializer

    def get_queryset(self):
        user = self.request.user

        # Admin → tout
        if user.is_staff:
            return Parcours.objects.all()

        # Formateur → organisation
        if user.is_authenticated and hasattr(user, "formateur_profile"):
            return Parcours.objects.filter(
                organisation=user.formateur_profile.organisation
            )

        # Étudiant / public
        return Parcours.objects.filter(is_published=True)

    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def progression(self, request, pk=None):
        parcours = self.get_object()
        progressions = Progression.objects.filter(
            user=request.user,
            lecon__parcours=parcours
        )
        return Response(ProgressionSerializer(progressions, many=True).data)



@action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
def demander_certificat(self, request, pk=None):
    parcours = self.get_object()

    if not parcours_est_certifiable(request.user, parcours):
        return Response({"error": "Parcours non validé"}, status=403)

    score = calculer_score_parcours(request.user, parcours)

    certification, _ = Certification.objects.get_or_create(
        user=request.user,
        parcours=parcours,
        defaults={"score_final": score}
    )

    # 🔁 AJOUT : génère ou régénère le PDF si nécessaire
    ensure_certificat_pdf(certification)

    return Response({
        "message": "Certification délivrée 🎓",
        "pdf": certification.pdf.url,
        "uuid": str(certification.uuid)
    })





class LeconViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LeconSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Lecon.objects.filter(
            parcours__is_published=True
        ).select_related("parcours")

    def retrieve(self, request, *args, **kwargs):
        lecon = self.get_object()

        if not lecon_est_debloquee(request.user, lecon):
            raise PermissionDenied(
                "Vous devez valider la leçon précédente pour continuer."
            )

        return super().retrieve(request, *args, **kwargs)




class BlocPedagogiqueViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BlocPedagogiqueSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        queryset = BlocPedagogique.objects.select_related(
            "lecon",
            "lecon__parcours",
            "lecon__parcours__organisation",
        )

        # 🟢 Admin → accès total
        if user.is_staff:
            return queryset

        # 🟢 Formateur → uniquement son organisation
        if hasattr(user, "formateur_profile"):
            return queryset.filter(
                lecon__parcours__organisation=user.formateur_profile.organisation
            )

        # 🟢 Étudiant → uniquement parcours publiés
        return queryset.filter(
            lecon__parcours__is_published=True
        )





class ProjectViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        queryset = Project.objects.select_related(
            "parcours",
            "parcours__organisation",
        )

        # 🟢 Admin → tout
        if user.is_staff:
            return queryset

        # 🟢 Formateur → organisation uniquement
        if hasattr(user, "formateur_profile"):
            return queryset.filter(
                parcours__organisation=user.formateur_profile.organisation
            )

        # 🟢 Étudiant → parcours publiés
        return queryset.filter(
            parcours__is_published=True
        )






class ProgressionViewSet(viewsets.ModelViewSet):
    serializer_class = ProgressionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Progression.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)




class QuizViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = QuizSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        queryset = Quiz.objects.select_related(
            "lecon",
            "lecon__parcours",
            "lecon__parcours__organisation",
        )

        # 🟢 Admin
        if user.is_staff:
            return queryset

        # 🟢 Formateur → organisation
        if hasattr(user, "formateur_profile"):
            return queryset.filter(
                lecon__parcours__organisation=user.formateur_profile.organisation
            )

        # 🟢 Étudiant → parcours publiés
        return queryset.filter(
            lecon__parcours__is_published=True
        )

    @action(detail=False, methods=["post"])
    def submit(self, request):
        lecon_id = request.data.get("lecon_id")
        reponses = request.data.get("reponses", {})

        if not lecon_id:
            return Response(
                {"error": "lecon_id manquant"},
                status=400
            )

        # 🔐 Sécurité multi-tenant + publication
        lecon = get_object_or_404(
            Lecon,
            id=lecon_id,
            parcours__is_published=True
        )

        # 🔒 Vérification progression
        if not lecon_est_debloquee(request.user, lecon):
            raise PermissionDenied(
                "Vous devez valider la leçon précédente."
            )

        quizzes = Quiz.objects.filter(lecon=lecon)

        total = quizzes.count()
        if total == 0:
            return Response(
                {"error": "Aucun quiz pour cette leçon"},
                status=400
            )

        bonnes = 0

        for quiz in quizzes:
            reponse = reponses.get(str(quiz.id))
            if not reponse:
                continue
            if isinstance(reponse, list):
                reponse_set = {str(r).strip().upper() for r in reponse}
            else:
                reponse_set = {r.strip().upper() for r in str(reponse).split(",") if r.strip()}
            if reponse_set == quiz.bonnes_reponses_set():
                bonnes += 1

        score = round((bonnes / total) * 100, 2)

        # ✅ Validation pédagogique
        completed = valider_lecon(request.user, lecon, score)

        return Response({
            "lecon": lecon.titre,
            "score": score,
            "completed": completed,
            "message": (
                "Leçon validée 🎉"
                if completed else
                "Score insuffisant"
            )
        })






# Les vues pour les templates

def verifier_certificat(request, uuid):
    certificat = get_object_or_404(
        Certification,
        uuid=uuid,
        is_valid=True
    )

    organisation = certificat.parcours.organisation

    return render(request, "iot/verification_certificat.html", {
        "certificat": certificat,
        "organisation": organisation,
        "couleur": organisation.couleur_principale or "#00d2ff",
    })



@login_required
def parcours_materiel_pdf(request, parcours_id):
    parcours = get_object_or_404(Parcours, id=parcours_id)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="materiel_{parcours.slug}.pdf"'
    )

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    y = height - 2.5 * cm

    p.setFont("Helvetica-Bold", 8)
    p.setFillColorRGB(0.5, 0.5, 0.5)
    p.drawString(2 * cm, height - 1.2 * cm, "FOUNATEK ACADEMY")

    p.setFont("Helvetica-Bold", 16)
    p.setFillColorRGB(0, 0, 0)
    p.drawString(2 * cm, y, "Liste du matériel requis")
    y -= 0.9 * cm

    p.setFont("Helvetica", 12)
    p.drawString(2 * cm, y, parcours.titre)
    y -= 1 * cm

    p.setStrokeColorRGB(0.7, 0.7, 0.7)
    p.line(2 * cm, y, width - 2 * cm, y)
    y -= 1 * cm

    if parcours.duree_totale_minutes():
        p.setFont("Helvetica-Oblique", 10)
        p.drawString(2 * cm, y, f"Durée totale estimée : ~{parcours.duree_totale_minutes()} minutes ({parcours.lecons.count()} leçons)")
        y -= 1 * cm

    p.setFont("Helvetica", 11)
    lignes = (parcours.materiel_requis or "").splitlines()
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne:
            continue
        if y < 2.5 * cm:
            p.showPage()
            y = height - 2.5 * cm
            p.setFont("Helvetica", 11)
        p.drawString(2.3 * cm, y, "•")
        p.drawString(2.9 * cm, y, ligne)
        y -= 0.7 * cm

    y -= 0.5 * cm
    p.setFont("Helvetica-Oblique", 9)
    p.setFillColorRGB(0.5, 0.5, 0.5)
    if y < 2 * cm:
        p.showPage()
        y = height - 2.5 * cm
    p.drawString(2 * cm, y, "Généré depuis Founatek Academy — apprentissage par le projet.")

    p.showPage()
    p.save()
    return response


@login_required
@never_cache
def liste_parcours(request):
    from django.db.models import Q
    parcours = Parcours.objects.filter(is_published=True).select_related("created_by", "organisation")

    query = request.GET.get("q", "").strip()
    if query:
        parcours = parcours.filter(
            Q(titre__icontains=query) |
            Q(description__icontains=query) |
            Q(lecons__titre__icontains=query) |
            Q(created_by__username__icontains=query) |
            Q(organisation__nom__icontains=query)
        ).distinct()

    following_ids = set(
        FormateurFollow.objects.filter(follower=request.user).values_list("formateur_id", flat=True)
    )

    return render(request, "iot/liste_parcours.html", {
        "parcours": parcours,
        "query": query,
        "following_ids": following_ids,
    })


@login_required
def toggle_follow_formateur(request, formateur_id):
    formateur = get_object_or_404(User, id=formateur_id)
    if formateur == request.user:
        messages.error(request, "Vous ne pouvez pas vous suivre vous-même.")
        return redirect(request.META.get("HTTP_REFERER", "iot:liste_parcours"))

    follow, created = FormateurFollow.objects.get_or_create(follower=request.user, formateur=formateur)
    if created:
        messages.success(request, f"✅ Vous suivez désormais {formateur.username}. Vous serez notifié de ses nouveaux cours.")
    else:
        follow.delete()
        messages.info(request, f"Vous ne suivez plus {formateur.username}.")

    return redirect(request.META.get("HTTP_REFERER", "iot:liste_parcours"))


@login_required
@never_cache
def liste_lecons(request, parcours_id):
    parcours = get_object_or_404(Parcours, id=parcours_id)

    lecons = (
        Lecon.objects
        .filter(parcours=parcours)
        .order_by('ordre')
    )

    progressions = {
        p.lecon_id: p
        for p in Progression.objects.filter(
            user=request.user,
            lecon__parcours=parcours
        )
    }

    lecons_data = []

    for lecon in lecons:
        progression = progressions.get(lecon.id)
        lecons_data.append({
            "lecon": lecon,
            "debloquee": lecon_est_debloquee(request.user, lecon),
            "completed": progression.completed if progression else False,
            "score": progression.score if progression else None,
        })

    is_following = FormateurFollow.objects.filter(follower=request.user, formateur=parcours.created_by).exists()

    return render(request, "iot/liste_lecons.html", {
        "parcours": parcours,
        "lecons_data": lecons_data,
        "is_following": is_following,
    })


@login_required
def lire_lecon(request, lecon_id):

    lecon = get_object_or_404(Lecon, id=lecon_id)

    if not lecon_est_debloquee(request.user, lecon):
        raise PermissionDenied("Vous devez valider la leçon précédente.")

    blocs = lecon.blocs.all().order_by("ordre")
    quizzes = lecon.quizzes.all()

    progression, _ = Progression.objects.get_or_create(
        user=request.user,
        lecon=lecon,
        defaults={"completed": False, "score": 0}
    )

    score = progression.score if progression.completed else None
    lecon_validee = progression.completed

    certificat_url = None
    certificat_uuid = None

    lecon_suivante = (
        Lecon.objects
        .filter(parcours=lecon.parcours, ordre__gt=lecon.ordre)
        .order_by("ordre")
        .first()
    )

    if request.method == "POST":

        if progression.completed:
            messages.info(request, "✅ Cette leçon est déjà validée.")
            return redirect("iot:lire_lecon", lecon_id=lecon.id)

        if not quizzes.exists():
            messages.warning(request, "⚠️ Aucun quiz pour cette leçon.")
            return redirect("iot:lire_lecon", lecon_id=lecon.id)

        bonnes_reponses = 0
        total = quizzes.count()

        for quiz in quizzes:
            reponses = request.POST.getlist(f"quiz_{quiz.id}")
            if not reponses:
                messages.warning(
                    request,
                    "⚠️ Veuillez répondre à toutes les questions."
                )
                return redirect("iot:lire_lecon", lecon_id=lecon.id)

            if {r.upper() for r in reponses} == quiz.bonnes_reponses_set():
                bonnes_reponses += 1

        score = round((bonnes_reponses / total) * 100, 2)
        progression.score = score

        if score >= 80:
            progression.completed = True
            lecon_validee = True

            # 🎓 CERTIFICATION – uniquement dernière leçon
            if not lecon_suivante:

                certification, created = Certification.objects.get_or_create(
                    user=request.user,
                    parcours=lecon.parcours,
                    defaults={
                        "score_final": score,
                        "is_valid": True
                    }
                )

                # Mise à jour score si besoin
                if not created:
                    certification.score_final = score
                    certification.save()

                # 🔁 AJOUT : garantit PDF toujours à jour
                ensure_certificat_pdf(certification)

                certificat_url = certification.pdf.url
                certificat_uuid = certification.uuid

        progression.save()

    return render(request, "iot/lire_lecon.html", {
        "lecon": lecon,
        "blocs": blocs,
        "quizzes": quizzes,
        "score": score,
        "lecon_validee": lecon_validee,
        "lecon_suivante": lecon_suivante,
        "certificat_url": certificat_url,
        "certificat_uuid": certificat_uuid,
    })




    # ==============================
    # 9️⃣ Render final
    # ==============================
    return render(request, "iot/lire_lecon.html", {
        "lecon": lecon,
        "blocs": blocs,
        "quizzes": quizzes,
        "score": score,
        "lecon_validee": lecon_validee,
        "lecon_suivante": lecon_suivante,
        "certificat_url": certificat_url,
        "certificat_uuid": certificat_uuid,
    })










def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)

        if form.is_valid():
            # Création utilisateur
            user = form.save(commit=False)
            user.email = form.cleaned_data['email']
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.save()

            # ✅ Groupe Abonné (créé automatiquement s’il n’existe pas)
            group, _ = Group.objects.get_or_create(name='Abonné')
            user.groups.add(group)

            # ✅ Groupe correspondant au rôle choisi (Formateur/Apprenant/Vendeur)
            # — n'accorde JAMAIS is_staff : uniquement une appartenance à un
            # Group Django, utilisée pour filtrer la navigation par rôle.
            # Le groupe "Formateur" déclenche déjà (signal iot.signals) la
            # création automatique du FormateurProfile associé.
            role = form.cleaned_data.get('role')
            if role in ('Formateur', 'Apprenant', 'Vendeur'):
                role_group, _ = Group.objects.get_or_create(name=role)
                user.groups.add(role_group)

            # Parrainage
            referral_code = form.cleaned_data.get('referral_code')
            referrer_user = None

            if referral_code:
                try:
                    ref = Referral.objects.get(code=referral_code)
                    referrer_user = ref.referred
                except Referral.DoesNotExist:
                    pass

            Referral.objects.create(
                referrer=referrer_user,
                referred=user,
                code=str(uuid.uuid4())
            )

            # Token API
            Token.objects.get_or_create(user=user)

            return redirect('login')

    else:
        form = CustomUserCreationForm()

    return render(request, 'iot/register.html', {'form': form})



@login_required
def profil(request):
    from espcontrol.models import UserProfile
    user = request.user

    # Récupération ou création du token
    token, _ = Token.objects.get_or_create(user=user)

    # Déterminer le rôle
    is_formateur = hasattr(user, "formateur_profile")

    account_profile, _ = UserProfile.objects.get_or_create(user=user)

    certificats = []
    if not is_formateur:
        certificats = Certification.objects.filter(
            user=user,
            is_valid=True
        ).select_related("parcours", "parcours__organisation")

        # 🔁 AJOUT : garantit un PDF à jour (logo, couleurs, etc.)
        for certif in certificats:
            ensure_certificat_pdf(certif)

    context = {
        "user_obj": user,
        "is_formateur": is_formateur,
        "certificats": certificats,
        "api_token": token.key,  # <-- On ajoute le token ici
        "account_profile": account_profile,
    }

    return render(request, "iot/profil.html", context)



#La transformation





@login_required
@formateur_required
def formateur_dashboard(request):
    org = request.user.formateur_profile.organisation
    parcours_qs = Parcours.objects.filter(organisation=org)
    progressions_qs = Progression.objects.filter(lecon__parcours__organisation=org)

    nb_apprenants = progressions_qs.values("user").distinct().count()
    avg_score = progressions_qs.filter(completed=True).aggregate(avg=Avg("score"))["avg"] or 0
    nb_certificats = Certification.objects.filter(parcours__organisation=org).count()

    top_parcours = []
    for p in parcours_qs:
        total_lecons = p.lecons.count()
        if total_lecons == 0:
            continue
        completions = Progression.objects.filter(lecon__parcours=p, completed=True).count()
        apprenants_p = Progression.objects.filter(lecon__parcours=p).values("user").distinct().count()
        taux = round((completions / (total_lecons * apprenants_p)) * 100, 1) if apprenants_p else 0
        top_parcours.append({
            "titre": p.titre, "apprenants": apprenants_p,
            "completions": completions, "taux": min(taux, 100),
        })
    top_parcours.sort(key=lambda x: x["apprenants"], reverse=True)
    top_parcours = top_parcours[:6]

    recent_activity = (
        progressions_qs.select_related("user", "lecon", "lecon__parcours")
        .order_by("-updated_at")[:8]
    )

    today = timezone.now().date()
    week_labels, week_counts = [], []
    for i in range(6, -1, -1):
        day = today - timezone.timedelta(days=i)
        week_labels.append(day.strftime("%d/%m"))
        week_counts.append(progressions_qs.filter(completed=True, updated_at__date=day).count())

    context = {
        "nb_parcours": parcours_qs.count(),
        "nb_lecons": Lecon.objects.filter(parcours__organisation=org).count(),
        "nb_blocs": BlocPedagogique.objects.filter(
            lecon__parcours__organisation=org
        ).count(),
        "nb_quiz": Quiz.objects.filter(
            lecon__parcours__organisation=org
        ).count(),
        "nb_projects": Project.objects.filter(
            parcours__organisation=org
        ).count(),
        "nb_apprenants": nb_apprenants,
        "avg_score": round(avg_score, 1),
        "nb_certificats": nb_certificats,
        "top_parcours": top_parcours,
        "recent_activity": recent_activity,
        "week_labels": json.dumps(week_labels),
        "week_counts": json.dumps(week_counts),
    }
    return render(request, "iot/dashboard.html", context)


@login_required
def apprenant_dashboard(request):
    user = request.user
    progressions = Progression.objects.filter(user=user).select_related("lecon", "lecon__parcours")

    parcours_ids = set(progressions.values_list("lecon__parcours_id", flat=True))
    parcours_stats = []
    for pid in parcours_ids:
        p = Parcours.objects.get(id=pid)
        total = p.lecons.count()
        if total == 0:
            continue
        done = progressions.filter(lecon__parcours=p, completed=True).count()
        pct = round((done / total) * 100)
        parcours_stats.append({
            "parcours": p, "total": total, "done": done,
            "pct": min(pct, 100), "termine": done >= total,
        })
    parcours_stats.sort(key=lambda x: x["pct"], reverse=True)

    nb_en_cours = sum(1 for s in parcours_stats if not s["termine"])
    nb_termines = sum(1 for s in parcours_stats if s["termine"])
    avg_score = progressions.filter(completed=True).aggregate(avg=Avg("score"))["avg"] or 0
    certificats = Certification.objects.filter(user=user).select_related("parcours").order_by("-created_at")

    recent_activity = progressions.order_by("-updated_at")[:8]

    context = {
        "parcours_stats": parcours_stats,
        "nb_en_cours": nb_en_cours,
        "nb_termines": nb_termines,
        "avg_score": round(avg_score, 1),
        "nb_certificats": certificats.count(),
        "certificats": certificats[:5],
        "recent_activity": recent_activity,
    }
    return render(request, "iot/apprenant_dashboard.html", context)




# -----------------------
# ✅ PARCOURS
# -----------------------
@login_required
@formateur_required
def parcours_list(request):
    org = request.user.formateur_profile.organisation
    items = Parcours.objects.filter(organisation=org)
    return render(request, "iot/parcours_list.html", {"items": items})


@login_required
@formateur_required
def parcours_create(request):
    if request.method == "POST":
        form = ParcoursForm(request.POST)
        if form.is_valid():
            parcours = form.save(commit=False)
            parcours.organisation = request.user.formateur_profile.organisation
            parcours.created_by = request.user
            parcours.save()
            messages.success(request, "Parcours créé ✅")
            return redirect("iot:formateur_parcours_list")
    else:
        form = ParcoursForm()

    return render(request, "iot/form.html", {"form": form})


@login_required
@formateur_required
def parcours_update(request, pk):
    obj = get_object_or_404(
        Parcours,
        pk=pk,
        organisation=request.user.formateur_profile.organisation
    )

    if request.method == "POST":
        form = ParcoursForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Parcours modifié ✅")
            return redirect("iot:formateur_parcours_list")
    else:
        form = ParcoursForm(instance=obj)

    return render(request, "iot/form.html", {"form": form})




# -----------------------
# ✅ LECONS
# -----------------------


@login_required
@formateur_required
def lecon_list(request):
    org = request.user.formateur_profile.organisation
    items = Lecon.objects.filter(parcours__organisation=org)
    return render(request, "iot/lecon_list.html", {"items": items})


@login_required
@formateur_required
def lecon_create(request):
    if request.method == "POST":
        form = LeconForm(request.POST)
        if form.is_valid():
            lecon = form.save(commit=False)
            if lecon.parcours.organisation != request.user.formateur_profile.organisation:
                raise PermissionDenied("Accès interdit")
            lecon.save()
            messages.success(request, "Leçon créée ✅")
            return redirect("iot:formateur_lecon_list")
    else:
        form = LeconForm()

    return render(request, "iot/form.html", {"form": form})





@login_required
@formateur_required
def lecon_update(request, pk):
    org = request.user.formateur_profile.organisation

    obj = get_object_or_404(
        Lecon,
        pk=pk,
        parcours__organisation=org
    )

    if request.method == "POST":
        form = LeconForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Leçon modifiée ✅")
            return redirect("iot:formateur_lecon_list")
    else:
        form = LeconForm(instance=obj)

    return render(request, "iot/form.html", {
        "title": "Modifier une leçon",
        "form": form
    })




# -----------------------
# ✅ BLOCS
# -----------------------
@login_required
@formateur_required
def bloc_list(request):
    org = request.user.formateur_profile.organisation

    items = BlocPedagogique.objects.select_related(
        "lecon", "lecon__parcours"
    ).filter(
        lecon__parcours__organisation=org
    ).order_by(
        "lecon__parcours__titre",
        "lecon__ordre",
        "ordre"
    )

    return render(request, "iot/bloc_list.html", {"items": items})





@login_required
@formateur_required
def bloc_create(request):
    org = request.user.formateur_profile.organisation

    if request.method == "POST":
        form = BlocPedagogiqueForm(request.POST, request.FILES)
        if form.is_valid():
            bloc = form.save(commit=False)

            if bloc.lecon.parcours.organisation != org:
                raise PermissionDenied("Accès interdit")

            bloc.save()
            messages.success(request, "Bloc créé ✅")
            return redirect("iot:formateur_bloc_list")
    else:
        form = BlocPedagogiqueForm()

        form.fields["lecon"].queryset = Lecon.objects.filter(
            parcours__organisation=org
        )

    return render(request, "iot/form.html", {
        "title": "Créer un bloc",
        "form": form,
        "is_multipart": True
    })






@login_required
@formateur_required
def bloc_update(request, pk):
    org = request.user.formateur_profile.organisation

    bloc = get_object_or_404(
        BlocPedagogique,
        pk=pk,
        lecon__parcours__organisation=org
    )

    if request.method == "POST":
        form = BlocPedagogiqueForm(
            request.POST,
            request.FILES,
            instance=bloc
        )

        if form.is_valid():
            form.save()
            messages.success(request, "Bloc modifié ✅")
            return redirect("iot:formateur_bloc_list")
    else:
        form = BlocPedagogiqueForm(instance=bloc)

        form.fields["lecon"].queryset = Lecon.objects.filter(
            parcours__organisation=org
        )

    return render(request, "iot/form.html", {
        "title": "Modifier un bloc",
        "form": form,
        "is_multipart": True
    })



# -----------------------
# ✅ QUIZ
# -----------------------

@login_required
@formateur_required
def quiz_list(request):
    org = request.user.formateur_profile.organisation

    items = Quiz.objects.select_related(
        "lecon", "lecon__parcours"
    ).filter(
        lecon__parcours__organisation=org
    ).order_by(
        "lecon__parcours__titre",
        "lecon__ordre"
    )

    return render(request, "iot/quiz_list.html", {"items": items})





@login_required
@formateur_required
def quiz_create(request):
    org = request.user.formateur_profile.organisation

    if request.method == "POST":
        form = QuizForm(request.POST)

        if form.is_valid():
            quiz = form.save(commit=False)

            if quiz.lecon.parcours.organisation != org:
                raise PermissionDenied("Accès interdit")

            quiz.save()
            messages.success(request, "Quiz créé ✅")
            return redirect("iot:formateur_quiz_list")
    else:
        form = QuizForm()
        form.fields["lecon"].queryset = Lecon.objects.filter(
            parcours__organisation=org
        )

    return render(request, "iot/form.html", {
        "title": "Créer un quiz",
        "form": form
    })





@login_required
@formateur_required
def quiz_update(request, pk):
    org = request.user.formateur_profile.organisation

    quiz = get_object_or_404(
        Quiz,
        pk=pk,
        lecon__parcours__organisation=org
    )

    if request.method == "POST":
        form = QuizForm(request.POST, instance=quiz)

        if form.is_valid():
            form.save()
            messages.success(request, "Quiz modifié ✅")
            return redirect("iot:formateur_quiz_list")
    else:
        form = QuizForm(instance=quiz)
        form.fields["lecon"].queryset = Lecon.objects.filter(
            parcours__organisation=org
        )

    return render(request, "iot/form.html", {
        "title": "Modifier un quiz",
        "form": form
    })




# -----------------------
# ✅ PROJECTS
# -----------------------


@login_required
@formateur_required
def project_list(request):
    org = request.user.formateur_profile.organisation

    items = Project.objects.select_related("parcours").filter(
        parcours__organisation=org
    ).order_by("parcours__titre", "ordre")

    return render(request, "iot/project_list.html", {"items": items})





@login_required
@formateur_required
def project_create(request):
    org = request.user.formateur_profile.organisation

    if request.method == "POST":
        form = ProjectForm(request.POST, request.FILES)
        if form.is_valid():
            project = form.save(commit=False)

            if project.parcours.organisation != org:
                raise PermissionDenied("Accès interdit")

            project.save()
            messages.success(request, "Projet créé ✅")
            return redirect("iot:formateur_project_list")
    else:
        form = ProjectForm()
        form.fields["parcours"].queryset = Parcours.objects.filter(
            organisation=org
        )

    return render(request, "iot/form.html", {
        "title": "Créer un projet",
        "form": form,
        "is_multipart": True
    })





@login_required
@formateur_required
def project_update(request, pk):
    org = request.user.formateur_profile.organisation

    obj = get_object_or_404(
        Project,
        pk=pk,
        parcours__organisation=org
    )

    if request.method == "POST":
        form = ProjectForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Projet modifié ✅")
            return redirect("iot:formateur_project_list")
    else:
        form = ProjectForm(instance=obj)
        form.fields["parcours"].queryset = Parcours.objects.filter(
            organisation=org
        )

    return render(request, "iot/form.html", {
        "title": "Modifier un projet",
        "form": form,
        "is_multipart": True
    })






@login_required
@formateur_required
def formateur_progressions(request):
    org = request.user.formateur_profile.organisation

    progressions = Progression.objects.select_related(
        "user", "lecon", "lecon__parcours"
    ).filter(
        lecon__parcours__organisation=org
    ).order_by(
        "user__username",
        "lecon__parcours__titre",
        "lecon__ordre"
    )

    return render(request, "iot/formateur_progressions.html", {
        "progressions": progressions
    })






@login_required
@formateur_required
def formateur_progressions_pdf(request):
    org = request.user.formateur_profile.organisation

    # 🔐 Progressions UNIQUEMENT de l'organisation du formateur
    progressions = (
        Progression.objects
        .select_related("user", "lecon", "lecon__parcours")
        .filter(
            lecon__parcours__organisation=org
        )
        .order_by(
            "user__username",
            "lecon__parcours__titre",
            "lecon__ordre"
        )
    )

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        'attachment; filename="progressions_etudiants.pdf"'
    )

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    y = height - 2 * cm

    # 🏷️ Titre
    p.setFont("Helvetica-Bold", 14)
    p.drawString(2 * cm, y, "Suivi des progressions des étudiants")
    y -= 1.5 * cm

    # 📊 En-têtes
    p.setFont("Helvetica-Bold", 9)
    headers = ["Étudiant", "Parcours", "Leçon", "Score", "Statut"]
    x_positions = [2, 6, 11, 16, 18]

    for header, x in zip(headers, x_positions):
        p.drawString(x * cm, y, header)

    y -= 0.7 * cm
    p.setFont("Helvetica", 9)

    # 📄 Lignes
    for prog in progressions:
        if y < 2 * cm:
            p.showPage()
            y = height - 2 * cm
            p.setFont("Helvetica", 9)

        p.drawString(2 * cm, y, prog.user.username)
        p.drawString(6 * cm, y, prog.lecon.parcours.titre[:25])
        p.drawString(11 * cm, y, prog.lecon.titre[:30])
        p.drawString(16 * cm, y, f"{prog.score}%")
        p.drawString(
            18 * cm,
            y,
            "Validée" if prog.completed else "En cours"
        )

        y -= 0.5 * cm

    p.showPage()
    p.save()

    return response




@login_required
@formateur_required
def formateur_progressions_excel(request):
    org = request.user.formateur_profile.organisation

    # 🔐 Progressions UNIQUEMENT de l'organisation du formateur
    progressions = (
        Progression.objects
        .select_related("user", "lecon", "lecon__parcours")
        .filter(
            lecon__parcours__organisation=org
        )
        .order_by(
            "user__username",
            "lecon__parcours__titre",
            "lecon__ordre"
        )
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Progressions"

    # 📊 En-têtes
    headers = [
        "Étudiant",
        "Parcours",
        "Leçon",
        "Score (%)",
        "Statut",
        "Dernière mise à jour"
    ]
    ws.append(headers)

    # 📄 Données
    for p in progressions:
        ws.append([
            p.user.username,
            p.lecon.parcours.titre,
            p.lecon.titre,
            p.score,
            "Validée" if p.completed else "En cours",
            p.updated_at.strftime("%d/%m/%Y %H:%M"),
        ])

    response = HttpResponse(
        content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    )
    response["Content-Disposition"] = (
        'attachment; filename="progressions_etudiants.xlsx"'
    )

    wb.save(response)
    return response


from django.http import HttpResponseForbidden


from django.http import HttpResponseForbidden
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

@login_required
@organisation_required
def organisation_dashboard(request):

    # =========================
    # 🟢 CAS SUPERUSER
    # =========================
    if request.user.is_superuser:
        org_id = request.GET.get("org")

        # 👉 Pas encore d'organisation choisie
        if not org_id:
            organisations = Organisation.objects.all()
            return render(
                request,
                "iot/organisation_select.html",
                {"organisations": organisations}
            )

        # 👉 Organisation sélectionnée
        org = get_object_or_404(Organisation, id=org_id)

    # =========================
    # 🟢 CAS FORMATEUR NORMAL
    # =========================
    else:
        if not hasattr(request.user, "formateur_profile"):
            return HttpResponseForbidden(
                "Accès réservé aux formateurs d’une organisation"
            )

        org = request.user.formateur_profile.organisation

    # =========================
    # 📊 STATISTIQUES ORGANISATION
    # =========================
    context = {
        "organisation": org,

        # 👥 Utilisateurs
        "nb_formateurs": User.objects.filter(
            formateur_profile__organisation=org
        ).count(),

        "nb_etudiants": User.objects.filter(
            progression__lecon__parcours__organisation=org
        ).distinct().count(),

        # 📚 Contenu
        "nb_parcours": Parcours.objects.filter(
            organisation=org
        ).count(),

        "nb_lecons": Lecon.objects.filter(
            parcours__organisation=org
        ).count(),

        "nb_blocs": BlocPedagogique.objects.filter(
            lecon__parcours__organisation=org
        ).count(),

        "nb_quiz": Quiz.objects.filter(
            lecon__parcours__organisation=org
        ).count(),

        # 🎓 Certifications
        "nb_certificats": Certification.objects.filter(
            parcours__organisation=org,
            is_valid=True
        ).count(),

        # 📈 Progressions
        "nb_progressions": Progression.objects.filter(
            lecon__parcours__organisation=org
        ).count(),
    }

    return render(
        request,
        "iot/organisation_dashboard.html",
        context
    )
