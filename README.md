# TAIICO CRM

Sistema de gestión modular para TAIICO Life Advisors, construido con Next.js y TypeScript.

## Requisitos Previos

- Node.js (v18 o superior)
- Acceso a la carpeta de Google Drive donde residen los archivos de Excel.

## Instalación

1. Navega a la carpeta del proyecto:
   ```bash
   cd "taiico-crm"
   ```

2. Instala las dependencias:
   ```bash
   npm install
   ```

## Ejecución

Para iniciar la aplicación en modo desarrollo:

```bash
npm run dev
```

Abre [http://localhost:3000](http://localhost:3000) en tu navegador.

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

## Lanzador de macOS (macOS Launcher)

Hemos implementado un lanzador nativo de macOS para que los usuarios puedan iniciar el backend de FastAPI, el frontend de Next.js y abrir el navegador de manera automática con un solo click.

### Estructura de Scripts
- `scripts/start-crm.sh`: El script que se encarga de verificar el montaje de Google Drive, auto-inicializar el entorno virtual de Python, instalar dependencias faltantes tanto del frontend como del backend, arrancar ambos servidores en segundo plano y abrir el navegador en `http://localhost:3000`.
- `scripts/build-macos-app.sh`: Script para empaquetar el lanzador en una aplicación de macOS (`TAIICO CRM.app`) con el logo oficial como icono de la aplicación.

### Cómo construir la app (.app)
Para regenerar la aplicación localmente, ejecute el siguiente comando en la raíz del proyecto:
```bash
./scripts/build-macos-app.sh
```
Esto creará el paquete ejecutable en `dist/TAIICO CRM.app`.

### Cómo instalarla en `/Applications`
1. Genere el paquete ejecutando el script de construcción anterior.
2. Copie o arrastre el archivo `TAIICO CRM.app` desde la carpeta `dist/` a su directorio de aplicaciones de macOS (`/Applications`).
3. La aplicación buscará de manera automática el repositorio en su carpeta de Google Drive (`~/Library/CloudStorage/GoogleDrive-...`) e iniciará el sistema normalmente.

### Cómo ver logs
El lanzador registra todas sus operaciones y las salidas de los servidores en el directorio de logs estándar de macOS. Puede revisarlos usando la Consola de macOS o abriendo los archivos de log directamente:
- **Log del Lanzador principal**: `~/Library/Logs/TAIICO CRM/launcher.log`
- **Log del Servidor Backend**: `~/Library/Logs/TAIICO CRM/backend.log`
- **Log del Servidor Frontend**: `~/Library/Logs/TAIICO CRM/frontend.log`

Para monitorear los logs en vivo desde la terminal, ejecute:
```bash
tail -f ~/Library/Logs/TAIICO/launcher.log
```

### Cómo cambiar el puerto o comando de arranque
- **Cambio de puertos**: Si desea cambiar los puertos por defecto (7777 para backend o 3000 para frontend), edite el archivo [start-crm.sh](file:///Users/albertoalfaromendoza/Library/CloudStorage/GoogleDrive-alberto.alfaro@taiico.com/Shared%20drives/Administrativos/2025%20-%20Antigravity%20CRM/taiico-crm/scripts/start-crm.sh) y configure los puertos deseados, asegurándose de actualizar también las URLs correspondientes en la configuración del frontend y backend.
- **Cambio de comandos**: Para modificar la forma en que inician los servidores (por ejemplo, cambiar el comando de desarrollo de Next.js `npm run dev` a uno de producción como `npm run start`), edite las secciones correspondientes en [start-crm.sh](file:///Users/albertoalfaromendoza/Library/CloudStorage/GoogleDrive-alberto.alfaro@taiico.com/Shared%20drives/Administrativos/2025%20-%20Antigravity%20CRM/taiico-crm/scripts/start-crm.sh).
