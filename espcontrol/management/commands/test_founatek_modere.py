# espcontrol/management/commands/test_founatek_modere.py
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
    help = "Simulation Air Modéré : cycle ESP32 réel (10s), alertes WARN sans relais"

    def add_arguments(self, parser):
        parser.add_argument('--user',  type=str, help="Nom d'utilisateur (ex: elhadj)")
        parser.add_argument('--count', type=int, default=20,
                            help="Nombre de points (défaut : 20 = ~3 min)")
        parser.add_argument('--delay', type=float, default=10.0,
                            help="Délai entre chaque point en secondes (défaut : 10s = cycle ESP32 réel)")
        parser.add_argument('--device_name', type=str, default='Station Modérée Founatek Pro',
                            help="Nom de la station (défaut : Station Modérée Founatek Pro)")

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
            "║  ⚠️  SIMULATION AIR MODÉRÉ — FOUNATEK NEXUS                  ║\n"
            "║  Cycle ESP32 réel (10s) — Alertes WARN sans activer relais   ║\n"
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
                device_id="capteur_demo_pro_modere",
                user=user,
                defaults={'name': "Station Modérée Founatek Pro"}
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

        # ❌ ANCIENNES RÈGLES INFO obsolètes — nettoyage
        old_codes = ['HIGH_TEMP', 'HIGH_HUM']
        n_old = SensorRule.objects.filter(user=user, device=device, code__in=old_codes).count()
        if n_old > 0:
            SensorRule.objects.filter(user=user, device=device, code__in=old_codes).delete()
            self.stdout.write(self.style.WARNING(
                f"   🗑 {n_old} ancienne(s) règle(s) INFO obsolète(s) supprimée(s)"
            ))

        # Affichage récapitulatif des règles actives
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
        # 4. INJECTION TOUTES LES 10s — VALEURS MODÉRÉES
        # ==========================================
        # 🎯 OBJECTIF : déclencher uniquement des alertes WARN (PAS de CRITICAL, PAS de relais)
        # Toutes les valeurs sont entre WARN et CRITICAL
        self.stdout.write(self.style.WARNING(
            f"\n⚠️  Injection de {count} points MODÉRÉS dans '{device.name}' "
            f"(délai : {delay}s — cycle ESP32 réel)\n"
            f"📊 Objectif : alertes WARN sans activer les relais\n"
        ))
        self.stdout.write("─" * 70 + "\n")

        agent = FounatekAgent(user)
        alertes_initiales = AgentAlert.objects.filter(user=user).count()

        for i in range(1, count + 1):
            # Génération de valeurs MODÉRÉES réalistes (entre seuils WARN et CRITICAL)
            pm2p5 = round(22.0  + random.uniform(-3,  5),   2)   # 19-27 µg/m³   (>15 WARN, <35 CRIT)
            pm10  = round(60.0  + random.uniform(-5,  10),  2)   # 55-70 µg/m³   (>45 WARN, <150 CRIT)
            mq135 = round(450.0 + random.uniform(-20, 50),  1)   # 430-500 PPM   (>400 WARN, <700 CRIT)
            temp  = round(36.0  + random.uniform(-1,  2),   1)   # 35-38°C       (>35 WARN, <40 CRIT)
            hum   = round(82.0  + random.uniform(-2,  4),   1)   # 80-86%        (>80 WARN, <90 CRIT)

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

            # 🎯 État des relais après l'agent (doit rester OFF en modéré)
            relais_on = Relais.objects.filter(user=user, etat=True).values_list('num', flat=True)
            relais_marker = f" ⚡ Relais ON: {list(relais_on)}" if relais_on else ""

            alert_marker = f" 🚨 +{new_alerts} alerte(s)" if new_alerts > 0 else ""

            self.stdout.write(
                f"   [{i:03d}/{count}] " +
                self.style.WARNING(f"[MODÉRÉ] ") +
                f"PM2.5={pm2p5:5.1f} | PM10={pm10:5.1f} | Gaz={mq135:5.0f} | "
                f"T={temp:4.1f}°C | H={hum:4.1f}%" +
                self.style.WARNING(alert_marker) +
                self.style.ERROR(relais_marker)
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

        # État des relais (doivent tous être OFF en air modéré)
        self.stdout.write(self.style.HTTP_INFO("📡 État final des actionneurs :"))
        relais_list = Relais.objects.filter(user=user).order_by('num')
        relais_on_count = 0
        for r in relais_list:
            status = "🔴 ON (anormal !)" if r.etat else "💤 OFF (sécurité OK)"
            color  = self.style.ERROR if r.etat else self.style.SUCCESS
            self.stdout.write(color(f"   → Relais {r.num} ({r.nom}) : {status}"))
            if r.etat:
                relais_on_count += 1

        # Statistiques alertes par niveau
        self.stdout.write(self.style.HTTP_INFO("\n📊 Répartition des alertes générées :"))
        alertes_recentes = AgentAlert.objects.filter(
            user=user, device=device
        ).order_by('-created_at')[:nouvelles_alertes]
        
        n_info = sum(1 for a in alertes_recentes if a.level == 'INFO')
        n_warn = sum(1 for a in alertes_recentes if a.level == 'WARN')
        n_crit = sum(1 for a in alertes_recentes if a.level == 'CRITICAL')
        
        self.stdout.write(self.style.HTTP_INFO(f"   • INFO     : {n_info} alerte(s)"))
        self.stdout.write(self.style.WARNING(f"   • WARN     : {n_warn} alerte(s) ← attendu"))
        self.stdout.write(self.style.ERROR(f"   • CRITICAL : {n_crit} alerte(s) ← doit être 0"))

        # Détail des alertes générées
        self.stdout.write(self.style.HTTP_INFO("\n📢 Alertes générées par l'agent IA :"))
        if alertes_recentes:
            for a in alertes_recentes:
                level_color = {
                    'INFO':     self.style.HTTP_INFO,
                    'WARN':     self.style.WARNING,
                    'CRITICAL': self.style.ERROR,
                }.get(a.level, self.style.HTTP_INFO)
                self.stdout.write(level_color(
                    f"   • [{a.level:8s}] {a.sensor:12s} → {a.code} : {a.message}"
                ))
        else:
            self.stdout.write(self.style.SUCCESS("   ✅ Aucune nouvelle alerte (cooldown actif)"))

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
        if n_warn >= 3 and n_crit == 0 and relais_on_count == 0:
            self.stdout.write(self.style.SUCCESS(
                "   ✅ Gradation parfaite : WARN détectés, CRITICAL absents."
            ))
            self.stdout.write(self.style.SUCCESS(
                "   ✅ Aucun relais activé — l'agent ne déclenche les actionneurs que pour CRITICAL."
            ))
            self.stdout.write(self.style.SUCCESS(
                "   ✅ L'utilisateur est informé sans action mécanique inutile."
            ))
        elif n_crit > 0:
            self.stdout.write(self.style.ERROR(
                f"   ❌ {n_crit} alerte(s) CRITICAL — anormal en zone modérée, vérifier seuils."
            ))
        elif relais_on_count > 0:
            self.stdout.write(self.style.ERROR(
                f"   ❌ {relais_on_count} relais actif(s) — anormal en zone modérée."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"   ⚠️ {nouvelles_alertes} alerte(s) générée(s) — vérifier comportement attendu."
            ))

        self.stdout.write(self.style.HTTP_INFO(
            f"\n💡 Dashboard : badge AQI doit afficher ⚠️ MODÉRÉ (orange).\n"
        ))