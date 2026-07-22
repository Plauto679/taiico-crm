import { ReclutaView } from '@/components/recluta/ReclutaView';
import { getReclutaProspects } from '@/modules/recluta/service';


export const dynamic = 'force-dynamic';

export default async function ReclutaPage() {
    const source = await getReclutaProspects();

    return (
        <div className="flex h-full flex-col">
            <div className="flex-none px-8 pb-4 pt-8">
                <h1 className="text-2xl font-bold text-white">Recluta</h1>
                <p className="mt-1 text-sm text-blue-100">
                    Seguimiento de prospectos a agentes y sus documentos.
                </p>
            </div>
            <div className="min-h-0 flex-1 px-8 pb-8">
                <ReclutaView initialSource={source} />
            </div>
        </div>
    );
}
