from django.urls import path
from .import views


urlpatterns = [
    path('', views.login_page, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('compteur/', views.CompteurDataAPIView.as_view(), name='compteur-data'),
    path('home/', views.home, name='accueil'),  # Route pour la page d'accueil
    path('led/', views.led_status),
    path('led-control/', views.led_control, name='led_control'),
    path('dht-data/', views.dht_data, name='dht_data'),
    path('irrigation/', views.irrigation_auto, name='irrigation_auto'),
    path('poubelle/', views.poubelle_intelligente, name='poubelle_intelligente'),
    path('surveillance/', views.systeme_surveillance, name='surveillance'),
    path('controle_appareils/', views.controle_appareils, name='controle_appareils'),
    path('Upload/', views.UploadedImage, name='waste_detect'),
    path('comptage/', views.ComptageAPIView.as_view(), name='comptage'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('initCompteur/', views.initCompteur, name='initCompteur'),
]
