"""Pruebas de descubrimiento e invocación con el cliente del SDK oficial."""

import asyncio
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from mcp import Client, StdioServerParameters
from mcp.types import TextContent

from servidor import servidor
import test_conexion_mqtt as pruebas_mqtt
import test_control_leds as pruebas_leds


class PruebasServidor(unittest.IsolatedAsyncioTestCase):
    async def comprobar_herramienta(self, cliente: Client) -> None:
        listado = await cliente.list_tools()
        self.assertEqual(
            [herramienta.name for herramienta in listado.tools],
            ["verificar_conexion", "leer_distancia", "controlar_led", "consultar_leds"],
        )
        self.assertEqual(listado.tools[0].input_schema.get("properties", {}), {})
        self.assertEqual(listado.tools[1].input_schema.get("properties", {}), {})
        self.assertEqual(listado.tools[3].input_schema.get("properties", {}), {})
        parametros = listado.tools[2].input_schema["properties"]
        self.assertFalse(listado.tools[2].input_schema["additionalProperties"])
        self.assertEqual(set(listado.tools[2].input_schema["required"]), {"color", "accion"})
        self.assertEqual(set(parametros), {"color", "accion", "solo"})
        self.assertEqual(parametros["color"]["enum"], ["rojo", "amarillo", "verde", "todos"])
        self.assertEqual(parametros["accion"]["enum"], ["encender", "apagar"])
        self.assertEqual(parametros["solo"]["type"], "boolean")
        self.assertFalse(parametros["solo"]["default"])

        resultado = await cliente.call_tool("verificar_conexion", {})
        self.assertFalse(resultado.is_error)
        self.assertEqual(len(resultado.content), 1)
        self.assertIsInstance(resultado.content[0], TextContent)
        self.assertEqual(
            resultado.content[0].text,
            "Servidor MCP del equipo 08 disponible",
        )

    async def test_herramienta_en_memoria(self) -> None:
        with TemporaryDirectory() as carpeta:
            with patch.dict("os.environ", {"EQUIPO08_CONFIG_MQTT": str(Path(carpeta) / "sin_configuracion.json")}):
                async with asyncio.timeout(20):
                    async with Client(servidor, raise_exceptions=True) as cliente:
                        await self.comprobar_herramienta(cliente)
                        resultado = await cliente.call_tool("leer_distancia", {})
                        self.assertFalse(resultado.is_error)
                        self.assertEqual(json.loads(resultado.content[0].text)["estado"], "mqtt_no_disponible")
                        consulta = await cliente.call_tool("consultar_leds", {})
                        self.assertFalse(consulta.is_error)
                        self.assertFalse(json.loads(consulta.content[0].text)["conexion_mqtt"])
                        orden = await cliente.call_tool("controlar_led", {"color": "rojo", "accion": "encender"})
                        self.assertFalse(orden.is_error)
                        self.assertEqual(json.loads(orden.content[0].text)["estado"], "no_enviado")

    async def test_lectura_mcp_con_datos_simulados(self) -> None:
        prueba = pruebas_mqtt.PruebasConexionMqtt()
        prueba.setUp()
        self.addCleanup(prueba.doCleanups)
        prueba.lectura_valida()
        with patch("servidor.ConexionMqtt.desde_archivo", return_value=prueba.conexion):
            with patch.object(prueba.conexion, "iniciar"), patch.object(prueba.conexion, "detener"):
                async with asyncio.timeout(20):
                    async with Client(servidor, raise_exceptions=True) as cliente:
                        resultado = await cliente.call_tool("leer_distancia", {})
                        self.assertFalse(resultado.is_error)
                        lectura = json.loads(resultado.content[0].text)
                        self.assertEqual(lectura["estado"], "valida")
                        self.assertEqual(lectura["distancia_cm"], 24.6)

    async def test_herramienta_por_stdio(self) -> None:
        with TemporaryDirectory() as carpeta:
            parametros = StdioServerParameters(
                command=sys.executable,
                args=[str(Path(__file__).resolve().with_name("servidor.py"))],
                env={"EQUIPO08_CONFIG_MQTT": str(Path(carpeta) / "sin_configuracion.json")},
            )
            async with asyncio.timeout(20):
                async with Client(parametros) as cliente:
                    await self.comprobar_herramienta(cliente)
                    resultado = await cliente.call_tool("leer_distancia", {})
                    self.assertFalse(resultado.is_error)
                    self.assertEqual(json.loads(resultado.content[0].text)["estado"], "mqtt_no_disponible")
                    consulta = await cliente.call_tool("consultar_leds", {})
                    self.assertFalse(consulta.is_error)
                    self.assertEqual(json.loads(consulta.content[0].text)["leds"]["rojo"]["estado"], "desconocido")
                    orden = await cliente.call_tool("controlar_led", {"color": "todos", "accion": "apagar"})
                    self.assertFalse(orden.is_error)
                    self.assertEqual(json.loads(orden.content[0].text)["estado"], "no_enviado")

                    orden_invalida = await cliente.call_tool(
                        "controlar_led",
                        {"color": "rojo", "accion": "encender", "exclusivo": True},
                    )
                    self.assertTrue(orden_invalida.is_error)

    async def test_control_y_consulta_mcp_simulados(self) -> None:
        prueba = pruebas_leds.PruebasControlLeds()
        prueba.setUp()
        self.addCleanup(prueba.doCleanups)
        prueba.publicacion.wait_for_publish.side_effect = (
            lambda timeout: prueba.enviar_estados({"rojo": "off", "amarillo": "off", "verde": "on"})
        )
        with patch("servidor.ConexionMqtt.desde_archivo", return_value=prueba.conexion):
            with patch.object(prueba.conexion, "iniciar"), patch.object(prueba.conexion, "detener"):
                async with asyncio.timeout(20):
                    async with Client(servidor, raise_exceptions=True) as cliente:
                        orden = await cliente.call_tool(
                            "controlar_led", {"color": "verde", "accion": "encender", "solo": True}
                        )
                        self.assertFalse(orden.is_error)
                        self.assertEqual(json.loads(orden.content[0].text)["estado"], "estado_informado")
                        consulta = await cliente.call_tool("consultar_leds", {})
                        self.assertFalse(consulta.is_error)
                        valores = json.loads(consulta.content[0].text)["leds"]
                        self.assertEqual(valores["verde"]["estado"], "on")
                        self.assertEqual(valores["rojo"]["estado"], "off")

    async def test_parametros_mcp_invalidos_no_publican(self) -> None:
        prueba = pruebas_leds.PruebasControlLeds()
        prueba.setUp()
        self.addCleanup(prueba.doCleanups)
        with patch("servidor.ConexionMqtt.desde_archivo", return_value=prueba.conexion):
            with patch.object(prueba.conexion, "iniciar"), patch.object(prueba.conexion, "detener"):
                async with asyncio.timeout(20):
                    async with Client(servidor, raise_exceptions=True) as cliente:
                        for parametros in (
                            {}, {"color": "azul", "accion": "encender"},
                            {"color": "rojo", "accion": "toggle"},
                            {"color": 1, "accion": "encender"},
                            *({"color": "rojo", "accion": "encender", "solo": valor}
                              for valor in ("false", "true", 0, 1, None)),
                        ):
                            with self.subTest(parametros=parametros):
                                resultado = await cliente.call_tool("controlar_led", parametros)
                                self.assertTrue(resultado.is_error)
                        resultado = await cliente.call_tool(
                            "controlar_led", {"color": "todos", "accion": "encender", "solo": True}
                        )
                        self.assertFalse(resultado.is_error)
                        self.assertEqual(json.loads(resultado.content[0].text)["estado"], "rechazado")
                        prueba.cliente.publish.assert_not_called()

    async def test_argumentos_desconocidos_no_publican(self) -> None:
        prueba = pruebas_leds.PruebasControlLeds()
        prueba.setUp()
        self.addCleanup(prueba.doCleanups)
        with patch("servidor.ConexionMqtt.desde_archivo", return_value=prueba.conexion):
            with patch.object(prueba.conexion, "iniciar"), patch.object(prueba.conexion, "detener"):
                async with asyncio.timeout(20):
                    async with Client(servidor, raise_exceptions=True) as cliente:
                        for nombre_extra in ("exclusivo", "retain", "contexto"):
                            with self.subTest(nombre_extra=nombre_extra):
                                resultado = await cliente.call_tool(
                                    "controlar_led",
                                    {"color": "rojo", "accion": "encender", nombre_extra: True},
                                )
                                self.assertTrue(resultado.is_error)
                                prueba.cliente.publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
