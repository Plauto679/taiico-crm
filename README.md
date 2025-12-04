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
