import { fetchFromApi } from '@/lib/api';
import type { QuoteAgent, QuoteClient } from '@/modules/cotizaciones/service';

export type CommercialStage = {
  id: string; code: string; name: string; position: number; conversion_rate: number;
};

export type CommercialTask = {
  id: string; title: string; description: string; status: string; priority: string;
  assigned_to: string; responsible_role: string; due_date?: string | null;
  is_required: boolean; blocks_stage_change: boolean; opportunity_id: string;
};

export type CommercialOpportunity = {
  id: string; client_id?: string | null; client_name: string; product_id?: string | null;
  product_name: string; business_line: string; owner_agent_rfc: string;
  owner_agent_name: string; owner_promotoria: string; potential_premium: number;
  currency: string; stage: CommercialStage; expected_value: number; status: string;
  priority: 'low' | 'medium' | 'high'; source: string; estimated_close_date?: string | null;
  detected_need: string; description: string; next_activity_at?: string | null;
  quote_ids: string[]; tasks: CommercialTask[]; blocking_tasks: number; created_at?: string | null;
};

export type CommercialPipeline = {
  stages: CommercialStage[];
  opportunities: CommercialOpportunity[];
  summary: {
    paid_sales: number; potential_funnel: number; expected_funnel: number;
    projection: number; active_opportunities: number;
  };
};

export type CommercialProduct = { id: string; name: string; branch: string };

export type CommercialConfig = {
  agents: QuoteAgent[];
  products: CommercialProduct[];
  can_operate: boolean;
};

export type OpportunityInput = {
  client_id?: string;
  prospect_name?: string;
  product_id?: string;
  product_name: string;
  business_line?: string;
  owner_agent_rfc: string;
  owner_agent_name: string;
  owner_promotoria: string;
  potential_premium: number;
  currency: string;
  stage_code: string;
  priority: 'low' | 'medium' | 'high';
  source?: string;
  estimated_close_date?: string;
  detected_need?: string;
  description?: string;
};

export const getCommercialPipeline = () => fetchFromApi<CommercialPipeline>('/gestion-comercial');
export const getCommercialConfig = () => fetchFromApi<CommercialConfig>('/gestion-comercial/config');

export async function createCommercialOpportunity(payload: OpportunityInput) {
  const response = await fetchFromApi<{ opportunity: CommercialOpportunity }>('/gestion-comercial/opportunities', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  return response.opportunity;
}

export async function changeCommercialStage(id: string, stageCode: string) {
  const response = await fetchFromApi<{ opportunity: CommercialOpportunity }>(`/gestion-comercial/opportunities/${encodeURIComponent(id)}/stage`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ stage_code: stageCode }),
  });
  return response.opportunity;
}

export type { QuoteClient };
