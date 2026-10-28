#include "SensorUltrasonico.h"

#include <Arduino.h>
#include <math.h>

SensorUltrasonico::SensorUltrasonico(uint8_t pinTrig, uint8_t pinEcho)
    : pinTrig_(pinTrig), pinEcho_(pinEcho) {}

void SensorUltrasonico::iniciar() {
    digitalWrite(pinTrig_, LOW);
    pinMode(pinTrig_, OUTPUT);
    pinMode(pinEcho_, INPUT);
}

SensorUltrasonico::Medicion SensorUltrasonico::medir() {
    digitalWrite(pinTrig_, LOW);
    delayMicroseconds(2);
    digitalWrite(pinTrig_, HIGH);
    delayMicroseconds(10);
    digitalWrite(pinTrig_, LOW);

    const unsigned long duracionEcoUs = pulseIn(pinEcho_, HIGH, TiempoEsperaEcoUs);
    if (duracionEcoUs == 0) {
        return {NAN, false};
    }

    // ECHO representa el recorrido de ida y vuelta; dividir entre dos.
    const float distanciaCm = duracionEcoUs * VelocidadSonidoCmPorUs / 2.0f;
    if (distanciaCm < DistanciaMinimaCm || distanciaCm > DistanciaMaximaCm) {
        return {NAN, false};
    }

    return {distanciaCm, true};
}
