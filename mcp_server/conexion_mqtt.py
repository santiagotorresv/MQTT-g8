"""Conexión compartida, telemetría y control MQTT de los LEDs del equipo 08."""

import json
import logging
import math
from pathlib import Path
import re
import ssl
from threading import Condition, Lock
from time import monotonic

import paho.mqtt.client as mqtt


registro = logging.getLogger(__name__)
carpeta_proyecto = Path(__file__).resolve().parent.parent
prefijo = "sis234/equipo08/esp32-01/"
topico_distancia = prefijo + "telemetry/distance_cm"
topico_sensor = prefijo + "telemetry/sensor_status"
topico_disponibilidad = prefijo + "availability"
topico_comandos = prefijo + "cmd"
topicos_leds = {prefijo + "state/" + color: color for color in ("rojo", "amarillo", "verde")}
tiempo_limite_comando = 3.0


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
        self._cambio = Condition(self._bloqueo)
        self._bloqueo_comandos = Lock()
        self._sesion = 0
        self._numero_estado = 0
        self._estados_leds = {color: None for color in topicos_leds.values()}
        self._conectada = False
        self._suscrita = False
        self._suscrita_leds = False
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
            self._suscrita_leds = False
            self._motivo = "Conexión MQTT detenida."
            self._limpiar_lectura()
            self._cambio.notify_all()

    def _limpiar_lectura(self):
        """Llamar con el bloqueo adquirido, excepto durante la construcción."""
        self._sesion += 1
        self._distancia = None
        self._instante_distancia = None
        self._estado_sensor = None
        self._instante_sensor = None
        self._disponibilidad = None

    def _al_conectar(self, cliente, datos, indicadores, codigo, propiedades):
        with self._bloqueo:
            self._limpiar_lectura()
            self._suscrita = False
            self._suscrita_leds = False
            self._conectada = not codigo.is_failure
            self._motivo = "Conexión MQTT rechazada por el broker."
            self._cambio.notify_all()
        if codigo.is_failure:
            registro.error("EMQX rechazó la conexión MQTT (código %s).", codigo.value)
            return
        resultado, _ = cliente.subscribe([
            (topico_distancia, 0), (topico_sensor, 0), (topico_disponibilidad, 1),
            *((topico, 1) for topico in topicos_leds),
        ])
        with self._bloqueo:
            self._motivo = (
                "Esperando confirmación de suscripciones MQTT."
                if resultado == mqtt.MQTT_ERR_SUCCESS
                else "No se pudieron solicitar las suscripciones MQTT."
            )
        registro.info("Conexión MQTT establecida; suscripciones solicitadas.")

    def _al_suscribir(self, cliente, datos, identificador, codigos, propiedades):
        telemetria_aceptada = len(codigos) == 6 and all(not codigo.is_failure for codigo in codigos[:3])
        leds_aceptados = len(codigos) == 6 and all(not codigo.is_failure for codigo in codigos[3:])
        aceptada = telemetria_aceptada and leds_aceptados
        with self._bloqueo:
            self._suscrita = telemetria_aceptada
            self._suscrita_leds = leds_aceptados
            self._motivo = (
                "Suscripciones MQTT listas."
                if aceptada else "El broker rechazó una suscripción MQTT."
            )
            self._cambio.notify_all()
        if aceptada:
            registro.info("Las seis suscripciones MQTT están confirmadas.")
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
            self._suscrita_leds = False
            self._motivo = "MQTT desconectado; no se puede comprobar el estado del ESP32."
            self._limpiar_lectura()
            self._cambio.notify_all()
        registro.warning("Conexión MQTT cerrada.")

    def _al_mensaje(self, cliente, datos, mensaje):
        if mensaje.topic not in (topico_distancia, topico_sensor, topico_disponibilidad, *topicos_leds):
            return
        try:
            if len(mensaje.payload) > 64:
                raise ValueError("Mensaje demasiado largo.")
            texto = mensaje.payload.decode("utf-8")
            if mensaje.topic in (topico_distancia, topico_sensor) and mensaje.retain:
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
            elif mensaje.topic in topicos_leds and texto not in ("on", "off"):
                raise ValueError("Estado de LED desconocido.")
        except (UnicodeError, ValueError):
            with self._bloqueo:
                # No conservar una lectura anterior como actual tras un mensaje erróneo.
                if mensaje.topic == topico_distancia:
                    self._distancia = self._instante_distancia = None
                elif mensaje.topic == topico_sensor:
                    self._estado_sensor = self._instante_sensor = None
                elif mensaje.topic == topico_disponibilidad:
                    self._disponibilidad = None
                else:
                    self._estados_leds[topicos_leds[mensaje.topic]] = None
                self._cambio.notify_all()
            registro.warning("Mensaje MQTT rechazado en un tópico suscrito.")
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
            elif mensaje.topic == topico_disponibilidad:
                if texto == "offline" or self._disponibilidad == "offline":
                    self._sesion += 1
                    self._distancia = self._instante_distancia = None
                    self._estado_sensor = self._instante_sensor = None
                self._disponibilidad = texto
            else:
                self._numero_estado += 1
                self._estados_leds[topicos_leds[mensaje.topic]] = {
                    "estado": texto, "instante": monotonic(), "retenido": bool(mensaje.retain),
                    "numero": self._numero_estado, "sesion": self._sesion,
                }
            self._cambio.notify_all()

    @staticmethod
    def _preparar_comando(color, accion, solo):
        if type(color) is not str or color not in ("rojo", "amarillo", "verde", "todos"):
            raise ValueError("Color permitido: rojo, amarillo, verde o todos.")
        if type(accion) is not str or accion not in ("encender", "apagar"):
            raise ValueError("Acción permitida: encender o apagar.")
        if type(solo) is not bool:
            raise ValueError("solo debe ser un booleano.")
        if solo and (color == "todos" or accion != "encender"):
            raise ValueError("solo únicamente permite encender un LED individual.")
        valor = "off"
        if accion == "encender":
            valor = "on"
        esperados = {}
        if solo:
            for led in topicos_leds.values():
                if led == color:
                    esperados[led] = "on"
                else:
                    esperados[led] = "off"
            return "solo:" + color, esperados
        if color == "todos":
            for led in topicos_leds.values():
                esperados[led] = valor
        else:
            esperados[color] = valor
        return color + ":" + valor, esperados

    def consultar_leds(self) -> dict:
        """Últimos informes MQTT: no equivalen a comprobación física de los LEDs."""
        with self._bloqueo:
            conexion_lista = self._conectada and self._suscrita
            estados = {}
            ahora = monotonic()
            for color, dato in self._estados_leds.items():
                if dato is None:
                    estados[color] = {"estado": "desconocido", "referencia": "sin_datos"}
                    continue
                edad = ahora - dato["instante"]
                reciente = (
                    conexion_lista and self._suscrita_leds and self._disponibilidad == "online"
                    and dato["sesion"] == self._sesion and not dato["retenido"]
                    and edad <= self._antiguedad_maxima
                )
                referencia = "ultimo_estado_conocido"
                if reciente:
                    referencia = "informe_reciente"
                estados[color] = {
                    "estado": dato["estado"], "antiguedad_segundos": round(edad, 3),
                    "retenido": dato["retenido"],
                    "referencia": referencia,
                }
            return {
                "conexion_mqtt": conexion_lista,
                "suscripcion_leds": self._suscrita_leds,
                "disponibilidad_esp32": self._disponibilidad or "desconocida",
                "leds": estados,
                "mensaje": "Estados informados por MQTT; no verifican iluminación física ni una orden concreta.",
            }

    def controlar_led(self, color, accion, solo=False) -> dict:
        """Publica una orden idempotente y espera evidencia MQTT durante un plazo acotado."""
        try:
            comando, esperados = self._preparar_comando(color, accion, solo)
        except ValueError as error:
            return {"estado": "rechazado", "mensaje": str(error)}
        if not self._bloqueo_comandos.acquire(blocking=False):
            return {"estado": "ocupado", "mensaje": "Hay otra orden en curso; no se publicó esta orden."}
        try:
            limite = monotonic() + tiempo_limite_comando
            with self._cambio:
                if not self._conectada or not self._suscrita or not self._suscrita_leds:
                    return {"estado": "no_enviado", "mensaje": self._motivo}
                if self._disponibilidad != "online":
                    return {"estado": "no_enviado", "mensaje": "El ESP32 no tiene disponibilidad online anunciada."}
                sesion = self._sesion
                numero_inicial = self._numero_estado
                # Capturar la referencia y publicar sin permitir actualizaciones intermedias.
                try:
                    publicacion = self._cliente.publish(topico_comandos, comando, qos=1, retain=False)
                except (OSError, ValueError, RuntimeError):
                    return {"estado": "envio_sin_confirmar", "comando": comando,
                            "mensaje": "No se pudo confirmar el envío de la orden al broker."}
            recibido_por_broker = False
            try:
                restante = limite - monotonic()
                if publicacion.rc == mqtt.MQTT_ERR_SUCCESS and restante > 0:
                    publicacion.wait_for_publish(timeout=restante)
                    recibido_por_broker = publicacion.is_published()
            except (ValueError, RuntimeError, OSError):
                registro.warning("No se pudo confirmar la publicación del comando MQTT.")

            with self._cambio:
                coinciden = False
                while recibido_por_broker:
                    if (self._sesion != sesion or not self._conectada
                            or not self._suscrita or not self._suscrita_leds
                            or self._disponibilidad != "online"):
                        break
                    coinciden = True
                    for color, valor_esperado in esperados.items():
                        dato = self._estados_leds[color]
                        if dato is None:
                            coinciden = False
                            break
                        if dato["estado"] != valor_esperado or dato["retenido"]:
                            coinciden = False
                            break
                        if dato["numero"] <= numero_inicial or dato["instante"] > limite:
                            coinciden = False
                            break
                    restante = limite - monotonic()
                    if coinciden or restante <= 0:
                        break
                    self._cambio.wait(timeout=restante)
            if coinciden:
                estado = "estado_informado"
                mensaje = (
                    "El broker recibió la orden y llegaron estados nuevos coincidentes. "
                    "Sin identificador de orden no se demuestra causalidad ni encendido físico."
                )
            elif recibido_por_broker:
                estado = "enviado_sin_verificar"
                mensaje = "Orden enviada al broker; su ejecución no pudo verificarse mediante estados nuevos coincidentes."
            else:
                estado = "envio_sin_confirmar"
                mensaje = "No se recibió confirmación del broker dentro del plazo; el resultado del envío es incierto."
            confirmacion_broker = "no_recibida"
            if recibido_por_broker:
                confirmacion_broker = "recibida"
            return {
                "estado": estado, "comando": comando,
                "confirmacion_broker": confirmacion_broker,
                "estados_coincidentes": coinciden, "estados_esperados": esperados,
                "mensaje": mensaje,
            }
        finally:
            self._bloqueo_comandos.release()

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
