# Contrato MQTT de la práctica SIS-234

Fecha: 24 de octubre de 2026. Versión documental: 4.

Este documento formaliza el contrato acordado a partir de la [consigna oficial](Práctica_MQTT.md). Describe el comportamiento de la futura integración MQTT; no acredita que la aplicación móvil, EMQX o MCP ya funcionen. La implementación actual se limita al control local de los tres LEDs mediante Serial. El equipo confirmó mediante pruebas físicas el control de los tres LEDs y `todos:off`; la prueba física del nuevo `todos:on` permanece pendiente. La verificación de la plantilla original se conserva en la sección 9.

## 1. Alcance y decisiones aprobadas

- Objeto inteligente: DOIT ESP32 DEVKIT V1, C++ y framework Arduino con PlatformIO; sensor ultrasónico y tres LEDs: rojo, amarillo y verde.
- Broker: EMQX Cloud Serverless, MQTT sobre TLS con verificación del certificado y del nombre del servidor.
- Aplicación móvil: IoT MQTT Panel para iOS.
- IA: Claude Desktop Free con servidor MCP local en Python, SDK oficial MCP v2 y paho-mqtt. Transporte local propuesto: stdio.
- Frecuencia objetivo: dos mediciones por segundo, con intervalo nominal de 500 ms. Con sensor válido y conexión disponible, cada medición produce una publicación de distancia.
- Toda comunicación con el ESP32 pasa por el broker. El móvil y Python son clientes MQTT independientes.
- Los LEDs responden exclusivamente a comandos explícitos. No hay automatismos por distancia ni comandos toggle.

La conexión real con el broker, la versión concreta del cliente MQTT de C++, la compatibilidad efectiva de iOS y el funcionamiento con Claude Desktop Free quedan pendientes de prueba. No se instalan dependencias en esta etapa.

## 2. Transporte, identidad y acceso

Se adopta MQTT 3.1.1 como base de interoperabilidad. Cada cliente utilizará un client ID distinto: ESP32, panel iOS y puente Python no compartirán identificador.

