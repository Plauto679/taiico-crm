from __future__ import annotations

import re


SINIESTROS_DOCUMENT_REQUIREMENTS = [
    "Identificación",
    "Comprobante de domicilio",
    "Informe Médico",
    "Facturas",
    "Finiquito",
]


GMM_DOCUMENT_REQUIREMENTS: dict[str, list[str]] = {
    "EMISION PERSONA FISICA": [
        "Solicitud Única Digital",
        "Carta Firma Solicitud Única Digital Sign Now",
        "Identificación oficial",
        "Comprobante de domicilio",
        "Cotización",
        "Documentos adicionales",
        "Carta Reconocimiento de antigüedad o carátula de la póliza anterior",
        "Carta de no periodo al descubierto en reconocimiento de antigüedad",
    ],
    "EMISION PERSONA MORAL": [
        "Solicitud Única Digital (SUD)",
        "Carta Firma Solicitud Única Digital Sign Now",
        "Identificación oficial",
        "Cédula Fiscal de la empresa",
        "Comprobante de domicilio de la empresa",
        "Cotización",
        "Documentos adicionales",
        "Carta Reconocimiento de antigüedad o carátula de la póliza anterior",
        "Carta de no periodo al descubierto en reconocimiento de antigüedad",
        "Articulo 492",
    ],
    "Modificación de nombre y apellidos GMM": ["Solicitud de Cambios", "Acta de Nacimiento", "Identificación Oficial Vigente", "Formato 5"],
    "Cambio de contratante GMM": ["Solicitud de Cambios", "Cédula Fiscal", "Identificación Oficial Vigente", "Formato 5"],
    "Cambio de domicilio GMM": ["Solicitud de Cambios", "Comprobante de domicilio", "Identificación Oficial Vigente", "Formato 5", "Constancia de situacion fiscal"],
    "Corrección RFC GMM": ["Solicitud de Cambios", "Cédula Fiscal", "Identificación Oficial Vigente", "Formato 5"],
    "Cambio de beneficiario GMM": ["Solicitud de Cambios", "Formato de Beneficiarios", "Identificación Oficial Vigente"],
    "Duplicado de póliza GMM": ["Solicitud de Cambios", "Identificación Oficial Vigente"],
    "Duplicado de endoso GMM": ["Solicitud de Cambios", "Identificación Oficial Vigente"],
    "Cambio clave de agente": ["Solicitud de Cambios", "Identificación Oficial Vigente", "Carta Cliente"],
    "Reconocimiento de antigüedad": ["Solicitud de Cambios", "Identificación Oficial Vigente", "Caratula de Póliza", "Carta de Antigüedad"],
    "Rehabilitación GMM": ["Solicitud de Cambios", "Formato de Rehabilitación", "Identificación Oficial Vigente", "Comprobante de Domicilio", "Caratula de Póliza", "Carta no Siniestro por asegurado", "Comprobante de pago"],
    "Cambio de conducto de cobro (Débito o crédito)": ["Solicitud de Cambios", "Instrucción de pago de Primas", "Identificación Oficial Vigente"],
    "Cambio de conducto de cobro (Conducto Agente)": ["Solicitud de Cambios", "Caratula de poliza", "Identificación Oficial Vigente"],
    "Cambio de forma de pago GMM": ["Solicitud de Cambios", "Identificación Oficial Vigente", "Caratula de Póliza"],
    "Inclusión/Exclusión De Coberturas GMM": ["Solicitud de Cambios", "Identificación Oficial Vigente", "Nueva Cotización", "Caratula de Póliza", "Alta de recien nacido"],
    "Inclusión/Exclusión De Dependientes GMM": ["Solicitud de Cambios", "Solicitud GMM", "Identificación Oficial Vigente", "Comprobante de Domicilio", "Nueva Cotización", "Caratula de Póliza"],
    "Cancelación de pólizas GMM": ["Solicitud de Cambios", "Identificación Oficial Vigente", "Caratula de Póliza", "Validacion INE", "Estado de cuenta"],
    "Aclaración de pagos GMM": ["Solicitud de Cambios", "Identificación Oficial Vigente", "Comprobante de Pago"],
    "Aplicación de pagos GMM": ["Recibo", "Escrito de aplicación de pago"],
    "Reembolso GMM": ["Formato de cambios", "Informe medico", "Facturas", "Resultados de auxiliares del Dr.", "Identificación oficial", "Comprobante de domicilio", "Edo de cuenta bancario", "Otro"],
}


