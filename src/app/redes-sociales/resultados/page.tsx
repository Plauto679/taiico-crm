import {SocialResults,type ResultsData} from '@/components/redes-sociales/SocialResults';
import {fetchFromApi} from '@/lib/api';
export const dynamic='force-dynamic';
export default async function ResultsPage(){return <SocialResults initial={await fetchFromApi<ResultsData>('/redes-sociales/results')}/>;}
