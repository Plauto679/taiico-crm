# Evolución operativa de Taiico a partir de Titan

Fecha: 2026-11-06. Base de partida: `4dc017b` de `taiico-os`.

## Objetivo y alcance

Taiico asumirá la operación que actualmente realiza KC. Titan sirve como referencia de capacidades y recorridos. El módulo de Pendientes se conserva y se amplía con avisos de avance. Los avisos de campañas se incorporarán después.

Esta primera revisión distingue evidencia del repositorio, documentación suministrada y funciones pendientes de observar en Titan. No acredita que los reportes ya estén importados ni que las nuevas capacidades estén implementadas.

## Fuentes

- `CATALOGOS TITAN 2.xlsx`, proporcionado por el usuario: hojas GMM, VIDA y FUERZA DE VENTAS. Revisado completo, sin modificarlo.
- `Tabla 24 reportes titan.pdf`, proporcionado por el usuario: 24 reportes en páginas 1 y 2; página 3 sin contenido de reportes. Texto y páginas renderizadas revisados.
- Repositorio Taiico en la base indicada arriba.
- Titan: `https://titan.grupokc.com.mx/auth`. Versión 3.1.20. Primera exploración autenticada realizada el 2026-11-08 con la cuenta autorizada de Verónica; alcance detallado al final.
- REA confirmado por el usuario: https://github.com/morluto/rea. Documentación consultada: https://raw.githubusercontent.com/morluto/rea/main/docs/cli.md y https://raw.githubusercontent.com/morluto/rea/main/docs/installation.md.

Los adjuntos son material de referencia. Sus notas operativas no autorizan por sí mismas cambios, envíos ni modificaciones de documentos o expedientes.

## Capacidades actuales y ampliaciones

| Frente | Evidencia actual | Ampliación necesaria |
| --- | --- | --- |
| Pendientes | `backend/services/pendientes.py` y `pending_document_requirements.py`: registro, requisitos por trámite y archivos en Drive | Avisos por evento; mantener el funcionamiento existente |
| Mesa de control | Checklists de Vida/GMM, expedientes y asistente Plauto | Formatos descargables versionados, condiciones y notas documentales, revisión asistida y siguiente paso del trámite |
| Carga de reportes | `base_loads.py`: preview y aplicación de bases de renovaciones GMM/Vida; `ingestion.py` y modelos de ingesta | Adaptadores para los reportes reales, procedencia, fecha de corte, validación y publicación por lote |
| Administrativos de agentes | `auth.py`: roles admin/agente; `agent_scope.py`: alcance por RFC y claves del agente | Identidad propia del auxiliar, vínculo explícito con el agente y restricción de ingresos también en las respuestas y exportaciones del backend |
| WhatsApp | `whatsapp.py`: previsualización y envío de prueba de renovación; registro en AgentAction | Eventos operativos, mensajes persistidos, recepción y estados de entrega, asignación de conversaciones y preferencias por canal |
| Campañas comerciales | `campanas.py`: audiencias, correos, seguimiento de envíos y encuestas | Objetivos e incentivos, reglas versionadas, avance por agente y fuente de cada cálculo |
| Bandeja de comunicación | Modelo genérico `Conversation` con canal/transcripción | Integración operativa de conversaciones de agentes, identificadores de proveedor, responsables e historial de estados |

El modelo Conversation existente no demuestra que ya haya una bandeja WhatsApp operativa. Asimismo, el módulo Campañas actual no es un motor de cálculo de incentivos.

## Los 24 reportes

La periodicidad procede del PDF. La columna de destino es una propuesta para Taiico, no una correspondencia técnica verificada de importadores. Son 16 diarios, 7 mensuales y 1 semanal.

