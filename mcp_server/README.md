# Servidor MCP local · Equipo 08

Esta subiteración comprueba el servidor Python y prepara su descubrimiento desde Claude Desktop. No se conecta al broker ni al ESP32. RF6 completo sigue pendiente: todavía no consulta el sensor ni controla LEDs.

## Entorno y archivos

- Python comprobado: **3.12.6**, de 64 bits. El proyecto requiere Python 3.11 o superior.
- SDK oficial: **mcp==2.3.0**, fijado en `requirements.txt`; se utiliza `MCPServer`, sin FastMCP.
- Entorno independiente: `mcp_server/.venv/`, excluido de Git por las reglas existentes.
- `servidor.py`: instancia `MCPServer`, registra una herramienta y ejecuta el transporte local `stdio`.
- `test_servidor.py`: pruebas con `unittest` y el cliente del SDK, sin bibliotecas de pruebas adicionales.
- `claude_desktop_config.ejemplo.json`: configuración de ejemplo con las rutas absolutas comprobadas en este equipo.

La única dependencia directa es `mcp`. Pip instala también las dependencias requeridas por el propio SDK; aunque algunas soportan HTTP, este servidor utiliza exclusivamente `stdio` y no abre un servidor HTTP. No se instalan los extras de CLI ni paho-mqtt.

Se utiliza directamente una instancia de la clase `MCPServer` del SDK y una función registrada; no se añade otra clase propia para devolver una constante.

## Herramienta

| Nombre | Parámetros | Resultado exacto |
|---|---|---|
| `verificar_conexion` | Ninguno | `Servidor MCP del equipo 08 disponible` |

El nombre se refiere a la disponibilidad del servidor local, no a WiFi, EMQX ni al estado físico del ESP32. La función devuelve el texto; no lo imprime. No se añaden mensajes de depuración en stdout, reservado para el protocolo. Si se necesitan registros posteriores, deberán dirigirse a stderr.

El bloque `if __name__ == "__main__"` inicia el servidor únicamente al ejecutar el archivo. Importarlo durante las pruebas no inicia un proceso de servicio.

## Preparar o reproducir el entorno

Desde la raíz del repositorio en PowerShell, con Python 3.11 o superior:

```powershell
python --version
python -m venv mcp_server/.venv
& '.\mcp_server\.venv\Scripts\python.exe' -m pip install -r mcp_server/requirements.txt
& '.\mcp_server\.venv\Scripts\python.exe' -m pip check
& '.\mcp_server\.venv\Scripts\python.exe' -m unittest discover -s mcp_server -p test_servidor.py -v
```

No es necesario activar el entorno: se invoca su ejecutable directamente. No reutilizar el entorno de PlatformIO. En esta máquina `python` corresponde a Python 3.12.6; el lanzador `py` no detectó instalaciones, por lo que no se utiliza en estas instrucciones.

Las pruebas comprueban que el listado contiene únicamente `verificar_conexion`, sin parámetros, que la llamada no informa error y que devuelve un solo bloque de texto con el resultado exacto. Se realiza una conexión en memoria mediante `Client(servidor)` y otra lanzando `servidor.py` como subproceso mediante `Client(StdioServerParameters(...))`. Cada prueba tiene un timeout de 20 segundos.

Validación realizada el **28 de octubre de 2026**: importación de `mcp` y `MCPServer` correcta, `pip check` sin conflictos y **2 pruebas aprobadas**, en 2,795 s, con salida 0. Se comprobaron también ambas rutas del ejemplo JSON y la exclusión del entorno virtual de Git. La creación inicial del entorno falló en `ensurepip` bajo el sandbox y la descarga restringida falló por DNS; ambas operaciones se completaron con permisos ampliados. La ejecución de pruebas dentro del sandbox no terminó y se interrumpió; el resultado aprobado corresponde a su ejecución fuera de ese entorno restringido.

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
2. Abrir su lista de herramientas y comprobar que contiene únicamente `verificar_conexion`, sin parámetros.
3. En una conversación nueva escribir: **«Ejecuta la herramienta verificar_conexion del servidor equipo08 y muestra su resultado exacto.»**
4. Autorizar la ejecución si Claude lo solicita y comprobar que aparece una llamada real a la herramienta. Una respuesta escrita por el modelo sin invocación no acredita la integración.
5. Revisar el resultado de la llamada: debe ser exactamente **`Servidor MCP del equipo 08 disponible`**.

El descubrimiento y la ejecución desde Claude Desktop Free **no se dan por comprobados** hasta que el equipo realice esta prueba. Dependen de la versión instalada, las opciones disponibles en la cuenta y sus límites de uso. No se necesita un servicio de pago para el servidor local desarrollado.

Si no aparece el servidor, comprobar las dos rutas, la instalación de dependencias en ese entorno, la sintaxis JSON y el reinicio completo de Claude. Revisar los registros en `%APPDATA%\Claude\logs`, especialmente `mcp.log` y el registro correspondiente a `equipo08`. Ejecutar `servidor.py` sin un cliente puede dejarlo esperando mensajes por stdin sin mostrar texto; eso por sí solo no acredita ni descarta su funcionamiento.

## Referencias

- [SDK oficial y API MCPServer](https://py.sdk.modelcontextprotocol.io/).
- [Versión mcp 2.3.0 en PyPI](https://pypi.org/project/mcp/2.3.0/).
- [Pruebas en memoria con el cliente del SDK](https://py.sdk.modelcontextprotocol.io/get-started/testing/).
- [Transporte stdio](https://py.sdk.modelcontextprotocol.io/run/).
- [Configuración de servidores locales en Claude Desktop](https://modelcontextprotocol.io/docs/develop/connect-local-servers).
