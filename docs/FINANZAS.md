# Finanzas

El módulo `/finanzas` sigue el mismo modelo de sesión, navegación, permisos y auditoría de Taiico CRM. En **Accesos** aparece como `Finanzas` y requiere permiso explícito:

- `Lectura`: consulta de tableros, movimientos, recurrentes, facturas, proyecciones y reglas.
- `Operación`: sincronizar/cargar fuentes, enriquecer movimientos, confirmar recurrentes, conciliar facturas, editar proyecciones y aplicar reglas.

## Fuentes y persistencia

Los cuatro CSV históricos siguen siendo la fuente canónica externa. `finance_movements` es un índice interno para consultas; las categorías y decisiones humanas se guardan como una capa de enriquecimiento y no sobrescriben silenciosamente los datos originales.

Las rutas se configuran con `FINANCE_ROOT` o con cada variable `FINANCE_*_CSV`. Si el volumen local no está montado, el servidor descarga cada histórico mediante su `GOOGLE_DRIVE_FINANCE_*_FILE_ID`; el archivo local siempre tiene precedencia. Si ninguna fuente está configurada o accesible, la interfaz la muestra como no disponible y no genera cifras de ejemplo.

La sincronización usa `source_key + id_movimiento` como identidad estable, compara SHA-256 y es idempotente. Una carga nueva pasa por previsualización y detección de duplicados. Al publicar:

1. crea un respaldo fechado del histórico;
2. escribe en un archivo temporal dentro del mismo directorio;
3. reemplaza el canónico con `os.replace`;
4. vuelve a indexar y registra la mutación en Auditoría.

La reversión restaura el respaldo mediante el mismo reemplazo atómico.

## Facturas y estados PDF

Los XML CFDI se indexan por UUID, RFC, fecha, total y moneda. Esto facilita conciliación, pero **no declara validez fiscal ante el SAT**. Los PDF de facturas se conservan como evidencia sin inventar campos ausentes.

Los formatos bancarios PDF requieren un parser validado por banco y versión. Mientras el servidor no tenga uno validado, el asistente rechaza su publicación con un mensaje explícito y permite usar el CSV canónico. Esta decisión evita interpretar importes incorrectamente.

## Activación

1. Ejecutar `alembic upgrade head` contra la base del entorno.
2. Montar las fuentes financieras o configurar sus IDs de Google Drive.
3. Dar permiso `Finanzas` a los usuarios autorizados desde Accesos.
4. Abrir Finanzas y ejecutar **Sincronizar**.
