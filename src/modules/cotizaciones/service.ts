import { fetchFromApi } from '@/lib/api';

export type Quote = {
  id: string;
  cliente: string;
  rfc: string;
  ramo: string;
  producto: string;
  estatus: string;
  cotizaciones: string;
};

export type QuoteClient = { id: string; nombre: string; rfc: string };
export type QuoteCreate = {
  client_id?: string;
  prospect_name?: string;
  ramo: string;
  producto: string;
};

export async function getQuotes(): Promise<Quote[]> {
  const response = await fetchFromApi<{ quotes: Quote[] }>('/cotizaciones');
  return response.quotes;
}

export async function getQuoteConfig() {
  return fetchFromApi<{ products: Record<string, string[]>; initial_status: string }>('/cotizaciones/config');
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
