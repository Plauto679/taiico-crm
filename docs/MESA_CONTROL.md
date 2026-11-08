# Mesa de control con Plauto · primera entrega

Implementación local del 9 de noviembre de 2026. Ruta `/mesa-control`, enlazada desde Pendientes y el menú. La página mantiene autenticación y prescinde del menú lateral. Jev no es dependencia ni recibe datos.

## Alcance disponible

- Emisión GMM de persona física: borrador persistente, identificación UUID del movimiento y agente/promotoría asignados desde el directorio autorizado.
- Requisitos del catálogo operativo actual, con documentos de reconocimiento de antigüedad condicionados a la selección del agente. La presencia de un archivo no acredita su validez.
- Carga de PDF/JPG/PNG hasta 25 MB por documento en una carpeta privada por movimiento. Se conservan versiones; el backend controla cada descarga y no entrega identificadores de Drive al navegador.
- Plauto recibe el estado, datos capturados, nombres de documentos y última revisión de ese movimiento. Puede orientar y proponer datos a partir del mensaje. El usuario ve la propuesta completa y confirma antes de guardarla. No recibe otros expedientes ni contenido de archivos. Sin configuración de IA, permanece disponible la orientación por checklist.
- Revisión obligatoria: `draft → submitted → reviewing → validated/correction`. Solo un administrador con operación en Pendientes puede tomar y resolver la revisión. Una devolución exige motivo, campo/documento y explicación. La aprobación registra versión revisada y documentos.
- Cualquier cambio de datos o nuevo archivo devuelve el expediente a borrador. Control optimista de versión en cada escritura para evitar aprobar un expediente cambiado en otra sesión.
- Historial con actor, fecha, estado, versión y cambios. Creación idempotente por UUID y creador. Permisos verificados en cada endpoint, incluyendo chat y descargas.

Los expedientes preparatorios viven en SQL. No se insertan automáticamente en el Excel canónico de Pendientes ni se envían a MetLife. Se conserva el módulo existente sin cambiar su operación. Las cuentas administrativas actuales revisan; no se introducen usuarios asistentes de agentes.

## Habilitación

1. Aplicar la migración `20261109_0024` en la base existente, después de su respaldo y de comprobar el revisionado de Alembic. La cadena histórica presupone tablas iniciales: no debe usarse `upgrade head` como inicializador de una base vacía sin el bootstrap existente.
2. Configurar `MESA_DRIVE_ROOT_ID` con una carpeta **privada del equipo administrativo**, accesible a la cuenta de servicio de Drive. No usar una carpeta compartida con todos los agentes, porque Drive hereda permisos del padre. El servicio no crea permisos públicos ni comparte carpetas con agentes: sus descargas pasan por el backend autenticado.
3. Usar la autenticación de Drive existente. Sin carpeta configurada se permite preparar datos, pero se bloquean cargas con explicación visible.
4. Plauto reutiliza `PLAUTO_ENABLED`, `PLAUTO_MODEL` y `OPENAI_API_KEY`. No se configura un proveedor adicional.
5. Los agentes necesitan permiso de Pendientes y vínculo MetLife válido; los revisores requieren rol admin y operación en Pendientes, siempre dentro de sus promotorías.

La migración y la configuración de Drive **no se han aplicado a producción** desde esta tarea. No se han subido expedientes, llamado al proveedor de IA con datos reales ni enviado mensajes.

## Verificación

- Pruebas HTTP con SQLite aislado: autorización por agente/promotoría, roles de consulta, creación repetida, requisitos condicionales, revisión obligatoria y asignada, devolución estructurada, versiones obsoletas, invalidación de revisión, tipos de archivos, conservación de versiones y propuesta de Plauto sin escritura hasta confirmar.
- Migración nueva: upgrade/downgrade aislado desde la revisión anterior.
- TypeScript y compilación de producción.
- Playwright en escritorio y móvil con respuestas de API simuladas: creación, propuesta/confirmación, envío, toma de revisión y devolución; sin errores JS ni desbordamiento horizontal. Drive y el proveedor de IA están simulados en las pruebas, no se certifica su conexión real.

## Próximas capacidades

Todavía no hay OCR/extracción documental, llenado de PDFs oficiales, sincronización diaria de formatos, transferencia automática al Excel de Pendientes ni ingreso a MetLife. La página lo declara para evitar confundir orientación con operaciones ejecutadas. El enlace de formatos lleva al catálogo oficial, no a una versión de PDF validada para llenado.

La siguiente entrega debe verificar el PDF oficial aplicable, mapear campos, mostrar fuente de cada dato extraído y generar un borrador antes de la revisión humana. La actualización de formatos y sus mapeos será versionada. Jev queda como experimento independiente de latencia y precisión con datos ficticios.
