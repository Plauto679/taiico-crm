'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { PanelLeftClose, PanelLeftOpen, LogOut, KeyRound, Menu, X } from 'lucide-react';
import { MODULE_CATALOG, canShowModule } from '@/lib/module-catalog';
import { SmartLink } from '@/components/navigation/SmartLink';
import { IdleModulePrefetch } from '@/components/navigation/IdleModulePrefetch';

const SESSION_CACHE_KEY = 'taiico_session_profile';

const NAV_ITEMS = MODULE_CATALOG.flatMap<{ module: string; name: string; href: string; icon: (typeof MODULE_CATALOG)[number][4] }>(([module, name, href, , icon]) => module === 'pendientes'
    ? [{ module, name, href, icon }, { module, name: 'Mesa de control', href: '/mesa-control', icon }]
    : [{ module, name, href, icon }]);

function isPublicPath(pathname: string): boolean {
    return pathname === '/login'
        || pathname === '/olvide-password'
        || pathname === '/restablecer-password'
        || pathname.startsWith('/solicitud-datos/') || pathname.startsWith('/encuesta/');
}

export function Sidebar() {
    const [mesaAccess, setMesaAccess] = useState(false);
    const [collapsed, setCollapsed] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);
    const [loggingOut, setLoggingOut] = useState(false);
    const [permissions, setPermissions] = useState<Record<string, string> | null>(null);
    const [username, setUsername] = useState('');
    const pathname = usePathname();
    const router = useRouter();
    const publicPath = isPublicPath(pathname);

    useEffect(() => setMobileOpen(false), [pathname]);

    useEffect(() => {
        if (publicPath) return;
        let active = true;
        try {
            const cached = window.sessionStorage.getItem(SESSION_CACHE_KEY);
            if (cached) {
                const data = JSON.parse(cached);
                setPermissions(data.module_permissions || {});
                setUsername(data.username || '');
                setMesaAccess(data.mesa_access === true);
            }
        } catch {
            window.sessionStorage.removeItem(SESSION_CACHE_KEY);
        }
        let latestRequest = 0;
        const refreshPermissions = () => {
            const request = ++latestRequest;
            return fetch('/api/session', { credentials: 'same-origin', cache: 'no-store' })
                .then((response) => response.ok ? response.json() : Promise.reject())
                .then((data) => {
                    if (active && request === latestRequest) {
                        setPermissions(data.module_permissions || {});
                        setUsername(data.username || '');
                setMesaAccess(data.mesa_access === true);
                        window.sessionStorage.setItem(SESSION_CACHE_KEY, JSON.stringify({
                            module_permissions: data.module_permissions || {},
                            username: data.username || '',
                            mesa_access: data.mesa_access === true,
                        }));
                    }
                })
                .catch(() => {
                    if (active && request === latestRequest) setPermissions({});
                });
        };
        const refreshWhenVisible = () => {
            if (document.visibilityState === 'visible') void refreshPermissions();
        };
        void refreshPermissions();
        window.addEventListener('focus', refreshWhenVisible);
        document.addEventListener('visibilitychange', refreshWhenVisible);
        return () => {
            active = false;
            window.removeEventListener('focus', refreshWhenVisible);
            document.removeEventListener('visibilitychange', refreshWhenVisible);
        };
    }, [publicPath, pathname]);

    if (publicPath || pathname === '/mesa-control') return null;

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
            window.sessionStorage.removeItem(SESSION_CACHE_KEY);
            router.replace('/login');
            router.refresh();
        }
    }

    return (
        <>
        <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="fixed left-3 top-3 z-40 rounded-full border border-slate-200 bg-white p-2.5 text-slate-600 shadow-lg md:hidden"
            aria-label="Abrir menú"
        >
            <Menu className="h-5 w-5" />
        </button>
        {mobileOpen && <button aria-label="Cerrar menú" onClick={() => setMobileOpen(false)} className="fixed inset-0 z-40 bg-slate-950/45 md:hidden" />}
        <aside className={`fixed inset-y-0 left-0 z-50 flex h-[100dvh] min-h-0 w-[min(86vw,20rem)] shrink-0 flex-col overflow-visible border-r bg-white shadow-2xl transition-transform duration-200 md:relative md:z-20 md:h-screen md:translate-x-0 md:shadow-none ${mobileOpen ? 'translate-x-0' : '-translate-x-full'} ${collapsed ? 'md:w-20' : 'md:w-64'}`}>
            <div className="flex min-h-52 flex-none flex-col items-center justify-center gap-2 border-b px-3 py-4">
                <img src="/logo.png" alt="TAIICO CRM" className={`w-auto transition-all ${collapsed ? 'h-12' : 'h-20'}`} />
                {!collapsed && (
                    <p className="w-full text-center text-xs leading-4 text-slate-500">
                        Sesión iniciada como:
                        <span className="block break-all font-semibold text-slate-700">{username || 'Cargando...'}</span>
                    </p>
                )}
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
                <SmartLink
                    href="/cambiar-password"
                    className={`flex items-center justify-center rounded-md px-2 py-1.5 text-sm font-medium text-slate-500 hover:bg-blue-50 hover:text-blue-700 ${collapsed ? '' : 'w-full'}`}
                    aria-label="Cambiar contraseña"
                    title="Cambiar contraseña"
                >
                    <KeyRound className={`h-4 w-4 ${collapsed ? '' : 'mr-2'}`} />
                    {!collapsed && <span>Cambiar contraseña</span>}
                </SmartLink>
                <button
                    type="button"
                    onClick={() => setCollapsed((current) => !current)}
                    className="absolute -right-3 top-4 z-20 hidden rounded-full border border-slate-200 bg-white p-1.5 text-slate-500 shadow-md hover:bg-slate-50 hover:text-slate-800 md:block"
                    aria-label={collapsed ? 'Mostrar barra lateral' : 'Ocultar barra lateral'}
                    title={collapsed ? 'Mostrar barra lateral' : 'Ocultar barra lateral'}
                >
                    {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
                </button>
                <button type="button" onClick={() => setMobileOpen(false)} className="absolute right-3 top-3 rounded-full p-2 text-slate-500 hover:bg-slate-100 md:hidden" aria-label="Cerrar menú"><X className="h-5 w-5" /></button>
            </div>
            <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto overscroll-contain px-2 py-4 [scrollbar-gutter:stable]">
                {NAV_ITEMS.filter((item) => canShowModule(item.module, permissions) && (item.href !== '/mesa-control' || mesaAccess)).map((item) => (
                    <SmartLink
                        key={item.name}
                        href={item.href}
                        onClick={() => setMobileOpen(false)}
                        className={`group flex items-center rounded-md px-2 py-2.5 text-sm font-medium text-gray-600 hover:bg-gray-50 hover:text-gray-900 ${collapsed ? 'md:justify-center' : ''}`}
                        title={collapsed ? item.name : undefined}
                    >
                        <item.icon className={`h-5 w-5 shrink-0 text-gray-400 group-hover:text-gray-500 ${collapsed ? '' : 'mr-3'}`} />
                        <span className={collapsed ? 'md:hidden' : ''}>{item.name}</span>
                    </SmartLink>
                ))}
            </nav>
            <IdleModulePrefetch permissions={permissions} />
        </aside>
        </>
    );
}
