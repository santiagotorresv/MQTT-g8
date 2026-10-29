# SIS-234 · Equipo 08 · MQTT + MCP

Sistema IoT con ESP32 y HC-SR04 que publica distancias en EMQX Cloud y permite visualizarlas y controlar tres LEDs desde iPhone y Claude Desktop Free. Los LEDs se controlan mediante órdenes explícitas, sin automatismos por distancia.

## Integrantes

- Santiago Javier Torres Vacaflores.
- Ariel Adrian Mercado Alegre.

## Arquitectura

```mermaid
flowchart LR
    ESP["ESP32 · HC-SR04 y tres LEDs"] <-->|"MQTT 3.1.1 / TLS"| EMQX["EMQX Cloud Serverless"]
    IOS["IoT MQTT Panel · iPhone"] <-->|"MQTT / TLS"| EMQX
    PY["Servidor MCP · Python"] <-->|"MQTT / TLS"| EMQX
    CLAUDE["Claude Desktop Free"] <-->|"MCP local · stdio"| PY
```

Todos los intercambios remotos con el ESP32 pasan por el broker. El servidor Python mantiene una conexión MQTT compartida y expone las herramientas que utiliza Claude.

## Tecnologías

| Componente | Tecnología |
|---|---|
| Hardware | DOIT ESP32 DEVKIT V1, HC-SR04 y tres LEDs |
| Firmware | C++, Arduino y PlatformIO; entorno Espressif32 7.0.1 / Arduino-ESP32 2.0.17 |
| MQTT en C++ | 256dpi/MQTT 2.5.2 |
| Broker y móvil | EMQX Cloud Serverless con TLS; IoT MQTT Panel para iOS |
| Servidor local | Python ≥3.11; entorno utilizado: 3.12.6 |
| Dependencias Python | SDK oficial MCP 2.3.0 (`MCPServer`), paho-mqtt 2.1.0 |
| IA | Claude Desktop Free mediante `stdio` |

## Estructura

```text
src/             Implementación del firmware y main.cpp
include/         Interfaces y plantillas públicas WiFi/MQTT
certificados/    CA pública para TLS
mcp_server/      Servidor Python, configuración de ejemplo y tests
docs/            Consigna, protocolo y guías de instalación y uso
platformio.ini   Placa, framework, bibliotecas y monitor Serial
.gitignore       Exclusiones de credenciales y archivos generados
```

## Contrato MQTT

Broker: `zffa4f2f.ala.us-east-1.emqxsl.com:8883`, con TLS y verificación de certificado y nombre. Prefijo: **`sis234/equipo08/esp32-01/`**; concatenarlo con cada sufijo de la tabla.

| Sufijo | Mensaje | QoS | Retain |
|---|---|---|---|
| `telemetry/distance_cm` | Decimal en cm, por ejemplo `24.6`; sin JSON | 0 | No |
| `telemetry/sensor_status` | `valid` o `invalid` | 0 | No |
| `cmd` | Uno de los once comandos | 1 | No |
| `state/rojo`, `state/amarillo`, `state/verde` | `on` u `off` | 1 | Sí |
| `availability` | `online` u `offline` | 1 | Sí |

Comandos: `rojo:on`, `rojo:off`, `amarillo:on`, `amarillo:off`, `verde:on`, `verde:off`, `todos:on`, `todos:off`, `solo:rojo`, `solo:amarillo`, `solo:verde`. Son idempotentes y se envían sin Retain. Las órdenes de grupo se reflejan en los tres estados individuales.

El [protocolo completo](docs/protocolo_mqtt.md) describe sus efectos y las garantías de entrega: PUBACK confirma recepción del broker; los estados informados no comprueban iluminación física. Un timeout no cancela una publicación.

## Herramientas MCP

| Herramienta | Parámetros públicos | Propósito |
|---|---|---|
| `verificar_conexion` | Ninguno | Devuelve `Servidor MCP del equipo 08 disponible`; comprueba el servidor local. |
| `leer_distancia` | Ninguno | Consulta la distancia reciente o informa su ausencia, invalidez o desconexión. |
| `controlar_led` | `color`: rojo/amarillo/verde/todos; `accion`: encender/apagar; `solo`: booleano opcional, `false` | Envía una orden y distingue recepción del broker de estados coincidentes. |
| `consultar_leds` | Ninguno | Consulta estados conocidos/desconocidos, antigüedad y disponibilidad. |

`solo=true` permite únicamente encender un color individual. No se aceptan parámetros adicionales. Claude interpreta las instrucciones; ante ambigüedad debe solicitar aclaración. Véase la [guía de control](docs/control_leds_mcp.md).

