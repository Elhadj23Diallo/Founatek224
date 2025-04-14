from django.urls import path
from .import views


urlpatterns = [
    path('login/', views.login_page, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('compteur/', views.CompteurDataAPIView.as_view(), name='compteur-data'),
    path('home/', views.home, name='accueil'),  # Route pour la page d'accueil
    path('led/', views.led_status),
    path('dht-data/', views.led_control, name='dht-data/'),
    path('irrigation/', views.irrigation_auto, name='irrigation_auto'),
    path('poubelle/', views.poubelle_intelligente, name='poubelle_intelligente'),
    path('surveillance/', views.systeme_surveillance, name='surveillance'),
    path('upload/', views.ImageUploadView.as_view(), name='upload_image'),
    path('comptage/', views.ComptageAPIView.as_view(), name='comptage'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('initCompteur/', views.initCompteur, name='initCompteur'),
    path('toggle/relais/<int:relais_num>/', views.toggle_relais, name='toggle_relais'),
    path('control_relais/', views.control_relais, name='control_relais'),
    path('soil-data/', views.soil_data, name='soil_data'),
    path('soil_data/', views.display_soil_data, name='soil_data'),
    path('get_latest_image/', views.get_latest_image, name='get_latest_image'),
]
