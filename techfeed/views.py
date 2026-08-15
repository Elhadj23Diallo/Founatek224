from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import (
    TechVideo, TechCommentaire, TechCategorie, TechVideoLike, TechGroup, GroupCallSession,
    TechNotification, Profile, TechFollow, TechMessage, LiveSession, LiveInvite, LiveChatMessage, LiveNotification, CallSession
)
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.db.models import Q
# techfeed/views.py (Ajoute les imports en haut)
from espcontrol.models import Relais
from espcontrol.ai_controller import analyze_iot_command
import time

import jwt
from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden



#Notifications

def badging(request):
    if request.user.is_authenticated:
        # Compte les notifications (Likes, Commentaires, Follows, Live) non lues
        notif_count = TechNotification.objects.filter(receiver=request.user, is_read=False).count()

        # Compte les messages privés non lus
        msg_count = TechMessage.objects.filter(receiver=request.user, is_read=False).count()

        return {
            'badge_notif_count': notif_count,
            'badge_msg_count': msg_count,
        }
    return {}

# ============================================================
#                        PROFIL
# ============================================================
@login_required
def profile_view(request, username):
    user_profile = get_object_or_404(User, username=username)
    profile, created = Profile.objects.get_or_create(user=user_profile)

    following_count = TechFollow.objects.filter(follower=user_profile).count()
    followers_count = TechFollow.objects.filter(following=user_profile).count()
    likes_count = TechVideoLike.objects.filter(video__auteur=user_profile).count()

    is_following = TechFollow.objects.filter(follower=request.user, following=user_profile).exists()

    # --- GESTION DES ONGLETS (TABS) ---
    tab = request.GET.get('tab')
    videos = []

    if tab == 'likes' and request.user == user_profile:
        # Récupérer les vidéos que J'AI likées
        liked_video_ids = TechVideoLike.objects.filter(user=user_profile).values_list('video_id', flat=True)
        videos = TechVideo.objects.filter(id__in=liked_video_ids).order_by('-date_pub')

    elif tab == 'private' and request.user == user_profile:
        # Placeholder pour vidéos privées (si tu ajoutes un champ is_private plus tard)
        # Pour l'instant, vide ou filtre sur un champ spécifique
        videos = []

    else:
        # Par défaut : Mes vidéos publiques
        videos = TechVideo.objects.filter(auteur=user_profile).order_by('-date_pub')

    # ----------------------------------

    tags = profile.tags.split(",") if profile.tags else []
    can_message = is_following

    context = {
        "user_profile": user_profile,
        "profile": profile,
        "following_count": following_count,
        "followers_count": followers_count,
        "likes_count": likes_count,
        "is_following": is_following,
        "videos": videos,
        "tags": tags,
        "can_message": can_message,
    }

    return render(request, "techfeed/updated_profile.html", context)


@login_required
def delete_video(request, pk):
    video = get_object_or_404(TechVideo, pk=pk)

    # Sécurité : seul l'auteur peut supprimer
    if request.user == video.auteur:
        # Supprime les fichiers physiques (optionnel mais recommandé)
        video.video.delete(save=False)
        if video.miniature:
            video.miniature.delete(save=False)

        video.delete()

    return redirect('techfeed:profile', username=request.user.username)


@login_required
def edit_video(request, pk):
    video = get_object_or_404(TechVideo, pk=pk)

    if request.user != video.auteur:
        return redirect('techfeed:feed')

    if request.method == "POST":
        new_desc = request.POST.get("description")
        # On peut aussi ajouter la modif de tags, catégorie, etc.
        if new_desc:
            video.description = new_desc
            video.save()
            return redirect('techfeed:profile', username=request.user.username)

    # Si GET, on affiche un petit formulaire d'édition (page dédiée ou simple template)
    return render(request, "techfeed/edit_video.html", {"video": video})


@login_required
def upload_avatar(request):
    # On récupère le profil (ou on le crée s'il n'existe pas)
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        # 1. Gestion de l'Image
        avatar_file = request.FILES.get("avatar")
        if avatar_file:
            profile.avatar = avatar_file

        # 2. Gestion de la Bio
        bio = request.POST.get("bio")
        if bio is not None:
            profile.bio = bio

        # 3. Gestion des Tags (Optionnel)
        tags = request.POST.get("tags")
        if tags is not None:
            profile.tags = tags

        profile.save()
        return redirect("techfeed:profile", username=request.user.username)

    # Pour le GET, on passe le profil existant pour pré-remplir les champs
    return render(request, "techfeed/upload_avatar.html", {"profile": profile})


