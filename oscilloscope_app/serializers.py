from rest_framework import serializers
from .models import (
    OscilloscopeSession, Channel, WaveformData,
    MeasurementSnapshot, SignalGenerator, ComponentAnalysis
)
import numpy as np
import math


def calculate_metrics(samples):
    """Calcule toutes les mesures à partir d'une liste de valeurs tension"""
    if not samples or len(samples) < 2:
        return {}

    values = [s['v'] for s in samples]
    times  = [s['t'] for s in samples]

    vmax = max(values)
    vmin = min(values)
    vpp  = vmax - vmin
    vavg = sum(values) / len(values)
    vrms = math.sqrt(sum(v**2 for v in values) / len(values))

    # Fréquence par zero-crossing
    frequency = None
    period    = None
    crossings = []
    for i in range(1, len(values)):
        if values[i-1] < vavg <= values[i]:
            crossings.append(times[i])

    if len(crossings) >= 2:
        periods   = [crossings[i+1] - crossings[i] for i in range(len(crossings)-1)]
        period    = sum(periods) / len(periods)
        frequency = 1000.0 / period if period > 0 else None

    # Rapport cyclique (signal carré)
    duty_cycle = None
    if frequency:
        above = sum(1 for v in values if v > vavg)
        duty_cycle = (above / len(values)) * 100

    # Temps de montée (10% → 90%)
    rise_time = None
    v10 = vmin + 0.1 * vpp
    v90 = vmin + 0.9 * vpp
    t10 = t90 = None
    for i in range(len(values)-1):
        if values[i] <= v10 < values[i+1] and t10 is None:
            t10 = times[i]
        if values[i] <= v90 < values[i+1] and t90 is None:
            t90 = times[i]
    if t10 is not None and t90 is not None and t90 > t10:
        rise_time = (t90 - t10) * 1000  # en µs

    return {
        'vmax':       round(vmax, 4),
        'vmin':       round(vmin, 4),
        'vpp':        round(vpp, 4),
        'vrms':       round(vrms, 4),
        'vavg':       round(vavg, 4),
        'frequency':  round(frequency, 2) if frequency else None,
        'period':     round(period, 4) if period else None,
        'duty_cycle': round(duty_cycle, 1) if duty_cycle else None,
        'rise_time':  round(rise_time, 2) if rise_time else None,
    }


def calculate_fft(samples, sample_rate=1000):
    """Calcule la FFT d'un signal"""
    if not samples or len(samples) < 8:
        return []

    values = np.array([s['v'] for s in samples])
    N      = len(values)
    fft    = np.fft.fft(values)
    freqs  = np.fft.fftfreq(N, d=1.0/sample_rate)
    mag    = np.abs(fft[:N//2]) * 2 / N

    return [
        {'f': round(float(freqs[i]), 2), 'mag': round(float(mag[i]), 4)}
        for i in range(len(freqs[:N//2]))
        if freqs[i] >= 0
    ]


class ChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Channel
        fields = '__all__'


class WaveformDataSerializer(serializers.ModelSerializer):
    metrics = serializers.SerializerMethodField()

    class Meta:
        model  = WaveformData
        fields = '__all__'

    def get_metrics(self, obj):
        return calculate_metrics(obj.raw_data)


class SignalGeneratorSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SignalGenerator
        fields = '__all__'


class MeasurementSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model  = MeasurementSnapshot
        fields = '__all__'


class ComponentAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ComponentAnalysis
        fields = '__all__'


class OscilloscopeSessionSerializer(serializers.ModelSerializer):
    channels   = ChannelSerializer(many=True, read_only=True)
    generators = SignalGeneratorSerializer(many=True, read_only=True)

    class Meta:
        model  = OscilloscopeSession
        fields = '__all__'


# ── Serializer pour la réception de données ESP32 / Arduino ──
class IngestDataSerializer(serializers.Serializer):
    """
    Reçoit les données envoyées par ESP32 (WiFi) ou Arduino (Série→API)
    Format attendu :
    {
        "session_id": 1,
        "channel": 1,
        "samples": [{"t": 0.0, "v": 1.65}, {"t": 1.0, "v": 2.1}, ...],
        "sample_rate": 1000
    }
    """
    session_id  = serializers.IntegerField()
    channel     = serializers.IntegerField(default=1)
    samples     = serializers.ListField(child=serializers.DictField())
    sample_rate = serializers.FloatField(default=1000.0)

    def validate_samples(self, value):
        if len(value) < 2:
            raise serializers.ValidationError("Au moins 2 échantillons requis")
        for s in value:
            if 't' not in s or 'v' not in s:
                raise serializers.ValidationError("Chaque échantillon doit avoir 't' (temps ms) et 'v' (tension V)")
        return value
