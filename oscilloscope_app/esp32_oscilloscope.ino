// ============================================================
//  FOUNATEK OSCILLOSCOPE — Code ESP32
//  Envoie les données ADC vers l'oscilloscope Founatek
//  Branchement : CH1 → Pin 34, CH2 → Pin 35
// ============================================================

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ── CONFIGURATION ──────────────────────────────────────────
const char* WIFI_SSID     = "TON_WIFI";
const char* WIFI_PASSWORD = "TON_MOT_DE_PASSE";
const char* API_TOKEN     = "Token TON_TOKEN_FOUNATEK";
const char* SERVER_URL    = "http://founatek224.pythonanywhere.com/oscilloscope/api/ingest/";
const int   SESSION_ID    = 1;      // ID de ta session sur Founatek

// ── PARAMÈTRES D'ACQUISITION ───────────────────────────────
#define CH1_PIN       34     // ADC1 Channel 6 — entrée analogique CH1
#define CH2_PIN       35     // ADC1 Channel 7 — entrée analogique CH2
#define N_SAMPLES     200    // Nombre d'échantillons par envoi
#define SAMPLE_RATE   2000   // Hz — fréquence d'échantillonnage
#define V_REF         3.3    // Tension de référence ESP32 (V)
#define ADC_MAX       4095   // Résolution 12 bits

// ── VARIABLES ──────────────────────────────────────────────
float ch1_samples[N_SAMPLES];
float ch2_samples[N_SAMPLES];
float time_samples[N_SAMPLES];
unsigned long lastSend = 0;
int sendInterval = 500;  // ms entre chaque envoi (ajustable)

// ── SETUP ──────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println("════════════════════════════════════");
  Serial.println("  FOUNATEK OSCILLOSCOPE — ESP32");
  Serial.println("════════════════════════════════════");

  // Configuration ADC
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);  // Plage 0-3.3V

  // Connexion WiFi
  connectWiFi();
}

// ── LOOP ───────────────────────────────────────────────────
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Reconnexion...");
    connectWiFi();
  }

  unsigned long now = millis();
  if (now - lastSend >= sendInterval) {
    lastSend = now;
    acquireAndSend();
  }
}

// ── CONNEXION WIFI ─────────────────────────────────────────
void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[WiFi] Connexion");
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 20) {
    delay(500); Serial.print("."); tries++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] ✅ Connecté — IP: " + WiFi.localIP().toString());
  } else {
    Serial.println("\n[WiFi] ❌ Échec de connexion");
  }
}

// ── ACQUISITION + ENVOI ────────────────────────────────────
void acquireAndSend() {
  Serial.println("[ACQ] Acquisition...");

  long dt_us = 1000000L / SAMPLE_RATE;  // µs entre chaque sample

  // Acquérir N_SAMPLES échantillons
  for (int i = 0; i < N_SAMPLES; i++) {
    unsigned long t_start = micros();

    // Lire les deux canaux
    int raw1 = analogRead(CH1_PIN);
    int raw2 = analogRead(CH2_PIN);

    // Convertir en tension (0 → 3.3V)
    ch1_samples[i]  = (raw1 / (float)ADC_MAX) * V_REF;
    ch2_samples[i]  = (raw2 / (float)ADC_MAX) * V_REF;
    time_samples[i] = (i * 1000.0f) / SAMPLE_RATE;  // temps en ms

    // Attendre le bon interval
    while (micros() - t_start < dt_us);
  }

  Serial.printf("[ACQ] ✅ %d samples acquis (CH1 max: %.3fV, CH2 max: %.3fV)\n",
    N_SAMPLES,
    *std::max_element(ch1_samples, ch1_samples + N_SAMPLES),
    *std::max_element(ch2_samples, ch2_samples + N_SAMPLES)
  );

  // Envoyer CH1
  sendChannel(1, ch1_samples, time_samples);
  delay(100);
  // Envoyer CH2
  sendChannel(2, ch2_samples, time_samples);
}

// ── ENVOI D'UN CANAL ───────────────────────────────────────
void sendChannel(int channel, float* voltages, float* times) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Authorization", API_TOKEN);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(8000);

  // Construire le JSON manuellement (économie mémoire)
  String body = "{\"session_id\":" + String(SESSION_ID)
              + ",\"channel\":" + String(channel)
              + ",\"sample_rate\":" + String(SAMPLE_RATE)
              + ",\"samples\":[";

  for (int i = 0; i < N_SAMPLES; i++) {
    body += "{\"t\":" + String(times[i], 3)
         + ",\"v\":" + String(voltages[i], 4) + "}";
    if (i < N_SAMPLES - 1) body += ",";
  }
  body += "]}";

  Serial.printf("[HTTP] Envoi CH%d → %d octets\n", channel, body.length());

  int code = http.POST(body);
  if (code == 201) {
    Serial.printf("[HTTP] ✅ CH%d envoyé (201)\n", channel);
  } else if (code == 403) {
    Serial.println("[HTTP] ❌ Token invalide ou quota dépassé (403)");
  } else {
    Serial.printf("[HTTP] ❌ Erreur %d : %s\n", code, http.getString().c_str());
  }
  http.end();
}
