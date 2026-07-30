import { fetchFromApi } from '@/lib/api';
import { BirthdayDirectory } from '@/lib/types/cumpleanos';


export async function getBirthdayDirectory(): Promise<BirthdayDirectory> {
    return fetchFromApi('/cumpleanos/clientes');
}