| Nº | Reporte | Frecuencia | Destino propuesto en Taiico |
| --- | --- | --- | --- |
| 1 | Activity Ratio GMM | Mensual | Productividad, clasificación del agente, bonos e incentivos |
| 2 | Activity Ratio Vida | Mensual | Productividad, clasificación del agente, bonos e incentivos |
| 3 | Camino a la Excelencia | Mensual | Seguimiento del primer año de agentes nuevos sin experiencia |
| 4 | Cancelación definitiva GMM | Diaria | Cobranza, pólizas canceladas y efectos en métricas |
| 5 | Cancelación definitiva Vida | Diaria | Cobranza, pólizas canceladas y efectos en métricas |
| 6 | Detalle pagado | Diaria | Producción pagada y avance de campañas |
| 7 | Pendiente de pago | Diaria | Producción emitida pendiente de primer pago y avance de campañas |
| 8 | Persistencia 24 meses | Mensual | Persistencia, elegibilidad y avance de incentivos |
| 9 | Previo de pólizas a cancelar GMM | Diaria | Priorización de cobranza preventiva |
| 10 | Previo de pólizas a cancelar Vida | Diaria | Priorización de cobranza preventiva |
| 11 | Primas en depósito GMM | Diaria | Incidencias de aplicación de pagos |
| 12 | Primas en depósito Vida | Diaria | Incidencias de aplicación de pagos |
| 13 | Producción GMM | Diaria | Producción, reexpediciones y renovaciones |
| 14 | Producción Vida | Diaria | Producción nueva emitida |
| 15 | Quién es quién GMM | Mensual | Producción por agente/promotoría, ranking y bonos |
| 16 | Quién es quién Vida | Mensual | Producción por agente/promotoría, ranking y bonos |
| 17 | Rechazos y aceptación con cargos a tarjeta GMM | Diaria | Cobranza, respuesta bancaria y reintentos |
| 18 | Rechazos y aceptación con cargos a tarjeta Vida | Diaria | Cobranza, respuesta bancaria y reintentos |
| 19 | Recibos aplicados GMM | Diaria | Pagos y despagos de recibos |
| 20 | Recibos aplicados Vida | Diaria | Pagos y despagos de recibos |
| 21 | Recibos pendientes de pago GMM | Diaria | Seguimiento de recibos y cobranza |
| 22 | Recibos pendientes de pago Vida | Diaria | Seguimiento de recibos y cobranza |
| 23 | Reporte integral de comisiones | Semanal | Conciliación de comisiones e ingresos del agente |
| 24 | Siniestralidad GMM | Mensual | Métricas de siniestralidad y bonos de renovación |

### Datos que faltan para construir importadores

El PDF describe finalidad y periodicidad. No contiene los archivos de datos ni sus encabezados, tipos, claves únicas, esquemas, ejemplos o reglas completas de cálculo. Hace falta una muestra representativa de cada formato que se vaya a integrar, con su fecha de corte y origen.

Para cada reporte, registrar: aseguradora, tipo y versión de formato, fecha de corte, período, archivo original y hash, usuario que carga, validaciones, filas aceptadas/rechazadas y lote publicado. Resolver agente por clave canónica; no unir únicamente por nombre. Determinar por formato si el archivo es una foto completa o movimientos incrementales antes de definir reemplazos y deduplicación.

Conservar separados prima emitida, pagada, pendiente, PNA, PCA y prima ponderada. No sumar reportes solapados ni acumular monedas sin una regla de conversión. Los despagos y las reexpediciones requieren tratamiento explícito.

### Ambigüedades que deben resolverse

- El PDF escribe la persistencia como prima necesaria / prima pagada. Conservar esa observación sin implementar ni invertir la fórmula por suposición. Confirmar definición, denominador, cohortes, período y tratamiento de ceros con un reporte real y las reglas aplicables.
- Activity Ratio menciona multiplicidad por PNA, pero no proporciona los umbrales para implementarla.
- Los cuadernos de bonos, bases de campañas, fechas, metas, exclusiones y ajustes no están adjuntos. Sin esas reglas no se puede afirmar que un agente ganó un bono.
- Pendiente de pago y Recibos pendientes de pago son reportes distintos. Mantener ambas fuentes hasta validar su granularidad.
- La persona o mecanismo responsable de cargas no queda cerrado en el pedido original: puede ser un administrativo autorizado o una adquisición automatizada. El flujo debe admitir ambos sin asignar todavía esa responsabilidad a una persona concreta.

