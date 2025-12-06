import { getCobranzaVida, getCobranzaGMM } from '@/modules/cobranza/service';
import { CobranzaView } from '@/components/cobranza/CobranzaView';

export const dynamic = 'force-dynamic';

export default async function CobranzaPage() {
    const vidaData = await getCobranzaVida();
    const gmmData = await getCobranzaGMM();

    return (
        <div className="flex flex-col h-full">
            <div className="flex-none p-8 pb-4">
                <h1 className="text-2xl font-bold text-gray-900">Cobranza</h1>
            </div>
            <div className="flex-1 min-h-0 px-8 pb-8">
                <CobranzaView vidaData={vidaData} gmmData={gmmData} />
            </div>
        </div>
    );
}
