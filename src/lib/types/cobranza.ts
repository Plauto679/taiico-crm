export interface CobranzaVida {
    '# de Póliza': string;
    'Producto': string;
    'Conducto de Cobro': string;
    'Fecha de Pago del Recibo': string; // Date YYYY-MM-DD
    'Año de Vida Póliza': number;
    'Prima Pagada': number;
    'Comisión Bruto': number;
    'Comisión Neta': number;
}

export interface CobranzaGMM {
    '# de Póliza': string;
    'Producto': string;
    'Conducto de Cobro': string;
    'Fecha de Pago del Recibo': string; // Date YYYY-MM-DD
    'Año de Vida Póliza': number;
    'Estado': string;
    'Prima Pagada': number;
    'Comisión Bruto': number;
    'Comisión Neta': number;
    'IVA Causado': number;
}

export interface CobranzaSura {
    'Daños/Vida': string;
    'Grupo': number;
    'Oficina': number;
    'Ramo': number;
    'Póliza': number;
    'Contratante': string;
    'Clave Agente': number;
    'Tipo de Cambio': string;
    '# Recibo': number;
    'Serie de Recibo': string;
    'Prima Total': number;
    'Prima Neta': number;
    '% Comisión pagado': number;
    'Comisión de derecho': number;
    'Monto Comisión Neta': number;
    'Total Comisión pagado': number;
    '# Liquidación': number;
    '# Comprobante': number;
    'Fecha aplicación de la póliza': string; // Date YYYY-MM-DD
}

export type CobranzaItem = CobranzaVida | CobranzaGMM | CobranzaSura;