## Catálogo de trámites y mesa de control

El Excel contiene 22 grupos de solicitud en GMM, 22 en VIDA y 6 en FUERZA DE VENTAS. Son grupos, no 50 reglas completas: algunos no tienen checklist.

Vida y GMM ya tienen buena parte de sus documentos en `pending_document_requirements.py`. La ampliación debe reutilizar ese servicio y los expedientes actuales. El catálogo aporta también notas y prioridades que la lista de nombres por sí sola no expresa: antigüedad del comprobante de domicilio, firmas de contratantes y condiciones de documentación fiscal, entre otras. Estas notas deben revisarse y modelarse como condiciones visibles antes de automatizarlas.

La hoja FUERZA DE VENTAS incluye préstamos, alta de agentes MetLife/KC, mantenimiento de datos y aclaraciones de bonos/comisiones. No trasladar automáticamente los requisitos internos de KC a Taiico. Revisar cuáles corresponden a la nueva operación y cuáles se conectan con Recluta y Agentes.

El archivo no incluye los formatos en blanco. El usuario confirmó que se obtendrán de las publicaciones oficiales de MetLife; falta verificar su versión, vigencia y asociación a cada requisito. La mesa podrá guiar con reglas explícitas y Plauto podrá explicar faltantes; cualquier evaluación no determinada por esas reglas debe quedar identificada para revisión.

## Acceso del administrativo del agente

Propuesta: cuenta propia vinculada al agente, conservando el usuario real en auditoría. No compartir la contraseña del agente ni otorgar el rol admin.

La implementación requiere revisar `resolve_agent_scope`: hoy los perfiles que no son agente salen sin alcance de agente. Añadir un tercer rol sin cambiar esa condición podría dejar consultas demasiado amplias.

El auxiliar debe heredar únicamente el alcance operativo autorizado de su agente. Bloquear ingresos, comisiones, bonos y estados financieros del agente en endpoints, exportaciones, documentos enlazados, respuestas de Plauto y resúmenes. Distinguir esas cifras de primas y recibos del cliente necesarios para operar. Verificar con pruebas que no puede consultar otro agente ni obtener campos financieros por una ruta alternativa.

## Comunicación por eventos

Primer evento propuesto: cambio relevante de un Pendiente. Registrar el evento después de confirmar el cambio de negocio, vinculado al trámite y al agente. Una cola persistente debe impedir duplicados, permitir reintentos controlados y conservar el resultado del proveedor. El mensaje indicará el avance y un enlace autorizado al CRM.

Puntos de integración identificados: `update_pending` y `create_pending_follow_up` en `pendientes.py`. Actualmente guardan cambios en el archivo canónico de Drive. La escritura en Drive y la cola SQL no comparten una transacción: diseñar conciliación y una identidad estable del trámite antes de conectar el envío. El número de fila por sí solo puede cambiar y no debe ser la identidad persistente de la conversación.

Para la bandeja hacen falta mensajes entrantes/salientes, estado de envío, responsable, contexto del trámite y asociación al agente. Reutilizar el conector de prueba solo tras separar configuración de prueba y producción. Revisar la configuración y documentación vigente del proveedor al implementar. Este análisis no habilita ni realiza envíos.

## Orden de ejecución acordado con el usuario (2026-11-08)

1. Pendientes y mesa de control del agente: preparación asistida de solicitudes y documentos desde la carpeta única del movimiento, requisitos condicionales y revisión del expediente.
2. Bandeja WhatsApp: recepción de documentos, seguimiento y notificaciones; consultas autorizadas de renovaciones y avance conforme existan fuentes verificadas.
3. Reportes e indicadores: importaciones trazables y métricas; módulo separado **Campañas comerciales** para metas e incentivos. El módulo actual de campañas conserva su enfoque de comunicación a agentes/clientes.
4. Usuarios asistentes: prioridad posterior. La experiencia del agente debe permitir resolver las tareas habituales desde WhatsApp, sin depender de una cuenta administrativa adicional.

