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

La lectura de documentos del movimiento admite PDF con texto, PDF escaneado, JPG y PNG, hasta 4 MB y 30 páginas. Usa OCR local de Apple Vision para imágenes y páginas rasterizadas; muestra el texto por página y marca la procedencia OCR. Reconoce posibles RFC, CURP, correos y teléfonos, además de nombres/apellidos que estén explícitamente etiquetados. No divide un nombre completo sin etiquetas ni atribuye automáticamente una coincidencia al contratante: puede ser un dato de otra persona del documento.

Al confirmar, el backend vuelve a comprobar el valor y su página contra el contenido original, verifica la huella del archivo y registra evidencia, documento, actor y versión. No guarda valores que no coincidan con la evidencia. No se corrigen por suposición letras confundidas con números. El OCR puede equivocarse o no leer una imagen; se conserva la alternativa de captura manual y la confirmación humana sigue siendo obligatoria.

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
- Frontend inicial en `.runtime/releases/mesa-control-20261109`, sustituido por `.next-mesa-ocr-20261109-final` a través de `.next`; destino previo conservado en el manifiesto de respaldo.
- Backend y frontend reiniciados mediante sus LaunchAgents existentes. No se reiniciaron los jobs de renovaciones ni se enviaron mensajes.
- Suite completa: 488 pruebas y 117 subtests; compilación de producción y TypeScript correctos. Se añadieron comprobaciones posteriores focalizadas de confirmación de extracción.
- Pruebas de API aisladas cubren acceso exclusivo, permisos, carpeta por RFC, rechazo de cambio de identidad, flujo de revisión, conflictos de versión, procedencia de extracción y propuestas sin escritura automática.
- PDF con datos ficticios: campos canónicos y apariencias verificados, 15 páginas renderizadas e inspeccionadas, conservación del original y bloqueos por cambio de plantilla/producto/desbordamiento.
- Interfaz real de producción comprobada en escritorio/móvil sin errores JS. Se abrió el formulario sin crear expedientes de prueba. Se verificó lectura de la raíz existente de Drive y capacidad de crear subcarpetas; no se subieron documentos reales durante estas comprobaciones.

Pendiente para ampliar: más campos y productos, conexión automática al registro operativo de Pendientes e ingreso a aseguradora. No habilitar usuarios adicionales sin instrucción del titular del piloto.


## OCR y guía de campos: actualización del 9 de noviembre

- `backend/ocr/recognize.swift` usa Vision/PDFKit localmente; `backend/ocr/build.sh` genera `.runtime/mesa-ocr/recognize` en el Mac servidor. No se distribuye un binario compilado en Git. Para otro servidor se debe instalar un lector compatible explícitamente; si falta el ejecutable, se devuelve un error claro, sin enviar imágenes a otro proveedor.
- Worker con dos lecturas simultáneas, timeout de 90 segundos, límite de 4 MB/30 páginas y 100.000 caracteres. Usa un directorio temporal privado que se elimina al terminar, incluso ante error o timeout. No ejecuta comandos provenientes del documento ni registra texto en logs.
- Los PDFs mixtos conservan texto nativo y lectura OCR de las páginas con imágenes. Se muestran hasta 40 coincidencias y hasta 6.000 caracteres por página en la vista; los recortes se indican. El número de página se mantiene en la evidencia confirmada.
- «Usar esta lectura con Plauto» permite orientar con el documento seleccionado del mismo movimiento. El OCR es local; únicamente al solicitar esta orientación se envía el texto seleccionado al proveedor de Plauto ya configurado, con `store=false`. No se envían las imágenes. El usuario puede elegir cualquier página inicial; el contexto contiene hasta cinco páginas por consulta, con indicación de lectura parcial. No se consultan otros expedientes ni carpetas completas.
- Plauto recibe los campos faltantes y formula una pregunta a la vez. Los valores propuestos desde la lectura deben aparecer en las páginas seleccionadas o en el mensaje del usuario, y requieren confirmación antes de guardarse.
- El panel muestra cuántos campos del **llenado parcial** están resueltos y las secciones que todavía deben completarse en el formato: domicilio/identificación, información laboral, producto/coberturas, pago/familia, salud, privacidad/firmas y beneficiarios. Un indicador completo de campos mapeados nunca declara completa la solicitud.
- «No tiene apellido materno» requiere confirmación explícita. Se almacena separado del texto y no puede coexistir con un apellido capturado.
- `backend/assets/metlife_forms/catalog.json` separa producto, versión, huella, campos mapeados, preguntas y guía por sección. Actualmente solo está habilitado el formato ya verificado. Los demás formatos se incorporarán posteriormente con su propia fuente oficial, comprobación de actualidad, mapeo, prueba de llenado y revisión; no se reutilizará un PDF de otro producto.

