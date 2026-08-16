from django.urls import path
from django.contrib.auth import views as auth_views
from rest_framework.authtoken.views import obtain_auth_token
from . import api_views, views, web_views
from django.contrib.auth.views import LoginView, LogoutView


urlpatterns = [
    path('api/token-auth/', obtain_auth_token, name='token_auth'),
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
    # Mobile-first API endpoints
    path('api/mobile/relays/', api_views.mobile_relay_list, name='mobile_relay_list'),
    path('api/mobile/relays/<int:num>/', api_views.mobile_relay_detail, name='mobile_relay_detail'),
    path('api/mobile/soil-data/', api_views.mobile_soil_data, name='mobile_soil_data'),
    path('api/mobile/sensor-ingest/', api_views.mobile_sensor_ingest, name='mobile_sensor_ingest'),
    path('api/mobile/upload-image/', api_views.MobileImageUploadAPIView.as_view(), name='mobile_image_upload'),
    path('api/mobile/air-quality-summary/', api_views.mobile_air_quality_summary, name='mobile_air_quality_summary'),
    path('api/mobile/alerts/', api_views.mobile_alerts, name='mobile_alerts'),
    path('api/mobile/alerts/archive/', api_views.mobile_alerts_archive, name='mobile_alerts_archive'),
    path('api/mobile/alerts/delete/', api_views.mobile_alerts_delete, name='mobile_alerts_delete'),
    path('api/mobile/access-check/', api_views.mobile_access_check, name='mobile_access_check'),
    path('api/mobile/dht/', api_views.mobile_dht_data, name='mobile_dht_data'),
    path('api/mobile/gas/', api_views.mobile_gas_data, name='mobile_gas_data'),
    path('api/mobile/ntc/', api_views.mobile_ntc_data, name='mobile_ntc_data'),
    path('api/mobile/surveillance/', api_views.mobile_surveillance, name='mobile_surveillance'),
    path('api/mobile/access-logs/', api_views.mobile_access_logs, name='mobile_access_logs'),
    path('api/mobile/chatbot/', api_views.mobile_chatbot, name='mobile_chatbot'),
    path('api/mobile/devices/', api_views.mobile_devices, name='mobile_devices'),
    path('api/mobile/stats/', api_views.mobile_stats, name='mobile_stats'),
    path('api/mobile/rules/', api_views.mobile_rules, name='mobile_rules'),
    path('api/mobile/action-logs/', api_views.mobile_action_logs, name='mobile_action_logs'),
    path('api/mobile/led-color/', api_views.mobile_led_color, name='mobile_led_color'),
    path('api/mobile/comptage/', api_views.mobile_comptage, name='mobile_comptage'),
    path('api/mobile/relays/create/', api_views.mobile_relay_create, name='mobile_relay_create'),
    path('api/mobile/relays/<int:num>/delete/', api_views.mobile_relay_delete, name='mobile_relay_delete'),
    path('api/mobile/relays/<int:num>/rename/', api_views.mobile_relay_rename, name='mobile_relay_rename'),
    path('api/mobile/comptage/list/', api_views.mobile_comptage_list, name='mobile_comptage_list'),
    path('api/mobile/access-logs/full/', api_views.mobile_access_logs_full, name='mobile_access_logs_full'),
    path('api/mobile/profile/', api_views.mobile_profile, name='mobile_profile'),
    path('home/', web_views.home, name='home'),  # Route pour la page d'accueil
    path('api/led/', views.led_status),
    path('api/dht-data/', web_views.led_control, name='dht-data'),
    path('irrigation/', web_views.irrigation_auto, name='irrigation_auto'),
    path('poubelle/', web_views.poubelle_intelligente, name='poubelle_intelligente'),
    path('api/compteur/', views.ComptageAPIView.as_view(), name='compteur-data'),
    path('dashboard/', web_views.dashboard, name='dashboard'),
    path('api/initCompteur/', web_views.initCompteur, name='initCompteur'),
    path("dashboard/live/", web_views.comptage_live, name="comptage-live"),
    path('tableau_bord_univ/', views.dashboard_univers, name='tableau_bord_univ'),
    path('menu/', web_views.menu_page, name='menu_page'),


    #Relais
    path("api/relais/<int:num>/get/", views.get_relais_etat, name="get_relais_etat"),
    path("relais/", web_views.afficher_relais, name="afficher_relais"),
    path("relais/<int:num>/toggle/", web_views.toggle_relais, name="toggle_relais"),
    path("api/relais/get/", views.get_all_relais_etats, name="get_all_relais_etats"),

    path('soil-data/', views.soil_data, name='soil_data'),
    path('soil_data/', web_views.display_soil_data, name='soil_data'),
    path('gas-data/', web_views.gas_data_view, name='gas_data'),
    path('creer_relais/', web_views.control_relais, name='control_relais'),
    path('NTCdata/', web_views.view_ntc_data, name='ntc_data'),

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

    # 🌍 AIR QUALITY DASHBOARD - nouvelles routes
    path("air-quality/", views.air_quality_dashboard, name="air_quality_dashboard"),
    path("api/air-quality/data/", views.air_quality_data_api, name="air_quality_data_api"),

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
    path('alert/read/<int:alert_id>/', views.mark_alert_read, name='mark_alert_read'),
    path('export/air-data/<int:device_id>/', views.export_air_founatek_nexus_excel, name='export_air_founatek_nexus_excel'),

    # ── Formateur (iot) ───────────────────────────────────────────────────────
    path('api/mobile/formateur/', api_views.mobile_formateur_dashboard, name='mobile_formateur_dashboard'),
    path('api/mobile/formateur/parcours/create/', api_views.mobile_formateur_create_parcours, name='mobile_formateur_create_parcours'),
    path('api/mobile/formateur/parcours/<int:parcours_id>/', api_views.mobile_formateur_edit_parcours, name='mobile_formateur_edit_parcours'),
    path('api/mobile/formateur/parcours/<int:parcours_id>/lecons/create/', api_views.mobile_formateur_create_lecon, name='mobile_formateur_create_lecon'),
    path('api/mobile/formateur/lecons/<int:lecon_id>/blocs/create/', api_views.mobile_formateur_create_bloc, name='mobile_formateur_create_bloc'),
    path('api/mobile/formateur/lecons/<int:lecon_id>/quiz/create/', api_views.mobile_formateur_create_quiz, name='mobile_formateur_create_quiz'),
    path('api/mobile/formateur/lecons/<int:lecon_id>/detail/', api_views.mobile_formateur_lecon_detail, name='mobile_formateur_lecon_detail'),
    path('api/mobile/formateur/blocs/<int:bloc_id>/delete/', api_views.mobile_formateur_delete_bloc, name='mobile_formateur_delete_bloc'),
    path('api/mobile/formateur/quiz/<int:quiz_id>/delete/', api_views.mobile_formateur_delete_quiz, name='mobile_formateur_delete_quiz'),
    path('api/mobile/formateur/parcours/<int:parcours_id>/projects/', api_views.mobile_formateur_projects, name='mobile_formateur_projects'),
    path('api/mobile/formateur/projects/<int:project_id>/delete/', api_views.mobile_formateur_delete_project, name='mobile_formateur_delete_project'),
    path('api/mobile/formateur/progressions/', api_views.mobile_formateur_progressions, name='mobile_formateur_progressions'),

    # ── Education (iot) ────────────────────────────────────────────────────────
    path('api/mobile/education/parcours/', api_views.mobile_education_parcours, name='mobile_education_parcours'),
    path('api/mobile/education/parcours/<int:parcours_id>/lecons/', api_views.mobile_education_lecons, name='mobile_education_lecons'),
    path('api/mobile/education/parcours/<int:parcours_id>/projects/', api_views.mobile_education_projects, name='mobile_education_projects'),
    path('api/mobile/education/lecons/<int:lecon_id>/quiz/', api_views.mobile_education_quiz, name='mobile_education_quiz'),
    path('api/mobile/education/lecons/<int:lecon_id>/submit/', api_views.mobile_education_submit_quiz, name='mobile_education_submit_quiz'),
    path('api/mobile/education/certificats/', api_views.mobile_education_certificats, name='mobile_education_certificats'),

    # ── Monétisation ───────────────────────────────────────────────────────────
    path('api/mobile/monetisation/', api_views.mobile_monetisation_dashboard, name='mobile_monetisation_dashboard'),
    path('api/mobile/monetisation/recharge/', api_views.mobile_monetisation_recharge, name='mobile_monetisation_recharge'),
    path('api/mobile/monetisation/upgrade/', api_views.mobile_monetisation_upgrade, name='mobile_monetisation_upgrade'),
    path('api/mobile/monetisation/referral/', api_views.mobile_monetisation_referral, name='mobile_monetisation_referral'),
    path('api/mobile/monetisation/convert/', api_views.mobile_monetisation_convert, name='mobile_monetisation_convert'),
    path('api/mobile/monetisation/transactions/', api_views.mobile_monetisation_transactions, name='mobile_monetisation_transactions'),
    path('api/mobile/monetisation/paypal/create-order/', api_views.mobile_monetisation_paypal_create_order, name='mobile_monetisation_paypal_create_order'),
    path('api/mobile/monetisation/paypal/capture-order/', api_views.mobile_monetisation_paypal_capture_order, name='mobile_monetisation_paypal_capture_order'),

    # ── Transparence Produit ───────────────────────────────────────────────────
    path('api/mobile/transparence/company/', api_views.mobile_transparence_company, name='mobile_transparence_company'),
    path('api/mobile/transparence/products/', api_views.mobile_transparence_products, name='mobile_transparence_products'),
    path('api/mobile/transparence/products/create/', api_views.mobile_transparence_create_product, name='mobile_transparence_create_product'),
    path('api/mobile/transparence/products/<int:product_id>/pricing/', api_views.mobile_transparence_update_pricing, name='mobile_transparence_update_pricing'),
    path('api/mobile/transparence/products/<int:product_id>/image/', api_views.mobile_transparence_update_product_image, name='mobile_transparence_update_product_image'),
    path('api/mobile/transparence/products/<int:product_id>/edit/', api_views.mobile_transparence_update_product, name='mobile_transparence_update_product'),
    path('api/mobile/transparence/products/<int:product_id>/qr/', api_views.mobile_transparence_download_qr, name='mobile_transparence_download_qr'),
    path('api/mobile/transparence/qr-labels/pdf/', api_views.mobile_transparence_qr_labels_pdf, name='mobile_transparence_qr_labels_pdf'),
    path('api/mobile/transparence/scan/<str:uuid>/', api_views.mobile_transparence_scan, name='mobile_transparence_scan'),
    path('api/mobile/transparence/sales/create/', api_views.mobile_transparence_create_sale, name='mobile_transparence_create_sale'),

    # ── Qualité de l'air (multi-villes, prévision, alertes) ────────────────────
    path('api/mobile/air/map/', api_views.mobile_air_map, name='mobile_air_map'),
    path('api/mobile/air/city/<str:city>/', api_views.mobile_air_city_latest, name='mobile_air_city_latest'),
    path('api/mobile/air/forecast/', api_views.mobile_air_forecast, name='mobile_air_forecast'),
    path('api/mobile/air/alert-now/<str:city>/', api_views.mobile_air_alert_now, name='mobile_air_alert_now'),

    # ── Irrigation ML ────────────────────────────────────────────────────────
    path('api/mobile/irrigation/predict/', api_views.mobile_irrigation_prediction, name='mobile_irrigation_prediction'),

    # ── Exports Excel ────────────────────────────────────────────────────────
    path('api/mobile/export/excel/', api_views.mobile_export_data_excel, name='mobile_export_data_excel'),

    # ── Archives de surveillance ─────────────────────────────────────────────
    path('api/mobile/surveillance/archive/', api_views.mobile_surveillance_archive, name='mobile_surveillance_archive'),
    path('api/mobile/surveillance/archive/zip/', api_views.mobile_surveillance_download_zip, name='mobile_surveillance_download_zip'),

    # ── Dashboard "univers" + alertes par capteur ───────────────────────────
    path('api/mobile/univers/', api_views.mobile_dashboard_univers, name='mobile_dashboard_univers'),
    path('api/mobile/alerts/sensor/<str:sensor>/graph/', api_views.mobile_alert_graph_data, name='mobile_alert_graph_data'),
    path('api/mobile/alerts/sensor/<str:sensor>/', api_views.mobile_alerts_by_sensor, name='mobile_alerts_by_sensor'),
]
