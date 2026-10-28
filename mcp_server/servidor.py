"""Servidor MCP local de comprobación del equipo 08, sin conexión MQTT."""

from mcp.server import MCPServer


servidor = MCPServer("Equipo 08")


@servidor.tool()
def verificar_conexion() -> str:
    """Comprueba que el servidor MCP local está disponible."""
    return "Servidor MCP del equipo 08 disponible"


if __name__ == "__main__":
    servidor.run(transport="stdio")
