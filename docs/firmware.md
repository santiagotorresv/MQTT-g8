# Firmware y montaje · Equipo 08

Guía de conexiones, configuración y ejecución del firmware C++ con PlatformIO y Arduino para DOIT ESP32 DEVKIT V1.

## Conexiones

Cada LED se conecta como GPIO → resistencia de 220 Ω → ánodo; todos los cátodos van a GND. El encendido utiliza HIGH. Montar con la alimentación desconectada.

| LED | GPIO | Resistencia |
|---|---|---|
| Rojo | 27 | 220 Ω |
| Amarillo | 26 | 220 Ω |
| Verde | 25 | 220 Ω |

`ControlLeds::iniciar()` deja los tres LEDs apagados. El firmware no controla los niveles anteriores a su inicialización.

| HC-SR04 | Conexión |
|---|---|
| VCC | 5 V |
| GND | GND común con el ESP32 |
| TRIG | GPIO5 |
| ECHO | GPIO18 mediante el divisor anterior de tres resistencias de 2,2 kΩ |

El divisor corresponde al circuito anterior, **sujeto a verificación eléctrica**. Sus valores no bastan para deducir la relación de división: antes de conectar ECHO, revisar el esquema real, la disposición de las resistencias, la toma hacia GPIO18 y la tensión resultante. No conectar ECHO directamente al ESP32.

GPIO5 es un pin de strapping; el circuito debe respetar sus condiciones durante reset. Consultar la [documentación GPIO de Espressif](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/gpio.html).

## Módulos

| Archivos | Responsabilidad |
|---|---|
| `include/ControlLeds.h`, `src/ControlLeds.cpp` | Tres salidas y estados privados; ejecución de los once comandos idempotentes. |
| `include/SensorUltrasonico.h`, `src/SensorUltrasonico.cpp` | Inicialización del HC-SR04 y medición con distancia y validez separadas. |
| `include/ConexionWifi.h`, `src/ConexionWifi.cpp` | Conexión de estación y reintentos WiFi temporizados. |
| `include/ConexionMqtt.h`, `src/ConexionMqtt.cpp` | Hora, TLS, suscripción a comandos y publicación de telemetría, estados y disponibilidad. |
| `src/main.cpp` | Inicialización, comandos Serial y coordinación periódica de los módulos. |
| `platformio.ini` | Placa, framework, biblioteca MQTT, CA incrustada y monitor Serial. |

`ControlLeds` ofrece métodos para establecer cada salida, encender/apagar todos, encender exclusivamente un color y consultar sus estados. `ejecutarComando()` valida los textos del [contrato MQTT](protocolo_mqtt.md).

`SensorUltrasonico::iniciar()` prepara TRIG en LOW y ECHO como entrada. `medir()` genera LOW durante 2 µs y HIGH durante 10 µs; utiliza `pulseIn(..., HIGH, 30000UL)`. Calcula `distancia_cm = duración_ECHO_µs × 0,034 / 2`, por el recorrido de ida y vuelta del sonido.

