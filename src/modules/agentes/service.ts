import { fetchFromApi } from '@/lib/api';

export type Agent = {
  row_number: number;
  fingerprint: string;
  nombre: string;
  nombres: string;
  apellido_paterno: string;
  apellido_materno: string;
  clave_arranque: string;
  clave_definitiva: string;
  promotoria: string;
  rfc: string;
  telefono_particular: string;
  correo_personal: string;
  inicio_vigencia_cedula: string;
  fin_vigencia_cedula: string;
  clasificacion_comercial: string;
  estatus_met: string;
};

export type AgentInput = Omit<Agent, 'row_number' | 'fingerprint' | 'nombre'>;

export type AgentDirectory = {
  version: string;
  can_operate: boolean;
  source_url: string;
  agents: Agent[];
  catalogs: {
    promotorias: string[];
    clasificaciones: string[];
    estatus_met: string[];
  };
};

export async function getAgents(): Promise<AgentDirectory> {
  return fetchFromApi<AgentDirectory>('/agentes');
}

export async function createAgent(payload: AgentInput, version: string): Promise<AgentDirectory> {
  return fetchFromApi<AgentDirectory>('/agentes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, version }),
  });
}

export async function updateAgent(agent: Agent, payload: AgentInput, version: string): Promise<AgentDirectory> {
  return fetchFromApi<AgentDirectory>(`/agentes/${agent.row_number}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, version, fingerprint: agent.fingerprint }),
  });
}
