import { SmartLink } from '@/components/navigation/SmartLink';
import { DollarSign, Calendar, CakeSlice, PartyPopper, ClipboardList, Users, BarChart3, Briefcase, Mail, UserRoundSearch, DatabaseZap, UserCog, FilePenLine, ScrollText, ContactRound, Megaphone, UserRoundCog } from 'lucide-react';
import { fetchFromApi } from '@/lib/api';

export default async function Home() {
  const session = await fetchFromApi<{
    module_permissions: Record<string, string>;
  }>('/session');
  return (
    <div className="h-full overflow-y-auto">
      <div className="flex min-h-full flex-col items-center space-y-8 p-4 sm:space-y-12 sm:p-8">
      <div className="text-center space-y-6">
        <img
          src="/logo.png"
          alt="TAIICO CRM"
          className="mx-auto h-24 w-auto sm:h-32"
        />
        <div className="space-y-2">
          <h1 className="text-4xl font-bold text-white">Bienvenido a TAIICO CRM</h1>
          <p className="text-base text-blue-100 sm:text-xl">Seleccione un módulo para comenzar:</p>
        </div>
      </div>

      <div className="grid w-full max-w-6xl grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-8 lg:grid-cols-4">
        <SmartLink href="/cobranza" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-blue-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="rounded-full bg-blue-100 p-4 text-blue-600 group-hover:bg-blue-600 group-hover:text-white transition-colors duration-300">
              <DollarSign className="h-8 w-8" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Cobranza</h2>
              <p className="text-gray-500 mt-2">Gestión de pagos y comisiones</p>
            </div>
          </div>
        </SmartLink>

        <SmartLink href="/renovaciones" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-green-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="rounded-full bg-green-100 p-4 text-green-600 group-hover:bg-green-600 group-hover:text-white transition-colors duration-300">
              <Calendar className="h-8 w-8" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Renovaciones</h2>
              <p className="text-gray-500 mt-2">Próximos vencimientos y agenda</p>
            </div>
          </div>
        </SmartLink>

        {['lectura', 'operacion'].includes(session.module_permissions.cumpleanos || '') && (
          <SmartLink href="/cumpleanos" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-pink-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
            <div className="flex flex-col items-center text-center space-y-4">
              <div className="rounded-full bg-pink-100 p-4 text-pink-600 group-hover:bg-pink-600 group-hover:text-white transition-colors duration-300">
                <CakeSlice className="h-8 w-8" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-gray-900">Cumpleaños</h2>
                <p className="text-gray-500 mt-2">Clientes, pólizas y agentes</p>
              </div>
            </div>
          </SmartLink>
        )}

        {['lectura', 'operacion'].includes(session.module_permissions.cumpleanos_agentes || '') && (
          <SmartLink href="/cumpleanos-agentes" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-violet-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
            <div className="flex flex-col items-center text-center space-y-4">
              <div className="rounded-full bg-violet-100 p-4 text-violet-600 group-hover:bg-violet-600 group-hover:text-white transition-colors duration-300">
                <PartyPopper className="h-8 w-8" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-gray-900">Cumpleaños de agentes</h2>
                <p className="text-gray-500 mt-2">Agentes, claves y promotorías</p>
              </div>
            </div>
          </SmartLink>
        )}

        {['lectura', 'operacion'].includes(session.module_permissions.agentes || '') && (
          <SmartLink href="/agentes" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-blue-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
            <div className="flex flex-col items-center text-center space-y-4">
              <div className="rounded-full bg-blue-100 p-4 text-blue-700 group-hover:bg-blue-700 group-hover:text-white transition-colors duration-300"><UserRoundCog className="h-8 w-8" /></div>
              <div><h2 className="text-2xl font-bold text-gray-900">Agentes</h2><p className="text-gray-500 mt-2">Claves, cédulas y estatus MetLife</p></div>
            </div>
          </SmartLink>
        )}

        <SmartLink href="/pendientes" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-cyan-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="rounded-full bg-cyan-100 p-4 text-cyan-600 group-hover:bg-cyan-600 group-hover:text-white transition-colors duration-300">
              <ClipboardList className="h-8 w-8" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Pendientes</h2>
              <p className="text-gray-500 mt-2">Emisión, servicios y siniestros</p>
            </div>
          </div>
        </SmartLink>

        <SmartLink href="/cartera" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-purple-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="rounded-full bg-purple-100 p-4 text-purple-600 group-hover:bg-purple-600 group-hover:text-white transition-colors duration-300">
              <Briefcase className="h-8 w-8" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Cartera de Prospectadores</h2>
              <p className="text-gray-500 mt-2">Asignación de prospectadores por póliza</p>
            </div>
          </div>
        </SmartLink>
        <SmartLink href="/clientes" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-pink-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="rounded-full bg-pink-100 p-4 text-pink-600 group-hover:bg-pink-600 group-hover:text-white transition-colors duration-300">
              <Users className="h-8 w-8" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Clientes</h2>
              <p className="text-gray-500 mt-2">Directorio de contactos</p>
            </div>
          </div>
        </SmartLink>

        <SmartLink href="/recluta" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-indigo-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="rounded-full bg-indigo-100 p-4 text-indigo-600 group-hover:bg-indigo-600 group-hover:text-white transition-colors duration-300">
              <UserRoundSearch className="h-8 w-8" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Recluta</h2>
              <p className="text-gray-500 mt-2">Seguimiento de prospectos a agentes</p>
            </div>
          </div>
        </SmartLink>

        <SmartLink href="/dashboards" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-orange-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="rounded-full bg-orange-100 p-4 text-orange-600 group-hover:bg-orange-600 group-hover:text-white transition-colors duration-300">
              <BarChart3 className="h-8 w-8" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Dashboards</h2>
              <p className="text-gray-500 mt-2">Visualización de datos y métricas</p>
            </div>
          </div>
        </SmartLink>

        <SmartLink href="/configuracion-mail" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-sky-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="rounded-full bg-sky-100 p-4 text-sky-600 group-hover:bg-sky-600 group-hover:text-white transition-colors duration-300">
              <Mail className="h-8 w-8" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Configuración de Mail</h2>
              <p className="text-gray-500 mt-2">Cuenta remitente y conexión SMTP</p>
            </div>
          </div>
        </SmartLink>

        {session.module_permissions.carga_bases === 'operacion' && (
          <SmartLink href="/carga-bases" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-emerald-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
            <div className="flex flex-col items-center text-center space-y-4">
              <div className="rounded-full bg-emerald-100 p-4 text-emerald-600 group-hover:bg-emerald-600 group-hover:text-white transition-colors duration-300">
                <DatabaseZap className="h-8 w-8" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-gray-900">Carga de bases</h2>
                <p className="text-gray-500 mt-2">Actualización controlada de pólizas</p>
              </div>
            </div>
          </SmartLink>
        )}

        {session.module_permissions.accesos === 'operacion' && (
          <SmartLink href="/accesos" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-slate-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
            <div className="flex flex-col items-center text-center space-y-4">
              <div className="rounded-full bg-slate-100 p-4 text-slate-600 group-hover:bg-slate-700 group-hover:text-white transition-colors duration-300">
                <UserCog className="h-8 w-8" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-gray-900">Accesos</h2>
                <p className="text-gray-500 mt-2">Usuarios, roles y permisos</p>
              </div>
            </div>
          </SmartLink>
        )}
        {['lectura', 'operacion'].includes(session.module_permissions.cotizaciones || '') && (
          <SmartLink href="/cotizaciones" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-blue-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
            <div className="flex flex-col items-center text-center space-y-4">
              <div className="rounded-full bg-blue-100 p-4 text-blue-600 group-hover:bg-blue-600 group-hover:text-white transition-colors duration-300"><FilePenLine className="h-8 w-8" /></div>
              <div><h2 className="text-2xl font-bold text-gray-900">Cotizaciones</h2><p className="text-gray-500 mt-2">Prospectos, productos y seguimiento</p></div>
            </div>
          </SmartLink>
        )}
        {['lectura', 'operacion'].includes(session.module_permissions.logs || '') && (
          <SmartLink href="/logs" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-amber-400 hover:shadow-2xl hover:scale-105 transition-all duration-300">
            <div className="flex flex-col items-center text-center space-y-4"><div className="rounded-full bg-amber-100 p-4 text-amber-700 group-hover:bg-amber-600 group-hover:text-white transition-colors duration-300"><ScrollText className="h-8 w-8" /></div><div><h2 className="text-2xl font-bold text-gray-900">Logs</h2><p className="text-gray-500 mt-2">Auditoría de usuarios y cambios</p></div></div>
          </SmartLink>
        )}
        {['lectura', 'operacion'].includes(session.module_permissions.rrhh || '') && (
          <SmartLink href="/rrhh" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-teal-400 hover:shadow-2xl hover:scale-105 transition-all duration-300"><div className="flex flex-col items-center text-center space-y-4"><div className="rounded-full bg-teal-100 p-4 text-teal-700 group-hover:bg-teal-600 group-hover:text-white transition-colors duration-300"><ContactRound className="h-8 w-8" /></div><div><h2 className="text-2xl font-bold text-gray-900">RRHH</h2><p className="text-gray-500 mt-2">Colaboradores, contratos y vacaciones</p></div></div></SmartLink>
        )}
        {['lectura', 'operacion'].includes(session.module_permissions.campanas || '') && (
          <SmartLink href="/campanas" className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg hover:border-rose-400 hover:shadow-2xl hover:scale-105 transition-all duration-300"><div className="flex flex-col items-center text-center space-y-4"><div className="rounded-full bg-rose-100 p-4 text-rose-700 group-hover:bg-rose-600 group-hover:text-white transition-colors duration-300"><Megaphone className="h-8 w-8" /></div><div><h2 className="text-2xl font-bold text-gray-900">Campañas</h2><p className="text-gray-500 mt-2">Audiencias, mensajes y resultados</p></div></div></SmartLink>
        )}
      </div>
      </div>
    </div>
  );
}
