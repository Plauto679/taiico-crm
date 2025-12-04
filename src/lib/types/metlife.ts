export interface MetlifeVidaRaw {
  "# de Póliza": number;
  "Clave del Agente": number;
  Producto: string;
  "Conducto de Cobro": string;
  MSI: string;
  "Estatus Recibo": string;
  "Fecha de Pago del Recibo": number | string; // Excel dates can be numbers or strings
  "Estatus Póliza": string;
  "Año de Vida Póliza": number;
  "Edad Asegurado": number;
  "Prima Pagada": string; // Note: Prompt says string for Vida
  "Comisión Bruto": number;
  "Comisión Neta": number;
}

export interface MetlifeGMMRaw {
  "# de Póliza": number;
  "Clave del Agente": number;
  Producto: string;
  "Conducto de Cobro": string;
  MSI: string;
  "Estatus Recibo": string;
  "Fecha de Pago del Recibo": number | string;
  Ramo: number;
  "Estatus Póliza": string;
  "Año de Vida Póliza": number;
  "Edad Asegurado": number;
  Género: string;
  Estado: string;
  "Tipo de Comisión": string;
  "Prima Pagada": number; // Note: Prompt says float for GMM
  "Comisión Bruto": number;
  "Comisión Neta": number;
  "IVA Causado": number;
}

// Normalized Interfaces (for internal use)
export interface MetlifePolicy {
  poliza: string;
  agente: string;
  producto: string;
  conducto: string;
  estatusRecibo: string;
  fechaPago: Date | null;
  estatusPoliza: string;
  primaPagada: number;
  comisionNeta: number;
  type: 'VIDA' | 'GMM';
}