Este orden reemplaza la propuesta inicial. La autorización y el aislamiento por agente siguen siendo requisitos desde el primer módulo, aunque las cuentas de asistentes se implementen al final.

## Encuesta de agentes y alcance de la primera entrega

Fuente: respuestas suministradas por el usuario el 2026-11-08. Se conservan aquí resultados agregados, sin nombres ni respuestas identificables. Hay 6 respuestas frente a 301 invitaciones **preparadas**; no consta cuántas fueron entregadas y no corresponde calcular una tasa de respuesta sobre entregas.

- Preparar/comparar cotizaciones: 5 de 6.
- Llenar solicitudes y formatos: 3 de 6; una persona adicional lo menciona en el texto abierto.
- Revisar requisitos, consultar productos y prospectar/preparar propuestas: 2 de 6 cada opción.
- Renovaciones, cobranza, trámites/siniestros y mensajes a clientes: 1 de 6 cada opción.
- Cuatro personas aceptan participar en pruebas y dos quieren conocer más. Esto no autoriza envíos desde esta tarea.

Las opciones admitían hasta tres selecciones. Los resultados orientan un piloto, no demuestran preferencias representativas de toda la fuerza de ventas. Cotizaciones es la primera demanda observada; integrarlas como documentos de entrada y prever su comparación posterior sin inventar tarifas ni sustituir cotizadores oficiales.

Primera entrega propuesta: emisión persona física de GMM, sujeta a comprobar el formato oficial aplicable; después ampliar a un producto concreto de Vida. Recorrido: elegir trámite/producto → reutilizar o crear carpeta del movimiento → aportar documentos/cotización → extraer datos con referencia al archivo de origen → preguntar solo por faltantes o contradicciones → generar borrador del formato oficial → revisión del agente → preparar expediente para ingreso. La preparación no equivale a envío a MetLife ni a aprobación de la aseguradora.

Cada carpeta se vinculará a una identidad estable de trámite y a su agente; no mezclar movimientos del mismo cliente. Mostrar procedencia y grado de verificación de datos; no inferir respuestas médicas, firmas, consentimientos ni datos faltantes. Reutilizar datos confirmados sin exigir que el agente vuelva a capturarlos. Conservar documento original, borrador y versión revisada por separado.

Criterios de aceptación: acceso limitado al agente, expediente existente reutilizado sin duplicados, faltantes visibles, campos generados rastreables a evidencia/confirmación, PDF legible sin desbordes, versión exacta del formato registrada e historial del movimiento preservado. Medir tiempo hasta expediente listo, correcciones del agente y devoluciones por documentación con una línea base del piloto.

## Formatos oficiales de MetLife y actualización

El usuario indica que los formatos se vincularán a los publicados por MetLife. Fuente pública verificada el 2026-11-08: https://www.metlife.com.mx/tramites-y-servicios/documentacion-y-solicitudes/ . El catálogo separa productos y contiene documentación de Vida y Gastos Médicos. No se ha validado aún la correspondencia de cada archivo con cada trámite/producto ni su estructura de campos.

Diseño propuesto: comprobación diaria configurable, con descarga solo cuando cambie el contenido. Registrar URL oficial, producto/trámite, fecha de consulta, hash y versión/fecha declarada cuando exista. No confundir fecha de descarga con vigencia. Mantener las versiones anteriores y fijar en cada expediente la utilizada.

Detectar cambios aunque MetLife conserve la misma URL. Un archivo nuevo se registra automáticamente como candidato; si cambian campos, páginas o requisitos, validar el mapeo y la generación antes de activarlo para llenado automático. Un enlace roto o una respuesta HTML no reemplaza el PDF válido. Alertar ante cambios o fallos que requieren intervención; conservar la última versión verificada con su estado visible. No migrar silenciosamente expedientes en curso.

Este documento define el proceso; no se ha instalado ni programado todavía un trabajo recurrente. La implementación debe ejecutarse en el backend desplegado, con historial de ejecuciones, y no depender de que un chat esté abierto.