Despliegue sin migración adicional ni cambio de propietario. Respaldo previo y manifiesto: `.runtime/deploy-backups/mesa-ocr-20261109-011834/`. El control diario volvió a verificar la fuente oficial. Se comprobaron por HTTPS acceso del propietario, OCR disponible, bloqueo de otra cuenta administrativa y de solicitudes anónimas.

Validación: suite completa con 504 pruebas y 117 subtests; pruebas focalizadas adicionales para selección de páginas posteriores. OCR real probado con imagen y PDF escaneado ficticios, confirmación con evidencia, límites, limpieza de temporales, PDF mixto, nombres sin inferencia, guía progresiva y acceso exclusivo. Interfaz de escritorio/móvil probada con fixtures para lectura, confirmación, orientación desde documento y continuación al siguiente campo. Compilación, TypeScript y lint correctos. No se crearon expedientes ni subieron documentos reales de prueba a producción.


## Reembolso inicial y complemento: entrega del 9 de noviembre

El selector de nueva solicitud admite emisión y reembolso GMM. El tipo de movimiento queda fijo después de crear el expediente. Los expedientes anteriores conservan emisión por defecto; los nuevos campos viven en el JSON existente, sin migración SQL. En reembolso, `client_name`/`rfc` y los datos de identidad sin prefijo corresponden al **asegurado titular**; `contractor_name` identifica a quien contrató la póliza y `patient_*` al paciente. Nunca se copian datos de una persona a otra por suposición. La confirmación de extracción permite elegir titular o paciente para nombres/CURP y registra esa atribución.

Se conserva el mismo acceso exclusivo, alcance, historial, reserva de revisión y resolución de carpetas por RFC. La carpeta del movimiento se llama `Reembolso GMM - Mesa - UUID` dentro de la carpeta actual del RFC del titular. No se crean permisos públicos, se habilitan otros usuarios ni se envían solicitudes a MetLife.

### Reglas y documentos

`mesa_claims.py` distingue inicial/complemento, paciente menor de edad/CURP, cambio de cuenta bancaria, medicamentos, estudios, histopatología, desglose de facturas, firma digital y respuesta a requerimiento. Las condiciones empiezan en `null`: no responder no equivale a «No». Complemento requiere número de siniestro; respuesta a requerimiento requiere DCN. Se solicitan documentos según las respuestas y se comprueban fechas confirmadas contra límites de calendario; mesa debe contrastarlas con los originales.

