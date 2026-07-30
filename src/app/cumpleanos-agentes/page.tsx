import { CumpleanosAgentesView } from '@/components/cumpleanos-agentes/CumpleanosAgentesView';
import { getAgentBirthdayDirectory } from '@/modules/cumpleanos-agentes/service';


export const dynamic = 'force-dynamic';

export default async function CumpleanosAgentesPage() {
    const directory = await getAgentBirthdayDirectory();

    return (
        <div className="flex h-full min-h-0 flex-col">
            <div className="flex-none px-8 pb-4 pt-8">
                <h1 className="text-2xl font-bold text-white">Cumpleaños de agentes</h1>
                <p className="mt-1 text-sm text-blue-100">
                    Cumpleaños derivados del RFC de los agentes registrados en MetLife.
                </p>
            </div>
            <div className="min-h-0 flex-1 px-8 pb-8">
                <CumpleanosAgentesView directory={directory} />
            </div>
        </div>
    );
}