## Archivos a solicitar por etapas

Para mesa de control no hacen falta los 24 reportes. Primero conviene contar con 2–3 expedientes de ejemplo desidentificados: uno aceptado y otro devuelto/corregido, incluyendo motivo, documentos aportados y formato final, manteniendo coherencia entre los datos de ejemplo. Sirven para comprobar el flujo y los errores que debemos prevenir. Los formatos en blanco se obtendrán de MetLife.

Primer paquete de reportes propuesto: **Producción GMM, Recibos pendientes de pago GMM y Recibos aplicados GMM**, junto con la base de renovaciones GMM que ya utilice la operación. Permiten estudiar renovaciones, recibos abiertos y pagos, sin asumir que Producción contiene por sí sola la agenda completa de renovaciones. Solicitar dos cortes consecutivos del mismo alcance y, si existen, ejemplos de pago aplicado, despago/cancelación y renovación con cambio de prima.

Para cada archivo: formato original Excel/CSV sin alterar encabezados/hojas, fecha de corte, alcance (cartera completa o movimientos), clave de agente, diccionario disponible y explicación de qué sustituye la siguiente entrega. Pueden desidentificarse los datos personales conservando claves consistentes entre archivos y cortes.

Segundo paquete: Detalle pagado, Pendiente de pago y Quién es Quién GMM/Vida para avance comercial; confirmar granularidad y solapamiento antes de sumar. Después: Integral de Comisiones, Persistencia 24 meses, Siniestralidad GMM y bases oficiales de bonos/campañas con vigencia, metas, exclusiones y moneda. Priorizar la equivalencia Vida una vez validado el primer flujo GMM.

## Guion para la exploración autenticada

| Recorrido | Evidencia que recoger | Decisión que permite tomar |
| --- | --- | --- |
| Inicio y navegación | Módulos visibles, fecha de corte y alcance por agente | Diferencias reales respecto a Taiico |
| Nuevo trámite | Tipo, condiciones, campos y formatos ofrecidos antes de enviar | Diseño de guía documental |
| Seguimiento | Estados, responsables, historial y documentos | Eventos que justifican avisos |
| Campaña | Meta, avance, vigencia, desglose y regla visible | Modelo de avance comercial |
| Reportes | Nombre, filtros, período, columnas y descarga disponible | Prioridad y contrato de cada importador |
| Accesos, si está disponible | Vínculos y capacidades de auxiliares | Referencia para permisos propios de Taiico |

La navegación será de consulta. No crear trámites de prueba ni enviar mensajes a agentes durante el descubrimiento.

## Primera ejecución de REA

REA 6.8.0 ejecutado por CLI con Node 24.22.1 mediante paquetes de npm aislados del proyecto. No se modificaron las dependencias del CRM ni se registró un servidor MCP global. La versión habitual de Node del equipo, 25.9.0, no está dentro del rango declarado por esta versión de REA.

Se descargaron, sin cookies ni credenciales, los 25 scripts del mismo origen referenciados por la página pública `/auth`: 1.888.172 bytes en total. La primera pasada completa alcanzó el límite de 30 segundos por archivo. Una segunda pasada acotada al archivo `0x4quonj22b9_.js`, que contiene textos de acceso, terminó con código de salida 0 y evidencia conservada.

Resultado acotado: 1 archivo analizado de 25 inventariados, 142.603 bytes, sin fallos de parseo. La cobertura es parcial: 24 archivos quedaron fuera de alcance y se alcanzó el límite de 5.000 nodos semánticos. No usar este resultado para afirmar funcionamiento interno, reglas de negocio o ausencia de funcionalidades.

Evidencia principal: `ev_1be2fa248eb8c60cefef32465c9fc0493d694947418d1a95735bb6715686bec1`. El manifiesto, resumen y evidencia completos se conservan localmente en `tmp/titan-discovery/rea/`, excluido de Git. El código descargado no forma parte de la implementación de Taiico.