Fuente contrastada: [reembolso MetLife](https://www.metlife.com.mx/tramites-y-servicios/tramites-de-seguros-de-gastos-medicos/reembolso/). Se detectó una discrepancia real: el portal señala estado de cuenta de hasta seis meses; el checklist del PDF vigente, página 5, señala tres meses. **El piloto aplica tres meses, lo informa en la interfaz y exige revisión administrativa del criterio**. No se presenta como un requisito unificado de ambas fuentes. Domicilio: tres meses; informe médico de complemento: seis meses. Los casos especiales no resueltos por estas reglas requieren revisión de mesa y condiciones de póliza.

Se admiten facturas XML CFDI 3/4 de hasta 1 MB únicamente en su categoría: sin DTD, entidades, NUL ni recursos externos. Se conservan como originales privados; no se mandan al OCR. Las facturas PDF se aportan en categoría separada. La presencia de un PDF y un XML **no comprueba** que coincidan todas las facturas: el administrativo debe revisar cada pareja, RFC, conceptos, importes y total. La validación exige cinco comprobaciones explícitas (identidad, informes médicos, facturas, condiciones/vigencias y solicitud firmada) y comentario, registrados en el historial. Editar datos/documentos invalida esa revisión.

### Formatos oficiales y generación

- Solicitud de reclamación GMM **VG-2-068 VER. 12**, seis páginas. Fuente enlazada desde el portal: `https://www.metlife.com.mx/content/dam/metlifecom/mx/pdfs/common-files/reclamacion-gmm/solicitud-de-reclamacion-gastos-medicos-mayores-vg-2-068-ver-12-pdf-editable.pdf`. SHA-256 `f7d41d38c376b80376c872f74c024f83221c68d1e85511b75659572fb15056b2`.
- Informe médico **CC-1-020 VER. 7**, cuatro páginas. Fuente: `https://www.metlife.com.mx/content/dam/metlifecom/mx/pdfs/internas/Soy-Cliente/Tramites-y-Servicios/Programar-Cirugia/Informe-medico.pdf`. SHA-256 `7f5efd22a6b8c6fc5b2779e885caa49622f9469fe3fce72f211d135022d7b792`. Se ofrece el formato oficial y lectura de documentos recibidos. Lo llena y firma cada médico; no se generan diagnósticos ni firmas.

El job diario existente comprueba además la presencia de ambos enlaces en el portal y sus hashes. Guarda estado independiente en `.runtime/mesa-form-status-claims.json`. Cambios, errores o comprobación vencida bloquean la generación. No activa nuevas plantillas automáticamente. Esta comprobación no sustituye una revisión de cambios en requisitos redactados en las páginas web.

La solicitud se conserva editable, con sus seis páginas y aviso de borrador parcial. Se llenan datos confirmados de titular/paciente, contratante, póliza, contacto, tipo de reembolso y siniestro/DCN cuando aplican. No se llenan importes, CLABE, información clínica, declaraciones, consentimientos ni firmas. Se borran valores precargados del original, incluida una fecha de ejemplo; se normalizan rectángulos invertidos y propiedades heredadas de celdas, manteniendo el árbol canónico y las apariencias coincidentes. El borrador nunca satisface el requisito de solicitud firmada.

Plauto recibe datos y condiciones del reembolso y, solo al elegir un documento, sus páginas seleccionadas. Propone cambios para confirmación, orienta a un faltante a la vez y distingue titular/paciente. El informe médico continúa siendo documentación externa: la lectura orienta sobre omisiones, sin certificación clínica.

### Validación de esta entrega

Suite completa: 514 pruebas y 117 subtests; comprobación posterior focalizada de propuestas Plauto con condiciones nulas y conservación del tipo de movimiento. Compilación de producción, TypeScript y lint correctos. PDF ficticio renderizado en sus seis páginas y validación de valores canónicos/widgets/apariencias, sin fecha precargada ni consentimientos marcados. Prueba de navegador con datos ficticios: creación, inicial/complemento, cuenta bancaria condicional, XML, propuesta Plauto, borrador que no satisface firma y revisión administrativa obligatoria; escritorio y móvil sin desbordamiento horizontal ni errores JS. No se crean expedientes reales de prueba en producción.

Frontend de esta entrega: `.next-mesa-claims-20261109-final`. Pago directo y cirugía programada continúan pendientes; comparten documentos, pero requieren sus propias reglas antes de habilitarse.

Activación verificada en localhost y `https://taiico-crm.com`: propietario permitido, otra cuenta administrativa bloqueada en API/generación/página, anónimo bloqueado; emisión y reembolso con fuentes verificadas y OCR disponible. Respaldo SQLite consistente y manifiesto en `.runtime/deploy-backups/mesa-claims-20261109-015940/`. Se reiniciaron solo backend y frontend; no hubo migración ni cambio del propietario. Comprobación focalizada final: 23 pruebas, incluido el esquema de propuestas de Plauto.


## Ampliación autorizada del piloto: Pamela (2026-11-09)

Por instrucción explícita del propietario se habilitó `pamela.alfaro@taiico.com`, única cuenta de Pamela localizada en el directorio del CRM. Se conserva `MESA_OWNER_USERNAME` y se agrega `MESA_OPERATOR_USERNAMES` como lista de usuarios exactos separados por coma. Una invitación solo funciona con permiso de operación existente en Pendientes y rol admitido; sin propietario configurado todo el piloto permanece cerrado. No se concede acceso al resto de administradores ni se amplían roles, promotorías o permisos de Pamela.

Pamela ya tenía rol administrativo y permiso de operación en Pendientes, por lo que puede preparar expedientes, tomar revisión, solicitar correcciones y validar dentro de su alcance actual. Se mantiene la reserva de revisión por administrativo y el historial. Esta autorización reemplaza la limitación previa de propietario único; el resto del flujo permanece igual.

Se respaldó la configuración en `.runtime/deploy-backups/mesa-pamela-20261109-091444/` y se reinició solo el backend. Sin migración ni nuevo build frontend. Verificación pública HTTPS: propietario y Pamela con operación/revisión; otra cuenta administrativa bloqueada; anónimo bloqueado. Dieciocho pruebas focalizadas aprobadas, incluyendo invitación explícita, permiso de operación obligatorio y cierre sin propietario. No se crearon expedientes para probar producción.

Se envió desde el correo de Alberto la explicación del alcance actual, flujo, límites, etapas futuras y solicitud de recomendaciones y visto bueno de Pamela. El envío fue autorizado por el propietario y confirmado como enviado.
