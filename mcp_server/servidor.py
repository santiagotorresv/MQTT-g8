"""Servidor MCP del equipo 08: disponibilidad local y consulta MQTT del sensor."""

import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path

from mcp.server import MCPServer
from mcp.server.mcpserver import Context

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


if __name__ == "__main__":
    servidor.run(transport="stdio")