Sin pulso completo o fuera del rango nominal 2–400 cm devuelve `valida=false` y `distanciaCm=NaN`. La validez debe consultarse antes de usar la distancia; no se representa un error como 0 cm. No hay filtros ni compensación por temperatura. Referencias: [ficha HC-SR04](https://cdn.sparkfun.com/datasheets/Sensors/Proximity/HCSR04.pdf) y [pulseIn](https://docs.arduino.cc/language-reference/en/functions/advanced-io/pulseIn/).

El bucle procesa hasta 32 bytes Serial por vuelta y programa una medición cada 500 ms con `millis()`. `pulseIn()` puede bloquear nominalmente hasta 30 ms; las operaciones de red también pueden retrasar el bucle. El sensor no modifica los LEDs.

## Configuración WiFi y MQTT

Crear las copias privadas solo si aún no existen, desde la raíz del repositorio:

```powershell
if (-not (Test-Path include/ConfiguracionWifi.h)) {
    Copy-Item include/ConfiguracionWifi.ejemplo.h include/ConfiguracionWifi.h
}
if (-not (Test-Path include/ConfiguracionMqtt.h)) {
    Copy-Item include/ConfiguracionMqtt.ejemplo.h include/ConfiguracionMqtt.h
}
git check-ignore -v include/ConfiguracionWifi.h include/ConfiguracionMqtt.h
```

Completar únicamente esas copias:

| Archivo local | Campos |
|---|---|
| `include/ConfiguracionWifi.h` | `NombreRedWifi`: red de 2,4 GHz; `ClaveRedWifi`: contraseña. Vacía solo para una red abierta. |
| `include/ConfiguracionMqtt.h` | `UsuarioMqtt` y `ClaveMqtt`: credenciales autorizadas en EMQX. Conservar host/puerto y usar un Client ID exclusivo para la placa. |

No sobrescribir configuraciones existentes ni publicar las copias privadas. Cambiar las credenciales requiere recompilar y cargar. Si falta configuración, se deshabilita la conexión correspondiente y se mantiene el control local.

La conexión requiere un despliegue EMQX activo, cuotas disponibles y permisos para publicar telemetría/estados/disponibilidad y suscribirse a `cmd`. Mantener el uso dentro de la cuota gratuita y el límite de gasto en 0. Antes de conectar la placa, eliminar del broker cualquier mensaje retenido antiguo en `sis234/equipo08/esp32-01/cmd`: el callback utilizado no expone esa bandera.

`ConexionWifi.iniciar()` lanza el intento; `actualizar()` supervisa cambios y reintenta cada 15 s mediante `millis()`; `estaConectada()` consulta `WL_CONNECTED`. Serial informa conexión, desconexión, reintentos e IP. Una IP local no garantiza acceso a Internet. No se implementan portales cautivos ni autenticación empresarial.

Las credenciales se incorporan al firmware al compilar; `.pio/` está ignorado. `WiFi.persistent(false)` evita nuevas escrituras del controlador en NVS, sin borrar las anteriores ni cifrar credenciales.

## TLS y funcionamiento de la conexión

Host: `zffa4f2f.ala.us-east-1.emqxsl.com`; puerto: `8883`; MQTT 3.1.1 sobre TLS. El dominio completo permite SNI y validación del nombre.

La CA pública [emqxsl-ca.crt](../certificados/emqxsl-ca.crt) corresponde a DigiCert Global Root G2. PlatformIO la incorpora mediante `board_build.embed_txtfiles` y el transporte usa `setCACert()`; no requiere subir un sistema de archivos. Mantener habilitada la validación del certificado y disponer de fecha/hora correctas.

| Operación | Configuración |
|---|---|
| Hora NTP | Inicio asíncrono, supervisión de 10 s; sin hora válida se aplaza TLS. |
| Reintento MQTT | 30 s tras un fallo o cierre. |
| TCP/escrituras TLS | Timeout nominal de 1000 ms; socket a 1 s. |
| Handshake TLS | Timeout nominal de 3 s. |
| Operación MQTT | Timeout de 1000 ms por operación. |
| Keepalive | 30 s. |

TLS/MQTT son síncronos y estos plazos no constituyen un límite global: se acumulan y DNS tiene esperas propias. El control local continúa entre intentos; la cadencia de 500 ms no está garantizada durante operaciones de red.

Tras suscribirse, el ESP32 publica los estados locales y `online`. El broker publica el Last Will `offline` cuando detecta la desconexión. Una pérdida de red no cambia los LEDs ni almacena mediciones para enviarlas después.

## Compilar, cargar y abrir Serial

Instalar PlatformIO con soporte para Espressif32/Arduino. Desde una terminal situada en la raíz:

```powershell
pio run -e esp32doit-devkit-v1
pio run -e esp32doit-devkit-v1 --target upload
pio device monitor -e esp32doit-devkit-v1
```

La segunda orden carga la placa: ejecutarla con el montaje revisado y un cable USB de datos. También pueden usarse **PlatformIO: Upload** y **PlatformIO: Serial Monitor** en VS Code. Si hay varios puertos, indicar el real con `--upload-port COMx` al cargar y `--port COMx` al abrir el monitor; `COMx` es un marcador.

Si `pio` no está en PATH, utilizar la terminal de PlatformIO o su ejecutable instalado. En una instalación estándar de Windows puede invocarse con `& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe"` seguido de los mismos argumentos.

El monitor utiliza **115200 baudios**, LF y `send_on_enter`. Escribir una orden del contrato, por ejemplo `todos:on`, `solo:verde` o `todos:off`, y pulsar Enter. Se muestran el comando, su aceptación o rechazo y los tres estados. También aparecen distancias en centímetros o el aviso de medición inválida.

Otros monitores pueden enviar LF, CR o CRLF. Los comandos admiten hasta 31 bytes ASCII imprimibles, sin espacios adicionales; una línea vacía o inválida no modifica los LEDs. Una línea excesiva se descarta por completo y la siguiente puede procesarse normalmente.

## Cliente MQTT.fx opcional

Para observar mensajes o enviar órdenes desde otra computadora, crear un perfil MQTT 3.1.1 con el mismo host, puerto 8883, TLS verificado y CA del repositorio. Introducir las credenciales autorizadas localmente y utilizar un Client ID distinto, por ejemplo `equipo08_mqttfx_01`.

Suscribirse a `sis234/equipo08/esp32-01/#`. Para controlar LEDs, publicar en `sis234/equipo08/esp32-01/cmd` un comando exacto del [protocolo](protocolo_mqtt.md), con QoS 1 y **Retain desactivado**. No compartir perfiles que contengan credenciales.

La plataforma Espressif32 no está fijada por versión en `platformio.ini`; la biblioteca MQTT sí lo está. El entorno usado y los objetivos del proyecto se describen en el [README](../README.md).
