#include "ConexionMqtt.h"

#include <math.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#if __has_include("ConfiguracionMqtt.h")
#include "ConfiguracionMqtt.h"
#else
#include "ConfiguracionMqtt.ejemplo.h"
#endif

// PlatformIO incorpora el PEM original y agrega el terminador de texto.
extern const char CertificadoCaEmqx[] asm("_binary_certificados_emqxsl_ca_crt_start");

namespace {

constexpr char TemaDistancia[] = "sis234/equipo08/esp32-01/telemetry/distance_cm";
constexpr char TemaSensor[] = "sis234/equipo08/esp32-01/telemetry/sensor_status";
constexpr char TemaComandos[] = "sis234/equipo08/esp32-01/cmd";
constexpr char TemaRojo[] = "sis234/equipo08/esp32-01/state/rojo";
constexpr char TemaAmarillo[] = "sis234/equipo08/esp32-01/state/amarillo";
constexpr char TemaVerde[] = "sis234/equipo08/esp32-01/state/verde";
constexpr char TemaDisponibilidad[] = "sis234/equipo08/esp32-01/availability";
constexpr time_t FechaMinimaValida = 1767225600;  // 1 de enero de 2026, UTC.

}  // namespace

ConexionMqtt::ConexionMqtt(ConexionWifi& conexionWifi, ControlLeds& leds)
    : conexionWifi_(conexionWifi), leds_(leds) {}

void ConexionMqtt::iniciar() {
    if (ServidorMqtt[0] == '\0' || UsuarioMqtt[0] == '\0' || ClaveMqtt[0] == '\0' ||
        IdentificadorClienteMqtt[0] == '\0' || PuertoMqtt != 8883) {
        Serial.println(F("MQTT: configuracion incompleta. Control local activo."));
        return;
    }

    transporteSeguro_.setCACert(CertificadoCaEmqx);
    transporteSeguro_.setHandshakeTimeout(3);  // Segundos, API de Arduino-ESP32.
    cliente_.begin(ServidorMqtt, PuertoMqtt, transporteSeguro_);
    cliente_.setOptions(30, true, 1000);  // Keepalive, sesion limpia, timeout MQTT en ms.
    cliente_.setWill(TemaDisponibilidad, "offline", true, 1);
    cliente_.onMessageAdvanced([this](MQTTClient*, char tema[], char datos[], int longitud) {
        recibirComando(tema, datos, longitud);
    });
    habilitada_ = true;
    Serial.println(F("MQTT: TLS configurado; esperando WiFi y hora valida."));
}

bool ConexionMqtt::prepararHora() {
    if (time(nullptr) >= FechaMinimaValida) {
        if (sincronizandoHora_) {
            Serial.println(F("MQTT: hora disponible para validar TLS."));
            sincronizandoHora_ = false;
        }
        return true;
    }

    const unsigned long ahora = millis();
    if (!sincronizandoHora_) {
        if (huboIntento_ && ahora - ultimoIntentoMs_ < IntervaloReintentoMs) {
            return false;
        }
        Serial.println(F("MQTT: solicitando hora por NTP."));
        configTime(0, 0, "pool.ntp.org", "time.cloudflare.com");
        inicioSincronizacionMs_ = ahora;
        sincronizandoHora_ = true;
    } else if (ahora - inicioSincronizacionMs_ >= TiempoSincronizacionMs) {
        Serial.println(F("MQTT: hora no disponible; TLS aplazado. Reintento en 30 s."));
        sincronizandoHora_ = false;
        huboIntento_ = true;
        ultimoIntentoMs_ = ahora;
    }
    return false;
}

void ConexionMqtt::cerrarConexion() {
    // Cerrar el transporte sin DISCONNECT permite al broker emitir el LWT.
    transporteSeguro_.stop();
    lista_ = false;
    estadosPendientes_ = false;
    huboIntento_ = true;
    ultimoIntentoMs_ = millis();
}

bool ConexionMqtt::publicarMensaje(const char* tema, const char* mensaje, bool retenido, int qos) {
    if (!cliente_.publish(tema, mensaje, retenido, qos)) {
        Serial.println(F("MQTT: fallo de publicacion. Reintento de conexion en 30 s."));
        cerrarConexion();
        return false;
    }
    return true;
}

