from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json


class OscilloscopeSession(models.Model):
    """Session d'oscilloscope — une mesure ou acquisition"""

    SOURCE_CHOICES = [
        ('wifi',   'ESP32 / ESP8266 via WiFi'),
        ('serial', 'Arduino via port Série'),
        ('sim',    'Simulateur interne'),
    ]

    SIGNAL_CHOICES = [
        ('sine',     'Sinusoïdal'),
        ('square',   'Carré'),
        ('triangle', 'Triangle'),
        ('sawtooth', 'Dent de scie'),
        ('noise',    'Bruit'),
        ('custom',   'Personnalisé'),
    ]

    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='osc_sessions')
    name        = models.CharField(max_length=200, default='Session sans titre')
    source      = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='sim')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    is_active   = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)

    # Paramètres d'acquisition
    sample_rate    = models.FloatField(default=1000.0,  help_text='Échantillons par seconde (Hz)')
    time_div       = models.FloatField(default=1.0,     help_text='ms par division')
    volt_div_ch1   = models.FloatField(default=1.0,     help_text='Volts par division CH1')
    volt_div_ch2   = models.FloatField(default=1.0,     help_text='Volts par division CH2')
    trigger_level  = models.FloatField(default=0.0,     help_text='Niveau de déclenchement (V)')
    trigger_source = models.CharField(max_length=4, default='CH1')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.user.username} ({self.source})"


class Channel(models.Model):
    """Canal de l'oscilloscope (CH1 ou CH2)"""

    COLOR_CHOICES = [
        ('#00ff88', 'Vert'),
        ('#00d4ff', 'Cyan'),
        ('#ffcc00', 'Jaune'),
        ('#ff4455', 'Rouge'),
        ('#ff8800', 'Orange'),
        ('#cc88ff', 'Violet'),
    ]

    session    = models.ForeignKey(OscilloscopeSession, on_delete=models.CASCADE, related_name='channels')
    number     = models.IntegerField(default=1, help_text='1 = CH1, 2 = CH2')
    label      = models.CharField(max_length=50, default='CH1')
    color      = models.CharField(max_length=10, default='#00ff88', choices=COLOR_CHOICES)
    enabled    = models.BooleanField(default=True)
    offset     = models.FloatField(default=0.0, help_text='Décalage vertical (V)')
    coupling   = models.CharField(max_length=3, default='DC', choices=[('DC','DC'),('AC','AC'),('GND','GND')])
    probe_attn = models.FloatField(default=1.0, help_text='Atténuation sonde (1x, 10x, 100x)')
    pin        = models.IntegerField(default=34, help_text='Pin ADC sur ESP32/Arduino')

    class Meta:
        unique_together = ('session', 'number')
        ordering = ['number']

    def __str__(self):
        return f"{self.session.name} — CH{self.number}"


class WaveformData(models.Model):
    """Données de forme d'onde capturées"""

    channel     = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='waveforms')
    timestamp   = models.DateTimeField(auto_now_add=True)
    raw_data    = models.JSONField(help_text='Liste de valeurs [{"t": ms, "v": volts}, ...]')
    sample_count = models.IntegerField(default=0)

    # Mesures calculées automatiquement
    vmax        = models.FloatField(null=True, blank=True, help_text='Tension max (V)')
    vmin        = models.FloatField(null=True, blank=True, help_text='Tension min (V)')
    vpp         = models.FloatField(null=True, blank=True, help_text='Tension crête-à-crête (V)')
    vrms        = models.FloatField(null=True, blank=True, help_text='Tension RMS (V)')
    vavg        = models.FloatField(null=True, blank=True, help_text='Tension moyenne (V)')
    frequency   = models.FloatField(null=True, blank=True, help_text='Fréquence (Hz)')
    period      = models.FloatField(null=True, blank=True, help_text='Période (ms)')
    duty_cycle  = models.FloatField(null=True, blank=True, help_text='Rapport cyclique (%)')
    rise_time   = models.FloatField(null=True, blank=True, help_text='Temps de montée (µs)')

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Waveform {self.channel.label} — {self.timestamp.strftime('%H:%M:%S')}"


