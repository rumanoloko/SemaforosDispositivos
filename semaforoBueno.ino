#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// Configuración WiFi
const char* ssid = "holahola";
const char* password = "holahola";

// Configuración MQTT
const char* mqtt_server = "192.168.45.190";
const char* topic_core_sender_0 = "core_0_sender";
const char* topic_core_sender_1 = "core_1_sender";
const char* topic_core_seleccionado = "core_seleccionado";

// Pines Core 0
const int alimentacionBotonAbajo = 16;
const int lectorBotonAbajo = 17;
const int alimentacionBotonArriba = 12;
const int lectorBotonArriba = 14;

const int ledRojoCore0 = 4;
const int ledVerdeCore0 = 2;

// Pines Core 1
const int alimentacionBotonDerecha = 19;
const int lecturaBotonDerecha = 21;
const int alimentacionBotonIzquierda = 33;
const int lecturaBotonIzquierda = 25;

const int ledRojoCore1 = 18;
const int ledVerdeCore1 = 5;
// Variables globales
bool prioridadPeatones_core0 = false;
bool prioridadPeatones_core1 = false;
int cola_abajo = 0;
int cola_arriba = 0;
int cola_derecha = 0;
int cola_izquierda = 0;
const float tasaLlegada = 0.85;

WiFiClient espClient0, espClient1;
PubSubClient client0(espClient0);
PubSubClient client1(espClient1);

int generarPoisson(float lambda) {
    float L = exp(-lambda);
    float p = 1.0;
    int k = 0;
    do {
        k++;
        p *= (float)random(0, 10000) / 10000.0;
    } while (p > L);
    return k - 1;
}

void setup_wifi() {
    delay(10);
    Serial.println("Conectando a WiFi...");
    WiFi.begin(ssid, password);

    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nConectado a WiFi.");
}


void callbackCore0(char* topic, byte* payload, unsigned int length) {
    Serial.print("Core 0 - Mensaje recibido en tópico: ");
    Serial.println(topic);

    DynamicJsonDocument jsonDoc(200);
    DeserializationError error = deserializeJson(jsonDoc, payload, length);
    if (error) {
        Serial.print("Core 0 - Error al deserializar JSON: ");
        Serial.println(error.f_str());
        return;
    }

    int coreSeleccionado = jsonDoc["coreSeleccionado"];
    prioridadPeatones_core0 = (coreSeleccionado == 0);

    Serial.print("Core 0 - Prioridad peatones actualizada a: ");
    Serial.println(prioridadPeatones_core0);
}

void callbackCore1(char* topic, byte* payload, unsigned int length) {
    Serial.print("Core 1 - Mensaje recibido en tópico: ");
    Serial.println(topic);

    DynamicJsonDocument jsonDoc(200);
    DeserializationError error = deserializeJson(jsonDoc, payload, length);
    if (error) {
        Serial.print("Core 1 - Error al deserializar JSON: ");
        Serial.println(error.f_str());
        return;
    }

    int coreSeleccionado = jsonDoc["coreSeleccionado"];
    prioridadPeatones_core1 = (coreSeleccionado == 1);

    Serial.print("Core 1 - Prioridad peatones actualizada a: ");
    Serial.println(prioridadPeatones_core1);
}

void publicarMensaje(int core, int primeraCola, int segundaCola, int primerBoton, int segundoBoton) {
    DynamicJsonDocument jsonDoc(200);
    jsonDoc["primera_cola"] = primeraCola;
    jsonDoc["segunda_cola"] = segundaCola;
    jsonDoc["primer_boton"] = primerBoton;
    jsonDoc["segundo_boton"] = segundoBoton;

    if (core == 0) {
        jsonDoc["prioridadPeatones"] = prioridadPeatones_core0;
        char buffer[200];
        serializeJson(jsonDoc, buffer);
        client0.publish(topic_core_sender_0, buffer);

        //Serial.print("Core 0 publicado: ");
        //Serial.println(buffer);
    } else if (core == 1) {
        jsonDoc["prioridadPeatones"] = prioridadPeatones_core1;
        char buffer[200];
        serializeJson(jsonDoc, buffer);
        client1.publish(topic_core_sender_1, buffer);

        //Serial.print("Core 1 publicado: ");
        //Serial.println(buffer);
    }
}

