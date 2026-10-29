# SIS-234 · Equipo 8 · MQTT + MCP

Estado actual: el equipo confirmó ESP32, EMQX, panel iOS y consulta de distancias reales mediante Claude Desktop Free. RF4 y RF5 están comprobados funcionalmente. La iteración 7.3 incorpora control y consulta de LEDs mediante MCP, con pruebas automatizadas aprobadas; su validación física desde Claude continúa pendiente. Se conservan los once comandos, GPIO y mediciones programadas cada 500 ms.

Contrato MQTT: [docs/protocolo_mqtt.md](docs/protocolo_mqtt.md). Prefijo definitivo: `sis234/equipo08/esp32-01/`. El estado de la integración iOS se registra en la guía siguiente; el contrato se conserva sin cambios.

## Aplicación iOS · Iteración 6

La [guía de configuración iOS](docs/configuracion_ios.md) documenta la conexión MQTT sobre TLS, el Dashboard `Control ESP32 - Equipo 08`, sus seis paneles y los pasos para reproducirlo en otro iPhone.

| Requisito | Estado | Prueba funcional confirmada por el equipo |
|---|---|---|
| RF4 · Visualización gráfica del sensor | Comprobado | El Gauge muestra la distancia recibida del broker en centímetros. |
| RF5 · Control móvil de actuadores | Comprobado | Los tres Switches encienden/apagan cada LED y los dos botones encienden/apagan los tres LEDs. |

Los Switches no tienen `Subscribe Topic`: su estado visual puede quedar desactualizado tras comandos de otros clientes. El ESP32 publica los estados aplicados en `state/rojo`, `state/amarillo` y `state/verde`, bajo el prefijo acordado. La prueba específica mediante datos móviles **no fue realizada**. Estas pruebas funcionales no acreditan valores medidos de latencia, estabilidad o frecuencia de publicación.

## Servidor MCP local · Distancia y LEDs

Se conservan Python 3.12.6, SDK MCP 2.3.0, paho-mqtt 2.1.0 y transporte `stdio`. Las herramientas `verificar_conexion()`, `leer_distancia()`, `controlar_led(color, accion, solo=false)` y `consultar_leds()` reutilizan una sola conexión MQTT/TLS. La [guía de control de LEDs MCP](docs/control_leds_mcp.md) detalla parámetros, confirmaciones, pruebas y limitaciones. La [guía de integración MCP/MQTT](docs/integracion_mcp_mqtt.md) conserva la preparación de credenciales y la consulta del sensor. La [guía del servidor MCP](mcp_server/README.md) explica el lanzamiento desde Claude.

Las 45 pruebas automatizadas de la iteración 7.3 pasaron, incluyendo los once comandos, entradas inválidas, QoS/Retain, estados históricos, timeouts y ejecución MCP. La consulta real de distancia desde Claude fue confirmada por el equipo. El control físico de LEDs desde Claude y la validación completa de RF6 siguen pendientes. Un PUBACK o estado MQTT no acredita iluminación física ni causalidad de una orden.

## Montaje previsto

Placa: DOIT ESP32 DEVKIT V1. Cada conexión es GPIO → resistencia de 220 Ω → ánodo del LED; todos los cátodos van a GND. El encendido utiliza HIGH. Montar con la alimentación desconectada.

| LED | GPIO | Resistencia |
|---|---|---|
| Rojo | 27 | 220 Ω |
| Amarillo | 26 | 220 Ω |
| Verde | 25 | 220 Ω |

Se conserva el circuito anterior, sin modificar GPIO ni resistencias. El software apaga los LEDs al ejecutar `ControlLeds::iniciar()`; no controla los niveles eléctricos anteriores a la inicialización del firmware.

| HC-SR04 | Conexión existente |
|---|---|
| VCC | 5 V |
| GND | GND común con el ESP32 |
| TRIG | GPIO5 |
| ECHO | GPIO18 a través del divisor anterior de tres resistencias de 2,2 kΩ |

El firmware configura TRIG como salida inicialmente LOW y ECHO como entrada. No cambia el circuito del divisor ni implementa ningún automatismo de LEDs por distancia.

