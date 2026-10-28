# Pruebas pendientes de MQTT/TLS con el ESP32

Fecha: 27 de octubre de 2026. Esta guía contiene resultados esperados, no pruebas físicas realizadas por el asistente. El equipo ya confirmó ControlLeds, SensorUltrasonico, ConexionWifi y su convivencia, además del broker mediante MQTT.fx. Falta probar la nueva conexión MQTT desde el ESP32.

## Configuración previa

1. Completar manualmente la contraseña en `include/ConfiguracionMqtt.h`. El archivo está ignorado por Git y se entrega con clave vacía. El usuario previsto es `equipo08_esp32`; la autenticación y las autorizaciones deben existir en EMQX. No usar credenciales reales en README, capturas públicas ni exportaciones compartidas de MQTT.fx.
2. Conservar la configuración WiFi privada que ya funciona. No cambiar conexiones ni GPIO: rojo 27, amarillo 26, verde 25; TRIG 5 y ECHO 18 con el divisor existente.
3. Confirmar que el despliegue está activo, sus cuotas disponibles y el límite de gasto en 0. Eliminar desde EMQX cualquier mensaje retenido anterior en `sis234/equipo08/esp32-01/cmd`, antes de conectar el ESP32.
4. Compilar con `pio run -e esp32doit-devkit-v1`. Cuando el circuito y la configuración estén listos, el usuario puede ejecutar PlatformIO: Upload y abrir Serial Monitor a 115200 baudios. No se ejecutó Upload durante el desarrollo.

La ausencia de clave mantiene MQTT deshabilitado e informa configuración incompleta una sola vez. No impide medir ni controlar LEDs. Las credenciales se incorporan al firmware al compilar una configuración real; .pio/ está ignorado. La CA pública sí debe conservarse en el repositorio.

## Perfil de MQTT.fx

| Campo | Valor |
|---|---|
| Broker | `zffa4f2f.ala.us-east-1.emqxsl.com` |
| Puerto | `8883` |
| Protocolo | MQTT 3.1.1 |
| SSL/TLS | Habilitado, con verificación del servidor y su nombre |
| CA | `certificados/emqxsl-ca.crt` |
| Client ID de MQTT.fx | Por ejemplo, `equipo08_mqttfx_01`; siempre diferente de `equipo08_esp32_01` |
| Autenticación | Usuario autorizado y clave introducida localmente |

Los nombres de las opciones SSL varían según la versión de MQTT.fx. No seleccionar opciones que acepten cualquier certificado o desactiven la verificación. El perfil debe usar el dominio completo para SNI y validación del nombre. El usuario de MQTT.fx debe poder publicar cmd y suscribirse a los tópicos del equipo; no necesita publicar telemetría ni estados del ESP32.

## Publicaciones y comandos

