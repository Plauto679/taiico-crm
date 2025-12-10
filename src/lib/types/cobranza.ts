export interface CobranzaVida {
    '# de Póliza': string | number;
    'Producto': string;
    'Conducto de Cobro': string;
    'Fecha de Pago del Recibo': string;
    'Año de Vida Póliza': number;
    'Prima Pagada': number;
    'Comisión Bruto': number;
    'Comisión Neta': number;
}

export interface CobranzaGMM {
    '# de Póliza': string | number;
    'Producto': string;
    'Conducto de Cobro': string;
    'Fecha de Pago del Recibo': string;
    'Año de Vida Póliza': number;
    'Estado': string;
    'Prima Pagada': number;
    'Comisión Bruto': number;
    'Comisión Neta': number;
    'IVA Causado': number;
}

export interface CobranzaSura {
    'Daños/Vida': string;
    'Grupo': string;
    'Oficina': string;
    'Ramo': string;
    'Póliza': string;
    'Contratante': string;
    'Clave Agente': string;
    'Tipo de Cambio': string;
    '# Recibo': string;
    'Serie de Recibo': string;
    'Prima Total': number;
    'Prima Neta': number;
    '% Comisión pagado': number;
    'Comisión de derecho': string; // Verify type
    'Monto Comisión Neta': number;
    'Total Comisión pagado': number;
    '# Liquidación': string;
    '# Comprobante': string;
    'Fecha aplicación de la póliza': string;
}

export interface CobranzaAarco {
    'CIA': string;
    'NUM_POL': string;
    'CLIENTE': string;
    'PROSPECTADOR': string;
    'F_COBRO': string;
    'PRIMA_NETA_MN': number;
    'COM_APL_MN': number;
    '% COMISION PROSPECTADOR': number;
    '$ COMISION PROSPECTADOR': number;
}
