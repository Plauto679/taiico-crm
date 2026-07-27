'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Suspense, useState } from 'react';
import { fetchFromApi } from '@/lib/api';

function ResetPasswordForm() {
    const searchParams = useSearchParams();
    const token = searchParams.get('token') || '';
    const [password, setPassword] = useState('');
    const [confirmation, setConfirmation] = useState('');
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    async function handleSubmit(event: React.FormEvent) {
        event.preventDefault();
        setError('');
        if (password !== confirmation) {
            setError('Las contraseñas no coinciden.');
            return;
        }
        setLoading(true);
        try {
            await fetchFromApi('/password/reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token, new_password: password }),
            });
            setMessage('Tu contraseña fue actualizada. Ya puedes iniciar sesión.');
            setPassword('');
            setConfirmation('');
        } catch (requestError) {
            setError(requestError instanceof Error ? requestError.message : 'No fue posible cambiar la contraseña.');
        } finally {
            setLoading(false);
        }
    }

    return (
        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
            {!token && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">El enlace no contiene un token válido.</p>}
            <input
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Nueva contraseña"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
            <input
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                placeholder="Confirmar nueva contraseña"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
            {message && <p className="rounded-md bg-green-50 p-3 text-sm text-green-800">{message}</p>}
            {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
            <button
                type="submit"
                disabled={loading || !token || Boolean(message)}
                className="w-full rounded-md bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
                {loading ? 'Guardando...' : 'Restablecer contraseña'}
            </button>
            <Link href="/login" className="block text-center text-sm text-blue-600 hover:text-blue-800">
                Volver a iniciar sesión
            </Link>
        </form>
    );
}

export default function ResetPasswordPage() {
    return (
        <div className="flex min-h-screen items-center justify-center bg-gray-100 px-4">
            <div className="w-full max-w-md rounded-xl bg-white p-8 shadow-lg">
                <div className="flex flex-col items-center">
                    <img src="/logo.png" alt="TAIICO CRM" className="mb-6 h-16 w-auto" />
                    <h1 className="text-2xl font-bold text-gray-900">Restablecer contraseña</h1>
                </div>
                <Suspense fallback={<p className="mt-6 text-center text-gray-600">Cargando...</p>}>
                    <ResetPasswordForm />
                </Suspense>
            </div>
        </div>
    );
}