1. Conectar MQTT.fx y suscribirse a `sis234/equipo08/esp32-01/#` solicitando QoS 1. Observar el log Serial del ESP32. Con reloj válido, TLS, autenticación y autorización correctos, el firmware debe anunciar la sesión segura y la suscripción cmd.
2. Comprobar que publica inicialmente los tres estados reales del programa y después `online` en availability, con QoS 1 y retained. Estos mensajes describen GPIO aplicados; verificar visualmente los LEDs como comprobación física independiente.
3. Con un objeto frente al sensor, comprobar `valid` y una distancia decimal con punto y una cifra decimal, QoS 0 y no retained, aproximadamente dos veces por segundo con conexión estable. Solicitar QoS 1 en el suscriptor no cambia el QoS 0 del publicador.
4. Cuando se produzca ausencia de pulso completo o lectura fuera de rango, comprobar `invalid` y ausencia de una nueva distancia para ese ciclo. No debe emitirse cero, NaN ni una lectura antigua como si fuera nueva. Otros objetos pueden producir ecos aunque se retire el objetivo.
5. Publicar en `sis234/equipo08/esp32-01/cmd` cada uno de los once comandos de [protocolo_mqtt.md](protocolo_mqtt.md), con QoS 1 y **Retain desmarcado**. Probar cada uno dos veces para comprobar idempotencia y verificar los tres mensajes state posteriores. `solo:*` debe apagar los demás LEDs; `todos:on` y `todos:off` deben afectar los tres.
6. Probar desde MQTT.fx mensajes vacíos, `rojo:toggle`, `Rojo:on`, espacios adicionales y un texto largo: deben rechazarse sin alterar salidas. El callback admite hasta 31 bytes ASCII imprimibles y delega la validación del comando a ControlLeds. Paquetes que excedan el buffer MQTT de 256 bytes pueden provocar cierre de conexión por la biblioteca, sin ejecución parcial.
7. Enviar los mismos comandos válidos por Serial: también deben actualizar los estados publicados. Mover el objeto sin comandos no debe modificar los LEDs.
8. Desconectar y volver a conectar solo MQTT.fx: debe recibir los últimos estados retenidos y la disponibilidad, pero no una distancia retenida. Esperar la siguiente medición nueva. Las publicaciones de distintos tópicos no forman una transacción atómica.

## Reconexión y fallos

- **Corte WiFi:** apagar el punto de acceso. Comprobar que los comandos Serial y el sensor siguen ejecutándose entre intentos. El broker debe publicar el LWT offline al detectar el cierre o la pérdida; no se exige que aparezca inmediatamente al apagar el AP. Volver a habilitar el mismo AP: ConexionWifi conserva sus reintentos de 15 s y MQTT reintenta tras su propio plazo de 30 s, restaura cmd, publica los tres estados actuales y online.
- **Fallo de MQTT con WiFi disponible:** interrumpir la salida a Internet del AP, manteniendo su radio activa, si el entorno de prueba lo permite. Observar el cierre o timeout de sesión y la pausa de 30 s antes de reintentar. Al restaurar la salida debe resuscribir cmd sin reiniciar el ESP32. Verificar con un nuevo comando remoto, no solo con el mensaje Serial.
- **Autenticación incorrecta:** modificar únicamente la copia privada, compilar y cargar personalmente una clave incorrecta. Debe fallar sin imprimirla y seguir operando localmente entre intentos. Restaurar luego la clave correcta y volver a compilar. No confundir CONNACK/PUBACK con una comprobación visual de los LEDs.
- **Hora no disponible:** si la red bloquea NTP y el reloj arranca sin fecha válida, el firmware debe aplazar TLS tras 10 s de supervisión sin espera activa. Reintenta pasado el intervalo. Nunca debe recurrir a TLS sin verificación. El servicio SNTP del framework puede recibir la hora más tarde; no se inventa una fecha mediante setTime.
- **Conflicto de identificadores:** evitar otra conexión con el client ID del ESP32. EMQX puede cerrar una de las conexiones y producir reconexiones repetidas.

Antes de repetir las pruebas comprobar que cmd continúa sin retained. La biblioteca 2.5.2 no entrega la marca retained al callback utilizado; el ESP32 no puede distinguir de forma fiable un comando retenido antiguo de uno nuevo. La limpieza del broker y la configuración de los publicadores son necesarias.

Los estados conservan su valor local si se pierde la red; al reconectar se publica lo que haya aplicado ControlLeds. No se reenvían comandos desde el firmware ni se almacenan mediciones atrasadas. Después de offline, un state retenido representa el último estado conocido, no una lectura física actual. Dos publicadores pueden enviar órdenes concurrentes y no hay identificador de orden/ACK de aplicación.

## Tiempos y límites

