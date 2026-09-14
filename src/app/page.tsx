import { HomeWidgets } from '@/components/home/HomeWidgets';
import { fetchFromApi } from '@/lib/api';
import type { HomeWidgetPreference } from '@/components/home/HomeWidgets';

export const dynamic = 'force-dynamic';

export default async function Home() {
  const preferences = await fetchFromApi<HomeWidgetPreference>('/home-widgets');
  return <div className="h-full overflow-y-auto"><div className="flex min-h-full flex-col items-center space-y-8 p-4 sm:space-y-12 sm:p-8"><div className="space-y-6 text-center"><img src="/logo.png" alt="TAIICO CRM" className="mx-auto h-24 w-auto sm:h-32" /><div className="space-y-2"><h1 className="text-4xl font-bold text-white">Bienvenido a TAIICO CRM</h1><p className="text-base text-blue-100 sm:text-xl">Selecciona un módulo para comenzar:</p></div></div><HomeWidgets initial={preferences} /></div></div>;
}
