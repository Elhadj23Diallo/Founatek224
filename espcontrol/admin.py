from django.contrib import admin
from django.contrib.auth.models import User

from .models import (
    DHTData,
    UploadedImage,
    LED,
    Comptage,
    Relais,
    Comment,
    NtcSensorData,
    Badge,
    Door,
    AccessRule,
    AccessLog,
    AirReading,
    AirSimulatedData,
    SensorData,
    Device,
    AppareilData,
    AgentAlert, SensorRule,
)



@admin.register(SensorRule)
class SensorRuleAdmin(admin.ModelAdmin):
    list_display = ("user", "device", "sensor", "min_value", "max_value", "level", "active")
    list_filter = ("level", "active")
    search_fields = ("user__username", "sensor", "code")

# =========================
# 🤖 AGENT ALERT (IA)
# =========================
@admin.register(AgentAlert)
class AgentAlertAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "user",
        "device",
        "level",
        "code",
        "message",
        "is_read",
    )
    list_filter = ("level", "is_read", "created_at")
    search_fields = ("message", "code", "user__username", "device__name")
    ordering = ("-created_at",)
    list_editable = ("is_read",)
    readonly_fields = ("created_at",)

# =========================
# APPAREIL DATA
# =========================
@admin.register(AppareilData)
class AppareilDataAdmin(admin.ModelAdmin):
    list_display = ("device", "received_at", "is_anomaly")
    list_filter = ("is_anomaly", "received_at")
    search_fields = ("device__name",)
    ordering = ("-received_at",)

# =========================
# DEVICE
# =========================
@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("device_id", "name", "api_key", "is_active", "last_seen")
    search_fields = ("device_id", "name")
    list_filter = ("is_active",)

# =========================
# DOOR
# =========================
@admin.register(Door)
class DoorAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "actuator", "is_active")
    search_fields = ("name", "slug")
    list_filter = ("is_active",)

# =========================
# BADGE
# =========================
@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("uid", "label", "owner", "is_active")
    search_fields = ("uid", "label", "owner__username")
    fields = ("uid", "owner", "label", "notes", "is_active")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "owner":
            kwargs["queryset"] = User.objects.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

# =========================
# ACCESS RULE
# =========================
@admin.register(AccessRule)
class AccessRuleAdmin(admin.ModelAdmin):
    list_display = ("badge", "door", "allowed", "start_time", "end_time")
    list_filter = ("allowed", "door")

# =========================
# ACCESS LOG
# =========================
@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "uid",
        "badge",
        "door",
        "user",
        "allowed",
        "ip_address",
    )
    list_filter = ("allowed", "door")
    search_fields = ("uid", "badge__uid", "user__username", "door__name")
    readonly_fields = ("timestamp", "raw_payload")
    date_hierarchy = "timestamp"

# =========================
# AIR READING
# =========================
@admin.register(AirReading)
class AirReadingAdmin(admin.ModelAdmin):
    list_display = ("created_at", "source", "pm2p5", "pm10", "co", "no2")
    list_filter = ("source",)


# =========================
# ACTION LOG & AGENT CONFIG
# =========================
from .models import ActionLog, AgentConfig


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action")
    search_fields = ("user__username", "action")
    readonly_fields = ("created_at",)


@admin.register(AgentConfig)
class AgentConfigAdmin(admin.ModelAdmin):
    list_display = ("user", "cooldown_minutes")
    search_fields = ("user__username",)

# =========================
# AIR SIMULATED DATA
# =========================
@admin.register(AirSimulatedData)
class AirSimulatedDataAdmin(admin.ModelAdmin):
    list_display = ("simulated_time", "source", "pm2p5", "pm10", "co", "no2")
    list_filter = ("source",)

# =========================
# IMAGES
# =========================
@admin.register(UploadedImage)
class UploadedImageAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "image")
    search_fields = ("id",)

# =========================
# DHT DATA
# =========================
@admin.register(DHTData)
class DHTDataAdmin(admin.ModelAdmin):
    list_display = ("temperature", "humidity", "created_at")
    list_filter = ("created_at",)

# =========================
# AUTRES
# =========================
admin.site.register(NtcSensorData)
admin.site.register(LED)
admin.site.register(Comptage)
admin.site.register(Relais)
admin.site.register(Comment)

# =========================
# SENSOR DATA
# =========================
@admin.register(SensorData)
class SensorDataAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "temperature", "humidity", "co2", "gaz_type")
