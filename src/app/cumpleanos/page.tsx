import { CumpleanosView } from '@/components/cumpleanos/CumpleanosView';
import { getBirthdayDirectory } from '@/modules/cumpleanos/service';


export const dynamic = 'force-dynamic';

export default async function CumpleanosPage() {
    const directory = await getBirthdayDirectory();

    return (
        <div className="flex h-full min-h-0 flex-col">
            <div className="flex-none px-8 pb-4 pt-8">
                <h1 className="text-2xl font-bold text-white">Cumpleaños</h1>
                <p className="mt-1 text-sm text-blue-100">
                    Cumpleaños derivados del RFC de clientes MetLife y relacionados con su agente.
                </p>
            </div>
            <div className="min-h-0 flex-1 px-8 pb-8">
                <CumpleanosView directory={directory} />
            </div>
        </div>
    );
}
