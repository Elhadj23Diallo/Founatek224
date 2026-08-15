from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib import messages

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, authentication_classes, permission_classes

import json
import math
import numpy as np
import random

from .models import (
    OscilloscopeSession, Channel, WaveformData,
    MeasurementSnapshot, SignalGenerator, ComponentAnalysis
)
from .serializers import (
    OscilloscopeSessionSerializer, ChannelSerializer,
    WaveformDataSerializer, IngestDataSerializer,
    MeasurementSnapshotSerializer, SignalGeneratorSerializer,
    ComponentAnalysisSerializer, calculate_metrics, calculate_fft
)


# ═══════════════════════════════════════════════════════════
#  VUES HTML
# ═══════════════════════════════════════════════════════════

@login_required
def oscilloscope_home(request):
    """Page principale — liste des sessions"""
    sessions = OscilloscopeSession.objects.filter(user=request.user).order_by('-updated_at')
    return render(request, 'oscilloscope_app/home.html', {'sessions': sessions})


@login_required
def oscilloscope_view(request, session_id=None):
    """Interface oscilloscope principale"""
    if session_id:
        session = get_object_or_404(OscilloscopeSession, id=session_id, user=request.user)
    else:
        # Créer une session par défaut
        session = OscilloscopeSession.objects.create(
            user=request.user,
            name=f"Session {timezone.now().strftime('%d/%m/%Y %H:%M')}",
            source='sim'
        )
        # Créer CH1 et CH2 par défaut
        Channel.objects.create(session=session, number=1, label='CH1', color='#00ff88', pin=34)
        Channel.objects.create(session=session, number=2, label='CH2', color='#00d4ff', pin=35)
        # Générateur par défaut CH1
        SignalGenerator.objects.create(
            session=session, channel=1, wave_type='sine',
            frequency=100.0, amplitude=3.3, offset=0.0
        )
        return redirect('oscilloscope:view', session_id=session.id)

    channels   = Channel.objects.filter(session=session)
    generators = SignalGenerator.objects.filter(session=session)
    snapshots  = MeasurementSnapshot.objects.filter(session=session)[:10]
    analyses   = ComponentAnalysis.objects.filter(session=session)[:10]

    return render(request, 'oscilloscope_app/oscilloscope.html', {
        'session':    session,
        'channels':   channels,
        'generators': generators,
        'snapshots':  snapshots,
        'analyses':   analyses,
    })


@login_required
def create_session(request):
    if request.method == 'POST':
        name   = request.POST.get('name', 'Nouvelle session')
        source = request.POST.get('source', 'sim')
        desc   = request.POST.get('description', '')

        session = OscilloscopeSession.objects.create(
            user=request.user, name=name, source=source, description=desc
        )
        Channel.objects.create(session=session, number=1, label='CH1', color='#00ff88', pin=34)
        Channel.objects.create(session=session, number=2, label='CH2', color='#00d4ff', pin=35)
        SignalGenerator.objects.create(
            session=session, channel=1, wave_type='sine',
            frequency=100.0, amplitude=3.3
        )
        messages.success(request, f'Session "{name}" créée !')
        return redirect('oscilloscope:view', session_id=session.id)

    return render(request, 'oscilloscope_app/create_session.html')


@login_required
def delete_session(request, session_id):
    session = get_object_or_404(OscilloscopeSession, id=session_id, user=request.user)
    session.delete()
    messages.success(request, 'Session supprimée.')
    return redirect('oscilloscope:home')


# ═══════════════════════════════════════════════════════════
#  API — GÉNÉRATION DE SIGNAL (SIMULATEUR)
# ═══════════════════════════════════════════════════════════

