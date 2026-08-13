import { fetchFromApi } from '@/lib/api';

export type Collaborator = { id: string; nombre_completo: string; inicio_colaboracion: string; dias_colaborando: number; expediente: string; puesto: string; area: string; tipo_relacion: string; estatus: string; dias_vacaciones_anuales: number; dias_vacaciones_usados: number; dias_vacaciones_disponibles: number; notas: string };
export type Vacation = { id: string; collaborator_id: string; nombre_completo: string; fecha_inicio: string; fecha_fin: string; dias: number; estatus: string; comentarios: string };
export type CollaboratorInput = Omit<Collaborator, 'id' | 'dias_colaborando' | 'dias_vacaciones_usados' | 'dias_vacaciones_disponibles'>;
export type VacationInput = { collaborator_id: string; fecha_inicio: string; fecha_fin: string; estatus: string; comentarios: string };

export async function getHrData() { return fetchFromApi<{ collaborators: Collaborator[]; vacations: Vacation[]; source_url: string }>('/rrhh'); }
export async function createCollaborator(payload: CollaboratorInput) { return (await fetchFromApi<{ collaborator: Collaborator }>('/rrhh/collaborators', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })).collaborator; }
export async function updateCollaborator(id: string, payload: CollaboratorInput) { return (await fetchFromApi<{ collaborator: Collaborator }>(`/rrhh/collaborators/${encodeURIComponent(id)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })).collaborator; }
export async function createVacation(payload: VacationInput) { return (await fetchFromApi<{ vacation: Vacation }>('/rrhh/vacations', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })).vacation; }
