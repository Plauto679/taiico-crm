import { fetchFromApi } from '@/lib/api';

export type Campaign = {
  id: string;
  nombre: string;
  asunto: string;
  cuerpo: string;
  estatus: string;
  deducible_minimo: number;
  creado_por: string;
  created_at: string;
  updated_at: string;
};

export type CampaignInput = Pick<Campaign, 'nombre' | 'asunto' | 'cuerpo' | 'deducible_minimo'>;

export type AudienceRow = {
  key: string;
  source_row: number;
  numero_poliza: string;
  rfc: string;
  nombre_cliente: string;
  nombre_producto: string;
  fecha_fin_vigencia: string;
  deducible: number;
  agente: string;
  email: string;
  multiple_policies: boolean;
};

export type CampaignAudience = {
  rows: AudienceRow[];
  summary: {
    policies: number;
    unique_clients: number;
    clients_with_email: number;
    clients_missing_email: number;
    clients_with_multiple_policies: number;
    rows_without_rfc: number;
  };
  generated_on: string;
  segment: { source: string; vigencia: string; deducible_minimo: number };
};

export type CampaignPreview = {
  recipient: AudienceRow;
  subject: string;
  body: string;
  missing_variables: string[];
};

export type CampaignDelivery = {
  id: string;
  recipient_key: string;
  numero_poliza: string;
  rfc: string;
  nombre_cliente: string;
  email: string;
  estatus: string;
  error: string;
  intentos: number;
  sent_at: string | null;
};

export type CampaignDeliveryReport = {
  deliveries: CampaignDelivery[];
  summary: {
    total: number;
    pendientes: number;
    enviando: number;
    enviados: number;
    sin_correo: number;
    variables_incompletas: number;
    rechazados: number;
    errores: number;
    entrega_incierta: number;
    rebotados: number;
  };
};

export async function getCampaigns() {
  return fetchFromApi<{ campaigns: Campaign[]; safe_variables: string[] }>('/campanas');
}

export async function createCampaign(payload: CampaignInput) {
  return (await fetchFromApi<{ campaign: Campaign }>('/campanas', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  })).campaign;
}

export async function updateCampaign(id: string, payload: CampaignInput) {
  return (await fetchFromApi<{ campaign: Campaign }>(`/campanas/${encodeURIComponent(id)}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  })).campaign;
}

export async function getCampaignAudience(id: string) {
  return fetchFromApi<CampaignAudience>(`/campanas/${encodeURIComponent(id)}/audience`);
}

export async function getCampaignPreview(id: string, recipientKey: string) {
  return fetchFromApi<CampaignPreview>(`/campanas/${encodeURIComponent(id)}/preview/${encodeURIComponent(recipientKey)}`);
}

export async function sendCampaignTest(id: string, recipientKey: string, testEmail: string) {
  return fetchFromApi<{ sent: boolean; recipient: string }>(`/campanas/${encodeURIComponent(id)}/send-test`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ recipient_key: recipientKey, test_email: testEmail }),
  });
}

export async function prepareCampaign(id: string) {
  return fetchFromApi<CampaignDeliveryReport>(`/campanas/${encodeURIComponent(id)}/prepare`, { method: 'POST' });
}

export async function getCampaignDeliveries(id: string) {
  return fetchFromApi<CampaignDeliveryReport>(`/campanas/${encodeURIComponent(id)}/deliveries`);
}

export async function sendCampaignBatch(id: string, confirmation: string, batchSize = 20) {
  return fetchFromApi<{ accepted: number; batch_size: number }>(`/campanas/${encodeURIComponent(id)}/send-batch`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirmation, batch_size: batchSize }),
  });
}

export async function reconcileCampaignBounces(id: string) {
  return fetchFromApi<CampaignDeliveryReport & { matched: number; scanned: number }>(`/campanas/${encodeURIComponent(id)}/reconcile-bounces`, { method: 'POST' });
}
