# Servicios permanentes del CRM en macOS

Estos LaunchAgents mantienen activos FastAPI y Next.js bajo el usuario operativo
del Mac mini. Ambos escuchan exclusivamente en loopback; Cloudflare Tunnel es el
único punto público de entrada.

Los servicios requieren una sesión de macOS iniciada para conservar acceso a
Google Drive y a las credenciales locales del usuario.

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
cp ops/launchd/com.taiico.crm.frontend.plist ~/Library/LaunchAgents/
cp ops/launchd/com.taiico.crm.pending-report.plist ~/Library/LaunchAgents/
cp ops/launchd/com.taiico.crm.renewal-agent.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.taiico.crm.backend.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.taiico.crm.frontend.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.taiico.crm.pending-report.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.taiico.crm.renewal-agent.plist
```

## Estado

```bash
launchctl print gui/$(id -u)/com.taiico.crm.backend
launchctl print gui/$(id -u)/com.taiico.crm.frontend
launchctl print gui/$(id -u)/com.taiico.crm.pending-report
launchctl print gui/$(id -u)/com.taiico.crm.renewal-agent
```

## Reinicio después de desplegar cambios

Antes de reiniciar el frontend, ejecutar `npm run build`.

```bash
launchctl kickstart -k gui/$(id -u)/com.taiico.crm.backend
launchctl kickstart -k gui/$(id -u)/com.taiico.crm.frontend
launchctl kickstart -k gui/$(id -u)/com.taiico.crm.pending-report
launchctl kickstart -k gui/$(id -u)/com.taiico.crm.renewal-agent
```

Los logs se escriben en `.runtime/logs/` y no se versionan.

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

Esta primera versión no ejecuta descargas ni envíos. Reserva una tarea, registra
la consulta de cobranza y exige que `Pagado Hasta` sea igual o posterior a
`FFINVIG` antes de permitir la aprobación humana. El alcance está fijado en el
servidor a MetLife GMM y a los agentes TAIICO `16200`, `18412` y `73640`.

## Alcance

Estos agentes mantienen disponibles la interfaz web y la API. El agente
`com.taiico.crm.pending-report` comprueba cada cinco minutos la hora de
`America/Mexico_City` y envía el informe una sola vez por día después de las
19:00.

El agente `com.taiico.crm.renewal-agent` realiza la misma comprobación y comienza
una sola corrida diaria de renovaciones MetLife GMM después de las 09:00 de
Ciudad de México. Incluye pendientes vencidos que continúen en cola y pólizas
con vencimiento durante los siguientes 30 días. La fecha de inicio se guarda
antes de procesar para impedir reintentos automáticos y correos duplicados si
la corrida falla. WhatsApp está desactivado en este job; sólo se realizan los
correos autorizados y se registra el paso como omitido.
