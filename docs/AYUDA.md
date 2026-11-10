# Ayuda del CRM

Disponible en `/ayuda` y en el menú lateral. Incluye buscador por módulo o tarea y 26 guías: los 25 módulos de `MODULE_CATALOG` y Mesa de control. Cada guía explica propósito, recorrido, resultado y consideraciones del flujo actual.

En las rutas de esos módulos, la barra superior ofrece «¿Cómo usar este módulo?». Abre la misma guía en un diálogo sin navegar ni desmontar el formulario de trabajo. El diálogo admite teclado, Escape, cierre explícito y retorno del foco al control que lo abrió; al cambiar de ruta se desmonta. La barra ocupa espacio propio y no cubre controles ni al asistente Plauto.

La biblioteca valida la sesión en servidor y filtra las guías según los permisos existentes. El acceso contextual verifica la sesión y se oculta si no puede validarla. Mesa exige `mesa_access`; no basta con tener Pendientes. Ayuda no concede permisos ni ejecuta operaciones sobre registros, envíos o bases. Los formularios públicos no muestran ayuda interna.

Contenido: `src/lib/help-catalog.ts`. Las claves del catálogo principal tienen instrucciones obligatorias comprobadas por TypeScript; al modificar un flujo, actualizar sus pasos, resultado y límites. Mesa se mantiene como guía adicional con su autorización particular. No hay generación de instrucciones con IA ni actualización automática del contenido. La ruta histórica `/estados-agentes` resuelve la guía de Estados de Prospectadores.

Componentes: `HelpCenter` (biblioteca), `ModuleHelp` (entrada contextual) y `HelpDialog` (lectura compartida). El contenido debe explicar controles existentes; no describir funcionalidades futuras como disponibles.

Validación: TypeScript, lint del código nuevo y build de producción; pruebas de navegador con cuenta administrativa y cuenta restringida, búsqueda con y sin resultados, modal contextual, cierre/retorno del foco, navegación, acceso anónimo y diseño de escritorio/móvil. No se requieren migraciones ni cambios de backend.

Entrega activada el 10 de noviembre de 2026: `.next-help-20261110-final`. Manifiesto de reversión: `.runtime/deploy-backups/help-20261110-160856/manifest.json`. Solo se reinició frontend. Verificación pública HTTPS de biblioteca y modal contextual, acceso de Pamela/Flor y redirección anónima al login; pruebas de navegador de las 26 guías, búsqueda, filtros de acceso, foco y móvil aprobadas.
