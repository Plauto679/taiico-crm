import { PoliciesView } from '@/components/polizas/PoliciesView';
import { api, Inventory, Options } from '@/modules/polizas/service';
export const dynamic='force-dynamic';
export default async function PoliciesPage(){
 const [inventory,options]=await Promise.all([api<Inventory>(''),api<Options>('/options')]);
 return <PoliciesView initial={inventory} options={options}/>;
}