class MeasurementSnapshot(models.Model):
    """Instantané de mesure sauvegardé par l'utilisateur"""

    session     = models.ForeignKey(OscilloscopeSession, on_delete=models.CASCADE, related_name='snapshots')
    name        = models.CharField(max_length=200)
    created_at  = models.DateTimeField(auto_now_add=True)
    notes       = models.TextField(blank=True, null=True)

    # Données figées des deux canaux
    ch1_data    = models.JSONField(null=True, blank=True)
    ch2_data    = models.JSONField(null=True, blank=True)
    ch1_metrics = models.JSONField(null=True, blank=True)
    ch2_metrics = models.JSONField(null=True, blank=True)

    # FFT
    fft_data    = models.JSONField(null=True, blank=True, help_text='Données spectre FFT')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Snapshot: {self.name}"


class SignalGenerator(models.Model):
    """Générateur de signal interne (simulation)"""

    WAVE_CHOICES = [
        ('sine',     'Sinusoïdal'),
        ('square',   'Carré'),
        ('triangle', 'Triangle'),
        ('sawtooth', 'Dent de scie'),
        ('noise',    'Bruit blanc'),
        ('pwm',      'PWM'),
        ('damped',   'Sinusoïde amortie'),
        ('am',       'AM modulé'),
    ]

    session    = models.ForeignKey(OscilloscopeSession, on_delete=models.CASCADE, related_name='generators')
    channel    = models.IntegerField(default=1, help_text='Canal cible (1 ou 2)')
    wave_type  = models.CharField(max_length=20, choices=WAVE_CHOICES, default='sine')
    frequency  = models.FloatField(default=100.0,  help_text='Fréquence (Hz)')
    amplitude  = models.FloatField(default=3.3,    help_text='Amplitude crête (V)')
    offset     = models.FloatField(default=0.0,    help_text='Offset DC (V)')
    phase      = models.FloatField(default=0.0,    help_text='Phase (degrés)')
    duty_cycle = models.FloatField(default=50.0,   help_text='Rapport cyclique % (carré/PWM)')
    noise_amp  = models.FloatField(default=0.0,    help_text='Amplitude bruit ajouté (V)')
    enabled    = models.BooleanField(default=True)

    def __str__(self):
        return f"Gen {self.wave_type} {self.frequency}Hz CH{self.channel}"


class ComponentAnalysis(models.Model):
    """Analyse d'un composant électronique spécifique"""

    COMPONENT_CHOICES = [
        ('resistor',    'Résistance'),
        ('capacitor',   'Condensateur'),
        ('inductor',    'Inductance'),
        ('diode',       'Diode'),
        ('transistor',  'Transistor'),
        ('opamp',       'AOP (Amplificateur Opérationnel)'),
        ('filter_lp',   'Filtre passe-bas RC'),
        ('filter_hp',   'Filtre passe-haut RC'),
        ('filter_bp',   'Filtre passe-bande'),
        ('rectifier',   'Redresseur'),
        ('custom',      'Circuit personnalisé'),
    ]

    session        = models.ForeignKey(OscilloscopeSession, on_delete=models.CASCADE, related_name='analyses')
    component_type = models.CharField(max_length=20, choices=COMPONENT_CHOICES)
    name           = models.CharField(max_length=200, default='Analyse sans titre')
    created_at     = models.DateTimeField(auto_now_add=True)
    notes          = models.TextField(blank=True, null=True)

    # Paramètres du composant
    component_value   = models.FloatField(null=True, blank=True, help_text='Valeur (Ω, F, H selon le composant)')
    component_unit    = models.CharField(max_length=10, blank=True, null=True)
    measured_value    = models.FloatField(null=True, blank=True, help_text='Valeur mesurée')
    theoretical_value = models.FloatField(null=True, blank=True, help_text='Valeur théorique')

    # Résultats de l'analyse
    results     = models.JSONField(null=True, blank=True)
    bode_data   = models.JSONField(null=True, blank=True, help_text='Données diagramme de Bode')
    phase_data  = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_component_type_display()} — {self.name}"
