# SIS-234 · Equipo 8 · MQTT + MCP

Estado actual: control local de tres LEDs con `LedBank` y una interfaz temporal por Serial. No se implementan todavía WiFi, MQTT, sensor ultrasónico ni MCP. El equipo confirmó mediante pruebas físicas el control de los tres LEDs y `todos:off`. Se añade `todos:on`, cuya prueba física permanece pendiente; no se ha cargado el firmware durante esta modificación.

Contrato de la futura integración: [docs/protocolo_mqtt.md](docs/protocolo_mqtt.md). Prefijo definitivo: `sis234/equipo08/esp32-01/`.

## Montaje previsto

Placa: DOIT ESP32 DEVKIT V1. Cada conexión es GPIO → resistencia de 220 Ω → ánodo del LED; todos los cátodos van a GND. El encendido utiliza HIGH. Montar con la alimentación desconectada.

| LED | GPIO | Resistencia |
|---|---|---|
| Rojo | 27 | 220 Ω |
| Amarillo | 26 | 220 Ω |
| Verde | 25 | 220 Ω |

Comprobar polaridad, correspondencia entre etiquetas GPIO y cabeceras, resistencias y masa común. El sensor no se conecta en esta etapa. El software apaga los LEDs al ejecutar `begin()`; no controla los niveles eléctricos anteriores a la inicialización del firmware.

La asignación definitiva reservada para el HC-SR04 es TRIG en GPIO5 y ECHO en GPIO18 mediante divisor resistivo. Estos pines solo se documentan: el firmware actual no los configura ni implementa lectura del sensor.

En el circuito anterior se utilizaron tres resistencias de 2,2 kΩ para el divisor de ECHO. Se registra como **circuito anterior sujeto a verificación eléctrica**: los valores por sí solos no permiten confirmar la relación de división. Antes de conectarlo al ESP32 se debe revisar el esquema real, la disposición de las tres resistencias, el punto de toma hacia GPIO18, la masa común y el nivel de tensión resultante. No conectar ECHO directamente a GPIO18 ni dar por validado el divisor sin esa revisión.

GPIO5 es un pin de strapping del ESP32; antes de integrar el HC-SR04 se comprobará que el circuito conectado respete su configuración durante reset. Véase la [documentación GPIO de Espressif](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/gpio.html).

## Organización del código

- `include/LedBank.h`: interfaz de la clase y enumeración de LEDs.
- `src/LedBank.cpp`: salidas activas en HIGH, estados lógicos y validación exacta de los once comandos.
- `src/main.cpp`: instancia en el orden del constructor rojo=GPIO27, amarillo=GPIO26 y verde=GPIO25; inicialización y recepción de líneas por Serial.
- `platformio.ini`: placa/framework y monitor a 115200 baudios, LF y filtro `send_on_enter` de PlatformIO para escribir una línea antes de enviarla.

`begin()` configura las salidas apagadas; `set()` controla un LED, `allOn()` enciende los tres, `allOff()` los apaga y `only()` apaga los demás antes de encender el seleccionado. `isOn()` consulta el estado lógico guardado y `executeCommand()` devuelve si una orden fue válida. `allOn()` fija HIGH y el estado lógico en true para cada LED, de modo que repetirlo mantiene los tres encendidos. La clase no depende de Serial ni realiza asignaciones dinámicas de memoria. Se debe llamar a `begin()` antes de controlar los LEDs.

## Compilar y cargar cuando el circuito esté listo

Desde una terminal con PlatformIO disponible y situada en la raíz del proyecto:

```powershell
pio run -e esp32doit-devkit-v1
pio run -e esp32doit-devkit-v1 --target upload
pio device monitor -e esp32doit-devkit-v1
```

La segunda orden realiza la carga y debe ejecutarla el usuario cuando haya revisado el circuito y conectado el USB de datos. También puede usar PlatformIO: Upload y PlatformIO: Serial Monitor en VS Code. Si hay varios puertos, elegir el real mediante `--upload-port COMx` al cargar y `--port COMx` al abrir el monitor; COMx es un marcador, no un puerto detectado.

Si `pio` no está en PATH, en este equipo el ejecutable está en `%USERPROFILE%\.platformio\penv\Scripts\platformio.exe`. En PowerShell puede invocarse con `& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe"` seguido de los mismos argumentos.

