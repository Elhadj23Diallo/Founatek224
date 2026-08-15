# espcontrol/management/commands/test_founatek_melange.py
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
    help = "Simulation Air Mélangé : injection toutes les 10s (cycle ESP32 réel) avec scénarios variés"

    def add_arguments(self, parser):
        parser.add_argument('--user',  type=str, help="Nom d'utilisateur (ex: elhadj)")
        parser.add_argument('--count', type=int, default=30,
                            help="Nombre de points (défaut : 30 = 5 min de simulation)")
        parser.add_argument('--delay', type=float, default=10.0,
                            help="Délai entre chaque point en secondes (défaut : 10s = cycle ESP32 réel)")
        parser.add_argument('--device_name', type=str, default='Device Station 001 QA Ratoma',
                            help="Nom de la station à utiliser (défaut : station réelle Ratoma)")

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
        # 1. PRÉPARATION
        # ==========================================
        self.stdout.write(self.style.HTTP_INFO(
            "\n╔══════════════════════════════════════════════════════════════╗\n"
            "║  🌪️  SIMULATION AIR MÉLANGÉ — FOUNATEK NEXUS                ║\n"
            "║  Cycle ESP32 réel (10s) — Scénarios complets bon→critique    ║\n"
            "╚══════════════════════════════════════════════════════════════╝\n"
        ))

        # Récupère la station réelle ou en crée une de test
        try:
            device = Device.objects.get(user=user, name=device_name)
            self.stdout.write(f"✅ Station trouvée : {device.name} ({device.device_id})\n")
        except Device.DoesNotExist:
            device, _ = Device.objects.get_or_create(
                device_id="capteur_demo_pro_melange",
                user=user,
                defaults={'name': "Station mélangée Founatek Pro"}
            )
            self.stdout.write(f"⚠️ Station par défaut créée : {device.name}\n")

        # S'assure que les 3 relais existent avec des noms cohérents
        relais_config = [
            (1, "Ventilateur / Purificateur d'air"),
            (2, "Extracteur d'air (gaz toxiques)"),
            (3, "Climatiseur / Déshumidificateur"),
        ]
        for num, nom in relais_config:
            relais, created = Relais.objects.get_or_create(
                user=user, num=num,
                defaults={'nom': nom}
            )
            # Met à jour le nom si différent
            if relais.nom != nom:
                relais.nom = nom
                relais.save(update_fields=['nom'])

        # ==========================================
        # 1bis. CRÉATION / MISE À JOUR DES RÈGLES OMS COMPLÈTES
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

            # ────────── TEMPÉRATURE (NOUVEAU : gradation complète) ──────────
            ('temperature', 35,   'WARN',     'WARN_TEMP',
             'Température élevée (>35°C) — Inconfort thermique',
             'alert', 3),
            ('temperature', 40,   'CRITICAL', 'CRITICAL_TEMP',
             'Chaleur DANGEREUSE (>40°C) — Climatiseur ACTIVÉ automatiquement !',
             'START_IRRIGATION', 3),

            # ────────── HUMIDITÉ (NOUVEAU : gradation complète) ──────────
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
                # 🔄 Met à jour les règles existantes (corriger anciens action_type)
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
        # 2. SCÉNARIOS DE POLLUTION ENRICHIS
        # ==========================================
        # 🎯 Mise à jour : ajout de pics de chaleur et d'humidité critiques
        # pour démontrer l'activation du Relais 3
        scenarios = [
            # ─── PHASE 1 (mesures 1-5) : Air BON ───────────────────────
            {"phase": "BON",   "pm2p5": (8, 2),   "pm10": (20, 3),  "mq135": (150, 20),
             "temp": (28, 1), "hum": (60, 5), "desc": "Air sain matinal"},
            {"phase": "BON",   "pm2p5": (9, 2),   "pm10": (22, 3),  "mq135": (160, 20),
             "temp": (28, 1), "hum": (62, 5), "desc": "Air sain stable"},
            {"phase": "BON",   "pm2p5": (10, 2),  "pm10": (24, 3),  "mq135": (170, 20),
             "temp": (29, 1), "hum": (63, 5), "desc": "Légère augmentation"},
            {"phase": "BON",   "pm2p5": (11, 2),  "pm10": (26, 3),  "mq135": (180, 20),
             "temp": (29, 1), "hum": (64, 5), "desc": "Trafic léger"},
            {"phase": "BON",   "pm2p5": (12, 2),  "pm10": (28, 3),  "mq135": (200, 20),
             "temp": (30, 1), "hum": (65, 5), "desc": "Activité urbaine"},

            # ─── PHASE 2 (mesures 6-10) : Pic CIGARETTE (ponctuel) ─────
            {"phase": "PIC",   "pm2p5": (45, 3),  "pm10": (60, 5),  "mq135": (250, 25),
             "temp": (30, 1), "hum": (65, 5), "desc": "🚬 CIGARETTE — pic ponctuel"},
            {"phase": "BON",   "pm2p5": (12, 2),  "pm10": (28, 3),  "mq135": (200, 20),
             "temp": (30, 1), "hum": (65, 5), "desc": "Cigarette dispersée — retour normal"},
            {"phase": "BON",   "pm2p5": (11, 2),  "pm10": (27, 3),  "mq135": (190, 20),
             "temp": (30, 1), "hum": (64, 5), "desc": "Air bon stabilisé"},
            {"phase": "BON",   "pm2p5": (13, 2),  "pm10": (29, 3),  "mq135": (210, 20),
             "temp": (31, 1), "hum": (65, 5), "desc": "Mi-journée"},
            {"phase": "BON",   "pm2p5": (14, 2),  "pm10": (32, 3),  "mq135": (220, 20),
             "temp": (31, 1), "hum": (66, 5), "desc": "Activité normale"},

            # ─── PHASE 3 (mesures 11-15) : Pollution MODÉRÉE + Chaleur WARN ───
            # 🆕 La température dépasse 35°C → alerte WARN_TEMP attendue
            {"phase": "MOD",   "pm2p5": (22, 3),  "pm10": (55, 4),  "mq135": (350, 30),
             "temp": (34, 1), "hum": (70, 5), "desc": "⚠️ Embouteillage + chaleur"},
            {"phase": "MOD",   "pm2p5": (24, 3),  "pm10": (58, 4),  "mq135": (380, 30),
             "temp": (35, 1), "hum": (72, 5), "desc": "⚠️ Trafic dense + T>35°C"},
            {"phase": "MOD",   "pm2p5": (26, 3),  "pm10": (62, 4),  "mq135": (410, 30),
             "temp": (36, 1), "hum": (75, 5), "desc": "⚠️ Gaz d'échappement + chaleur"},
            {"phase": "MOD",   "pm2p5": (28, 3),  "pm10": (65, 4),  "mq135": (420, 30),
             "temp": (37, 1), "hum": (78, 5), "desc": "⚠️ Inconfort thermique"},
            {"phase": "MOD",   "pm2p5": (30, 3),  "pm10": (68, 4),  "mq135": (430, 30),
             "temp": (38, 1), "hum": (80, 5), "desc": "⚠️ Limite WARN_HUM"},

                # ─── PHASE 4 (mesures 16-20) : CRITIQUE complet (PM, gaz, T, HR) ─
            {"phase": "MAUVAIS", "pm2p5": (42, 4), "pm10": (95, 5),  "mq135": (780, 30),
             "temp": (39, 1), "hum": (82, 5), "desc": "🔴 ALERTE — Pollution critique"},
            {"phase": "MAUVAIS", "pm2p5": (45, 4), "pm10": (110, 5), "mq135": (820, 30),
             "temp": (40, 1), "hum": (86, 5), "desc": "🔴 Chaleur critique + pollution"},
            {"phase": "MAUVAIS", "pm2p5": (48, 4), "pm10": (130, 5), "mq135": (860, 30),
             "temp": (41, 1), "hum": (88, 5), "desc": "🔴 Pic chaleur (>40°C) — Relais 3"},
            {"phase": "MAUVAIS", "pm2p5": (50, 4), "pm10": (140, 5), "mq135": (880, 30),
             "temp": (42, 1), "hum": (91, 5), "desc": "🔴 Pic gaz + humidité critique"},
            {"phase": "MAUVAIS", "pm2p5": (46, 4), "pm10": (135, 5), "mq135": (850, 30),
             "temp": (42, 1), "hum": (92, 5), "desc": "🔴 Tous les seuils dépassés"},

            # ─── PHASE 5 (mesures 21-25) : Retour MODÉRÉ ───────────────
            {"phase": "MOD",   "pm2p5": (25, 3),  "pm10": (60, 4),  "mq135": (400, 30),
             "temp": (38, 1), "hum": (82, 5), "desc": "⚠️ Amélioration progressive"},
            {"phase": "MOD",   "pm2p5": (22, 3),  "pm10": (55, 4),  "mq135": (380, 30),
             "temp": (36, 1), "hum": (78, 5), "desc": "⚠️ Trafic se dissipe"},
            {"phase": "MOD",   "pm2p5": (20, 3),  "pm10": (50, 4),  "mq135": (360, 30),
             "temp": (34, 1), "hum": (74, 5), "desc": "⚠️ Légèrement modéré"},
            {"phase": "BON",   "pm2p5": (16, 2),  "pm10": (40, 3),  "mq135": (300, 25),
             "temp": (32, 1), "hum": (70, 5), "desc": "Quasi normal"},
            {"phase": "BON",   "pm2p5": (14, 2),  "pm10": (35, 3),  "mq135": (260, 20),
             "temp": (31, 1), "hum": (68, 5), "desc": "Retour à la normale"},

            # ─── PHASE 6 (mesures 26-30) : Air BON stabilisé ───────────
            {"phase": "BON",   "pm2p5": (12, 2),  "pm10": (30, 3),  "mq135": (230, 20),
             "temp": (30, 1), "hum": (66, 5), "desc": "Air bon en fin de journée"},
            {"phase": "BON",   "pm2p5": (10, 2),  "pm10": (26, 3),  "mq135": (210, 20),
             "temp": (29, 1), "hum": (64, 5), "desc": "Soirée calme"},
            {"phase": "BON",   "pm2p5": (9, 2),   "pm10": (23, 3),  "mq135": (190, 20),
             "temp": (28, 1), "hum": (62, 5), "desc": "Air sain stable"},
            {"phase": "BON",   "pm2p5": (8, 2),   "pm10": (21, 3),  "mq135": (170, 20),
             "temp": (28, 1), "hum": (61, 5), "desc": "Air pur nocturne"},
            {"phase": "BON",   "pm2p5": (8, 2),   "pm10": (20, 3),  "mq135": (160, 20),
             "temp": (27, 1), "hum": (60, 5), "desc": "✅ Stabilisation finale"},
        ]

        # Couleur par phase pour l'affichage
        phase_colors = {
            "BON":     self.style.SUCCESS,
            "PIC":     self.style.WARNING,
            "MOD":     self.style.WARNING,
            "MAUVAIS": self.style.ERROR,
        }

        # ==========================================
        # 3. INJECTION TOUTES LES 10s
        # ==========================================
        self.stdout.write(self.style.SUCCESS(
            f"\n📊 Injection de {count} points dans '{device.name}' "
            f"(délai : {delay}s — cycle ESP32 réel)\n"
        ))
        self.stdout.write("─" * 70 + "\n")

        agent = FounatekAgent(user)
        alertes_initiales = AgentAlert.objects.filter(user=user).count()

        for i in range(count):
            sc = scenarios[i % len(scenarios)]
            phase = sc["phase"]

            # Générer la mesure avec un peu de bruit aléatoire
            pm2p5 = round(sc["pm2p5"][0] + random.uniform(-sc["pm2p5"][1], sc["pm2p5"][1]), 2)
            pm10  = round(sc["pm10"][0]  + random.uniform(-sc["pm10"][1],  sc["pm10"][1]),  2)
            mq135 = round(sc["mq135"][0] + random.uniform(-sc["mq135"][1], sc["mq135"][1]), 1)
            temp  = round(sc["temp"][0]  + random.uniform(-sc["temp"][1],  sc["temp"][1]),  1)
            hum   = round(sc["hum"][0]   + random.uniform(-sc["hum"][1],   sc["hum"][1]),   1)

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

            # L'agent analyse immédiatement (comme en temps réel)
            alertes_avant = AgentAlert.objects.filter(user=user).count()
            report = agent.run()
            alertes_apres = AgentAlert.objects.filter(user=user).count()
            new_alerts = alertes_apres - alertes_avant

            # 🎯 Vérification de l'état des relais après l'agent
            relais_on = Relais.objects.filter(user=user, etat=True).values_list('num', flat=True)
            relais_marker = f" ⚡ Relais ON: {list(relais_on)}" if relais_on else ""

            # Affichage formaté
            color = phase_colors.get(phase, self.style.HTTP_INFO)
            alert_marker = f" 🚨 +{new_alerts} alerte(s)" if new_alerts > 0 else ""

            self.stdout.write(
                f"   [{i+1:03d}/{count}] " +
                color(f"[{phase:8s}] ") +
                f"PM2.5={pm2p5:5.1f} | PM10={pm10:5.1f} | Gaz={mq135:5.0f} | "
                f"T={temp:4.1f}°C | H={hum:4.1f}% — {sc['desc']}" +
                self.style.ERROR(alert_marker) +
                self.style.WARNING(relais_marker)
            )

            if delay > 0 and i < count - 1:
                time.sleep(delay)

        # ==========================================
        # 4. BILAN FINAL
        # ==========================================
        self.stdout.write("\n" + "─" * 70)
        self.stdout.write(self.style.HTTP_INFO("\n🎯 BILAN FINAL DE LA SIMULATION\n"))

        alertes_finales = AgentAlert.objects.filter(user=user).count()
        nouvelles_alertes = alertes_finales - alertes_initiales

        # État des relais
        self.stdout.write(self.style.HTTP_INFO("📡 État final des actionneurs :"))
        relais_list = Relais.objects.filter(user=user).order_by('num')
        for r in relais_list:
            status = "🔴 ON" if r.etat else "💤 OFF"
            color  = self.style.ERROR if r.etat else self.style.SUCCESS
            self.stdout.write(color(f"   → Relais {r.num} ({r.nom}) : {status}"))

        # Statistiques alertes par niveau
        self.stdout.write(self.style.HTTP_INFO("\n📊 Répartition des alertes par niveau :"))
        for level in ['INFO', 'WARN', 'CRITICAL']:
            count_level = AgentAlert.objects.filter(
                user=user, device=device, level=level
            ).order_by('-created_at')[:nouvelles_alertes].count()
            level_color = {
                'INFO':     self.style.HTTP_INFO,
                'WARN':     self.style.WARNING,
                'CRITICAL': self.style.ERROR,
            }.get(level, self.style.HTTP_INFO)
            self.stdout.write(level_color(f"   • {level:8s} : {count_level} alerte(s)"))

        # Détail des alertes générées
        self.stdout.write(self.style.HTTP_INFO("\n📢 Alertes générées par l'agent IA :"))
        alertes_recentes = AgentAlert.objects.filter(
            user=user, device=device
        ).order_by('-created_at')[:nouvelles_alertes]

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
            self.stdout.write(self.style.SUCCESS("   ✅ Aucune nouvelle alerte (cooldown actif ou air bon)"))

        # Résumé chiffré
        actions_count = ActionLog.objects.filter(user=user).count()
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Simulation terminée :"
        ))
        self.stdout.write(f"   📊 Points injectés       : {count}")
        self.stdout.write(f"   🚨 Nouvelles alertes IA  : {nouvelles_alertes}")
        self.stdout.write(f"   📋 Total alertes en base : {alertes_finales}")
        self.stdout.write(f"   📝 Actions journalisées  : {actions_count}")

        # Analyse pédagogique
        self.stdout.write(self.style.HTTP_INFO("\n🧠 ANALYSE PÉDAGOGIQUE :"))
        if nouvelles_alertes >= 5:
            self.stdout.write(self.style.SUCCESS(
                "   ✅ L'agent IA a bien détecté les pollutions et anomalies climatiques."
            ))
            self.stdout.write(self.style.SUCCESS(
                "   ✅ Les 3 actionneurs (ventilateur, extracteur, climatiseur) ont été activés."
            ))
            self.stdout.write(self.style.SUCCESS(
                "   ✅ La moyenne glissante filtre les pics ponctuels (cigarette)."
            ))
            self.stdout.write(self.style.SUCCESS(
                "   ✅ Le cooldown 10min évite le spam d'alertes."
            ))
        elif nouvelles_alertes == 0:
            self.stdout.write(self.style.WARNING(
                "   ⚠️ Aucune alerte — vérifier les règles SensorRule actives."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"   ✅ {nouvelles_alertes} alerte(s) générée(s) — système réactif."
            ))

        self.stdout.write(self.style.HTTP_INFO(
            f"\n💡 Dashboard : visualiser l'évolution en temps réel sur le site.\n"
        ))