@login_required
def profile_followers(request, username):
    user_profile = get_object_or_404(User, username=username)

    # 1. On récupère la liste brute des abonnés
    # (Ceux qui suivent le profil qu'on regarde)
    raw_followers = User.objects.filter(suivis__following=user_profile)

    # 2. On enrichit la liste pour savoir si JE les suis aussi
    followers = []
    for person in raw_followers:
        # Est-ce que JE suis cette personne ?
        person.is_followed = TechFollow.objects.filter(follower=request.user, following=person).exists()
        # Est-ce que cette personne ME suit ? (Utile pour le badge "Amis")
        person.is_following_me = TechFollow.objects.filter(follower=person, following=request.user).exists()
        followers.append(person)

    return render(request, "techfeed/profile_followers.html", {
        "user_profile": user_profile,
        "followers": followers
    })


@login_required
def profile_following(request, username):
    user_profile = get_object_or_404(User, username=username)

    # 1. On récupère la liste brute des abonnements
    # (Ceux que le profil suit)
    raw_following = User.objects.filter(abonnés__follower=user_profile)

    # 2. On enrichit la liste
    following = []
    for person in raw_following:
        # Est-ce que JE suis cette personne ?
        person.is_followed = TechFollow.objects.filter(follower=request.user, following=person).exists()
        # Est-ce que cette personne ME suit ?
        person.is_following_me = TechFollow.objects.filter(follower=person, following=request.user).exists()
        following.append(person)

    return render(request, "techfeed/profile_following.html", {
        "user_profile": user_profile,
        "following": following
    })



# ============================================================
#                        FOLLOW
# ============================================================

@login_required
def toggle_follow(request, user_id):
    other = get_object_or_404(User, id=user_id)

    if request.user == other:
        return redirect(request.META.get("HTTP_REFERER", "/"))

    follow, created = TechFollow.objects.get_or_create(
        follower=request.user, following=other
    )

    if not created:
        follow.delete()
    else:
        TechNotification.objects.create(
            sender=request.user,
            receiver=other,
            notif_type="follow",
            message=f"{request.user.username} vous a suivi."
        )

    return redirect(request.META.get("HTTP_REFERER", "/"))


# ============================================================
#                   NOTIFICATIONS
# ============================================================

@login_required
def notifications_view(request):
    # 1. Marquer toutes les notifs comme lues quand on ouvre la page
    TechNotification.objects.filter(receiver=request.user, is_read=False).update(is_read=True)

    # 2. Récupérer les notifs pour l'affichage
    notifications = TechNotification.objects.filter(receiver=request.user).order_by("-created_at")

    # ... (reste de ta logique de filtre) ...

    return render(request, "techfeed/updated_notifications.html", {
        "notifications": notifications
    })



@login_required
@require_POST
def delete_notification(request, notif_id):
    notif = get_object_or_404(
        TechNotification,
        id=notif_id,
        receiver=request.user  # 🔐 sécurité clé
    )
    notif.delete()
    return redirect("techfeed:notifications")
# ============================================================
#                        RECHERCHE
# ============================================================

@login_required
def search_view(request):
    query = request.GET.get("q", "").strip()

    following_ids = list(
        TechFollow.objects.filter(follower=request.user)
        .values_list("following", flat=True)
    )

    users = []
    videos = []

    if query:
        users = User.objects.filter(username__icontains=query)\
                            .exclude(id=request.user.id)

        videos = TechVideo.objects.filter(
            Q(description__icontains=query) |
            Q(tags__icontains=query)
        )

    return render(request, "techfeed/updated_search.html", {
        "query": query,
        "users": users,
        "videos": videos,
        "following_ids": following_ids,
    })


# ============================================================
#                        AMIS
# ============================================================

@login_required
def friends_view(request):
    follower_ids = TechFollow.objects.filter(
        following=request.user
    ).values_list("follower", flat=True)

    friends = User.objects.filter(id__in=follower_ids)

    for friend in friends:
        friend.is_followed = TechFollow.objects.filter(
            follower=request.user, following=friend
        ).exists()

    return render(request, "techfeed/updated_friends.html", {
        "friends": friends
    })


# ============================================================
#                     UPLOAD VIDEO (API)
# ============================================================

@csrf_exempt
@login_required
@require_POST
def api_upload_video(request):

    video_file = request.FILES.get("video")
    description = request.POST.get("description", "")
    tags = request.POST.get("tags", "")
    categorie_id = request.POST.get("categorie_id")

    if not video_file:
        return JsonResponse({"error": "Aucun fichier vidéo reçu."}, status=400)

    categorie = None
    if categorie_id:
        categorie = TechCategorie.objects.filter(id=categorie_id).first()

    video = TechVideo.objects.create(
        auteur=request.user,
        video=video_file,
        description=description,
        tags=tags,
        categorie=categorie,
    )

    return JsonResponse({
        "message": "Vidéo ajoutée avec succès.",
        "video_id": video.id
    })


# ============================================================
#                     FEED TIKTOK STYLE
# ============================================================

