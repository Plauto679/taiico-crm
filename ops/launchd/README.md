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
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.taiico.crm.backend.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.taiico.crm.frontend.plist
```

## Estado

```bash
launchctl print gui/$(id -u)/com.taiico.crm.backend
launchctl print gui/$(id -u)/com.taiico.crm.frontend
```

## Reinicio después de desplegar cambios

Antes de reiniciar el frontend, ejecutar `npm run build`.

```bash
launchctl kickstart -k gui/$(id -u)/com.taiico.crm.backend
launchctl kickstart -k gui/$(id -u)/com.taiico.crm.frontend
```

Los logs se escriben en `.runtime/logs/` y no se versionan.

## Alcance

Estos agentes mantienen disponibles la interfaz web y la API. No programan la
ejecución diaria del agente de renovaciones. Esa agenda debe instalarse y
validarse por separado.
