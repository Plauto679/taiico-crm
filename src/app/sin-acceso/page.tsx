'use client';

import { ArrowLeft, Home, ShieldX } from 'lucide-react';
import { useRouter } from 'next/navigation';

export default function SinAccesoPage() {
  const router = useRouter();

  return (
    <div className="flex h-full min-h-0 items-center justify-center overflow-y-auto p-6">
      <div className="w-full max-w-xl rounded-2xl bg-white p-10 text-center shadow-2xl">
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-amber-100 text-amber-700">
          <ShieldX className="h-10 w-10" />
        </div>
        <h1 className="mt-6 text-3xl font-bold text-slate-900">
          Parece que no tienes acceso a este módulo
        </h1>
        <p className="mx-auto mt-3 max-w-md text-slate-600">
          Si necesitas utilizarlo, solicita a un administrador que habilite el permiso correspondiente desde el módulo de Accesos.
        </p>
        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
          <button
            type="button"
            onClick={() => router.back()}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 px-5 py-2.5 font-semibold text-slate-700 hover:bg-slate-50"
          >
            <ArrowLeft className="h-4 w-4" />
            Regresar
          </button>
          <button
            type="button"
            onClick={() => router.push('/')}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 font-semibold text-white hover:bg-blue-700"
          >
            <Home className="h-4 w-4" />
            Ir al inicio
          </button>
        </div>
      </div>
    </div>
  );
}
