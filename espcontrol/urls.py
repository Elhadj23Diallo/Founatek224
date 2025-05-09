from django.urls import path
from .import views
from django.contrib.auth.views import LoginView, LogoutView


urlpatterns = [
    path('login/', LoginView.as_view(template_name='espcontrol/login.html'), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('compteur/', views.CompteurDataAPIView.as_view(), name='compteur-data'),
    path('home/', views.home, name='home'),  # Route pour la page d'accueil
    path('api/led/', views.led_status),
    path('api/dht-data/', views.led_control, name='dht-data'),
    path('irrigation/', views.irrigation_auto, name='irrigation_auto'),
    path('poubelle/', views.poubelle_intelligente, name='poubelle_intelligente'),
    path('surveillance/', views.systeme_surveillance, name='surveillance'),
    path('api/upload/', views.ImageUploadView.as_view(), name='upload_image'),
    path('api/compteur/', views.ComptageAPIView.as_view(), name='compteur-data'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('api/initCompteur/', views.initCompteur, name='initCompteur'),
    path('api/relais/<int:relais_num>/toggle', views.toggle_relais, name='toggle_relais'),
    path('api/control_relais/', views.control_relais, name='control_relais'),
    path('soil-data/', views.soil_data, name='soil_data'),
    path('soil_data/', views.display_soil_data, name='soil_data'),
    path('get_latest_image/', views.get_latest_image, name='get_latest_image'),
    path('api/gas/', views.GasDataListCreateView.as_view(), name='gas-data-api'),
    path('gas-data/', views.gas_data_view, name='gas_data'),
]
