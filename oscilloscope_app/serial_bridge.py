#!/usr/bin/env python3
"""
FOUNATEK OSCILLOSCOPE — Bridge Arduino Série → API
Lit les données du port COM et les envoie vers Founatek

Usage:
  python serial_bridge.py --port COM3 --session 1 --token "Token VOTRE_TOKEN"
  python serial_bridge.py --port /dev/ttyUSB0 --session 1 --token "Token TON_TOKEN"

Format attendu depuis Arduino (Serial.println) :
  CH1:1.65,0.32,1.82,2.10,...  (valeurs tension séparées par virgule)
  CH2:0.45,1.20,0.88,...
"""

import serial
import requests
import argparse
import time
import sys

def send_to_founatek(session_id, channel, samples, token, base_url):
    url = f"{base_url}/oscilloscope/api/ingest/"
    payload = {
        "session_id":  session_id,
        "channel":     channel,
        "sample_rate": 1000,
        "samples":     samples,
    }
    try:
        r = requests.post(url, json=payload,
                          headers={"Authorization": token}, timeout=8)
        print(f"[HTTP] CH{channel} → {r.status_code}")
        return r.status_code == 201
    except Exception as e:
        print(f"[HTTP] Erreur: {e}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port',    default='COM3')
    parser.add_argument('--baud',    default=115200, type=int)
    parser.add_argument('--session', default=1, type=int)
    parser.add_argument('--token',   required=True)
    parser.add_argument('--url',     default='http://founatek224.pythonanywhere.com')
    args = parser.parse_args()

    print(f"[BRIDGE] Connexion {args.port} @ {args.baud} baud")
    try:
        ser = serial.Serial(args.port, args.baud, timeout=2)
        print("[BRIDGE] ✅ Port série ouvert")
    except Exception as e:
        print(f"[BRIDGE] ❌ Erreur port série: {e}")
        sys.exit(1)

    sample_rate = 1000
    dt = 1000.0 / sample_rate  # ms

    while True:
        try:
            line = ser.readline().decode('utf-8').strip()
            if not line:
                continue

            # Format: CH1:v1,v2,v3,...
            if line.startswith('CH1:') or line.startswith('CH2:'):
                parts = line.split(':')
                ch    = int(parts[0][2])
                vals  = [float(x) for x in parts[1].split(',') if x]
                samples = [{'t': round(i * dt, 3), 'v': v}
                           for i, v in enumerate(vals)]
                print(f"[BRIDGE] CH{ch}: {len(samples)} samples")
                send_to_founatek(args.session, ch, samples, args.token, args.url)
            else:
                print(f"[Arduino] {line}")

        except KeyboardInterrupt:
            print("\n[BRIDGE] Arrêté.")
            ser.close()
            break
        except Exception as e:
            print(f"[BRIDGE] Erreur: {e}")

if __name__ == '__main__':
    main()
