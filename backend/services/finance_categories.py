"""Controlled classification vocabulary for TAIICO's financial movements."""

FINANCE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "Ingresos por seguros": (
        "Comisiones de aseguradoras",
        "Bonos y sobrecomisiones",
        "Recuperación de comisiones",
        "Otros ingresos por seguros",
    ),
    "Pagos a red comercial": (
        "Comisiones a agentes",
        "Comisiones a prospectadores",
        "Incentivos a la red comercial",
        "Devoluciones a la red comercial",
    ),
    "Personal y honorarios": (
        "Nómina",
        "Asimilados a salarios",
        "Prestaciones y seguridad social",
        "Honorarios profesionales",
    ),
    "Administración y oficina": (
        "Renta y mantenimiento de oficinas",
        "Servicios de oficina",
        "Papelería y suministros",
        "Mensajería y trámites",
        "Otros gastos administrativos",
    ),
    "Tecnología y comunicaciones": (
        "Software y licencias",
        "Infraestructura y nube",
        "Telefonía e internet",
        "Equipos de cómputo",
    ),
    "Comercial y relaciones": (
        "Publicidad y campañas",
        "Eventos y capacitación",
        "Atención a clientes",
        "Material promocional",
    ),
    "Viajes y representación": (
        "Transporte y movilidad",
        "Hospedaje",
        "Alimentos de trabajo",
        "Viáticos",
    ),
    "Impuestos y contribuciones": (
        "IVA",
        "ISR",
        "IMSS e INFONAVIT",
        "Impuestos locales",
        "Otros impuestos y derechos",
    ),
    "Financiamiento y tarjetas": (
        "Pago de tarjeta de crédito",
        "Intereses y financiamiento",
        "Planes de pagos diferidos",
        "Créditos recibidos",
        "Amortización de créditos",
        "Comisiones bancarias",
    ),
    "Transferencias y capital": (
        "Transferencias entre cuentas TAIICO",
        "Aportaciones de socios",
        "Retiros de socios",
    ),
    "Ajustes y conciliación": (
        "Reversos de movimientos",
        "Devoluciones de proveedores",
        "Aclaraciones bancarias",
        "Movimientos por identificar",
    ),
    "Gastos no deducibles": (
        "Consumo personal",
        "Otros gastos no deducibles",
    ),
}
