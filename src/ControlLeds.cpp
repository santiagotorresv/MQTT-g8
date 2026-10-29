#include "ControlLeds.h"

#include <Arduino.h>
#include <string.h>

ControlLeds::ControlLeds(uint8_t pinRojo, uint8_t pinAmarillo, uint8_t pinVerde)
    : pinRojo_(pinRojo), pinAmarillo_(pinAmarillo), pinVerde_(pinVerde) {}

void ControlLeds::iniciar() {
    // Preparar LOW antes de habilitar cada salida evita encenderla al iniciar.
    establecerRojo(false);
    pinMode(pinRojo_, OUTPUT);
    establecerAmarillo(false);
    pinMode(pinAmarillo_, OUTPUT);
    establecerVerde(false);
    pinMode(pinVerde_, OUTPUT);
}

void ControlLeds::establecerRojo(bool encendido) {
    if (encendido) {
        digitalWrite(pinRojo_, HIGH);
    } else {
        digitalWrite(pinRojo_, LOW);
    }
    rojoEncendido_ = encendido;
}

bool ControlLeds::estaRojoEncendido() const {
    return rojoEncendido_;
}

void ControlLeds::establecerAmarillo(bool encendido) {
    if (encendido) {
        digitalWrite(pinAmarillo_, HIGH);
    } else {
        digitalWrite(pinAmarillo_, LOW);
    }
    amarilloEncendido_ = encendido;
}

bool ControlLeds::estaAmarilloEncendido() const {
    return amarilloEncendido_;
}

void ControlLeds::establecerVerde(bool encendido) {
    if (encendido) {
        digitalWrite(pinVerde_, HIGH);
    } else {
        digitalWrite(pinVerde_, LOW);
    }
    verdeEncendido_ = encendido;
}

bool ControlLeds::estaVerdeEncendido() const {
    return verdeEncendido_;
}

void ControlLeds::encenderTodos() {
    establecerRojo(true);
    establecerAmarillo(true);
    establecerVerde(true);
}

void ControlLeds::apagarTodos() {
    establecerRojo(false);
    establecerAmarillo(false);
    establecerVerde(false);
}

void ControlLeds::encenderSoloRojo() {
    // Apagar los otros antes; repetir no apaga el seleccionado.
    establecerAmarillo(false);
    establecerVerde(false);
    establecerRojo(true);
}

void ControlLeds::encenderSoloAmarillo() {
    // Apagar los otros antes; repetir no apaga el seleccionado.
    establecerRojo(false);
    establecerVerde(false);
    establecerAmarillo(true);
}

void ControlLeds::encenderSoloVerde() {
    // Apagar los otros antes; repetir no apaga el seleccionado.
    establecerRojo(false);
    establecerAmarillo(false);
    establecerVerde(true);
}

bool ControlLeds::ejecutarComando(const char* comando) {
    if (comando == nullptr) {
        return false;
    }

    if (strcmp(comando, "rojo:on") == 0) {
        establecerRojo(true);
        return true;
    }
    if (strcmp(comando, "rojo:off") == 0) {
        establecerRojo(false);
        return true;
    }
    if (strcmp(comando, "amarillo:on") == 0) {
        establecerAmarillo(true);
        return true;
    }
    if (strcmp(comando, "amarillo:off") == 0) {
        establecerAmarillo(false);
        return true;
    }
    if (strcmp(comando, "verde:on") == 0) {
        establecerVerde(true);
        return true;
    }
    if (strcmp(comando, "verde:off") == 0) {
        establecerVerde(false);
        return true;
    }
    if (strcmp(comando, "todos:on") == 0) {
        encenderTodos();
        return true;
    }
    if (strcmp(comando, "todos:off") == 0) {
        apagarTodos();
        return true;
    }
    if (strcmp(comando, "solo:rojo") == 0) {
        encenderSoloRojo();
        return true;
    }
    if (strcmp(comando, "solo:amarillo") == 0) {
        encenderSoloAmarillo();
        return true;
    }
    if (strcmp(comando, "solo:verde") == 0) {
        encenderSoloVerde();
        return true;
    }

    return false;
}
