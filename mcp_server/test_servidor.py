"""Pruebas de descubrimiento e invocación con el cliente del SDK oficial."""

import asyncio
from pathlib import Path
import sys
import unittest

from mcp import Client, StdioServerParameters
from mcp.types import TextContent

from servidor import servidor


class PruebasServidor(unittest.IsolatedAsyncioTestCase):
    async def comprobar_herramienta(self, cliente: Client) -> None:
        listado = await cliente.list_tools()
        self.assertEqual(
            [herramienta.name for herramienta in listado.tools],
            ["verificar_conexion"],
        )
        self.assertEqual(listado.tools[0].input_schema.get("properties", {}), {})

        resultado = await cliente.call_tool("verificar_conexion", {})
        self.assertFalse(resultado.is_error)
        self.assertEqual(len(resultado.content), 1)
        self.assertIsInstance(resultado.content[0], TextContent)
        self.assertEqual(
            resultado.content[0].text,
            "Servidor MCP del equipo 08 disponible",
        )

    async def test_herramienta_en_memoria(self) -> None:
        async with asyncio.timeout(20):
            async with Client(servidor, raise_exceptions=True) as cliente:
                await self.comprobar_herramienta(cliente)

    async def test_herramienta_por_stdio(self) -> None:
        parametros = StdioServerParameters(
            command=sys.executable,
            args=[str(Path(__file__).resolve().with_name("servidor.py"))],
        )
        async with asyncio.timeout(20):
            async with Client(parametros) as cliente:
                await self.comprobar_herramienta(cliente)


if __name__ == "__main__":
    unittest.main()
