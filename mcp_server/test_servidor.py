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


class PruebasServidor(unittest.IsolatedAsyncioTestCase):
    async def comprobar_herramienta(self, cliente: Client) -> None:
        listado = await cliente.list_tools()
        self.assertEqual(
            [herramienta.name for herramienta in listado.tools],
            ["verificar_conexion", "leer_distancia"],
        )
        self.assertEqual(listado.tools[0].input_schema.get("properties", {}), {})
        self.assertEqual(listado.tools[1].input_schema.get("properties", {}), {})

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


if __name__ == "__main__":
    unittest.main()
