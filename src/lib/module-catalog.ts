import { Home, ArchiveRestore, BarChart3, Briefcase, CakeSlice, Calendar, ChartNoAxesCombined, ClipboardList, ContactRound, DatabaseZap, DollarSign, FilePenLine, HandCoins, Landmark, Mail, MailCheck, Megaphone, PartyPopper, ScrollText, UserCog, UserRoundCog, UserRoundSearch, Users } from 'lucide-react';

// Shared by navigation and home cards; keys match backend/services/auth.py.
export const MODULE_CATALOG = [
  ['inicio', 'Inicio', '/', 'Módulos disponibles', Home],
  ['cobranza', 'Cobranza', '/cobranza', 'Gestión de pagos y comisiones', DollarSign],
  ['renovaciones', 'Renovaciones', '/renovaciones', 'Próximos vencimientos y agenda', Calendar],
  ['cumpleanos', 'Cumpleaños de clientes', '/cumpleanos', 'Clientes, pólizas y agentes', CakeSlice],
  ['cumpleanos_agentes', 'Cumpleaños de agentes', '/cumpleanos-agentes', 'Agentes, claves y promotorías', PartyPopper],
  ['agentes', 'Agentes', '/agentes', 'Claves, cédulas y estatus MetLife', UserRoundCog],
  ['pendientes', 'Pendientes', '/pendientes', 'Emisión, servicios y siniestros', ClipboardList],
  ['cartera', 'Cartera de Prospectadores', '/cartera', 'Asignación por póliza', Briefcase],
  ['prospectadores', 'Prospectadores', '/prospectadores', 'Catálogo, pagos y cartera', UserRoundSearch],
  ['cobranza_prospectadores', 'Cobranza para prospectadores', '/cobranza-prospectadores', 'Comisiones y distribución mensual', HandCoins],
  ['estados_agentes', 'Estados de Prospectadores', '/estados-prospectadores', 'Estados de cuenta y pagos', ScrollText],
  ['clientes', 'Clientes', '/clientes', 'Directorio de contactos', Users],
  ['recluta', 'Recluta', '/recluta', 'Seguimiento de prospectos a agentes', UserRoundSearch],
  ['dashboards', 'Dashboards', '/dashboards', 'Datos y métricas', BarChart3],
  ['configuracion_mail', 'Configuración de Mail', '/configuracion-mail', 'Cuenta remitente y conexión SMTP', Mail],
  ['mails_automaticos', 'Mails automáticos', '/mails-automaticos', 'Programación y destinatarios', MailCheck],
  ['carga_bases', 'Carga de bases', '/carga-bases', 'Actualización controlada de pólizas', DatabaseZap],
  ['time_machine', 'Time Machine', '/time-machine', 'Consulta y restaura respaldos', ArchiveRestore],
  ['accesos', 'Accesos', '/accesos', 'Usuarios, roles y permisos', UserCog],
  ['cotizaciones', 'Cotizaciones', '/cotizaciones', 'Prospectos, productos y seguimiento', FilePenLine],
  ['gestion_comercial', 'Gestión Comercial', '/gestion-comercial', 'Oportunidades y seguimiento', ChartNoAxesCombined],
  ['logs', 'Logs', '/logs', 'Auditoría de usuarios y cambios', ScrollText],
  ['rrhh', 'RRHH', '/rrhh', 'Colaboradores, contratos y vacaciones', ContactRound],
  ['campanas', 'Campañas', '/campanas', 'Audiencias, mensajes y resultados', Megaphone],
  ['finanzas', 'Finanzas', '/finanzas', 'Movimientos, presupuestos y proyecciones', Landmark],
] as const;

export function canShowModule(key: string, permissions: Record<string, string> | null): boolean {
  return key === 'inicio' || permissions?.[key] === 'lectura' || permissions?.[key] === 'operacion';
}
