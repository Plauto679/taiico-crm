# Evolución operativa de Taiico a partir de Titan

Fecha: 2026-11-06. Base de partida: `4dc017b` de `taiico-os`.

## Objetivo y alcance

Taiico asumirá la operación que actualmente realiza KC. Titan sirve como referencia de capacidades y recorridos. El módulo de Pendientes se conserva y se amplía con avisos de avance. Los avisos de campañas se incorporarán después.

Esta primera revisión distingue evidencia del repositorio, documentación suministrada y funciones pendientes de observar en Titan. No acredita que los reportes ya estén importados ni que las nuevas capacidades estén implementadas.

## Fuentes

- `CATALOGOS TITAN 2.xlsx`, proporcionado por el usuario: hojas GMM, VIDA y FUERZA DE VENTAS. Revisado completo, sin modificarlo.
- `Tabla 24 reportes titan.pdf`, proporcionado por el usuario: 24 reportes en páginas 1 y 2; página 3 sin contenido de reportes. Texto y páginas renderizadas revisados.
- Repositorio Taiico en la base indicada arriba.
- Titan: `https://titan.grupokc.com.mx/auth`. Pantalla pública observada: versión 3.1.20. Exploración autenticada pendiente de sesión de Verónica.
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

El archivo no incluye los formatos en blanco. Para ofrecer descargas faltan los documentos oficiales, su versión, vigencia y asociación a cada requisito. La mesa podrá guiar con reglas explícitas y Plauto podrá explicar faltantes; cualquier evaluación no determinada por esas reglas debe quedar identificada para revisión.

## Acceso del administrativo del agente

Propuesta: cuenta propia vinculada al agente, conservando el usuario real en auditoría. No compartir la contraseña del agente ni otorgar el rol admin.

La implementación requiere revisar `resolve_agent_scope`: hoy los perfiles que no son agente salen sin alcance de agente. Añadir un tercer rol sin cambiar esa condición podría dejar consultas demasiado amplias.

El auxiliar debe heredar únicamente el alcance operativo autorizado de su agente. Bloquear ingresos, comisiones, bonos y estados financieros del agente en endpoints, exportaciones, documentos enlazados, respuestas de Plauto y resúmenes. Distinguir esas cifras de primas y recibos del cliente necesarios para operar. Verificar con pruebas que no puede consultar otro agente ni obtener campos financieros por una ruta alternativa.

## Comunicación por eventos

Primer evento propuesto: cambio relevante de un Pendiente. Registrar el evento después de confirmar el cambio de negocio, vinculado al trámite y al agente. Una cola persistente debe impedir duplicados, permitir reintentos controlados y conservar el resultado del proveedor. El mensaje indicará el avance y un enlace autorizado al CRM.

Puntos de integración identificados: `update_pending` y `create_pending_follow_up` en `pendientes.py`. Actualmente guardan cambios en el archivo canónico de Drive. La escritura en Drive y la cola SQL no comparten una transacción: diseñar conciliación y una identidad estable del trámite antes de conectar el envío. El número de fila por sí solo puede cambiar y no debe ser la identidad persistente de la conversación.

Para la bandeja hacen falta mensajes entrantes/salientes, estado de envío, responsable, contexto del trámite y asociación al agente. Reutilizar el conector de prueba solo tras separar configuración de prueba y producción. Revisar la configuración y documentación vigente del proveedor al implementar. Este análisis no habilita ni realiza envíos.

## Orden de ejecución propuesto

1. Observar Titan con la cuenta autorizada: menú, detalle y alta de trámite, formatos, campañas y reportes. Registrar evidencia y separar observaciones de hipótesis.
2. Definir permisos del auxiliar y cerrar las vías de exposición de ingresos antes de crear cuentas reales.
3. Incorporar avisos de Pendientes y una bandeja mínima sobre eventos persistidos.
4. Extender Carga de bases con los primeros reportes reales y su trazabilidad, reutilizando preview y publicación controlada.
5. Añadir avance comercial con reglas y fuentes confirmadas; después, avisos de actualización de campañas.
6. Ampliar la mesa de control con formatos verificados y asistencia de Plauto sobre los requisitos existentes.

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