@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def generate_signal(request):
    """
    Génère un signal simulé selon les paramètres du générateur.
    Appelé par le frontend JavaScript en temps réel.
    """
    data       = request.data
    wave_type  = data.get('wave_type', 'sine')
    frequency  = float(data.get('frequency', 100.0))
    amplitude  = float(data.get('amplitude', 3.3))
    offset     = float(data.get('offset', 0.0))
    phase      = float(data.get('phase', 0.0))
    duty_cycle = float(data.get('duty_cycle', 50.0))
    noise_amp  = float(data.get('noise_amp', 0.0))
    n_samples  = int(data.get('n_samples', 500))
    duration   = float(data.get('duration', 50.0))  # ms

    samples = []
    dt = duration / n_samples  # ms par échantillon
    phase_rad = math.radians(phase)

    for i in range(n_samples):
        t = i * dt  # temps en ms
        t_s = t / 1000.0  # temps en secondes
        omega = 2 * math.pi * frequency

        if wave_type == 'sine':
            v = amplitude * math.sin(omega * t_s + phase_rad) + offset

        elif wave_type == 'square':
            raw = math.sin(omega * t_s + phase_rad)
            v = amplitude * (1 if raw >= 0 else -1) + offset
            # Duty cycle
            frac = (omega * t_s + phase_rad) / (2 * math.pi) % 1.0
            v = amplitude if frac < duty_cycle/100 else -amplitude
            v += offset

        elif wave_type == 'triangle':
            frac = (omega * t_s + phase_rad) / (2 * math.pi) % 1.0
            if frac < 0.5:
                v = amplitude * (4 * frac - 1) + offset
            else:
                v = amplitude * (3 - 4 * frac) + offset

        elif wave_type == 'sawtooth':
            frac = (omega * t_s + phase_rad) / (2 * math.pi) % 1.0
            v = amplitude * (2 * frac - 1) + offset

        elif wave_type == 'noise':
            v = amplitude * (random.random() * 2 - 1) + offset

        elif wave_type == 'pwm':
            frac = (omega * t_s + phase_rad) / (2 * math.pi) % 1.0
            v = amplitude if frac < duty_cycle/100 else 0.0
            v += offset

        elif wave_type == 'damped':
            decay = math.exp(-2.0 * t_s)
            v = amplitude * decay * math.sin(omega * t_s + phase_rad) + offset

        elif wave_type == 'am':
            carrier = math.sin(omega * t_s + phase_rad)
            mod     = 0.5 * (1 + math.sin(2 * math.pi * frequency * 0.1 * t_s))
            v = amplitude * mod * carrier + offset

        else:
            v = 0.0

        # Ajouter du bruit si demandé
        if noise_amp > 0:
            v += noise_amp * (random.random() * 2 - 1)

        # Clamp à ±5V (limites ESP32)
        v = max(-5.0, min(5.0, v))
        samples.append({'t': round(t, 3), 'v': round(v, 4)})

    metrics = calculate_metrics(samples)
    fft     = calculate_fft(samples, sample_rate=n_samples / (duration / 1000))

    return Response({
        'samples': samples,
        'metrics': metrics,
        'fft':     fft[:100],  # Limiter à 100 points FFT
    })


# ═══════════════════════════════════════════════════════════
#  API — INGESTION DONNÉES ESP32 / ARDUINO
# ═══════════════════════════════════════════════════════════

class IngestWaveformView(APIView):
    """
    Endpoint pour recevoir les données d'un ESP32 (WiFi) ou Arduino (Série→bridge)
    POST /oscilloscope/api/ingest/
    Header: Authorization: Token VOTRE_TOKEN
    Body: {"session_id": 1, "channel": 1, "samples": [...], "sample_rate": 1000}
    """
    authentication_classes = [TokenAuthentication]
    permission_classes     = [IsAuthenticated]

    def post(self, request):
        serializer = IngestDataSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Vérifier que la session appartient à l'utilisateur
        try:
            session = OscilloscopeSession.objects.get(
                id=data['session_id'], user=request.user
            )
        except OscilloscopeSession.DoesNotExist:
            return Response({'error': 'Session introuvable'}, status=404)

        # Trouver le canal
        channel = Channel.objects.filter(
            session=session, number=data['channel']
        ).first()

        if not channel:
            return Response({'error': f"Canal CH{data['channel']} introuvable"}, status=404)

        # Calculer les métriques
        samples = data['samples']
        metrics = calculate_metrics(samples)

        # Sauvegarder la forme d'onde
        waveform = WaveformData.objects.create(
            channel      = channel,
            raw_data     = samples,
            sample_count = len(samples),
            vmax         = metrics.get('vmax'),
            vmin         = metrics.get('vmin'),
            vpp          = metrics.get('vpp'),
            vrms         = metrics.get('vrms'),
            vavg         = metrics.get('vavg'),
            frequency    = metrics.get('frequency'),
            period       = metrics.get('period'),
            duty_cycle   = metrics.get('duty_cycle'),
            rise_time    = metrics.get('rise_time'),
        )

        # Mettre à jour la source de la session
        session.source = 'wifi'
        session.save()

        fft = calculate_fft(samples, data['sample_rate'])

        return Response({
            'status':       'ok',
            'waveform_id':  waveform.id,
            'sample_count': len(samples),
            'metrics':      metrics,
            'fft':          fft[:50],
        }, status=status.HTTP_201_CREATED)


# ═══════════════════════════════════════════════════════════
#  API — DONNÉES TEMPS RÉEL (polling JS)
# ═══════════════════════════════════════════════════════════