En el circuito anterior se utilizaron tres resistencias de 2,2 kΩ para el divisor de ECHO. Se registra como **circuito anterior sujeto a verificación eléctrica**: los valores por sí solos no permiten confirmar la relación de división. Antes de conectarlo al ESP32 se debe revisar el esquema real, la disposición de las tres resistencias, el punto de toma hacia GPIO18, la masa común y el nivel de tensión resultante. No conectar ECHO directamente a GPIO18 ni dar por validado el divisor sin esa revisión.

GPIO5 es un pin de strapping del ESP32; antes de integrar el HC-SR04 se comprobará que el circuito conectado respete su configuración durante reset. Véase la [documentación GPIO de Espressif](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/gpio.html).

## Organización del código

- `include/ControlLeds.h`: interfaz pública, pines privados y estados explícitos de rojo, amarillo y verde.
- `src/ControlLeds.cpp`: salidas activas en HIGH, estados lógicos y validación exacta de los once comandos.
- `include/SensorUltrasonico.h` y `src/SensorUltrasonico.cpp`: inicialización, activación y medición del HC-SR04 con distancia y validez separadas.
- `src/main.cpp`: conserva rojo=GPIO27, amarillo=GPIO26 y verde=GPIO25; añade TRIG=GPIO5, ECHO=GPIO18 y programación con millis(), manteniendo los once comandos por Serial.
- `include/ConexionWifi.h` y `src/ConexionWifi.cpp`: conexión en modo estación, consulta del estado y reintentos WiFi temporizados, sin tocar salidas ni mediciones.
- `include/ConfiguracionWifi.ejemplo.h`: plantilla vacía versionable; la copia privada `include/ConfiguracionWifi.h` está excluida de Git.
- `include/ConexionMqtt.h` y `src/ConexionMqtt.cpp`: TLS, preparación de hora, conexión, suscripción, telemetría y estados; reutiliza ControlLeds y ConexionWifi.
- `include/ConfiguracionMqtt.ejemplo.h`: configuración MQTT pública de ejemplo. `include/ConfiguracionMqtt.h` es la copia privada ignorada, creada sin contraseña real.
- `certificados/emqxsl-ca.crt`: CA pública aportada por el equipo, incorporada por PlatformIO sin duplicarla como encabezado.
- `platformio.ini`: placa/framework y monitor a 115200 baudios, LF y filtro `send_on_enter` de PlatformIO para escribir una línea antes de enviarla.

`ControlLeds` encapsula tres pines y tres estados booleanos privados, sin estructura de canales, arreglo ni enumeración. `iniciar()` prepara LOW y configura las salidas. `establecerRojo(bool)`, `establecerAmarillo(bool)` y `establecerVerde(bool)` actualizan salida y estado. `encenderTodos()`, `apagarTodos()` y los tres métodos `encenderSolo...()` reutilizan esos métodos; los de selección apagan primero los otros dos LEDs. `estaRojoEncendido()`, `estaAmarilloEncendido()` y `estaVerdeEncendido()` consultan los estados. `ejecutarComando()` valida los once textos exactos, sin invertir estados al repetirlos. El único puntero de la interfaz es texto de solo lectura terminado en cero: reutiliza el buffer Serial sin copias ni asignaciones dinámicas y conserva el rechazo de nullptr.

## Módulo SensorUltrasonico

- `SensorUltrasonico(pinTrig, pinEcho)`: guarda los dos GPIO sin acceder al hardware. En main se instancia con `(5, 18)`.
- `iniciar()`: prepara TRIG en LOW, lo configura como salida y configura ECHO como entrada.
- `medir()`: mantiene TRIG bajo durante 2 µs, genera un pulso HIGH de 10 µs, vuelve a LOW y mide ECHO con `pulseIn(pinEcho, HIGH, 30000UL)`. Devuelve un `Medicion` con `distanciaCm` y `valida`.

