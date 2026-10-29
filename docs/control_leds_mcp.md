# Control de LEDs mediante MCP · Equipo 08

Guía de parámetros, comandos y respuestas de `controlar_led` y `consultar_leds`. Preparar el entorno con la [guía MCP](../mcp_server/README.md) y las credenciales con la [guía MQTT Python](integracion_mcp_mqtt.md).

## Arquitectura y conexión compartida

Se conservan Python 3.12.6, MCP 2.3.0, paho-mqtt 2.1.0, TLS y transporte `stdio`. `StrictBool` pertenece a Pydantic, ya requerido por el SDK MCP, y evita aceptar cadenas o números como booleanos.

El ciclo de vida del servidor sigue creando una sola instancia de `ConexionMqtt`. Las herramientas que acceden a MQTT reutilizan esa instancia; `verificar_conexion` comprueba únicamente el servidor MCP local. El hilo de Paho recibe telemetría, disponibilidad y estados; no se crea una conexión por orden o consulta. Los registros siguen en stderr.

La conexión existente utiliza estas tres suscripciones de LEDs a QoS 1, además de distancia, sensor_status y disponibilidad:

- `sis234/equipo08/esp32-01/state/rojo`
- `sis234/equipo08/esp32-01/state/amarillo`
- `sis234/equipo08/esp32-01/state/verde`

Cada reconexión solicita las seis suscripciones y comprueba SUBACK. Se comprueban por separado las suscripciones originales y las de LEDs: un rechazo de las últimas bloquea la actuación, pero conserva la consulta de distancia si sus tres suscripciones siguen aceptadas. Las órdenes se publican exclusivamente en `sis234/equipo08/esp32-01/cmd`, sin espacios, con **QoS 1 y Retain desactivado**. La herramienta `controlar_led` traduce los parámetros al [contrato MQTT](protocolo_mqtt.md).

## controlar_led

| Parámetro | Valores permitidos |
|---|---|
| `color` | `rojo`, `amarillo`, `verde`, `todos` |
| `accion` | `encender`, `apagar` |
| `solo` | Booleano, opcional, valor predeterminado `false` |

Se rechazan valores desconocidos, diferencias de mayúsculas, espacios adicionales y tipos incorrectos. `solo=true` únicamente admite `encender` sobre un color individual. Las combinaciones inválidas no publican mensajes. Se rechazan argumentos no declarados, como `exclusivo`, antes de publicar: `ServidorEquipo` valida la petición original y anuncia `additionalProperties=false`. No se aceptan `retain` ni `contexto` como parámetros públicos.

| color | accion | solo | Mensaje MQTT |
|---|---|---|---|
| rojo | encender | false | `rojo:on` |
| rojo | apagar | false | `rojo:off` |
| amarillo | encender | false | `amarillo:on` |
| amarillo | apagar | false | `amarillo:off` |
| verde | encender | false | `verde:on` |
| verde | apagar | false | `verde:off` |
| todos | encender | false | `todos:on` |
| todos | apagar | false | `todos:off` |
| rojo | encender | true | `solo:rojo` |
| amarillo | encender | true | `solo:amarillo` |
| verde | encender | true | `solo:verde` |

No se publica si MQTT o las suscripciones no están disponibles, ni si el ESP32 no tiene disponibilidad `online` anunciada. Una segunda orden concurrente recibe `ocupado` y no se publica mientras la primera está en curso. Esto limita la confusión entre órdenes del propio servidor; otros clientes siguen siendo independientes.

## Envío y evidencia de estado

El plazo inicial es **3 segundos en total**, definido en `tiempo_limite_comando`, dentro de `conexion_mqtt.py`. Incluye la espera del PUBACK y de estados coincidentes. `controlar_led` ejecuta esa espera con `asyncio.to_thread`, para que el bucle asíncrono de MCP siga disponible. Una `Condition` comparte el bloqueo de los datos MQTT y permite que los callbacks despierten la espera.

La secuencia es:

1. Validar parámetros y disponibilidad, capturar el número de recepción de estados y la sesión MQTT, y publicar una sola vez.
2. Esperar la finalización QoS 1 mediante `wait_for_publish()` y comprobar `is_published()`. Un retorno exitoso de `publish()` por sí solo no confirma recepción del broker.
3. Buscar estados recibidos después de comenzar la publicación, dentro del plazo, sin bandera retained y sin cambio de sesión o disponibilidad. Para una orden individual basta el color afectado; para `todos` y `solo` se exigen los tres valores esperados.
4. Informar por separado la recepción del broker y la coincidencia de estados. Ante desconexión/reconexión no se reutilizan estados de otra sesión para verificar la orden.

