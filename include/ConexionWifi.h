#pragma once

/** Supervisa WiFi desde loop(), sin esperar a que termine una conexion. */
class ConexionWifi {
public:
    // Las cadenas deben seguir existiendo durante toda la vida del objeto.
    ConexionWifi(const char* nombreRed, const char* claveRed);

    void iniciar();
    void actualizar();
    bool estaConectada() const;

private:
    static constexpr unsigned long IntervaloReintentoMs = 15000UL;

    const char* nombreRed_;
    const char* claveRed_;
    unsigned long ultimoIntentoMs_ = 0;
    bool habilitada_ = false;
    bool estabaConectada_ = false;

    void intentarConectar();
};
