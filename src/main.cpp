#include <Arduino.h>

#include "LedBank.h"

namespace {

// Unica instancia compartida por setup() y loop(); no usa GPIO al construirse.
// Orden del constructor: rojo, amarillo, verde.
LedBank leds(27, 26, 25);

void printStates() {
    Serial.print(F("Estado: rojo="));
    Serial.print(leds.isOn(LedBank::Led::Rojo) ? "on" : "off");
    Serial.print(F(" amarillo="));
    Serial.print(leds.isOn(LedBank::Led::Amarillo) ? "on" : "off");
    Serial.print(F(" verde="));
    Serial.println(leds.isOn(LedBank::Led::Verde) ? "on" : "off");
}

void processLine(const char* command, bool invalidLine) {
    Serial.print(F("Comando recibido: "));
    Serial.println(command[0] == '\0' ? "<vacio>" : command);

    if (invalidLine) {
        Serial.println(F("ERROR: linea demasiado larga o con bytes de control; descartada."));
    } else if (!leds.executeCommand(command)) {
        Serial.println(F("ERROR: comando no valido. No se modificaron los LEDs."));
    } else {
        Serial.println(F("OK: comando aplicado."));
    }

    printStates();
}

}  // namespace

void setup() {
    leds.begin();
    Serial.begin(115200);
    Serial.println(F("Prueba local de LEDs - SIS-234 equipo08"));
    Serial.println(F("Escriba un comando y pulse Enter (LF, CR o CRLF)."));
    Serial.println(F("rojo:on/off, amarillo:on/off, verde:on/off"));
    Serial.println(F("todos:on/off, solo:rojo, solo:amarillo, solo:verde"));
    printStates();
}

void loop() {
    // Buffer fijo: 31 bytes de contenido y el terminador. No espera una linea.
    static char command[32] = {};
    static size_t length = 0;
    static bool invalidLine = false;
    static bool previousWasCr = false;

    while (Serial.available() > 0) {
        const char incoming = static_cast<char>(Serial.read());

        if (incoming == '\r' || incoming == '\n') {
            // CRLF es un unico fin de linea, incluso si llega en dos vueltas.
            if (incoming == '\n' && previousWasCr) {
                previousWasCr = false;
                continue;
            }
            previousWasCr = incoming == '\r';

            processLine(command, invalidLine);
            length = 0;
            command[0] = '\0';
            invalidLine = false;
            continue;
        }

        previousWasCr = false;
        if (invalidLine) {
            // Descartar hasta fin de linea: nunca ejecutar un prefijo truncado.
            continue;
        }

        const uint8_t byte = static_cast<uint8_t>(incoming);
        if (byte < 32 || byte > 126 || length >= sizeof(command) - 1) {
            invalidLine = true;
            continue;
        }

        command[length++] = incoming;
        command[length] = '\0';
    }
}
