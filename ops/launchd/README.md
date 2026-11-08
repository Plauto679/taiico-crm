# Servicios permanentes del CRM en macOS

Estos LaunchAgents mantienen activos FastAPI y Next.js bajo el usuario operativo
del Mac mini. Ambos escuchan exclusivamente en loopback; Cloudflare Tunnel es el
único punto público de entrada.

Los servicios requieren una sesión de macOS iniciada para conservar acceso a
Google Drive y a las credenciales locales del usuario.

El agente `com.taiico.crm.keep-awake` ejecuta `caffeinate -is` para impedir
la suspensión automática del Mac servidor mientras la sesión esté abierta.
Permite que la pantalla se apague. No reemplaza el inicio de sesión necesario
después de reiniciar el equipo.

Como el repositorio vive dentro de `Desktop`, macOS debe conceder acceso total
al disco a los ejecutables usados por los agentes:

- `/opt/homebrew/bin/node`
- `/opt/homebrew/opt/python@3.13/Frameworks/Python.framework/Versions/3.13/Resources/Python.app`

Sin ese permiso, `launchd` puede cargar los agentes pero Node o Python no podrán
leer el proyecto. El permiso se administra en **Configuración del Sistema >
Privacidad y seguridad > Acceso total al disco**.

## Instalación

```bash
mkdir -p .runtime/logs ~/Library/LaunchAgents
cp ops/launchd/com.taiico.crm.backend.plist ~/Library/LaunchAgents/
cp ops/launchd/com.taiico.crm.keep-awake.plist ~/Library/LaunchAgents/
cp ops/launchd/com.taiico.crm.frontend.plist ~/Library/LaunchAgents/
cp ops/launchd/com.taiico.crm.pending-report.plist ~/Library/LaunchAgents/
cp ops/launchd/com.taiico.crm.agent-license-report.plist ~/Library/LaunchAgents/
cp ops/launchd/com.taiico.crm.renewal-agent.plist ~/Library/LaunchAgents/
cp ops/launchd/com.taiico.crm.database-backups.plist ~/Library/LaunchAgents/
cp ops/launchd/com.taiico.crm.agent-birthday-report.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.taiico.crm.backend.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.taiico.crm.keep-awake.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.taiico.crm.frontend.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.taiico.crm.pending-report.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.taiico.crm.agent-license-report.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.taiico.crm.renewal-agent.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.taiico.crm.database-backups.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.taiico.crm.agent-birthday-report.plist
```

## Estado

```bash
launchctl print gui/$(id -u)/com.taiico.crm.backend
launchctl print gui/$(id -u)/com.taiico.crm.frontend
launchctl print gui/$(id -u)/com.taiico.crm.pending-report
launchctl print gui/$(id -u)/com.taiico.crm.agent-license-report
launchctl print gui/$(id -u)/com.taiico.crm.renewal-agent
launchctl print gui/$(id -u)/com.taiico.crm.database-backups
launchctl print gui/$(id -u)/com.taiico.crm.agent-birthday-report
```

## Reinicio después de desplegar cambios

Antes de reiniciar el frontend, ejecutar `npm run build`.

```bash
launchctl kickstart -k gui/$(id -u)/com.taiico.crm.backend
launchctl kickstart -k gui/$(id -u)/com.taiico.crm.frontend
launchctl kickstart -k gui/$(id -u)/com.taiico.crm.pending-report
launchctl kickstart -k gui/$(id -u)/com.taiico.crm.agent-license-report
launchctl kickstart -k gui/$(id -u)/com.taiico.crm.renewal-agent
launchctl kickstart -k gui/$(id -u)/com.taiico.crm.database-backups
launchctl kickstart -k gui/$(id -u)/com.taiico.crm.agent-birthday-report
```

Los logs se escriben en `.runtime/logs/` y no se versionan.

## Concurrencia de la base local

La recuperación del 5 de octubre de 2026 activó `journal_mode=WAL` en la base
SQLite local, tras crear un respaldo consistente. Esta opción persiste en el
archivo y permite consultas mientras la ingestión de renovaciones escribe.
El backend espera hasta 30 segundos por un bloqueo de escritura. La migración
`20261005_0020` añade índices para las búsquedas repetidas por RFC normalizado
y por póliza/fecha de renovación.

Al restaurar una base anterior, verificar su modo de diario antes de reanudar
las tareas. Los respaldos deben usar la API de SQLite (`Connection.backup`),
como el job de respaldos existente: copiar sólo el archivo `.db` mientras hay
escrituras en WAL no garantiza un respaldo completo.

El agente `com.taiico.crm.database-backups` revisa cada cinco minutos si ya existe
el respaldo del día en horario de Ciudad de México. Crea una subcarpeta por cada
base canónica de Drive y otra para la base SQL local, genera como máximo una copia
diaria con prefijo `YYYY-MM-DD` y envía a la papelera únicamente sus propias copias
cuando salen de la ventana de retención de 30 días. Al iniciar después de una
interrupción crea el respaldo faltante del día automáticamente.

## API supervisada de renovaciones

La API de operación remota usa un token de servicio independiente de la sesión
web. Antes de reiniciar el backend, configura en `backend/.env` un valor aleatorio
largo para `RENEWAL_AGENT_API_TOKEN`. El token se envía exclusivamente mediante
el encabezado `Authorization: Bearer ...`; nunca debe incluirse en la URL ni
confirmarse en Git.

La ruta pública pasa por el rewrite existente de Next.js:

```text
GET  /api/renewal-agent/candidates
POST /api/renewal-agent/tasks/{task_id}/claim
POST /api/renewal-agent/tasks/{task_id}/collection-check
POST /api/renewal-agent/tasks/{task_id}/approve
POST /api/renewal-agent/tasks/{task_id}/review-required
```

