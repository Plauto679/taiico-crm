import { ClientesView } from '@/components/clientes/ClientesView';
import { getClients } from '@/modules/clientes/service';

export const dynamic = 'force-dynamic';

export default async function ClientesPage() {
    const clients = await getClients();

    return (
        <div className="flex flex-col h-full">
            <div className="flex-none p-8 pb-4">
                <h1 className="text-2xl font-bold text-white mb-4">Cartera de Clientes</h1>
            </div>

            <div className="flex-1 min-h-0 px-8 pb-8">
                <ClientesView initialClients={clients} />
            </div>
        </div>
    );
}
