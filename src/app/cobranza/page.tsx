import { loadCobranzaVida, loadCobranzaGMM } from '@/modules/cobranza/service';
import { CobranzaView } from '@/components/cobranza/CobranzaView';

export const dynamic = 'force-dynamic';

export default async function CobranzaPage() {
    const vidaData = await loadCobranzaVida();
    const gmmData = await loadCobranzaGMM();

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-bold text-gray-900">Cobranza</h1>
                <button className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
                    Exportar Excel
                </button>
            </div>
            <CobranzaView vidaData={vidaData} gmmData={gmmData} />
        </div>
    );
}
