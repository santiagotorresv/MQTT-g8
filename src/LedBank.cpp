#include "LedBank.h"

#include <Arduino.h>
#include <string.h>

LedBank::LedBank(uint8_t redPin, uint8_t yellowPin, uint8_t greenPin)
    : channels_{{redPin, false}, {yellowPin, false}, {greenPin, false}} {}

void LedBank::begin() {
    for (size_t i = 0; i < LedCount; ++i) {
        // Preparar LOW antes de habilitar la salida reduce transitorios al iniciar.
        digitalWrite(channels_[i].pin, LOW);
        pinMode(channels_[i].pin, OUTPUT);
        channels_[i].on = false;
    }
}

void LedBank::write(size_t index, bool on) {
    digitalWrite(channels_[index].pin, on ? HIGH : LOW);
    channels_[index].on = on;
}

bool LedBank::set(Led led, bool on) {
    const size_t index = static_cast<size_t>(led);
    if (index >= LedCount) {
        return false;
    }

    write(index, on);
    return true;
}

void LedBank::allOn() {
    for (size_t i = 0; i < LedCount; ++i) {
        write(i, true);
    }
}

void LedBank::allOff() {
    for (size_t i = 0; i < LedCount; ++i) {
        write(i, false);
    }
}

bool LedBank::only(Led led) {
    const size_t index = static_cast<size_t>(led);
    if (index >= LedCount) {
        return false;
    }

    // Apagar primero los otros LEDs. Repetir la orden no pulsa el seleccionado.
    for (size_t i = 0; i < LedCount; ++i) {
        if (i != index) {
            write(i, false);
        }
    }
    write(index, true);
    return true;
}

bool LedBank::isOn(Led led) const {
    const size_t index = static_cast<size_t>(led);
    return index < LedCount && channels_[index].on;
}

bool LedBank::executeCommand(const char* command) {
    if (command == nullptr) {
        return false;
    }

    if (strcmp(command, "rojo:on") == 0) {
        return set(Led::Rojo, true);
    }
    if (strcmp(command, "rojo:off") == 0) {
        return set(Led::Rojo, false);
    }
    if (strcmp(command, "amarillo:on") == 0) {
        return set(Led::Amarillo, true);
    }
    if (strcmp(command, "amarillo:off") == 0) {
        return set(Led::Amarillo, false);
    }
    if (strcmp(command, "verde:on") == 0) {
        return set(Led::Verde, true);
    }
    if (strcmp(command, "verde:off") == 0) {
        return set(Led::Verde, false);
    }
    if (strcmp(command, "todos:on") == 0) {
        allOn();
        return true;
    }
    if (strcmp(command, "todos:off") == 0) {
        allOff();
        return true;
    }
    if (strcmp(command, "solo:rojo") == 0) {
        return only(Led::Rojo);
    }
    if (strcmp(command, "solo:amarillo") == 0) {
        return only(Led::Amarillo);
    }
    if (strcmp(command, "solo:verde") == 0) {
        return only(Led::Verde);
    }

    return false;
}
