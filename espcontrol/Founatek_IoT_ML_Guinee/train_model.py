import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib

# =========================
# 1️⃣ Chargement des données
# =========================
data = pd.read_csv("founatek_iot_guinee.csv")

# Colonnes utilisées pour l'entraînement
FEATURES = [
    "temperature_c",
    "humidity_air",
    "soil_moisture",
    "rainfall_mm",
    "hour"
]

TARGET = "irrigation"

X = data[FEATURES]
y = data[TARGET]

# =========================
# 2️⃣ Séparation train / test
# =========================
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# =========================
# 3️⃣ Entraînement du modèle
# =========================
model = RandomForestClassifier(
    n_estimators=100,
    random_state=42
)
model.fit(X_train, y_train)

# =========================
# 4️⃣ Évaluation
# =========================
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print(f"Model accuracy: {accuracy:.2f}")

# =========================
# 5️⃣ Sauvegarde du modèle
# =========================
joblib.dump(model, "irrigation_model.pkl")
print("✅ Modèle sauvegardé : irrigation_model.pkl")

# =========================
# 6️⃣ Prédiction de test
# =========================
sample_data = {
    "temperature_c": 34,
    "humidity_air": 60,
    "soil_moisture": 20,
    "rainfall_mm": 0,
    "hour": 15
}

sample_df = pd.DataFrame([sample_data], columns=FEATURES)
prediction = model.predict(sample_df)[0]

print("🌱 Irrigation needed :", "YES" if prediction == 1 else "NO")