El cálculo es `distancia_cm = duración_ECHO_µs × 0,034 / 2`. Se usa una velocidad del sonido aproximada de 340 m/s, expresada como 0,034 cm/µs, y se divide entre dos por el trayecto de ida y vuelta. El rango nominal aceptado por software es de 2 a 400 cm; no constituye un rango ni una exactitud verificados para nuestro módulo. El pulso, rango y cálculo se basan en la [ficha HC-SR04 de ELECFREAKS alojada por SparkFun](https://cdn.sparkfun.com/datasheets/Sensors/Proximity/HCSR04.pdf).

Si `pulseIn()` devuelve cero, no se recibió un pulso completo dentro del timeout. También se rechazan distancias calculadas fuera de 2–400 cm. En ambos casos el resultado es `valida=false` y `distanciaCm=NaN`: se debe comprobar valida antes de usar la distancia. Serial muestra una medición inválida sin imprimir NaN ni sustituirla por 0 cm o por una lectura anterior. No hay filtros, promedios ni compensación por temperatura. Véase [pulseIn() en Arduino](https://docs.arduino.cc/language-reference/en/functions/advanced-io/pulseIn/).

Cada vuelta de loop procesa hasta 32 bytes pendientes de Serial y después comprueba si transcurrieron 500 ms desde el inicio de la última lectura. La resta sin signo de millis() tolera su desbordamiento. El timestamp se guarda antes de medir para evitar añadir la duración del eco al intervalo; si hay retrasos, no se lanzan ráfagas para recuperar mediciones atrasadas. Los 500 ms también respetan el intervalo de más de 60 ms indicado en la ficha.

`pulseIn()` es bloqueante, con presupuesto nominal de 30 ms en el Arduino-ESP32 instalado, más el pulso de activación y la sobrecarga de ejecución. Durante ese breve periodo los bytes Serial se reciben en el buffer del framework y se procesan al volver al bucle. No se espera 500 ms con delay() ni se deshabilitan interrupciones. No es una implementación completamente asíncrona ni se garantiza latencia estricta con tráfico continuo. El sensor nunca modifica los LEDs.

## Conexión WiFi y credenciales locales

La implementación utiliza únicamente `WiFi.h` del Arduino-ESP32 instalado. Los métodos públicos de `ConexionWifi` son:

- `iniciar()`: valida la configuración y lanza un intento sin esperar a obtener conexión. Se llama una vez desde setup(), después de inicializar Serial y los periféricos.
- `actualizar()`: se llama en cada vuelta de loop(). Detecta los cambios observados de conexión, muestra la IP al conectar y programa los intentos siguientes.
- `estaConectada()`: consulta si el framework indica `WL_CONNECTED`. No comprueba acceso a Internet ni al broker.

Los intentos comienzan al iniciar y, si sigue sin conexión, cada 15 000 ms mediante una resta sin signo de millis(). Al detectar la pérdida de una conexión establecida, el contador se reinicia y se espera 15 s antes del siguiente intento. Cada intento cancela el anterior y vuelve a llamar a WiFi.begin(). Se desactiva la reconexión automática continua del framework para que la clase supervise el intervalo; el controlador puede realizar su propio reintento inicial interno. No se añade while de espera, delay(), escaneo síncrono ni waitForConnectResult(). Las llamadas del controlador tienen sobrecarga, por lo que no se declara latencia estricta sin medirla en hardware.

Solo se informa del inicio, de cada reintento espaciado, de errores al iniciar un intento y de los cambios de conexión observados. Una conexión estable no genera mensajes WiFi en cada vuelta. Los mensajes propios no muestran SSID, contraseña ni dirección MAC; sí muestran la IP local solicitada. La supervisión por consulta puede no registrar una desconexión muy breve ocurrida entre dos vueltas de loop().

Para configurar la red:

1. Copiar manualmente `include/ConfiguracionWifi.ejemplo.h` como `include/ConfiguracionWifi.h`, si la copia local aún no existe.
2. Editar únicamente la copia local: completar `NombreRedWifi` con el nombre de la red de 2,4 GHz y `ClaveRedWifi` con su contraseña. Mantener nombres, tipos y comillas de las constantes. La clave solo puede estar vacía para una red abierta, cuya autenticación se permite expresamente en ese caso.
3. Verificar la exclusión ejecutando `git check-ignore -v include/ConfiguracionWifi.h`. No añadir esa copia a Git mediante opciones de forzado.
4. Compilar y, cuando se vaya a probar en la placa, ejecutar personalmente Upload. Cambiar el archivo local requiere recompilar y cargar de nuevo.

No se crea automáticamente la copia local ni se incluyen credenciales reales. Si no existe, main incluye la plantilla vacía: compila, informa una sola vez que falta configuración y deja WiFi deshabilitado. LEDs, sensor y comandos siguen funcionando. Una configuración con nombre vacío, SSID de más de 32 bytes, clave de más de 64 bytes o punteros nulos también se rechaza sin imprimir sus valores. La autenticación restante la resuelve el framework; una clave incorrecta puede provocar reintentos sin conexión.

WiFi.persistent(false) evita nuevas escrituras de configuración del controlador en NVS. No borra configuraciones anteriores ni cifra las credenciales: al compilar una copia local real, estas quedan incorporadas al firmware. Los archivos de compilación están ignorados en .pio/.

## Prueba de conexión y reconexión WiFi

El equipo confirmó las pruebas WiFi de la versión anterior. Esta secuencia permite repetirlas como regresión; la validación funcional iOS no acredita por sí sola todos estos escenarios:

1. Sin archivo local, compilar y probar la versión con plantilla vacía: debe informar configuración ausente una sola vez, conservar los once comandos y continuar las lecturas aproximadamente cada 500 ms.
2. Configurar una red de 2,4 GHz con autenticación personal o abierta, compilar y cargar cuando el usuario lo decida. Abrir Serial Monitor a 115200 baudios y pulsar EN/RESET. Esperar el mensaje de conexión e IP; una IP no acredita acceso a Internet ni MQTT.
3. Mantener conexión estable y comprobar que no se repite el mensaje de IP constantemente. Ejecutar los once comandos y observar las mediciones mientras está conectada.
4. Apagar el punto de acceso o su radio WiFi. Tras la detección de pérdida, deben aparecer un aviso y reintentos espaciados unos 15 s. Continuar usando LEDs y sensor, sin reiniciar la placa.
5. Volver a habilitar el mismo punto de acceso con las mismas credenciales. Esperar un nuevo intento y la asignación DHCP: debe volver a informar conexión e IP. El tiempo total incluye detección del corte, intervalo de reintento, asociación y DHCP; no se promete recuperación en 15 s exactos.
6. Arrancar con el punto de acceso apagado y habilitarlo después. También probar una contraseña incorrecta en la copia local. En ambos casos el control local debe permanecer operativo; restaurar después la clave correcta y recompilar.

Quedan pendientes la estabilidad y latencia reales durante inicialización/reintentos, el comportamiento de DHCP, alcance y alimentación con la radio activa. No se implementan portales cautivos ni autenticación empresarial; una red universitaria que los requiera necesita otra configuración. El timeout de pulseIn() sigue siendo 30 ms y no se modifica la lógica del sensor. La documentación oficial de referencia es la [API WiFi de Arduino-ESP32](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/wifi.html); también se revisó el código de la versión 2.0.17 instalada.

## Integración MQTT sobre TLS

Se utiliza **256dpi/MQTT 2.5.2**, fijada exactamente en platformio.ini y compilada con Espressif32 7.0.1 / Arduino-ESP32 2.0.17. WiFiClientSecure pertenece al framework, sin otra biblioteca externa. El contrato de tópicos y los once comandos se conserva en [protocolo_mqtt.md](docs/protocolo_mqtt.md).

`ConexionMqtt::iniciar()` configura CA, LWT y callback; `actualizar()` atiende mensajes y prepara/reintenta la conexión cuando hay WiFi. `publicarMedicion()` envía solo la lectura actual, y `solicitarPublicacionEstados()` marca estados pendientes sin publicar desde el callback ni desde el procesador Serial. `estaConectada()` consulta si la sesión terminó de inicializarse. Los módulos anteriores no se modifican.

Completar únicamente `include/ConfiguracionMqtt.h`, ya creado y excluido de Git: host `zffa4f2f.ala.us-east-1.emqxsl.com`, puerto 8883, client ID `equipo08_esp32_01`, usuario previsto `equipo08_esp32` y contraseña real en `ClaveMqtt`. La clave entregada queda vacía: así MQTT se deshabilita y el control local permanece activo. La plantilla versionable es `include/ConfiguracionMqtt.ejemplo.h`; un clon sin copia privada también compila con MQTT deshabilitado. No imprimir, versionar ni forzar la inclusión de la copia privada. Verificar con `git check-ignore -v include/ConfiguracionMqtt.h`.

Se utiliza exactamente `certificados/emqxsl-ca.crt`, aunque el nombre mencionado inicialmente en la solicitud era `ca_emqx.crt`. El archivo encontrado es PEM y declara DigiCert Global Root G2, vigencia 2013-08-01 a 2038-01-15. `board_build.embed_txtfiles` incorpora su contenido original terminado en cero; `setCACert()` lo utiliza para validar TLS. No se usa setInsecure() ni se desactiva la validación. Su formato y vigencia no acreditan por sí solos la cadena presentada por el endpoint.

NTP se solicita sin bucle de espera; se consulta time() en cada vuelta durante hasta 10 s. Sin hora válida no se intenta TLS. Los fallos aplazan nuevos intentos 30 s. TCP/escrituras tienen timeout nominal de 1 s, handshake TLS de 3 s y operaciones MQTT de 1 s; estos plazos no forman un límite global de conexión. **Las llamadas síncronas de TLS/MQTT y DNS pueden pausar las mediciones y los comandos.** En el core instalado, DNS incluye esperas internas de hasta 16 s y 15 s; no se promete una cadencia estricta de 500 ms durante fallos de red. Entre intentos sigue ejecutándose el control local. No hay espera indefinida ni recuperación de lecturas atrasadas.

Compilación final con clave MQTT vacía: **SUCCESS**, salida 0, 8,50 s; RAM estática 46 392 bytes (14,2 %), flash 905 685 bytes (69,1 %). También se compiló y enlazó la ruta habilitada con una clave ficticia, sin ejecutar firmware: SUCCESS, 8,64 s; flash 909 197 bytes (69,4 %). Se comprobó la incorporación de la CA completa y su hash sin cambios; después se restauró la clave vacía y se recompiló. La RAM informada no incluye el máximo de heap utilizado durante un handshake real.

La guía de [pruebas con MQTT.fx y reconexión](docs/pruebas_mqtt.md) explica cómo comprobar esos escenarios. Los resultados funcionales posteriores desde el iPhone se registran en la [guía iOS](docs/configuracion_ios.md). La actualización documental de la iteración 6 no modifica firmware ni ejecuta cargas o commits.

## Compilar y cargar cuando el circuito esté listo

Desde una terminal con PlatformIO disponible y situada en la raíz del proyecto:

```powershell
pio run -e esp32doit-devkit-v1
pio run -e esp32doit-devkit-v1 --target upload
pio device monitor -e esp32doit-devkit-v1
```

La segunda orden realiza la carga y debe ejecutarla el usuario cuando haya revisado el circuito y conectado el USB de datos. También puede usar PlatformIO: Upload y PlatformIO: Serial Monitor en VS Code. Si hay varios puertos, elegir el real mediante `--upload-port COMx` al cargar y `--port COMx` al abrir el monitor; COMx es un marcador, no un puerto detectado.

Si `pio` no está en PATH, en este equipo el ejecutable está en `%USERPROFILE%\.platformio\penv\Scripts\platformio.exe`. En PowerShell puede invocarse con `& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe"` seguido de los mismos argumentos.

Los resultados de compilación de la sección MQTT corresponden a esa implementación. La validación física posterior desde el iPhone fue realizada y confirmada por el equipo; esta actualización de documentación no requiere recompilar ni cargar firmware.

Los archivos de ControlLeds, SensorUltrasonico y ConexionWifi permanecen intactos. No hay una suite automatizada implementada en test/; la revisión estructural y las compilaciones no sustituyen las pruebas físicas de la integración MQTT.

## Prueba física del sensor desde PlatformIO

1. Con la alimentación desconectada, revisar el montaje existente: HC-SR04 a 5 V, masa común, TRIG en GPIO5 y ECHO en GPIO18 después del divisor. Verificar el esquema y nivel eléctrico del divisor previo; no se cambia su disposición desde el firmware.
2. Cuando el circuito esté listo, conectar el USB de datos y ejecutar la carga indicada arriba, o PlatformIO: Upload. Esa operación la realiza el usuario; no se ha ejecutado durante el desarrollo de esta iteración.
3. Abrir PlatformIO: Serial Monitor a 115200 baudios y pulsar EN/RESET. Deben mostrarse el mensaje de inicio y, aproximadamente cada 500 ms, `Sensor: distancia=... cm` o `Sensor: medicion invalida (sin eco/timeout o fuera de 2-400 cm).` Estas son salidas esperadas, no lecturas obtenidas durante el desarrollo.
4. Usar un objeto plano frente al sensor y una cinta métrica para comparar, por ejemplo, 10, 30 y 100 cm desde la cara de los transductores. Registrar lectura, referencia y error; todavía no se declara exactitud física ni se aplica calibración.
5. Retirar o desviar el objeto para buscar ausencia de eco y verificar la respuesta inválida cuando no se complete un pulso a tiempo. Otros objetos pueden seguir reflejando el sonido: retirar un objetivo no garantiza por sí solo un timeout. Una lectura fuera del rango aceptado también se informa como inválida.
6. Mientras aparecen lecturas, enviar los once comandos de la tabla siguiente y comprobar su respuesta. Repetir `todos:on`, `solo:rojo`, `solo:amarillo`, `solo:verde` y `todos:off`; mover el objeto sin enviar comandos y verificar que los LEDs no cambien por la distancia.
7. Observar la cadencia aproximada de dos intentos de medición por segundo y la continuidad de los comandos, también cuando se informa invalidez. Registrar reinicios, bloqueos, errores y latencia perceptible. Esta secuencia comprueba el sensor; completar después las pruebas MQTT de la guía enlazada.

## Prueba manual por Serial

1. Abrir el monitor a 115200 baudios. Para ver el mensaje inicial, pulsar EN/RESET con el monitor abierto. Los tres LEDs deben quedar apagados después de inicializarse.
2. Escribir cada comando exacto y pulsar Enter. En otros monitores seleccionar LF, CR o CRLF como fin de línea. No incluir comillas ni espacios adicionales.
3. Enviar las once órdenes de esta tabla en orden y repetir cada una dos veces. El equipo ya probó físicamente el comportamiento anterior; esta secuencia permite comprobar la regresión del código refactorizado.

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

Para comprobar el encendido general durante las mediciones, enviar `todos:off`, `todos:on`, `todos:on` y `todos:off`, una línea por orden. Las dos ejecuciones consecutivas de `todos:on` deben mostrar `Estado: rojo=on amarillo=on verde=on`, sin apagar ni invertir ningún LED. La última orden debe devolver los tres a off.

Probar `rojo:toggle`, `Rojo:on`, un comando con espacios y una línea de 32 o más bytes ASCII: deben rechazarse sin cambiar los estados. El receptor guarda como máximo 31 bytes y descarta toda línea con exceso de longitud o bytes de control, sin ejecutar su prefijo. En esos errores se imprime solo el fragmento guardado y se informa el descarte. La siguiente línea válida debe procesarse normalmente.

## Límites de esta etapa

- El equipo confirmó las pruebas físicas de LEDs, sensor, WiFi y la integración funcional iOS de la iteración 6. No se registran valores medidos de exactitud ni latencia.
- Los estados mostrados son estados lógicos del programa. No detectan un LED invertido, dañado o desconectado.
- Las escrituras sobre los tres GPIO son consecutivas, no una conmutación eléctrica simultánea y atómica.
- Los comandos se aplican al recibir un fin de línea; no hay timeout para una línea incompleta. No se utiliza delay() ni lectura serie con espera de línea. Solo se usan delayMicroseconds(2) y delayMicroseconds(10) para TRIG, además de pulseIn() con timeout explícito de 30 ms.
- Una medición válida solo significa pulso recibido dentro del timeout y distancia calculada dentro del rango nominal; no garantiza un eco del objeto deseado ni la exactitud de la medida. Se usa velocidad del sonido fija, sin filtrado ni compensación térmica.
- No se admiten caracteres de control dentro del comando, incluidos retroceso y tabulación. El filtro `send_on_enter` agrupa la entrada hasta Enter, pero no elimina los bytes de retroceso: si se comete un error, enviar esa línea para descartarla y volver a escribir el comando completo.
- La consola está pensada para pruebas manuales. Un flujo continuo de mensajes puede saturar la salida serie.
- RF4 y RF5 están comprobados funcionalmente. Queda pendiente registrar valores medibles de los atributos no funcionales de estabilidad, exactitud, respuesta móvil, publicación y reconexión exigidos para la integración final.
- Los Switches iOS pueden mostrar un estado desactualizado al no suscribirse a los estados publicados por el ESP32. La prueba específica mediante datos móviles no fue realizada.
