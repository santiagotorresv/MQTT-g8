# Protocolo MQTT · SIS-234 · Equipo 08

Contrato de comunicación entre el ESP32, IoT MQTT Panel y el servidor MCP de Claude Desktop.

## 1. Alcance

DOIT ESP32 DEVKIT V1, HC-SR04 y tres LEDs, con firmware C++/Arduino. EMQX Cloud Serverless intermedia todos los intercambios del objeto con IoT MQTT Panel para iOS y el servidor Python MCP de Claude Desktop Free. No hay automatismos de LEDs por distancia ni comandos toggle.

La arquitectura, GPIO y módulos están documentados en [firmware](firmware.md) y el [README](../README.md).

## 2. Transporte, identidad y acceso

MQTT **3.1.1 sobre TLS**, host `zffa4f2f.ala.us-east-1.emqxsl.com`, puerto **8883**. Se verifica certificado y hostname usando la CA pública existente `certificados/emqxsl-ca.crt`; el dominio conserva SNI. El ESP32 prepara la hora mediante NTP antes de conectar. No se utiliza TLS sin validación.

| Cliente | Identificador |
|---|---|
| ESP32 | `equipo08_esp32_01` |
| Python MCP | `equipo08_mcp_python` |
| iPhone | `equipo08_iphone` |
| MQTT.fx | Usar uno distinto; ejemplo `equipo08_mqttfx_01` |

Las credenciales se completan únicamente en las copias locales ignoradas: `include/ConfiguracionWifi.h`, `include/ConfiguracionMqtt.h` y `mcp_server/configuracion_mqtt.local.json`. Las plantillas públicas no contienen valores privados. Véanse [firmware](firmware.md) e [integración Python](integracion_mcp_mqtt.md).

El ESP32 publica telemetría, estados y disponibilidad; recibe comandos. Los otros clientes publican comandos y consumen la información correspondiente a sus paneles o herramientas. La autorización efectiva y las cuotas se administran en EMQX. Mantener el uso dentro de la cuota gratuita y el límite de gasto en 0.

## 3. Prefijo y representación

Prefijo definitivo: **`sis234/equipo08/esp32-01/`**. El tópico completo se forma concatenando el prefijo y el sufijo sin otra barra.

Los textos distinguen mayúsculas/minúsculas. Los payloads son UTF-8, sin comillas envolventes, espacios añadidos ni salto de línea. La distancia es un número decimal simple, no JSON; el firmware la presenta con punto y una cifra decimal. Esa resolución de presentación no acredita exactitud.

## 4. Tópicos, QoS y retención

| Sufijo | Publica | Se suscribe | Payload | QoS de publicación | Retained |
|---|---|---|---|---|---|
| `telemetry/distance_cm` | ESP32 | iOS, Python | Decimal en cm, por ejemplo `24.6` | 0 | No |
| `telemetry/sensor_status` | ESP32 | Python | `valid` o `invalid` | 0 | No |
| `cmd` | iOS, Python | ESP32 | Uno de los once comandos de la sección 5 | 1 | No |
| `state/rojo` | ESP32 | Python | `on` u `off` | 1 | Sí |
| `state/amarillo` | ESP32 | Python | `on` u `off` | 1 | Sí |
| `state/verde` | ESP32 | Python | `on` u `off` | 1 | Sí |
| `availability` | ESP32; broker para Last Will | Python | `online` u `offline` | 1 | Sí |

La tabla describe los consumidores actuales. El iPhone se suscribe a distancia; sus Switches no están suscritos a estados y no hay paneles documentados para `sensor_status` o `availability`. Python solicita seis suscripciones: distancia y sensor_status a QoS 0; disponibilidad y los tres estados a QoS 1. El ESP32 solicita QoS 1 para `cmd`.

**No existe un tópico `state/todos`.** Las órdenes de grupo se reflejan en los tres estados individuales. Retained conserva el último valor de cada tópico, no un historial ni un comprobante de ejecución.

## 5. Once comandos y efectos

Todos se publican en `sis234/equipo08/esp32-01/cmd`, QoS 1 y **Retain desactivado**. «Conservar» mantiene el estado previo del LED.

| Comando exacto | Rojo | Amarillo | Verde |
|---|---|---|---|
| `rojo:on` | Encender | Conservar | Conservar |
| `rojo:off` | Apagar | Conservar | Conservar |
| `amarillo:on` | Conservar | Encender | Conservar |
| `amarillo:off` | Conservar | Apagar | Conservar |
| `verde:on` | Conservar | Conservar | Encender |
| `verde:off` | Conservar | Conservar | Apagar |
| `todos:on` | Encender | Encender | Encender |
| `todos:off` | Apagar | Apagar | Apagar |
| `solo:rojo` | Encender | Apagar | Apagar |
| `solo:amarillo` | Apagar | Encender | Apagar |
| `solo:verde` | Apagar | Apagar | Encender |

Los comandos son explícitos e idempotentes: repetir la misma orden deja el mismo estado solicitado. Los mensajes desconocidos, vacíos, demasiado largos o con caracteres no permitidos se rechazan. El callback del firmware admite como máximo 31 bytes ASCII imprimibles y delega la validación exacta a `ControlLeds`.

Los GPIO se escriben consecutivamente. Un comando válido marca pendiente publicar los estados; si se reciben varias órdenes antes de publicarlos, pueden observarse los últimos estados aplicados. No hay un ACK de aplicación por orden ni transacción atómica de las tres publicaciones. Un estado describe el GPIO informado por el firmware, sin realimentación que compruebe iluminación.