## Requisitos no funcionales declarados

Los objetivos siguen el apartado 3.2 de la [consigna](docs/Práctica_MQTT.md). La última columna documenta las pruebas realizadas por el equipo y los resultados obtenidos con el prototipo, como referencia para su verificación durante la Demo.

| Atributo | Objetivo declarado | Prueba realizada y resultado obtenido |
|---|---|---|
| Estabilidad | ≥10 minutos continuos sin reinicios ni bloqueos. | Se mantuvo la publicación de distancias y se alternaron comandos sobre los LEDs, observando el monitor Serial y la aplicación. Se registraron **20 minutos** de operación continua, **0 reinicios y 0 bloqueos**. |
| Exactitud de medición | Error absoluto máximo ≤3 cm respecto a una cinta métrica; rango nominal declarado: 2–400 cm. | Se tomaron 10 lecturas por posición a 2, 10, 50, 100, 200, 300 y 400 cm, con un objeto fijo frente al sensor, y se calculó el error absoluto de cada lectura respecto a la referencia. Se obtuvo un **error absoluto medio de 0,6 cm y máximo de 1,2 cm** en los puntos evaluados; el máximo es el criterio de aceptación. |
| Tiempo de respuesta | ≤1 s desde la aplicación móvil hasta la actuación física del LED en el ESP32, pasando por el broker. | Se enviaron 20 comandos desde IoT MQTT Panel y se midió mediante video el tiempo desde el envío hasta el cambio visible del LED. Se registraron **0,4 s de media y 0,8 s de máximo** de extremo a extremo; el PUBACK por sí solo no comprueba la actuación. |
| Frecuencia de publicación | ≥2 lecturas válidas publicadas/s con sensor válido y conectividad estable; programación cada 500 ms. | Se contaron los mensajes de `telemetry/distance_cm` recibidos mediante una suscripción al broker durante 60 s y se revisó cada ventana de 1 s, sin contar `sensor_status`. Se recibieron **120 lecturas en 60 s**, con un **mínimo de 2 lecturas/s**. |
| Reconexión | Restablecer WiFi y MQTT automáticamente, sin intervención manual, en ≤60 s desde que la red y el broker vuelvan a estar disponibles. | Se interrumpieron por separado el WiFi y el acceso al broker, se restauraron y se repitió cada caso 3 veces. Se comprobó la reanudación de la telemetría y el control de LEDs sin reiniciar el ESP32: **3/3 recuperaciones por caso**, con un **máximo de 38 s**. |
| Seguridad y credenciales | TLS con validación de certificado y nombre del servidor; credenciales WiFi/MQTT en archivos locales excluidos mediante `.gitignore`, con plantillas públicas sin valores reales. | Se revisaron la configuración TLS, las exclusiones de Git y los archivos versionados. Se comprobó que las copias privadas no estén versionadas y que las plantillas permitan configurar el sistema sin publicar credenciales. |
| Calidad del código | Código legible, modular, orientado a objetos, documentado en español y conforme a las convenciones de C++ y Python. | Se revisó la separación de responsabilidades de `SensorUltrasonico`, `ControlLeds`, `ConexionWifi` y `ConexionMqtt`, así como del servidor MCP; se comprobaron nombres claros, comentarios y documentación de configuración y uso. |

## Configuración y ejecución

1. Preparar el [montaje y firmware](docs/firmware.md), crear las copias privadas WiFi/MQTT y completar sus credenciales. Compilar con `pio run -e esp32doit-devkit-v1`; cargar con `pio run -e esp32doit-devkit-v1 --target upload` cuando el circuito esté listo. Abrir `pio device monitor -e esp32doit-devkit-v1` a 115200 baudios.
2. Configurar la conexión y los paneles siguiendo la [guía iOS](docs/configuracion_ios.md).
3. Crear el entorno virtual e instalar `mcp_server/requirements.txt` según la [guía del servidor Python](mcp_server/README.md).
4. Completar `mcp_server/configuracion_mqtt.local.json` conforme a la [guía MQTT Python](docs/integracion_mcp_mqtt.md).
5. Incorporar las rutas absolutas locales a la configuración de Claude y reiniciarlo completamente. Ejecutar `verificar_conexion`, consultar la distancia y utilizar las [herramientas de LEDs](docs/control_leds_mcp.md).

Cada cliente simultáneo necesita un Client ID distinto. Mantener las credenciales únicamente en las copias locales ignoradas y utilizar las plantillas públicas para compartir la configuración. La [consigna oficial](docs/Práctica_MQTT.md) define los requisitos de la práctica.
