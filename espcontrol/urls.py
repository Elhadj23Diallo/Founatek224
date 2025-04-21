from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_page, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('compteur/', views.CompteurDataAPIView.as_view(), name='compteur-data'),
    path('home/', views.home, name='accueil'),  # Route pour la page d'accueil

    # Routes pour l'API
    path('api/led/', views.led_status),
    path('api/dht-data/', views.led_control, name='dht-data/'),
    path('api/irrigation/', views.irrigation_auto, name='irrigation_auto'),
    path('api/poubelle/', views.poubelle_intelligente, name='poubelle_intelligente'),
    path('api/surveillance/', views.systeme_surveillance, name='surveillance'),
    path('api/upload/', views.ImageUploadView, name='upload_image'),
    path('api/comptage/', views.ComptageAPIView, name='compte'),
    path('api/dashboard/', views.dashboard, name='dashboard'),
    path('api/initCompteur/', views.initCompteur, name='initCompteur'),
    path('api/toggle/relais/<int:relais_num>/', views.toggle_relais, name='toggle_relais'),
    path('api/control_relais/', views.control_relais, name='control_relais'),
    path('api/soil-data/', views.soil_data, name='soil_data'),
    path('api/soil_data/', views.display_soil_data, name='soil_data'),
    path('api/get_latest_image/', views.get_latest_image, name='get_latest_image'),

    # Routes supplémentaires non-API
    path('led/', views.led_status),
    path('dht-data/', views.led_control, name='dht-data/'),
    path('irrigation/', views.irrigation_auto, name='irrigation_auto'),
    path('poubelle/', views.poubelle_intelligente, name='poubelle_intelligente'),
    path('surveillance/', views.systeme_surveillance, name='surveillance'),
    path('upload/', views.ImageUploadView.as_view(), name='upload_image'),
    path('comptage/', views.ComptageAPIView.as_view(), name='compte'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('initCompteur/', views.initCompteur, name='initCompteur'),
    path('soil-data/', views.soil_data, name='soil_data'),
    path('soil_data/', views.display_soil_data, name='soil_data'),
    path('get_latest_image/', views.get_latest_image, name='get_latest_image'),
    path('relais/<int:relais_num>/status', views.relais_status, name='relais_status'),
    path('relais/<int:relais_num>/control', views.relais_control, name='relais_control'),

    # Route pour les données de gaz
    path('gas/', views.GasDataListCreateView.as_view(), name='gas-data-api'),
    path('gas-data/', views.gas_data_view, name='gas_data'),
]