El host será el dominio exacto del despliegue EMQX, con SNI y puerto MQTT/TLS 8883. Se utilizará una CA de confianza correspondiente al despliegue, con reloj válido en el ESP32. No se aceptará desactivar la verificación TLS ni sustituir el dominio por una IP fija. Estas condiciones están documentadas en la [guía de EMQX Serverless](https://docs.emqx.com/en/cloud/latest/deployments/port_guide_serverless.html).

Las credenciales se suministrarán mediante configuración local excluida del repositorio y una plantilla sin valores reales, según la consigna. Su creación y las exclusiones necesarias se realizarán en una etapa posterior, antes de incorporar secretos. Este documento no contiene credenciales.

Permisos previstos: el ESP32 publica telemetría, estados y disponibilidad, y se suscribe a comandos; móvil y Python publican comandos y se suscriben a la información del ESP32. La configuración efectiva de autorización debe verificarse en EMQX. El límite de gasto deberá mantenerse en 0 para usar exclusivamente la cuota gratuita.

## 3. Prefijo y representación

Prefijo definitivo del equipo 8: `sis234/equipo08/esp32-01/`.

Los tres clientes utilizarán exactamente este prefijo, reservado para el equipo 8. Cada tópico completo se forma concatenando este prefijo y uno de los sufijos de la tabla siguiente, sin agregar otra barra.

Los nombres y mensajes son sensibles a mayúsculas y minúsculas. Los payloads son texto UTF-8 sin comillas envolventes, espacios adicionales ni salto de línea. La distancia es un número simple, no un objeto JSON; los mensajes de control y estado son las cadenas literales indicadas.

## 4. Tópicos, dirección, QoS y retención

| Sufijo | Publica | Se suscribe | Payload | QoS de publicación | Retained |
|---|---|---|---|---|---|
| `telemetry/distance_cm` | ESP32 | iOS, Python | Decimal en cm, por ejemplo `24.6` | 0 | No |
| `telemetry/sensor_status` | ESP32 | iOS, Python | `valid` o `invalid` | 0 | No |
| `cmd` | iOS, Python | ESP32 | Uno de los once comandos de la sección 5 | 1 | No |
| `state/rojo` | ESP32 | iOS, Python | `on` u `off` | 1 | Sí |
| `state/amarillo` | ESP32 | iOS, Python | `on` u `off` | 1 | Sí |
| `state/verde` | ESP32 | iOS, Python | `on` u `off` | 1 | Sí |
| `availability` | ESP32; broker para Last Will | iOS, Python | `online` u `offline` | 1 | Sí |

El ESP32 solicitará suscripción QoS 1 a `cmd`. Los consumidores solicitarán QoS 0 para telemetría y QoS 1 para estados y disponibilidad. Se comprobará el QoS concedido por el broker y la configuración correspondiente del panel iOS.

QoS 0 permite pérdidas; una suscripción QoS 1 no convierte una publicación QoS 0 en fiable. QoS 1 admite duplicados y su PUBACK acredita recepción en el salto MQTT correspondiente, no encendido físico del LED. La retención conserva el último mensaje de un tópico; no es historial ni confirmación de una orden. Estas propiedades siguen [MQTT 3.1.1, OASIS](https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html).

## 5. Comandos y efectos

Todos los comandos se publican en `sis234/equipo08/esp32-01/cmd`. `Conservar` significa mantener el estado anterior de ese LED.

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

Los once comandos son oficiales; `todos:on` amplía la lista sin alterar los diez anteriores. Cada comando es idempotente: repetirlo consecutivamente deja el mismo resultado. Se rechazarán sin modificar salidas los mensajes vacíos, desconocidos, truncados o con cualquier diferencia respecto a estos once valores. No se deducirán comandos a partir de texto libre en el ESP32.

`todos:on` enciende el grupo completo mediante `LedBank::allOn()`, simétrico a `allOff()`. Las escrituras de GPIO son consecutivas; la orden agrupa el cambio lógico y no promete una conmutación eléctrica atómica de los tres pines.

El ESP32 procesará las órdenes en el orden en que las reciba. Ante órdenes diferentes de móvil y Python no existe un orden global entre publicadores: prevalece el efecto de la última orden procesada sobre cada salida. La idempotencia no elimina conflictos entre comandos distintos ni demuestra causalidad.

Después de aplicar cualquier comando válido, incluido uno repetido, el ESP32 publicará los tres estados. Los comandos `solo:*` se aplicarán localmente como una operación de selección exclusiva; sus tres publicaciones de estado son mensajes separados y no constituyen una transacción MQTT atómica.

Un estado publicado describe la salida GPIO aplicada por el firmware. No hay sensor de realimentación que confirme emisión de luz, integridad del LED o cableado. La comprobación física se hará durante las pruebas de montaje.

## 6. Medición, publicación y frescura

Con una medición válida se publicará la distancia en centímetros y el estado `valid`. La representación utilizará punto decimal y una cifra decimal; esto es resolución de presentación, no una promesa de exactitud. Solo se aceptarán valores finitos, no negativos y dentro del rango de trabajo que se declare para el sensor real. No se usarán unidades dentro del payload, coma decimal, NaN, infinito ni valores centinela.

Ante ausencia de eco, timeout o lectura fuera del rango declarado se publicará `invalid` y se omitirá la distancia de ese ciclo. No se publicará cero ni se repetirá una distancia anterior como si fuera una medición nueva. El intervalo y timeout concretos se comprobarán con la ficha del sensor para sostener el objetivo de 500 ms.

El objetivo de dos publicaciones de distancia por segundo se verificará con lecturas válidas y conectividad estable. Dos intentos de medición por segundo, o dos mensajes de estado, no acreditan dos distancias publicadas. Tras una desconexión se reanuda la publicación de mediciones nuevas; no se reconstruirá ni enviará un historial de lecturas atrasadas.

Distancia y sensor_status viajan en tópicos separados con QoS 0; pueden perderse de forma independiente. No tienen identificador de muestra ni constituyen un par atómico. Este contrato permite consultar la última lectura recibida, pero no garantiza correlacionar exactamente ambos mensajes con una misma medición física.

Cada consumidor registrará cuándo recibió la última distancia y el último estado del sensor. Al iniciar o reconectar esperará información nueva. Ante `invalid`, falta de información reciente o disponibilidad `offline`, no presentará el último número como una lectura actual válida. Un `valid` sin distancia reciente tampoco habilita una lectura actual. El umbral inicial propuesto de caducidad es 2 s para ambos mensajes, pendiente de validar con la red y la aplicación.

RF4 se demostrará con un gauge, barra o gráfico de línea suscrito a la distancia. Se configurará además una señal visible de invalidez o pérdida de actualización; un indicador textual adicional de diagnóstico no sustituye la visualización gráfica. Debe probarse cómo representar esa situación en IoT MQTT Panel sin inventar una distancia.

## 7. Sesiones, disponibilidad y recuperación

Se utilizarán sesiones limpias para evitar una cola persistente de comandos del ESP32 desconectado. No se enviarán órdenes retenidas y se verificará que no exista un mensaje retained antiguo en `cmd` antes de habilitar las suscripciones. Las órdenes emitidas sin el ESP32 conectado no se consideran ejecutadas; no habrá reenvío automático desde los consumidores al recuperar conexión.

Antes de conectar, el ESP32 configurará Last Will `offline`, QoS 1 y retained, en `availability`. Tras conectar, restaurar la suscripción y publicar los tres estados vigentes, publicará `online` retained. En una desconexión planificada intentará publicar `offline` antes de cerrar la sesión; en una pérdida inesperada la detección y publicación del Will dependen del broker y del keepalive.

`online` expresa conexión MQTT anunciada; no acredita medición válida ni disponibilidad instantánea. Su último valor retenido puede quedar temporalmente desactualizado. Los clientes combinarán disponibilidad, conexión propia y frescura de telemetría. Los estados retenidos de LEDs se mostrarán como últimos estados conocidos cuando no exista conexión actual comprobable.

La pérdida de WiFi o MQTT no cambiará automáticamente los LEDs. El arranque aprobado tras encendido o reinicio es con los tres apagados. El montaje definitivo utiliza GPIO27 para rojo, GPIO26 para amarillo y GPIO25 para verde, activos en HIGH, con resistencia individual de 220 Ω y cátodos a GND. El equipo confirmó el funcionamiento físico del control local y `todos:off`; falta probar físicamente `todos:on`. Al reconectar sin reinicio se publicarán los estados locales existentes.

El HC-SR04 tiene asignados TRIG en GPIO5 y ECHO en GPIO18 mediante divisor resistivo. El circuito anterior utilizó tres resistencias de 2,2 kΩ para ese divisor; se documenta como circuito anterior sujeto a verificación eléctrica. Antes de conectarlo se debe confirmar la disposición real de las resistencias, el punto de toma a GPIO18, masa común y tensión resultante; no se presupone una relación de división correcta solo a partir de sus valores. La lectura del sensor y la configuración de sus GPIO aún no se implementan. GPIO5 es un pin de strapping, cuya condición durante reset se revisará antes de integrar el sensor; véase [Espressif](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/gpio.html).

## 8. Herramientas MCP previstas y cobertura funcional

El SDK y Paho se integrarán en una fase posterior. Python mantendrá una caché en memoria con edades calculadas mediante reloj monotónico; stdout se reservará al transporte MCP y los logs irán a stderr. La documentación actual del [SDK oficial MCP v2](https://py.sdk.modelcontextprotocol.io/) exige Python 3.11 o posterior. No se ha comprobado todavía el entorno Python ni su ejecución desde Claude Desktop Free.

| Herramienta prevista | Parámetros | Propósito y resultado esperado |
|---|---|---|
| `leer_distancia` | Ninguno | Última distancia recibida, unidad cm, edad, estado del sensor y disponibilidad; indicar explícitamente si es desconocida, inválida o antigua. |
| `consultar_leds` | Ninguno | Últimos estados conocidos de rojo, amarillo y verde, junto con disponibilidad y vigencia conocida. |
| `ejecutar_comando` | `comando`: enumeración de los once valores exactos de la sección 5 | Validar y publicar QoS 1, sin retained; distinguir envío pendiente, aceptado por el broker y fallo. |

Las herramientas de actuación no afirmarán ejecución física a partir de PUBACK ni de estados retained. Este contrato no incluye tópico de ACK ni identificador de orden; una actualización de estado permite observar el resultado informado, pero no confirmar que proviene de una orden concreta con varios publicadores activos. Las herramientas rechazarán nuevas órdenes si Python no está conectado al broker y no aceptarán comandos arbitrarios fuera de la enumeración.

Ejemplos de interpretación prevista: «¿A qué distancia está ahora?» utiliza `leer_distancia`; «Enciende el rojo y apaga los demás» envía `solo:rojo`; «Enciende todos» envía `todos:on`; «Apaga todos» envía `todos:off`. La interpretación de lenguaje natural corresponde a Claude; Python y ESP32 validan parámetros y mensajes.

| Requisito | Mecanismo y evidencia futura |
|---|---|
| RF1 | Medición ultrasónica contrastada con una referencia física. MQTT transporta el resultado, no realiza la medición. |
| RF2 | `telemetry/distance_cm` periódico en EMQX, con objetivo de 2 lecturas válidas/s. |
| RF3 | Suscripción a `cmd`, ejecución de los once comandos y publicación de estados. |
| RF4 | Visualización gráfica en iOS, con datos recibidos del broker. |
| RF5 | Controles iOS que publican los comandos aprobados sin retained. |
| RF6 | Claude consulta y actúa mediante las herramientas MCP, con Python como cliente MQTT. |

El contrato cubre RF1 a RF6 en diseño. El cumplimiento solo podrá acreditarse con implementación y pruebas. El servomotor de los ejemplos oficiales no es necesario porque el grupo ha elegido tres LEDs, alternativa admitida por la consigna.

## 9. Verificación inicial efectuada

Se leyó completa la consigna y se revisó platformio.ini. El 24 de octubre de 2026 se ejecutó la compilación de la plantilla mediante `platformio run -e esp32doit-devkit-v1`, utilizando el ejecutable del entorno instalado en `.platformio/penv/Scripts/`.

| Elemento | Evidencia local |
|---|---|
| PlatformIO Core | 6.2.0 |
| Plataforma Espressif32 | 7.0.1 |
| Placa y framework | esp32doit-devkit-v1; Arduino |
| Paquete framework | 3.20017.241212+sha.dcc1105b; núcleo Arduino-ESP32 2.0.17 |
| Toolchain | toolchain-xtensa-esp32 8.4.0+2021r2-patch5 |
| Resultado | SUCCESS, código de salida 0; 38,77 s informados por PlatformIO |
| RAM de la plantilla | 21 032 / 327 680 bytes, 6,4 % |
| Flash de aplicación | 233 241 / 1 310 720 bytes, 17,8 % |

La primera ejecución quedó bloqueada por permisos del aislamiento sobre `.platformio/platforms.lock` y la caché global. Se repitió con el permiso solicitado y finalizó correctamente. No fue necesario modificar platformio.ini ni instalar bibliotecas adicionales. La estructura PlatformIO y el código fuente se conservaron.

La [documentación de PlatformIO](https://docs.platformio.org/en/latest/boards/espressif32/esp32doit-devkit-v1.html) identifica esta placa y su soporte Arduino. La compilación comprueba compatibilidad de construcción de la plantilla con los paquetes indicados; no verifica la placa física, la carga, el sensor, TLS ni las futuras dependencias MQTT/MCP. El límite de aplicación de 1 310 720 bytes corresponde a la partición utilizada y no contradice los 4 MB físicos indicados por el perfil de placa.

La plataforma continúa sin versión fijada en platformio.ini. No impide esta compilación, pero una instalación futura puede resolver versiones distintas. Fijarla para reproducibilidad queda como mejora posterior, antes de integrar dependencias. Los artefactos de compilación permanecen en `.pio/`, directorio ya ignorado por Git. No se ejecutó carga al ESP32.

## 10. Decisiones y datos pendientes

Antes del montaje se necesita:

1. El sensor está identificado como HC-SR04. Quedan pendientes fabricante/revisión y ficha técnica, tensión de alimentación, niveles TRIG/ECHO, rango, intervalo mínimo y timeout admisible. Verificar eléctricamente el divisor anterior de tres resistencias de 2,2 kΩ antes de conectar ECHO al ESP32.
2. Identificación de la placa física y del módulo montado, pinout de sus cabeceras y comprobación de que los GPIO25/26/27 aprobados para los LEDs están disponibles. La asignación definitiva del sensor es TRIG=GPIO5 y ECHO=GPIO18 con divisor; está reservada y documentada, sin implementación.
3. Verificación física del montaje aprobado: rojo en GPIO27, amarillo en GPIO26 y verde en GPIO25; una resistencia de 220 Ω por LED, cátodos a GND y encendido con HIGH. Comprobar polaridad, valores de resistencia y tensión directa de los LEDs reales.
4. Fuente de alimentación, cable USB de datos, protoboard y conexiones de masa común. Confirmar qué alimentación admite la placa y qué alimentación requiere el sensor.
5. Revisión del esquema con las conexiones aprobadas y prueba visual de cada LED. El arranque apagado ya está aprobado e implementado en el control local; no hace falta esperar las credenciales del broker. Véase la guía de prueba en [README](../README.md).

El identificador del grupo ya está definido: equipo08. Antes de las integraciones de red se necesita WiFi de 2,4 GHz utilizable sin portal cautivo, host/CA del despliegue, autenticación y autorización configuradas localmente, acceso a DNS/NTP y puerto 8883, cuotas verificadas y client IDs únicos. No se deben copiar contraseñas al repositorio ni a este documento.

También quedan pendientes: elegir y fijar la biblioteca MQTT de C++ con soporte de los QoS acordados; probar handshake TLS/SNI; verificar QoS, retained, gráfico y caducidad en iOS; comprobar Python/SDK MCP v2/Paho y descubrimiento de herramientas en Claude Desktop Free; medir recuperación ante cortes y ajustar los tiempos acotados de conexión, keepalive y frescura.

## 11. Criterios para la integración posterior

Las siguientes pruebas están pendientes, no son resultados obtenidos:

- Medir distancias conocidas dentro del rango declarado, incluyendo ausencia de eco y timeout, sin fabricar lecturas.
- Verificar dos publicaciones de distancia por segundo con sensor válido y red estable; medir tanto emisión como recepción para identificar pérdidas QoS 0.
- Probar los once comandos, sus repeticiones y entradas inválidas en la futura integración MQTT; comprobar visualmente cada LED y la coherencia de los tres estados. Las pruebas locales previas comunicadas por el equipo no acreditan esa integración ni el nuevo `todos:on`.
- Confirmar ausencia de retained en cmd y de reproducción de órdenes antiguas al reconectar.
- Visualizar gráficamente la distancia en iOS, controlar los tres LEDs y mostrar pérdida de validez/actualización.
- Ejecutar consultas y comandos en lenguaje natural desde Claude; informar fallos, datos antiguos y confirmaciones limitadas sin inventar resultados.
- Cortar WiFi/MQTT y reiniciar el ESP32 para comprobar reconexión automática, resuscripción, Last Will y republicación de estados.
- Probar rechazo de CA/hostname o credenciales incorrectos manteniendo la verificación TLS.

La sección 3.2 de la consigna exige declarar en README y verificar estabilidad, exactitud, tiempo de respuesta, frecuencia y reconexión. Las referencias oficiales son al menos 10 minutos sin bloqueos, error máximo de ±3 cm dentro del rango declarado y respuesta móvil-broker-ESP32 de hasta 1 s. Son referencias para acordar y medir, no resultados. La frecuencia objetivo de 2 lecturas/s sí está aprobada para este proyecto. Faltan el rango de trabajo y los restantes valores definitivos, incluido un tiempo máximo de reconexión medible; el README actual documenta exclusivamente la etapa local de LEDs.
