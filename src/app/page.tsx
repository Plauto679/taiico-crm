import Link from 'next/link';
import { DollarSign, Calendar, Users } from 'lucide-react';

export default function Home() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-900">Bienvenido a TAIICO CRM</h1>
      <p className="text-gray-600">Seleccione un módulo para comenzar:</p>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <Link href="/cobranza" className="group block rounded-lg border bg-white p-6 shadow-sm hover:border-blue-500 hover:shadow-md transition-all">
          <div className="flex items-center space-x-4">
            <div className="rounded-full bg-blue-100 p-3 text-blue-600 group-hover:bg-blue-600 group-hover:text-white transition-colors">
              <DollarSign className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Cobranza</h2>
              <p className="text-sm text-gray-500">Gestión de pagos y comisiones</p>
            </div>
          </div>
        </Link>

        <Link href="/renovaciones" className="group block rounded-lg border bg-white p-6 shadow-sm hover:border-green-500 hover:shadow-md transition-all">
          <div className="flex items-center space-x-4">
            <div className="rounded-full bg-green-100 p-3 text-green-600 group-hover:bg-green-600 group-hover:text-white transition-colors">
              <Calendar className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Renovaciones</h2>
              <p className="text-sm text-gray-500">Próximos vencimientos y agenda</p>
            </div>
          </div>
        </Link>

        <Link href="/cartera" className="group block rounded-lg border bg-white p-6 shadow-sm hover:border-purple-500 hover:shadow-md transition-all">
          <div className="flex items-center space-x-4">
            <div className="rounded-full bg-purple-100 p-3 text-purple-600 group-hover:bg-purple-600 group-hover:text-white transition-colors">
              <Users className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Cartera</h2>
              <p className="text-sm text-gray-500">Perfiles de clientes y pólizas</p>
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}
