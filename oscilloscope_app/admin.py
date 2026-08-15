from django.contrib import admin
from .models import (
    OscilloscopeSession, Channel, WaveformData,
    MeasurementSnapshot, SignalGenerator, ComponentAnalysis
)


@admin.register(OscilloscopeSession)
class OscilloscopeSessionAdmin(admin.ModelAdmin):
    list_display  = ['name', 'user', 'source', 'created_at', 'is_active']
    list_filter   = ['source', 'is_active']
    search_fields = ['name', 'user__username']


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ['label', 'session', 'number', 'enabled', 'coupling', 'pin']


@admin.register(WaveformData)
class WaveformDataAdmin(admin.ModelAdmin):
    list_display  = ['channel', 'timestamp', 'sample_count', 'vpp', 'frequency', 'vrms']
    list_filter   = ['channel__session']
    readonly_fields = ['timestamp']


@admin.register(MeasurementSnapshot)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = ['name', 'session', 'created_at']


@admin.register(SignalGenerator)
class SignalGeneratorAdmin(admin.ModelAdmin):
    list_display = ['wave_type', 'frequency', 'amplitude', 'channel', 'session', 'enabled']


@admin.register(ComponentAnalysis)
class ComponentAnalysisAdmin(admin.ModelAdmin):
    list_display  = ['name', 'component_type', 'session', 'created_at', 'measured_value']
    list_filter   = ['component_type']
