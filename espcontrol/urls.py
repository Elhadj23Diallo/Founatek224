from django.urls import path
from django.contrib.auth import views as auth_views
from .import views
from django.contrib.auth.views import LoginView, LogoutView


urlpatterns = [
    path('', LoginView.as_view(template_name='espcontrol/login.html'), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    # Changement de mot de passe pour utilisateur connecté
    path('password_change/', auth_views.PasswordChangeView.as_view(template_name='registration/password_change.html'), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='registration/password_change_done.html'), name='password_change_done'),

    # Réinitialisation mot de passe (oublié)
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),
    path('compteur/', views.CompteurDataAPIView.as_view(), name='compteur-data'),
    path('home/', views.home, name='home'),  # Route pour la page d'accueil
    path('api/led/', views.led_status),
    path('api/dht-data/', views.led_control, name='dht-data'),
    path('irrigation/', views.irrigation_auto, name='irrigation_auto'),
    path('poubelle/', views.poubelle_intelligente, name='poubelle_intelligente'),
    path('api/compteur/', views.ComptageAPIView.as_view(), name='compteur-data'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('api/initCompteur/', views.initCompteur, name='initCompteur'),
    path("dashboard/live/", views.comptage_live, name="comptage-live"),
    path('tableau_bord_univ/', views.dashboard_univers, name='tableau_bord_univ'),
    path('menu/', views.menu_page, name='menu_page'),


    #Relais
    path("api/relais/<int:num>/get/", views.get_relais_etat, name="get_relais_etat"),
    path("relais/", views.afficher_relais, name="afficher_relais"),
    path("relais/<int:num>/toggle/", views.toggle_relais, name="toggle_relais"),
    path("api/relais/get/", views.get_all_relais_etats, name="get_all_relais_etats"),

    path('soil-data/', views.soil_data, name='soil_data'),
    path('soil_data/', views.display_soil_data, name='soil_data'),
    path('gas-data/', views.gas_data_view, name='gas_data'),
    path('creer_relais/', views.control_relais, name='control_relais'),
    path('NTCdata/', views.view_ntc_data, name='ntc_data'),

    #Systeme de controle de l'atmosphere
    path('api/sensor/', views.receive_sensor_data, name="sensor"),
    path('api/sensor_ntc/', views.receive_sensor_NTC, name="sensor"),
    path("export-excel/", views.export_excel, name="export_excel"),
    path("export-gas-excel/", views.export_gas_excel, name="export_gas_excel"),
    path('export_ntc_excel/', views.export_ntc_excel, name='export_ntc_excel'),


    path('api/led_color/', views.led_color_esp, name='led_color_esp'),
    path('chatbot/', views.chatbot_view, name='chatbot_view'),
    path("api/relais/<int:num>/set/", views.set_relais_etat, name="set_relais_etat"),

    #controle d'accès
    path("api/check_access/", views.check_access, name="check-access"),

    # Template côté admin pour visualiser les logs
    path("access-logs/", views.access_logs_view, name="access-logs"),
     # ESP32 API

    # AJAX dernière image
    path("surveillance/latest/<str:camera_id>/", views.get_latest_image, name="get_latest_image"),

    # Vue Dashboard HTML
    path("surveillance/", views.systeme_surveillance, name="surveillance"),

    # API Réception (ESP32)
    path("api/upload/", views.ImageUploadView.as_view(), name="upload_image"),

    # API JSON pour le JS du dashboard
    path("get_latest_frames/", views.get_latest_frames, name="get_latest_frames"),

    # API Flux RAM (Image binaire)
    path("stream/<str:camera_id>/", views.get_live_image_content, name="get_live_image_content"),
    # 👇 NOUVELLES ROUTES
    path("archive/", views.archive_gallery, name="archive_gallery"),
    path("archive/download_zip/", views.download_zip, name="download_zip"),
    #API MACHINE LEARNING
    path("irrigation/predict/", views.irrigation_prediction, name="irrigation_predict"),
    path("air/predict/", views.air_predict, name="air_predict"),
    path("dashboard/air/", views.air_dashboard, name="air_dashboard"),
    path("air/map/", views.air_map_data, name="air_map_data"),
    path("air/map/view/", views.air_map_view, name="air_map_view"),
    path("air/alerts/", views.air_alerts, name="air_alerts"),
    path("air/sim/reading/", views.latest_air_reading, name="air_sim_reading"),
    #similateur
    path("air/sim/latest/", views.air_sim_latest, name="air_sim_latest"),
    path("air/sim/tick/", views.air_sim_tick, name="air_sim_tick"),
    path("air/latest/<str:city>/", views.latest_air_data, name="air_latest"),
    path("air/alert/now/<str:city>/", views.air_alert_now, name="air_alert_now"),
    path("api/iot/ingest/", views.SensorIngestAPIView.as_view()),
    path('api/device/<int:device_id>/last10/', views.DeviceLast10APIView.as_view(), name='device_last10'),
    path("api/alerts/latest/", views.latest_alerts, name="latest_alerts"),
    #api pour l'historique des alerts
    path("api/alerts/sensor/<str:sensor>/", views.alerts_by_sensor, name="alerts_by_sensor"),
    #api pour les graphes alerts
    path("api/alerts/graph/<str:sensor>/", views.alert_graph_data, name="alert_graph"),



]