Esta API no ejecuta descargas ni envíos. Reserva una tarea, registra la consulta
de cobranza y exige que `Pagado Hasta` sea igual o posterior a `FFINVIG` antes
de permitir la aprobación humana. El alcance está fijado en el servidor a todas
las pólizas MetLife GMM con vencimiento dentro de los siguientes 45 días.

## Alcance

Estos agentes mantienen disponibles la interfaz web y la API. El agente
`com.taiico.crm.pending-report` comprueba cada cinco minutos la hora de
`America/Mexico_City` y envía el informe una sola vez por día después de las
19:00.

El agente `com.taiico.crm.agent-license-report` comprueba cada cinco minutos la
fecha y hora de Ciudad de México. Sólo el día 1 de cada mes, después de las
10:00, envía a los mismos destinatarios del informe de Pendientes la lista de
agentes cuya cédula vence entre ese día y los tres meses calendario siguientes.
Un archivo de estado evita duplicar el correo durante el mismo mes.

El agente `com.taiico.crm.agent-birthday-report` comprueba cada cinco minutos la
agenda semanal. Los lunes después de las 08:00, hora de Ciudad de México, envía
el resumen de cumpleaños de los próximos 15 días a la distribución interna y
una versión filtrada para cada promotoría configurada. Un estado por semana y
por informe evita envíos duplicados.

El agente `com.taiico.crm.renewal-agent` realiza la misma comprobación y comienza
una sola corrida diaria de renovaciones MetLife GMM después de las 07:00 de
Ciudad de México. Incluye pendientes vencidos que continúen en cola y pólizas
con vencimiento durante los siguientes 45 días. Las claves TAIICO `16200`,
`18412`, `73640` y `16190` (Isis Karina Cervera Garza) se envían al cliente; las demás se envían exclusivamente al
`Correo_Personal` inequívoco del agente, con copia a Alberto. La fecha de inicio se guarda
antes de procesar para impedir reintentos automáticos y correos duplicados si
la corrida falla. WhatsApp está desactivado en este job; sólo se realizan los
correos autorizados y se registra el paso como omitido.

## Plauto: buscador y asistente del CRM

Plauto usa el pingüino original de Marketing Taiico. El botón flotante abre un
panel que permanece en memoria durante la sesión; no guarda conversaciones en
el navegador. Se oculta en login y páginas públicas. La búsqueda funciona sin IA.

Configuración en `backend/.env`:

- `PLAUTO_ENABLED=true` activa el widget para usuarios con lectura de Clientes.
- `PLAUTO_LEGACY_DRIVE_ROOT_ID=1fT7OSoCNrw510tLbCsdWPAONuDRrMa1g` habilita
  **Administrativos / Clientes de los agentes** y sus descendientes. No es una
  búsqueda exhaustiva de toda la unidad Administrativos. Marketing, RRHH y otros
  archivos administrativos quedan fuera de este árbol.
- El Drive nuevo reutiliza la configuración de `CLIENT_FOLDERS_PARENT_ID`.
- Más adelante, configurar `OPENAI_API_KEY` y `PLAUTO_MODEL` en el servidor y
  reiniciar el backend habilita conversación mediante Responses API. No colocar
  claves en variables `NEXT_PUBLIC_*`, en el código ni en el chat.

Sin motor, permite localizar clientes del CRM por nombre/RFC/póliza, listar
archivos de su carpeta vinculada y, para administración central, localizar
carpetas antiguas por nombre. Los enlaces abren la fuente original en Drive.
Los resultados acotados indican cuando son parciales. No hay indexación global
por contenido ni OCR. La lectura de documentos preparada para el motor admite
PDF con texto, Google Docs y archivos de texto hasta 4 MB (20 páginas/18.000
caracteres de texto). No interpreta archivos escaneados sin texto.

Cada consulta vuelve a aplicar los permisos del CRM. Los expedientes completos
no se exponen a agentes, porque pueden incluir pólizas de otros agentes. Las
carpetas antiguas sin asociación a un cliente requieren administración central;
los demás administrativos sólo consultan carpetas asociadas a su alcance.
Para ampliar esta cobertura se deben vincular explícitamente las carpetas a
clientes, sin deducir permisos por similitud de nombres.

La única acción preparada para el motor es actualizar correo/teléfono del
cliente: exige permiso de operación, muestra antes/después, caduca a los 15
minutos y requiere confirmación. Vuelve a comprobar permisos, usuario y datos
actuales al guardar; cambio y auditoría se confirman en la misma transacción.
No incluye envíos, pagos ni decisiones de cobertura. La auditoría general de
consultas registra longitud y modo, no el texto de la conversación. Las
propuestas guardan los datos de contacto necesarios para confirmar/auditar.

Despliegue: instalar requisitos, respaldar SQLite con `Connection.backup`,
ejecutar `alembic upgrade head` (migración `20261009_0021`), compilar frontend y
reiniciar únicamente backend/frontend. Para desactivar, `PLAUTO_ENABLED=false`
y reiniciar backend; la migración es aditiva y no requiere eliminar datos.

Validación: `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_plauto.py -q`.

## Formato oficial de Mesa de control

`com.taiico.crm.mesa-forms` comprueba diariamente a las 10:15 (hora del servidor)
el catálogo y la solicitud oficial de MédicaLife Familiar. No envía mensajes ni
activa versiones desconocidas: un cambio bloquea el llenado hasta revisar el mapeo.
Se instala como los demás LaunchAgents y registra únicamente el estado de la fuente.
El piloto de Mesa requiere `MESA_OWNER_USERNAME`; ver `docs/MESA_CONTROL.md`.