VIDA_DOCUMENT_REQUIREMENTS: dict[str, list[str]] = {
    "EMISION PERSONA FISICA": ["Solicitud Única Digital", "Carta Firma Solicitud Única Digital Sign Now", "Identificación oficial", "Comprobante de domicilio", "Cotización", "Documentos adicionales", "Carta Reconocimiento de antigüedad o carátula de la póliza anterior"],
    "EMISION PERSONA MORAL": ["Solicitud Única Digital (SUD)", "Carta Firma Solicitud Única Digital Sign Now", "Identificación oficial", "Cédula Fiscal de la empresa", "Comprobante de domicilio de la empresa", "Cotización", "Documentos adicionales", "Articulo 492"],
    "Modificación de nombre y apellidos VIDA": ["Solicitud de Cambios", "Acta de Nacimiento", "Identificación Oficial Vigente", "Formato 5"],
    "Cambio de contratante VIDA": ["Solicitud de Cambios", "Cédula Fiscal", "Identificación Oficial Vigente", "Formato 5"],
    "Cambio de domicilio VIDA": ["Solicitud de Cambios", "Comprobante de domicilio", "Identificación Oficial Vigente", "Formato 5", "Constancia de situacion fiscal"],
    "Corrección RFC VIDA": ["Solicitud de Cambios", "Cédula Fiscal", "Identificación Oficial Vigente", "Formato 5"],
    "Cambio de beneficiario VIDA": ["Solicitud de Cambios", "Formato de Beneficiarios", "Identificación Oficial Vigente"],
    "Duplicado de póliza GMM": ["Solicitud de Cambios", "Identificación Oficial Vigente"],
    "Cambio clave de agente VIDA": ["Solicitud de Cambios", "Identificación Oficial Vigente", "Carta Cliente"],
    "Rehabilitación VIDA": ["Solicitud de Cambios", "Formato de Rehabilitación", "Identificación Oficial Vigente", "Comprobante de Domicilio", "Caratula de Póliza", "Carta no Siniestro por asegurado", "Comprobante de pago"],
    "Cambio de conducto de cobro (Débito o crédito)": ["Solicitud de Cambios", "Instrucción de pago de Primas", "Identificación Oficial Vigente"],
    "Cambio de conducto de cobro (Conducto Agente)": ["Solicitud de Cambios", "Caratula de poliza", "Identificación Oficial Vigente"],
    "Duplicado de recibo VIDA": ["Solicitud de Cambios", "Identificación Oficial Vigente"],
    "Cambio de forma de pago VIDA": ["Solicitud de Cambios", "Identificación Oficial Vigente", "Caratula de Póliza"],
    "Corrección de edad / Corrección fecha de nacimiento VIDA": ["Solicitud de Cambios", "Identificación Oficial Vigente", "Formato 5", "Acta de Nacimiento"],
    "Inclusión/Exclusión De Coberturas VIDA": ["Solicitud de Cambios", "Identificación Oficial Vigente", "Nueva Cotización", "Caratula de Póliza"],
    "Rescate total / parcial VIDA": ["Solicitud de Cambios", "Tabla de valores Garantizados", "Identificación Oficial Vigente", "Comprobante de Domicilio", "Caratula de Póliza", "Estado de cuenta", "Validacion INE"],
    "Devolución de primas VIDA": ["Solicitud de Cambios", "Identificación Oficial Vigente", "Comprobante de Pago"],
    "Aclaración de pagos VIDA": ["Solicitud de Cambios", "Identificación Oficial Vigente", "Comprobante de Pago"],
    "Aplicación de pagos VIDA": ["Recibo", "Escrito de aplicación de pago"],
}


def split_request_types(request_types: str) -> list[str]:
    return [
        " ".join(value.split())
        for value in re.split(r"\s*(?:,|&|\|)\s*", request_types)
        if value.strip()
    ]


def requirements_for(classification: str, request_type: str) -> list[str]:
    catalog = GMM_DOCUMENT_REQUIREMENTS if classification.strip().casefold() == "gmm" else VIDA_DOCUMENT_REQUIREMENTS
    combined: list[str] = []
    seen: set[str] = set()
    for selected_request in split_request_types(request_type):
        for document in catalog.get(selected_request, []):
            key = " ".join(document.split()).casefold()
            if key not in seen:
                seen.add(key)
                combined.append(document)
    return combined
