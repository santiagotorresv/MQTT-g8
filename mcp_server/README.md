# Servidor MCP local · Equipo 08

Servidor Python que comunica Claude Desktop Free con el ESP32 mediante MQTT. Utiliza transporte local `stdio` y una conexión compartida a EMQX con TLS verificado.

## Organización y versiones

- Python comprobado: **3.12.6**, de 64 bits; para este proyecto se requiere 3.11 o superior.
- SDK oficial **mcp==2.3.0**, API `MCPServer`, y **paho-mqtt==2.1.0**, callbacks VERSION2, fijados en `requirements.txt`.
- `servidor.py`: cuatro herramientas, ciclo de vida y clase `ServidorEquipo`, una subclase pequeña de `MCPServer` para rechazar argumentos desconocidos antes de que el SDK los descarte.
- `conexion_mqtt.py`: clase `ConexionMqtt`, conexión compartida, telemetría, estados, publicación y evidencia MQTT.
- `test_conexion_mqtt.py`, `test_control_leds.py` y `test_servidor.py`: suite automatizada con simulaciones aisladas del broker.
- `claude_desktop_config.ejemplo.json`: ejemplo Windows que debe adaptarse a las rutas absolutas de cada integrante.
- `.venv/`: entorno independiente excluido de Git.

No se usa FastMCP ni se abre un servidor HTTP. Los paquetes transitivos del SDK, aunque soporten otros transportes, no son servicios añadidos por el proyecto. `StrictBool` pertenece a Pydantic, dependencia del SDK; no requiere otra instalación.

El ciclo de vida crea una sola conexión MQTT y la cierra al finalizar. Los callbacks de Paho y las herramientas comparten datos protegidos con `Lock`; `Condition` permite esperar estados. La espera de actuación usa `asyncio.to_thread`. Los logs van a stderr y stdout queda reservado al protocolo.

## Herramientas públicas

| Herramienta | Parámetros | Resultado |
|---|---|---|
| `verificar_conexion` | Ninguno | Texto exacto: `Servidor MCP del equipo 08 disponible`. Comprueba el servidor local, no el broker ni el ESP32. |
| `leer_distancia` | Ninguno | Última lectura MQTT válida reciente, o ausencia, invalidez, antigüedad o desconexión. |
| `controlar_led` | `color`: rojo/amarillo/verde/todos; `accion`: encender/apagar; `solo`: booleano opcional false | Orden QoS 1 sin Retain y resultado diferenciado de envío/estados. |
| `consultar_leds` | Ninguno | Estados informados, conocidos/desconocidos, con edad y referencia reciente/histórica. |

`contexto` es inyectado por el SDK; no es un parámetro público. `controlar_led` anuncia `additionalProperties=false` y rechaza claves adicionales antes de publicar. Se conservan sus parámetros válidos y el rechazo de combinaciones incorrectas de `solo`.

Claude interpreta la intención, no un catálogo de frases codificado en Python. Ejemplos: «¿A cuánto está el objeto?», «Prende el rojo», «Apaga todas las luces», «Deja solamente el verde prendido» y «¿Qué luces están encendidas?». Ante ambigüedad debe pedir aclaración; sus interpretaciones no son infalibles.

## Entorno Python

Desde la raíz del repositorio, comprobar la versión y crear el entorno solo si aún no existe:

```powershell
python --version
if (-not (Test-Path mcp_server/.venv)) {
    python -m venv mcp_server/.venv
}
& 'mcp_server/.venv/Scripts/python.exe' -m pip install -r mcp_server/requirements.txt
& 'mcp_server/.venv/Scripts/python.exe' -m pip check
```

No es necesario activarlo: se invoca su Python directamente. No reutilizar el entorno de PlatformIO ni copiar un entorno virtual de otra computadora. Las dependencias directas están fijadas; las transitivas no están congeladas.

Completar las credenciales siguiendo la [guía MQTT Python](../docs/integracion_mcp_mqtt.md). El archivo local ignorado es `configuracion_mqtt.local.json`, junto a `servidor.py`. No se incorporan credenciales al JSON público de Claude.

## Configurar Claude Desktop Free en Windows

1. Obtener las rutas absolutas reales desde la raíz del clon:
   ```powershell
   (Resolve-Path mcp_server/.venv/Scripts/python.exe).Path
   (Resolve-Path mcp_server/servidor.py).Path
   ```
2. Abrir **Settings → Developer → Edit Config** en Claude Desktop; la ubicación habitual de Windows es `%APPDATA%/Claude/claude_desktop_config.json`. Los nombres visibles pueden variar por idioma/versión.
3. Usar el [ejemplo JSON](claude_desktop_config.ejemplo.json), sustituyendo `command` por la primera ruta y el argumento de `args` por la segunda. El ejemplo conserva rutas absolutas de la computadora original; no son portables ni deben copiarse sin verificar. Escapar barras invertidas conforme a JSON.
4. Si ya hay configuración, conservar una copia y añadir la entrada `equipo08` dentro del objeto `mcpServers` existente. Preservar otros servidores y ajustes; no duplicar `mcpServers` ni sobrescribir todo el archivo.
5. Cerrar completamente Claude y volver a abrirlo. No iniciar otra instancia del servidor en paralelo con el mismo Client ID.

Estas instrucciones no modifican automáticamente la configuración de Claude. No se utiliza el comando de instalación del SDK para escribirla.

## Uso y diagnóstico

1. Comprobar que el servidor expone las cuatro herramientas y ejecutar `verificar_conexion`.
2. Ejecutar `leer_distancia` con el ESP32 publicando; revisar estado, antigüedad y origen.
3. Probar control y consulta siguiendo la [guía de LEDs](../docs/control_leds_mcp.md).
4. Revisar la llamada real a la herramienta, no solo una respuesta redactada por Claude. Observar físicamente los LEDs por separado de PUBACK y estados.
5. Si hay errores, revisar rutas, entorno, configuración local y registros en `%APPDATA%/Claude/logs`; no compartir secretos.

Una ejecución de `servidor.py` sin cliente puede esperar mensajes por stdin sin imprimir texto. Eso por sí solo no acredita funcionamiento. Si faltan credenciales, el servidor MCP sigue disponible y las herramientas MQTT informan la condición.

## Límites de las respuestas

La medición Python caduca inicialmente a los 5 s; la actuación espera evidencia MQTT durante 3 s. Un timeout no cancela una publicación: Paho puede retransmitir pendientes QoS 1. Estados coincidentes no demuestran causalidad ni iluminación física. La explicación completa está en [protocolo MQTT](../docs/protocolo_mqtt.md).

Referencias: [SDK oficial MCP](https://py.sdk.modelcontextprotocol.io/), [ciclo de vida](https://py.sdk.modelcontextprotocol.io/handlers/lifespan/), [servidores locales en Claude](https://modelcontextprotocol.io/docs/develop/connect-local-servers).