| Operación | Configuración y alcance |
|---|---|
| Sensor | Programación cada 500 ms, pulseIn con timeout de 30 ms, sin cambios |
| WiFi | Reintentos de la clase existente cada 15 s |
| NTP | configTime asíncrono, consulta de time() por vuelta y plazo lógico de 10 s; no se intenta TLS con reloj anterior al 1 de enero de 2026 |
| Reconexión MQTT | 30 s tras un fallo/cierre; sin bucle que espere conexión |
| TCP/escrituras TLS | Timeout nominal de 1000 ms; se configura también el timeout de socket a 1 s |
| Handshake TLS | 3 s nominales |
| Operación MQTT | 1000 ms por operación; no por todo el ciclo de inicialización |
| Keepalive | 30 s; disponibilidad offline depende de detección TCP/keepalive del broker |

TLS y MQTT son síncronos. Al conectarse se realizan CONNECT, SUBSCRIBE, tres publicaciones de estados y online. La biblioteca también puede atender callbacks mientras espera ACK. El callback aplica comandos y solo marca estados pendientes; nunca publica de forma recursiva. Si llega otro comando durante un PUBACK, queda marcada una nueva publicación de estados para la siguiente vuelta.

**La cadencia de 500 ms no está garantizada durante operaciones de red.** Los plazos anteriores se acumulan con sobrecargas; DNS no está limitado por el timeout TCP. El código instalado de Arduino-ESP32 2.0.17 contiene una espera DNS de hasta 16 s por exclusión y otra de hasta 15 s por resolución. Esas pausas también pueden retrasar comandos Serial. La solución conserva el control local entre intentos, pero no es un cliente de red completamente asíncrono ni ofrece tiempo real estricto. Medir esta limitación durante la práctica, incluyendo red sin Internet y pérdida de DNS.

## Certificado y compilación comprobados

Se utilizó el archivo aportado por el equipo `certificados/emqxsl-ca.crt`, sin modificarlo ni reemplazarlo por otro. Es PEM, sujeto/emisor DigiCert Global Root G2, con vigencia declarada 2013-08-01 a 2038-01-15. SHA-256 del archivo: `5d550643b6400d4341550a9b14aedd0b4fac33ae5deb7d8247b6b4f799c13306`.

PlatformIO lo incorpora con board_build.embed_txtfiles, incluido el terminador cero, y WiFiClientSecure lo recibe mediante setCACert(). No hace falta convertirlo a un encabezado ni subir un sistema de archivos. Se verificó por inspección del binario de prueba la presencia de los bytes originales completos más el terminador. Se usa connect() con el dominio completo; en el core instalado esto configura el hostname de mbedTLS para SNI y validación del nombre. La llamada connect(..., true) de MQTT solo omite abrir de nuevo el transporte que ya completó TLS; no omite la validación TLS.

El 27 de octubre de 2026 se compiló con PlatformIO, Espressif32 7.0.1, Arduino-ESP32 2.0.17 y `256dpi/MQTT@2.5.2`:

- Ruta habilitada con clave ficticia exclusivamente para compilar/enlazar: SUCCESS, salida 0, 8,64 s; RAM estática 46 392 bytes y flash 909 197 bytes. No se ejecutó ni se intentó autenticar con esa clave.
- Después de restaurar la clave privada vacía: SUCCESS, salida 0, 8,50 s; RAM estática 46 392 bytes (14,2 %) y flash 905 685 bytes (69,1 %).

La compilación comprueba compatibilidad de construcción con esas versiones. No comprueba handshake real, cadena del endpoint, autenticación, autorización, resuscripción, QoS entregado, LWT, consumo máximo de heap TLS, watchdog, exactitud ni frecuencia bajo carga. Todas esas verificaciones de ejecución permanecen pendientes.

Referencias: [biblioteca 2.5.2](https://github.com/256dpi/arduino-mqtt/tree/v2.5.2), [datos incrustados en PlatformIO](https://docs.platformio.org/en/latest/platforms/espressif32.html#embedding-binary-data), [conexión EMQX Serverless](https://docs.emqx.com/en/cloud/latest/deployments/port_guide_serverless.html).
