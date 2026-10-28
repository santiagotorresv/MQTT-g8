#include "ConexionWifi.h"

#include <Arduino.h>
#include <WiFi.h>
#include <string.h>

ConexionWifi::ConexionWifi(const char* nombreRed, const char* claveRed)
    : nombreRed_(nombreRed), claveRed_(claveRed) {}

void ConexionWifi::iniciar() {
    if (nombreRed_ == nullptr || claveRed_ == nullptr || nombreRed_[0] == '\0' ||
        strlen(nombreRed_) > 32 || strlen(claveRed_) > 64) {
        Serial.println(F("WiFi: configuracion ausente o no valida. Control local activo."));
        return;
    }

    // La clase programa los reintentos; evitar escrituras de configuracion en NVS.
    WiFi.persistent(false);
    WiFi.setAutoReconnect(false);
    if (claveRed_[0] == '\0') {
        WiFi.setMinSecurity(WIFI_AUTH_OPEN);
    }

    habilitada_ = true;
    Serial.println(F("WiFi: iniciando conexion."));
    intentarConectar();
}

void ConexionWifi::intentarConectar() {
    ultimoIntentoMs_ = millis();
    if (!WiFi.mode(WIFI_STA)) {
        Serial.println(F("WiFi: no se pudo iniciar el modo estacion. Se reintentara."));
        return;
    }

    // Cancelar el intento anterior sin apagar la radio ni borrar configuracion.
    WiFi.disconnect(false, false);
    if (WiFi.begin(nombreRed_, claveRed_) == WL_CONNECT_FAILED) {
        Serial.println(F("WiFi: no se pudo iniciar el intento. Se reintentara."));
    }
}

bool ConexionWifi::estaConectada() const {
    return habilitada_ && WiFi.status() == WL_CONNECTED;
}

void ConexionWifi::actualizar() {
    if (!habilitada_) {
        return;
    }

    if (estaConectada()) {
        if (!estabaConectada_) {
            Serial.print(F("WiFi: conexion establecida. IP: "));
            Serial.println(WiFi.localIP());
            estabaConectada_ = true;
        }
        return;
    }

    if (estabaConectada_) {
        Serial.println(F("WiFi: conexion perdida. Reintento en 15 s."));
        estabaConectada_ = false;
        ultimoIntentoMs_ = millis();
    }

    // La resta sin signo mantiene el intervalo al desbordarse millis().
    if (millis() - ultimoIntentoMs_ >= IntervaloReintentoMs) {
        Serial.println(F("WiFi: reintentando conexion."));
        intentarConectar();
    }
}
