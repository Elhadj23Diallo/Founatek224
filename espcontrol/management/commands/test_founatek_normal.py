# espcontrol/management/commands/test_founatek_normal.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import random
import time

from espcontrol.models import (
    Device, AppareilData, AgentAlert, ActionLog,
    SensorRule, AgentConfig, Relais
)
from espcontrol.agent.agent import FounatekAgent


class Command(BaseCommand):
    help = "Simulation Air Pur : cycle ESP32 réel (10s), validation du système au repos"

    def add_arguments(self, parser):
        parser.add_argument('--user',  type=str, help="Nom d'utilisateur (ex: elhadj)")
        parser.add_argument('--count', type=int, default=20,
                            help="Nombre de points (défaut : 20 = ~3 min)")
        parser.add_argument('--delay', type=float, default=10.0,
                            help="Délai en secondes entre chaque point (défaut : 10s = cycle ESP32 réel)")
        parser.add_argument('--device_name', type=str, default='Station normale Founatek Pro',
                            help="Nom de la station (défaut : Station normale Founatek Pro)")

    def handle(self, *args, **options):
        username    = options.get('user')
        count       = options.get('count')
        delay       = options.get('delay')
        device_name = options.get('device_name')

        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Utilisateur '{username}' introuvable."))
            return

        # ==========================================
        # 1. ENTÊTE
        # ==========================================
        self.stdout.write(self.style.HTTP_INFO(
            "\n╔══════════════════════════════════════════════════════════════╗\n"
            "║  🍃 SIMULATION AIR PUR — FOUNATEK NEXUS                      ║\n"
            "║  Cycle ESP32 réel (10s) — Système au repos, aucun relais ON  ║\n"
            "╚══════════════════════════════════════════════════════════════╝\n"
        ))

        # ==========================================
        # 2. RÉCUPÉRATION / CRÉATION STATION
        # ==========================================
        try:
            device = Device.objects.get(user=user, name=device_name)
            self.stdout.write(f"✅ Station trouvée : {device.name} ({device.device_id})\n")
        except Device.DoesNotExist:
            device, _ = Device.objects.get_or_create(
                device_id="capteur_demo_pro_normal",
                user=user,
                defaults={'name': "Station normale Founatek Pro"}
            )
            self.stdout.write(f"⚠️ Station créée : {device.name}\n")

        # Création des 3 relais avec noms cohérents
        relais_config = [
            (1, "Ventilateur / Purificateur d'air"),
            (2, "Extracteur d'air (gaz toxiques)"),
            (3, "Climatiseur / Déshumidificateur"),
        ]
        for num, nom in relais_config:
            relais, created = Relais.objects.get_or_create(
                user=user, num=num,
                defaults={'nom': nom, 'etat': False}
            )
            if relais.nom != nom:
                relais.nom = nom
                relais.save(update_fields=['nom'])

        # ==========================================
        # 3. CRÉATION / MISE À JOUR DES RÈGLES OMS COMPLÈTES
        # ==========================================
        # 🎯 LOGIQUE COMPLÈTE :
        #   - WARN     → action_type='alert'              (juste alerte dashboard)
        #   - CRITICAL → action_type='START_IRRIGATION'   (alerte + activation relais)
        #
        # 📡 RÉPARTITION DES RELAIS :
        #   - Relais 1 → Ventilateur/Purificateur (PM2.5, PM10)
        #   - Relais 2 → Extracteur d'air (gaz toxiques)
        #   - Relais 3 → Climatiseur/Déshumidificateur (température, humidité)
        self.stdout.write(self.style.HTTP_INFO(
            "🔧 Vérification des règles SensorRule pour cette station..."
        ))

        # Format : (sensor, max_value, level, code, message, action_type, target_num)
        regles_oms = [
            # ────────── PM2.5 ──────────
            ('pm2p5',       15,   'WARN',     'WARN_PM25',
             'PM2.5 dépasse le seuil OMS (15 µg/m³)',
             'alert', 1),
            ('pm2p5',       35,   'CRITICAL', 'CRITICAL_PM25',
             'PM2.5 DANGEREUX — Ventilateur ACTIVÉ automatiquement !',
             'START_IRRIGATION', 1),

            # ────────── PM10 ──────────
            ('pm10',        45,   'WARN',     'WARN_PM10',
             'PM10 dépasse le seuil OMS (45 µg/m³)',
             'alert', 1),
            ('pm10',        150,  'CRITICAL', 'CRITICAL_PM10',
             'PM10 DANGEREUX — Purificateur ACTIVÉ automatiquement !',
             'START_IRRIGATION', 1),

            # ────────── GAZ (MQ-135) ──────────
            ('mq135_ppm',   400,  'WARN',     'WARN_GAZ',
             'Concentration gaz élevée (>400 PPM)',
             'alert', 2),
            ('mq135_ppm',   700,  'CRITICAL', 'CRITICAL_GAZ',
             'Gaz DANGEREUX — Extracteur d\'air ACTIVÉ automatiquement !',
             'START_IRRIGATION', 2),

            # ────────── TEMPÉRATURE (gradation complète) ──────────
            ('temperature', 35,   'WARN',     'WARN_TEMP',
             'Température élevée (>35°C) — Inconfort thermique',
             'alert', 3),
            ('temperature', 40,   'CRITICAL', 'CRITICAL_TEMP',
             'Chaleur DANGEREUSE (>40°C) — Climatiseur ACTIVÉ automatiquement !',
             'START_IRRIGATION', 3),

            # ────────── HUMIDITÉ (gradation complète) ──────────
            ('humidity',    80,   'WARN',     'WARN_HUM',
             'Humidité élevée (>80%) — Risque moisissures',
             'alert', 3),
            ('humidity',    90,   'CRITICAL', 'CRITICAL_HUM',
             'Humidité EXCESSIVE (>90%) — Déshumidificateur ACTIVÉ !',
             'START_IRRIGATION', 3),
        ]

        regles_creees     = 0
        regles_existantes = 0
        regles_maj        = 0

        for sensor, max_val, level, code, message, action_type, target_num in regles_oms:
            obj, created = SensorRule.objects.get_or_create(
                user=user,
                device=device,
                sensor=sensor,
                code=code,
                defaults={
                    'max_value':   max_val,
                    'level':       level,
                    'message':     message,
                    'action_type': action_type,
                    'target_num':  target_num,
                    'active':      True,
                }
            )
            if created:
                regles_creees += 1
            else:
                regles_existantes += 1
                # 🔄 Met à jour les règles existantes
                needs_update = (
                    obj.action_type != action_type or
                    obj.target_num != target_num or
                    obj.message != message or
                    obj.max_value != max_val or
                    obj.level != level
                )
                if needs_update:
                    obj.action_type = action_type
                    obj.target_num  = target_num
                    obj.message     = message
                    obj.max_value   = max_val
                    obj.level       = level
                    obj.save(update_fields=['action_type', 'target_num', 'message', 'max_value', 'level'])
                    regles_maj += 1

        if regles_creees > 0:
            self.stdout.write(self.style.SUCCESS(
                f"   ✅ {regles_creees} nouvelle(s) règle(s) OMS créée(s)"
            ))
        if regles_existantes > 0:
            self.stdout.write(
                f"   ⚠️ {regles_existantes} règle(s) déjà existante(s) — réutilisées"
            )
        if regles_maj > 0:
            self.stdout.write(self.style.SUCCESS(
                f"   🔄 {regles_maj} règle(s) mise(s) à jour"
            ))

        # Affichage récapitulatif
        self.stdout.write(self.style.HTTP_INFO(
            "\n📋 Règles SensorRule actives pour cette station :"
        ))
        for r in SensorRule.objects.filter(user=user, device=device, active=True).order_by('sensor', 'max_value'):
            level_color = {
                'INFO':     self.style.HTTP_INFO,
                'WARN':     self.style.WARNING,
                'CRITICAL': self.style.ERROR,
            }.get(r.level, self.style.HTTP_INFO)
            action_info = f" → Relais {r.target_num}" if r.action_type == 'START_IRRIGATION' else ""
            self.stdout.write(level_color(
                f"   • {r.sensor:12s} max={r.max_value:6.1f}  [{r.level:8s}]  {r.code:18s}  [{r.action_type}]{action_info}"
            ))

        # ==========================================
        # 4. INJECTION TOUTES LES 10s — VALEURS SAINES
        # ==========================================
        # 🎯 OBJECTIF : démontrer que le système RESTE AU REPOS
        # Toutes les valeurs sont SOUS les seuils WARN
        self.stdout.write(self.style.SUCCESS(
            f"\n🍃 Injection de {count} points SAINS dans '{device.name}' "
            f"(délai : {delay}s — cycle ESP32 réel)\n"
            f"✅ Objectif : aucune alerte, aucun relais activé\n"
        ))
        self.stdout.write("─" * 70 + "\n")

        agent = FounatekAgent(user)
        alertes_initiales = AgentAlert.objects.filter(user=user).count()

        for i in range(1, count + 1):
            # Génération de valeurs SAINES réalistes (sous TOUS les seuils WARN)
            pm2p5 = round(10.0  + random.uniform(-2,    2),    2)   # 8-12 µg/m³   (<15 WARN)
            pm10  = round(20.0  + random.uniform(-3,    3),    2)   # 17-23 µg/m³  (<45 WARN)
            mq135 = round(250.0 + random.uniform(-10,  10),   1)    # 240-260 PPM  (<400 WARN)
            temp  = round(28.0  + random.uniform(-0.5, 0.5),  1)    # 27.5-28.5°C  (<35 WARN)
            hum   = round(60.0  + random.uniform(-2,    2),   1)    # 58-62%       (<80 WARN)

            AppareilData.objects.create(
                device=device,
                payload={
                    "pm2p5":       pm2p5,
                    "pm10":        pm10,
                    "mq135_ppm":   mq135,
                    "temperature": temp,
                    "humidity":    hum,
                    "latitude":    9.6412,
                    "longitude":   -13.5784,
                }
            )

            # L'agent analyse immédiatement
            alertes_avant = AgentAlert.objects.filter(user=user).count()
            agent.run()
            alertes_apres = AgentAlert.objects.filter(user=user).count()
            new_alerts = alertes_apres - alertes_avant

            # 🎯 État des relais après l'agent (doit rester OFF)
            relais_on = Relais.objects.filter(user=user, etat=True).values_list('num', flat=True)
            relais_marker = f" ⚡ Relais ON: {list(relais_on)}" if relais_on else ""

            alert_marker = f" 🚨 +{new_alerts} alerte(s)" if new_alerts > 0 else ""

            self.stdout.write(
                f"   [{i:03d}/{count}] " +
                self.style.SUCCESS(f"[SAIN] ") +
                f"PM2.5={pm2p5:5.1f} | PM10={pm10:5.1f} | Gaz={mq135:5.0f} | "
                f"T={temp:4.1f}°C | H={hum:4.1f}%" +
                self.style.ERROR(alert_marker) +
                self.style.WARNING(relais_marker)
            )

            if delay > 0 and i < count:
                time.sleep(delay)

        # ==========================================
        # 5. BILAN FINAL
        # ==========================================
        self.stdout.write("\n" + "─" * 70)
        self.stdout.write(self.style.HTTP_INFO("\n🎯 BILAN FINAL DE LA SIMULATION\n"))

        alertes_finales   = AgentAlert.objects.filter(user=user).count()
        nouvelles_alertes = alertes_finales - alertes_initiales

        # État des relais (doivent tous être OFF en air pur)
        self.stdout.write(self.style.HTTP_INFO("📡 État final des actionneurs :"))
        relais_list = Relais.objects.filter(user=user).order_by('num')
        relais_on_count = 0
        for r in relais_list:
            status = "🔴 ON (anormal !)" if r.etat else "💤 OFF (sécurité OK)"
            color  = self.style.ERROR if r.etat else self.style.SUCCESS
            self.stdout.write(color(f"   → Relais {r.num} ({r.nom}) : {status}"))
            if r.etat:
                relais_on_count += 1

        # Résumé chiffré
        actions_count = ActionLog.objects.filter(user=user).count()
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Simulation terminée :"
        ))
        self.stdout.write(f"   📊 Points injectés       : {count}")
        self.stdout.write(f"   🚨 Nouvelles alertes IA  : {nouvelles_alertes}")
        self.stdout.write(f"   📋 Total alertes en base : {alertes_finales}")
        self.stdout.write(f"   📝 Actions journalisées  : {actions_count}")
        self.stdout.write(f"   ⚡ Relais actifs en fin  : {relais_on_count}/3")

        # Analyse pédagogique
        self.stdout.write(self.style.HTTP_INFO("\n🧠 ANALYSE PÉDAGOGIQUE :"))
        if nouvelles_alertes == 0 and relais_on_count == 0:
            self.stdout.write(self.style.SUCCESS(
                "   ✅ Aucune alerte créée — comportement attendu pour air pur."
            ))
            self.stdout.write(self.style.SUCCESS(
                "   ✅ Tous les relais OFF — sécurité maintenue, système au repos."
            ))
            self.stdout.write(self.style.SUCCESS(
                "   ✅ Pas de faux positifs : robustesse industrielle validée."
            ))
        elif nouvelles_alertes > 0:
            self.stdout.write(self.style.WARNING(
                f"   ⚠️ {nouvelles_alertes} alerte(s) créée(s) — anormal pour air pur, vérifier seuils."
            ))
        if relais_on_count > 0:
            self.stdout.write(self.style.ERROR(
                f"   ❌ {relais_on_count} relais actif(s) — anormal, vérifier balayage de sécurité."
            ))

        self.stdout.write(self.style.HTTP_INFO(
            f"\n💡 Dashboard : badge AQI doit afficher ✅ BON (vert).\n"
        ))