@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def latest_waveform(request, session_id, channel_num):
    """Retourne la dernière forme d'onde d'un canal — appelé par le JS toutes les X ms"""
    session = get_object_or_404(OscilloscopeSession, id=session_id, user=request.user)
    channel = get_object_or_404(Channel, session=session, number=channel_num)

    waveform = WaveformData.objects.filter(channel=channel).first()
    if not waveform:
        return Response({'samples': [], 'metrics': {}})

    metrics = calculate_metrics(waveform.raw_data)
    fft     = calculate_fft(waveform.raw_data)

    return Response({
        'samples':    waveform.raw_data,
        'metrics':    metrics,
        'fft':        fft[:100],
        'timestamp':  waveform.timestamp.isoformat(),
    })


# ═══════════════════════════════════════════════════════════
#  API — SNAPSHOTS
# ═══════════════════════════════════════════════════════════

@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def save_snapshot(request, session_id):
    """Sauvegarde un instantané de la forme d'onde actuelle"""
    session = get_object_or_404(OscilloscopeSession, id=session_id, user=request.user)

    name     = request.data.get('name', f"Snapshot {timezone.now().strftime('%H:%M:%S')}")
    ch1_data = request.data.get('ch1_data', [])
    ch2_data = request.data.get('ch2_data', [])
    fft_data = request.data.get('fft_data', [])
    notes    = request.data.get('notes', '')

    ch1_metrics = calculate_metrics(ch1_data) if ch1_data else {}
    ch2_metrics = calculate_metrics(ch2_data) if ch2_data else {}

    snapshot = MeasurementSnapshot.objects.create(
        session     = session,
        name        = name,
        notes       = notes,
        ch1_data    = ch1_data,
        ch2_data    = ch2_data,
        ch1_metrics = ch1_metrics,
        ch2_metrics = ch2_metrics,
        fft_data    = fft_data,
    )

    return Response({
        'status':      'saved',
        'snapshot_id': snapshot.id,
        'name':        snapshot.name,
    }, status=201)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_snapshots(request, session_id):
    session   = get_object_or_404(OscilloscopeSession, id=session_id, user=request.user)
    snapshots = MeasurementSnapshot.objects.filter(session=session)
    return Response(MeasurementSnapshotSerializer(snapshots, many=True).data)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_snapshot(request, session_id, snapshot_id):
    session  = get_object_or_404(OscilloscopeSession, id=session_id, user=request.user)
    snapshot = get_object_or_404(MeasurementSnapshot, id=snapshot_id, session=session)
    return Response(MeasurementSnapshotSerializer(snapshot).data)


# ═══════════════════════════════════════════════════════════
#  API — ANALYSE DE COMPOSANTS
# ═══════════════════════════════════════════════════════════

