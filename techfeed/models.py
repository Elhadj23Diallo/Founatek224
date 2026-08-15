from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    """
    Profil utilisateur – stocke un avatar, une bio et des tags personnels.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(blank=True)
    tags = models.CharField(max_length=255, blank=True)  # ex. "#IoT,#Robotique"

    # ✅ AJOUTÉ : Indispensable pour ton système de Live
    is_live = models.BooleanField(default=False)

    def __str__(self):
        return f"Profil de {self.user.username}"




class TechGroup(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    # CHANGEMENT ICI : ManyToMany pour avoir plusieurs admins
    admins = models.ManyToManyField(User, related_name='admin_groups')

    members = models.ManyToManyField(User, related_name='tech_groups')
    avatar = models.ImageField(upload_to='group_avatars/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class GroupCallSession(models.Model):
    CALL_TYPES = (
        ("audio", "Audio"),
        ("video", "Vidéo"),
    )

    group = models.ForeignKey(
        TechGroup,
        on_delete=models.CASCADE,
        related_name="group_calls"
    )

    room_name = models.CharField(max_length=255, unique=True)

    call_type = models.CharField(
        max_length=10,
        choices=CALL_TYPES,
        default="audio"
    )

    started_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="group_calls_started"
    )

    ended = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)




class TechNotification(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    notif_type = models.CharField(max_length=50, blank=True)  # 'like', 'follow', 'comment', 'live', 'message', 'call'

    video = models.ForeignKey('TechVideo', on_delete=models.CASCADE, null=True, blank=True)

    # ✅ AJOUT : pour les appels 1–1
    call_session = models.ForeignKey(
        "CallSession",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications"
    )
    # ✅ AJOUT POUR GROUPE
    group_call_session = models.ForeignKey(
        "GroupCallSession",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.sender.username} → {self.receiver.username} ({self.message})"


class TechCategorie(models.Model):
    nom = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nom


class TechVideo(models.Model):
    auteur = models.ForeignKey(User, on_delete=models.CASCADE, related_name="videos_tech")
    video = models.FileField(upload_to="techfeed/videos/")
    description = models.TextField(blank=True)
    tags = models.CharField(max_length=255, blank=True)
    categorie = models.ForeignKey(TechCategorie, on_delete=models.SET_NULL, null=True, blank=True, related_name="videos")
    miniature = models.ImageField(upload_to="techfeed/thumbnails/", blank=True, null=True)
    vues = models.PositiveIntegerField(default=0)
    date_pub = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Vidéo de {self.auteur.username} - {self.date_pub.strftime('%Y-%m-%d')}"


class TechVideoLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    video = models.ForeignKey(TechVideo, on_delete=models.CASCADE, related_name='like_entries')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'video')

    def __str__(self):
        return f"{self.user.username} liked video {self.video.id}"


class TechCommentaire(models.Model):
    video = models.ForeignKey(
        TechVideo,
        on_delete=models.CASCADE,
        related_name="commentaires"
    )

    auteur = models.ForeignKey(User, on_delete=models.CASCADE)

    contenu = models.TextField()

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reponses"
    )

    date_pub = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date_pub"]

    def __str__(self):
        return f"{self.auteur.username}: {self.contenu[:30]}"



class TechFollow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name="suivis")
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name="abonnés")
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')

    def __str__(self):
        return f"{self.follower.username} suit {self.following.username}"




class TechMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')

    # ✅ CORRIGÉ : null=True est OBLIGATOIRE ici pour les groupes !
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages', null=True, blank=True)

    group = models.ForeignKey(TechGroup, on_delete=models.CASCADE, related_name='group_messages', null=True, blank=True)

    content = models.TextField(blank=True, null=True)
    attachment = models.FileField(upload_to='chat_attachments/', blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        display_content = self.content[:20] if self.content else "[Fichier]"

        # ✅ CORRIGÉ : Gestion de l'affichage si receiver est None (Groupe)
        if self.group:
            return f"{self.sender.username} (Groupe: {self.group.name}): {display_content}"
        elif self.receiver:
            return f"{self.sender.username} → {self.receiver.username}: {display_content}"
        else:
            return f"{self.sender.username}: {display_content}"



class LiveSession(models.Model):
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name="live_host")
    group = models.ForeignKey(
        TechGroup,
        on_delete=models.CASCADE,
        related_name="live_sessions",
        null=True,
        blank=True
    )

    title = models.CharField(max_length=255, blank=True)
    is_live = models.BooleanField(default=False)

    room_name = models.CharField(max_length=255, unique=True)

    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Live {self.title or self.room_name}"



class LiveInvite(models.Model):
    session = models.ForeignKey(LiveSession, on_delete=models.CASCADE)
    inviter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="invite_sent")
    invited = models.ForeignKey(User, on_delete=models.CASCADE, related_name="invite_received")
    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class LiveChatMessage(models.Model):
    session = models.ForeignKey(LiveSession, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

class LiveNotification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session = models.ForeignKey(LiveSession, on_delete=models.CASCADE)
    sent_at = models.DateTimeField(auto_now_add=True)
    message = models.CharField(max_length=255)


class CallSession(models.Model):
    CALL_TYPES = (
        ("audio", "Audio"),
        ("video", "Vidéo"),
    )

    caller = models.ForeignKey(User, on_delete=models.CASCADE, related_name="calls_made")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="calls_received")
    room_name = models.CharField(max_length=255, unique=True)

    call_type = models.CharField(
        max_length=10,
        choices=CALL_TYPES,
        default="video"
    )

    accepted = models.BooleanField(default=False)
    ended = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.call_type.upper()} {self.caller.username} → {self.receiver.username}"