bool ConexionMqtt::publicarEstados() {
    // Un comando recibido durante un PUBACK vuelve a activar la marca.
    estadosPendientes_ = false;
    return publicarMensaje(TemaRojo, leds_.estaRojoEncendido() ? "on" : "off", true, 1) &&
           publicarMensaje(TemaAmarillo, leds_.estaAmarilloEncendido() ? "on" : "off", true, 1) &&
           publicarMensaje(TemaVerde, leds_.estaVerdeEncendido() ? "on" : "off", true, 1);
}

void ConexionMqtt::intentarConectar() {
    huboIntento_ = true;
    ultimoIntentoMs_ = millis();
    Serial.println(F("MQTT: iniciando conexion TLS y MQTT."));

    // El dominio completo conserva SNI y la validacion del nombre del servidor.
    if (!transporteSeguro_.connect(ServidorMqtt, PuertoMqtt, 1000)) {
        Serial.println(F("MQTT: fallo TLS/DNS/TCP. Revisar red, hora y CA."));
        cerrarConexion();
        return;
    }
    transporteSeguro_.setTimeout(1);  // Timeout de socket en segundos en este core.

    // true omite solo la apertura de red: TLS ya se valido en connect().
    if (!cliente_.connect(IdentificadorClienteMqtt, UsuarioMqtt, ClaveMqtt, true)) {
        Serial.print(F("MQTT: conexion rechazada o agotada. Codigo: "));
        Serial.println(static_cast<int>(cliente_.returnCode()));
        cerrarConexion();
        return;
    }
    if (!cliente_.subscribe(TemaComandos, 1)) {
        Serial.println(F("MQTT: no se pudo suscribir cmd."));
        cerrarConexion();
        return;
    }
    if (!publicarEstados() || !publicarMensaje(TemaDisponibilidad, "online", true, 1)) {
        return;
    }

    lista_ = true;
    Serial.println(F("MQTT: conexion segura establecida; cmd suscrito."));
}

bool ConexionMqtt::estaConectada() {
    return habilitada_ && lista_ && conexionWifi_.estaConectada() && cliente_.connected();
}

void ConexionMqtt::actualizar() {
    if (!habilitada_) {
        return;
    }
    if (!conexionWifi_.estaConectada()) {
        if (lista_) {
            Serial.println(F("MQTT: WiFi perdido; el broker notificara offline mediante LWT."));
            cerrarConexion();
        }
        sincronizandoHora_ = false;
        return;
    }
    if (lista_) {
        if (!cliente_.loop()) {
            Serial.println(F("MQTT: conexion perdida. Reintento en 30 s."));
            cerrarConexion();
        } else if (estadosPendientes_) {
            publicarEstados();
        }
        return;
    }
    if (!prepararHora()) {
        return;
    }
    if (huboIntento_ && millis() - ultimoIntentoMs_ < IntervaloReintentoMs) {
        return;
    }
    intentarConectar();
}

void ConexionMqtt::recibirComando(const char* tema, const char* datos, int longitud) {
    if (strcmp(tema, TemaComandos) != 0) {
        return;
    }
    if (datos == nullptr || longitud <= 0 || longitud > 31) {
        Serial.println(F("MQTT: comando rechazado por formato o longitud."));
        return;
    }

    char comando[32];
    for (int indice = 0; indice < longitud; ++indice) {
        const uint8_t valor = static_cast<uint8_t>(datos[indice]);
        if (valor < 32 || valor > 126) {
            Serial.println(F("MQTT: comando rechazado por caracteres invalidos."));
            return;
        }
        comando[indice] = datos[indice];
    }
    comando[longitud] = '\0';

    if (leds_.ejecutarComando(comando)) {
        // No publicar desde el callback: la biblioteca puede estar esperando un ACK.
        solicitarPublicacionEstados();
        Serial.println(F("MQTT: comando aplicado; estados pendientes de publicar."));
    } else {
        Serial.println(F("MQTT: comando desconocido; LEDs sin cambios."));
    }
}

void ConexionMqtt::solicitarPublicacionEstados() {
    estadosPendientes_ = true;
}

void ConexionMqtt::publicarMedicion(const SensorUltrasonico::Medicion& medicion) {
    if (!estaConectada()) {
        return;  // No almacenar ni reenviar mediciones antiguas al reconectar.
    }

    const bool valida = medicion.valida && isfinite(medicion.distanciaCm);
    if (!publicarMensaje(TemaSensor, valida ? "valid" : "invalid", false, 0) || !valida) {
        return;
    }
    char distancia[16];
    snprintf(distancia, sizeof(distancia), "%.1f", static_cast<double>(medicion.distanciaCm));
    publicarMensaje(TemaDistancia, distancia, false, 0);
}