## 6. Medición, invalidez y frescura

El firmware programa intentos cada **500 ms**. El HC-SR04 usa TRIG=GPIO5, ECHO=GPIO18, pulso HIGH de 10 µs y timeout explícito de 30 000 µs. Calcula duración × 0,034 / 2, acepta nominalmente 2–400 cm y representa internamente una medición inválida como `valida=false` y `NaN`. **NaN nunca se publica.**

Una lectura válida publica `valid` y una distancia; una inválida publica `invalid` y omite la distancia de ese ciclo. No se publica cero para representar errores ni se repite la lectura anterior. El ESP32 no acumula un historial de mediciones para enviarlo después de reconectar.

Distancia y sensor_status son mensajes separados con QoS 0: pueden perderse independientemente y no identifican una misma muestra de forma inequívoca. Una suscripción QoS 1 no eleva el QoS 0 del publicador. El intervalo de programación no garantiza una frecuencia efectiva de entrega.

Python registra la recepción de ambos mensajes mediante reloj monotónico. Su umbral inicial real es **5 s**, configurable: se aceptan edades de hasta 5 s y se rechazan las mayores. Al reconectar espera datos nuevos; `invalid`, falta de información reciente o `offline` impiden presentar un número como lectura válida reciente.

El Gauge iOS muestra la distancia; su configuración no define un indicador de invalidez o caducidad equivalente al de Python. Véase la [guía iOS](configuracion_ios.md).

## 7. QoS 1, PUBACK, reconexión y disponibilidad

QoS 1 utiliza confirmación y retransmisión para ofrecer entrega al menos una vez durante el intercambio correspondiente; permite duplicados. No garantiza ejecución del dispositivo, plazo máximo ni entrega a un cliente desconectado con sesión limpia.

Hay tres niveles distintos:

1. `publish()` puede aceptar o encolar localmente una orden: todavía no acredita recepción del broker.
2. PUBACK de la publicación Python → broker acredita ese salto, no su entrega al ESP32.
3. Estados posteriores del ESP32 aportan evidencia de valores informados, pero no prueban iluminación ni causalidad exacta de una orden.

**Un timeout no cancela una publicación ni garantiza que no se reenviará.** Paho puede mantener publicaciones QoS 1 pendientes y retransmitirlas al reconectar, incluso con sesión limpia. La herramienta no programa reintentos propios y rechaza nuevas órdenes cuando detecta desconexión, pero existe una ventana entre detectar el fallo y publicar. El resultado puede ser incierto. No se manipulan colas internas de Paho.

La idempotencia limita el efecto de duplicados de la misma orden, pero una retransmisión antigua puede contradecir otra posterior de un cliente diferente. No hay identificador de orden ni tópico ACK que permita correlacionar inequívocamente estados y solicitudes.

El ESP32 usa sesión limpia y configura Last Will `offline`, QoS 1 y retained, en `availability`. Después de suscribirse y publicar estados anuncia `online` retained. El cierre del transporte del firmware se realiza sin paquete MQTT DISCONNECT, permitiendo que el broker emita el Will; no se promete una publicación explícita previa de `offline`. El keepalive es de 30 s y la detección no es instantánea.

`online` es disponibilidad anunciada y puede quedar temporalmente desactualizada. Perder la red no modifica automáticamente los LEDs; al reconectar se publican los estados locales existentes. Al reiniciar el ESP32, la inicialización deja los tres LEDs apagados.

Los publicadores no deben retener órdenes en `cmd`. El callback MQTT usado por el firmware no expone la bandera retained; una orden antigua retenida podría ejecutarse al reconectar. Debe comprobarse su ausencia en el broker.

## 8. Herramientas MCP

Python 3.12.6, SDK oficial MCP 2.3.0, paho-mqtt 2.1.0 y transporte local `stdio`. Se mantiene una conexión MQTT y datos en memoria protegidos entre hilos; los logs se dirigen a stderr.

| Herramienta actual | Parámetros públicos | Resultado |
|---|---|---|
| `verificar_conexion` | Ninguno | `Servidor MCP del equipo 08 disponible`; disponibilidad del servidor local. |
| `leer_distancia` | Ninguno | Última distancia válida reciente o condición explícita de ausencia, invalidez, antigüedad o desconexión. |
| `controlar_led` | color: rojo/amarillo/verde/todos; accion: encender/apagar; solo: booleano opcional false | Publica uno de los once comandos y distingue PUBACK de estados coincidentes. |
| `consultar_leds` | Ninguno | Estados conocidos/desconocidos, edad, conexión y referencia reciente o histórica. |

Se rechazan argumentos MCP no declarados antes de publicar. `solo=true` únicamente permite encender un LED individual. La espera de evidencia de `controlar_led` tiene un plazo inicial de 3 s; solo admite estados nuevos no retained de la misma sesión. Una coincidencia no es un ACK causal de aplicación.

La [guía de LEDs](control_leds_mcp.md) contiene las once traducciones y los estados devueltos por las herramientas. Para instalar el entorno y configurar Claude, consultar el [servidor Python](../mcp_server/README.md).

Referencias: [MQTT 3.1.1 · OASIS](https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html), [Paho y limitaciones](https://eclipse.dev/paho/files/paho.mqtt.python/html/index.html#known-limitations), [guía EMQX Serverless](https://docs.emqx.com/en/cloud/latest/deployments/port_guide_serverless.html).