| Resultado `estado` | Interpretación |
|---|---|
| `rechazado` | Parámetros o combinación inválidos; no se publica. Los tipos o enumeraciones inválidos también pueden producir un error MCP de validación. |
| `no_enviado` | MQTT/suscripciones no disponibles o ESP32 sin `online` anunciado; no se publica. |
| `ocupado` | Otra orden está en curso; no se publica esta orden. |
| `envio_sin_confirmar` | No se pudo confirmar el envío o no llegó PUBACK dentro del plazo. El resultado es incierto. |
| `enviado_sin_verificar` | El broker confirmó recepción, pero faltaron estados nuevos coincidentes dentro del plazo. |
| `estado_informado` | El broker confirmó recepción y se observaron estados nuevos coincidentes. No demuestra causalidad ni iluminación física. |

Cuando se completa el intento se incluyen `comando`, `confirmacion_broker`, `estados_coincidentes`, `estados_esperados` y una explicación. La herramienta no programa reintentos de la orden. Un timeout no cancela una publicación ya iniciada ni demuestra que no se haya aplicado.

## consultar_leds

No recibe parámetros ni publica mensajes. Devuelve `conexion_mqtt`, `suscripcion_leds`, `disponibilidad_esp32` y un objeto `leds` con rojo, amarillo y verde.

Cada color sin informe tiene `estado=desconocido` y `referencia=sin_datos`. Un estado recibido contiene `on` u `off`, edad desde su recepción y bandera `retenido`. Se etiqueta como `informe_reciente` solo si es de la sesión actual, no retenido, tiene hasta 5 segundos de edad y la conexión/disponibilidad están activas; el resto es `ultimo_estado_conocido`.

Los estados se publican al aplicar comandos y al reconectar, no son un pulso periódico de actividad. Por eso una edad superior a 5 segundos no significa necesariamente que el LED haya cambiado o que el ESP32 esté desconectado. Los estados conocidos se conservan como históricos al perder la conexión. Un mensaje de estado mal formado pasa ese color a desconocido.

## Lenguaje natural y ambigüedad

Claude interpreta la frase y elige la herramienta y los parámetros; Python valida y traduce únicamente la petición estructurada. No hay un catálogo de variantes lingüísticas programadas.

| Ejemplo de instrucción | Herramienta o interpretación |
|---|---|
| «¿A cuánto está el objeto?» | `leer_distancia()` |
| «Prende el rojo» | `controlar_led(rojo, encender, false)` |
| «Apaga las luces» | `controlar_led(todos, apagar, false)` |
| «Enciende todas» | `controlar_led(todos, encender, false)` |
| «Deja solamente el verde encendido» | `controlar_led(verde, encender, true)` |
| «Apaga el amarillo» | `controlar_led(amarillo, apagar, false)` |
| «Qué luces están prendidas» | `consultar_leds()` |
| «Pon todos los focos en verde» | Pedir aclaración antes de actuar: hay tres LEDs físicos de color fijo, no focos RGB. |

Las descripciones MCP indican que debe pedirse aclaración ante ambigüedad. El servidor valida parámetros, pero no puede comprobar por sí mismo si la interpretación del LLM representa la intención de una frase. Los casos ambiguos requieren aclaración antes de ejecutar una orden.

## Uso desde Claude

1. Configurar el servidor `equipo08` y reiniciar completamente Claude; no iniciar otro proceso con el mismo Client ID.
2. Abrir las herramientas del servidor y ejecutar `verificar_conexion`. Consultar `leer_distancia` o `consultar_leds` para conocer los datos disponibles.
3. Solicitar una acción de la tabla de ejemplos y revisar sus parámetros antes de autorizarla.
4. Leer el resultado MQTT según la tabla de estados. La observación de los LEDs físicos permite comprobar su iluminación; los estados de la herramienta corresponden a los valores informados por el ESP32.

## Límites y riesgos

- El contrato no tiene ACK de aplicación ni identificador de orden. Estados nuevos coincidentes pueden proceder de MQTT.fx, del iPhone u otra orden pendiente; no se garantiza causalidad. Las tres publicaciones de estado tampoco son una transacción atómica.
- PUBACK confirma el salto Python → broker. No confirma entrega al ESP32 ni encendido físico. Un informe GPIO no detecta un LED desconectado o averiado.
- QoS 1 permite duplicados. Paho puede retransmitir una publicación pendiente al reconectar, aunque la herramienta no programe reintentos y rechace órdenes cuando detecta desconexión. Los comandos son idempotentes, pero un timeout deja incertidumbre; evitar repetir órdenes a ciegas o mezclar clientes al operar.
- `online` retenido puede quedar desactualizado hasta que el broker detecte la pérdida y publique el Last Will. La disponibilidad anunciada no garantiza conexión instantánea.
- Una pérdida de estados, autorización insuficiente en EMQX o un cambio concurrente puede producir `enviado_sin_verificar`. Se deben comprobar permisos de publicación en `cmd` y suscripción en los tres `state/*` en la configuración del broker.

Referencias: [publicación y espera de PUBACK en Paho](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html), [contrato conservado](protocolo_mqtt.md).
