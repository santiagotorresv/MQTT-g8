# Configuración iOS · Iteración 6 · Equipo 08

La iteración 6 integra IoT MQTT Panel en un iPhone con el ESP32 mediante EMQX Cloud. El equipo confirmó las pruebas físicas del Gauge, de los tres Switches y de los dos botones descritos aquí. Esta guía registra esa configuración y esos resultados; no se realizaron nuevas pruebas al redactarla.

El contrato de referencia es [protocolo_mqtt.md](protocolo_mqtt.md), que se conserva sin cambios. Todos los clientes intercambian mensajes a través del broker.

## Conexión al broker

| Campo | Valor |
|---|---|
| Aplicación | IoT MQTT Panel para iOS |
| Broker | EMQX Cloud Serverless |
| Host | `zffa4f2f.ala.us-east-1.emqxsl.com` |
| Puerto | `8883` |
| Transporte | MQTT sobre TLS |
| Client ID del iPhone probado | `equipo08_iphone` |
| Prefijo del equipo | `sis234/equipo08/esp32-01/` |

Introducir el usuario y la contraseña autorizados del broker únicamente en la aplicación. No incluirlos en el repositorio ni en capturas o exportaciones compartidas. Mantener la validación del certificado TLS habilitada.

## Dashboard y tópicos completos

Nombre del Dashboard: **`Control ESP32 - Equipo 08`**.

Los paneles utilizan los tópicos completos indicados abajo. La opción **`Disable dashboard prefix topic` está activada** para evitar que se anteponga otra vez el prefijo del Dashboard. Por ejemplo, el Gauge usa `sis234/equipo08/esp32-01/telemetry/distance_cm`, no únicamente `telemetry/distance_cm`.

El Dashboard contiene seis paneles: un Gauge, tres Switches y dos botones.

## Gauge de distancia

| Campo | Valor |
|---|---|
| Tipo de panel | Gauge |
| Topic de suscripción | `sis234/equipo08/esp32-01/telemetry/distance_cm` |
| Unidad | cm |
| Mínimo | 0 |
| Máximo | 400 |
| Factor | 1 |
| Precisión decimal | 1 |
| QoS | 0 |
| Formato del mensaje | Número decimal, por ejemplo `24.6`; sin JSON |

El Gauge representa gráficamente la distancia recibida. No se necesita extraer un campo JSON. El rango del panel es una escala visual; no constituye una prueba de exactitud del sensor.

## Switches de LEDs

Los tres Switches publican en **`sis234/equipo08/esp32-01/cmd`**, con **QoS 1** y **Retain desactivado**.

| Switch | Mensaje al encender | Mensaje al apagar | Subscribe Topic |
|---|---|---|---|
| LED rojo | `rojo:on` | `rojo:off` | Sin configurar |
| LED amarillo | `amarillo:on` | `amarillo:off` | Sin configurar |
| LED verde | `verde:on` | `verde:off` | Sin configurar |

Enviar cada texto exactamente como aparece, sin comillas, espacios adicionales ni JSON. Son comandos explícitos e idempotentes: repetir una orden mantiene el estado solicitado.

## Botones de control conjunto

Ambos botones publican en **`sis234/equipo08/esp32-01/cmd`**, con **QoS 1** y **Retain desactivado**.

| Botón | Mensaje al pulsar | Acción |
|---|---|---|
| Encender todos | `todos:on` | Encender los tres LEDs. |
| Apagar todos | `todos:off` | Apagar los tres LEDs. |

Este Dashboard utiliza ocho de los once comandos oficiales. Los tres comandos `solo:rojo`, `solo:amarillo` y `solo:verde` permanecen en el contrato, pero no tienen un panel configurado en esta iteración.

## Reproducir la configuración en otro iPhone

1. Abrir IoT MQTT Panel y crear una conexión con el host, puerto y transporte TLS de la tabla. Introducir las credenciales autorizadas de forma local y mantener la validación del certificado habilitada.
2. Utilizar `equipo08_iphone` si se reemplaza el teléfono original y su sesión está desconectada. Si ambos teléfonos se usarán simultáneamente, asignar al segundo un Client ID distinto para evitar que se reemplacen sus conexiones.
3. Crear el Dashboard `Control ESP32 - Equipo 08` y activar `Disable dashboard prefix topic`, ya que los paneles utilizarán tópicos completos.
4. Añadir el Gauge y copiar su tópico y todos sus parámetros de la tabla de distancia.
5. Añadir los tres Switches con el tópico completo `sis234/equipo08/esp32-01/cmd`. Configurar sus mensajes de encendido/apagado, QoS 1 y Retain desactivado. Dejar `Subscribe Topic` sin configurar para reproducir la versión probada.
6. Añadir los dos botones con el mismo tópico, sus mensajes respectivos, QoS 1 y Retain desactivado.
7. Con el ESP32 conectado al broker y publicando mediciones válidas, abrir el Dashboard y repetir las pruebas de la tabla siguiente. Observar los LEDs físicos al accionar los controles.

Los resultados confirmados corresponden al iPhone utilizado por el equipo. Reproducir los ajustes en otro teléfono requiere volver a comprobar su funcionamiento.

## Pruebas funcionales realizadas

Resultados **confirmados por el equipo mediante pruebas físicas**:

| Prueba realizada | Resultado confirmado | Requisito |
|---|---|---|
| Visualizar la distancia recibida en el Gauge | La distancia se muestra gráficamente en centímetros. | RF4 |
| Encender y apagar el LED rojo desde su Switch | El LED rojo responde a `rojo:on` y `rojo:off`. | RF5 |
| Encender y apagar el LED amarillo desde su Switch | El LED amarillo responde a `amarillo:on` y `amarillo:off`. | RF5 |
| Encender y apagar el LED verde desde su Switch | El LED verde responde a `verde:on` y `verde:off`. | RF5 |
| Pulsar Encender todos | Los tres LEDs se encienden mediante `todos:on`. | RF5 |
| Pulsar Apagar todos | Los tres LEDs se apagan mediante `todos:off`. | RF5 |

**RF4 y RF5 quedan comprobados mediante estas pruebas funcionales.** El funcionamiento observado no aporta por sí solo medidas de latencia, exactitud, frecuencia de publicación, estabilidad o reconexión. No se asignan valores ni se dan por aprobadas esas pruebas cuantitativas.

La prueba específica con el iPhone utilizando **datos móviles no fue realizada** y queda pendiente. No se registra como aprobada.

## Limitación conocida de los Switches

Los Switches no tienen `Subscribe Topic`. Por ello, su posición visual puede quedar desactualizada después de comandos enviados desde otros clientes. Los botones de control conjunto tampoco aportan sincronización a esos Switches.

El ESP32 publica los estados aplicados en estos tópicos, con mensajes `on` u `off`:

- `sis234/equipo08/esp32-01/state/rojo`
- `sis234/equipo08/esp32-01/state/amarillo`
- `sis234/equipo08/esp32-01/state/verde`

Esos estados están disponibles en el broker, pero los Switches actuales no los consumen. La posición de un Switch no confirma por sí sola el estado actual del LED. Esta iteración registra la limitación y conserva la configuración que fue probada.