Compilación verificada con `todos:on` el 24 de octubre de 2026: `SUCCESS` (salida 0), 14,69 s, con Espressif32 7.0.1 y Arduino-ESP32 2.0.17. RAM: 21 512 / 327 680 bytes (6,6 %); flash de aplicación: 270 793 / 1 310 720 bytes (20,7 %). No se instalaron bibliotecas ni se cargó firmware durante esta modificación; la prueba física del nuevo comando está pendiente.

La revisión del código confirma que `begin()` prepara LOW y configura como salida cada GPIO; `only()` apaga los otros dos LEDs antes de encender el seleccionado. Los diez comandos anteriores conservan su implementación y se añade `todos:on` como undécimo comando. Esta es una verificación estática del programa, distinta de las pruebas físicas comunicadas por el equipo.

## Prueba manual por Serial

1. Abrir el monitor a 115200 baudios. Para ver el mensaje inicial, pulsar EN/RESET con el monitor abierto. Los tres LEDs deben quedar apagados después de inicializarse.
2. Escribir cada comando exacto y pulsar Enter. En otros monitores seleccionar LF, CR o CRLF como fin de línea. No incluir comillas ni espacios adicionales.
3. Enviar las once órdenes de esta tabla en orden. Repetir cada una dos veces: el resultado esperado debe mantenerse. La tabla describe resultados esperados; no registra una ejecución física de la versión nueva.

| Comando | Rojo esperado | Amarillo esperado | Verde esperado |
|---|---|---|---|
| `rojo:on` | on | off | off |
| `rojo:off` | off | off | off |
| `amarillo:on` | off | on | off |
| `amarillo:off` | off | off | off |
| `verde:on` | off | off | on |
| `verde:off` | off | off | off |
| `todos:on` | on | on | on |
| `todos:off` | off | off | off |
| `solo:rojo` | on | off | off |
| `solo:amarillo` | off | on | off |
| `solo:verde` | off | off | on |

Por cada línea se muestra el comando recibido, `OK` o el motivo de rechazo y el estado de rojo, amarillo y verde. Una línea vacía también es inválida.

Para comprobar los efectos de grupo, enviar `rojo:on`, `amarillo:on` y `verde:on`: los tres deben encenderse. Desde ese estado probar `solo:rojo`, después `solo:amarillo` y `solo:verde`. Volver a encender los tres y enviar `todos:off`.

Para validar específicamente el nuevo comando, enviar `todos:off`, `todos:on`, `todos:on` y `todos:off`, una línea por orden. Las dos ejecuciones consecutivas de `todos:on` deben mostrar `Estado: rojo=on amarillo=on verde=on`, sin apagar ni invertir ningún LED. La última orden debe devolver los tres a off.

Probar `rojo:toggle`, `Rojo:on`, un comando con espacios y una línea de 32 o más bytes ASCII: deben rechazarse sin cambiar los estados. El receptor guarda como máximo 31 bytes y descarta toda línea con exceso de longitud o bytes de control, sin ejecutar su prefijo. En esos errores se imprime solo el fragmento guardado y se informa el descarte. La siguiente línea válida debe procesarse normalmente.

## Límites de esta etapa

- El control local anterior y `todos:off` cuentan con confirmación física del equipo. La compilación de la mejora no sustituye la prueba física pendiente de `todos:on`.
- Los estados mostrados son estados lógicos del programa. No detectan un LED invertido, dañado o desconectado.
- Las escrituras sobre los tres GPIO son consecutivas, no una conmutación eléctrica simultánea y atómica.
- Los comandos se aplican al recibir un fin de línea; no hay timeout para una línea incompleta. No se utiliza `delay()` ni lectura serie con espera de línea.
- No se admiten caracteres de control dentro del comando, incluidos retroceso y tabulación. El filtro `send_on_enter` agrupa la entrada hasta Enter, pero no elimina los bytes de retroceso: si se comete un error, enviar esa línea para descartarla y volver a escribir el comando completo.
- La consola está pensada para pruebas manuales. Un flujo continuo de mensajes puede saturar la salida serie; se revisará la interfaz temporal antes de integrar MQTT.
- No se han verificado todavía los atributos de estabilidad, medición, respuesta móvil, publicación o reconexión exigidos para la integración final.
