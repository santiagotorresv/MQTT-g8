"""Control MQTT simulado: estas pruebas nunca publican en EMQX."""

from threading import Event, Thread
import unittest
from unittest.mock import MagicMock, patch

import paho.mqtt.client as mqtt

from conexion_mqtt import topico_comandos, topico_disponibilidad, prefijo
import test_conexion_mqtt as pruebas_mqtt


class PruebasControlLeds(unittest.TestCase):
    def setUp(self):
        self.datos = pruebas_mqtt.PruebasConexionMqtt()
        self.datos.setUp()
        self.addCleanup(self.datos.doCleanups)
        # La espera acotada usa tiempo real, no el reloj fijo de pruebas del sensor.
        self.datos.parche_reloj.stop()
        self.conexion = self.datos.conexion
        self.cliente = self.datos.cliente
        self.datos.enviar(topico_disponibilidad, "online", retenido=True)
        self.publicacion = MagicMock(spec=mqtt.MQTTMessageInfo)
        self.publicacion.rc = mqtt.MQTT_ERR_SUCCESS
        self.publicacion.is_published.return_value = True
        self.cliente.publish.return_value = self.publicacion
        self.parche_plazo = patch("conexion_mqtt.tiempo_limite_comando", 0.05)
        self.parche_plazo.start()
        self.addCleanup(self.parche_plazo.stop)

    def enviar_estados(self, estados, retenido=False):
        for color, valor in estados.items():
            self.datos.enviar(prefijo + "state/" + color, valor, retenido)

    def test_los_once_comandos_qos_y_retain(self):
        casos = [
            ("rojo", "encender", False, "rojo:on", {"rojo": "on"}),
            ("rojo", "apagar", False, "rojo:off", {"rojo": "off"}),
            ("amarillo", "encender", False, "amarillo:on", {"amarillo": "on"}),
            ("amarillo", "apagar", False, "amarillo:off", {"amarillo": "off"}),
            ("verde", "encender", False, "verde:on", {"verde": "on"}),
            ("verde", "apagar", False, "verde:off", {"verde": "off"}),
            ("todos", "encender", False, "todos:on", {"rojo": "on", "amarillo": "on", "verde": "on"}),
            ("todos", "apagar", False, "todos:off", {"rojo": "off", "amarillo": "off", "verde": "off"}),
            ("rojo", "encender", True, "solo:rojo", {"rojo": "on", "amarillo": "off", "verde": "off"}),
            ("amarillo", "encender", True, "solo:amarillo", {"rojo": "off", "amarillo": "on", "verde": "off"}),
            ("verde", "encender", True, "solo:verde", {"rojo": "off", "amarillo": "off", "verde": "on"}),
        ]
        for color, accion, solo, comando, esperados in casos:
            with self.subTest(comando=comando):
                self.publicacion.wait_for_publish.side_effect = (
                    lambda timeout, valores=esperados: self.enviar_estados(valores)
                )
                resultado = self.conexion.controlar_led(color, accion, solo)
                self.cliente.publish.assert_called_with(topico_comandos, comando, qos=1, retain=False)
                self.assertEqual(resultado["estado"], "estado_informado")
                self.assertEqual(resultado["estados_esperados"], esperados)
                self.assertEqual(resultado["confirmacion_broker"], "recibida")
        self.assertEqual(self.cliente.publish.call_count, 11)
        self.cliente.connect_async.assert_not_called()

    def test_rechazo_de_parametros_sin_publicar(self):
        casos = [
            ("azul", "encender", False), ("Rojo", "encender", False),
            ("rojo ", "encender", False), (None, "encender", False),
            ([], "encender", False), (True, "encender", False),
            ("rojo", "toggle", False), ("rojo", "on", False),
            ("rojo", None, False), ("rojo", 1, False),
            ("todos", "encender", True), ("todos", "apagar", True),
            ("rojo", "apagar", True), ("amarillo", "apagar", True),
            ("verde", "apagar", True), ("rojo", "encender", "false"),
            ("rojo", "encender", 0), ("rojo", "encender", 1),
            ("rojo", "encender", None),
        ]
        for parametros in casos:
            with self.subTest(parametros=parametros):
                self.assertEqual(self.conexion.controlar_led(*parametros)["estado"], "rechazado")
        self.cliente.publish.assert_not_called()

    def test_estados_desconocidos(self):
        consulta = self.conexion.consultar_leds()
        self.assertEqual({dato["estado"] for dato in consulta["leds"].values()}, {"desconocido"})
        self.cliente.publish.assert_not_called()

    def test_estados_conocidos_retenidos(self):
        self.enviar_estados({"rojo": "on", "amarillo": "off"}, retenido=True)
        consulta = self.conexion.consultar_leds()["leds"]
        self.assertEqual(consulta["rojo"]["estado"], "on")
        self.assertEqual(consulta["amarillo"]["estado"], "off")
        self.assertEqual(consulta["verde"]["estado"], "desconocido")
        self.assertTrue(consulta["rojo"]["retenido"])
        self.assertEqual(consulta["rojo"]["referencia"], "ultimo_estado_conocido")

    def test_informe_reciente_y_antiguo(self):
        self.enviar_estados({"verde": "on"})
        self.assertEqual(self.conexion.consultar_leds()["leds"]["verde"]["referencia"], "informe_reciente")
        with patch("conexion_mqtt.monotonic", return_value=10**12):
            self.assertEqual(self.conexion.consultar_leds()["leds"]["verde"]["referencia"], "ultimo_estado_conocido")

    def test_estado_malformado_se_vuelve_desconocido(self):
        for texto in ("toggle", "ON", "on\n", "", b"\xff", "x" * 65):
            with self.subTest(texto=texto):
                self.enviar_estados({"rojo": "on"})
                self.datos.enviar(prefijo + "state/rojo", texto)
                self.assertEqual(self.conexion.consultar_leds()["leds"]["rojo"]["estado"], "desconocido")

    def test_desconexion_impide_publicar_y_marca_historial(self):
        self.enviar_estados({"rojo": "on"})
        self.conexion._al_desconectar(self.cliente, None, None, None, None)
        self.assertEqual(self.conexion.controlar_led("rojo", "apagar")["estado"], "no_enviado")
        consulta = self.conexion.consultar_leds()
        self.assertFalse(consulta["conexion_mqtt"])
        self.assertEqual(consulta["leds"]["rojo"]["referencia"], "ultimo_estado_conocido")
        self.cliente.publish.assert_not_called()

    def test_offline_o_disponibilidad_desconocida_impiden_publicar(self):
        for valor in ("offline", "desconocida"):
            with self.subTest(valor=valor):
                self.datos.enviar(topico_disponibilidad, valor)
                self.assertEqual(self.conexion.controlar_led("todos", "apagar")["estado"], "no_enviado")
        self.cliente.publish.assert_not_called()

    def test_sin_subscripciones_no_publica(self):
        self.conexion._suscrita = False
        self.assertEqual(self.conexion.controlar_led("verde", "encender")["estado"], "no_enviado")
        self.cliente.publish.assert_not_called()

    def test_timeout_sin_informes_nuevos(self):
        resultado = self.conexion.controlar_led("rojo", "encender")
        self.assertEqual(resultado["estado"], "enviado_sin_verificar")
        self.assertEqual(resultado["confirmacion_broker"], "recibida")
        self.assertFalse(resultado["estados_coincidentes"])

    def test_estado_anterior_no_verifica_orden(self):
        self.enviar_estados({"rojo": "on"})
        self.assertEqual(self.conexion.controlar_led("rojo", "encender")["estado"], "enviado_sin_verificar")

    def test_retained_recibido_despues_no_verifica_orden(self):
        self.publicacion.wait_for_publish.side_effect = lambda timeout: self.enviar_estados({"rojo": "on"}, True)
        self.assertEqual(self.conexion.controlar_led("rojo", "encender")["estado"], "enviado_sin_verificar")

    def test_solo_exige_los_tres_estados(self):
        self.publicacion.wait_for_publish.side_effect = lambda timeout: self.enviar_estados({"verde": "on"})
        self.assertEqual(self.conexion.controlar_led("verde", "encender", True)["estado"], "enviado_sin_verificar")

    def test_estado_distinto_no_verifica_orden(self):
        self.publicacion.wait_for_publish.side_effect = lambda timeout: self.enviar_estados({"rojo": "off"})
        self.assertEqual(self.conexion.controlar_led("rojo", "encender")["estado"], "enviado_sin_verificar")

    def test_sin_puback_no_afirma_envio(self):
        self.publicacion.is_published.return_value = False
        resultado = self.conexion.controlar_led("rojo", "encender")
        self.assertEqual(resultado["estado"], "envio_sin_confirmar")
        self.assertEqual(resultado["confirmacion_broker"], "no_recibida")
        plazo = self.publicacion.wait_for_publish.call_args.kwargs["timeout"]
        self.assertGreater(plazo, 0)
        self.assertLessEqual(plazo, 0.051)

    def test_error_publicando_no_se_reintenta(self):
        self.cliente.publish.side_effect = OSError("fallo simulado")
        self.assertEqual(self.conexion.controlar_led("rojo", "encender")["estado"], "envio_sin_confirmar")
        self.cliente.publish.assert_called_once()

    def test_error_devuelto_por_paho(self):
        self.publicacion.rc = mqtt.MQTT_ERR_NO_CONN
        self.assertEqual(self.conexion.controlar_led("rojo", "encender")["estado"], "envio_sin_confirmar")
        self.publicacion.wait_for_publish.assert_not_called()

    def test_error_esperando_puback(self):
        self.publicacion.wait_for_publish.side_effect = RuntimeError("fallo simulado")
        self.assertEqual(self.conexion.controlar_led("rojo", "encender")["estado"], "envio_sin_confirmar")

    def test_desconexion_durante_confirmacion(self):
        self.publicacion.wait_for_publish.side_effect = (
            lambda timeout: self.conexion._al_desconectar(self.cliente, None, None, None, None)
        )
        self.assertEqual(self.conexion.controlar_led("rojo", "encender")["estado"], "enviado_sin_verificar")

    def test_reconexion_no_verifica_orden_anterior(self):
        def reconectar(timeout):
            self.conexion._al_desconectar(self.cliente, None, None, None, None)
            self.datos.conectar()
            self.datos.enviar(topico_disponibilidad, "online", retenido=True)
            self.enviar_estados({"rojo": "on"})
        self.publicacion.wait_for_publish.side_effect = reconectar
        self.assertEqual(self.conexion.controlar_led("rojo", "encender")["estado"], "enviado_sin_verificar")

    def test_orden_concurrente_no_publica(self):
        with self.conexion._bloqueo_comandos:
            self.assertEqual(self.conexion.controlar_led("rojo", "encender")["estado"], "ocupado")
        self.cliente.publish.assert_not_called()

    def test_estados_desde_otro_hilo_despiertan_la_espera(self):
        esperando = Event()
        espera_original = self.conexion._cambio.wait
        def esperar(timeout):
            esperando.set()
            return espera_original(timeout)
        def responder():
            if esperando.wait(1):
                self.enviar_estados({"rojo": "on"})
        hilo = Thread(target=responder)
        hilo.start()
        try:
            with patch("conexion_mqtt.tiempo_limite_comando", 1):
                with patch.object(self.conexion._cambio, "wait", side_effect=esperar):
                    self.assertEqual(self.conexion.controlar_led("rojo", "encender")["estado"], "estado_informado")
        finally:
            hilo.join(timeout=2)
        self.assertFalse(hilo.is_alive())


if __name__ == "__main__":
    unittest.main()