@login_required
def feed(request):
    tab = request.GET.get("tab")

    following_ids = list(
        TechFollow.objects.filter(follower=request.user)
        .values_list("following", flat=True)
    )

    if tab == "following":
        videos = TechVideo.objects.filter(auteur_id__in=following_ids)
    else:
        videos = TechVideo.objects.all()

    videos = videos.order_by("-date_pub")

    liked_ids = list(
        TechVideoLike.objects.filter(user=request.user)
        .values_list("video_id", flat=True)
    )

    return render(request, "techfeed/feed.html", {
        "videos": videos,
        "liked_ids": liked_ids,
        "following_ids": following_ids,
    })


# ============================================================
#                       VIDEO DETAIL
# ============================================================

@login_required
def video_detail(request, pk):
    video = get_object_or_404(TechVideo, pk=pk)

    # Incrémenter les vues
    video.vues += 1
    video.save(update_fields=["vues"])

    # 🔥 UNIQUEMENT les commentaires parents
    commentaires = (
        TechCommentaire.objects
        .filter(video=video, parent__isnull=True)
        .select_related(
            "auteur",
            "auteur__profile"
        )
        .prefetch_related(
            "reponses",
            "reponses__auteur",
            "reponses__auteur__profile",
            "reponses__reponses",                     # 🔥 réponses de réponses
            "reponses__reponses__auteur",
            "reponses__reponses__auteur__profile"
        )
        .order_by("-date_pub")
    )

    # Follow logic
    is_following = False
    if request.user != video.auteur:
        is_following = TechFollow.objects.filter(
            follower=request.user,
            following=video.auteur
        ).exists()

    return render(
        request,
        "techfeed/video_detail.html",
        {
            "video": video,
            "commentaires": commentaires,
            "is_following": is_following,
        }
    )




@login_required
def repondre_commentaire(request, comment_id):
    parent = get_object_or_404(TechCommentaire, id=comment_id)

    if request.method == "POST":
        contenu = request.POST.get("contenu", "").strip()
        if contenu:
            TechCommentaire.objects.create(
                video=parent.video,
                auteur=request.user,
                contenu=contenu,
                parent=parent  # 👈 LIEN CRITIQUE
            )

    return redirect("techfeed:video_detail", pk=parent.video.id)


# ============================================================
#                         LIKE
# ============================================================

@login_required
def like_video(request, pk):
    video = get_object_or_404(TechVideo, pk=pk)

    obj, created = TechVideoLike.objects.get_or_create(video=video, user=request.user)

    if not created:
        obj.delete()
        liked = False
    else:
        liked = True

    return JsonResponse({
        "liked": liked,
        "likes_count": TechVideoLike.objects.filter(video=video).count()
    })


# ============================================================
#                      COMMENTAIRES
# ============================================================

@login_required
def ajouter_commentaire(request, video_id):
    if request.method == "POST":
        contenu = request.POST.get("contenu", "").strip()
        parent_id = request.POST.get("parent_id")

        if contenu:
            video = get_object_or_404(TechVideo, id=video_id)

            parent = None
            if parent_id:
                parent = TechCommentaire.objects.filter(id=parent_id).first()

            TechCommentaire.objects.create(
                video=video,
                auteur=request.user,
                contenu=contenu,
                parent=parent
            )

    return redirect("techfeed:video_detail", pk=video_id)




# ============================================================
#                        UPLOADER
# ============================================================

@login_required
def uploader_video(request):
    if request.method == "POST":
        video_file = request.FILES.get("video")
        description = request.POST.get("description", "")
        tags = request.POST.get("tags", "")
        categorie_id = request.POST.get("categorie_id")

        categorie = TechCategorie.objects.filter(id=categorie_id).first()

        if video_file:
            TechVideo.objects.create(
                auteur=request.user,
                video=video_file,
                description=description,
                tags=tags,
                categorie=categorie,
            )
            return redirect("techfeed:feed")

    return render(request, "techfeed/uploader.html", {
        "categories": TechCategorie.objects.all()
    })


# ============================================================
#                         MESSAGES
# ============================================================

# views.py

# techfeed/views.py

@login_required
def delete_message(request, message_id):
    msg = get_object_or_404(TechMessage, id=message_id)
    # On redirige vers l'autre personne
    redirect_user_id = msg.receiver.id if msg.sender == request.user else msg.sender.id

    if msg.sender == request.user:
        if msg.attachment:
            msg.attachment.delete(save=False)
        msg.delete()

    return redirect('techfeed:conversation', user_id=redirect_user_id)

@login_required
def messages_view(request):
    # 1. Conversations Privées
    msgs = TechMessage.objects.filter(
        (Q(sender=request.user) | Q(receiver=request.user)) & Q(group__isnull=True)
    ).order_by("-timestamp")

    conversations = {}
    for msg in msgs:
        other = msg.receiver if msg.sender == request.user else msg.sender
        if other.id not in conversations:
            conversations[other.id] = {
                "type": "private",
                "object": other,
                "last_message": msg,
                "timestamp": msg.timestamp
            }

    # 2. Groupes
    my_groups = request.user.tech_groups.all()
    for group in my_groups:
        last_msg = group.group_messages.last()
        conversations[f"group_{group.id}"] = {
            "type": "group",
            "object": group,
            "last_message": last_msg,
            "timestamp": last_msg.timestamp if last_msg else group.created_at
        }

    # Trier par date (le plus récent en haut)
    sorted_convs = sorted(conversations.values(), key=lambda x: x['timestamp'], reverse=True)

    # Liste des amis pour le formulaire de création de groupe
    friends = User.objects.filter(suivis__following=request.user)

    return render(request, "techfeed/updated_messages.html", {
        "conversations": sorted_convs,
        "friends": friends
    })

