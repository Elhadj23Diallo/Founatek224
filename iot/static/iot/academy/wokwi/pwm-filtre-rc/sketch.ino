const int PWM = 9;
void setup() { Serial.begin(9600); pinMode(PWM, OUTPUT); }
void loop() {
  for (int r : {64, 128, 192, 255}) {
    analogWrite(PWM, r);
    delay(1000);
    float u = analogRead(A0) * 5.0 / 1023.0;
    Serial.print(r); Serial.print(" -> ");
    Serial.print(u, 2); Serial.println(" V");
  }
}
