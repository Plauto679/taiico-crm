# Mesa de control con Plauto

Actualización y despliegue: 9 de noviembre de 2026. URL: https://taiico-crm.com/mesa-control

## Piloto privado en producción

`MESA_OWNER_USERNAME` está configurado exclusivamente con `alberto.alfaro@taiico.com`. Si falta esa variable, el módulo queda cerrado. No es una lista ni habilita implícitamente a otros administradores. Todos los endpoints exigen esa identidad además de los permisos y el alcance de Pendientes.

El endpoint de sesión publica `mesa_access` para ocultar los enlaces a otras cuentas. La página también comprueba la sesión en servidor y redirige a Sin acceso; la API devuelve 403. Se verificó con el usuario autorizado y otra cuenta administrativa real, localmente y por HTTPS. La redirección de Next puede viajar dentro de una respuesta HTML 200 en streaming; el navegador termina en `/sin-acceso` sin renderizar la mesa.

La revisión administrativa permanece implementada, pero durante el piloto solo Alberto puede realizarla. Ampliar el acceso requiere una decisión explícita posterior; no se habilitaron cuentas de colaboradores.

## Expedientes y carpetas existentes

Cada movimiento tiene un UUID persistente en SQL. Los documentos se guardan en:

`Raíz actual de clientes / RFC - Nombre / Emisión GMM - Mesa - UUID`

Se reutiliza `_client_folder_for_row` de Pendientes y su bloqueo de creación por RFC. No se configura una raíz independiente de Mesa ni se comparten carpetas nuevas. El RFC debe ser propio del contratante; no se aceptan RFC genéricos para crear la carpeta. Tras crear la subcarpeta, no se puede cambiar el RFC del movimiento. Se verifica su pertenencia al padre esperado al reutilizarla y se recupera mediante una propiedad de Drive si hubo una interrupción antes de guardar en SQL.

Los permisos heredados de Drive siguen siendo los del proceso existente. El acceso exclusivo de esta entrega corresponde a la aplicación Mesa; no se modificaron permisos de carpetas históricas. Descargas por backend autenticado, sin exponer identificadores de Drive ni conceder permisos públicos. Las operaciones no leen indiscriminadamente las carpetas de clientes.

## Flujo y revisión humana

- Emisión GMM de persona física: captura, documentos por movimiento y requisitos condicionales de reconocimiento de antigüedad.
- Estados: `draft → submitted → reviewing → validated/correction`. La devolución exige motivo, campo/documento y explicación. Solo el administrativo que tomó la revisión puede resolverla.
- Toda modificación de datos, nuevo archivo o borrador generado devuelve el expediente a preparación. Las escrituras llevan control de versión y las revisiones registran la versión y documentos revisados.
- Plauto orienta y propone datos desde mensajes. La propuesta completa se confirma antes de guardarla. No separa automáticamente nombres y apellidos ni acepta declaraciones médicas por inferencia.
- Crear el mismo UUID con la misma cuenta es idempotente. Un agente, cuando se habilite, seguirá restringido por RFC, promotoría y permisos.

Los registros preparatorios no se insertan automáticamente en el Excel canónico de Pendientes ni se ingresan a MetLife. Las renovaciones y demás módulos conservan su funcionamiento. Jev no es dependencia ni recibe datos.

## Extracción con evidencia

La lectura de documentos del movimiento admite PDF con texto, hasta 4 MB y 30 páginas. Reconoce posibles RFC, CURP, correos y teléfonos; muestra valor, página y fragmento. No atribuye automáticamente una coincidencia al contratante: puede ser un dato de otra persona del documento.

Al confirmar, el backend vuelve a comprobar el valor y su página contra el contenido original, verifica la huella del archivo y registra evidencia, documento, actor y versión. No guarda valores que no coincidan con la evidencia. Los escaneos e imágenes aún requieren captura manual: no hay OCR visual en esta entrega.

## Borrador de solicitud oficial

Se admite exclusivamente **MédicaLife Familiar**, persona física. El archivo oficial consultado conserva `ver25` en la URL, pero el contenido muestra `IG-1-002 VER. 27`. Se fija al SHA-256 `efc99565e1b842a1c7d77890e30c9a0d590b53107d476a087920d03d239e4eab`.

Fuente: https://www.metlife.com.mx/content/dam/metlifecom/mx/pdfs/recas/Seguros-Individuales/Seguros-de-Gastos-Medicos-y-Accidentes-MedicaLife-Familiar/ig-1-002-ver25-validacion.pdf

El borrador conserva las 15 páginas del archivo y añade campos editables para nombres, apellidos, RFC, CURP, correo y teléfono confirmados. Mantiene declaraciones, autorizaciones, datos médicos y firmas sin completar. Cada página indica **BORRADOR PARCIAL**. No cuenta automáticamente como solicitud completa/firmada y no satisface ese requisito del checklist.

Se verifica la huella de la plantilla antes del llenado y se reabre el resultado para validar los valores canónicos de los campos. Se rechazan textos que no caben, caracteres no compatibles y productos distintos. El PDF generado queda en la carpeta del movimiento con fuente, versión de plantilla y versión de datos en su procedencia. El original se conserva en `backend/assets/metlife_forms/`.

## Actualización diaria de formato

El LaunchAgent `com.taiico.crm.mesa-forms` ejecuta `backend/jobs/check_mesa_forms.py` a las 10:15, hora del Mac servidor, y al cargarse. Consulta el catálogo oficial y el PDF sin credenciales de clientes. Solo permite la fuente HTTPS de MetLife, limita descargas y no sigue redirecciones.

Si cambia el enlace del catálogo o el contenido del PDF, bloquea la generación hasta revisar y versionar el mapeo. No activa automáticamente una plantilla desconocida. Un fallo de consulta también bloquea la generación; la comprobación caduca tras siete días. El estado se muestra en la página y queda en `.runtime/mesa-form-status.json`; los logs del job no incluyen datos de clientes. Primera ejecución verificada con salida 0.

## Despliegue y validación

- Respaldo consistente SQLite y copia restringida de configuración en `.runtime/deploy-backups/mesa-20261109-004828/`.
- Migración aplicada desde `20261029_0023` a `20261109_0024`.
- Frontend activo en `.runtime/releases/mesa-control-20261109`, a través de `.next`; destino previo conservado en el manifiesto de respaldo.
- Backend y frontend reiniciados mediante sus LaunchAgents existentes. No se reiniciaron los jobs de renovaciones ni se enviaron mensajes.
- Suite completa: 488 pruebas y 117 subtests; compilación de producción y TypeScript correctos. Se añadieron comprobaciones posteriores focalizadas de confirmación de extracción.
- Pruebas de API aisladas cubren acceso exclusivo, permisos, carpeta por RFC, rechazo de cambio de identidad, flujo de revisión, conflictos de versión, procedencia de extracción y propuestas sin escritura automática.
- PDF con datos ficticios: campos canónicos y apariencias verificados, 15 páginas renderizadas e inspeccionadas, conservación del original y bloqueos por cambio de plantilla/producto/desbordamiento.
- Interfaz real de producción comprobada en escritorio/móvil sin errores JS. Se abrió el formulario sin crear expedientes de prueba. Se verificó lectura de la raíz existente de Drive y capacidad de crear subcarpetas; no se subieron documentos reales durante estas comprobaciones.

Pendiente para ampliar: OCR de escaneos, más campos y productos, conexión automática al registro operativo de Pendientes e ingreso a aseguradora. No habilitar usuarios adicionales sin instrucción del titular del piloto.
