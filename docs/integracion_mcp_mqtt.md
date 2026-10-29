# MQTT Python y consulta de distancia · Equipo 08

Configuración de la conexión compartida con EMQX y uso de `leer_distancia`. La instalación del servidor está en la [guía MCP](../mcp_server/README.md) y la actuación en la [guía de LEDs](control_leds_mcp.md).

## Entorno y responsabilidades

Python 3.12.6, MCP 2.3.0, paho-mqtt 2.1.0 con CallbackAPIVersion.VERSION2 y transporte local MCP stdio.

`ConexionMqtt.iniciar()` prepara TLS/autenticación y utiliza `connect_async()`/`loop_start()`. El hilo de Paho recibe mensajes y reconecta con esperas entre 1 y 30 s. El ciclo de vida del servidor reutiliza una sola instancia y la cierra al terminar; no hay conexiones nuevas por consulta.

Un `Lock` protege medición, validez, instantes y estados. Las consultas devuelven una instantánea en memoria sin esperar una lectura nueva. La sincronización y los contadores de sesión se conservan. Los registros van a stderr; stdout pertenece a MCP.

## Configuración privada

El archivo es **`mcp_server/configuracion_mqtt.local.json`**, excluido de Git. El ejemplo público actual se llama **`configuracion_mqtt.ejemplo copy.json`** y contiene usuario/contraseña vacíos.

Desde la raíz, copiarlo solo si aún no existe la configuración local:

```powershell
if (-not (Test-Path mcp_server/configuracion_mqtt.local.json)) {
    Copy-Item 'mcp_server/configuracion_mqtt.ejemplo copy.json' mcp_server/configuracion_mqtt.local.json
}
git check-ignore -v mcp_server/configuracion_mqtt.local.json
```

Completar manualmente `usuario` y `contrasena` únicamente en esa copia. Mantener `antiguedad_maxima_segundos` en **5** inicialmente; admite un número finito positivo. No publicar valores reales ni copiar una configuración privada a una plantilla pública.

La ruta predeterminada se obtiene desde `servidor.py`, independientemente del directorio de trabajo de Claude. `EQUIPO08_CONFIG_MQTT` permite indicar una configuración alternativa; normalmente no hace falta.

Después de modificar la copia local, reiniciar completamente Claude para recrear el servidor. Sin archivo, con JSON incorrecto o con credenciales vacías, MCP permanece disponible e informa MQTT no configurado; no simula mediciones.

## Conexión y tópicos

| Parámetro | Valor público |
|---|---|
| Broker | `zffa4f2f.ala.us-east-1.emqxsl.com` |
| Puerto | 8883 |
| Protocolo | MQTT 3.1.1 sobre TLS |
| Client ID | `equipo08_mcp_python` |
| CA | `certificados/emqxsl-ca.crt` |

La ruta de la CA se resuelve desde el módulo hasta la raíz del proyecto. El contexto TLS verifica certificado y hostname y requiere TLS 1.2 o posterior. El archivo existente se conserva; no se utiliza TLS inseguro.

| Tópico completo de suscripción | QoS |
|---|---|
| `sis234/equipo08/esp32-01/telemetry/distance_cm` | 0 |
| `sis234/equipo08/esp32-01/telemetry/sensor_status` | 0 |
| `sis234/equipo08/esp32-01/availability` | 1 |
| `sis234/equipo08/esp32-01/state/rojo` | 1 |
| `sis234/equipo08/esp32-01/state/amarillo` | 1 |
| `sis234/equipo08/esp32-01/state/verde` | 1 |

Al reconectar se solicitan de nuevo las seis suscripciones y se comprueba SUBACK. Si el broker rechaza las de LEDs, se bloquea la actuación, pero se conserva la lectura de distancia si sus tres suscripciones originales están aceptadas.

## leer_distancia

No recibe parámetros. Su resultado JSON incluye `estado`, `mensaje` y `origen`. Solo con lectura válida y reciente añade `distancia_cm`, `unidad=cm` y `antiguedad_segundos`. La distancia se obtiene exclusivamente de mensajes MQTT aceptados, no de valores inventados o simulados en producción.

| Estado | Significado |
|---|---|
| `valida` | Distancia y estado `valid` recientes, con conexión/suscripciones activas y disponibilidad anunciada `online`. |
| `invalida` | Se recibió `invalid` recientemente; no se devuelve la distancia anterior. |
| `sin_datos` | Falta distancia, estado del sensor o disponibilidad conocida. |
| `desactualizada` | La distancia o el estado del sensor supera la antigüedad configurada. |
| `esp32_desconectado` | Se recibió `availability=offline`. |
| `mqtt_no_disponible` | Configuración, conexión o suscripciones no disponibles; el mensaje concreta la condición. |

La edad se calcula desde recepción con `time.monotonic()`. Se aceptan hasta 5 s y se rechazan edades mayores. Tanto distancia como estado deben ser recientes. Un `valid` nuevo sin distancia nueva después de `invalid` no habilita una lectura anterior.

Se rechazan mensajes mal formados, demasiado largos, UTF-8 inválido, NaN, infinito, distancias fuera de 2–400 cm, estados desconocidos y telemetría retained. Al desconectar/reconectar se descartan medición y disponibilidad anteriores. Los estados de LEDs pueden conservarse como históricos; su consulta no constituye confirmación física.

## Uso desde Claude

1. Mantener el ESP32 conectado al broker, publicando mediciones, y una sola instancia Python con `equipo08_mcp_python`.
2. Tras editar la configuración privada, cerrar completamente Claude Desktop y abrirlo de nuevo.
3. Ejecutar `verificar_conexion` y solicitar **«¿A cuánto está el objeto? Usa leer_distancia del servidor equipo08.»**
4. Revisar la llamada a la herramienta y su respuesta: estado, antigüedad y origen. Si no devuelve una distancia, interpretar el estado con la tabla anterior.

## Límites

Distancia y estado llegan por tópicos separados con QoS 0, sin identificador de muestra; la edad es de recepción, no del instante físico de medición. `online` retenido puede estar desactualizado hasta la detección del broker. La pérdida de MQTT en Python impide conocer en ese momento si el ESP32 sigue conectado por su lado.

DNS/TCP/TLS y el cierre del hilo dependen del sistema y de la red; no se declara un tiempo exacto de recuperación. Las garantías de publicación, PUBACK y retransmisión se explican en [protocolo MQTT](protocolo_mqtt.md).

Referencias: [Paho](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html), [ciclo de vida MCP](https://py.sdk.modelcontextprotocol.io/handlers/lifespan/).
