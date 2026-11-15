# Pólizas · primera versión

El módulo `/polizas` utiliza las tablas Policy, Client, Renewal, Document y
PolicyProspectorAssignment existentes; no migra ni regenera registros o estados.

- Consulta, búsqueda por póliza/nombre/RFC, filtros combinables por aseguradora, ramo (Vida, GMM y demás productos disponibles) y revisión.
- Alta manual o selección de una emisión concluida en Pendientes. El alta
  desde emisión guarda la referencia y su snapshot, y exige que no haya cambiado.
- El contratante debe existir con RFC válido, propio, normalizado y único. Si
  falta o está duplicado, se resuelve en Clientes. No crea clientes por nombre.
- Número de póliza conservado como texto. Posibles variantes se bloquean para
  revisión. La restricción actual de la BD (número único global) se mantiene;
  una colisión entre aseguradoras nunca reasigna una póliza existente.
- Ficha: resumen, asegurados capturados, agente (incluida fuente MetLife disponible),
  asignaciones actuales e históricas, vigencias, enlaces al expediente y documentos,
  historial de cambios del módulo y origen de emisión.
- Conciliación CSV/XLS/XLSX: primera hoja, encabezados en primera fila, 500 filas
  máximo y 10 MB. Plantilla descargable. Las filas sin producto_id pueden usar
  el producto seleccionado; las columnas aseguradora/ramo se validan si existen.
- Vista previa persistente por usuario. Se aplican únicamente filas seleccionadas,
  con comprobación de cambios concurrentes. Identidades contradictorias y variantes
  del número quedan bloqueadas. Una fila puede descartarse conservando el registro.
- Cada aplicación conserva Policy.id, Client.id, las asignaciones y el historial
  financiero; registra antes/después y usuario en AgentAction. No genera movimientos.
- Edición de identidad (cliente/producto/número) bloqueada en esta versión. No se
  inventa un historial de cambios anteriores al módulo.
- Las cargas canónicas siguen sus parsers existentes. Una vigencia validada aquí
  no se reemplaza automáticamente: una nueva fecha genera un aviso en la ficha.
  Una carga tampoco reemplaza un RFC válido del cliente por otro RFC diferente.
- Permisos `polizas`: navegación, tarjeta, guía de ayuda y catálogo de Accesos.
  Lectura restringida por alcance; escritura requiere operación y rol autorizado.

Validación: tests de RFC único, colisiones, permisos, creación, edición,
conservación de asignaciones, importación parcial/idempotente, concurrencia,
rechazo de diferencias y catálogos. Pruebas visuales en escritorio y móvil.

Pendiente por instrucción del usuario: descargar y vincular pólizas MetLife Vida de la cartera Taiico para clientes con RFC. No iniciar hasta que el usuario lo indique, pues el control de la computadora está ocupado con renovaciones.
