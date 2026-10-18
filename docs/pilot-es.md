# Conecte su controlador DJI con OpenUTM

[English](pilot-en.md) · [Inicio del proyecto](../README.md)

**La conexión todavía necesita alojamiento y validación en un controlador real.** El coordinador debe confirmar que está lista antes de entregar el enlace definitivo. Una vista previa del sitio no conecta una aeronave.

## Antes de empezar

Necesita:

- Aeronave y controlador aprobados por el laboratorio, con **DJI Pilot 2**. Los primeros objetivos de Panamá son Mavic 3 Enterprise y Matrice 400 con sus controladores correctos.
- Internet en el controlador.
- La **dirección del sitio de conexión** proporcionada por el coordinador.
- El **código privado asignado a este controlador**.

Esta ruta no requiere APK, cuenta de desarrollador ni comandos. El código no es su contraseña Passport y no identifica al piloto. Complete por separado el acceso del piloto, la planificación y los permisos del laboratorio.

## 1. Abra la página

1. Siga la preparación normal del laboratorio, con la aeronave en tierra.
2. Abra DJI Pilot 2.
3. En su página inicial, abra **Cloud Service → Open Platforms**. Los nombres pueden variar según la versión; consulte al coordinador si difieren.
4. Introduzca la dirección HTTPS exacta del laboratorio.
5. Compruebe la dirección y que no haya aviso de certificado. Si algo no coincide, deténgase y consulte al coordinador.
6. Elija **Español** o **English** en la parte superior.

Si aparece **Abra esta página en DJI Pilot 2**, está usando un navegador normal. Vuelva a Pilot 2 y ábrala desde **Open Platforms**.

## 2. Introduzca el código

1. Escriba el código privado en **Código de conexión**.
2. Toque **Conectar telemetría →**.
3. Espere mientras Pilot 2 verifica la licencia y conecta.

No comparta el código ni lo incluya en capturas. Si corresponde a otro controlador, pida el correcto; no seleccione otro piloto o aeronave para eludir el problema.

## 3. Compruebe los tres estados

| Estado | Qué significa |
|---|---|
| **Conexión del controlador** | **Conectado**: Pilot 2 comunica que está conectado al servicio de telemetría. |
| **Telemetría de la aeronave** | **Conectado**: el adaptador recibió una posición reciente de una aeronave registrada. |
| **Flight Blender** | **API: aceptado**: la API aceptó una muestra reciente. El laboratorio debe comprobar también el registro/panel posterior. |

Revise **Última muestra de la aeronave**, **Última aceptación de la API** y **Pendientes de envío**. Los estados **Sin configurar**, **Sin datos recientes**, **En espera** o **Estado no disponible** necesitan revisión; no indican que todo esté listo.

No necesita despegar ni arrancar motores para comprobar la conexión. La posición puede depender de la preparación normal y de la recepción GPS. Siga las instrucciones de comprobación en tierra del coordinador.

## 4. Siga el procedimiento operativo del laboratorio

La conexión solo comparte telemetría. No crea declaraciones, autoriza vuelos, selecciona pilotos ni sube fotografías. El coordinador debe explicar el proceso separado de planificación, identidad y permisos antes de operar.

Pilot 2 sigue siendo la aplicación de vuelo. El adaptador no solicita control remoto; la página no debe pedir activar autoridad de control de vuelo en la nube. Consulte cualquier aviso inesperado con el coordinador.

Mantenga internet cuando se requiera seguimiento en directo. Una interrupción puede dejar huecos en la trayectoria; el servicio no garantiza recuperar después posiciones que el controlador nunca transmitió.

## Si algo falla

| Problema | Qué hacer |
|---|---|
| No aparece Open Platforms | Confirme controlador, versión de Pilot 2 y combinación aprobada. |
| No se verifica la licencia | Pida revisar la aplicación DJI y la versión del controlador. No necesita reinstalar un APK para esta conexión. |
| Código inválido o de otro controlador | Compruebe el código completo y pida una corrección si corresponde. |
| Demasiados intentos | Espere un minuto y vuelva a intentar. Consulte qué código usar. |
| Controlador conectado, sin telemetría | Compruebe encendido/enlace, registro de la combinación y GPS en tierra. |
| Blender sin configurar o envío pendiente | Pida revisar credenciales del servidor y servicio. No cambie fechas ni recree operaciones para resolverlo. |
| La sesión terminó | Introduzca de nuevo el código del controlador; no es su cuenta Passport. |
| Se pierde internet o el estado | Considere interrumpido el seguimiento y siga el procedimiento local. No cambie de aplicación de control durante el vuelo. |

Informe del paso, mensaje exacto, modelos, versión de Pilot y fecha/hora/zona horaria por el canal privado aprobado. No envíe códigos de conexión, contraseñas ni credenciales.

Para terminar la conexión en tierra, use **Desconectar este controlador**. Si se pierde o comparte el equipo, el coordinador debe gestionar la revocación; cerrar la página no revoca por sí solo las credenciales MQTT.