El siguiente análisis útil requiere observar un recorrido autenticado concreto y seleccionar sus archivos o evidencia. La página de acceso por sí sola no permite estudiar las campañas de Verónica ni su mesa de control.

## Exploración autenticada: 2026-11-08

Acceso verificado mediante la interfaz de Chrome. No se guardaron credenciales en el repositorio ni en el gestor de contraseñas. No se enviaron solicitudes, documentos ni mensajes. Esta sección registra capacidades y etiquetas de interfaz; omite datos personales de asegurados, importes de cartera e identificadores de expedientes.

### Inicio e indicadores

Ruta observada: `/inbox/agentes`. Menú: Inicio, Reportes, Persistencia, Estado de Cuenta, Emisión y Servicios, Siniestros, Bonos de MetLife, Expedientes IP / MetLife, Perfil y Cotizador Autos. También aparece Chat AI. No se observó un módulo independiente llamado Campañas en este menú; esto no demuestra que no exista en otras pantallas o perfiles.

Los indicadores separan cierre QEQ, cálculo KC del período posterior, pendiente de pago y total. Cada columna muestra período o fecha de corte. Las métricas distinguen Vida, Meta, Primordial y Gastos Médicos; incluyen PCA, PNA, primas ponderadas, conservación y siniestralidad. Algunos valores tienen enlace al detalle.

La interfaz identifica el Integral de Comisiones como fuente del cálculo provisional KC y advierte que coberturas y otros factores pueden modificarlo. Los rankings de Vida indican PCA QEQ más PCA KC; los de GMM indican prima ponderada QEQ más prima ponderada KC. Se segmentan por promotoría y por agentes nuevos, en crecimiento y consolidados.

«Ver Archivos» abre un listado con reporte, período, fecha/hora de carga y usuario cargador. En la consulta aparecieron 12 fuentes, entre ellas Quién es Quién Primordial, además de Vida/GMM. Ese listado describe archivos cargados para los indicadores; no sustituye al catálogo general de 24 reportes.

Implicación para Taiico: separar cifras de cierre y estimaciones, mostrar su procedencia y fecha de corte y permitir desglose. No deducir reglas completas de bonos a partir de la suma mostrada en un ranking.

### Reportes

Ruta observada: `/reportes`. Catálogo con 24 registros, búsqueda, paginación y botón Export to Excel. La tabla muestra Nombre y Nombre_Tabla_BI. Se observaron, entre otros, Camino a la Excelencia, Pendiente de Pago, Detalle Pagado, Integral de Comisiones, Siniestralidad y Recibos Pendientes de Pago Vida/GMM.

En la primera página, Pendiente de Pago y Recibos Pendientes de Pago GMM muestran el mismo nombre de tabla BI. Es una etiqueta visible, no evidencia suficiente para afirmar que comparten esquema o datos. No se descargaron muestras de reportes en este recorrido.

### Mesa de control y formulario

Ruta de Titan: `/tickets`. La pestaña Mesa integra una aplicación de `tts.grupokc.com.mx`. Hay otra pestaña Reporte del año. Los filtros de navegación incluyen Bandeja de entrada, Asignado, En Met, Devuelto, Terminado y Cancelado. La tabla muestra ticket, agente, asunto, estado, fecha de movimiento, asegurado, DCN y detalle. Los estados visibles en filas pueden ser más específicos que los filtros, como Póliza emitida, Servicio emitido y Cerrado validado.

Se abrió Agregar Ticket, se seleccionó GMM y Emisión persona física y se canceló el formulario; se verificó el regreso al listado. No se creó ningún ticket.

El formulario solicita ramo, subramo, tipo de trámite, asunto, asegurado, prima neta, forma de pago, descripción y archivos. La prima neta pasa a ser obligatoria al seleccionar la emisión observada. Aparece un checklist dinámico de siete requisitos: solicitud digital/tradicional, identificación cotejada, cotización, carta SUD firmada, constancia fiscal reciente, comprobante de domicilio reciente cotejado y adicionales.

