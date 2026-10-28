#pragma once

#include <MQTT.h>
#include <WiFiClientSecure.h>

#include "ConexionWifi.h"
#include "ControlLeds.h"
#include "SensorUltrasonico.h"

/** MQTT sobre TLS. Los modulos locales no dependen de que haya conexion. */
class ConexionMqtt {
public:
    ConexionMqtt(ConexionWifi& conexionWifi, ControlLeds& leds);

    void iniciar();
    void actualizar();
    bool estaConectada();
    void publicarMedicion(const SensorUltrasonico::Medicion& medicion);
    void solicitarPublicacionEstados();

private:
    static constexpr unsigned long IntervaloReintentoMs = 30000UL;
    static constexpr unsigned long TiempoSincronizacionMs = 10000UL;

    ConexionWifi& conexionWifi_;
    ControlLeds& leds_;
    WiFiClientSecure transporteSeguro_;
    MQTTClient cliente_{256};
    bool habilitada_ = false;
    bool lista_ = false;
    bool huboIntento_ = false;
    bool sincronizandoHora_ = false;
    bool estadosPendientes_ = false;
    unsigned long ultimoIntentoMs_ = 0;
    unsigned long inicioSincronizacionMs_ = 0;

    bool prepararHora();
    void intentarConectar();
    void cerrarConexion();
    bool publicarMensaje(const char* tema, const char* mensaje, bool retenido, int qos);
    bool publicarEstados();
    void recibirComando(const char* tema, const char* datos, int longitud);
};