@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def analyze_component(request, session_id):
    """Analyse un composant électronique à partir des données CH1 et CH2"""
    session        = get_object_or_404(OscilloscopeSession, id=session_id, user=request.user)
    component_type = request.data.get('component_type', 'resistor')
    name           = request.data.get('name', 'Analyse')
    ch1_samples    = request.data.get('ch1_samples', [])
    ch2_samples    = request.data.get('ch2_samples', [])
    comp_value     = request.data.get('component_value', None)
    notes          = request.data.get('notes', '')

    ch1_m = calculate_metrics(ch1_samples)
    ch2_m = calculate_metrics(ch2_samples)

    results = {}

    if component_type == 'resistor' and ch1_m and ch2_m:
        # Loi d'Ohm : R = V/I, ici CH1 = tension totale, CH2 = tension aux bornes
        if ch1_m.get('vrms') and ch2_m.get('vrms') and ch1_m['vrms'] > 0:
            # Tension sur résistance connue (shunt) pour calculer le courant
            r_shunt = float(request.data.get('r_shunt', 100))
            i_rms   = ch2_m['vrms'] / r_shunt
            v_comp  = ch1_m['vrms'] - ch2_m['vrms']
            r_meas  = v_comp / i_rms if i_rms > 0 else None
            results = {
                'V_rms_total':    ch1_m['vrms'],
                'V_rms_shunt':    ch2_m['vrms'],
                'I_rms_A':        round(i_rms, 6),
                'R_mesuree_ohm':  round(r_meas, 2) if r_meas else None,
                'R_theorique':    comp_value,
                'erreur_pct':     round(abs(r_meas - comp_value) / comp_value * 100, 2)
                                  if r_meas and comp_value else None,
            }

    elif component_type in ('capacitor', 'filter_lp', 'filter_hp'):
        if ch1_m.get('frequency') and ch2_m.get('vrms') and ch1_m.get('vrms'):
            freq   = ch1_m['frequency']
            gain   = ch2_m['vrms'] / ch1_m['vrms'] if ch1_m['vrms'] > 0 else 0
            gain_db = 20 * math.log10(gain) if gain > 0 else -100

            # Fréquence de coupure théorique si R et C connus
            r_val = float(request.data.get('r_value', 1000))
            fc    = 1 / (2 * math.pi * r_val * comp_value) if comp_value else None

            results = {
                'frequence_Hz':   freq,
                'gain_lineaire':  round(gain, 4),
                'gain_dB':        round(gain_db, 2),
                'f_coupure_Hz':   round(fc, 2) if fc else None,
                'phase_deg':      None,
            }

            # Calcul de la phase
            if len(ch1_samples) > 10 and len(ch2_samples) > 10:
                try:
                    v1 = np.array([s['v'] for s in ch1_samples])
                    v2 = np.array([s['v'] for s in ch2_samples])
                    corr    = np.correlate(v1 - v1.mean(), v2 - v2.mean(), mode='full')
                    lag     = corr.argmax() - (len(v1) - 1)
                    dt_ms   = ch1_samples[1]['t'] - ch1_samples[0]['t']
                    if freq:
                        phase_deg = (lag * dt_ms / 1000.0) * freq * 360
                        results['phase_deg'] = round(phase_deg % 360, 2)
                except Exception:
                    pass

    elif component_type == 'diode':
        if ch1_m and ch2_m:
            results = {
                'V_anode_max':   ch1_m.get('vmax'),
                'V_cathode_max': ch2_m.get('vmax'),
                'V_seuil_V':     round((ch1_m.get('vmax', 0) - ch2_m.get('vmax', 0)), 3),
                'type_estime':   'Silicium (0.6-0.7V)' if 0.5 < abs(ch1_m.get('vmax', 0) - ch2_m.get('vmax', 0)) < 0.8 else 'Germanium (<0.3V) ou LED (>1.5V)',
            }

    # Générer données de Bode (amplitude vs fréquence simulée)
    bode_data = []
    if component_type in ('filter_lp', 'filter_hp', 'filter_bp', 'capacitor'):
        r_val = float(request.data.get('r_value', 1000))
        c_val = comp_value or 1e-6
        fc    = 1 / (2 * math.pi * r_val * c_val)
        for f_exp in np.linspace(1, 5, 50):
            f    = 10 ** f_exp
            w    = 2 * math.pi * f
            wc   = 2 * math.pi * fc
            if component_type == 'filter_lp':
                gain = 1 / math.sqrt(1 + (f/fc)**2)
            elif component_type == 'filter_hp':
                gain = (f/fc) / math.sqrt(1 + (f/fc)**2)
            else:
                gain = 1.0
            bode_data.append({
                'f':       round(f, 2),
                'gain_db': round(20 * math.log10(gain) if gain > 0 else -100, 2)
            })

    analysis = ComponentAnalysis.objects.create(
        session           = session,
        component_type    = component_type,
        name              = name,
        notes             = notes,
        component_value   = comp_value,
        measured_value    = results.get('R_mesuree_ohm') or results.get('gain_lineaire'),
        theoretical_value = comp_value,
        results           = results,
        bode_data         = bode_data,
    )

    return Response({
        'analysis_id': analysis.id,
        'component':   component_type,
        'results':     results,
        'bode_data':   bode_data,
        'ch1_metrics': ch1_m,
        'ch2_metrics': ch2_m,
    }, status=201)


# ═══════════════════════════════════════════════════════════
#  API — MISE À JOUR PARAMÈTRES SESSION
# ═══════════════════════════════════════════════════════════

@api_view(['PATCH'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_session(request, session_id):
    session = get_object_or_404(OscilloscopeSession, id=session_id, user=request.user)
    for field in ['time_div', 'volt_div_ch1', 'volt_div_ch2',
                  'trigger_level', 'trigger_source', 'name', 'source']:
        if field in request.data:
            setattr(session, field, request.data[field])
    session.save()
    return Response({'status': 'updated'})


@api_view(['PATCH'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_generator(request, session_id, channel_num):
    session   = get_object_or_404(OscilloscopeSession, id=session_id, user=request.user)
    generator = get_object_or_404(SignalGenerator, session=session, channel=channel_num)

    for field in ['wave_type', 'frequency', 'amplitude', 'offset',
                  'phase', 'duty_cycle', 'noise_amp', 'enabled']:
        if field in request.data:
            setattr(generator, field, request.data[field])
    generator.save()
    return Response({'status': 'updated'})
