#pragma once

#include <stddef.h>
#include <stdint.h>

/** Tres LEDs activos en HIGH. Llamar a begin() antes de controlarlos. */
class LedBank {
public:
    enum class Led : uint8_t { Rojo, Amarillo, Verde };

    // El constructor guarda la configuracion; no accede al hardware.
    LedBank(uint8_t redPin, uint8_t yellowPin, uint8_t greenPin);

    void begin();
    bool set(Led led, bool on);
    void allOn();
    void allOff();
    bool only(Led led);

    // Devuelve el estado logico guardado, no una medicion electrica.
    // Un identificador fuera de la enumeracion devuelve false.
    bool isOn(Led led) const;

    // Solo admite los once comandos del contrato. Un rechazo no cambia salidas.
    bool executeCommand(const char* command);

private:
    struct Channel {
        uint8_t pin;
        bool on;
    };

    static constexpr size_t LedCount = 3;
    Channel channels_[LedCount];

    void write(size_t index, bool on);
};