# views.py

@login_required
def create_group(request):
    if request.method == "POST":
        name = request.POST.get("group_name")
        members_ids = request.POST.getlist("members")

        if name:
            group = TechGroup.objects.create(name=name)
            # Le créateur est ajouté aux membres ET aux admins
            group.members.add(request.user)
            group.admins.add(request.user)

            for uid in members_ids:
                group.members.add(User.objects.get(id=uid))

            return redirect('techfeed:group_chat', group_id=group.id)

    return redirect('techfeed:messages')


@login_required
def group_conversation_view(request, group_id):
    group = get_object_or_404(TechGroup, id=group_id)

    # 🔐 Sécurité : membre obligatoire
    if request.user not in group.members.all():
        return redirect("techfeed:messages")

    # 💬 Messages du groupe
    messages = TechMessage.objects.filter(group=group).order_by("timestamp")

    # 👥 Amis que je peux ajouter
    my_friends_ids = TechFollow.objects.filter(
        follower=request.user
    ).values_list("following_id", flat=True)

    potential_members = User.objects.filter(
        id__in=my_friends_ids
    ).exclude(id__in=group.members.all())

    # 👑 Admin ?
    is_admin = request.user in group.admins.all()

    # 🔴 LIVE ACTIF (IMPORTANT)
    live_session = LiveSession.objects.filter(
        group=group,
        is_live=True
    ).first()

    return render(request, "techfeed/updated_group_chat.html", {
        "group": group,
        "messages": messages,
        "potential_members": potential_members,
        "is_admin": is_admin,
        "live_session": live_session,  # ✅ CRUCIAL
    })


@login_required
@require_POST
def update_group_settings(request, group_id):
    group = get_object_or_404(TechGroup, id=group_id)

    # SÉCURITÉ : Seul un admin peut modifier les infos
    if request.user not in group.admins.all():
        return redirect("techfeed:group_chat", group_id=group.id)

    # 1. Modif Infos
    if request.POST.get('group_name'):
        group.name = request.POST.get('group_name')
    if request.POST.get('description'):
        group.description = request.POST.get('description')
    if request.FILES.get('avatar'):
        group.avatar = request.FILES.get('avatar')

    # 2. Ajout Membres (Tout membre peut ajouter, ou seulement admin selon ton choix. Ici Admin.)
    new_members = request.POST.getlist('new_members')
    if new_members:
        for member_id in new_members:
            user_to_add = User.objects.get(id=member_id)
            group.members.add(user_to_add)

    group.save()
    return redirect("techfeed:group_chat", group_id=group.id)

@login_required
def manage_group_member(request, group_id, action, member_id):
    """
    Action: 'promote' (devenir admin), 'demote' (retirer admin), 'kick' (virer du groupe)
    """
    group = get_object_or_404(TechGroup, id=group_id)
    target_user = get_object_or_404(User, id=member_id)

    # Sécurité : Seul un admin peut faire ça
    if request.user not in group.admins.all():
        return redirect("techfeed:group_chat", group_id=group.id)

    if action == 'promote':
        group.admins.add(target_user)
    elif action == 'demote':
        # On ne peut pas se retirer soi-même si on est le dernier admin (optionnel)
        group.admins.remove(target_user)
    elif action == 'kick':
        group.members.remove(target_user)
        group.admins.remove(target_user) # On le retire aussi des admins par sécurité

    return redirect("techfeed:group_chat", group_id=group.id)



@login_required
@require_POST
def send_group_message(request, group_id):
    group = get_object_or_404(TechGroup, id=group_id)

    if request.user not in group.members.all():
        return redirect('techfeed:messages')

    content = request.POST.get("content", "").strip()
    attachment = request.FILES.get("attachment")

    if content or attachment:
        TechMessage.objects.create(
            sender=request.user,
            group=group,  # On lie au groupe, pas à un receiver
            content=content,
            attachment=attachment
        )

        # Optionnel : Créer des notifs pour les membres (sauf l'expéditeur)
        # for member in group.members.exclude(id=request.user.id):
        #    TechNotification.objects.create(...)

    return redirect("techfeed:group_chat", group_id=group.id)


@login_required
def conversation_view(request, user_id):
    other = get_object_or_404(User, id=user_id)

    msgs = TechMessage.objects.filter(
        Q(sender=request.user, receiver=other) |
        Q(sender=other, receiver=request.user)
    ).order_by("timestamp")

    return render(request, "techfeed/updated_conversation.html", {
        "messages": msgs,
        "other_user": other,
    })


