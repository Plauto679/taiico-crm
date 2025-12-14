import Link from 'next/link';
import { Home, DollarSign, Calendar, Users, BarChart3 } from 'lucide-react';

const NAV_ITEMS = [
    { name: 'Inicio', href: '/', icon: Home },
    { name: 'Cobranza', href: '/cobranza', icon: DollarSign },
    { name: 'Renovaciones', href: '/renovaciones', icon: Calendar },
    { name: 'Cartera', href: '/cartera', icon: Users },
    { name: 'Dashboards', href: '/dashboards', icon: BarChart3 },
];

export function Sidebar() {
    return (
        <div className="flex h-screen w-64 flex-col border-r bg-white">
            <div className="flex h-32 items-center justify-center border-b px-4">
                <img src="/logo.png" alt="TAIICO CRM" className="h-20 w-auto" />
            </div>
            <nav className="flex-1 space-y-1 px-2 py-4">
                {NAV_ITEMS.map((item) => (
                    <Link
                        key={item.name}
                        href={item.href}
                        className="group flex items-center rounded-md px-2 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                    >
                        <item.icon className="mr-3 h-5 w-5 text-gray-400 group-hover:text-gray-500" />
                        {item.name}
                    </Link>
                ))}
            </nav>
        </div>
    );
}