El selector GMM incluye variantes más específicas que las del Excel adjunto, como emisión con antigüedad/conversión, pago anticipado, cambio a CLABE, impresión de tarjetas y renovación. También se observaron dos etiquetas de Reembolso con distinta capitalización. No se verificaron sus equivalencias funcionales.

En este formulario se observaron nombres de documentos requeridos y controles de carga; no se verificaron enlaces a formatos en blanco. Mantener pendiente esa parte de la mesa de control.

### Persistencia

Ruta observada: `/persistencia`. Resumen por período con cosechas, prima necesaria, prima pagada y porcentaje; el período más reciente ofrece Ver Detalle. El detalle separa encabezados de importes USD y MXN y muestra por póliza: producto, asegurado, moneda, primas, persistencia, frecuencia de pago, estatus, rehabilitación y tiempo de vida.

La muestra observada no resuelve la fórmula pendiente del PDF: las cifras necesarias y pagadas son iguales o casi iguales y el porcentaje redondeado es 100. Tampoco permite establecer una política de conversión monetaria. Mantener estas reglas sin implementar hasta disponer de evidencia que las determine.

### Bonos y siguientes recorridos

`/bonos/metlife` muestra antes del contenido un aviso de estimaciones y exclusión de responsabilidad con botones SI ACEPTO y NO ACEPTO. Se cerró sin aceptar y la aplicación regresó a Inicio. Se solicitó autorización específica al usuario para continuar con esa aceptación.

### Siniestros

Ruta observada: `/siniestros`, con mesa integrada de `tts.grupokc.com.mx`. Reutiliza filtros operativos y añade Aceptado parcial. La tabla distingue tipo de reclamación inicial/complemento, póliza, folio de reingreso, DCN, número de siniestro y reclamación, cobertura, monto reclamado, fecha de movimiento, dictamen y número de trámite. En filas se observaron estados Asignado, En proceso / Ingresado en Met y Suspendido KC.

Se abrió el detalle de un ticket en la ruta de bitácora. Muestra secciones Principales, Estado y Detalles adicionales, controles de Movimientos, descarga y archivos adjuntos, y un área para responder. No se enviaron respuestas ni se descargaron expedientes. La existencia del botón Movimientos no acredita todavía el contenido del historial.

Implicación propuesta: distinguir eventos de estado, devolución y documentos al diseñar comunicaciones, manteniendo las referencias de aseguradora separadas del identificador interno del trámite.

Pendientes: contenido de Bonos tras resolver el aviso, campañas concretas, contenido del historial de un ticket, formatos descargables, Expedientes y capacidades del perfil para auxiliares. El inicio de sesión ya no bloquea la exploración.

## Ajuste de experiencia y operación acordado (2026-11-09)

La entrada principal será una página **Mesa de control** con Plauto, accesible mediante identificación del agente y sin exigir navegar por los módulos del CRM. Plauto guiará la solicitud, recabará documentos y utilizará operaciones autorizadas del backend para crear o recuperar el registro y la carpeta del movimiento. La interfaz combinará conversación con selección de trámite, carga de archivos, resumen del expediente y estado visible; las acciones estructuradas no necesitan una respuesta del modelo para cada clic.

La revisión de los administrativos internos de Taiico es obligatoria antes de declarar el expediente listo para ingreso. No confundir estos revisores con los futuros usuarios asistentes particulares de cada agente, que mantienen la última prioridad. Estados propuestos: borrador, faltan datos/documentos, listo para revisión, en revisión, requiere corrección, validado por mesa; ingreso a aseguradora y resultado se registran aparte con evidencia. La validación de mesa no significa aceptación de MetLife.

Los revisores registrarán resultado, motivo estructurado, explicación, documento/campo afectado, corrección solicitada, responsable, fecha y versión revisada. Distinguir error de captura, documento faltante, ilegibilidad, vigencia, inconsistencia y otros. Una modificación relevante tras la revisión debe reabrirla. Conservar la extracción original y la corrección humana para medir errores y preparar evaluaciones; las etiquetas no entrenan ni modifican automáticamente el modelo. Los casos del día a día construirán el conjunto de ejemplos, por lo que no se condiciona el diseño a recibir expedientes históricos.

