# TAIICO CRM

Sistema de gestión modular para TAIICO Life Advisors.

## Stack Detectado

- Frontend: Next.js 16, React 19 y TypeScript.
- Backend: FastAPI con Python 3.
- Base local: SQLite por defecto en `backend/.env.example`.
- Puertos locales: frontend `http://localhost:3000`, backend `http://localhost:7777`.
- Dependencias frontend: `npm install`.
- Dependencias backend: `python3 -m venv backend/.venv` y `pip install -r backend/requirements.txt`.
- Variables locales: `backend/.env.example`. El launcher crea `backend/.env` desde ese ejemplo si no existe.
- Datos: el CRM depende de archivos Excel en Google Drive, ubicados en carpetas hermanas del repo como `Bases de cobranza y comisiones`, `Relaciones de cartera`, `Fechas de emision de Polizas y renovaciones`, `Correos de los clientes` y `Users`.

## Requisitos Previos

- macOS.
- Node.js 18 o superior con `npm`.
- Python 3.
- Google Drive para escritorio montado y sincronizado con las carpetas de datos del CRM.

## Instalación Manual

Desde la raíz del proyecto:

```bash
npm install
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

## Ejecución Manual

En una terminal:

```bash
source backend/.venv/bin/activate
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 7777 --reload
```

En otra terminal:

```bash
npm run dev
```

Abre [http://localhost:3000](http://localhost:3000) en el navegador.

## Estructura del Proyecto

- `src/app`: Páginas y rutas de la aplicación (App Router).
- `src/components`: Componentes de UI reutilizables.
- `src/lib`: Utilidades, tipos y lógica de acceso a datos.
  - `excel`: Servicios para leer/escribir archivos Excel.
  - `types`: Definiciones de tipos TypeScript para los modelos de datos.
- `src/modules`: Lógica de negocio modular.
  - `cobranza`: Gestión de cobranza Metlife.
  - `renovaciones`: Lógica de detección de renovaciones.
  - `cartera`: Perfiles de clientes y búsqueda.

## Módulos Implementados

### 1. Cobranza
- Carga de archivos "Base de Cobranza" (Vida y GMM).
- Visualización en tablas separadas.
- (Próximamente) Conciliación de pagos.

### 2. Renovaciones
- Detección automática de pólizas próximas a vencer (30, 60, 90 días).
- Unificación de renovaciones de Vida y GMM.

### 3. Cartera
- Búsqueda unificada de clientes por nombre o número de póliza.
- Visualización de perfil básico del cliente.

## Notas Importantes

- La aplicación lee directamente los archivos de Excel de la carpeta de Google Drive.
- Asegúrese de que los archivos existan en las rutas configuradas en `src/lib/config.ts`.

---

## Lanzador de macOS

El repo incluye un launcher nativo para macOS. La app resultante se llama `TAIICO CRM.app` y se puede abrir con doble click desde Finder.

### Scripts

- `scripts/start-crm.sh`: verifica dependencias, valida que Google Drive esté disponible, instala dependencias faltantes, levanta backend y frontend, espera a que respondan los puertos y abre `http://localhost:3000`.
- `scripts/start-crm.command`: wrapper ejecutable por doble click si se quiere correr el launcher sin empaquetar la app.
- `scripts/build-macos-app.sh`: genera `dist/TAIICO CRM.app`.

### Construir la App

Desde la raíz del proyecto:

```bash
./scripts/build-macos-app.sh
```

Esto genera:

```bash
dist/TAIICO CRM.app
../TAIICO CRM.app
```

Cuando el repo está dentro de `2025 - Antigravity CRM/taiico-crm`, la segunda copia queda visible directamente en la carpeta `2025 - Antigravity CRM`.

### Cómo instalarla en `/Applications`

Construye la app y cópiala a `/Applications`:

```bash
./scripts/build-macos-app.sh
cp -R "dist/TAIICO CRM.app" /Applications/
```

La app recuerda la ruta del repo desde donde fue construida. Si mueves el repo después, vuelve a ejecutar `./scripts/build-macos-app.sh` y copia de nuevo la app.

### Cómo ver logs

Los logs se escriben en:

- Launcher: `~/Library/Logs/TAIICO CRM/launcher.log`
- Backend: `~/Library/Logs/TAIICO CRM/backend.log`
- Frontend: `~/Library/Logs/TAIICO CRM/frontend.log`

Para monitorear los logs en vivo desde la terminal, ejecute:

```bash
tail -f "$HOME/Library/Logs/TAIICO CRM/launcher.log"
```

### Cómo cambiar el puerto o comando de arranque

Por defecto:

- Backend: `7777`
- Frontend: `3000`

Puedes cambiar los puertos al ejecutar el launcher:

```bash
TAIICO_CRM_BACKEND_PORT=7777 TAIICO_CRM_FRONTEND_PORT=3000 ./scripts/start-crm.sh
```

Para cambiar el comando de arranque, edita `scripts/start-crm.sh` en las funciones `start_backend` y `start_frontend`.

### Comportamiento Esperado

- Si el CRM ya está corriendo, el launcher solo abre el navegador.
- Si faltan dependencias, las instala automáticamente.
- Si Google Drive no está montado o faltan carpetas de datos, muestra un error claro en la app y deja detalles en `launcher.log`.
- No se guardan secretos en el repo. `backend/.env` está ignorado por git.
