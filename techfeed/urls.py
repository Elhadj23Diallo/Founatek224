from django.urls import path
from . import views

app_name = "techfeed"

urlpatterns = [
    path("", views.feed, name="feed"),
    path("video/<int:pk>/", views.video_detail, name="video_detail"),
    path("video/<int:pk>/like/", views.like_video, name="like_video"),
    path("video/<int:pk>/comment/", views.ajouter_commentaire, name="ajouter_commentaire"),
    path("uploader/", views.uploader_video, name="uploader_video"),
    path("api/upload/", views.api_upload_video, name="api_upload_video"),
    # nouvelles routes :
    path("video/delete/<int:pk>/", views.delete_video, name="delete_video"),
    path("video/edit/<int:pk>/", views.edit_video, name="edit_video"),
    path("profile/upload-avatar/", views.upload_avatar, name="upload_avatar"),
    path("profile/<str:username>/", views.profile_view, name="profile"),
    path("profile/<str:username>/followers/", views.profile_followers, name="profile_followers"),
    path("profile/<str:username>/following/", views.profile_following, name="profile_following"),
    path("toggle_follow/<int:user_id>/", views.toggle_follow, name="toggle_follow"),
    path("notifications/", views.notifications_view, name="notifications"),
    path("search/", views.search_view, name="search"),
    path("friends/", views.friends_view, name="friends"),
    path("messages/", views.messages_view, name="messages"),
    path("messages/<int:user_id>/", views.conversation_view, name="conversation"),
    path("messages/send/<int:user_id>/", views.send_message, name="send_message"),
    path("message/delete/<int:message_id>/", views.delete_message, name="delete_message"),
    # ... tes autres urls ...
    path("live/update/", views.update_live_status, name="update_live_status"),
    path("live/join/<str:username>/", views.join_live, name="join_live"),
    # Routes pour les Groupes
    path("group/<int:group_id>/", views.group_conversation_view, name="group_chat"),
    path("group/send/<int:group_id>/", views.send_group_message, name="send_group_message"),
    path("group/create/", views.create_group, name="create_group"),
    path("group/update/<int:group_id>/", views.update_group_settings, name="update_group_settings"),
    path("group/manage/<int:group_id>/<str:action>/<int:member_id>/", views.manage_group_member, name="manage_group_member"),
    path("group/message/delete/<int:message_id>/", views.delete_group_message, name="delete_group_message"),
    path("group/leave/<int:group_id>/", views.leave_group, name="leave_group"),
    path("live/command/", views.send_live_command, name="send_live_command"),
    #Routes pour live
    path("live/", views.live_home, name="live_home"),
    path("live/start/", views.start_live, name="start_live"),
    path("live/<str:room_name>/", views.watch_live, name="watch_live"),
    path("livekit/token/<str:room_name>/", views.livekit_token, name="livekit_token"),
    # ... tes routes existantes ...

    # ✅ CALL 1–1
    path("call/start/<int:user_id>/", views.start_call, name="start_call"),
    path("call/wait/<str:room_name>/", views.call_wait, name="call_wait"),
    path("call/status/<str:room_name>/", views.call_status, name="call_status"),

    path("call/incoming/<str:room_name>/", views.call_incoming, name="call_incoming"),
    path("call/accept/<str:room_name>/", views.accept_call, name="accept_call"),
    path("call/refuse/<str:room_name>/", views.refuse_call, name="refuse_call"),

    path("call/<str:room_name>/", views.call_room, name="call_room"),
    path("call/end/<str:room_name>/", views.end_call, name="end_call"),

    path("call/token/<str:room_name>/", views.call_livekit_token, name="call_livekit_token"),
    # urls.py

    path(
        "group/<int:group_id>/call/audio/start/",
        views.start_group_audio_call,
        name="start_group_audio_call"
    ),

    path(
        "group/call/<str:room_name>/",
        views.group_call_room,
        name="group_call_room"
    ),

    path(
        "group/call/<str:room_name>/token/",
        views.group_call_livekit_token,
        name="group_call_livekit_token"
    ),

    path(
        "group/call/<str:room_name>/end/",
        views.end_group_call,
        name="end_group_call"
    ),
    # ===============================
    # 📺 LIVE DE GROUPE
    # ===============================
    path(
        "group/live/<str:room_name>/",
        views.group_live_room,
        name="group_live_room"
    ),

    path(
    "group/<int:group_id>/live/start/",
    views.start_group_live,
    name="start_group_live"
    ),

    path(
        "group/live/token/<str:room_name>/",
        views.group_live_token,
        name="group_live_token"
    ),
    path(
    "group/<int:group_id>/call/video/start/",
    views.start_group_video_call,
    name="start_group_video_call"
    ),

        # techfeed/urls.py

    path(
        "notifications/delete/<int:notif_id>/",
        views.delete_notification,
        name="delete_notification"
    ),

    path(
    "commentaire/<int:comment_id>/repondre/",
    views.repondre_commentaire,
    name="repondre_commentaire"
   ),
]
