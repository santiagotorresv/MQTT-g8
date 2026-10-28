#pragma once

#include <stdint.h>

/** Tres LEDs activos en HIGH; iniciar() deja todas las salidas apagadas. */
class ControlLeds {
public:
    ControlLeds(uint8_t pinRojo, uint8_t pinAmarillo, uint8_t pinVerde);

    void iniciar();
    void establecerRojo(bool encendido);
    void establecerAmarillo(bool encendido);
    void establecerVerde(bool encendido);
    void encenderTodos();
    void apagarTodos();
    void encenderSoloRojo();
    void encenderSoloAmarillo();
    void encenderSoloVerde();

    // Estados lógicos guardados; no son mediciones eléctricas.
    bool estaRojoEncendido() const;
    bool estaAmarilloEncendido() const;
    bool estaVerdeEncendido() const;

    // Texto de solo lectura, terminado en cero. Rechazar no cambia las salidas.
    bool ejecutarComando(const char* comando);

private:
    const uint8_t pinRojo_;
    const uint8_t pinAmarillo_;
    const uint8_t pinVerde_;
    bool rojoEncendido_ = false;
    bool amarilloEncendido_ = false;
    bool verdeEncendido_ = false;
};
