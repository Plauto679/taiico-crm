import { fetchFromApi } from '@/lib/api';

export type Quote = {
  id: string;
  cliente: string;
  rfc: string;
  ramo: string;
  producto: string;
  estatus: string;
  cotizaciones: string;
  documentos_adicionales: string;
  agente: string;
  promotoria: string;
  aseguradora: string;
  clave_agente: string;
  folder_id?: string;
  folder_name?: string;
};

export type QuoteClient = { id: string; nombre: string; rfc: string };
export type QuoteAgent = { rfc: string; name: string; promotoria: string; key: string; key_source: string };
export type QuoteCreate = {
  client_id?: string;
  prospect_name?: string;
  ramo: string;
  producto: string;
  agent_rfc?: string;
  agent_promotoria?: string;
};

export type QuoteUpdate = {
  cliente: string;
  rfc?: string;
  ramo: string;
  producto: string;
  agent_rfc?: string;
  agent_promotoria?: string;
};

export type QuoteBrowserStep = {
  step_name: string;
  status: string;
  started_at: string;
  completed_at?: string | null;
  error_message?: string | null;
  metadata?: Record<string, unknown>;
};

export type QuoteBrowserQuestionOption = {
  id: string;
  label: string;
  value?: string | null;
  description?: string;
};

export type QuoteBrowserQuestion = {
  id: string;
  text: string;
  options: QuoteBrowserQuestionOption[];
};

export type QuoteBrowserSession = {
  status: string;
  task_id: string;
  rfc: string;
  current_url?: string | null;
  steps: QuoteBrowserStep[];
  error_message?: string | null;
  prompt?: string | null;
  question?: QuoteBrowserQuestion | null;
  portal_state?: Record<string, unknown> | null;
};

export type QuoteDocumentFile = {
  id: string;
  name: string;
  mimeType: string;
  webViewLink?: string;
  modifiedTime?: string;
  size?: string;
};

export type QuoteEmailDraft = {
  quote: Quote;
  files: QuoteDocumentFile[];
  folder_link: string;
  default_recipients: string[];
  default_subject: string;
  default_body: string;
};

export type QuoteDataRequestLink = {
  token: string;
  path: string;
  expires_at: string;
  quote: Pick<Quote, 'id' | 'cliente' | 'rfc' | 'ramo' | 'producto' | 'estatus' | 'agente' | 'promotoria' | 'aseguradora'>;
};

export type QuoteDataRequestPublic = {
  token: string;
  expires_at: string;
  expired: boolean;
  submitted: boolean;
  quote: Pick<Quote, 'id' | 'cliente' | 'rfc' | 'ramo' | 'producto' | 'estatus' | 'agente' | 'promotoria' | 'aseguradora'>;
};

export async function getQuotes(): Promise<Quote[]> {
  const response = await fetchFromApi<{ quotes: Quote[] }>('/cotizaciones');
  return response.quotes;
}

export async function getQuoteConfig() {
  return fetchFromApi<{
    products: Record<string, string[]>;
    initial_status: string;
    insurer: string;
    agents: QuoteAgent[];
    agent_is_automatic: boolean;
    quotation_portal_credentials_configured: boolean;
  }>('/cotizaciones/config');
}

export async function searchQuoteClients(query: string): Promise<QuoteClient[]> {
  const response = await fetchFromApi<{ clients: QuoteClient[] }>(`/cotizaciones/clients?q=${encodeURIComponent(query)}`);
  return response.clients;
}

export async function createQuote(payload: QuoteCreate): Promise<Quote> {
  const response = await fetchFromApi<{ quote: Quote }>('/cotizaciones', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return response.quote;
}

export async function updateQuote(id: string, payload: QuoteUpdate): Promise<Quote> {
  const response = await fetchFromApi<{ quote: Quote }>(`/cotizaciones/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return response.quote;
}

export async function startQuote(id: string, rfc: string): Promise<Quote> {
  const response = await fetchFromApi<{ quote: Quote }>(`/cotizaciones/${encodeURIComponent(id)}/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rfc }),
  });
  return response.quote;
}

export async function openQuoteBrowserSession(id: string): Promise<QuoteBrowserSession> {
  const response = await fetchFromApi<{ session: QuoteBrowserSession }>(`/cotizaciones/${encodeURIComponent(id)}/browser-session`, {
    method: 'POST',
  });
  return response.session;
}

export async function answerQuoteBrowserSession(
  id: string,
  payload: { question_id: string; option_id: string; value?: string | null },
): Promise<QuoteBrowserSession> {
  const response = await fetchFromApi<{ session: QuoteBrowserSession }>(`/cotizaciones/${encodeURIComponent(id)}/browser-session/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return response.session;
}

export async function releaseQuoteBrowserSession(id: string): Promise<void> {
  await fetchFromApi<{ released: boolean; active_quote_id?: string | null }>(`/cotizaciones/${encodeURIComponent(id)}/browser-session/release`, {
    method: 'POST',
  });
}

export async function uploadQuoteDocument(
  id: string,
  documentKind: 'cotizaciones' | 'documentos_adicionales',
  file: File,
): Promise<Quote> {
  const formData = new FormData();
  formData.append('document', file);
  const response = await fetchFromApi<{ quote: Quote }>(`/cotizaciones/${encodeURIComponent(id)}/documents/${documentKind}`, {
    method: 'POST',
    body: formData,
  });
  return response.quote;
}

export async function getQuoteEmailDraft(id: string): Promise<QuoteEmailDraft> {
  return fetchFromApi<QuoteEmailDraft>(`/cotizaciones/${encodeURIComponent(id)}/quote-email-draft`);
}

export async function sendQuoteEmail(
  id: string,
  payload: { file_ids: string[]; recipients: string[]; subject: string; body: string },
): Promise<{ sent: boolean; recipients: string[]; attachment_count: number }> {
  return fetchFromApi<{ sent: boolean; recipients: string[]; attachment_count: number }>(`/cotizaciones/${encodeURIComponent(id)}/send-quote-email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function createQuoteDataRequestLink(id: string): Promise<QuoteDataRequestLink> {
  return fetchFromApi<QuoteDataRequestLink>(`/cotizaciones/${encodeURIComponent(id)}/data-request-link`, {
    method: 'POST',
  });
}

export async function getQuoteDataRequest(token: string): Promise<QuoteDataRequestPublic> {
  const response = await fetch(`/api/cotizaciones/public/data-requests/${encodeURIComponent(token)}`, {
    cache: 'no-store',
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || 'No fue posible leer la solicitud');
  }
  return response.json();
}

export async function submitQuoteDataRequest(
  token: string,
  payload: Record<string, string>,
  documents: File[],
): Promise<{ submitted: boolean; folder_link: string; uploaded_count: number; notification_sent: boolean; notification_warning?: string | null }> {
  const formData = new FormData();
  formData.append('payload', JSON.stringify(payload));
  documents.forEach((document) => formData.append('documents', document));
  const response = await fetch(`/api/cotizaciones/public/data-requests/${encodeURIComponent(token)}`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    throw new Error(errorPayload.detail || 'No fue posible enviar la solicitud');
  }
  return response.json();
}
