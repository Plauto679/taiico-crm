import { fetchFromApi } from '@/lib/api';

export type Quote = {
  id: string;
  cliente: string;
  rfc: string;
  ramo: string;
  producto: string;
  estatus: string;
  cotizaciones: string;
  agente: string;
  promotoria: string;
  aseguradora: string;
  clave_agente: string;
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