void manejarCore0(void* pvParameters) {
    client0.setServer(mqtt_server, 1883);
    client0.setCallback(callbackCore0);

    while (!client0.connected()) {
        Serial.println("Core 0 - Conectando al broker MQTT...");
        if (client0.connect("ESP32_Core0")) {
            client0.subscribe(topic_core_seleccionado);
            Serial.println("Core 0 - Suscrito correctamente!");
        } else {
          Serial.print("Core 0 - Falló la conexión. Código de error: ");
          Serial.println(client0.state());
        }
        delay(1000);
    }
    pinMode(lectorBotonAbajo, INPUT_PULLDOWN);
    pinMode(lectorBotonArriba, INPUT_PULLDOWN);
    pinMode(alimentacionBotonAbajo, OUTPUT);
    pinMode(alimentacionBotonArriba, OUTPUT);
    digitalWrite(alimentacionBotonAbajo, HIGH);
    digitalWrite(alimentacionBotonArriba, HIGH);
    pinMode(ledRojoCore0, OUTPUT);
    pinMode(ledVerdeCore0, OUTPUT);

    while (true) {
        client0.loop();
        if (!prioridadPeatones_core0) {
            digitalWrite(ledRojoCore0, HIGH);
            digitalWrite(ledVerdeCore0, LOW);
        } else {
            cola_abajo -= 2;
            cola_arriba -= 2;
            if (cola_abajo < 0) {
                cola_abajo = 0;
            }
            if (cola_arriba < 0) {
                cola_arriba = 0;
            }
            digitalWrite(ledRojoCore0, LOW);
            digitalWrite(ledVerdeCore0, HIGH);
        }
        int estadoPrimerBoton = 0;
        int estadoSegundoBoton = 0;
        if (digitalRead(lectorBotonAbajo) == HIGH) {
          estadoPrimerBoton = 1;
        }
        if (digitalRead(lectorBotonArriba) == HIGH) {
          estadoSegundoBoton = 1;
        }
        int llegadas = generarPoisson(tasaLlegada);
        int llegadas2 = generarPoisson(tasaLlegada);
        cola_abajo += llegadas;
        cola_arriba += llegadas2;
        publicarMensaje(0, cola_abajo, cola_arriba, estadoPrimerBoton, estadoSegundoBoton);
        delay(1000);
    }
}

// Tarea para Core 1
void manejarCore1(void* pvParameters) {
    client1.setServer(mqtt_server, 1883);
    client1.setCallback(callbackCore1);
    while (!client1.connected()) {
        Serial.println("Core 1 - Conectando al broker MQTT...");
        if (client1.connect("ESP32_Core1")) {
            client1.subscribe(topic_core_seleccionado);
            Serial.println("Core 1 - Suscrito correctamente!");
        } else {
          Serial.print("Core 1 - Falló la conexión. Código de error: ");
          Serial.println(client1.state());
        }
        delay(1000);
    }

    pinMode(lecturaBotonDerecha, INPUT_PULLDOWN);
    pinMode(lecturaBotonIzquierda, INPUT_PULLDOWN);
    pinMode(alimentacionBotonDerecha, OUTPUT);
    pinMode(alimentacionBotonIzquierda, OUTPUT);
    digitalWrite(alimentacionBotonDerecha, HIGH);
    digitalWrite(alimentacionBotonIzquierda, HIGH);
    pinMode(ledRojoCore1, OUTPUT);
    pinMode(ledVerdeCore1, OUTPUT);

    while (true) {
        client1.loop(); // Procesar mensajes entrantes
        if (!prioridadPeatones_core1) {
            digitalWrite(ledRojoCore1, HIGH);
            digitalWrite(ledVerdeCore1, LOW);
        } else {
            cola_derecha -= 2;
            cola_izquierda -= 2;
            if(cola_derecha < 0){
                cola_derecha = 0;
            }
            if(cola_izquierda < 0){
                cola_izquierda = 0;
            }
            digitalWrite(ledRojoCore1, LOW);
            digitalWrite(ledVerdeCore1, HIGH);
        }

        int estadoBoton = 0;
        int estadoBoton2 = 0;
        if (digitalRead(lecturaBotonDerecha) == HIGH) {
          estadoBoton = 1;
        }
        if (digitalRead(lecturaBotonIzquierda) == HIGH) {
          estadoBoton2 = 1;
        }

        int llegadas = generarPoisson(tasaLlegada);
        int llegadas2 = generarPoisson(tasaLlegada);
        cola_derecha += llegadas;
        cola_izquierda += llegadas2;
        publicarMensaje(1, cola_derecha, cola_izquierda, estadoBoton, estadoBoton2);

        delay(1000);
    }
}
void setup() {
    Serial.begin(115200);
    setup_wifi();

    xTaskCreatePinnedToCore(manejarCore0, "Tarea Core 0", 10000, NULL, 1, NULL, 0);
    xTaskCreatePinnedToCore(manejarCore1, "Tarea Core 1", 10000, NULL, 1, NULL, 1);
}
void loop() {}