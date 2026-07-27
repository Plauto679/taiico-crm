'use client';

import Link from 'next/link';
import { useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Home, DollarSign, Calendar, ClipboardList, Users, BarChart3, Briefcase, Mail, UserRoundSearch, PanelLeftClose, PanelLeftOpen, LogOut, KeyRound } from 'lucide-react';

const NAV_ITEMS = [
    { name: 'Inicio', href: '/', icon: Home },
    { name: 'Cobranza', href: '/cobranza', icon: DollarSign },
    { name: 'Renovaciones', href: '/renovaciones', icon: Calendar },
    { name: 'Pendientes', href: '/pendientes', icon: ClipboardList },
    { name: 'Cartera', href: '/cartera', icon: Briefcase },
    { name: 'Clientes', href: '/clientes', icon: Users },
    { name: 'Recluta', href: '/recluta', icon: UserRoundSearch },
    { name: 'Dashboards', href: '/dashboards', icon: BarChart3 },
    { name: 'Configuración de Mail', href: '/configuracion-mail', icon: Mail },
];

export function Sidebar() {
    const [collapsed, setCollapsed] = useState(false);
    const [loggingOut, setLoggingOut] = useState(false);
    const pathname = usePathname();
    const router = useRouter();

    if (pathname === '/login' || pathname === '/olvide-password' || pathname === '/restablecer-password') return null;

    async function handleLogout() {
        if (loggingOut) return;
        setLoggingOut(true);
        try {
            await fetch('/api/logout', {
                method: 'POST',
                credentials: 'same-origin',
                cache: 'no-store',
            });
        } finally {
            window.localStorage.removeItem('taiico_last_activity');
            router.replace('/login');
            router.refresh();
        }
    }

    return (
        <aside className={`relative flex h-screen shrink-0 flex-col border-r bg-white transition-[width] duration-200 ${collapsed ? 'w-20' : 'w-64'}`}>
            <div className="flex h-40 flex-col items-center justify-center gap-2 border-b px-3">
                <img src="/logo.png" alt="TAIICO CRM" className={`w-auto transition-all ${collapsed ? 'h-12' : 'h-20'}`} />
                <button
                    type="button"
                    onClick={handleLogout}
                    disabled={loggingOut}
                    className={`flex items-center justify-center rounded-md px-2 py-1.5 text-sm font-medium text-slate-500 hover:bg-red-50 hover:text-red-700 disabled:opacity-50 ${collapsed ? '' : 'w-full'}`}
                    aria-label="Cerrar sesión"
                    title="Cerrar sesión"
                >
                    <LogOut className={`h-4 w-4 ${collapsed ? '' : 'mr-2'}`} />
                    {!collapsed && <span>{loggingOut ? 'Cerrando...' : 'Cerrar sesión'}</span>}
                </button>
                <Link
                    href="/cambiar-password"
                    className={`flex items-center justify-center rounded-md px-2 py-1.5 text-sm font-medium text-slate-500 hover:bg-blue-50 hover:text-blue-700 ${collapsed ? '' : 'w-full'}`}
                    aria-label="Cambiar contraseña"
                    title="Cambiar contraseña"
                >
                    <KeyRound className={`h-4 w-4 ${collapsed ? '' : 'mr-2'}`} />
                    {!collapsed && <span>Cambiar contraseña</span>}
                </Link>
                <button
                    type="button"
                    onClick={() => setCollapsed((current) => !current)}
                    className="absolute -right-3 top-4 z-20 rounded-full border border-slate-200 bg-white p-1.5 text-slate-500 shadow-md hover:bg-slate-50 hover:text-slate-800"
                    aria-label={collapsed ? 'Mostrar barra lateral' : 'Ocultar barra lateral'}
                    title={collapsed ? 'Mostrar barra lateral' : 'Ocultar barra lateral'}
                >
                    {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
                </button>
            </div>
            <nav className="flex-1 space-y-1 px-2 py-4">
                {NAV_ITEMS.map((item) => (
                    <Link
                        key={item.name}
                        href={item.href}
                        className={`group flex items-center rounded-md py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 hover:text-gray-900 ${collapsed ? 'justify-center px-2' : 'px-2'}`}
                        title={collapsed ? item.name : undefined}
                    >
                        <item.icon className={`h-5 w-5 shrink-0 text-gray-400 group-hover:text-gray-500 ${collapsed ? '' : 'mr-3'}`} />
                        {!collapsed && <span>{item.name}</span>}
                    </Link>
                ))}
            </nav>
        </aside>
    );
}
