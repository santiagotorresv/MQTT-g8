"""Suscripción MQTT y última lectura en memoria; sin control de actuadores."""

import json
import logging
import math
from pathlib import Path
import re
import ssl
from threading import Lock
from time import monotonic

import paho.mqtt.client as mqtt


registro = logging.getLogger(__name__)
carpeta_proyecto = Path(__file__).resolve().parent.parent
prefijo = "sis234/equipo08/esp32-01/"
topico_distancia = prefijo + "telemetry/distance_cm"
topico_sensor = prefijo + "telemetry/sensor_status"
topico_disponibilidad = prefijo + "availability"


class ConexionMqtt:
    def __init__(self, usuario="", contrasena="", antiguedad_maxima_segundos=5):
        if (
            isinstance(antiguedad_maxima_segundos, bool)
            or not isinstance(antiguedad_maxima_segundos, (int, float))
            or not math.isfinite(antiguedad_maxima_segundos)
            or antiguedad_maxima_segundos <= 0
        ):
            raise ValueError("El umbral de antigüedad debe ser finito y positivo.")
        if not isinstance(usuario, str) or not isinstance(contrasena, str):
            raise ValueError("Las credenciales deben ser cadenas de texto.")
        self._usuario = usuario
        self._contrasena = contrasena
        self._antiguedad_maxima = antiguedad_maxima_segundos
        self._bloqueo = Lock()
        self._conectada = False
        self._suscrita = False
        self._iniciada = False
        self._motivo = "Conexión MQTT todavía no iniciada."
        self._limpiar_lectura()
        self._cliente = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="equipo08_mcp_python",
            protocol=mqtt.MQTTv311,
            clean_session=True,
        )
        self._cliente.on_connect = self._al_conectar
        self._cliente.on_connect_fail = self._al_fallar_conexion
        self._cliente.on_disconnect = self._al_desconectar
        self._cliente.on_subscribe = self._al_suscribir
        self._cliente.on_message = self._al_mensaje
        self._cliente.reconnect_delay_set(min_delay=1, max_delay=30)
        self._cliente.connect_timeout = 5

    @classmethod
    def desde_archivo(cls, ruta: Path):
        """Sin archivo o con configuración incorrecta, conservar MCP disponible."""
        try:
            configuracion = json.loads(ruta.read_text(encoding="utf-8-sig"))
            return cls(
                usuario=configuracion["usuario"],
                contrasena=configuracion["contrasena"],
                antiguedad_maxima_segundos=configuracion.get(
                    "antiguedad_maxima_segundos", 5
                ),
            )
        except (OSError, ValueError, KeyError, TypeError):
            registro.warning("Configuración MQTT ausente o incorrecta; revisar copia local.")
            return cls()

    def iniciar(self):
        if self._iniciada:
            return
        if not self._usuario or not self._contrasena:
            with self._bloqueo:
                self._motivo = "MQTT sin configurar: completar las credenciales locales."
            registro.warning("MQTT deshabilitado: faltan credenciales locales.")
            return
        try:
            contexto_tls = ssl.create_default_context(
                cafile=str(carpeta_proyecto / "certificados" / "emqxsl-ca.crt")
            )
            contexto_tls.minimum_version = ssl.TLSVersion.TLSv1_2
            self._cliente.tls_set_context(contexto_tls)
            self._cliente.username_pw_set(self._usuario, self._contrasena)
            self._cliente.connect_async("zffa4f2f.ala.us-east-1.emqxsl.com", 8883, 30)
            with self._bloqueo:
                self._motivo = "Esperando conexión MQTT con EMQX."
            resultado = self._cliente.loop_start()
            if resultado != mqtt.MQTT_ERR_SUCCESS:
                raise OSError("No se pudo iniciar el hilo MQTT.")
            self._iniciada = True
            registro.info("Cliente MQTT iniciado; conexión y reintentos en segundo plano.")
        except (OSError, ValueError):
            with self._bloqueo:
                self._motivo = "No se pudo iniciar MQTT; revisar configuración y certificado CA."
            registro.error("No se pudo iniciar MQTT; revisar configuración y certificado CA.")

    def detener(self):
        if self._iniciada:
            try:
                self._cliente.disconnect()
            finally:
                self._cliente.loop_stop()
                self._iniciada = False
        with self._bloqueo:
            self._conectada = False
            self._suscrita = False
            self._motivo = "Conexión MQTT detenida."
            self._limpiar_lectura()

    def _limpiar_lectura(self):
        """Llamar con el bloqueo adquirido, excepto durante la construcción."""
        self._distancia = None
        self._instante_distancia = None
        self._estado_sensor = None
        self._instante_sensor = None
        self._disponibilidad = None

    def _al_conectar(self, cliente, datos, indicadores, codigo, propiedades):
        with self._bloqueo:
            self._limpiar_lectura()
            self._suscrita = False
            self._conectada = not codigo.is_failure
            self._motivo = "Conexión MQTT rechazada por el broker."
        if codigo.is_failure:
            registro.error("EMQX rechazó la conexión MQTT (código %s).", codigo.value)
            return
        resultado, _ = cliente.subscribe([
            (topico_distancia, 0), (topico_sensor, 0), (topico_disponibilidad, 1)
        ])
        with self._bloqueo:
            self._motivo = (
                "Esperando confirmación de suscripciones MQTT."
                if resultado == mqtt.MQTT_ERR_SUCCESS
                else "No se pudieron solicitar las suscripciones MQTT."
            )
        registro.info("Conexión MQTT establecida; suscripciones solicitadas.")

    def _al_suscribir(self, cliente, datos, identificador, codigos, propiedades):
        aceptada = len(codigos) == 3 and all(not codigo.is_failure for codigo in codigos)
        with self._bloqueo:
            self._suscrita = aceptada
            self._motivo = (
                "Suscripciones MQTT listas."
                if aceptada else "El broker rechazó una suscripción MQTT."
            )
        if aceptada:
            registro.info("Las tres suscripciones MQTT están confirmadas.")
        else:
            registro.error("El broker rechazó una suscripción MQTT.")

    def _al_fallar_conexion(self, cliente, datos):
        with self._bloqueo:
            self._motivo = "No se pudo conectar con EMQX; se reintentará automáticamente."
        registro.warning("Fallo de conexión MQTT; reintento automático pendiente.")

    def _al_desconectar(self, cliente, datos, indicadores, codigo, propiedades):
        with self._bloqueo:
            self._conectada = False
            self._suscrita = False
            self._motivo = "MQTT desconectado; no se puede comprobar el estado del ESP32."
            self._limpiar_lectura()
        registro.warning("Conexión MQTT cerrada.")

    def _al_mensaje(self, cliente, datos, mensaje):
        if mensaje.topic not in (topico_distancia, topico_sensor, topico_disponibilidad):
            return
        try:
            if len(mensaje.payload) > 64:
                raise ValueError("Mensaje demasiado largo.")
            texto = mensaje.payload.decode("utf-8")
            if mensaje.topic != topico_disponibilidad and mensaje.retain:
                raise ValueError("La telemetría no debe estar retenida.")
            if mensaje.topic == topico_distancia:
                if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", texto):
                    raise ValueError("Distancia mal formada.")
                distancia = float(texto)
                if not math.isfinite(distancia) or not 2 <= distancia <= 400:
                    raise ValueError("Distancia fuera del rango nominal.")
            elif mensaje.topic == topico_sensor and texto not in ("valid", "invalid"):
                raise ValueError("Estado de sensor desconocido.")
            elif mensaje.topic == topico_disponibilidad and texto not in ("online", "offline"):
                raise ValueError("Disponibilidad desconocida.")
        except (UnicodeError, ValueError):
            with self._bloqueo:
                # No conservar una lectura anterior como actual tras un mensaje erróneo.
                if mensaje.topic == topico_distancia:
                    self._distancia = self._instante_distancia = None
                elif mensaje.topic == topico_sensor:
                    self._estado_sensor = self._instante_sensor = None
                else:
                    self._disponibilidad = None
            registro.warning("Mensaje MQTT rechazado en un tópico de telemetría o disponibilidad.")
            return
        with self._bloqueo:
            if not self._conectada:
                return
            if mensaje.topic == topico_distancia:
                self._distancia = distancia
                self._instante_distancia = monotonic()
            elif mensaje.topic == topico_sensor:
                self._estado_sensor = texto
                self._instante_sensor = monotonic()
                if texto == "invalid":
                    self._distancia = self._instante_distancia = None
            else:
                if texto == "offline" or self._disponibilidad == "offline":
                    self._distancia = self._instante_distancia = None
                    self._estado_sensor = self._instante_sensor = None
                self._disponibilidad = texto

    def consultar_distancia(self) -> dict:
        """Devuelve una instantánea coherente, sin esperas de red ni valores inventados."""
        with self._bloqueo:
            resultado = {"origen": "ESP32 mediante MQTT"}
            if not self._conectada or not self._suscrita:
                resultado.update(estado="mqtt_no_disponible", mensaje=self._motivo)
            elif self._disponibilidad == "offline":
                resultado.update(estado="esp32_desconectado", mensaje="El ESP32 anunció offline.")
            elif self._disponibilidad is None:
                resultado.update(estado="sin_datos", mensaje="Todavía no hay disponibilidad conocida del ESP32.")
            elif self._instante_sensor is None:
                resultado.update(estado="sin_datos", mensaje="Todavía no hay estado válido recibido del sensor.")
            else:
                ahora = monotonic()
                edad_sensor = ahora - self._instante_sensor
                if edad_sensor > self._antiguedad_maxima:
                    resultado.update(estado="desactualizada", mensaje="El estado del sensor está desactualizado.")
                elif self._estado_sensor == "invalid":
                    resultado.update(estado="invalida", mensaje="El sensor informó que la medición actual no es válida.")
                elif self._instante_distancia is None:
                    resultado.update(estado="sin_datos", mensaje="Todavía no hay distancia recibida mediante MQTT.")
                elif ahora - self._instante_distancia > self._antiguedad_maxima:
                    resultado.update(estado="desactualizada", mensaje="La última distancia está desactualizada.")
                else:
                    resultado.update(
                        estado="valida", distancia_cm=self._distancia, unidad="cm",
                        antiguedad_segundos=round(ahora - self._instante_distancia, 3),
                        mensaje="Última distancia válida y reciente recibida del ESP32 mediante MQTT.",
                    )
            return resultado