# Dans views.py

@login_required
@require_POST
def send_message(request, user_id):
    other = get_object_or_404(User, id=user_id)
    content = request.POST.get("content", "").strip()

    # On récupère le fichier (image ou autre)
    attachment = request.FILES.get("attachment")

    # On envoie si y'a du texte OU un fichier
    if content or attachment:
        TechMessage.objects.create(
            sender=request.user,
            receiver=other,
            content=content,
            # Assure-toi que ton modèle a ce champ (ex: image=attachment)
            # Si ton champ s'appelle 'image', change 'attachment' par 'image' ci-dessous
            attachment=attachment
        )

        TechNotification.objects.create(
            sender=request.user,
            receiver=other,
            notif_type="message",
            message=f"Nouveau message de {request.user.username}"
        )

    return redirect("techfeed:conversation", user_id=other.id)


# techfeed/views.py

@login_required
def delete_group_message(request, message_id):
    msg = get_object_or_404(TechMessage, id=message_id)
    group_id = msg.group.id # On garde l'ID pour la redirection

    # Sécurité : Seul l'expéditeur OU un admin du groupe peut supprimer
    is_sender = (msg.sender == request.user)
    is_group_admin = (request.user in msg.group.admins.all())

    if is_sender or is_group_admin:
        # Si le message a une pièce jointe (image/vidéo), on supprime le fichier du disque
        if msg.attachment:
            msg.attachment.delete(save=False)

        msg.delete()

    return redirect('techfeed:group_chat', group_id=group_id)



@login_required
def leave_group(request, group_id):
    group = get_object_or_404(TechGroup, id=group_id)

    if request.user in group.members.all():
        group.members.remove(request.user)

        # Si c'était un admin, on le retire aussi des admins
        if request.user in group.admins.all():
            group.admins.remove(request.user)

        # Optionnel : Si le groupe est vide, on le supprime
        if group.members.count() == 0:
            group.delete()

    return redirect('techfeed:messages')

#Live
# techfeed/views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@login_required
@csrf_exempt # Pour faciliter l'appel JS
def update_live_status(request):
    if request.method == "POST":
        data = json.loads(request.body)
        status = data.get('status') # 'start' ou 'stop'
        room_name = data.get('room_name')

        profile = request.user.profile

        if status == 'start':
            profile.is_live = True # Assure-toi d'avoir ce champ dans ton modèle Profile
            profile.save()

            # Récupérer tous les abonnés
            followers = User.objects.filter(suivis__following=request.user)

            # Créer une notification pour chaque abonné
            notifications = []
            for follower in followers:
                notifications.append(TechNotification(
                    sender=request.user,
                    receiver=follower,
                    notif_type="live", # Nouveau type
                    message=f"🔴 {request.user.username} a lancé un Live ! Rejoins vite.",
                    # On stocke le lien de la salle dans un champ ou on le générera
                    video=None # Pas de vidéo liée, c'est un live
                ))

            # Bulk create pour la performance (évite 1000 requêtes si 1000 abonnés)
            TechNotification.objects.bulk_create(notifications)

            return JsonResponse({'success': True, 'message': 'Live démarré, abonnés notifiés.'})

        elif status == 'stop':
            profile.is_live = False
            profile.save()
            return JsonResponse({'success': True, 'message': 'Live arrêté.'})

    return JsonResponse({'success': False})



@login_required
def join_live(request, username):
    # On récupère l'utilisateur qui est en train de faire le live (l'Hôte)
    host_user = get_object_or_404(User, username=username)

    # On recrée le nom de la salle exactement comme dans l'uploader
    # (Note : .replace(' ', '') est important pour éviter les bugs d'URL Jitsi)
    room_name = f"FounatekLive_{username.replace(' ', '')}"

    # ICI : On appelle le nouveau template "live_room.html"
    return render(request, "techfeed/live_room.html", {
        "host_user": host_user,
        "room_name": room_name
    })




@login_required
@csrf_exempt
def send_live_command(request):
    if request.method == "POST":
        data = json.loads(request.body)
        command_text = data.get('command')

        # 1. Récupérer les relais DE L'UTILISATEUR QUI EST EN LIVE (l'hôte)
        # Attention : Ici on suppose que c'est le proprio du live qui reçoit l'ordre
        # Si c'est un spectateur qui tape, il faut savoir sur QUEL live il est.
        # Pour simplifier ici, on va dire que l'action se passe chez l'utilisateur connecté (si tu testes toi-même)
        # Dans un vrai live, il faudrait passer l'ID de l'hôte.

        my_relais = Relais.objects.filter(user=request.user).values('num', 'nom')

        # 2. Appel à Gemini
        analysis = analyze_iot_command(command_text, list(my_relais))

        response_data = {
            "success": False,
            "message": analysis.get('message', "Commande non comprise"),
            "ai_safe": analysis.get('safe')
        }

        # 3. Exécution
        if analysis.get('safe') and analysis.get('relais_num') is not None:
            try:
                target_num = analysis['relais_num']
                relais = Relais.objects.get(user=request.user, num=target_num)

                action = analysis.get('action')
                if action == 'on':
                    relais.etat = True
                elif action == 'off':
                    relais.etat = False
                elif action == 'toggle':
                    relais.etat = not relais.etat

                relais.save()

                response_data["success"] = True
                response_data["message"] = f"⚡ Action : {relais.nom} est maintenant {'ON' if relais.etat else 'OFF'}"

            except Relais.DoesNotExist:
                response_data["message"] = "Appareil introuvable."

        return JsonResponse(response_data)

    return JsonResponse({'success': False})




