"""Mensajes y reloj simulados exclusivamente para pruebas, sin acceso al broker."""

import ssl
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import paho.mqtt.client as mqtt

from conexion_mqtt import (
    ConexionMqtt, topico_distancia, topico_sensor, topico_disponibilidad,
)


class PruebasConexionMqtt(unittest.TestCase):
    def setUp(self):
        self.ahora = 100.0
        self.parche_reloj = patch("conexion_mqtt.monotonic", side_effect=lambda: self.ahora)
        self.parche_reloj.start()
        self.addCleanup(self.parche_reloj.stop)
        self.cliente = MagicMock()
        self.cliente.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 1)
        self.cliente.loop_start.return_value = mqtt.MQTT_ERR_SUCCESS
        self.parche_cliente = patch("conexion_mqtt.mqtt.Client", return_value=self.cliente)
        self.parche_cliente.start()
        self.addCleanup(self.parche_cliente.stop)
        self.conexion = ConexionMqtt()
        self.conectar()

    def conectar(self):
        codigo = SimpleNamespace(is_failure=False)
        self.conexion._al_conectar(self.cliente, None, None, codigo, None)
        self.conexion._al_suscribir(self.cliente, None, 1, [codigo] * 3, None)

    def enviar(self, topico, texto, retenido=False):
        mensaje = mqtt.MQTTMessage()
        mensaje.topic = topico.encode()
        mensaje.payload = texto.encode() if isinstance(texto, str) else texto
        mensaje.retain = retenido
        self.conexion._al_mensaje(self.cliente, None, mensaje)

    def lectura_valida(self):
        self.enviar(topico_disponibilidad, "online", retenido=True)
        self.enviar(topico_sensor, "valid")
        self.enviar(topico_distancia, "24.6")

    def test_distancia_valida(self):
        self.lectura_valida()
        resultado = self.conexion.consultar_distancia()
        self.assertEqual(resultado["estado"], "valida")
        self.assertEqual(resultado["distancia_cm"], 24.6)
        self.assertEqual(resultado["unidad"], "cm")
        self.assertEqual(resultado["antiguedad_segundos"], 0)
        self.assertEqual(resultado["origen"], "ESP32 mediante MQTT")

    def test_sensor_invalido_no_reutiliza_numero(self):
        self.lectura_valida()
        self.enviar(topico_sensor, "invalid")
        resultado = self.conexion.consultar_distancia()
        self.assertEqual(resultado["estado"], "invalida")
        self.assertNotIn("distancia_cm", resultado)
        self.enviar(topico_sensor, "valid")
        self.assertEqual(self.conexion.consultar_distancia()["estado"], "sin_datos")

    def test_ausencia_de_datos(self):
        self.assertEqual(self.conexion.consultar_distancia()["estado"], "sin_datos")

    def test_valid_sin_distancia(self):
        self.enviar(topico_disponibilidad, "online")
        self.enviar(topico_sensor, "valid")
        self.assertEqual(self.conexion.consultar_distancia()["estado"], "sin_datos")

    def test_distancia_desactualizada(self):
        self.lectura_valida()
        self.ahora += 5.001
        self.enviar(topico_sensor, "valid")
        resultado = self.conexion.consultar_distancia()
        self.assertEqual(resultado["estado"], "desactualizada")
        self.assertNotIn("distancia_cm", resultado)

    def test_estado_sensor_desactualizado(self):
        self.lectura_valida()
        self.ahora += 5.001
        self.enviar(topico_distancia, "25.0")
        self.assertEqual(self.conexion.consultar_distancia()["estado"], "desactualizada")

    def test_limite_de_cinco_segundos(self):
        self.lectura_valida()
        self.ahora += 5
        self.assertEqual(self.conexion.consultar_distancia()["estado"], "valida")

    def test_desconexion_mqtt(self):
        self.lectura_valida()
        self.conexion._al_desconectar(self.cliente, None, None, None, None)
        resultado = self.conexion.consultar_distancia()
        self.assertEqual(resultado["estado"], "mqtt_no_disponible")
        self.assertNotIn("distancia_cm", resultado)

    def test_esp32_offline(self):
        self.lectura_valida()
        self.enviar(topico_disponibilidad, "offline", retenido=True)
        resultado = self.conexion.consultar_distancia()
        self.assertEqual(resultado["estado"], "esp32_desconectado")
        self.assertNotIn("distancia_cm", resultado)

    def test_reconexion_exige_datos_nuevos(self):
        self.lectura_valida()
        self.conexion._al_desconectar(self.cliente, None, None, None, None)
        self.conectar()
        self.enviar(topico_disponibilidad, "online", retenido=True)
        self.assertEqual(self.conexion.consultar_distancia()["estado"], "sin_datos")
        self.lectura_valida()
        self.assertEqual(self.conexion.consultar_distancia()["estado"], "valida")

    def test_mensajes_malformados(self):
        for texto in ("", "NaN", "Infinity", "-1", "0", "401", "24,6", '{"cm":24.6}',
                      "24.6\n", "9" * 65, b"\xff"):
            with self.subTest(texto=texto):
                self.lectura_valida()
                self.enviar(topico_distancia, texto)
                self.assertNotIn("distancia_cm", self.conexion.consultar_distancia())

    def test_estados_desconocidos(self):
        for topico in (topico_sensor, topico_disponibilidad):
            with self.subTest(topico=topico):
                self.lectura_valida()
                self.enviar(topico, "desconocido")
                self.assertNotIn("distancia_cm", self.conexion.consultar_distancia())

    def test_telemetria_retenida_rechazada(self):
        for topico, texto in ((topico_distancia, "24.6"), (topico_sensor, "valid")):
            with self.subTest(topico=topico):
                self.lectura_valida()
                self.enviar(topico, texto, retenido=True)
                self.assertNotIn("distancia_cm", self.conexion.consultar_distancia())

    def test_suscripcion_rechazada(self):
        self.lectura_valida()
        fallo = SimpleNamespace(is_failure=True)
        self.conexion._al_suscribir(self.cliente, None, 1, [fallo] * 3, None)
        self.assertEqual(self.conexion.consultar_distancia()["estado"], "mqtt_no_disponible")

    def test_suscripciones_y_sesion(self):
        self.cliente.subscribe.assert_called_with([
            (topico_distancia, 0), (topico_sensor, 0), (topico_disponibilidad, 1)
        ])
        self.conexion.consultar_distancia()
        self.cliente.publish.assert_not_called()

    def test_inicio_tls_y_cierre(self):
        conexion = ConexionMqtt("usuario_de_prueba", "clave_de_prueba")
        conexion.iniciar()
        contexto = self.cliente.tls_set_context.call_args.args[0]
        self.assertTrue(contexto.check_hostname)
        self.assertEqual(contexto.verify_mode, ssl.CERT_REQUIRED)
        self.cliente.connect_async.assert_called_once_with(
            "zffa4f2f.ala.us-east-1.emqxsl.com", 8883, 30
        )
        conexion.iniciar()
        self.cliente.loop_start.assert_called_once()
        conexion.detener()
        self.cliente.disconnect.assert_called_once()
        self.cliente.loop_stop.assert_called_once()

    def test_umbral_invalido(self):
        for umbral in (0, -1, float("nan"), float("inf"), True, "5"):
            with self.subTest(umbral=umbral):
                with self.assertRaises(ValueError):
                    ConexionMqtt(antiguedad_maxima_segundos=umbral)


if __name__ == "__main__":
    unittest.main()
