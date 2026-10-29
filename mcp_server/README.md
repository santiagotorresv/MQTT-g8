# Servidor MCP local · Equipo 08

El equipo confirmó que `verificar_conexion` se ejecutó correctamente desde Claude Desktop Free. La segunda subiteración incorpora la conexión MQTT y `leer_distancia`; su [guía de integración](../docs/integracion_mcp_mqtt.md) documenta la configuración privada y las pruebas actuales. La consulta real de distancia desde Claude y RF6 completo siguen pendientes; todavía no hay control de LEDs desde Python.

## Entorno y archivos

- Python comprobado: **3.12.6**, de 64 bits. El proyecto requiere Python 3.11 o superior.
- SDK oficial: **mcp==2.3.0**, fijado en `requirements.txt`; se utiliza `MCPServer`, sin FastMCP.
- Entorno independiente: `mcp_server/.venv/`, excluido de Git por las reglas existentes.
- `servidor.py`: instancia `MCPServer`, registra dos herramientas y gestiona una conexión MQTT durante su ciclo de vida.
- `conexion_mqtt.py`: suscripciones y última lectura recibida, protegida con un bloqueo.
- `test_servidor.py`: pruebas con `unittest` y el cliente del SDK, sin bibliotecas de pruebas adicionales.
- `claude_desktop_config.ejemplo.json`: configuración de ejemplo con las rutas absolutas comprobadas en este equipo.

Las dependencias directas son `mcp==2.3.0` y `paho-mqtt==2.1.0`. Pip instala también las dependencias requeridas por el SDK; aunque algunas soportan HTTP, este servidor utiliza exclusivamente `stdio` y no abre un servidor HTTP. No se instalan los extras de CLI.

Se utiliza directamente una instancia de la clase `MCPServer` del SDK y una función registrada; no se añade otra clase propia para devolver una constante.

## Herramienta

| Nombre | Parámetros | Resultado exacto |
|---|---|---|
| `verificar_conexion` | Ninguno | `Servidor MCP del equipo 08 disponible` |
| `leer_distancia` | Ninguno | Última distancia MQTT válida y reciente, o una condición explícita de ausencia, invalidez, antigüedad o desconexión. |

`verificar_conexion` comprueba la disponibilidad del servidor local, no WiFi, EMQX ni el estado físico del ESP32. Mantiene su texto exacto. `leer_distancia` consulta la conexión compartida y no crea conexiones nuevas. No se añaden mensajes de depuración en stdout, reservado para el protocolo; los registros se dirigen a stderr.

El bloque `if __name__ == "__main__"` inicia el servidor únicamente al ejecutar el archivo. Importarlo durante las pruebas no inicia un proceso de servicio.

## Preparar o reproducir el entorno

Desde la raíz del repositorio en PowerShell, con Python 3.11 o superior:

```powershell
python --version
python -m venv mcp_server/.venv
& '.\mcp_server\.venv\Scripts\python.exe' -m pip install -r mcp_server/requirements.txt
& '.\mcp_server\.venv\Scripts\python.exe' -m pip check
& '.\mcp_server\.venv\Scripts\python.exe' -m unittest discover -s mcp_server -p 'test_*.py' -v
```

No es necesario activar el entorno: se invoca su ejecutable directamente. No reutilizar el entorno de PlatformIO. En esta máquina `python` corresponde a Python 3.12.6; el lanzador `py` no detectó instalaciones, por lo que no se utiliza en estas instrucciones.

Las pruebas comprueban las dos herramientas, sin parámetros expuestos al modelo. Se mantiene la validación exacta de `verificar_conexion` y se comprueban los estados de `leer_distancia`. Se usa `Client(servidor)` en memoria y `Client(StdioServerParameters(...))` por `stdio`. Las pruebas MCP tienen un timeout de 20 segundos. La guía de integración registra los 20 casos actuales y distingue mensajes simulados de datos reales.