#Vue pour live

@login_required
def live_home(request):
    lives = LiveSession.objects.filter(is_live=True)
    return render(request, "techfeed/live_home.html", {"lives": lives})

@login_required
def start_live(request):
    room_name = f"live_{request.user.id}_{int(time.time())}"

    live = LiveSession.objects.create(
        host=request.user,
        title=request.POST.get("title", ""),
        room_name=room_name,
        is_live=True
    )

    return redirect("techfeed:watch_live", room_name=room_name)


@login_required
def watch_live(request, room_name):
    session = get_object_or_404(LiveSession, room_name=room_name)
    messages = LiveChatMessage.objects.filter(session=session).order_by("timestamp")

    is_host = (request.user == session.host)

    return render(request, "techfeed/live_watch.html", {
        "session": session,
        "messages": messages,
        "is_host": is_host,
        "LIVEKIT_URL": settings.LIVEKIT_URL,
    })




@login_required
def invite_user(request, room_name, user_id):
    session = get_object_or_404(LiveSession, room_name=room_name)
    invited = get_object_or_404(User, id=user_id)

    LiveInvite.objects.create(
        session=session,
        inviter=request.user,
        invited=invited
    )

    # Notification
    LiveNotification.objects.create(
        user=invited,
        session=session,
        message=f"{request.user.username} t'invite à monter dans son live."
    )

    return redirect("techfeed:watch_live", room_name=room_name)

@login_required
def accept_invite(request, room_name):
    session = get_object_or_404(LiveSession, room_name=room_name)

    invite = LiveInvite.objects.filter(
        session=session, invited=request.user, accepted=False
    ).first()

    if invite:
        invite.accepted = True
        invite.save()

    return redirect("techfeed:watch_live", room_name=room_name)




import jwt
import time
from django.conf import settings
from django.http import JsonResponse

@login_required
def livekit_token(request, room_name):
    user = request.user
    api_key = settings.LIVEKIT_API_KEY
    secret = settings.LIVEKIT_SECRET_KEY

    now = int(time.time())

    payload = {
        "sub": user.username,
        "name": user.username,
        "iss": api_key,
        "nbf": now - 10,
        "exp": now + 60 * 60,  # token valide 1h
        "video": {
            "roomCreate": True,
            "roomJoin": True,
            "room": room_name
        }
    }

    token = jwt.encode(payload, secret, algorithm="HS256")

    return JsonResponse({"token": token})






def _can_access_call(user, call: CallSession) -> bool:
    return user.is_authenticated and (user == call.caller or user == call.receiver)


@login_required
@require_POST
def start_call(request, user_id):
    """
    A appelle B depuis la conversation.
    - crée une CallSession
    - envoie une notification
    - redirige vers call_wait (audio ou vidéo)
    """
    other = get_object_or_404(User, id=user_id)

    if other == request.user:
        return HttpResponseForbidden("Impossible de vous appeler vous-même.")

    # 🔁 type d'appel (par défaut vidéo)
    call_type = request.POST.get("call_type", "video")  # "audio" | "video"

    # Room unique
    room_name = f"call_{min(request.user.id, other.id)}_{max(request.user.id, other.id)}_{int(time.time())}"

    call = CallSession.objects.create(
        caller=request.user,
        receiver=other,
        room_name=room_name,
        accepted=False,
        ended=False,
        call_type=call_type,   # ✅ IMPORTANT
    )

    # 📩 Notification adaptée
    TechNotification.objects.create(
        sender=request.user,
        receiver=other,
        notif_type="call",
        message=(
            f"📞 Appel audio entrant de @{request.user.username}"
            if call_type == "audio"
            else f"📹 Appel vidéo entrant de @{request.user.username}"
        ),
        call_session=call
    )

    # ✅ TOUJOURS call_wait
    return redirect("techfeed:call_wait", room_name=room_name)



@login_required
def call_wait(request, room_name):
    """
    Page côté appelant : “en attente…”
    On poll /call/status/<room_name>/ pour savoir si accepté/refusé.
    """
    call = get_object_or_404(CallSession, room_name=room_name)

    if not _can_access_call(request.user, call):
        return HttpResponseForbidden("Accès interdit.")

    # Seul l'appelant doit rester ici
    if request.user != call.caller:
        return redirect("techfeed:call_incoming", room_name=room_name)

    return render(request, "techfeed/call_wait.html", {"call": call})


