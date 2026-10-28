#include <Arduino.h>

#include "ControlLeds.h"
#include "SensorUltrasonico.h"
#include "ConexionWifi.h"

#if __has_include("ConfiguracionWifi.h")
#include "ConfiguracionWifi.h"
#else
#include "ConfiguracionWifi.ejemplo.h"
#endif

namespace {

// Unica instancia compartida por setup() y loop(); no usa GPIO al construirse.
// Orden del constructor: rojo, amarillo, verde.
ControlLeds leds(27, 26, 25);
SensorUltrasonico sensor(5, 18);  // TRIG, ECHO mediante el divisor existente.
ConexionWifi conexionWifi(NombreRedWifi, ClaveRedWifi);
constexpr unsigned long IntervaloMedicionMs = 500UL;

void mostrarEstados() {
    Serial.print(F("Estado: rojo="));
    Serial.print(leds.estaRojoEncendido() ? "on" : "off");
    Serial.print(F(" amarillo="));
    Serial.print(leds.estaAmarilloEncendido() ? "on" : "off");
    Serial.print(F(" verde="));
    Serial.println(leds.estaVerdeEncendido() ? "on" : "off");
}

void procesarLinea(const char* comando, bool lineaInvalida) {
    Serial.print(F("Comando recibido: "));
    Serial.println(comando[0] == '\0' ? "<vacio>" : comando);

    if (lineaInvalida) {
        Serial.println(F("ERROR: linea demasiado larga o con bytes de control; descartada."));
    } else if (!leds.ejecutarComando(comando)) {
        Serial.println(F("ERROR: comando no valido. No se modificaron los LEDs."));
    } else {
        Serial.println(F("OK: comando aplicado."));
    }

    mostrarEstados();
}

}  // namespace

void setup() {
    leds.iniciar();
    sensor.iniciar();
    Serial.begin(115200);
    Serial.println(F("Prueba local de LEDs y HC-SR04 - SIS-234 equipo08"));
    Serial.println(F("Escriba un comando y pulse Enter (LF, CR o CRLF)."));
    Serial.println(F("rojo:on/off, amarillo:on/off, verde:on/off"));
    Serial.println(F("todos:on/off, solo:rojo, solo:amarillo, solo:verde"));
    Serial.println(F("Sensor: lectura cada 500 ms; timeout ECHO de 30 ms."));
    mostrarEstados();
    conexionWifi.iniciar();
}

void loop() {
    // Buffer fijo: 31 bytes de contenido y el terminador. No espera una linea.
    static char comando[32] = {};
    static size_t longitud = 0;
    static bool lineaInvalida = false;
    static bool anteriorEraCr = false;
    static unsigned long ultimaMedicionMs = 0;

    // Acotar la entrada por vuelta para no postergar el sensor con trafico continuo.
    for (size_t procesados = 0; procesados < 32 && Serial.available() > 0; ++procesados) {
        const char caracterRecibido = static_cast<char>(Serial.read());

        if (caracterRecibido == '\r' || caracterRecibido == '\n') {
            // CRLF es un unico fin de linea, incluso si llega en dos vueltas.
            if (caracterRecibido == '\n' && anteriorEraCr) {
                anteriorEraCr = false;
                continue;
            }
            anteriorEraCr = caracterRecibido == '\r';

            procesarLinea(comando, lineaInvalida);
            longitud = 0;
            comando[0] = '\0';
            lineaInvalida = false;
            continue;
        }

        anteriorEraCr = false;
        if (lineaInvalida) {
            // Descartar hasta fin de linea: nunca ejecutar un prefijo truncado.
            continue;
        }

        const uint8_t valorByte = static_cast<uint8_t>(caracterRecibido);
        if (valorByte < 32 || valorByte > 126 || longitud >= sizeof(comando) - 1) {
            lineaInvalida = true;
            continue;
        }

        comando[longitud++] = caracterRecibido;
        comando[longitud] = '\0';
    }

    const unsigned long ahora = millis();
    // La resta sin signo sigue funcionando cuando millis() se desborda.
    if (ahora - ultimaMedicionMs >= IntervaloMedicionMs) {
        ultimaMedicionMs = ahora;
        const SensorUltrasonico::Medicion medicion = sensor.medir();
        if (medicion.valida) {
            Serial.print(F("Sensor: distancia="));
            Serial.print(medicion.distanciaCm, 1);
            Serial.println(F(" cm"));
        } else {
            Serial.println(F("Sensor: medicion invalida (sin eco/timeout o fuera de 2-400 cm)."));
        }
    }

    conexionWifi.actualizar();
}
