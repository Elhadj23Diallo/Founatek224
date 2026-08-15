from django.urls import path
from . import views

app_name = 'oscilloscope'

urlpatterns = [
    # ── Vues HTML ──────────────────────────────────────────
    path('',                          views.oscilloscope_home,  name='home'),
    path('new/',                      views.create_session,     name='create'),
    path('<int:session_id>/',         views.oscilloscope_view,  name='view'),
    path('<int:session_id>/delete/',  views.delete_session,     name='delete'),

    # ── API — Générateur de signal ─────────────────────────
    path('api/generate/',             views.generate_signal,    name='generate'),

    # ── API — Ingestion ESP32 / Arduino ────────────────────
    path('api/ingest/',               views.IngestWaveformView.as_view(), name='ingest'),

    # ── API — Données temps réel ───────────────────────────
    path('api/<int:session_id>/ch<int:channel_num>/latest/',
         views.latest_waveform, name='latest'),

    # ── API — Mise à jour session / générateur ─────────────
    path('api/<int:session_id>/update/',
         views.update_session, name='update_session'),
    path('api/<int:session_id>/generator/<int:channel_num>/',
         views.update_generator, name='update_generator'),

    # ── API — Snapshots ────────────────────────────────────
    path('api/<int:session_id>/snapshots/',
         views.list_snapshots, name='list_snapshots'),
    path('api/<int:session_id>/snapshots/save/',
         views.save_snapshot, name='save_snapshot'),
    path('api/<int:session_id>/snapshots/<int:snapshot_id>/',
         views.get_snapshot, name='get_snapshot'),

    # ── API — Analyse de composants ────────────────────────
    path('api/<int:session_id>/analyze/',
         views.analyze_component, name='analyze'),
]
