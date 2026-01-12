import Link from 'next/link';
import { DollarSign, Calendar, Users, BarChart3, Briefcase } from 'lucide-react';

export default function Home() {
  return (
    <div className="flex h-full flex-col items-center justify-center space-y-12 p-8">
      <div className="text-center space-y-6">
        <img
          src="/logo.png"
          alt="TAIICO CRM"
          className="mx-auto h-32 w-auto" // 100% larger than the sidebar's h-10 approx, maybe even bigger
        />
        <div className="space-y-2">
          <h1 className="text-4xl font-bold text-white">Bienvenido a TAIICO CRM</h1>
          <p className="text-xl text-blue-100">Seleccione un módulo para comenzar:</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8 md:grid-cols-2 lg:grid-cols-4 w-full max-w-6xl">
        <Link href="/cobranza" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-blue-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="rounded-full bg-blue-100 p-4 text-blue-600 group-hover:bg-blue-600 group-hover:text-white transition-colors duration-300">
              <DollarSign className="h-8 w-8" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Cobranza</h2>
              <p className="text-gray-500 mt-2">Gestión de pagos y comisiones</p>
            </div>
          </div>
        </Link>

        <Link href="/renovaciones" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-green-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="rounded-full bg-green-100 p-4 text-green-600 group-hover:bg-green-600 group-hover:text-white transition-colors duration-300">
              <Calendar className="h-8 w-8" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Renovaciones</h2>
              <p className="text-gray-500 mt-2">Próximos vencimientos y agenda</p>
            </div>
          </div>
        </Link>

        <Link href="/cartera" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-purple-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="rounded-full bg-purple-100 p-4 text-purple-600 group-hover:bg-purple-600 group-hover:text-white transition-colors duration-300">
              <Briefcase className="h-8 w-8" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Cartera</h2>
              <p className="text-gray-500 mt-2">Perfiles de clientes y pólizas</p>
            </div>
          </div>
        </Link>
        <Link href="/clientes" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-pink-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="rounded-full bg-pink-100 p-4 text-pink-600 group-hover:bg-pink-600 group-hover:text-white transition-colors duration-300">
              <Users className="h-8 w-8" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Clientes</h2>
              <p className="text-gray-500 mt-2">Directorio de contactos</p>
            </div>
          </div>
        </Link>

        <Link href="/dashboards" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-orange-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="rounded-full bg-orange-100 p-4 text-orange-600 group-hover:bg-orange-600 group-hover:text-white transition-colors duration-300">
              <BarChart3 className="h-8 w-8" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Dashboards</h2>
              <p className="text-gray-500 mt-2">Visualización de datos y métricas</p>
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}
