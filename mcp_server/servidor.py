"""Servidor MCP del equipo 08: disponibilidad local y consulta MQTT del sensor."""

import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Literal

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
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


servidor = MCPServer("Equipo 08", lifespan=ciclo_de_vida)


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
