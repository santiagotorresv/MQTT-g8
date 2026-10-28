#pragma once

#include <stdint.h>

/** HC-SR04: llamar a iniciar() y dejar al menos 60 ms entre mediciones. */
class SensorUltrasonico {
public:
    struct Medicion {
        float distanciaCm;  // NaN cuando valida es false; nunca representa un error con 0.
        bool valida;
    };

    // Guarda los pines sin acceder al hardware.
    SensorUltrasonico(uint8_t pinTrig, uint8_t pinEcho);

    void iniciar();

    // Lectura sin filtros. pulseIn espera hasta 30 ms nominales en este framework.
    Medicion medir();

private:
    static constexpr unsigned long TiempoEsperaEcoUs = 30000UL;
    static constexpr float VelocidadSonidoCmPorUs = 0.034f;  // Aproximacion: 340 m/s.
    static constexpr float DistanciaMinimaCm = 2.0f;
    static constexpr float DistanciaMaximaCm = 400.0f;

    const uint8_t pinTrig_;
    const uint8_t pinEcho_;
};