@login_required
def call_status(request, room_name):
    """
    Endpoint JSON pour polling (attente).
    """
    call = get_object_or_404(CallSession, room_name=room_name)

    if not _can_access_call(request.user, call):
        return JsonResponse({"error": "forbidden"}, status=403)

    return JsonResponse({
        "accepted": call.accepted,
        "ended": call.ended,
        "caller": call.caller.username,
        "receiver": call.receiver.username,
    })


@login_required
def call_incoming(request, room_name):
    """
    Page côté receveur : accepter / refuser.
    (Optionnelle si tu veux tout faire depuis la page notifications)
    """
    call = get_object_or_404(CallSession, room_name=room_name)

    if not _can_access_call(request.user, call):
        return HttpResponseForbidden("Accès interdit.")

    if request.user != call.receiver:
        return redirect("techfeed:call_wait", room_name=room_name)

    return render(request, "techfeed/call_incoming.html", {"call": call})


@login_required
@require_POST
def accept_call(request, room_name):
    call = get_object_or_404(CallSession, room_name=room_name)

    if request.user != call.receiver:
        return HttpResponseForbidden("Seul le receveur peut accepter.")

    if call.ended:
        return HttpResponseForbidden("Appel terminé.")

    call.accepted = True
    call.save(update_fields=["accepted"])

    return redirect("techfeed:call_room", room_name=room_name)


@login_required
@require_POST
def refuse_call(request, room_name):
    call = get_object_or_404(CallSession, room_name=room_name)

    if request.user != call.receiver:
        return HttpResponseForbidden("Seul le receveur peut refuser.")

    call.ended = True
    call.save(update_fields=["ended"])

    # Optionnel : prévenir l'appelant via notif
    TechNotification.objects.create(
        sender=request.user,
        receiver=call.caller,
        notif_type="call",
        message=f"❌ @{request.user.username} a refusé l’appel.",
        call_session=call
    )

    return redirect("techfeed:feed")


@login_required
def call_room(request, room_name):
    """
    Room d'appel audio ou vidéo selon call_type.
    """
    call = get_object_or_404(CallSession, room_name=room_name)

    if not _can_access_call(request.user, call):
        return HttpResponseForbidden("Accès interdit.")

    if call.ended:
        return HttpResponseForbidden("Appel terminé.")

    if not call.accepted:
        if request.user == call.caller:
            return redirect("techfeed:call_wait", room_name=room_name)
        return redirect("techfeed:call_incoming", room_name=room_name)

    # 🎯 Choix du template selon le type
    template = (
        "techfeed/call_room_audio.html"
        if call.call_type == "audio"
        else "techfeed/call_room.html"
    )

    return render(request, template, {
        "call": call,
        "LIVEKIT_URL": settings.LIVEKIT_URL,
    })



@login_required
@require_POST
def end_call(request, room_name):
    call = get_object_or_404(CallSession, room_name=room_name)

    if not _can_access_call(request.user, call):
        return JsonResponse({"error": "forbidden"}, status=403)

    call.ended = True
    call.save(update_fields=["ended"])

    return JsonResponse({"success": True})


@login_required
def call_livekit_token(request, room_name):
    """
    Token LiveKit sécurisé (seuls caller/receiver).
    """
    call = get_object_or_404(CallSession, room_name=room_name)

    if not _can_access_call(request.user, call):
        return JsonResponse({"error": "forbidden"}, status=403)

    if call.ended:
        return JsonResponse({"error": "ended"}, status=403)

    # On autorise join uniquement si accepté
    if not call.accepted:
        return JsonResponse({"error": "not_accepted"}, status=403)

    api_key = settings.LIVEKIT_API_KEY
    secret = settings.LIVEKIT_SECRET_KEY
    now = int(time.time())

    payload = {
        "sub": request.user.username,
        "name": request.user.username,
        "iss": api_key,
        "nbf": now - 10,
        "exp": now + 60 * 60,
        "video": {
            "room": room_name,
            "roomJoin": True,
            "roomCreate": False,   # ✅ pour l'appel 1–1, room déjà “logique”
        }
    }

    token = jwt.encode(payload, secret, algorithm="HS256")
    return JsonResponse({"token": token})



#vues groupe
@login_required
@require_POST
def start_group_audio_call(request, group_id):
    group = get_object_or_404(TechGroup, id=group_id)

    if request.user not in group.members.all():
        return HttpResponseForbidden("Accès interdit.")

    room_name = f"group_audio_{group.id}_{int(time.time())}"

    call = GroupCallSession.objects.create(
        group=group,
        room_name=room_name,
        started_by=request.user,
    )

    # 📩 notifier tous les membres (sauf initiateur)
    for member in group.members.exclude(id=request.user.id):
        TechNotification.objects.create(
            sender=request.user,
            receiver=member,
            notif_type="call",
            message=f"📞 Appel audio de groupe : {group.name}",
            group_call_session=call
        )

    return redirect("techfeed:group_call_room", room_name=room_name)


