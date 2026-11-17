const float R2 = 1000.0;
void setup() { Serial.begin(9600); }
void loop() {
  int brut = analogRead(A0);
  float u = brut * 5.0 / 1023.0;
  float i = u / R2 * 1000.0;
  Serial.print("U2 = "); Serial.print(u, 2);
  Serial.print(" V ; I = "); Serial.print(i, 2);
  Serial.println(" mA");
  delay(1000);
}