Registro de la primera subiteración, **28 de octubre de 2026**: importación de `mcp` y `MCPServer` correcta, `pip check` sin conflictos y 2 pruebas aprobadas, en 2,795 s, con salida 0. Se comprobaron ambas rutas del ejemplo y la exclusión del entorno virtual de Git. La creación y descarga requirieron permisos ampliados por restricciones del sandbox; las pruebas se ejecutaron fuera de él. La segunda subiteración amplía la validación a **20 pruebas aprobadas**, descritas en la guía de integración.

## Configurar Claude Desktop en Windows

Las rutas comprobadas son:

- Python del entorno: `C:\Users\santi\OneDrive\Documentos\PlatformIO\Projects\MQTT\mcp_server\.venv\Scripts\python.exe`
- Servidor: `C:\Users\santi\OneDrive\Documentos\PlatformIO\Projects\MQTT\mcp_server\servidor.py`

El [ejemplo JSON](claude_desktop_config.ejemplo.json) utiliza esas rutas, con las barras invertidas escapadas conforme a JSON. Al mover el repositorio a otra ubicación, recrear el entorno y actualizar ambas rutas absolutas.

1. Abrir Claude Desktop y acceder a **Settings → Developer → Edit Config**. Los nombres visibles pueden variar según idioma o versión.
2. La ubicación documentada para Windows es `%APPDATA%\Claude\claude_desktop_config.json`. En este equipo `%APPDATA%` se resolvió como `C:\Users\santi\AppData\Roaming`; durante la preparación no existían la carpeta `Claude` ni ese archivo. No se creó ni modificó esa configuración.
3. Si ya existe una configuración, conservar una copia de respaldo y añadir únicamente la entrada `equipo08` del ejemplo dentro de su objeto `mcpServers`, preservando otros servidores y ajustes. No crear dos claves `mcpServers`. Si no existe, usar el ejemplo completo.
4. Guardar JSON válido. El campo `command` debe contener solo la ruta del ejecutable, y `args` la ruta del archivo, como en el ejemplo; no introducir un comando PowerShell completo.
5. Cerrar completamente Claude Desktop y volver a abrirlo para que lance el servidor. No hace falta iniciar `servidor.py` por separado ni activar el entorno en otra terminal.

No se utiliza el comando de instalación del SDK, ya que modificaría la configuración del cliente. El usuario incorpora manualmente el ejemplo.

## Comprobación manual pendiente en Claude Desktop Free

1. Revisar los servidores o conectores MCP locales disponibles y comprobar que aparece `equipo08` sin error de inicio.
2. Abrir su lista de herramientas y comprobar que contiene `verificar_conexion` y `leer_distancia`, sin parámetros.
3. En una conversación nueva escribir: **«Ejecuta la herramienta verificar_conexion del servidor equipo08 y muestra su resultado exacto.»**
4. Autorizar la ejecución si Claude lo solicita y comprobar que aparece una llamada real a la herramienta. Una respuesta escrita por el modelo sin invocación no acredita la integración.
5. Revisar el resultado de la llamada: debe ser exactamente **`Servidor MCP del equipo 08 disponible`**.

El equipo ya confirmó el descubrimiento y la ejecución de `verificar_conexion`. La ejecución de `leer_distancia` con datos reales sigue pendiente de la prueba manual de la guía de integración. Se conserva Claude Desktop Free y no se añade ningún servicio de pago.

Si no aparece el servidor, comprobar las dos rutas, la instalación de dependencias en ese entorno, la sintaxis JSON y el reinicio completo de Claude. Revisar los registros en `%APPDATA%\Claude\logs`, especialmente `mcp.log` y el registro correspondiente a `equipo08`. Ejecutar `servidor.py` sin un cliente puede dejarlo esperando mensajes por stdin sin mostrar texto; eso por sí solo no acredita ni descarta su funcionamiento.

## Referencias

- [SDK oficial y API MCPServer](https://py.sdk.modelcontextprotocol.io/).
- [Versión mcp 2.3.0 en PyPI](https://pypi.org/project/mcp/2.3.0/).
- [Pruebas en memoria con el cliente del SDK](https://py.sdk.modelcontextprotocol.io/get-started/testing/).
- [Transporte stdio](https://py.sdk.modelcontextprotocol.io/run/).
- [Configuración de servidores locales en Claude Desktop](https://modelcontextprotocol.io/docs/develop/connect-local-servers).
