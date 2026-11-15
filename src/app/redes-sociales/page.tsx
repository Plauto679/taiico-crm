import { SocialWorkspace, type Workspace } from '@/components/redes-sociales/SocialWorkspace';
import { fetchFromApi } from '@/lib/api';
export const dynamic = 'force-dynamic';
export default async function RedesSocialesPage(){
 const data=await fetchFromApi<Workspace>('/redes-sociales');
 return <SocialWorkspace initial={data}/>;
}
