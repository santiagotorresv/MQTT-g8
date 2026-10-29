"""Servidor MCP del equipo 08: disponibilidad local y consulta MQTT del sensor."""

import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Literal

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import StrictBool

from conexion_mqtt import ConexionMqtt


@asynccontextmanager
async def ciclo_de_vida(aplicacion: MCPServer):
    ruta = Path(os.environ.get(
        "EQUIPO08_CONFIG_MQTT",
        str(Path(__file__).resolve().with_name("configuracion_mqtt.local.json")),
    ))
    conexion = ConexionMqtt.desde_archivo(ruta)
    try:
        conexion.iniciar()
        yield conexion
    finally:
        await asyncio.to_thread(conexion.detener)


class ServidorEquipo(MCPServer):
    """Valida las claves originales antes de que el SDK descarte las adicionales."""

    async def call_tool(self, name, arguments, context=None):
        # Se conservan los nombres de parámetros de la API oficial sobrescrita.
        if name == "controlar_led":
            for parametro in arguments:
                if parametro not in ("color", "accion", "solo"):
                    raise ToolError("controlar_led solo admite color, accion y solo.")
        return await super().call_tool(name, arguments, context)

    async def list_tools(self):
        herramientas = await super().list_tools()
        for herramienta in herramientas:
            if herramienta.name == "controlar_led":
                herramienta.input_schema["additionalProperties"] = False
        return herramientas


servidor = ServidorEquipo("Equipo 08", lifespan=ciclo_de_vida)


@servidor.tool()
def verificar_conexion() -> str:
    """Comprueba que el servidor MCP local está disponible."""
    return "Servidor MCP del equipo 08 disponible"


@servidor.tool()
def leer_distancia(contexto: Context[ConexionMqtt]) -> dict:
    """Consulta la última distancia MQTT; distingue ausencia, invalidez y antigüedad."""
    return contexto.request_context.lifespan_context.consultar_distancia()


@servidor.tool()
async def controlar_led(
    color: Literal["rojo", "amarillo", "verde", "todos"],
    accion: Literal["encender", "apagar"],
    contexto: Context[ConexionMqtt],
    solo: StrictBool = False,
) -> dict:
    """Enciende o apaga LEDs de color fijo: 'prende el rojo', 'apaga las luces'.

    Para 'deja solamente el verde', usar verde, encender y solo=true.
    solo es válido únicamente al encender un LED individual. Para todos usar solo=false.
    Ante frases ambiguas, como 'pon todos los focos en verde', pedir aclaración antes
    de actuar: los LEDs tienen colores fijos. No confundir PUBACK o estados MQTT con
    encendido físico. Espera hasta 3 segundos por evidencia MQTT, sin reintentos de la herramienta.
    """
    conexion = contexto.request_context.lifespan_context
    return await asyncio.to_thread(conexion.controlar_led, color, accion, solo)


@servidor.tool()
def consultar_leds(contexto: Context[ConexionMqtt]) -> dict:
    """Consulta qué luces están prendidas según los últimos estados MQTT recibidos.

    Distingue colores desconocidos, informes recientes y últimos estados conocidos.
    Los estados retained o antiguos no verifican una orden nueva ni iluminación física.
    """
    return contexto.request_context.lifespan_context.consultar_leds()


if __name__ == "__main__":
    servidor.run(transport="stdio")