Primera entrega vertical propuesta: agente inicia una emisión GMM, Plauto registra el borrador y vincula su carpeta, el agente aporta archivos y datos, envía a revisión, un administrativo valida o solicita corrección con motivo, y el agente puede retomar el mismo expediente. Integrar generación del formato oficial verificado en ese recorrido, con revisión previa del agente; no exponer una interfaz que prometa generación o ingreso aún no implementados.

### Cotizaciones y rapidez

La revisión del código confirma que `cotizaciones.py` ya prepara la carpeta, crea una tarea `MetLifeQuotationTask` y permite abrir/contestar una sesión con `MetLifeQuotationPortalAdapter`. Reutilizar este flujo y sus identificadores. La reserva actual de sesión activa utiliza una variable global del proceso y admite una cotización activa por proceso; revisar concurrencia y aislamiento antes de ofrecer acceso simultáneo a varios agentes.

Plauto dispone de herramientas acotadas en `plauto.py`; su conexión al backend no significa que hoy pueda crear expedientes de mesa. Será necesario añadir operaciones explícitas con autorización, validación, identidad estable y protección contra duplicados/reintentos.

Propuesta de rapidez: acciones directas al backend para pasos conocidos y validaciones; modelo para interpretar mensajes/documentos y explicar faltantes; ejecución del cotizador como trabajo con estado recuperable. Medir por separado latencia del modelo, cola y portal antes de escoger modelo/proveedor. «JEV» está pendiente de identificación por el usuario; no asumir qué producto es ni prometer respuesta instantánea del portal.

### Renovaciones y actualidad de cobranza

El usuario confirma que renovaciones ya funciona bien y requiere solo cambios menores. El problema señalado en cobranza es la falta de carga de reportes recientes; no rediseñar renovaciones como requisito de mesa ni atribuir una fecha real de desactualización sin consultar las cargas.

Prioridad operativa propuesta: mostrar fecha de corte de cada fuente, fecha de carga, responsable y antigüedad; distinguir ambas fechas y señalar fuentes vencidas según su frecuencia esperada. Evitar presentar un recibo como impagado al día de hoy cuando solo existe evidencia de un corte anterior. Preparar recepción de archivos, validación y publicación trazable. Identificar primero dónde llegan actualmente los reportes (correo, carpeta o descarga de portal) para automatizar su adquisición sin asumir acceso disponible.

Pedido ajustado: último **Recibos pendientes de pago GMM** y **Recibos aplicados GMM**, con fechas de corte compatibles y, si es posible, el corte anterior para reconciliación. Si la operación de cobranza incluye Vida, solicitar sus equivalentes. Pedir **Pendiente de pago** aparte si también se quiere cubrir primeras primas pendientes, sin confundirlo con recibos pendientes. Producción y la base de renovaciones dejan de ser prerrequisitos del primer desarrollo. Los reportes de indicadores/comisiones se mantienen para la tercera etapa.

Estas decisiones actualizan el diseño; no implican que la página, las herramientas de Plauto, la cola de revisión o las cargas automáticas estén implementadas.

## Primera implementación (2026-11-09)

Se implementó la entrada `/mesa-control`, borradores por movimiento, documentos privados, propuestas de datos con Plauto y revisión administrativa obligatoria. Ver `docs/MESA_CONTROL.md` para alcance, configuración, validaciones y límites. La extracción documental y generación de PDFs oficiales siguen pendientes; Jev queda separado como experimento.

## Piloto privado en producción (2026-11-09)

Mesa habilitada solo para Alberto mediante una identidad configurada en servidor. Se integró la subcarpeta por movimiento bajo la carpeta actual RFC - Nombre, extracción de coincidencias con evidencia/confirmación, borrador parcial editable de la solicitud oficial de MédicaLife Familiar y comprobación diaria de catálogo/huella. Se mantiene revisión humana y Jev separado. Ver `MESA_CONTROL.md` para límites y comprobaciones de despliegue.
