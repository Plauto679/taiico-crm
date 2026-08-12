'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { fetchFromApi } from '@/lib/api';

export default function LoginPage() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const router = useRouter();

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError('');

        try {
            await fetchFromApi('/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password }),
            });

            window.localStorage.setItem('taiico_last_activity', String(Date.now()));
            router.push('/');
        } catch {
            setError('Credenciales inválidas. Por favor intente de nuevo.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 px-6 py-10">
            <div
                className="absolute inset-0 bg-cover bg-center"
                style={{ backgroundImage: "url('/taiico-wall-login.jpg')" }}
                aria-hidden="true"
            />
            <div className="absolute inset-0 bg-gradient-to-br from-slate-950/80 via-[#0b3554]/55 to-slate-950/75" aria-hidden="true" />
            <div className="absolute left-10 top-10 h-40 w-40 rounded-full bg-cyan-400/20 blur-3xl" aria-hidden="true" />
            <div className="absolute bottom-10 right-10 h-56 w-56 rounded-full bg-blue-500/20 blur-3xl" aria-hidden="true" />

            <div className="relative w-full max-w-md space-y-8 rounded-3xl border border-white/25 bg-white/90 p-8 shadow-2xl shadow-slate-950/30 backdrop-blur-md">
                <div className="flex flex-col items-center">
                    <img src="/logo.png" alt="TAIICO CRM" className="mb-5 h-20 w-auto drop-shadow-lg" />
                    <p className="text-sm font-semibold uppercase tracking-[0.35em] text-blue-700">
                        TAIICO CRM
                    </p>
                    <h2 className="mt-3 text-center text-4xl font-extrabold text-slate-950">
                        Bienvenido
                    </h2>
                    <p className="mt-2 text-center text-sm text-slate-500">
                        Ingresa para continuar con la operación diaria.
                    </p>
                </div>
                <form className="mt-8 space-y-6" onSubmit={handleLogin}>
                    <div className="space-y-3">
                        <div>
                            <label htmlFor="username" className="sr-only">
                                Usuario
                            </label>
                            <input
                                id="username"
                                name="username"
                                type="text"
                                required
                                className="relative block w-full rounded-xl border border-slate-200 bg-white/95 px-4 py-3 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-500/15 sm:text-sm"
                                placeholder="Usuario"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                            />
                        </div>
                        <div>
                            <label htmlFor="password" className="sr-only">
                                Contraseña
                            </label>
                            <input
                                id="password"
                                name="password"
                                type="password"
                                required
                                className="relative block w-full rounded-xl border border-slate-200 bg-white/95 px-4 py-3 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-500/15 sm:text-sm"
                                placeholder="Contraseña"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                            />
                        </div>
                    </div>

                    {error && (
                        <div className="text-red-500 text-sm text-center">
                            {error}
                        </div>
                    )}

                    <div>
                        <button
                            type="submit"
                            disabled={isLoading}
                            className="group relative flex w-full justify-center rounded-xl border border-transparent bg-blue-600 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 transition hover:-translate-y-0.5 hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-500/20 disabled:translate-y-0 disabled:opacity-50"
                        >
                            {isLoading ? 'Iniciando...' : 'Ingresar'}
                        </button>
                    </div>
                    <div className="text-center">
                        <Link
                            href="/olvide-password"
                            className="text-sm font-semibold text-blue-700 hover:text-blue-900"
                        >
                            ¿Olvidaste tu contraseña?
                        </Link>
                    </div>
                </form>
            </div>
        </div>
    );
}