@login_required
def group_call_room(request, room_name):
    call = get_object_or_404(GroupCallSession, room_name=room_name)

    if request.user not in call.group.members.all():
        return HttpResponseForbidden("Accès interdit.")

    if call.ended:
        return HttpResponseForbidden("Appel terminé.")

    template = (
        "techfeed/group_call_room_video.html"
        if call.call_type == "video"
        else "techfeed/group_call_room.html"
    )

    return render(request, template, {
        "call": call,
        "LIVEKIT_URL": settings.LIVEKIT_URL,
    })




@login_required
def group_call_livekit_token(request, room_name):
    call = get_object_or_404(GroupCallSession, room_name=room_name)

    if call.ended:
        return JsonResponse({"error": "ended"}, status=403)

    if request.user not in call.group.members.all():
        return JsonResponse({"error": "forbidden"}, status=403)

    api_key = settings.LIVEKIT_API_KEY
    secret = settings.LIVEKIT_SECRET_KEY
    now = int(time.time())

    payload = {
        "sub": request.user.username,
        "name": request.user.username,
        "iss": api_key,
        "nbf": now - 10,
        "exp": now + 3600,
        "video": {
            "room": room_name,
            "roomJoin": True,
            "roomCreate": True,
        }
    }

    token = jwt.encode(payload, secret, algorithm="HS256")
    return JsonResponse({"token": token})


@login_required
@require_POST
def end_group_call(request, room_name):
    call = get_object_or_404(GroupCallSession, room_name=room_name)

    if request.user not in call.group.members.all():
        return JsonResponse({"error": "forbidden"}, status=403)

    call.ended = True
    call.save(update_fields=["ended"])

    return JsonResponse({"success": True})


@login_required
@require_POST
def start_group_live(request, group_id):
    group = get_object_or_404(TechGroup, id=group_id)

    if request.user not in group.admins.all():
        return HttpResponseForbidden("Seuls les admins peuvent lancer un live.")

    room_name = f"live_group_{group.id}_{int(time.time())}"

    live = LiveSession.objects.create(
        host=request.user,
        group=group,
        room_name=room_name,
        is_live=True
    )

    # 🔔 Notification aux membres
    for member in group.members.exclude(id=request.user.id):
        TechNotification.objects.create(
            sender=request.user,
            receiver=member,
            notif_type="live",
            message=f"📺 Live en cours dans {group.name}",
        )

    return redirect("techfeed:group_live_room", room_name=room_name)


@login_required
@require_POST
def start_group_video_call(request, group_id):
    group = get_object_or_404(TechGroup, id=group_id)

    if request.user not in group.members.all():
        return HttpResponseForbidden("Accès interdit.")

    room_name = f"group_video_{group.id}_{int(time.time())}"

    call = GroupCallSession.objects.create(
        group=group,
        room_name=room_name,
        started_by=request.user,
        call_type="video",
    )

    # 🔔 Notifications
    for member in group.members.exclude(id=request.user.id):
        TechNotification.objects.create(
            sender=request.user,
            receiver=member,
            notif_type="call",
            message=f"📹 Appel vidéo de groupe : {group.name}",
            group_call_session=call
        )

    return redirect("techfeed:group_call_room", room_name=room_name)


@login_required
def group_live_token(request, room_name):
    live = get_object_or_404(
        LiveSession,
        room_name=room_name,
        is_live=True
    )

    user = request.user
    now = int(time.time())

    is_host = (user == live.host)

    payload = {
        "sub": user.username,
        "name": user.username,
        "iss": settings.LIVEKIT_API_KEY,
        "nbf": now - 10,
        "exp": now + 60 * 60,

        "video": {
            "room": room_name,
            "roomJoin": True,

            # 👑 SEUL LE HOST PEUT PUBLIER
            "canPublish": is_host,
            "canPublishData": is_host,

            # 👥 TOUS PEUVENT REGARDER
            "canSubscribe": True,

            # ❌ PERSONNE NE CRÉE LA ROOM
            "roomCreate": False,
        }
    }

    token = jwt.encode(
        payload,
        settings.LIVEKIT_SECRET_KEY,
        algorithm="HS256"
    )

    return JsonResponse({
        "token": token,
        "role": "host" if is_host else "viewer"
    })



@login_required
def group_live_room(request, room_name):
    live = get_object_or_404(
        LiveSession,
        room_name=room_name,
        is_live=True
    )

    return render(request, "techfeed/group_live_room.html", {
        "live": live,
        "room_name": live.room_name,   # ✅ AJOUT CRITIQUE
        "group": live.group if hasattr(live, "group") else None,
        "LIVEKIT_URL": settings.LIVEKIT_URL,
    })

