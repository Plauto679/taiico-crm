import { fetchFromApi } from '@/lib/api';
import { AgentBirthdayDirectory } from '@/lib/types/cumpleanosAgentes';


export async function getAgentBirthdayDirectory(): Promise<AgentBirthdayDirectory> {
    return fetchFromApi('/cumpleanos-agentes');
}
